"""
tabs/new_referral.py
Radiology2u RIS — New Referral Order tab.
Handles referring doctor details, patient registration, and referral request.
Generates and downloads a professional PDF referral letter.
"""

import uuid
from datetime import date

import streamlit as st

from pdf_generator import generate_referral_pdf
from sheets_db import create_referral, get_all_doctors, register_patient, search_doctors
from tabs.constants import ALL_MODALITIES, ALL_URGENCIES, STATES

_TITLES = ["Dr", "Prof", "A/Prof", "Mr", "Ms", "Mrs"]


def _render_doctor_lookup() -> None:
    """
    A compact lookup widget placed above the manual doctor fields.
    Selecting a saved doctor from the registry populates all ref_ session-state
    keys so the form fields below auto-fill on the next render.
    """
    doctors = get_all_doctors()
    if not doctors:
        return  # no saved doctors yet — skip the widget entirely

    with st.expander("🔍 Load a saved doctor from the registry", expanded=False):
        # Build display labels + id map
        options = {
            f"{d['title']} {d['firstname']} {d['lastname']}  |  "
            f"Provider: {d['provider_number']}"
            + (f"  |  {d['practice']}" if d.get("practice") else ""): d["doctor_id"]
            for d in doctors
        }
        label_list = ["— Select a doctor —"] + list(options.keys())

        selected_label = st.selectbox(
            "Doctor",
            label_list,
            key="dr_lookup_selection",
            label_visibility="collapsed",
        )

        if selected_label != "— Select a doctor —":
            col_load, col_clear = st.columns([3, 1])
            with col_load:
                if st.button("✅ Load doctor into form", key="btn_load_doctor",
                             use_container_width=True, type="primary"):
                    doc_id = options[selected_label]
                    from sheets_db import get_doctor_by_id  # lazy import to avoid circular
                    doc = get_doctor_by_id(doc_id)
                    if doc:
                        st.session_state["ref_title"]  = doc.get("title", _TITLES[0])
                        st.session_state["ref_fn"]     = doc.get("firstname", "")
                        st.session_state["ref_ln"]     = doc.get("lastname", "")
                        st.session_state["ref_prov"]   = doc.get("provider_number", "")
                        st.session_state["ref_hpii"]   = doc.get("hpii", "")
                        st.session_state["ref_prac"]   = doc.get("practice", "")
                        st.session_state["ref_addr"]   = doc.get("address", "")
                        st.session_state["ref_sub"]    = doc.get("suburb", "")
                        st.session_state["ref_state"]  = doc.get("state", STATES[0])
                        st.session_state["ref_pc"]     = doc.get("postcode", "")
                        st.session_state["ref_ph"]     = doc.get("phone", "")
                        st.session_state["ref_fax"]    = doc.get("fax", "")
                        st.session_state["ref_email"]  = doc.get("email", "")
                        st.rerun()
            with col_clear:
                if st.button("🗑️ Clear fields", key="btn_clear_doctor",
                             use_container_width=True):
                    for k in ("ref_title","ref_fn","ref_ln","ref_prov","ref_hpii",
                              "ref_prac","ref_addr","ref_sub","ref_state",
                              "ref_pc","ref_ph","ref_fax","ref_email"):
                        st.session_state.pop(k, None)
                    st.rerun()


def render(cfg: dict) -> None:
    """Render the New Referral Order tab. Pass loaded settings dict as cfg."""

    st.markdown(
        '<p class="r2u-required-note">Fields marked <strong>*</strong> are required.</p>',
        unsafe_allow_html=True,
    )

    # ── Section 1 — Referring Doctor ──────────────────────────────────────────
    st.markdown(
        '<div class="r2u-section">① Referring Doctor / Practice Details</div>',
        unsafe_allow_html=True,
    )

    # Doctor lookup — search saved registry and auto-fill form
    _render_doctor_lookup()

    c1, c2 = st.columns(2)
    with c1:
        ref_title       = st.selectbox("Title", ["Dr", "Prof", "A/Prof", "Mr", "Ms", "Mrs"],
                                       key="ref_title")
        ref_firstname   = st.text_input("First Name *", key="ref_fn")
        ref_lastname    = st.text_input("Last Name *", key="ref_ln")
        ref_provider_no = st.text_input(
            "Medicare Provider Number *", placeholder="e.g. 2123456A", key="ref_prov"
        )
        ref_hpii = st.text_input(
            "HPI-I (optional)",
            placeholder="8003610000000000",
            help="Healthcare Provider Identifier – Individual (16 digits)",
            key="ref_hpii",
        )
    with c2:
        ref_practice = st.text_input(
            "Practice / Clinic Name *", value=cfg.get("practice", ""), key="ref_prac"
        )
        ref_address  = st.text_input(
            "Street Address *", value=cfg.get("address", ""), key="ref_addr"
        )
        ref_suburb   = st.text_input(
            "Suburb *", value=cfg.get("suburb", ""), key="ref_sub"
        )
        state_idx    = STATES.index(cfg["state"]) if cfg.get("state") in STATES else 0
        ref_state    = st.selectbox(
            "State / Territory *", STATES, index=state_idx, key="ref_state"
        )
        ref_postcode = st.text_input(
            "Postcode *", max_chars=4, value=cfg.get("postcode", ""), key="ref_pc"
        )

    c3, c4 = st.columns(2)
    with c3:
        ref_phone = st.text_input(
            "Phone *", value=cfg.get("phone", ""),
            placeholder="(02) 0000 0000", key="ref_ph"
        )
        ref_fax = st.text_input(
            "Fax", value=cfg.get("fax", ""),
            placeholder="(02) 0000 0000", key="ref_fax"
        )
    with c4:
        ref_email = st.text_input(
            "Email *", value=cfg.get("email", ""),
            placeholder="doctor@practice.com.au", key="ref_email"
        )

    # ── Section 2 — Patient Details ───────────────────────────────────────────
    st.markdown(
        '<div class="r2u-section">② Patient Details</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        pt_firstname  = st.text_input("First Name *", key="pt_fn")
        pt_lastname   = st.text_input("Surname *", key="pt_ln")
        pt_dob        = st.date_input(
            "Date of Birth *",
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            key="pt_dob",
        )
        pt_gender = st.selectbox(
            "Gender *",
            ["Male", "Female", "Non-binary", "Prefer not to say", "Other"],
        )
        pt_indigenous = st.selectbox(
            "Aboriginal / Torres Strait Islander Status",
            [
                "Neither",
                "Aboriginal",
                "Torres Strait Islander",
                "Both Aboriginal and Torres Strait Islander",
                "Prefer not to say",
            ],
            help="Required under Australian health reporting standards",
        )
    with c2:
        pt_medicare        = st.text_input(
            "Medicare Card Number *", placeholder="0000 00000 0", max_chars=12
        )
        pt_medicare_irn    = st.selectbox(
            "Medicare IRN *",
            list(range(1, 10)),
            help="Individual Reference Number (position on card)",
        )
        pt_medicare_expiry = st.text_input(
            "Medicare Expiry (MM/YYYY) *", placeholder="01/2027", max_chars=7
        )
        pt_dva        = st.text_input(
            "DVA File Number (if applicable)", placeholder="N000000"
        )
        pt_concession = st.text_input(
            "Concession / Health Care Card Number (if applicable)"
        )

    c3, c4 = st.columns(2)
    with c3:
        pt_address = st.text_input("Street Address *", key="pt_addr")
        pt_suburb  = st.text_input("Suburb *", key="pt_sub")
    with c4:
        pt_state    = st.selectbox("State / Territory *", STATES, key="pt_state")
        pt_postcode = st.text_input("Postcode *", max_chars=4, key="pt_pc")

    c5, c6 = st.columns(2)
    with c5:
        pt_phone = st.text_input("Phone *", placeholder="04XX XXX XXX", key="pt_ph")
        pt_email = st.text_input("Email (optional)", key="pt_email")
    with c6:
        pt_ihi = st.text_input(
            "IHI – Individual Healthcare Identifier (optional)",
            placeholder="8003608000000000",
        )
        pt_interpreter = st.selectbox("Interpreter Required?", ["No", "Yes"])
        pt_language    = st.text_input(
            "Language (if interpreter required)", key="pt_lang"
        )

    # ── Section 3 — Referral / Imaging Order ──────────────────────────────────
    st.markdown(
        '<div class="r2u-section">③ Imaging Order Details</div>',
        unsafe_allow_html=True,
    )

    today = date.today()
    try:
        default_valid = today.replace(year=today.year + 1)
    except ValueError:
        default_valid = today.replace(year=today.year + 1, day=28)

    c1, c2 = st.columns(2)
    with c1:
        ref_to_clinic = st.text_input(
            "Referred To (Facility / Department) *",
            placeholder="e.g. Radiology2u — Mobile Ultrasound",
        )
        modality    = st.selectbox("Imaging Modality *", ALL_MODALITIES)
        body_region = st.text_input(
            "Body Region / Examination *", placeholder="e.g. Abdomen and Pelvis"
        )
    with c2:
        urgency       = st.selectbox("Clinical Urgency *", ALL_URGENCIES[::-1])
        referral_date = st.date_input("Order Date *", value=date.today())
        valid_until   = st.date_input(
            "Valid Until (default 12 months)", value=default_valid
        )

    clinical_indication = st.text_area(
        "Clinical Indication / Reason for Referral *",
        placeholder="Describe the clinical reason and presenting complaint...",
        height=100,
    )
    relevant_history = st.text_area(
        "Relevant Medical History",
        placeholder="Past medical/surgical history, relevant conditions...",
        height=80,
    )
    current_medications = st.text_area(
        "Current Medications",
        placeholder="List relevant medications, doses and frequency...",
        height=80,
    )
    allergies = st.text_input(
        "Known Allergies / Adverse Drug Reactions",
        placeholder="e.g. Penicillin – anaphylaxis; Iodinated contrast – nausea",
    )
    investigations_done = st.text_area(
        "Relevant Investigations Already Performed",
        placeholder="e.g. FBC/UEC normal (01/2026); Prior US 2024...",
        height=80,
    )
    special_requirements = st.text_area(
        "Special Requirements / Instructions",
        placeholder=(
            "e.g. Patient claustrophobic, prior IV contrast reaction, "
            "requires sedation planning..."
        ),
        height=60,
    )

    st.markdown("---")
    generate_btn = st.button(
        "📄 Generate Referral & Register Patient",
        type="primary",
        use_container_width=True,
    )

    if generate_btn:
        required = {
            "Referring doctor first name": ref_firstname,
            "Referring doctor last name":  ref_lastname,
            "Medicare provider number":    ref_provider_no,
            "Practice name":               ref_practice,
            "Practice street address":     ref_address,
            "Practice suburb":             ref_suburb,
            "Practice postcode":           ref_postcode,
            "Doctor phone":                ref_phone,
            "Doctor email":                ref_email,
            "Patient first name":          pt_firstname,
            "Patient surname":             pt_lastname,
            "Medicare card number":        pt_medicare,
            "Medicare expiry":             pt_medicare_expiry,
            "Patient street address":      pt_address,
            "Patient suburb":              pt_suburb,
            "Patient postcode":            pt_postcode,
            "Patient phone":               pt_phone,
            "Referred to":                 ref_to_clinic,
            "Body region / examination":   body_region,
            "Clinical indication":         clinical_indication,
        }
        missing = [k for k, v in required.items() if not v.strip()]
        if missing:
            st.error(
                "Please complete the following required fields:\n\n"
                + "\n".join(f"- {m}" for m in missing)
            )
        else:
            # 1. Register patient first to get stable Patient ID
            patient_data = {
                "firstname":       pt_firstname.strip(),
                "lastname":        pt_lastname.strip(),
                "dob":             pt_dob.strftime("%d/%m/%Y"),
                "gender":          pt_gender,
                "indigenous":      pt_indigenous,
                "medicare":        pt_medicare.strip(),
                "irn":             pt_medicare_irn,
                "medicare_expiry": pt_medicare_expiry.strip(),
                "dva":             pt_dva.strip(),
                "concession":      pt_concession.strip(),
                "address":         (
                    f"{pt_address.strip()}, {pt_suburb.strip()} "
                    f"{pt_state} {pt_postcode.strip()}"
                ),
                "phone":           pt_phone.strip(),
                "email":           pt_email.strip(),
                "ihi":             pt_ihi.strip(),
                "interpreter":     pt_interpreter,
                "language":        pt_language.strip(),
            }
            patient_id = register_patient(patient_data)
            patient_data["patient_id"] = patient_id

            # 2. Build accession number for this study
            accession_number = (
                "R2U-"
                + referral_date.strftime("%Y%m%d")
                + "-"
                + str(uuid.uuid4())[:4].upper()
            )

            doctor_data = {
                "title":           ref_title,
                "firstname":       ref_firstname.strip(),
                "lastname":        ref_lastname.strip(),
                "provider_number": ref_provider_no.strip(),
                "hpii":            ref_hpii.strip(),
                "practice":        ref_practice.strip(),
                "address":         (
                    f"{ref_address.strip()}, {ref_suburb.strip()} "
                    f"{ref_state} {ref_postcode.strip()}"
                ),
                "phone":           ref_phone.strip(),
                "fax":             ref_fax.strip(),
                "email":           ref_email.strip(),
            }
            referral_data = {
                "accession_number":     accession_number,
                "medicare":             pt_medicare.strip(),
                "to_clinic":            ref_to_clinic.strip(),
                "modality":             modality,
                "body_region":          body_region.strip(),
                "urgency":              urgency,
                "date":                 referral_date.strftime("%d/%m/%Y"),
                "valid_until":          valid_until.strftime("%d/%m/%Y"),
                "clinical_indication":  clinical_indication.strip(),
                "relevant_history":     relevant_history.strip(),
                "medications":          current_medications.strip(),
                "allergies":            allergies.strip(),
                "investigations":       investigations_done.strip(),
                "special_requirements": special_requirements.strip(),
                "referring_doctor":     (
                    f"{ref_title} {ref_firstname.strip()} {ref_lastname.strip()}"
                ),
                "provider_number":      ref_provider_no.strip(),
                "practice":             ref_practice.strip(),
                "doctor_phone":         ref_phone.strip(),
                "doctor_email":         ref_email.strip(),
            }

            # 3. Generate PDF (patient_id and accession_number now in dicts)
            with st.spinner("Generating PDF and saving to RIS database..."):
                pdf_bytes = generate_referral_pdf(patient_data, doctor_data, referral_data)

            create_referral(referral_data)

            st.session_state.pdf_bytes       = pdf_bytes
            st.session_state.accession_number = accession_number
            st.session_state.patient_id      = patient_id
            st.session_state.pt_lastname     = pt_lastname.strip()
            st.session_state.pt_firstname    = pt_firstname.strip()

            st.success(
                f"✅ Referral issued — "
                f"Patient ID: **{patient_id}**  |  Accession: **{accession_number}**"
            )

    if st.session_state.get("pdf_bytes"):
        st.download_button(
            label="⬇️ Download Referral PDF",
            data=st.session_state.pdf_bytes,
            file_name=(
                f"R2U_{st.session_state.accession_number}_"
                f"{st.session_state.pt_lastname}_{st.session_state.pt_firstname}.pdf"
            ),
            mime="application/pdf",
            use_container_width=True,
        )
