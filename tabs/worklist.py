"""
tabs/worklist.py
Radiology2u RIS — Imaging Worklist tab.
Two sub-tabs: Active Orders (non-finalised) and Study History (finalised).
"""

from datetime import date

import pandas as pd
import streamlit as st

from sheets_db import get_referral_by_id, get_worklist, update_referral, update_referral_status
from tabs.constants import (
    ALL_MODALITIES,
    ALL_STATUSES,
    ALL_URGENCIES,
    STATUS_ICON,
    URGENCY_ICON,
)

_ACTIVE_STATUSES  = ["Pending", "Scheduled", "In Progress"]
_HISTORY_STATUSES = ["Reported", "Cancelled"]


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

    with st.expander("Clinical Details"):
        st.markdown(f"**Clinical Indication:**\n\n{rec.get('clinical_indication','—')}")
        if rec.get("relevant_history"):
            st.markdown(f"**History:** {rec['relevant_history']}")
        if rec.get("medications"):
            st.markdown(f"**Medications:** {rec['medications']}")
        if rec.get("investigations"):
            st.markdown(f"**Investigations Done:** {rec['investigations']}")
        if rec.get("special_requirements"):
            st.markdown(f"**Special Requirements:** {rec['special_requirements']}")

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

