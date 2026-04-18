"""
tabs/settings.py
Radiology2u RIS — Settings tab.

Doctor Registry — add, search, edit and delete referring doctors saved in DB.
Doctors can then be selected in the New Referral Order tab to auto-fill the form.
"""

import streamlit as st

from sheets_db import (
    delete_doctor,
    get_all_doctors,
    save_doctor,
    search_doctors,
    update_doctor,
)
from tabs.constants import STATES


def render() -> None:
    """Render the Settings tab (Doctor Registry)."""

    st.subheader("⚙️ Settings — Doctor Registry", divider="blue")
    st.markdown(
        "Manage your referring doctor list. "
        "Select a saved doctor on the **New Referral Order** tab to auto-fill their details."
    )
    st.markdown("")

    action_tabs = st.tabs(["➕  Add New Doctor", "🔍  Search & Manage"])

    # ── ADD NEW DOCTOR ─────────────────────────────────────────────────────────
    with action_tabs[0]:
        st.markdown('<div class="r2u-section">Doctor Details</div>',
                    unsafe_allow_html=True)

        a1, a2 = st.columns(2)
        with a1:
            d_title       = st.selectbox("Title *",
                                         ["Dr", "Prof", "A/Prof", "Mr", "Ms", "Mrs"],
                                         key="add_title")
            d_firstname   = st.text_input("First Name *", key="add_fn")
            d_lastname    = st.text_input("Last Name *", key="add_ln")
            d_provider_no = st.text_input("Medicare Provider Number *",
                                          placeholder="e.g. 2123456A",
                                          key="add_prov")
            d_hpii        = st.text_input("HPI-I (optional)",
                                          placeholder="8003610000000000",
                                          key="add_hpii")
            d_specialty   = st.text_input("Specialty / Discipline",
                                          placeholder="e.g. General Practice, Oncology",
                                          key="add_spec")
        with a2:
            d_practice = st.text_input("Practice / Clinic Name", key="add_prac")
            d_address  = st.text_input("Street Address", key="add_addr")
            d_suburb   = st.text_input("Suburb", key="add_sub")
            d_state    = st.selectbox("State / Territory", STATES, key="add_state")
            d_postcode = st.text_input("Postcode", max_chars=4, key="add_pc")

        b1, b2 = st.columns(2)
        with b1:
            d_phone = st.text_input("Phone", placeholder="(02) 0000 0000", key="add_ph")
            d_fax   = st.text_input("Fax",   placeholder="(02) 0000 0000", key="add_fax")
        with b2:
            d_email = st.text_input("Email",  placeholder="doctor@practice.com.au",
                                    key="add_email")
            d_notes = st.text_input("Notes (optional)",
                                    placeholder="e.g. Preferred referral contact",
                                    key="add_notes")

        st.markdown("")
        if st.button("💾 Save Doctor to Registry", type="primary",
                     use_container_width=True, key="btn_add_doctor"):
            if not d_firstname.strip() or not d_lastname.strip() or not d_provider_no.strip():
                st.error("First name, last name and Medicare provider number are required.")
            else:
                save_doctor({
                    "title":           d_title,
                    "firstname":       d_firstname,
                    "lastname":        d_lastname,
                    "provider_number": d_provider_no,
                    "hpii":            d_hpii,
                    "practice":        d_practice,
                    "address":         d_address,
                    "suburb":          d_suburb,
                    "state":           d_state,
                    "postcode":        d_postcode,
                    "phone":           d_phone,
                    "fax":             d_fax,
                    "email":           d_email,
                    "specialty":       d_specialty,
                    "notes":           d_notes,
                })
                st.success(
                    f"✅ {d_title} {d_firstname.strip()} {d_lastname.strip()} "
                    f"saved to the doctor registry."
                )
                st.rerun()

    # ── SEARCH & MANAGE ────────────────────────────────────────────────────────
    with action_tabs[1]:
        sc1, sc2 = st.columns([4, 1])
        with sc1:
            search_q = st.text_input(
                "Search doctors",
                placeholder="Search by name, provider number, or practice...",
                key="dr_search_q",
                label_visibility="collapsed",
            )
        with sc2:
            search_btn = st.button("🔍 Search", use_container_width=True,
                                   key="dr_search_btn")

        if search_btn and search_q.strip():
            doctors = search_doctors(search_q.strip())
        else:
            doctors = get_all_doctors()

        if not doctors:
            st.info("No doctors found. Add doctors using the **Add New Doctor** tab.")
        else:
            st.caption(f"{len(doctors)} doctor(s) in registry")

            for doc in doctors:
                full_name = (
                    f"{doc['title']} {doc['firstname']} {doc['lastname']}  —  "
                    f"Provider: {doc['provider_number']}"
                    + (f"  |  {doc['practice']}" if doc.get("practice") else "")
                )
                with st.expander(full_name):
                    e1, e2 = st.columns(2)
                    with e1:
                        st.markdown(f"**Specialty:** {doc.get('specialty') or '—'}")
                        st.markdown(f"**Practice:** {doc.get('practice') or '—'}")
                        st.markdown(
                            f"**Address:** {doc.get('address') or ''}, "
                            f"{doc.get('suburb') or ''} "
                            f"{doc.get('state') or ''} {doc.get('postcode') or ''}"
                        )
                    with e2:
                        st.markdown(f"**Phone:** {doc.get('phone') or '—'}")
                        st.markdown(f"**Fax:** {doc.get('fax') or '—'}")
                        st.markdown(f"**Email:** {doc.get('email') or '—'}")
                        st.markdown(f"**HPI-I:** {doc.get('hpii') or '—'}")
                    if doc.get("notes"):
                        st.caption(f"Notes: {doc['notes']}")

                    st.markdown("**Edit details:**")
                    ed1, ed2 = st.columns(2)
                    with ed1:
                        e_title = st.selectbox(
                            "Title",
                            ["Dr", "Prof", "A/Prof", "Mr", "Ms", "Mrs"],
                            index=["Dr","Prof","A/Prof","Mr","Ms","Mrs"].index(doc["title"])
                                  if doc["title"] in ["Dr","Prof","A/Prof","Mr","Ms","Mrs"]
                                  else 0,
                            key=f"e_title_{doc['doctor_id']}")
                        e_fn    = st.text_input("First Name",
                                                value=doc["firstname"],
                                                key=f"e_fn_{doc['doctor_id']}")
                        e_ln    = st.text_input("Last Name",
                                                value=doc["lastname"],
                                                key=f"e_ln_{doc['doctor_id']}")
                        e_prov  = st.text_input("Provider No.",
                                                value=doc["provider_number"],
                                                key=f"e_prov_{doc['doctor_id']}")
                        e_hpii  = st.text_input("HPI-I",
                                                value=doc.get("hpii", ""),
                                                key=f"e_hpii_{doc['doctor_id']}")
                        e_spec  = st.text_input("Specialty",
                                                value=doc.get("specialty", ""),
                                                key=f"e_spec_{doc['doctor_id']}")
                    with ed2:
                        e_prac  = st.text_input("Practice",
                                                value=doc.get("practice", ""),
                                                key=f"e_prac_{doc['doctor_id']}")
                        e_addr  = st.text_input("Address",
                                                value=doc.get("address", ""),
                                                key=f"e_addr_{doc['doctor_id']}")
                        e_sub   = st.text_input("Suburb",
                                                value=doc.get("suburb", ""),
                                                key=f"e_sub_{doc['doctor_id']}")
                        state_i = STATES.index(doc["state"]) \
                                  if doc.get("state") in STATES else 0
                        e_state = st.selectbox("State", STATES, index=state_i,
                                               key=f"e_state_{doc['doctor_id']}")
                        e_pc    = st.text_input("Postcode", max_chars=4,
                                                value=doc.get("postcode", ""),
                                                key=f"e_pc_{doc['doctor_id']}")
                        e_ph    = st.text_input("Phone",
                                                value=doc.get("phone", ""),
                                                key=f"e_ph_{doc['doctor_id']}")
                        e_fax   = st.text_input("Fax",
                                                value=doc.get("fax", ""),
                                                key=f"e_fax_{doc['doctor_id']}")
                        e_email = st.text_input("Email",
                                                value=doc.get("email", ""),
                                                key=f"e_email_{doc['doctor_id']}")

                    sv_col, del_col = st.columns([3, 1])
                    with sv_col:
                        if st.button("💾 Update Doctor",
                                     key=f"upd_{doc['doctor_id']}",
                                     use_container_width=True):
                            update_doctor(doc["doctor_id"], {
                                "title":           e_title,
                                "firstname":       e_fn,
                                "lastname":        e_ln,
                                "provider_number": e_prov,
                                "hpii":            e_hpii,
                                "specialty":       e_spec,
                                "practice":        e_prac,
                                "address":         e_addr,
                                "suburb":          e_sub,
                                "state":           e_state,
                                "postcode":        e_pc,
                                "phone":           e_ph,
                                "fax":             e_fax,
                                "email":           e_email,
                            })
                            st.success(f"✅ {e_fn} {e_ln} updated.")
                            st.rerun()
                    with del_col:
                        if st.button("🗑️ Delete",
                                     key=f"del_{doc['doctor_id']}",
                                     use_container_width=True,
                                     type="secondary"):
                            st.session_state[f"confirm_del_{doc['doctor_id']}"] = True

                    if st.session_state.get(f"confirm_del_{doc['doctor_id']}"):
                        st.warning(
                            f"Are you sure you want to delete "
                            f"**{doc['title']} {doc['firstname']} {doc['lastname']}** "
                            f"from the registry? This cannot be undone."
                        )
                        cf1, cf2 = st.columns(2)
                        with cf1:
                            if st.button("Yes, delete",
                                         key=f"yes_del_{doc['doctor_id']}",
                                         type="primary",
                                         use_container_width=True):
                                delete_doctor(doc["doctor_id"])
                                del st.session_state[f"confirm_del_{doc['doctor_id']}"]
                                st.success("Doctor removed from registry.")
                                st.rerun()
                        with cf2:
                            if st.button("Cancel",
                                         key=f"no_del_{doc['doctor_id']}",
                                         use_container_width=True):
                                del st.session_state[f"confirm_del_{doc['doctor_id']}"]
                                st.rerun()
