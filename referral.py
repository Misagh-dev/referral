"""
referral.py  —  Radiology2u RIS entry point
Run with:  streamlit run referral.py

This file owns only:
  - Streamlit page config
  - Global CSS / branding
  - Shared helpers (settings load/save)
  - Tab shell + routing to individual modules

To modify any tab, edit the corresponding file in tabs/
"""

import json
import os

import streamlit as st

from tabs import new_referral, patient_search, settings, worklist

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Radiology2u — RIS",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS / Radiology2u branding ─────────────────────────────────────────
st.markdown("""
<style>
    /* ── App header ── */
    .r2u-header {
        background: linear-gradient(135deg, #0d2b4e 0%, #1a5276 100%);
        color: white;
        padding: 1.4rem 2rem 1.1rem 2rem;
        border-radius: 10px;
        margin-bottom: 0.9rem;
        text-align: center;
    }
    .r2u-header h1   { margin: 0; font-size: 2rem; letter-spacing: 0.02em; }
    .r2u-header .sub { margin: 0.3rem 0 0 0; font-size: 0.88rem; opacity: 0.82; }

    /* ── Section label bar ── */
    .r2u-section {
        background: #eaf1fb;
        border-left: 4px solid #1a6faf;
        border-radius: 4px;
        padding: 0.45rem 0.9rem;
        margin: 1.1rem 0 0.6rem 0;
        font-weight: 700;
        color: #0d2b4e;
        font-size: 0.97rem;
    }

    /* ── Required fields note ── */
    .r2u-required-note { font-size: 0.8rem; color: #888; margin-bottom: 0.5rem; }

    /* ── Metric cards ── */
    .r2u-metric {
        background: #f0f5fb;
        border-radius: 8px;
        padding: 0.7rem 1rem;
        text-align: center;
        border: 1px solid #d0e3f5;
    }
    .r2u-metric-num   { font-size: 2rem; font-weight: 800; }
    .r2u-metric-label { font-size: 0.75rem; color: #555; margin-top: 0; }
</style>
""", unsafe_allow_html=True)

# ── Settings helpers ───────────────────────────────────────────────────────────
_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


def load_settings() -> dict:
    if os.path.exists(_SETTINGS_FILE):
        with open(_SETTINGS_FILE) as f:
            return json.load(f)
    return {}


def save_settings(data: dict) -> None:
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


cfg = load_settings()

# ── Session state defaults ─────────────────────────────────────────────────────
for _k, _v in [
    ("pdf_bytes",    None),
    ("referral_id",  None),
    ("pt_lastname",  ""),
    ("pt_firstname", ""),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── App header ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="r2u-header">
  <h1>🏥 Radiology2u</h1>
  <p class="sub">
    Radiology Information System (RIS) &nbsp;|&nbsp;
    Confidential — Privacy Act 1988 (Cth) &nbsp;|&nbsp;
    Australian Health Standards Compliant
  </p>
</div>
""", unsafe_allow_html=True)

# ── Tab navigation ─────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📋  New Referral Order",
    "📊  Imaging Worklist",
    "🔍  Patient Registry",
    "⚙️  Settings",
])

with tab1:
    new_referral.render(cfg)

with tab2:
    worklist.render()

with tab3:
    patient_search.render()

with tab4:
    settings.render()


# ── CSS ───────────────────────────────────────────────────────────────────────
