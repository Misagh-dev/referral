"""
pdf_generator.py
Generates a professional A4 radiology referral PDF using ReportLab.
Compliant with Australian health documentation standards.
"""

import io
import json
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Colour palette ─────────────────────────────────────────────────────────────
DARK_BLUE   = colors.HexColor("#1e3a5f")
MID_BLUE    = colors.HexColor("#2e6da4")
LIGHT_BLUE  = colors.HexColor("#dce8f5")
LIGHT_GREY  = colors.HexColor("#f5f5f5")
MID_GREY    = colors.HexColor("#cccccc")
DARK_GREY   = colors.HexColor("#555555")
RED         = colors.HexColor("#b71c1c")
ORANGE      = colors.HexColor("#e65c00")
AMBER       = colors.HexColor("#e68a00")
GREEN       = colors.HexColor("#1b5e20")

# ── Report PDF colour palette (purple, from gen/info/report_template.json) ─────
RPT_DEEP    = colors.HexColor("#3a1c71")   # primary
RPT_MID     = colors.HexColor("#4e2c8e")   # secondary
RPT_ACCENT  = colors.HexColor("#633aa8")   # accent
RPT_LIGHT   = colors.HexColor("#ede8f7")   # light tint

# ── Branding template (assets bundled with the app) ──────────────────────────
_ASSETS        = Path(__file__).resolve().parent / "assets"
_TEMPLATE_FILE = _ASSETS / "report_template.json"


def _load_gen_template() -> dict:
    try:
        if _TEMPLATE_FILE.exists():
            return json.loads(_TEMPLATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _urgency_color(urgency: str) -> colors.Color:
    if "Emergency" in urgency:
        return RED
    if "Urgent (" in urgency:        # "Urgent (within 7 days)"
        return ORANGE
    if "Semi" in urgency:
        return AMBER
    return GREEN


def _calculate_age(dob_str: str) -> str:
    try:
        dob   = datetime.strptime(dob_str, "%d/%m/%Y")
        today = datetime.today()
        age   = (today.year - dob.year
                 - ((today.month, today.day) < (dob.month, dob.day)))
        return str(age)
    except Exception:
        return "—"


# ── Shared paragraph styles ────────────────────────────────────────────────────
def _styles() -> dict:
    return {
        "header_title": ParagraphStyle(
            "header_title", fontSize=17, textColor=colors.white,
            alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "header_sub": ParagraphStyle(
            "header_sub", fontSize=8.5, textColor=colors.white,
            alignment=TA_CENTER, fontName="Helvetica"),
        "urgency": ParagraphStyle(
            "urgency", fontSize=10.5, textColor=colors.white,
            alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "section": ParagraphStyle(
            "section", fontSize=8.5, textColor=DARK_BLUE,
            fontName="Helvetica-Bold"),
        "label": ParagraphStyle(
            "label", fontSize=7.5, textColor=DARK_GREY, fontName="Helvetica"),
        "value": ParagraphStyle(
            "value", fontSize=8.5, textColor=colors.black, fontName="Helvetica"),
        "body": ParagraphStyle(
            "body", fontSize=8.5, textColor=colors.black,
            fontName="Helvetica", leading=13),
        "allergy": ParagraphStyle(
            "allergy", fontSize=9, textColor=colors.white,
            fontName="Helvetica-Bold"),
        "sig": ParagraphStyle(
            "sig", fontSize=9, textColor=DARK_BLUE, fontName="Helvetica-Bold"),
        "footer": ParagraphStyle(
            "footer", fontSize=7, textColor=DARK_GREY,
            fontName="Helvetica", alignment=TA_CENTER, leading=10),
    }


def _section_header_table(text: str, width: float, s: dict) -> Table:
    """Blue-tinted section label bar."""
    t = Table([[Paragraph(text, s["section"])]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("BOX",           (0, 0), (-1, -1), 0.5, MID_GREY),
    ]))
    return t


def _content_table(text: str, width: float, s: dict) -> Table:
    """White content box beneath a section header."""
    t = Table([[Paragraph(text or "—", s["body"])]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ("BOX",           (0, 0), (-1, -1), 0.5, MID_GREY),
    ]))
    return t


def _lv(label: str, value, s: dict) -> list:
    """Label-value row pair for inner detail tables."""
    return [
        Paragraph(label, s["label"]),
        Paragraph(str(value) if value else "—", s["value"]),
    ]


def generate_referral_pdf(
    patient: dict,
    doctor: dict,
    referral: dict,
) -> bytes:
    """
    Build and return a professional A4 referral PDF as bytes.

    Parameters
    ----------
    patient  : Patient demographics dict
    doctor   : Referring doctor / practice dict
    referral : Referral request dict
    """
    buffer = io.BytesIO()
    W      = 170 * mm   # usable page width (A4 - 20 mm each side)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=14 * mm, bottomMargin=18 * mm,
    )

    s     = _styles()
    story = []

    # ── HEADER ────────────────────────────────────────────────────────────────
    title_tbl = Table([[Paragraph("RADIOLOGY REFERRAL", s["header_title"])]],
                      colWidths=[W])
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), DARK_BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    sub_text = (
        f"Australian e-Referral System  |  Confidential Medical Document  |  "
        f"Patient ID: {patient.get('patient_id', '—')}  |  "
        f"Accession: {referral.get('accession_number', '—')}  |  "
        f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    sub_tbl = Table([[Paragraph(sub_text, s["header_sub"])]], colWidths=[W])
    sub_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), MID_BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story += [title_tbl, sub_tbl, Spacer(1, 4 * mm)]

    # ── URGENCY BANNER ────────────────────────────────────────────────────────
    urg_tbl = Table(
        [[Paragraph(f"URGENCY: {referral['urgency'].upper()}", s["urgency"])]],
        colWidths=[W])
    urg_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _urgency_color(referral["urgency"])),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [urg_tbl, Spacer(1, 4 * mm)]

    # ── REFERRING DOCTOR  +  REFERRAL DETAILS (side by side) ─────────────────
    # Inner column widths
    L1, L2 = 30 * mm, 52 * mm   # doctor inner cols
    R1, R2 = 36 * mm, 48 * mm   # referral info inner cols

    doc_rows = [
        [Paragraph("REFERRING DOCTOR", s["section"]), ""],
        *[_lv("Doctor:", f"{doctor['title']} {doctor['firstname']} {doctor['lastname']}", s)],
        *[_lv("Provider No:", doctor["provider_number"], s)],
        *[_lv("HPI-I:", doctor["hpii"] or "—", s)],
        *[_lv("Practice:", doctor["practice"], s)],
        *[_lv("Address:", doctor["address"], s)],
        *[_lv("Phone:", doctor["phone"], s)],
        *[_lv("Fax:", doctor["fax"] or "—", s)],
        *[_lv("Email:", doctor["email"], s)],
    ]
    # Unwrap: each _lv() call already returns a list, no extra nesting needed
    doc_rows = [
        [Paragraph("REFERRING DOCTOR", s["section"]), ""],
        _lv("Doctor:",      f"{doctor['title']} {doctor['firstname']} {doctor['lastname']}", s),
        _lv("Provider No:", doctor["provider_number"], s),
        _lv("HPI-I:",       doctor["hpii"] or "—", s),
        _lv("Practice:",    doctor["practice"], s),
        _lv("Address:",     doctor["address"], s),
        _lv("Phone:",       doctor["phone"], s),
        _lv("Fax:",         doctor["fax"] or "—", s),
        _lv("Email:",       doctor["email"], s),
    ]

    ref_rows = [
        [Paragraph("REFERRAL DETAILS", s["section"]), ""],
        _lv("Referring To:", referral["to_clinic"], s),
        _lv("Modality:",     referral["modality"], s),
        _lv("Examination:",  referral["body_region"], s),
        _lv("Date Issued:",  referral["date"], s),
        _lv("Valid Until:",  referral["valid_until"], s),
        _lv("Accession No:", referral.get("accession_number", "—"), s),
    ]

    def _inner_style(header_span):
        return TableStyle([
            ("SPAN",          (0, 0), (1, 0)),
            ("BACKGROUND",    (0, 0), (1, 0),   LIGHT_BLUE),
            ("TOPPADDING",    (0, 0), (-1, -1),  2),
            ("BOTTOMPADDING", (0, 0), (-1, -1),  2),
            ("LEFTPADDING",   (0, 0), (-1, -1),  5),
            ("RIGHTPADDING",  (0, 0), (-1, -1),  5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1),  [colors.white, LIGHT_GREY]),
            ("BOX",           (0, 0), (-1, -1),  0.5, MID_GREY),
            ("LINEBELOW",     (0, 0), (-1, -1),  0.3, MID_GREY),
        ])

    doc_inner = Table(doc_rows, colWidths=[L1, L2])
    doc_inner.setStyle(_inner_style(True))

    ref_inner = Table(ref_rows, colWidths=[R1, R2])
    ref_inner.setStyle(_inner_style(True))

    two_col = Table([[doc_inner, ref_inner]],
                    colWidths=[L1 + L2 + 4 * mm, R1 + R2 + 4 * mm])
    two_col.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [two_col, Spacer(1, 4 * mm)]

    # ── PATIENT DETAILS ───────────────────────────────────────────────────────
    story.append(_section_header_table("PATIENT DETAILS", W, s))

    age      = _calculate_age(patient["dob"])
    col_a_w  = 28 * mm
    col_b_w  = 55 * mm
    col_c_w  = 28 * mm
    col_d_w  = 59 * mm

    # Build left-column and right-column rows, then zip side-by-side
    left_rows = [
        _lv("Patient ID:",          patient.get("patient_id", "—"), s),
        _lv("Full Name:",           f"{patient['lastname'].upper()}, {patient['firstname']}", s),
        _lv("Date of Birth:",       f"{patient['dob']}  (Age: {age})", s),
        _lv("Gender:",              patient["gender"], s),
        _lv("Medicare No:",         f"{patient['medicare']}  IRN: {patient['irn']}", s),
        _lv("Medicare Expiry:",     patient["medicare_expiry"], s),
        _lv("DVA File No:",         patient["dva"] or "—", s),
    ]
    right_rows = [
        _lv("", "", s),
        _lv("Address:",             patient["address"], s),
        _lv("Phone:",               patient["phone"], s),
        _lv("Email:",               patient["email"] or "—", s),
        _lv("Concession Card:",     patient["concession"] or "—", s),
        _lv("ATSI Status:",         patient["indigenous"], s),
        _lv("IHI:",                 patient["ihi"] or "—", s),
    ]

    combined = [lr + rr for lr, rr in zip(left_rows, right_rows)]

    # Interpreter row if needed
    if patient["interpreter"] == "Yes":
        lang = patient.get("language") or "Not specified"
        combined.append(
            _lv("Interpreter:", f"Yes – {lang}", s) +
            _lv("", "", s)
        )

    pt_table = Table(combined,
                     colWidths=[col_a_w, col_b_w, col_c_w, col_d_w])
    pt_table.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [colors.white, LIGHT_GREY]),
        ("BOX",           (0, 0), (-1, -1), 0.5, MID_GREY),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, MID_GREY),
    ]))
    story += [pt_table, Spacer(1, 4 * mm)]

    # ── CLINICAL SECTIONS ─────────────────────────────────────────────────────
    def _clinical(title, content):
        if not content:
            return []
        return [
            _section_header_table(title, W, s),
            _content_table(content, W, s),
            Spacer(1, 3 * mm),
        ]

    story += _clinical("CLINICAL INDICATION / REASON FOR REFERRAL",
                        referral["clinical_indication"])
    story += _clinical("RELEVANT MEDICAL HISTORY",
                        referral["relevant_history"])
    story += _clinical("CURRENT MEDICATIONS",
                        referral["medications"])

    # Allergy block (highlighted red)
    if referral.get("allergies"):
        allergy_tbl = Table(
            [[Paragraph(
                f"[!]  ALLERGIES / ADVERSE DRUG REACTIONS:  {referral['allergies']}",
                s["allergy"])]],
            colWidths=[W])
        allergy_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), RED),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ]))
        story += [allergy_tbl, Spacer(1, 3 * mm)]

    story += _clinical("RELEVANT INVESTIGATIONS ALREADY PERFORMED",
                        referral["investigations"])
    story += _clinical("SPECIAL REQUIREMENTS / INSTRUCTIONS",
                        referral["special_requirements"])

    # ── SIGNATURE BLOCK ───────────────────────────────────────────────────────
    story += [Spacer(1, 5 * mm),
              HRFlowable(width=W, thickness=0.5, color=MID_GREY),
              Spacer(1, 4 * mm)]

    sig_left = ParagraphStyle("sl", fontSize=9, fontName="Helvetica-Bold",
                               textColor=DARK_BLUE)
    sig_norm = ParagraphStyle("sn", fontSize=9, fontName="Helvetica",
                               textColor=colors.black)

    sig_data = [[
        Paragraph(
            f"Referring Doctor: {doctor['title']} {doctor['firstname']} {doctor['lastname']}",
            sig_left),
        Paragraph(f"Provider No: {doctor['provider_number']}", sig_norm),
        Paragraph(f"Date: {referral['date']}", sig_norm),
    ]]
    sig_tbl = Table(sig_data, colWidths=[80 * mm, 50 * mm, 40 * mm])
    sig_tbl.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 10 * mm))

    sig_line_tbl = Table(
        [[Paragraph("Signature: ___________________________________________", sig_norm),
          Paragraph("", sig_norm)]],
        colWidths=[100 * mm, 70 * mm])
    story.append(sig_line_tbl)
    story.append(Spacer(1, 5 * mm))
    story.append(HRFlowable(width=W, thickness=0.5, color=MID_GREY))
    story.append(Spacer(1, 2 * mm))

    # ── FOOTER ────────────────────────────────────────────────────────────────
    footer_text = (
        f"Valid: {referral['date']} – {referral['valid_until']}  |  "
        f"Accession: {referral.get('accession_number') or referral.get('referral_id', '—')}  |  "
        "CONFIDENTIAL – This document contains private health information protected under the "
        "Privacy Act 1988 (Cth) and the Australian Privacy Principles (APPs). "
        "Unauthorised disclosure is prohibited."
    )
    story.append(Paragraph(footer_text, s["footer"]))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_report_pdf(
    patient: dict,
    referral: dict,
    report: dict,
) -> bytes:
    """
    Build and return a formal A4 radiology report PDF with full clinic branding
    loaded from gen/info/report_template.json (logo, purple palette, clinician
    details, disclaimer).

    Parameters
    ----------
    patient  : Patient demographics dict
    referral : Referral / study dict
    report   : Report dict (findings, impression, conclusion, radiologist, status)
    """
    # ── Load branding ────────────────────────────────────────────────────────
    tmpl           = _load_gen_template()
    clinic_name    = tmpl.get("clinic_name",        "Radiology2U")
    clinic_role    = tmpl.get("clinic_role",        "Mobile Ultrasound Services")
    clinic_addr    = tmpl.get("clinic_address",     "")
    clinic_phone   = tmpl.get("clinic_phone",       "")
    clinic_email   = tmpl.get("clinic_email",       "")
    clinician_name = tmpl.get("clinician_name",     "")
    clinician_cred = tmpl.get("clinician_credentials", "")
    clinician_spec = tmpl.get("Clinician_specialty","")
    accreditation  = tmpl.get("accreditation",      "")
    disclaimer_txt = tmpl.get("disclaimer",         "")

    buffer = io.BytesIO()
    W      = 170 * mm

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=12 * mm,  bottomMargin=16 * mm,
    )

    s     = _styles()
    story = []

    # ── Inline styles for the report layout ──────────────────────────────────
    st_center_hdr  = ParagraphStyle("rch",  fontName="Helvetica",      fontSize=8.5,
                                    textColor=colors.white, leading=15)
    st_right_hdr   = ParagraphStyle("rrh",  fontName="Helvetica",      fontSize=8,
                                    textColor=colors.HexColor("#d4c8f0"),
                                    alignment=TA_RIGHT, leading=12)
    st_rpt_section = ParagraphStyle("rrs",  fontName="Helvetica-Bold", fontSize=8.5,
                                    textColor=RPT_DEEP)
    st_provider    = ParagraphStyle("rpv",  fontName="Helvetica",      fontSize=8,
                                    textColor=DARK_GREY, leading=12)
    st_disclaimer  = ParagraphStyle("rdis", fontName="Helvetica",      fontSize=7.5,
                                    textColor=DARK_GREY, leading=11)

    # ── HEADER: logo | clinic + title | contact ───────────────────────────────
    logo_path = _ASSETS / "logo.png"
    if logo_path.exists():
        logo_cell = Image(str(logo_path), width=28 * mm, height=28 * mm)
    else:
        logo_cell = Paragraph(
            f'<font name="Helvetica-Bold" size="16" color="white">{clinic_name[:4]}</font>',
            ParagraphStyle("lf", textColor=colors.white),
        )

    center_markup = (
        f'<font name="Helvetica-Bold" size="14" color="white">{clinic_name}</font><br/>'
        f'<font name="Helvetica" size="8" color="#d4c8f0">{clinic_role}</font><br/><br/>'
        f'<font name="Helvetica-Bold" size="10" color="#c5b8e8">RADIOLOGY REPORT</font>'
    )
    center_cell = Paragraph(center_markup, st_center_hdr)

    right_lines = []
    if clinic_phone:
        right_lines.append(clinic_phone)
    if clinic_email:
        right_lines.append(clinic_email)
    right_cell = Paragraph("<br/>".join(right_lines), st_right_hdr)

    hdr_tbl = Table(
        [[logo_cell, center_cell, right_cell]],
        colWidths=[33 * mm, 95 * mm, 42 * mm],
    )
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), RPT_DEEP),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))

    # Sub-bar: generated timestamp only
    sub_text = f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    sub_tbl = Table([[Paragraph(sub_text, s["header_sub"])]], colWidths=[W])
    sub_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), RPT_MID),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [hdr_tbl, sub_tbl, Spacer(1, 4 * mm)]

    # ── Section helpers (purple) ──────────────────────────────────────────────
    def _rpt_hdr(title: str) -> Table:
        t = Table([[Paragraph(title, st_rpt_section)]], colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), RPT_LIGHT),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 7),
            ("BOX",           (0, 0), (-1, -1), 0.5, MID_GREY),
        ]))
        return t

    def _rpt_body(content: str) -> Table:
        t = Table([[Paragraph(content or "—", s["body"])]], colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.white),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("BOX",           (0, 0), (-1, -1), 0.5, MID_GREY),
        ]))
        return t

    def _rpt_section(title: str, content: str) -> list:
        if not content:
            return []
        return [_rpt_hdr(title), _rpt_body(content), Spacer(1, 4 * mm)]

    # ── STUDY INFORMATION ─────────────────────────────────────────────────────
    story.append(_rpt_hdr("STUDY INFORMATION"))
    age  = _calculate_age(patient.get("dob", ""))
    L, R = 28 * mm, 57 * mm

    study_rows = [
        _lv("Patient Name:",  f"{patient.get('lastname','').upper()}, {patient.get('firstname','')}", s),
        _lv("Date of Birth:", f"{patient.get('dob', '—')}  (Age: {age})", s),
        _lv("Patient ID:",    patient.get("patient_id", "—"), s),
        _lv("Modality:",      referral.get("modality", "—"), s),
        _lv("Examination:",   referral.get("body_region", "—"), s),
        _lv("Study Date:",    referral.get("referral_date") or referral.get("date_created", "—"), s),
        _lv("Referring Dr:",  referral.get("referring_doctor", "—"), s),
        _lv("Provider No:",   referral.get("provider_number", "—"), s),
    ]
    study_tbl_data = []
    for i in range(0, len(study_rows), 2):
        row = study_rows[i] + (study_rows[i + 1] if i + 1 < len(study_rows) else ["", ""])
        study_tbl_data.append(row)

    study_tbl = Table(study_tbl_data, colWidths=[L, R, L, R])
    study_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [colors.white, RPT_LIGHT]),
        ("BOX",           (0, 0), (-1, -1), 0.5, MID_GREY),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, MID_GREY),
    ]))
    story += [study_tbl, Spacer(1, 4 * mm)]

    # ── CLINICAL INDICATION ───────────────────────────────────────────────────
    story += _rpt_section("CLINICAL INDICATION", referral.get("clinical_indication", ""))

    # ── REPORT BODY ───────────────────────────────────────────────────────────
    story += _rpt_section("FINDINGS",                    report.get("findings",   ""))
    story += _rpt_section("IMPRESSION",                  report.get("impression", ""))
    story += _rpt_section("CONCLUSION / RECOMMENDATION", report.get("conclusion", ""))

    # ── RADIOLOGIST SIGNATURE ─────────────────────────────────────────────────
    story += [
        Spacer(1, 6 * mm),
        HRFlowable(width=W, thickness=0.5, color=RPT_MID),
        Spacer(1, 4 * mm),
    ]

    sig_bold = ParagraphStyle("sb", fontSize=9, fontName="Helvetica-Bold",
                               textColor=RPT_DEEP)
    sig_norm = ParagraphStyle("sn", fontSize=9, fontName="Helvetica",
                               textColor=colors.black)

    radiologist       = report.get("radiologist", "").strip() or "___________________________"
    # Append RANZCR credential if not already present
    if "RANZCR" not in radiologist:
        radiologist_display = f"{radiologist}, RANZCR"
    else:
        radiologist_display = radiologist
    perf_clinician = report.get("performing_clinician", "").strip() or "—"
    report_date    = datetime.now().strftime("%d/%m/%Y %H:%M")
    status_label   = report.get("status", "Draft").upper()
    status_color   = "#1b5e20" if status_label == "FINAL" else "#e65c00"

    sig_data = [
        [
            Paragraph(f"Reporting Radiologist: {radiologist_display}", sig_bold),
            Paragraph(f"Report Date: {report_date}", sig_norm),
            Paragraph(
                f'<font color="{status_color}"><b>Status: {status_label}</b></font>',
                ParagraphStyle("stc", fontSize=9, fontName="Helvetica"),
            ),
        ],
        [
            Paragraph(f"Performing Clinician: {perf_clinician}", sig_bold),
            Paragraph("", sig_norm),
            Paragraph("", sig_norm),
        ],
    ]
    sig_tbl = Table(sig_data, colWidths=[85 * mm, 45 * mm, 40 * mm])
    sig_tbl.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story += [
        sig_tbl,
        Spacer(1, 6 * mm),
        Table(
            [[Paragraph(
                f'Digitally signed  {report_date}',
                sig_norm,
            ),
              Paragraph("", sig_norm)]],
            colWidths=[120 * mm, 50 * mm],
        ),
        Spacer(1, 4 * mm),
        HRFlowable(width=W, thickness=0.5, color=RPT_MID),
        Spacer(1, 4 * mm),
    ]

    # ── DISCLAIMER ────────────────────────────────────────────────────────────
    if disclaimer_txt:
        disc_tbl = Table(
            [[Paragraph(f"<i>{disclaimer_txt}</i>", st_disclaimer)]],
            colWidths=[W],
        )
        disc_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GREY),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("BOX",           (0, 0), (-1, -1), 0.5, MID_GREY),
        ]))
        story += [disc_tbl, Spacer(1, 3 * mm)]

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
