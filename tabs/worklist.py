"""
tabs/worklist.py
Radiology2u RIS — Imaging Worklist tab.
Displays all referral orders with live metrics, filters, and status management.
"""

from datetime import date

import pandas as pd
import streamlit as st

from sheets_db import get_referral_by_id, get_worklist, update_referral_status
from tabs.constants import (
    ALL_MODALITIES,
    ALL_STATUSES,
    ALL_URGENCIES,
    STATUS_ICON,
    URGENCY_ICON,
)


def render() -> None:
    """Render the Imaging Worklist tab."""

    st.subheader("Imaging Worklist", divider="blue")
    st.caption("All referral orders received by Radiology2u. Sorted by clinical urgency.")

    # ── Live metrics ──────────────────────────────────────────────────────────
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

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 1])
    with fc1:
        f_status   = st.selectbox(
            "Filter by Status", ["All"] + ALL_STATUSES, key="wl_status"
        )
    with fc2:
        f_urgency  = st.selectbox(
            "Filter by Urgency", ["All"] + ALL_URGENCIES[::-1], key="wl_urgency"
        )
    with fc3:
        f_modality = st.selectbox(
            "Filter by Modality", ["All"] + ALL_MODALITIES, key="wl_mod"
        )
    with fc4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh Worklist", use_container_width=True):
            st.rerun()

    # ── Worklist table ────────────────────────────────────────────────────────
    rows = get_worklist(status=f_status, urgency=f_urgency, modality=f_modality)

    if not rows:
        st.info("No imaging orders match the current filters.")
    else:
        df = pd.DataFrame(rows)
        df["urgency"] = df["urgency"].apply(
            lambda x: f"{URGENCY_ICON.get(x, '')} {x}"
        )
        df["status"] = df["status"].apply(
            lambda x: f"{STATUS_ICON.get(x, '')} {x}"
        )
        df["⚠️"] = df["allergies"].apply(lambda x: "⚠️" if x else "")

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

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=min(38 * len(df) + 38, 520),
        )
        st.caption(f"{len(df)} order(s) shown")

    # ── Order detail / status update ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### View Order / Update Status")

    vu1, vu2 = st.columns([3, 1])
    with vu1:
        lookup_id = st.text_input(
            "Enter Accession Number", placeholder="e.g. R2U-20260417-3F9A", key="wl_lookup"
        )
    with vu2:
        st.markdown("<br>", unsafe_allow_html=True)
        lookup_btn = st.button(
            "🔍 Look Up", use_container_width=True, key="wl_lookup_btn"
        )

    if lookup_btn and lookup_id.strip():
        rec = get_referral_by_id(lookup_id.strip().upper())
        if not rec:
            st.error(f"Accession number **{lookup_id.strip().upper()}** not found.")
        else:
            with st.expander(
                f"📋 {rec.get('accession_number', rec['referral_id'])} — "
                f"{rec.get('lastname', '')}, {rec.get('firstname', '')}",
                expanded=True,
            ):
                d1, d2, d3 = st.columns(3)
                d1.markdown(
                    f"**Patient:** {rec.get('lastname','')}, {rec.get('firstname','')}"
                )
                d1.markdown(f"**DOB:** {rec.get('dob', '—')}")
                d1.markdown(f"**Medicare:** {rec.get('medicare', '—')}")
                d2.markdown(f"**Modality:** {rec.get('modality', '—')}")
                d2.markdown(f"**Examination:** {rec.get('body_region', '—')}")
                d2.markdown(
                    f"**Urgency:** "
                    f"{URGENCY_ICON.get(rec.get('urgency',''), '')} "
                    f"{rec.get('urgency', '—')}"
                )
                d3.markdown(f"**Referring Dr:** {rec.get('referring_doctor', '—')}")
                d3.markdown(f"**Provider No:** {rec.get('provider_number', '—')}")
                d3.markdown(f"**Date Issued:** {rec.get('referral_date', '—')}")

                if rec.get("allergies"):
                    st.error(f"⚠️ **Allergies / ADR:** {rec['allergies']}")

                with st.expander("Clinical Details"):
                    st.markdown(
                        f"**Clinical Indication:**\n\n{rec.get('clinical_indication','—')}"
                    )
                    if rec.get("relevant_history"):
                        st.markdown(f"**History:** {rec['relevant_history']}")
                    if rec.get("medications"):
                        st.markdown(f"**Medications:** {rec['medications']}")
                    if rec.get("investigations"):
                        st.markdown(f"**Investigations Done:** {rec['investigations']}")
                    if rec.get("special_requirements"):
                        st.markdown(
                            f"**Special Requirements:** {rec['special_requirements']}"
                        )

                st.markdown("**Update Order Status:**")
                ns_col, sv_col = st.columns([3, 1])
                cur_idx = (
                    ALL_STATUSES.index(rec["status"])
                    if rec["status"] in ALL_STATUSES
                    else 0
                )
                new_status = ns_col.selectbox(
                    "New Status",
                    ALL_STATUSES,
                    index=cur_idx,
                    key=f"ns_{rec['referral_id']}",
                )
                with sv_col:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(
                        "💾 Save",
                        key=f"sv_{rec['referral_id']}",
                        use_container_width=True,
                    ):
                        update_referral_status(rec["referral_id"], new_status)
                        st.success(f"Status updated to **{new_status}**.")
                        st.rerun()
