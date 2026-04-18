"""
tabs/patient_search.py
Radiology2u RIS — Patient Registry tab.

Two action tabs:
  1. Register Patient  — enter demographics without generating a referral
                         (for walk-ins presenting with an existing referral)
  2. Search & Manage   — search registered patients, view imaging history,
                         and edit patient details
"""

import pandas as pd
import streamlit as st

from sheets_db import (
    delete_patient,
    find_patient_by_medicare,
    get_all_patients,
    get_patient_referrals,
    register_patient,
    search_patients,
    update_patient,
)
from tabs.constants import STATUS_ICON, URGENCY_ICON

_GENDERS     = ["", "Male", "Female", "Non-binary / Gender diverse", "Prefer not to say"]
_INDIGENOUS  = ["", "Neither", "Aboriginal", "Torres Strait Islander",
                "Both Aboriginal and Torres Strait Islander", "Prefer not to say"]
_INTERPRETER = ["No", "Yes"]


def render() -> None:
    """Render the Patient Registry tab."""

    st.subheader("🔍 Patient Registry", divider="blue")

    action_tabs = st.tabs(["➕  Register Patient", "🔍  Search & Manage"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — REGISTER PATIENT
    # ══════════════════════════════════════════════════════════════════════════
    with action_tabs[0]:
        st.markdown(
            "Register a patient who is presenting with an **existing referral** "
            "or who needs to be added to the system without generating a new order."
        )
        st.markdown('<div class="r2u-section">Patient Demographics</div>',
                    unsafe_allow_html=True)

        r1, r2 = st.columns(2)
        with r1:
            rp_medicare = st.text_input(
                "Medicare Number *", placeholder="1234 56789 0", key="rp_medicare"
            )
            rp_irn      = st.number_input(
                "IRN (Individual Reference Number)", min_value=1, max_value=9,
                value=1, step=1, key="rp_irn"
            )
            rp_medicare_expiry = st.text_input(
                "Medicare Expiry (MM/YYYY)", placeholder="01/2028", key="rp_mex"
            )
            rp_dva = st.text_input(
                "DVA File Number (if applicable)", key="rp_dva"
            )
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
            rp_dob       = st.text_input(
                "Date of Birth * (DD/MM/YYYY)", placeholder="01/01/1980", key="rp_dob"
            )
            rp_gender    = st.selectbox("Gender", _GENDERS, key="rp_gender")
            rp_indigenous = st.selectbox(
                "Aboriginal / Torres Strait Islander Status",
                _INDIGENOUS, key="rp_indigenous"
            )

        r3, r4 = st.columns(2)
        with r3:
            rp_address = st.text_input(
                "Home Address", placeholder="1 Example St, Suburb NSW 2000",
                key="rp_addr"
            )
            rp_phone   = st.text_input(
                "Phone", placeholder="0400 000 000", key="rp_ph"
            )
        with r4:
            rp_email = st.text_input(
                "Email", placeholder="patient@email.com", key="rp_email"
            )
            rp_interpreter = st.selectbox(
                "Interpreter Required?", _INTERPRETER, key="rp_interp"
            )
            rp_language = st.text_input(
                "Language (if interpreter needed)", key="rp_lang"
            )

        st.markdown("")
        if st.button("💾 Register Patient", type="primary",
                     use_container_width=True, key="btn_reg_patient"):
            medicare_clean = rp_medicare.replace(" ", "")
            if not medicare_clean or not rp_lastname.strip() or not rp_firstname.strip() or not rp_dob.strip():
                st.error("Medicare number, surname, first name and date of birth are required.")
            else:
                register_patient({
                    "medicare":        rp_medicare,
                    "irn":             rp_irn,
                    "lastname":        rp_lastname,
                    "firstname":       rp_firstname,
                    "dob":             rp_dob,
                    "gender":          rp_gender,
                    "indigenous":      rp_indigenous,
                    "medicare_expiry": rp_medicare_expiry,
                    "dva":             rp_dva,
                    "concession":      rp_concession,
                    "address":         rp_address,
                    "phone":           rp_phone,
                    "email":           rp_email,
                    "ihi":             rp_ihi,
                    "interpreter":     rp_interpreter,
                    "language":        rp_language,
                })
                st.success(
                    f"✅ {rp_firstname.strip()} {rp_lastname.strip()} "
                    f"registered successfully (Medicare: {medicare_clean})."
                )
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — SEARCH & MANAGE
    # ══════════════════════════════════════════════════════════════════════════
    with action_tabs[1]:
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

        # Show all patients by default; filter when a query is entered
        if search_btn and search_q.strip():
            results = search_patients(search_q.strip())
        else:
            results = get_all_patients()

        if not results:
            st.info("No patients registered yet. Use the **Register Patient** tab to add patients.")
            return

        st.caption(f"{len(results)} patient(s)")

        # ── Results summary table ─────────────────────────────────────────────
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
        st.dataframe(pt_df, use_container_width=True, hide_index=True)

        # ── Per-patient expand: edit details + imaging history ────────────────
        st.markdown("---")
        for pat in results:
            label = (
                f"{pat['lastname']}, {pat['firstname']}  —  "
                f"ID: {pat.get('patient_id', '—')}  |  "
                f"Medicare: {pat['medicare']}  |  DOB: {pat.get('dob', '—')}"
            )
            with st.expander(label):
                # ── View summary row ─────────────────────────────────────────
                v1, v2 = st.columns(2)
                with v1:
                    st.markdown(f"**Gender:** {pat.get('gender') or '—'}")
                    st.markdown(f"**DOB:** {pat.get('dob') or '—'}")
                    st.markdown(f"**Address:** {pat.get('address') or '—'}")
                    st.markdown(f"**Phone:** {pat.get('phone') or '—'}")
                with v2:
                    st.markdown(f"**Email:** {pat.get('email') or '—'}")
                    st.markdown(f"**DVA:** {pat.get('dva') or '—'}")
                    st.markdown(f"**Concession:** {pat.get('concession') or '—'}")
                    st.markdown(f"**IHI:** {pat.get('ihi') or '—'}")

                # ── Edit form ────────────────────────────────────────────────
                st.markdown("**Edit patient details:**")
                mid = pat["medicare"]
                ed1, ed2 = st.columns(2)
                with ed1:
                    e_ln    = st.text_input("Surname", value=pat.get("lastname", ""),
                                            key=f"e_ln_{mid}")
                    e_fn    = st.text_input("First Name", value=pat.get("firstname", ""),
                                            key=f"e_fn_{mid}")
                    e_dob   = st.text_input("DOB (DD/MM/YYYY)", value=pat.get("dob", ""),
                                            key=f"e_dob_{mid}")
                    e_irn   = st.number_input("IRN", min_value=1, max_value=9,
                                              value=int(pat["irn"]) if pat.get("irn") else 1,
                                              key=f"e_irn_{mid}")
                    e_mex   = st.text_input("Medicare Expiry (MM/YYYY)",
                                            value=pat.get("medicare_expiry", ""),
                                            key=f"e_mex_{mid}")
                    e_dva   = st.text_input("DVA File Number",
                                            value=pat.get("dva", ""), key=f"e_dva_{mid}")
                    e_conc  = st.text_input("Concession Card No.",
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

                btn_col, del_col = st.columns([3, 1])
                with btn_col:
                    if st.button("💾 Update Patient", key=f"upd_{mid}",
                                 use_container_width=True):
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
                        st.rerun()
                with del_col:
                    if st.button("🗑️ Delete Patient", key=f"del_btn_{mid}",
                                 use_container_width=True):
                        st.session_state[f"confirm_del_{mid}"] = True

                if st.session_state.get(f"confirm_del_{mid}"):
                    st.warning(
                        f"⚠️ Are you sure you want to delete **{pat.get('firstname')} {pat.get('lastname')}** "
                        f"(Medicare: {mid})? This will also remove all their imaging orders and **cannot be undone.**"
                    )
                    conf1, conf2 = st.columns(2)
                    with conf1:
                        if st.button("✅ Yes, delete permanently", key=f"del_confirm_{mid}",
                                     use_container_width=True, type="primary"):
                            delete_patient(mid)
                            st.session_state.pop(f"confirm_del_{mid}", None)
                            st.success(f"Patient {mid} deleted.")
                            st.rerun()
                    with conf2:
                        if st.button("❌ Cancel", key=f"del_cancel_{mid}",
                                     use_container_width=True):
                            st.session_state.pop(f"confirm_del_{mid}", None)
                            st.rerun()

                # ── Imaging history ──────────────────────────────────────────
                st.markdown("**Imaging order history:**")
                history = get_patient_referrals(mid)
                if not history:
                    st.info("No imaging orders on record for this patient.")
                else:
                    hist_df = pd.DataFrame(history)[[
                        "referral_id", "referral_date", "modality", "body_region",
                        "urgency", "to_clinic", "referring_doctor", "status",
                    ]].rename(columns={
                        "referral_id":      "Order ID",
                        "referral_date":    "Date",
                        "modality":         "Modality",
                        "body_region":      "Examination",
                        "urgency":          "Urgency",
                        "to_clinic":        "Facility",
                        "referring_doctor": "Referring Dr",
                        "status":           "Status",
                    })
                    hist_df["Urgency"] = hist_df["Urgency"].apply(
                        lambda x: f"{URGENCY_ICON.get(x, '')} {x}"
                    )
                    hist_df["Status"] = hist_df["Status"].apply(
                        lambda x: f"{STATUS_ICON.get(x, '')} {x}"
                    )
                    st.dataframe(hist_df, use_container_width=True, hide_index=True)
                    st.caption(f"{len(hist_df)} order(s) on record")
