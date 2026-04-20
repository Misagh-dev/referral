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

from tabs import patient_search, settings, worklist

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Radiology2u — RIS",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Authentication gate ───────────────────────────────────────────────────────
if not st.user.is_logged_in:
    st.markdown("""
    <style>
        .login-card {
            max-width: 420px;
            margin: 8vh auto 0 auto;
            background: #ffffff;
            border-radius: 14px;
            padding: 2.5rem 2.5rem 2rem 2.5rem;
            box-shadow: 0 4px 28px rgba(13,43,78,0.13);
            text-align: center;
        }
        .login-card h1  { color: #0d2b4e; font-size: 1.7rem; margin-bottom: 0.2rem; }
        .login-card p   { color: #555; font-size: 0.88rem; margin-bottom: 1.6rem; }
        .login-footer   { margin-top: 1.4rem; font-size: 0.75rem; color: #aaa; }
    </style>
    <div class="login-card">
        <h1>🏥 Radiology2u</h1>
        <p>Radiology Information System (RIS)<br>
        Confidential — Privacy Act 1988 (Cth)</p>
    </div>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 1.5, 1])
    with col_c:
        st.button(
            "🔐 Sign in",
            on_click=st.login,
            args=("auth0",),
            use_container_width=True,
            type="primary",
        )
        st.markdown(
            '<p style="text-align:center;font-size:0.75rem;color:#aaa;">'
            'Authorised personnel only</p>',
            unsafe_allow_html=True,
        )
    st.stop()

# ── Authorisation check ───────────────────────────────────────────────────────
ALLOWED_EMAILS = st.secrets.get("allowed_emails", [])
if ALLOWED_EMAILS and st.user.get("email") not in ALLOWED_EMAILS:
    st.error("⛔ Access denied. Your account is not authorised to use this application.")
    st.caption(f"Signed in as: {st.user.get('email', 'unknown')}")
    st.button("Sign out", on_click=st.logout)
    st.stop()

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


cfg = load_settings()

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

# ── Navigation (radio triggers a real rerun on switch) ─────────────────────────
st.markdown("""
<style>
/* Style the horizontal radio to look like a tab bar */
div[data-testid="stRadio"] { margin-bottom: -0.5rem; }
div[data-testid="stRadio"] > div {
    display: flex; flex-direction: row; gap: 0;
    border-bottom: 2px solid #c8d8ea;
}
div[data-testid="stRadio"] > div > label {
    padding: 0.55rem 1.3rem;
    cursor: pointer;
    border: 1px solid transparent;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-bottom: -2px;
    font-weight: 500;
    color: #555;
    white-space: nowrap;
}
div[data-testid="stRadio"] > div > label:has(input:checked) {
    background: #ffffff;
    border-color: #c8d8ea;
    border-bottom-color: #ffffff;
    color: #0d2b4e;
    font-weight: 700;
}
div[data-testid="stRadio"] > div > label > div:first-child { display: none; }
</style>
""", unsafe_allow_html=True)

_NAV_LABELS = [
    "🏥  Patients & Referrals",
    "📊  Imaging Worklist",
    "⚙️  Settings",
]
_NAV_CLEAR = {
    "🏥  Patients & Referrals": [
        "rp_", "nv_", "ps_", "edit_", "act_",
        "ps_selected_mid", "ps_action",
    ],
    "📊  Imaging Worklist": ["wl_"],
    "⚙️  Settings": [
        "add_", "dr_search", "_dr_reg_nav", "_prev_dr_reg_nav",
        "_settings_nav", "_prev_settings_nav",
    ],
}

_active = st.radio(
    "Navigation",
    _NAV_LABELS,
    horizontal=True,
    label_visibility="collapsed",
    key="_nav",
)

# Detect switch — clear the NEWLY-SELECTED tab's stale state so it starts fresh
_prev_nav = st.session_state.get("_prev_nav", _active)
if _prev_nav != _active:
    for _k in list(st.session_state.keys()):
        for _pfx in _NAV_CLEAR.get(_active, []):
            if _k == _pfx or _k.startswith(_pfx):
                try:
                    del st.session_state[_k]
                except KeyError:
                    pass
                break
st.session_state["_prev_nav"] = _active

st.markdown("")

# Only the selected tab renders — inactive widgets don't exist, no stale state
if _active == "🏥  Patients & Referrals":
    patient_search.render(cfg)
elif _active == "📊  Imaging Worklist":
    worklist.render()
elif _active == "⚙️  Settings":
    settings.render()


# ── CSS ───────────────────────────────────────────────────────────────────────
