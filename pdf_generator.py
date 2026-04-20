"""
pdf_generator.py
Generates a professional A4 radiology referral PDF using ReportLab.
Compliant with Australian health documentation standards.
"""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
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
