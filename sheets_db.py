"""
sheets_db.py  —  Phase 1: SQLite local database
Phase 2: Replace each function body with gspread (Google Sheets) calls.

Google Sheet structure (Phase 2):
  Tab "Patients"  — one row per patient  (PRIMARY KEY: medicare)
  Tab "Referrals" — one row per referral (PRIMARY KEY: referral_id)
  Tab "Doctors"   — one row per doctor   (PRIMARY KEY: doctor_id)
"""

import os
import uuid
import sqlite3
from datetime import datetime

# ── Database path (same directory as this file) ───────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ris_database.db")

# ── Phase 2 setup (uncomment and fill in when ready) ─────────────────────────
# import gspread
# from google.oauth2.service_account import Credentials
# _SCOPES     = ["https://www.googleapis.com/auth/spreadsheets"]
# _CREDS_FILE = "credentials.json"
# _SHEET_NAME = "EReferral_DB"
#
# def _get_sheet():
#     creds  = Credentials.from_service_account_file(_CREDS_FILE, scopes=_SCOPES)
#     client = gspread.authorize(creds)
#     return client.open(_SHEET_NAME)
# ─────────────────────────────────────────────────────────────────────────────


# ── Modality → 2-4 char code map ────────────────────────────────────────────
_MODALITY_CODE: dict[str, str] = {
    "Ultrasound":               "US",
    "CT Scan":                  "CT",
    "MRI":                      "MRI",
    "X-Ray (Plain Film)":       "XR",
    "Nuclear Medicine":         "NM",
    "PET Scan":                 "PET",
    "Fluoroscopy":              "FL",
    "Mammography":              "MG",
    "DXA (Bone Density)":       "DXA",
    "Interventional Radiology": "IR",
    "Other":                    "OTH",
}


def _next_patient_seq(year: str) -> int:
    """
    Return the next sequential patient counter for the given year.
    Scans patient_id values of form 'R2U-YYYY-NNNN' and increments max.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(patient_id, 10) AS INTEGER)) "
            "FROM patients WHERE patient_id LIKE ?",
            (f"R2U-{year}-%",),
        ).fetchone()
    current_max = row[0] if (row and row[0] is not None) else 0
    return current_max + 1


def _next_study_seq(medicare: str) -> int:
    """
    Return the next sequential study counter for a patient (all-time).
    Counts existing referrals for that Medicare number.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM referrals WHERE medicare = ?",
            (medicare.replace(" ", ""),),
        ).fetchone()
    return (row[0] if row else 0) + 1


# ── Internal helpers ──────────────────────────────────────────────────────────
def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Called automatically on import."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                medicare        TEXT PRIMARY KEY,
                irn             INTEGER,
                lastname        TEXT,
                firstname       TEXT,
                dob             TEXT,
                gender          TEXT,
                indigenous      TEXT,
                medicare_expiry TEXT,
                dva             TEXT,
                concession      TEXT,
                address         TEXT,
                phone           TEXT,
                email           TEXT,
                ihi             TEXT,
                interpreter     TEXT,
                language        TEXT,
                date_registered TEXT,
                patient_id      TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referral_id          TEXT PRIMARY KEY,
                medicare             TEXT,
                to_clinic            TEXT,
                modality             TEXT,
                body_region          TEXT,
                urgency              TEXT,
                referral_date        TEXT,
                valid_until          TEXT,
                clinical_indication  TEXT,
                relevant_history     TEXT,
                medications          TEXT,
                allergies            TEXT,
                investigations       TEXT,
                special_requirements TEXT,
                referring_doctor     TEXT,
                provider_number      TEXT,
                practice             TEXT,
                doctor_phone         TEXT,
                doctor_email         TEXT,
                status               TEXT DEFAULT 'Pending',
                date_created         TEXT,
                accession_number     TEXT,
                FOREIGN KEY (medicare) REFERENCES patients(medicare)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                doctor_id       TEXT PRIMARY KEY,
                title           TEXT,
                firstname       TEXT NOT NULL,
                lastname        TEXT NOT NULL,
                provider_number TEXT NOT NULL,
                hpii            TEXT,
                practice        TEXT,
                address         TEXT,
                suburb          TEXT,
                state           TEXT,
                postcode        TEXT,
                phone           TEXT,
                fax             TEXT,
                email           TEXT,
                specialty       TEXT,
                notes           TEXT,
                date_added      TEXT
            )
        """)
        # ── Migration: add patient_id to existing patients table ──────────
        try:
            conn.execute("ALTER TABLE patients ADD COLUMN patient_id TEXT")
            existing = conn.execute(
                "SELECT medicare FROM patients WHERE patient_id IS NULL ORDER BY date_registered"
            ).fetchall()
            current_year = datetime.now().strftime("%Y")
            for i, row in enumerate(existing, start=1):
                pid = f"R2U-{current_year}-{i:04d}"
                conn.execute(
                    "UPDATE patients SET patient_id=? WHERE medicare=?",
                    (pid, row["medicare"]),
                )
        except sqlite3.OperationalError:
            pass  # column already exists

        # ── Migration: add accession_number to existing referrals table ───
        try:
            conn.execute("ALTER TABLE referrals ADD COLUMN accession_number TEXT")
            existing = conn.execute(
                "SELECT r.referral_id, r.medicare, r.modality, p.patient_id "
                "FROM referrals r LEFT JOIN patients p ON r.medicare = p.medicare "
                "WHERE r.accession_number IS NULL ORDER BY r.date_created"
            ).fetchall()
            study_counters: dict = {}
            for row in existing:
                pid      = row["patient_id"] or "R2U-LEGACY-0000"
                medicare = row["medicare"]
                mod_code = _MODALITY_CODE.get(row["modality"], "OTH")
                study_counters[medicare] = study_counters.get(medicare, 0) + 1
                # Extract year-seq from patient_id if possible, else fallback
                parts = pid.split("-")
                yr_seq = f"{parts[1]}-{parts[2]}" if len(parts) >= 3 else "LEGACY-0000"
                acc = f"R2U-{yr_seq}-{study_counters[medicare]:03d}-{mod_code}"
                conn.execute(
                    "UPDATE referrals SET accession_number=? WHERE referral_id=?",
                    (acc, row["referral_id"]),
                )
        except sqlite3.OperationalError:
            pass  # column already exists

        conn.commit()


init_db()


# ── Public API ────────────────────────────────────────────────────────────────

def find_patient_by_medicare(medicare: str) -> dict | None:
    """Return patient dict if found, else None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE medicare = ?",
            (medicare.replace(" ", ""),)
        ).fetchone()
        return dict(row) if row else None


def register_patient(patient_data: dict) -> str:
    """
    Insert a new patient or update existing record (upsert on Medicare number).
    Returns the patient's Patient ID (stable across updates).

    Phase 2:
        sheet = _get_sheet().worksheet("Patients")
        # check existing row, append or update accordingly
    """
    now          = datetime.now().strftime("%d/%m/%Y %H:%M")
    current_year = datetime.now().strftime("%Y")
    medicare_key = patient_data.get("medicare", "").replace(" ", "")
    # Check if patient already has an ID (returning patient)
    with _conn() as conn:
        existing = conn.execute(
            "SELECT patient_id FROM patients WHERE medicare=?", (medicare_key,)
        ).fetchone()
    if existing and existing["patient_id"]:
        new_pid = existing["patient_id"]
    else:
        seq     = _next_patient_seq(current_year)
        new_pid = f"R2U-{current_year}-{seq:04d}"
    with _conn() as conn:
        conn.execute("""
            INSERT INTO patients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(medicare) DO UPDATE SET
                irn=excluded.irn, lastname=excluded.lastname,
                firstname=excluded.firstname, dob=excluded.dob,
                gender=excluded.gender, indigenous=excluded.indigenous,
                medicare_expiry=excluded.medicare_expiry, dva=excluded.dva,
                concession=excluded.concession, address=excluded.address,
                phone=excluded.phone, email=excluded.email,
                ihi=excluded.ihi, interpreter=excluded.interpreter,
                language=excluded.language,
                patient_id=COALESCE(patients.patient_id, excluded.patient_id)
        """, (
            medicare_key,
            patient_data.get("irn"),
            patient_data.get("lastname"),
            patient_data.get("firstname"),
            patient_data.get("dob"),
            patient_data.get("gender"),
            patient_data.get("indigenous"),
            patient_data.get("medicare_expiry"),
            patient_data.get("dva") or "",
            patient_data.get("concession") or "",
            patient_data.get("address"),
            patient_data.get("phone"),
            patient_data.get("email") or "",
            patient_data.get("ihi") or "",
            patient_data.get("interpreter"),
            patient_data.get("language") or "",
            now,
            new_pid,
        ))
        conn.commit()
        row = conn.execute(
            "SELECT patient_id FROM patients WHERE medicare=?", (medicare_key,)
        ).fetchone()
        return row["patient_id"] if row else new_pid


def create_referral(referral_data: dict) -> str:
    """
    Insert a new referral with status = 'Pending'. Silently ignores duplicates.
    Returns the accession_number for this study.

    Phase 2:
        sheet = _get_sheet().worksheet("Referrals")
        sheet.append_row([...])
    """
    now              = datetime.now().strftime("%d/%m/%Y %H:%M")
    medicare_key     = referral_data.get("medicare", "").replace(" ", "")
    mod_code         = _MODALITY_CODE.get(referral_data.get("modality", ""), "OTH")
    study_seq        = _next_study_seq(medicare_key)
    # Derive year-seq from the patient's patient_id (R2U-YYYY-NNNN)
    with _conn() as conn:
        pid_row = conn.execute(
            "SELECT patient_id FROM patients WHERE medicare=?", (medicare_key,)
        ).fetchone()
    pid_str = pid_row["patient_id"] if (pid_row and pid_row["patient_id"]) else None
    if pid_str:
        parts    = pid_str.split("-")           # ['R2U', 'YYYY', 'NNNN']
        yr_seq   = f"{parts[1]}-{parts[2]}" if len(parts) >= 3 else "0000-0000"
    else:
        yr_seq   = datetime.now().strftime("%Y") + "-0000"
    accession_number = referral_data.get("accession_number") or (
        f"R2U-{yr_seq}-{study_seq:03d}-{mod_code}"
    )
    internal_id = str(uuid.uuid4())
    with _conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO referrals VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            internal_id,
            referral_data.get("medicare", "").replace(" ", ""),
            referral_data.get("to_clinic"),
            referral_data.get("modality"),
            referral_data.get("body_region"),
            referral_data.get("urgency"),
            referral_data.get("date"),
            referral_data.get("valid_until"),
            referral_data.get("clinical_indication"),
            referral_data.get("relevant_history") or "",
            referral_data.get("medications") or "",
            referral_data.get("allergies") or "",
            referral_data.get("investigations") or "",
            referral_data.get("special_requirements") or "",
            referral_data.get("referring_doctor"),
            referral_data.get("provider_number"),
            referral_data.get("practice"),
            referral_data.get("doctor_phone") or "",
            referral_data.get("doctor_email") or "",
            "Pending",
            now,
            accession_number,
        ))
        conn.commit()
    return accession_number


def get_worklist(
    status: str = "All",
    urgency: str = "All",
    modality: str = "All",
) -> list[dict]:
    """
    Return referrals joined with patient names, sorted by clinical urgency then date.

    Phase 2:
        Fetch both Google Sheet tabs, merge on medicare, filter in Python.
    """
    query = """
        SELECT
            r.referral_id,
            r.accession_number,
            COALESCE(p.patient_id, '—') AS patient_id,
            COALESCE(p.lastname || ', ' || p.firstname, '—') AS patient_name,
            COALESCE(p.dob, '—')  AS dob,
            r.medicare,
            r.modality,
            r.body_region,
            r.urgency,
            r.referring_doctor,
            r.practice,
            r.referral_date,
            r.valid_until,
            r.status,
            r.allergies,
            r.date_created
        FROM referrals r
        LEFT JOIN patients p ON r.medicare = p.medicare
        WHERE 1=1
    """
    params: list = []
    if status != "All":
        query += " AND r.status = ?"
        params.append(status)
    if urgency != "All":
        query += " AND r.urgency = ?"
        params.append(urgency)
    if modality != "All":
        query += " AND r.modality = ?"
        params.append(modality)

    # Clinical urgency sort
    query += """
        ORDER BY
            CASE r.urgency
                WHEN 'Emergency (same day)'        THEN 1
                WHEN 'Urgent (within 7 days)'      THEN 2
                WHEN 'Semi-urgent (within 30 days)' THEN 3
                ELSE 4
            END,
            r.referral_date ASC
    """
    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_referral_by_id(identifier: str) -> dict | None:
    """
    Return full referral + patient details by accession_number (preferred)
    or internal referral_id (fallback).
    """
    with _conn() as conn:
        row = conn.execute("""
            SELECT r.*, p.lastname, p.firstname, p.dob, p.gender,
                   p.ihi, p.interpreter, p.language, p.indigenous,
                   p.dva, p.concession, p.patient_id
            FROM referrals r
            LEFT JOIN patients p ON r.medicare = p.medicare
            WHERE r.accession_number = ? OR r.referral_id = ?
        """, (identifier, identifier)).fetchone()
        return dict(row) if row else None


def update_referral_status(referral_id: str, status: str) -> None:
    """
    Update the status column for a given referral.

    Phase 2:
        sheet = _get_sheet().worksheet("Referrals")
        # find row index by referral_id, update status cell
    """
    with _conn() as conn:
        conn.execute(
            "UPDATE referrals SET status = ? WHERE referral_id = ?",
            (status, referral_id)
        )
        conn.commit()


def search_patients(query: str) -> list[dict]:
    """
    Search patients by surname, first name, Medicare number, or Patient ID.

    Phase 2:
        records = _get_sheet().worksheet("Patients").get_all_records()
        return [r for r in records if query.lower() in ...]
    """
    like = f"%{query.strip()}%"
    with _conn() as conn:
        rows = conn.execute("""
            SELECT * FROM patients
            WHERE lastname LIKE ? OR firstname LIKE ?
               OR medicare LIKE ? OR patient_id LIKE ?
            ORDER BY lastname, firstname
        """, (like, like, like, like)).fetchall()
        return [dict(r) for r in rows]


def get_all_patients() -> list[dict]:
    """Return all patients ordered alphabetically by surname then firstname."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM patients ORDER BY lastname, firstname"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_patient(medicare: str) -> None:
    """Delete a patient record (and their referrals) by Medicare number."""
    with _conn() as conn:
        conn.execute("DELETE FROM referrals WHERE medicare = ?", (medicare,))
        conn.execute("DELETE FROM patients WHERE medicare = ?", (medicare,))


def get_patient_referrals(medicare: str) -> list[dict]:
    """Return all referrals for a patient (Medicare number), newest first."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT * FROM referrals WHERE medicare = ?
            ORDER BY date_created DESC
        """, (medicare,)).fetchall()
        return [dict(r) for r in rows]


def get_all_referrals() -> list[dict]:
    """Return all referrals. Kept for backward compatibility."""
    return get_worklist()


def update_patient(medicare: str, patient_data: dict) -> None:
    """
    Update an existing patient record by Medicare number.

    Phase 2:
        Find row by Medicare number in Patients sheet and update all cells.
    """
    with _conn() as conn:
        conn.execute("""
            UPDATE patients SET
                irn=?, lastname=?, firstname=?, dob=?, gender=?,
                indigenous=?, medicare_expiry=?, dva=?, concession=?,
                address=?, phone=?, email=?, ihi=?, interpreter=?, language=?
            WHERE medicare=?
        """, (
            patient_data.get("irn"),
            patient_data.get("lastname", "").strip(),
            patient_data.get("firstname", "").strip(),
            patient_data.get("dob"),
            patient_data.get("gender"),
            patient_data.get("indigenous"),
            patient_data.get("medicare_expiry"),
            patient_data.get("dva") or "",
            patient_data.get("concession") or "",
            patient_data.get("address", "").strip(),
            patient_data.get("phone", "").strip(),
            patient_data.get("email") or "",
            patient_data.get("ihi") or "",
            patient_data.get("interpreter"),
            patient_data.get("language") or "",
            medicare,
        ))
        conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# DOCTOR REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

def save_doctor(doctor_data: dict) -> str:
    """
    Insert a new doctor record. Returns the generated doctor_id.

    Phase 2:
        sheet = _get_sheet().worksheet("Doctors")
        sheet.append_row([doctor_id, ...])
    """
    doctor_id = str(uuid.uuid4())[:8].upper()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    with _conn() as conn:
        conn.execute("""
            INSERT INTO doctors VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            doctor_id,
            doctor_data.get("title", ""),
            doctor_data.get("firstname", "").strip(),
            doctor_data.get("lastname", "").strip(),
            doctor_data.get("provider_number", "").strip(),
            doctor_data.get("hpii", "").strip(),
            doctor_data.get("practice", "").strip(),
            doctor_data.get("address", "").strip(),
            doctor_data.get("suburb", "").strip(),
            doctor_data.get("state", ""),
            doctor_data.get("postcode", "").strip(),
            doctor_data.get("phone", "").strip(),
            doctor_data.get("fax", "").strip(),
            doctor_data.get("email", "").strip(),
            doctor_data.get("specialty", "").strip(),
            doctor_data.get("notes", "").strip(),
            now,
        ))
        conn.commit()
    return doctor_id


def update_doctor(doctor_id: str, doctor_data: dict) -> None:
    """
    Update an existing doctor record by doctor_id.

    Phase 2:
        Find row by doctor_id in Doctors sheet and update all cells.
    """
    with _conn() as conn:
        conn.execute("""
            UPDATE doctors SET
                title=?, firstname=?, lastname=?, provider_number=?,
                hpii=?, practice=?, address=?, suburb=?, state=?,
                postcode=?, phone=?, fax=?, email=?, specialty=?, notes=?
            WHERE doctor_id=?
        """, (
            doctor_data.get("title", ""),
            doctor_data.get("firstname", "").strip(),
            doctor_data.get("lastname", "").strip(),
            doctor_data.get("provider_number", "").strip(),
            doctor_data.get("hpii", "").strip(),
            doctor_data.get("practice", "").strip(),
            doctor_data.get("address", "").strip(),
            doctor_data.get("suburb", "").strip(),
            doctor_data.get("state", ""),
            doctor_data.get("postcode", "").strip(),
            doctor_data.get("phone", "").strip(),
            doctor_data.get("fax", "").strip(),
            doctor_data.get("email", "").strip(),
            doctor_data.get("specialty", "").strip(),
            doctor_data.get("notes", "").strip(),
            doctor_id,
        ))
        conn.commit()


def delete_doctor(doctor_id: str) -> None:
    """
    Remove a doctor record by doctor_id.

    Phase 2:
        Find row by doctor_id in Doctors sheet and delete it.
    """
    with _conn() as conn:
        conn.execute("DELETE FROM doctors WHERE doctor_id = ?", (doctor_id,))
        conn.commit()


def search_doctors(query: str) -> list[dict]:
    """
    Search doctors by surname, first name, provider number, or practice name.

    Phase 2:
        records = _get_sheet().worksheet("Doctors").get_all_records()
        return [r for r in records if query.lower() in ...]
    """
    like = f"%{query.strip()}%"
    with _conn() as conn:
        rows = conn.execute("""
            SELECT * FROM doctors
            WHERE lastname LIKE ? OR firstname LIKE ?
               OR provider_number LIKE ? OR practice LIKE ?
            ORDER BY lastname, firstname
        """, (like, like, like, like)).fetchall()
        return [dict(r) for r in rows]


def get_all_doctors() -> list[dict]:
    """Return all doctors ordered alphabetically by surname then firstname."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM doctors ORDER BY lastname, firstname"
        ).fetchall()
        return [dict(r) for r in rows]


def get_doctor_by_id(doctor_id: str) -> dict | None:
    """Return a single doctor dict by doctor_id, or None if not found."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM doctors WHERE doctor_id = ?", (doctor_id,)
        ).fetchone()
        return dict(row) if row else None

