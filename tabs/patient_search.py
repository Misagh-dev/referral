"""
tabs/patient_search.py
Radiology2u RIS — Patients & Referrals tab.

Workflow:
  1. Register / New Patient  — demographics only → generates Patient ID.
  2. Search & Manage         — view patient list, edit, delete, or create a New Visit.
  3. New Visit Wizard        — 3-step free-navigation wizard:
       Step 1: Study / Request Details  → generates Accession Number
       Step 2: Referring Doctor
       Step 3: Documents (upload existing  OR  generate referral PDF → auto-attaches)
"""

from datetime import date

import pandas as pd
import streamlit as st

from local_storage import is_local_storage_configured, upload_document
from pdf_generator import generate_referral_pdf
from sheets_db import (
    create_referral,
    delete_patient,
    delete_referral,
    get_all_doctors,
    get_all_patients,
    get_documents_for_referral,
    get_doctor_by_id,
    get_patient_referrals,
    get_referral_by_id,
    register_patient,
    save_document_metadata,
    search_patients,
    update_patient,
    update_referral,
)
from tabs.constants import ALL_MODALITIES, ALL_URGENCIES, STATES, STATUS_ICON, URGENCY_ICON

_GENDERS     = ["", "Male", "Female", "Non-binary / Gender diverse", "Prefer not to say"]
_INDIGENOUS  = ["", "Neither", "Aboriginal", "Torres Strait Islander",
                "Both Aboriginal and Torres Strait Islander", "Prefer not to say"]
_INTERPRETER = ["No", "Yes"]
_TITLES      = ["Dr", "Prof", "A/Prof", "Mr", "Ms", "Mrs"]


# ── Reusable doctor helpers ────────────────────────────────────────────────────

def _doctor_lookup_widget(key_prefix: str) -> None:
    """Populate session-state doctor fields from the registry."""
    doctors = get_all_doctors()
    if not doctors:
        return
    with st.expander("🔍 Load a saved doctor from the registry", expanded=False):
        options = {
            f"{d['title']} {d['firstname']} {d['lastname']}  |  "
            f"Provider: {d['provider_number']}"
            + (f"  |  {d['practice']}" if d.get("practice") else ""): d["doctor_id"]
            for d in doctors
        }
        label_list = ["— Select a doctor —"] + list(options.keys())
        sel = st.selectbox("Doctor", label_list,
                           key=f"{key_prefix}lookup",
                           label_visibility="collapsed")
        if sel != "— Select a doctor —":
            lc, cc = st.columns([3, 1])
            with lc:
                if st.button("✅ Load into form", key=f"{key_prefix}btn_load",
                             use_container_width=True, type="primary"):
                    doc = get_doctor_by_id(options[sel])
                    if doc:
                        st.session_state[f"{key_prefix}title"] = doc.get("title", "Dr")
                        st.session_state[f"{key_prefix}fn"]    = doc.get("firstname", "")
                        st.session_state[f"{key_prefix}ln"]    = doc.get("lastname", "")
                        st.session_state[f"{key_prefix}prov"]  = doc.get("provider_number", "")
                        st.session_state[f"{key_prefix}hpii"]  = doc.get("hpii", "")
                        st.session_state[f"{key_prefix}prac"]  = doc.get("practice", "")
                        st.session_state[f"{key_prefix}addr"]  = doc.get("address", "")
                        st.session_state[f"{key_prefix}sub"]   = doc.get("suburb", "")
                        st.session_state[f"{key_prefix}state"] = doc.get("state", STATES[0])
                        st.session_state[f"{key_prefix}pc"]    = doc.get("postcode", "")
                        st.session_state[f"{key_prefix}ph"]    = doc.get("phone", "")
                        st.session_state[f"{key_prefix}fax"]   = doc.get("fax", "")
                        st.session_state[f"{key_prefix}email"] = doc.get("email", "")
                    st.rerun()
            with cc:
                if st.button("🗑️ Clear", key=f"{key_prefix}btn_clear",
                             use_container_width=True):
                    for _s in ("title","fn","ln","prov","hpii","prac","addr",
                               "sub","state","pc","ph","fax","email"):
                        st.session_state.pop(f"{key_prefix}{_s}", None)
                    st.rerun()


def _render_doctor_fields(key_prefix: str) -> dict:
    """Render doctor input fields using session-state defaults. Returns values dict."""
    d1, d2 = st.columns(2)
    with d1:
        title = st.selectbox(
            "Title", _TITLES,
            index=_TITLES.index(st.session_state.get(f"{key_prefix}title", "Dr"))
                  if st.session_state.get(f"{key_prefix}title", "Dr") in _TITLES else 0,
            key=f"{key_prefix}title",
        )
        fn   = st.text_input("First Name *",
                             value=st.session_state.get(f"{key_prefix}fn", ""),
                             key=f"{key_prefix}fn")
        ln   = st.text_input("Last Name *",
                             value=st.session_state.get(f"{key_prefix}ln", ""),
                             key=f"{key_prefix}ln")
        prov = st.text_input("Medicare Provider Number *",
                             value=st.session_state.get(f"{key_prefix}prov", ""),
                             key=f"{key_prefix}prov")
        hpii = st.text_input("HPI-I (optional)",
                             value=st.session_state.get(f"{key_prefix}hpii", ""),
                             placeholder="8003610000000000",
                             key=f"{key_prefix}hpii")
    with d2:
        prac  = st.text_input("Practice / Clinic Name",
                              value=st.session_state.get(f"{key_prefix}prac", ""),
                              key=f"{key_prefix}prac")
        addr  = st.text_input("Street Address",
                              value=st.session_state.get(f"{key_prefix}addr", ""),
                              key=f"{key_prefix}addr")
        sub   = st.text_input("Suburb",
                              value=st.session_state.get(f"{key_prefix}sub", ""),
                              key=f"{key_prefix}sub")
        state_list = STATES
        state_val  = st.session_state.get(f"{key_prefix}state", state_list[0])
        state_i    = state_list.index(state_val) if state_val in state_list else 0
        state = st.selectbox("State / Territory", state_list, index=state_i,
                             key=f"{key_prefix}state")
        pc    = st.text_input("Postcode", max_chars=4,
                              value=st.session_state.get(f"{key_prefix}pc", ""),
                              key=f"{key_prefix}pc")
        ph    = st.text_input("Phone",
                              value=st.session_state.get(f"{key_prefix}ph", ""),
                              key=f"{key_prefix}ph")
        fax   = st.text_input("Fax",
                              value=st.session_state.get(f"{key_prefix}fax", ""),
                              key=f"{key_prefix}fax")
        email = st.text_input("Email",
                              value=st.session_state.get(f"{key_prefix}email", ""),
                              key=f"{key_prefix}email")
    return {
        "title": title, "firstname": fn, "lastname": ln,
        "provider_number": prov, "hpii": hpii,
        "practice": prac, "address": addr, "suburb": sub,
        "state": state, "postcode": pc,
        "phone": ph, "fax": fax, "email": email,
    }


# ── New Visit Wizard steps ─────────────────────────────────────────────────────

def _visit_step1(mid: str) -> None:
    """Step 1 — Study / Request Details."""
    st.markdown("#### Step 1 — Study / Request Details")
    st.caption(
        "Fill in the imaging request details below. "
        "An **accession number** will be generated when the visit is saved."
    )

    today = date.today()
    try:
        default_valid = today.replace(year=today.year + 1)
    except ValueError:
        default_valid = today.replace(year=today.year + 1, day=28)

    o1, o2 = st.columns(2)
    with o1:
        st.text_input(
            "Referred To (Facility / Department) *",
            placeholder="e.g. Radiology2u — Mobile Ultrasound",
            key="nv_clinic",
        )
        st.selectbox("Imaging Modality *", ALL_MODALITIES, key="nv_modality")
        st.text_input(
            "Body Region / Examination *",
            placeholder="e.g. Abdomen and Pelvis",
            key="nv_body",
        )
    with o2:
        st.selectbox("Clinical Urgency *", ALL_URGENCIES[::-1], key="nv_urgency")
        st.date_input("Order Date *", value=today, key="nv_date")
        st.date_input("Valid Until (default 12 months)", value=default_valid,
                      key="nv_valid")

    st.text_area(
        "Clinical Indication / Reason for Referral *",
        placeholder="Describe the clinical reason and presenting complaint...",
        height=90, key="nv_indication",
    )
    st.text_area(
        "Relevant Medical History",
        placeholder="Past medical/surgical history, relevant conditions...",
        height=70, key="nv_history",
    )
    st.text_area(
        "Current Medications",
        placeholder="List relevant medications, doses and frequency...",
        height=70, key="nv_meds",
    )
    st.text_input(
        "Known Allergies / Adverse Drug Reactions",
        placeholder="e.g. Penicillin – anaphylaxis; Iodinated contrast – nausea",
        key="nv_allergies",
    )
    st.text_area(
        "Relevant Investigations Already Performed",
        placeholder="e.g. FBC/UEC normal (01/2026); Prior US 2024...",
        height=70, key="nv_invest",
    )
    st.text_area(
        "Special Requirements / Instructions",
        placeholder="e.g. Patient claustrophobic, requires sedation planning...",
        height=60, key="nv_special",
    )


def _visit_step2() -> None:
    """Step 2 — Referring Doctor."""
    st.markdown("#### Step 2 — Referring Doctor")
    st.caption(
        "Select a doctor from the registry or enter their details manually. "
        "To add a new doctor, go to ⚙️ **Settings → 👨‍⚕️ Doctor Registry**."
    )
    _doctor_lookup_widget("nv_dr_")
    _render_doctor_fields("nv_dr_")


def _visit_step3(mid: str, pat: dict) -> None:
    """Step 3 — Documents: upload existing or generate new referral PDF."""
    st.markdown("#### Step 3 — Documents")
    st.caption(
        "Upload any existing referral documents, or generate a new referral PDF "
        "from the information entered in Steps 1 and 2."
    )

    persisted_errors = st.session_state.pop("nv_upload_errors", None)
    if persisted_errors:
        st.warning("Visit saved, but some storage uploads failed:")
        for err in persisted_errors:
            st.caption(f"- {err}")

    # ── Upload section ────────────────────────────────────────────────────────
    with st.expander("📎 Upload Existing Documents", expanded=False):
        uploaded = st.file_uploader(
            "Upload referral letter, prior imaging reports, or other documents",
            accept_multiple_files=True,
            type=["pdf", "jpg", "jpeg", "png", "doc", "docx"],
            key="nv_uploads",
        )
        if uploaded:
            st.success(f"{len(uploaded)} file(s) selected and ready to upload on save.")
            for uf in uploaded:
                st.caption(f"📄 {uf.name}  ({round(uf.size / 1024, 1)} KB)")
        if not is_local_storage_configured():
            st.warning(
                "⚠️ Local document storage is not configured. "
                "Files can be selected, but uploads will fail until storage_base_url "
                "is set in Streamlit secrets."
            )

    st.markdown("---")

    # ── Generate referral PDF ─────────────────────────────────────────────────
    st.markdown("**Generate a New Referral PDF**")
    st.caption(
        "This will create a visit record (with a new accession number) and generate "
        "a referral PDF based on the study and doctor details from Steps 1 and 2."
    )

    # Collect step-1 values from session state
    nv_clinic     = st.session_state.get("nv_clinic", "").strip()
    nv_modality   = st.session_state.get("nv_modality", "")
    nv_body       = st.session_state.get("nv_body", "").strip()
    nv_urgency    = st.session_state.get("nv_urgency", "")
    nv_date       = st.session_state.get("nv_date", date.today())
    nv_valid      = st.session_state.get("nv_valid", date.today())
    nv_indication = st.session_state.get("nv_indication", "").strip()
    nv_history    = st.session_state.get("nv_history", "").strip()
    nv_meds       = st.session_state.get("nv_meds", "").strip()
    nv_allergies  = st.session_state.get("nv_allergies", "").strip()
    nv_invest     = st.session_state.get("nv_invest", "").strip()
    nv_special    = st.session_state.get("nv_special", "").strip()

    # Collect step-2 doctor values
    dr_title = st.session_state.get("nv_dr_title", "Dr")
    dr_fn    = st.session_state.get("nv_dr_fn", "").strip()
    dr_ln    = st.session_state.get("nv_dr_ln", "").strip()
    dr_prov  = st.session_state.get("nv_dr_prov", "").strip()
    dr_hpii  = st.session_state.get("nv_dr_hpii", "").strip()
    dr_prac  = st.session_state.get("nv_dr_prac", "").strip()
    dr_addr  = st.session_state.get("nv_dr_addr", "").strip()
    dr_sub   = st.session_state.get("nv_dr_sub", "").strip()
    dr_state = st.session_state.get("nv_dr_state", "")
    dr_pc    = st.session_state.get("nv_dr_pc", "").strip()
    dr_ph    = st.session_state.get("nv_dr_ph", "").strip()
    dr_fax   = st.session_state.get("nv_dr_fax", "").strip()
    dr_email = st.session_state.get("nv_dr_email", "").strip()

    # Once a visit has been generated, show result only — no re-generation allowed.
    if st.session_state.get("nv_pdf_bytes"):
        acc  = st.session_state["nv_accession"]
        last = st.session_state["nv_pt_lastname"]
        frst = st.session_state["nv_pt_firstname"]
        st.success(f"✅ Visit created — Accession: **{acc}**")
        st.download_button(
            label="⬇️ Download Referral PDF",
            data=st.session_state["nv_pdf_bytes"],
            file_name=f"R2U_{acc}_{last}_{frst}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="nv_dl_pdf",
        )
        st.caption(f"📎 R2U_{acc}_{last}_{frst}.pdf — attached to this visit record.")
    else:
        if st.button("📄 Generate Referral & Save Visit", type="primary",
                     use_container_width=True, key="nv_generate"):
            required = {
                "Referred-to facility":         nv_clinic,
                "Body region / examination":     nv_body,
                "Clinical indication":           nv_indication,
                "Referring doctor first name":   dr_fn,
                "Referring doctor last name":    dr_ln,
                "Medicare provider number":      dr_prov,
            }
            missing = [k for k, v in required.items() if not v]
            if missing:
                st.error(
                    "The following fields are required before generating:\n\n"
                    + "\n".join(f"- {m}" for m in missing)
                )
            else:
                referral_data = {
                    "medicare":             mid,
                    "to_clinic":            nv_clinic,
                    "modality":             nv_modality,
                    "body_region":          nv_body,
                    "urgency":              nv_urgency,
                    "date":                 nv_date.strftime("%d/%m/%Y") if hasattr(nv_date, "strftime") else str(nv_date),
                    "valid_until":          nv_valid.strftime("%d/%m/%Y") if hasattr(nv_valid, "strftime") else str(nv_valid),
                    "clinical_indication":  nv_indication,
                    "relevant_history":     nv_history,
                    "medications":          nv_meds,
                    "allergies":            nv_allergies,
                    "investigations":       nv_invest,
                    "special_requirements": nv_special,
                    "referring_doctor":     f"{dr_title} {dr_fn} {dr_ln}",
                    "provider_number":      dr_prov,
                    "practice":             dr_prac,
                    "doctor_phone":         dr_ph,
                    "doctor_email":         dr_email,
                }
                doctor_data = {
                    "title":           dr_title,
                    "firstname":       dr_fn,
                    "lastname":        dr_ln,
                    "provider_number": dr_prov,
                    "hpii":            dr_hpii,
                    "practice":        dr_prac,
                    "address":         f"{dr_addr}, {dr_sub} {dr_state} {dr_pc}".strip(", "),
                    "phone":           dr_ph,
                    "fax":             dr_fax,
                    "email":           dr_email,
                }
                patient_data = {
                    "patient_id":      pat.get("patient_id", ""),
                    "firstname":       pat.get("firstname", ""),
                    "lastname":        pat.get("lastname", ""),
                    "dob":             pat.get("dob", ""),
                    "gender":          pat.get("gender", ""),
                    "medicare":        mid,
                    "irn":             pat.get("irn", ""),
                    "medicare_expiry": pat.get("medicare_expiry", ""),
                    "dva":             pat.get("dva", ""),
                    "concession":      pat.get("concession", ""),
                    "indigenous":      pat.get("indigenous", ""),
                    "address":         pat.get("address", ""),
                    "phone":           pat.get("phone", ""),
                    "email":           pat.get("email", ""),
                    "ihi":             pat.get("ihi", ""),
                    "interpreter":     pat.get("interpreter", "No"),
                    "language":        pat.get("language", ""),
                }

                with st.spinner("Creating visit and generating PDF..."):
                    accession = create_referral(referral_data)
                    referral_data["accession_number"] = accession
                    pdf_bytes = generate_referral_pdf(patient_data, doctor_data, referral_data)

                    upload_errors: list[str] = []
                    created_ref = get_referral_by_id(accession) or {}
                    referral_id = created_ref.get("referral_id", "")
                    patient_id = pat.get("patient_id", "")
                    patient_name = (
                        f"{pat.get('firstname', '')} {pat.get('lastname', '')}"
                    ).strip()

                    pdf_name = f"R2U_{accession}_{pat.get('lastname', '')}_{pat.get('firstname', '')}.pdf"
                    if is_local_storage_configured():
                        try:
                            pdf_uploaded = upload_document(
                                file_bytes=pdf_bytes,
                                filename=pdf_name,
                                mime_type="application/pdf",
                                patient_id=patient_id,
                                patient_name=patient_name,
                                accession_number=accession,
                                category="referral_pdf",
                            )
                            save_document_metadata({
                                "referral_id": referral_id,
                                "medicare": mid,
                                "accession_number": accession,
                                "file_name": pdf_uploaded.get("name", pdf_name),
                                "mime_type": pdf_uploaded.get("mimeType", "application/pdf"),
                                "file_size_bytes": int(pdf_uploaded.get("size", len(pdf_bytes))),
                                "category": "referral_pdf",
                                "storage_file_id": pdf_uploaded.get("id", ""),
                                "storage_url": pdf_uploaded.get("webViewLink", ""),
                            })
                        except Exception as ex:
                            upload_errors.append(f"Referral PDF upload failed: {ex}")
                    else:
                        save_document_metadata({
                            "referral_id": referral_id,
                            "medicare": mid,
                            "accession_number": accession,
                            "file_name": pdf_name,
                            "mime_type": "application/pdf",
                            "file_size_bytes": len(pdf_bytes),
                            "category": "referral_pdf",
                            "storage_file_id": "",
                            "storage_url": "",
                        })

                    for uf in (uploaded or []):
                        try:
                            if is_local_storage_configured():
                                up = upload_document(
                                    file_bytes=uf.getvalue(),
                                    filename=uf.name,
                                    mime_type=getattr(uf, "type", "application/octet-stream"),
                                    patient_id=patient_id,
                                    patient_name=patient_name,
                                    accession_number=accession,
                                    category="supporting_document",
                                )
                                save_document_metadata({
                                    "referral_id": referral_id,
                                    "medicare": mid,
                                    "accession_number": accession,
                                    "file_name": up.get("name", uf.name),
                                    "mime_type": up.get("mimeType", getattr(uf, "type", "application/octet-stream")),
                                    "file_size_bytes": int(up.get("size", uf.size)),
                                    "category": "supporting_document",
                                    "storage_file_id": up.get("id", ""),
                                    "storage_url": up.get("webViewLink", ""),
                                })
                            else:
                                save_document_metadata({
                                    "referral_id": referral_id,
                                    "medicare": mid,
                                    "accession_number": accession,
                                    "file_name": uf.name,
                                    "mime_type": getattr(uf, "type", "application/octet-stream"),
                                    "file_size_bytes": uf.size,
                                    "category": "supporting_document",
                                    "storage_file_id": "",
                                    "storage_url": "",
                                })
                        except Exception as ex:
                            upload_errors.append(f"{uf.name}: {ex}")

                    if upload_errors:
                        st.session_state["nv_upload_errors"] = upload_errors

                st.session_state["nv_pdf_bytes"]    = pdf_bytes
                st.session_state["nv_accession"]    = accession
                st.session_state["nv_pt_lastname"]  = pat.get("lastname", "")
                st.session_state["nv_pt_firstname"] = pat.get("firstname", "")
                st.rerun()

        # ── Save visit without generating PDF ────────────────────────────────
        st.markdown("---")
        st.caption(
            "Alternatively, save the visit without generating a new PDF "
            "(e.g. when the referral was already uploaded above)."
        )
        if st.button("💾 Save Visit (no PDF)", use_container_width=True,
                     key="nv_save_only"):
            if not nv_body.strip() or not nv_indication.strip():
                st.error("Body region and clinical indication are required to save a visit.")
            else:
                referral_data = {
                    "medicare":             mid,
                    "to_clinic":            nv_clinic or "—",
                    "modality":             nv_modality,
                    "body_region":          nv_body,
                    "urgency":              nv_urgency,
                    "date":                 nv_date.strftime("%d/%m/%Y") if hasattr(nv_date, "strftime") else str(nv_date),
                    "valid_until":          nv_valid.strftime("%d/%m/%Y") if hasattr(nv_valid, "strftime") else str(nv_valid),
                    "clinical_indication":  nv_indication,
                    "relevant_history":     nv_history,
                    "medications":          nv_meds,
                    "allergies":            nv_allergies,
                    "investigations":       nv_invest,
                    "special_requirements": nv_special,
                    "referring_doctor":     f"{dr_title} {dr_fn} {dr_ln}".strip(),
                    "provider_number":      dr_prov,
                    "practice":             dr_prac,
                    "doctor_phone":         dr_ph,
                    "doctor_email":         dr_email,
                }
                accession = create_referral(referral_data)
                upload_errors: list[str] = []
                created_ref = get_referral_by_id(accession) or {}
                referral_id = created_ref.get("referral_id", "")
                patient_id = pat.get("patient_id", "")
                patient_name = (
                    f"{pat.get('firstname', '')} {pat.get('lastname', '')}"
                ).strip()
                for uf in (uploaded or []):
                    try:
                        if is_local_storage_configured():
                            up = upload_document(
                                file_bytes=uf.getvalue(),
                                filename=uf.name,
                                mime_type=getattr(uf, "type", "application/octet-stream"),
                                patient_id=patient_id,
                                patient_name=patient_name,
                                accession_number=accession,
                                category="supporting_document",
                            )
                            save_document_metadata({
                                "referral_id": referral_id,
                                "medicare": mid,
                                "accession_number": accession,
                                "file_name": up.get("name", uf.name),
                                "mime_type": up.get("mimeType", getattr(uf, "type", "application/octet-stream")),
                                "file_size_bytes": int(up.get("size", uf.size)),
                                "category": "supporting_document",
                                "storage_file_id": up.get("id", ""),
                                "storage_url": up.get("webViewLink", ""),
                            })
                        else:
                            save_document_metadata({
                                "referral_id": referral_id,
                                "medicare": mid,
                                "accession_number": accession,
                                "file_name": uf.name,
                                "mime_type": getattr(uf, "type", "application/octet-stream"),
                                "file_size_bytes": uf.size,
                                "category": "supporting_document",
                                "storage_file_id": "",
                                "storage_url": "",
                            })
                    except Exception as ex:
                        upload_errors.append(f"{uf.name}: {ex}")
                st.success(f"✅ Visit saved — Accession: **{accession}**")
                if upload_errors:
                    st.warning("Visit saved, but some storage uploads failed:")
                    for err in upload_errors:
                        st.caption(f"- {err}")
                st.session_state.pop("ps_action", None)
                st.rerun()


# ── Main render ────────────────────────────────────────────────────────────────

def render(cfg: dict | None = None) -> None:
    """Render the Patients & Referrals tab."""

    if cfg is None:
        cfg = {}

    st.subheader("🏥 Patients & Referrals", divider="blue")

    _ps_section = st.radio(
        "Section",
        ["➕  Register / New Patient", "🔍  Search & Manage"],
        horizontal=True,
        label_visibility="collapsed",
        key="_ps_nav",
    )
    _prev_ps = st.session_state.get("_prev_ps_nav", _ps_section)
    if _prev_ps != _ps_section:
        _to_clear = (
            ["rp_"]
            if _prev_ps == "➕  Register / New Patient"
            else ["ps_", "nv_", "edit_", "act_", "ps_selected_mid", "ps_action"]
        )
        for _k in list(st.session_state.keys()):
            for _pfx in _to_clear:
                if _k == _pfx or _k.startswith(_pfx):
                    try:
                        del st.session_state[_k]
                    except KeyError:
                        pass
                    break
    st.session_state["_prev_ps_nav"] = _ps_section

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION: REGISTER / NEW PATIENT
    # ══════════════════════════════════════════════════════════════════════════
    if _ps_section == "➕  Register / New Patient":
        st.markdown(
            '<p class="r2u-required-note">Fields marked <strong>*</strong> are required.</p>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="r2u-section">Patient Demographics</div>',
                    unsafe_allow_html=True)

        r1, r2 = st.columns(2)
        with r1:
            rp_medicare = st.text_input(
                "Medicare Number *", placeholder="1234 56789 0", key="rp_medicare"
            )
            rp_irn = st.number_input(
                "IRN (Individual Reference Number)", min_value=1, max_value=9,
                value=1, step=1, key="rp_irn"
            )
            rp_medicare_expiry = st.text_input(
                "Medicare Expiry (MM/YYYY)", placeholder="01/2028", key="rp_mex"
            )
            rp_dva = st.text_input("DVA File Number (if applicable)", key="rp_dva")
            rp_concession = st.text_input(
                "Concession / Health Care Card No.", key="rp_conc"
            )
            rp_ihi = st.text_input(
                "IHI — Individual Healthcare Identifier",
                placeholder="8003608000000000", key="rp_ihi"
            )
        with r2:
            rp_lastname  = st.text_input("Surname *", key="rp_ln")
            rp_firstname = st.text_input("First Name *", key="rp_fn")
            rp_dob = st.date_input(
                "Date of Birth *",
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                key="rp_dob",
            )
            rp_gender = st.selectbox("Gender", _GENDERS, key="rp_gender")
            rp_indigenous = st.selectbox(
                "Aboriginal / Torres Strait Islander Status",
                _INDIGENOUS, key="rp_indigenous"
            )

        r3, r4 = st.columns(2)
        with r3:
            rp_address = st.text_input(
                "Home Address", placeholder="1 Example St", key="rp_addr"
            )
            rp_suburb = st.text_input("Suburb", key="rp_sub")
        with r4:
            rp_state    = st.selectbox("State / Territory", STATES, key="rp_state")
            rp_postcode = st.text_input("Postcode", max_chars=4, key="rp_pc")
            rp_phone    = st.text_input("Phone", placeholder="0400 000 000",
                                        key="rp_ph")
            rp_email    = st.text_input("Email", placeholder="patient@email.com",
                                        key="rp_email")

        r5, r6 = st.columns(2)
        with r5:
            rp_interpreter = st.selectbox(
                "Interpreter Required?", _INTERPRETER, key="rp_interp"
            )
        with r6:
            rp_language = st.text_input(
                "Language (if interpreter needed)", key="rp_lang"
            )

        st.markdown("---")
        if st.button("💾 Register Patient", type="primary",
                     use_container_width=True, key="btn_reg_patient"):
            medicare_clean = rp_medicare.replace(" ", "")
            if not medicare_clean or not rp_lastname.strip() or not rp_firstname.strip():
                st.error("Medicare number, surname, and first name are required.")
            else:
                pid = register_patient({
                    "medicare":        rp_medicare.strip(),
                    "irn":             rp_irn,
                    "lastname":        rp_lastname.strip(),
                    "firstname":       rp_firstname.strip(),
                    "dob":             rp_dob.strftime("%d/%m/%Y"),
                    "gender":          rp_gender,
                    "indigenous":      rp_indigenous,
                    "medicare_expiry": rp_medicare_expiry.strip(),
                    "dva":             rp_dva.strip(),
                    "concession":      rp_concession.strip(),
                    "address": (
                        f"{rp_address.strip()}, {rp_suburb.strip()} "
                        f"{rp_state} {rp_postcode.strip()}"
                    ).strip(", "),
                    "phone":           rp_phone.strip(),
                    "email":           rp_email.strip(),
                    "ihi":             rp_ihi.strip(),
                    "interpreter":     rp_interpreter,
                    "language":        rp_language.strip(),
                })
                st.success(
                    f"✅ **{rp_firstname.strip()} {rp_lastname.strip()}** registered — "
                    f"Patient ID: **{pid}**"
                )

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION: SEARCH & MANAGE
    # ══════════════════════════════════════════════════════════════════════════
    else:
        sc1, sc2 = st.columns([4, 1])
        with sc1:
            search_q = st.text_input(
                "Search patients",
                placeholder="Filter by name, Medicare number, or Patient ID...",
                key="ps_query",
                label_visibility="collapsed",
            )
        with sc2:
            search_btn = st.button("🔍 Search", use_container_width=True, key="ps_btn")

        if search_btn and search_q.strip():
            results = search_patients(search_q.strip())
        else:
            results = get_all_patients()

        if not results:
            st.info(
                "No patients registered yet. "
                "Use the **➕ Register / New Patient** section to add patients."
            )
            return

        st.caption(f"{len(results)} patient(s) — click a row to manage")

        pt_df = pd.DataFrame(results)[[
            "patient_id", "medicare", "irn", "lastname", "firstname", "dob",
            "gender", "phone", "address", "date_registered",
        ]].rename(columns={
            "patient_id":      "Patient ID",
            "medicare":        "Medicare",
            "irn":             "IRN",
            "lastname":        "Surname",
            "firstname":       "First Name",
            "dob":             "DOB",
            "gender":          "Gender",
            "phone":           "Phone",
            "address":         "Address",
            "date_registered": "Registered",
        })

        selection = st.dataframe(
            pt_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="ps_table",
        )

        sel_rows = selection.selection.get("rows", [])
        if not sel_rows:
            return

        row_idx = sel_rows[0]
        pat = results[row_idx]
        mid = pat["medicare"]

        if st.session_state.get("ps_selected_mid") != mid:
            st.session_state["ps_selected_mid"] = mid
            st.session_state.pop("ps_action", None)
            for _k in list(st.session_state.keys()):
                if _k.startswith("nv_"):
                    st.session_state.pop(_k, None)

        st.markdown("---")
        full_name = f"{pat.get('firstname', '')} {pat.get('lastname', '')}".strip()
        st.markdown(
            f"### {full_name}  "
            f"<span style='font-size:0.85rem;color:gray'>"
            f"ID: {pat.get('patient_id','—')}  |  "
            f"Medicare: {mid}  |  DOB: {pat.get('dob','—')}"
            f"</span>",
            unsafe_allow_html=True,
        )

        act_col1, act_col2, act_col3 = st.columns(3)
        with act_col1:
            if st.button("✏️ Edit Patient", key="act_edit", use_container_width=True):
                st.session_state["ps_action"] = "edit"
        with act_col2:
            if st.button("🏥 New Visit", key="act_new_visit", use_container_width=True,
                         type="primary"):
                st.session_state["ps_action"] = "new_visit"
                # clear any stale visit state when opening fresh
                for _k in list(st.session_state.keys()):
                    if _k.startswith("nv_"):
                        st.session_state.pop(_k, None)
        with act_col3:
            if st.button("🗑️ Delete Patient", key="act_delete",
                         use_container_width=True):
                st.session_state["ps_action"] = "delete"

        action = st.session_state.get("ps_action", "")

        # ── PANEL: EDIT PATIENT ───────────────────────────────────────────────
        if action == "edit":
            st.markdown("#### ✏️ Edit Patient Details")
            ed1, ed2 = st.columns(2)
            with ed1:
                e_ln   = st.text_input("Surname", value=pat.get("lastname", ""),
                                       key=f"e_ln_{mid}")
                e_fn   = st.text_input("First Name", value=pat.get("firstname", ""),
                                       key=f"e_fn_{mid}")
                e_dob  = st.text_input("DOB (DD/MM/YYYY)", value=pat.get("dob", ""),
                                       key=f"e_dob_{mid}")
                e_irn  = st.number_input("IRN", min_value=1, max_value=9,
                                         value=int(pat["irn"]) if pat.get("irn") else 1,
                                         key=f"e_irn_{mid}")
                e_mex  = st.text_input("Medicare Expiry (MM/YYYY)",
                                       value=pat.get("medicare_expiry", ""),
                                       key=f"e_mex_{mid}")
                e_dva  = st.text_input("DVA File Number",
                                       value=pat.get("dva", ""), key=f"e_dva_{mid}")
                e_conc = st.text_input("Concession Card No.",
                                       value=pat.get("concession", ""),
                                       key=f"e_conc_{mid}")
            with ed2:
                gender_i = _GENDERS.index(pat["gender"]) \
                           if pat.get("gender") in _GENDERS else 0
                e_gender = st.selectbox("Gender", _GENDERS, index=gender_i,
                                        key=f"e_gen_{mid}")
                indig_i  = _INDIGENOUS.index(pat["indigenous"]) \
                           if pat.get("indigenous") in _INDIGENOUS else 0
                e_indig  = st.selectbox("ATSI Status", _INDIGENOUS, index=indig_i,
                                        key=f"e_indig_{mid}")
                e_addr   = st.text_input("Address", value=pat.get("address", ""),
                                         key=f"e_addr_{mid}")
                e_ph     = st.text_input("Phone", value=pat.get("phone", ""),
                                         key=f"e_ph_{mid}")
                e_email  = st.text_input("Email", value=pat.get("email", ""),
                                         key=f"e_email_{mid}")
                e_ihi    = st.text_input("IHI", value=pat.get("ihi", ""),
                                         key=f"e_ihi_{mid}")
                interp_i = _INTERPRETER.index(pat["interpreter"]) \
                           if pat.get("interpreter") in _INTERPRETER else 0
                e_interp = st.selectbox("Interpreter Required?", _INTERPRETER,
                                        index=interp_i, key=f"e_interp_{mid}")
                e_lang   = st.text_input("Language", value=pat.get("language", ""),
                                         key=f"e_lang_{mid}")

            sv_col, cancel_col = st.columns([3, 1])
            with sv_col:
                if st.button("💾 Save Changes", key=f"upd_{mid}",
                             use_container_width=True, type="primary"):
                    update_patient(mid, {
                        "irn":             e_irn,
                        "lastname":        e_ln,
                        "firstname":       e_fn,
                        "dob":             e_dob,
                        "gender":          e_gender,
                        "indigenous":      e_indig,
                        "medicare_expiry": e_mex,
                        "dva":             e_dva,
                        "concession":      e_conc,
                        "address":         e_addr,
                        "phone":           e_ph,
                        "email":           e_email,
                        "ihi":             e_ihi,
                        "interpreter":     e_interp,
                        "language":        e_lang,
                    })
                    st.success(f"✅ {e_fn} {e_ln} updated.")
                    st.session_state.pop("ps_action", None)
                    st.rerun()
            with cancel_col:
                if st.button("Cancel", key="edit_cancel", use_container_width=True):
                    st.session_state.pop("ps_action", None)
                    st.rerun()

        # ── PANEL: NEW VISIT WIZARD ───────────────────────────────────────────
        elif action == "new_visit":
            st.markdown(
                f"#### 🏥 New Visit — {full_name}  "
                f"<span style='font-size:0.85rem;color:gray'>"
                f"ID: {pat.get('patient_id','—')}</span>",
                unsafe_allow_html=True,
            )

            # Free-navigation step tabs
            step_tab1, step_tab2, step_tab3 = st.tabs([
                "1️⃣  Study / Request Details",
                "2️⃣  Referring Doctor",
                "3️⃣  Documents",
            ])
            with step_tab1:
                _visit_step1(mid)
            with step_tab2:
                _visit_step2()
            with step_tab3:
                _visit_step3(mid, pat)

            st.markdown("")
            if st.button("✖ Cancel Visit", key="nv_cancel",
                         use_container_width=False):
                st.session_state.pop("ps_action", None)
                for _k in list(st.session_state.keys()):
                    if _k.startswith("nv_"):
                        st.session_state.pop(_k, None)
                st.rerun()

        # ── PANEL: DELETE PATIENT ─────────────────────────────────────────────
        elif action == "delete":
            st.warning(
                f"⚠️ Are you sure you want to delete **{full_name}** "
                f"(Medicare: {mid})? This will also remove all imaging orders "
                f"and **cannot be undone.**"
            )
            conf1, conf2 = st.columns(2)
            with conf1:
                if st.button("✅ Yes, delete permanently", key=f"del_confirm_{mid}",
                             use_container_width=True, type="primary"):
                    delete_patient(mid)
                    st.session_state.pop("ps_action", None)
                    st.success(f"Patient {mid} deleted.")
                    st.rerun()
            with conf2:
                if st.button("❌ Cancel", key=f"del_cancel_{mid}",
                             use_container_width=True):
                    st.session_state.pop("ps_action", None)
                    st.rerun()

        # ── Visit history (always shown below action panels, except delete) ───
        if action != "delete":
            st.markdown("---")
            st.markdown("**Visit history:**")
            history = get_patient_referrals(mid)
            if not history:
                st.info("No visits on record for this patient.")
            else:
                pending_del  = st.session_state.get("ps_del_visit_id")
                editing_id   = st.session_state.get("ps_edit_visit_id")

                for visit in history:
                    rid = visit["referral_id"]
                    acc = visit.get("accession_number") or rid[:8]
                    mod = visit.get("modality", "—")
                    bod = visit.get("body_region", "—")
                    urg = visit.get("urgency", "—")
                    dt  = visit.get("referral_date") or visit.get("date_created", "—")
                    dr  = visit.get("referring_doctor", "—")
                    sta = visit.get("status", "—")

                    with st.container(border=True):
                        hc1, hc2, hc3 = st.columns([5, 1, 1])
                        with hc1:
                            st.markdown(
                                f"**{acc}** &nbsp;·&nbsp; {mod} — {bod}  \n"
                                f"<span style='font-size:0.82rem;color:gray'>"
                                f"{URGENCY_ICON.get(urg,'')} {urg} &nbsp;·&nbsp; "
                                f"{STATUS_ICON.get(sta,'')} {sta} &nbsp;·&nbsp; "
                                f"Date: {dt} &nbsp;·&nbsp; Dr: {dr}"
                                f"</span>",
                                unsafe_allow_html=True,
                            )
                            docs = get_documents_for_referral(rid)
                            if docs:
                                for doc in docs:
                                    doc_name = doc.get("file_name", "Document")
                                    doc_link = doc.get("storage_url", "")
                                    if doc_link:
                                        st.markdown(
                                            f"- 📎 [{doc_name}]({doc_link})",
                                            unsafe_allow_html=False,
                                        )
                                    else:
                                        st.caption(f"📎 {doc_name}")
                        with hc2:
                            if st.button("✏️ Edit", key=f"edit_visit_{rid}",
                                         use_container_width=True):
                                if editing_id == rid:
                                    st.session_state.pop("ps_edit_visit_id", None)
                                else:
                                    st.session_state["ps_edit_visit_id"] = rid
                                    st.session_state.pop("ps_del_visit_id", None)
                                st.rerun()
                        with hc3:
                            if st.button("🗑️ Delete", key=f"del_visit_{rid}",
                                         use_container_width=True):
                                st.session_state["ps_del_visit_id"] = rid
                                st.session_state.pop("ps_edit_visit_id", None)
                                st.rerun()

                        # ── Inline edit form ──────────────────────────────────
                        if editing_id == rid:
                            st.markdown("###### ✏️ Edit Visit")
                            ev1, ev2 = st.columns(2)
                            with ev1:
                                e_clinic = st.text_input(
                                    "Referred To",
                                    value=visit.get("to_clinic", ""),
                                    key=f"ev_clinic_{rid}",
                                )
                                e_mod = st.selectbox(
                                    "Modality",
                                    ALL_MODALITIES,
                                    index=ALL_MODALITIES.index(mod) if mod in ALL_MODALITIES else 0,
                                    key=f"ev_mod_{rid}",
                                )
                                e_body = st.text_input(
                                    "Body Region / Examination",
                                    value=visit.get("body_region", ""),
                                    key=f"ev_body_{rid}",
                                )
                                e_urg = st.selectbox(
                                    "Urgency",
                                    ALL_URGENCIES,
                                    index=ALL_URGENCIES.index(urg) if urg in ALL_URGENCIES else 0,
                                    key=f"ev_urg_{rid}",
                                )
                                e_sta = st.selectbox(
                                    "Status",
                                    ["Pending", "Scheduled", "In Progress",
                                     "Completed", "Cancelled", "On Hold"],
                                    index=["Pending", "Scheduled", "In Progress",
                                           "Completed", "Cancelled", "On Hold"].index(sta)
                                           if sta in ["Pending", "Scheduled", "In Progress",
                                                      "Completed", "Cancelled", "On Hold"] else 0,
                                    key=f"ev_sta_{rid}",
                                )
                            with ev2:
                                e_date = st.text_input(
                                    "Order Date (DD/MM/YYYY)",
                                    value=visit.get("referral_date", ""),
                                    key=f"ev_date_{rid}",
                                )
                                e_valid = st.text_input(
                                    "Valid Until (DD/MM/YYYY)",
                                    value=visit.get("valid_until", ""),
                                    key=f"ev_valid_{rid}",
                                )
                                e_dr = st.text_input(
                                    "Referring Doctor",
                                    value=visit.get("referring_doctor", ""),
                                    key=f"ev_dr_{rid}",
                                )
                                e_prov = st.text_input(
                                    "Provider Number",
                                    value=visit.get("provider_number", ""),
                                    key=f"ev_prov_{rid}",
                                )
                                e_prac = st.text_input(
                                    "Practice",
                                    value=visit.get("practice", ""),
                                    key=f"ev_prac_{rid}",
                                )
                            e_ind = st.text_area(
                                "Clinical Indication",
                                value=visit.get("clinical_indication", ""),
                                height=70, key=f"ev_ind_{rid}",
                            )
                            e_hist = st.text_area(
                                "Relevant History",
                                value=visit.get("relevant_history", ""),
                                height=60, key=f"ev_hist_{rid}",
                            )
                            e_meds = st.text_area(
                                "Medications",
                                value=visit.get("medications", ""),
                                height=60, key=f"ev_meds_{rid}",
                            )
                            e_allg = st.text_input(
                                "Allergies",
                                value=visit.get("allergies", ""),
                                key=f"ev_allg_{rid}",
                            )
                            e_spec = st.text_area(
                                "Special Requirements",
                                value=visit.get("special_requirements", ""),
                                height=60, key=f"ev_spec_{rid}",
                            )
                            sv1, sv2 = st.columns([3, 1])
                            with sv1:
                                if st.button("💾 Save Changes", key=f"ev_save_{rid}",
                                             use_container_width=True, type="primary"):
                                    update_referral(rid, {
                                        "to_clinic":            e_clinic,
                                        "modality":             e_mod,
                                        "body_region":          e_body,
                                        "urgency":              e_urg,
                                        "referral_date":        e_date,
                                        "valid_until":          e_valid,
                                        "clinical_indication":  e_ind,
                                        "relevant_history":     e_hist,
                                        "medications":          e_meds,
                                        "allergies":            e_allg,
                                        "investigations":       visit.get("investigations", ""),
                                        "special_requirements": e_spec,
                                        "referring_doctor":     e_dr,
                                        "provider_number":      e_prov,
                                        "practice":             e_prac,
                                        "doctor_phone":         visit.get("doctor_phone", ""),
                                        "doctor_email":         visit.get("doctor_email", ""),
                                        "status":               e_sta,
                                    })
                                    st.session_state.pop("ps_edit_visit_id", None)
                                    st.rerun()
                            with sv2:
                                if st.button("Cancel", key=f"ev_cancel_{rid}",
                                             use_container_width=True):
                                    st.session_state.pop("ps_edit_visit_id", None)
                                    st.rerun()

                        # ── Inline delete confirmation ─────────────────────────
                        if pending_del == rid:
                            st.warning(
                                f"Delete visit **{acc}**? This cannot be undone."
                            )
                            cc1, cc2 = st.columns(2)
                            with cc1:
                                if st.button("✅ Yes, delete", key=f"del_visit_confirm_{rid}",
                                             use_container_width=True, type="primary"):
                                    delete_referral(rid)
                                    st.session_state.pop("ps_del_visit_id", None)
                                    st.rerun()
                            with cc2:
                                if st.button("❌ Cancel", key=f"del_visit_cancel_{rid}",
                                             use_container_width=True):
                                    st.session_state.pop("ps_del_visit_id", None)
                                    st.rerun()

                st.caption(f"{len(history)} visit(s) on record")
