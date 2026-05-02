"""
tabs/worklist.py
Radiology2u RIS — Imaging Worklist tab.
Two sub-tabs: Active Orders (non-finalised) and Study History (finalised).
"""

from datetime import date

import pandas as pd
import streamlit as st

from sheets_db import (
    get_documents_for_referral, get_referral_by_id, get_worklist,
    save_report, get_report_by_referral,
    update_referral, update_referral_status,
    delete_document_metadata,
)
from local_storage import download_document, upload_document, delete_document
from pdf_generator import generate_report_pdf
from sheets_db import save_document_metadata
from tabs.constants import (
    ALL_MODALITIES,
    ALL_STATUSES,
    ALL_URGENCIES,
    STATUS_ICON,
    URGENCY_ICON,
)

_ACTIVE_STATUSES  = ["Pending", "Scheduled", "In Progress"]
_HISTORY_STATUSES = ["Reported", "Cancelled"]

_CATEGORY_LABEL = {
    "referral_pdf":       ("📄", "Referral PDF"),
    "final_report":       ("📋", "Final Report"),
    "worksheet":          ("🔬", "Sonographer Worksheet"),
    "prior_report":       ("📑", "Prior Imaging Report"),
    "referral_letter":    ("✉️",  "Referral Letter"),
    "supporting_document":("📎", "Supporting Document"),
}


def _render_documents(referral_id: str, key_suffix: str) -> None:
    """Expander showing all attached documents with download/preview/delete."""
    docs = get_documents_for_referral(referral_id)
    label = f"📎 Documents ({len(docs)})" if docs else "📎 Documents (none)"
    with st.expander(label, expanded=False):
        if not docs:
            st.caption("No documents attached to this study.")
            return
        for i, doc in enumerate(docs):
            fname    = doc.get("file_name", "Document")
            fid      = doc.get("storage_file_id", "")
            mime     = doc.get("mime_type", "")
            category = doc.get("category", "")
            doc_id   = doc.get("document_id", "")
            size_kb  = round(int(doc.get("file_size_bytes") or 0) / 1024, 1)
            cat_icon, cat_label = _CATEGORY_LABEL.get(category, ("📎", category.replace("_", " ").title()))

            col_info, col_dl, col_del = st.columns([5, 1.5, 1.5])
            with col_info:
                st.markdown(f"{cat_icon} **{fname}** &nbsp; `{size_kb} KB` &nbsp; "
                            f"<span style='color:gray;font-size:0.8rem'>{cat_label}</span>",
                            unsafe_allow_html=True)

            confirm_key = f"del_confirm_{key_suffix}_{referral_id}_{i}"

            if fid:
                file_bytes = download_document(fid)
                if file_bytes:
                    with col_dl:
                        st.download_button(
                            label="⬇️",
                            data=file_bytes,
                            file_name=fname,
                            mime=mime or "application/octet-stream",
                            use_container_width=True,
                            key=f"dl_{key_suffix}_{referral_id}_{i}",
                        )
                    if mime and mime.startswith("image/"):
                        st.image(file_bytes, caption=fname, width=600)
                    elif mime == "application/pdf":
                        import base64
                        b64 = base64.b64encode(file_bytes).decode()
                        st.markdown(
                            f'<iframe src="data:application/pdf;base64,{b64}" '
                            f'width="100%" height="500px" style="border:1px solid #ddd;'
                            f'border-radius:6px;"></iframe>',
                            unsafe_allow_html=True,
                        )
                else:
                    with col_dl:
                        st.caption("Not found")
            else:
                with col_dl:
                    st.caption("No file")

            # Delete with one-click confirm
            with col_del:
                if not st.session_state.get(confirm_key):
                    if st.button("🗑️", key=f"del_{key_suffix}_{referral_id}_{i}",
                                 use_container_width=True, help="Delete this file"):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    if st.button("⚠️ Confirm", key=f"delok_{key_suffix}_{referral_id}_{i}",
                                 use_container_width=True, type="primary"):
                        if fid:
                            delete_document(fid)
                        if doc_id:
                            delete_document_metadata(doc_id)
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
                    if st.button("Cancel", key=f"delcancel_{key_suffix}_{referral_id}_{i}",
                                 use_container_width=True):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()


def _detail_panel(rec: dict, ks: str, tbl_ver_key: str, sel_acc_key: str) -> None:
    """Order detail + status update + edit form. ks = key suffix to avoid collisions."""
    st.markdown("---")
    hdr_col, close_col = st.columns([8, 1])
    with hdr_col:
        st.markdown(
            f"### {rec.get('lastname', '')}, {rec.get('firstname', '')}  "
            f"<span style='font-size:0.85rem;color:gray'>"
            f"Accession: {rec.get('accession_number', '—')}</span>",
            unsafe_allow_html=True,
        )
    with close_col:
        if st.button("✕ Close", key=f"close_{ks}_{rec['referral_id']}",
                     use_container_width=True):
            st.session_state.pop(sel_acc_key, None)
            st.rerun()

    d1, d2, d3 = st.columns(3)
    d1.markdown(f"**DOB:** {rec.get('dob', '—')}")
    d1.markdown(f"**Medicare:** {rec.get('medicare', '—')}")
    d2.markdown(f"**Modality:** {rec.get('modality', '—')}")
    d2.markdown(f"**Examination:** {rec.get('body_region', '—')}")
    d2.markdown(
        f"**Urgency:** {URGENCY_ICON.get(rec.get('urgency',''), '')} "
        f"{rec.get('urgency', '—')}"
    )
    d3.markdown(f"**Referring Dr:** {rec.get('referring_doctor', '—')}")
    d3.markdown(f"**Provider No:** {rec.get('provider_number', '—')}")
    d3.markdown(f"**Date Issued:** {rec.get('referral_date', '—')}")

    if rec.get("allergies"):
        st.error(f"⚠️ **Allergies / ADR:** {rec['allergies']}")

    st.markdown("**Update Order Status:**")
    ns_col, sv_col = st.columns([3, 1])
    cur_idx = ALL_STATUSES.index(rec["status"]) if rec["status"] in ALL_STATUSES else 0
    new_status = ns_col.selectbox(
        "New Status", ALL_STATUSES, index=cur_idx,
        key=f"ns_{ks}_{rec['referral_id']}",
    )
    with sv_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Save", key=f"sv_{ks}_{rec['referral_id']}",
                     use_container_width=True):
            update_referral_status(rec["referral_id"], new_status)
            st.success(f"Status updated to **{new_status}**.")
            st.session_state[tbl_ver_key] += 1
            st.rerun()

    st.markdown("---")
    with st.expander("✏️ Edit Order & Referring Doctor Details", expanded=False):
        rid = rec["referral_id"]

        st.markdown("**Referring Doctor**")
        ec1, ec2 = st.columns(2)
        with ec1:
            e_ref_dr   = st.text_input("Referring Doctor",
                                       value=rec.get("referring_doctor", ""),
                                       key=f"e_refdr_{ks}_{rid}")
            e_provider = st.text_input("Provider Number",
                                       value=rec.get("provider_number", ""),
                                       key=f"e_prov_{ks}_{rid}")
            e_practice = st.text_input("Practice / Clinic",
                                       value=rec.get("practice", ""),
                                       key=f"e_prac_{ks}_{rid}")
        with ec2:
            e_dr_phone = st.text_input("Doctor Phone",
                                       value=rec.get("doctor_phone", ""),
                                       key=f"e_drph_{ks}_{rid}")
            e_dr_email = st.text_input("Doctor Email",
                                       value=rec.get("doctor_email", ""),
                                       key=f"e_drem_{ks}_{rid}")

        st.markdown("**Order Details**")
        oc1, oc2 = st.columns(2)
        with oc1:
            e_clinic   = st.text_input("Referred To (Facility)",
                                       value=rec.get("to_clinic", ""),
                                       key=f"e_clinic_{ks}_{rid}")
            e_modality = st.selectbox(
                "Modality", ALL_MODALITIES,
                index=ALL_MODALITIES.index(rec["modality"])
                      if rec.get("modality") in ALL_MODALITIES else 0,
                key=f"e_mod_{ks}_{rid}",
            )
            e_body     = st.text_input("Body Region / Examination",
                                       value=rec.get("body_region", ""),
                                       key=f"e_body_{ks}_{rid}")
            e_urgency  = st.selectbox(
                "Urgency", ALL_URGENCIES[::-1],
                index=ALL_URGENCIES[::-1].index(rec["urgency"])
                      if rec.get("urgency") in ALL_URGENCIES else 0,
                key=f"e_urg_{ks}_{rid}",
            )
        with oc2:
            e_indication = st.text_area("Clinical Indication",
                                        value=rec.get("clinical_indication", ""),
                                        key=f"e_ind_{ks}_{rid}", height=90)
            e_allergies  = st.text_input("Allergies / ADR",
                                         value=rec.get("allergies", ""),
                                         key=f"e_allerg_{ks}_{rid}")
            e_special    = st.text_area("Special Requirements",
                                        value=rec.get("special_requirements", ""),
                                        key=f"e_spec_{ks}_{rid}", height=70)

        if st.button("💾 Save Order Changes", key=f"save_order_{ks}_{rid}",
                     use_container_width=True, type="primary"):
            update_referral(rid, {
                "referring_doctor":     e_ref_dr.strip(),
                "provider_number":      e_provider.strip(),
                "practice":             e_practice.strip(),
                "doctor_phone":         e_dr_phone.strip(),
                "doctor_email":         e_dr_email.strip(),
                "to_clinic":            e_clinic.strip(),
                "modality":             e_modality,
                "body_region":          e_body.strip(),
                "urgency":              e_urgency,
                "clinical_indication":  e_indication.strip(),
                "allergies":            e_allergies.strip(),
                "special_requirements": e_special.strip(),
            })
            st.success("✅ Order updated.")
            st.session_state[tbl_ver_key] += 1
            st.rerun()

    # ── Side-by-side: reference (left) + reporting (right) ───────────────────
    rid          = rec["referral_id"]
    acc          = rec.get("accession_number", rid)
    existing_rpt = get_report_by_referral(rid)

    # Load report defaults once outside the columns to avoid widget-key issues
    default_findings        = (existing_rpt or {}).get("findings", "")
    default_impression      = (existing_rpt or {}).get("impression", "")
    default_conclusion      = (existing_rpt or {}).get("conclusion", "")
    default_radiologist     = (existing_rpt or {}).get("radiologist", "")
    default_status          = (existing_rpt or {}).get("status", "Draft")
    default_perf_clinician  = (existing_rpt or {}).get("performing_clinician", "")

    st.markdown("---")
    ref_col, rpt_col = st.columns([11, 10], gap="large")

    # ── LEFT: Reference panel — clinical summary + documents ─────────────────
    with ref_col:
        st.markdown(
            "<span style='font-weight:600;font-size:1rem;color:#3a1c71'>"
            "📂 Reference — Clinical &amp; Documents</span>",
            unsafe_allow_html=True,
        )
        with st.container(height=680, border=True):
            if rec.get("clinical_indication"):
                st.markdown("**🩺 Clinical Indication**")
                st.info(rec["clinical_indication"])
            for _field, _label in [
                ("relevant_history",    "Relevant History"),
                ("medications",         "Medications"),
                ("investigations",      "Investigations Done"),
                ("special_requirements","Special Requirements"),
            ]:
                if rec.get(_field):
                    st.markdown(f"**{_label}:** {rec[_field]}")
            if rec.get("allergies"):
                st.error(f"⚠️ **Allergies / ADR:** {rec['allergies']}")

            docs = get_documents_for_referral(rid)
            st.markdown("---")
            st.markdown(f"**Attached Documents** ({len(docs)})")
            if not docs:
                st.caption("No documents attached to this study yet.")
            else:
                for i, doc in enumerate(docs):
                    fname    = doc.get("file_name", "Document")
                    fid      = doc.get("storage_file_id", "")
                    mime     = doc.get("mime_type", "")
                    category = doc.get("category", "")
                    doc_id   = doc.get("document_id", "")
                    size_kb  = round(int(doc.get("file_size_bytes") or 0) / 1024, 1)
                    cat_icon, cat_label = _CATEGORY_LABEL.get(
                        category, ("📎", category.replace("_", " ").title())
                    )
                    col_info, col_btn, col_del = st.columns([5, 1.5, 1.5])
                    with col_info:
                        st.markdown(
                            f"{cat_icon} **{fname}** &nbsp; `{size_kb} KB` &nbsp; "
                            f"<span style='color:gray;font-size:0.8rem'>{cat_label}</span>",
                            unsafe_allow_html=True,
                        )

                    confirm_key = f"ref_del_confirm_{ks}_{rid}_{i}"

                    if fid:
                        file_bytes = download_document(fid)
                        if file_bytes:
                            with col_btn:
                                st.download_button(
                                    label="⬇️",
                                    data=file_bytes,
                                    file_name=fname,
                                    mime=mime or "application/octet-stream",
                                    use_container_width=True,
                                    key=f"ref_dl_{ks}_{rid}_{i}",
                                )
                            if mime == "application/pdf":
                                import base64
                                b64 = base64.b64encode(file_bytes).decode()
                                st.markdown(
                                    f'<iframe src="data:application/pdf;base64,{b64}" '
                                    f'width="100%" height="480px" style="border:1px solid #ddd;'
                                    f'border-radius:6px;margin-top:4px"></iframe>',
                                    unsafe_allow_html=True,
                                )
                            elif mime and mime.startswith("image/"):
                                st.image(file_bytes, caption=fname, use_container_width=True)
                        else:
                            with col_btn:
                                st.caption("Not found")
                    else:
                        with col_btn:
                            st.caption("No file")

                    with col_del:
                        if not st.session_state.get(confirm_key):
                            if st.button("🗑️", key=f"ref_del_{ks}_{rid}_{i}",
                                         use_container_width=True, help="Delete this file"):
                                st.session_state[confirm_key] = True
                                st.rerun()
                        else:
                            if st.button("⚠️ Confirm", key=f"ref_delok_{ks}_{rid}_{i}",
                                         use_container_width=True, type="primary"):
                                if fid:
                                    delete_document(fid)
                                if doc_id:
                                    delete_document_metadata(doc_id)
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
                            if st.button("Cancel", key=f"ref_delcancel_{ks}_{rid}_{i}",
                                         use_container_width=True):
                                st.session_state.pop(confirm_key, None)
                                st.rerun()

    # ── RIGHT: Report form ────────────────────────────────────────────────────
    with rpt_col:
        st.markdown(
            "<span style='font-weight:600;font-size:1rem;color:#3a1c71'>"
            "📝 Radiology Report</span>",
            unsafe_allow_html=True,
        )
        with st.container(height=680, border=True):
            rpt_status = st.selectbox(
                "Report Status",
                ["Draft", "Preliminary", "Final"],
                index=["Draft", "Preliminary", "Final"].index(default_status)
                      if default_status in ["Draft", "Preliminary", "Final"] else 0,
                key=f"rpt_status_{rid}",
            )
            rc1, rc2 = st.columns(2)
            with rc1:
                rpt_radiologist = st.text_input(
                    "Reporting Radiologist",
                    value=default_radiologist,
                    placeholder="Dr Firstname Lastname",
                    key=f"rpt_rad_{rid}",
                )
            with rc2:
                rpt_perf_clinician = st.text_input(
                    "Performing Clinician",
                    value=default_perf_clinician,
                    placeholder="Sonographer name",
                    key=f"rpt_perf_{rid}",
                )

            rpt_findings = st.text_area(
                "Findings",
                value=default_findings,
                height=180,
                placeholder="Describe the imaging findings in detail...",
                key=f"rpt_find_{rid}",
            )
            rpt_impression = st.text_area(
                "Impression",
                value=default_impression,
                height=110,
                placeholder="Summarise the key diagnostic impression...",
                key=f"rpt_imp_{rid}",
            )
            rpt_conclusion = st.text_area(
                "Conclusion / Recommendation",
                value=default_conclusion,
                height=80,
                placeholder="Recommended follow-up or clinical action...",
                key=f"rpt_conc_{rid}",
            )

            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("💾 Save Report (Draft)", use_container_width=True,
                             key=f"rpt_save_{rid}"):
                    save_report({
                        "referral_id":          rid,
                        "accession_number":     acc,
                        "medicare":             rec.get("medicare", ""),
                        "findings":             rpt_findings.strip(),
                        "impression":           rpt_impression.strip(),
                        "conclusion":           rpt_conclusion.strip(),
                        "radiologist":          rpt_radiologist.strip(),
                        "performing_clinician": rpt_perf_clinician.strip(),
                        "status":               rpt_status,
                    })
                    st.success("Report saved.")
                    st.rerun()

            with bc2:
                if st.button("✅ Finalise & Generate PDF", type="primary",
                             use_container_width=True, key=f"rpt_finalise_{rid}"):
                    if not rpt_findings.strip() and not rpt_impression.strip():
                        st.error("Findings or Impression are required before finalising.")
                    else:
                        save_report({
                            "referral_id":          rid,
                            "accession_number":     acc,
                            "medicare":             rec.get("medicare", ""),
                            "findings":             rpt_findings.strip(),
                            "impression":           rpt_impression.strip(),
                            "conclusion":           rpt_conclusion.strip(),
                            "radiologist":          rpt_radiologist.strip(),
                            "performing_clinician": rpt_perf_clinician.strip(),
                            "status":               "Final",
                        })
                        from sheets_db import find_patient_by_medicare
                        pat = find_patient_by_medicare(rec.get("medicare", "")) or {}
                        rpt_dict = {
                            "findings":             rpt_findings.strip(),
                            "impression":           rpt_impression.strip(),
                            "conclusion":           rpt_conclusion.strip(),
                            "radiologist":          rpt_radiologist.strip(),
                            "performing_clinician": rpt_perf_clinician.strip(),
                            "status":               "Final",
                        }
                        pdf_bytes = generate_report_pdf(pat, rec, rpt_dict)
                        pdf_name  = f"RPT_{acc}_{rec.get('lastname','')}.pdf"

                        from local_storage import is_local_storage_configured
                        patient_id   = pat.get("patient_id", rec.get("medicare", ""))
                        patient_name = f"{pat.get('firstname','')} {pat.get('lastname','')}".strip()
                        if is_local_storage_configured():
                            try:
                                up = upload_document(
                                    file_bytes=pdf_bytes,
                                    filename=pdf_name,
                                    mime_type="application/pdf",
                                    patient_id=patient_id,
                                    patient_name=patient_name,
                                    accession_number=acc,
                                    category="final_report",
                                )
                                save_document_metadata({
                                    "referral_id":      rid,
                                    "medicare":         rec.get("medicare", ""),
                                    "accession_number": acc,
                                    "file_name":        up.get("name", pdf_name),
                                    "mime_type":        "application/pdf",
                                    "file_size_bytes":  int(up.get("size", len(pdf_bytes))),
                                    "category":         "final_report",
                                    "storage_file_id":  up.get("id", ""),
                                    "storage_url":      up.get("webViewLink", ""),
                                })
                            except Exception as ex:
                                st.warning(f"Report saved but PDF storage failed: {ex}")

                        update_referral_status(rid, "Reported")
                        st.session_state[f"rpt_pdf_{rid}"] = pdf_bytes
                        st.session_state[f"rpt_fname_{rid}"] = pdf_name
                        st.session_state[tbl_ver_key] += 1
                        st.rerun()

            if st.session_state.get(f"rpt_pdf_{rid}"):
                st.download_button(
                    label="⬇️ Download Final Report PDF",
                    data=st.session_state[f"rpt_pdf_{rid}"],
                    file_name=st.session_state.get(f"rpt_fname_{rid}", f"RPT_{acc}.pdf"),
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"rpt_dl_{rid}",
                )


def _worklist_section(scope_statuses: list[str], tab_key: str) -> None:
    """Render filters + selectable table + inline detail panel for a status scope."""
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 1])
    with fc1:
        f_status = st.selectbox(
            "Filter by Status", ["All"] + scope_statuses,
            key=f"wl_{tab_key}_status",
        )
    with fc2:
        f_urgency = st.selectbox(
            "Filter by Urgency", ["All"] + ALL_URGENCIES[::-1],
            key=f"wl_{tab_key}_urgency",
        )
    with fc3:
        f_modality = st.selectbox(
            "Filter by Modality", ["All"] + ALL_MODALITIES,
            key=f"wl_{tab_key}_mod",
        )
    with fc4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", use_container_width=True,
                     key=f"wl_{tab_key}_refresh"):
            st.rerun()

    # Session state keys for this tab instance
    tbl_ver_key = f"wl_tbl_v_{tab_key}"
    sel_acc_key = f"wl_sel_{tab_key}"
    if tbl_ver_key not in st.session_state:
        st.session_state[tbl_ver_key] = 0

    rows = get_worklist(
        status=f_status,
        urgency=f_urgency,
        modality=f_modality,
        status_in=scope_statuses,
    )

    if not rows:
        st.info("No orders match the current filters.")
        st.session_state.pop(sel_acc_key, None)
        return

    df = pd.DataFrame(rows)
    df["urgency"] = df["urgency"].apply(lambda x: f"{URGENCY_ICON.get(x, '')} {x}")
    df["status"]  = df["status"].apply(lambda x: f"{STATUS_ICON.get(x, '')} {x}")
    df["⚠️"]      = df["allergies"].apply(lambda x: "⚠️" if x else "")

    display_df = df[[
        "accession_number", "patient_name", "dob", "medicare",
        "modality", "body_region", "urgency",
        "referring_doctor", "referral_date", "status", "⚠️",
    ]].rename(columns={
        "accession_number": "Accession No.",
        "patient_name":     "Patient",
        "dob":              "DOB",
        "medicare":         "Medicare",
        "modality":         "Modality",
        "body_region":      "Examination",
        "urgency":          "Urgency",
        "referring_doctor": "Referring Dr",
        "referral_date":    "Date",
        "status":           "Status",
    })

    st.caption(f"{len(df)} order(s) — click a row to view / edit")
    sel = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=min(38 * len(df) + 38, 520),
        on_select="rerun",
        selection_mode="single-row",
        key=f"wl_table_{tab_key}_{st.session_state[tbl_ver_key]}",
    )

    # If the user clicked a row, record its accession number (identity, not index)
    sel_rows = sel.selection.get("rows", [])
    if sel_rows:
        st.session_state[sel_acc_key] = rows[sel_rows[0]]["accession_number"]

    selected_acc = st.session_state.get(sel_acc_key)
    if not selected_acc:
        return

    rec = get_referral_by_id(selected_acc)
    if rec:
        _detail_panel(rec, ks=tab_key, tbl_ver_key=tbl_ver_key, sel_acc_key=sel_acc_key)


def render() -> None:
    """Render the Imaging Worklist tab."""

    st.subheader("Imaging Worklist", divider="blue")
    st.caption("All referral orders received by Radiology2u. Sorted by clinical urgency.")

    # ── Live metrics (all orders) ─────────────────────────────────────────────
    all_refs  = get_worklist()
    today_str = date.today().strftime("%d/%m/%Y")
    total     = len(all_refs)
    pending   = sum(1 for r in all_refs if r["status"] == "Pending")
    urgent    = sum(
        1 for r in all_refs
        if r["urgency"] in ("Emergency (same day)", "Urgent (within 7 days)")
        and r["status"] not in ("Reported", "Cancelled")
    )
    today_new = sum(1 for r in all_refs if r["referral_date"] == today_str)

    m1, m2, m3, m4 = st.columns(4)
    for col, num, label, color in [
        (m1, total,     "Total Orders",               "#1e3a5f"),
        (m2, pending,   "Awaiting Action",             "#e65c00"),
        (m3, urgent,    "Urgent / Emergency",          "#b71c1c"),
        (m4, today_new, f"New Today ({today_str})",    "#1b5e20"),
    ]:
        col.markdown(
            f'<div class="r2u-metric">'
            f'<div class="r2u-metric-num" style="color:{color}">{num}</div>'
            f'<div class="r2u-metric-label">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── Sub-tabs (radio triggers real reruns) ─────────────────────────────────
    _wl_section = st.radio(
        "Worklist section",
        ["📋  Active Orders", "📁  Study History"],
        horizontal=True,
        label_visibility="collapsed",
        key="_wl_nav",
    )

    _prev_wl = st.session_state.get("_prev_wl_nav", _wl_section)
    if _prev_wl != _wl_section:
        if _prev_wl == "📋  Active Orders":
            st.session_state.pop("wl_sel_act", None)
            st.session_state.pop("wl_tbl_v_act", None)
        else:
            st.session_state.pop("wl_sel_hist", None)
            st.session_state.pop("wl_tbl_v_hist", None)
    st.session_state["_prev_wl_nav"] = _wl_section

    if _wl_section == "📋  Active Orders":
        _worklist_section(_ACTIVE_STATUSES, "act")
    else:
        _worklist_section(_HISTORY_STATUSES, "hist")

