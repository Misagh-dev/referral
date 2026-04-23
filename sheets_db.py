"""
sheets_db.py  —  Radiology2u RIS data layer (SQLite or PostgreSQL)
"""

import os
import sqlite3
import uuid
from datetime import datetime

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit may not be available in non-app contexts
    st = None

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:  # pragma: no cover - package may be unavailable until installed
    psycopg2 = None
    RealDictCursor = None


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ris_database.db")

_MODALITY_CODE: dict[str, str] = {
    "Ultrasound": "US",
    "CT Scan": "CT",
    "MRI": "MRI",
    "X-Ray (Plain Film)": "XR",
    "Nuclear Medicine": "NM",
    "PET Scan": "PET",
    "Fluoroscopy": "FL",
    "Mammography": "MG",
    "DXA (Bone Density)": "DXA",
    "Interventional Radiology": "IR",
    "Other": "OTH",
}


def _get_database_url() -> str | None:
    if os.getenv("SUPABASE_DB_URL"):
        return os.getenv("SUPABASE_DB_URL")
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    if st is not None:
        try:
            supabase_cfg = st.secrets.get("supabase", {})
            if supabase_cfg.get("db_url"):
                return supabase_cfg["db_url"]
        except Exception:
            return None
    return None


_DATABASE_URL = _get_database_url()
_USING_POSTGRES = bool(_DATABASE_URL)


class _DBConnection:
    def __init__(self):
        if _USING_POSTGRES:
            if psycopg2 is None or RealDictCursor is None:
                raise RuntimeError(
                    "PostgreSQL support requires psycopg2-binary to be installed."
                )
            self._conn = psycopg2.connect(_DATABASE_URL, cursor_factory=RealDictCursor)
        else:
            self._conn = sqlite3.connect(DB_PATH)
            self._conn.row_factory = sqlite3.Row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        return False

    def execute(self, query: str, params=()):
        cursor = self._conn.cursor()
        if _USING_POSTGRES:
            query = query.replace("?", "%s")
        cursor.execute(query, params)
        return cursor

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


def _conn() -> _DBConnection:
    return _DBConnection()


def _ensure_column(table: str, column: str, definition: str) -> bool:
    try:
        with _conn() as conn:
            if _USING_POSTGRES:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}"
                )
                return True
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            return True
    except Exception:
        return False


def _next_patient_seq(year: str) -> int:
    with _conn() as conn:
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(patient_id, 10) AS INTEGER)) AS max_seq "
            "FROM patients WHERE patient_id LIKE ?",
            (f"R2U-{year}-%",),
        ).fetchone()
    current_max = row["max_seq"] if (row and row["max_seq"] is not None) else 0
    return current_max + 1


def _next_study_seq(medicare: str) -> int:
    with _conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS study_count FROM referrals WHERE medicare = ?",
            (medicare.replace(" ", ""),),
        ).fetchone()
    return (row["study_count"] if row else 0) + 1


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
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
            """
        )
        conn.execute(
            """
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
            """
        )
        conn.execute(
            """
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
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id      TEXT PRIMARY KEY,
                referral_id      TEXT,
                medicare         TEXT,
                accession_number TEXT,
                file_name        TEXT,
                mime_type        TEXT,
                file_size_bytes  INTEGER,
                category         TEXT,
                drive_file_id    TEXT,
                drive_web_link   TEXT,
                uploaded_at      TEXT
            )
            """
        )

    patient_id_added = _ensure_column("patients", "patient_id", "TEXT")
    if patient_id_added:
        with _conn() as conn:
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

    accession_added = _ensure_column("referrals", "accession_number", "TEXT")
    if accession_added:
        with _conn() as conn:
            existing = conn.execute(
                "SELECT r.referral_id, r.medicare, r.modality, p.patient_id "
                "FROM referrals r LEFT JOIN patients p ON r.medicare = p.medicare "
                "WHERE r.accession_number IS NULL ORDER BY r.date_created"
            ).fetchall()
            study_counters: dict[str, int] = {}
            for row in existing:
                pid = row["patient_id"] or "R2U-LEGACY-0000"
                medicare = row["medicare"]
                mod_code = _MODALITY_CODE.get(row["modality"], "OTH")
                study_counters[medicare] = study_counters.get(medicare, 0) + 1
                parts = pid.split("-")
                yr_seq = f"{parts[1]}-{parts[2]}" if len(parts) >= 3 else "LEGACY-0000"
                acc = f"R2U-{yr_seq}-{study_counters[medicare]:03d}-{mod_code}"
                conn.execute(
                    "UPDATE referrals SET accession_number=? WHERE referral_id=?",
                    (acc, row["referral_id"]),
                )


init_db()


def find_patient_by_medicare(medicare: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE medicare = ?",
            (medicare.replace(" ", ""),),
        ).fetchone()
        return dict(row) if row else None


def register_patient(patient_data: dict) -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    current_year = datetime.now().strftime("%Y")
    medicare_key = patient_data.get("medicare", "").replace(" ", "")
    with _conn() as conn:
        existing = conn.execute(
            "SELECT patient_id FROM patients WHERE medicare=?", (medicare_key,)
        ).fetchone()
    if existing and existing["patient_id"]:
        new_pid = existing["patient_id"]
    else:
        seq = _next_patient_seq(current_year)
        new_pid = f"R2U-{current_year}-{seq:04d}"
    with _conn() as conn:
        conn.execute(
            """
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
            """,
            (
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
            ),
        )
        row = conn.execute(
            "SELECT patient_id FROM patients WHERE medicare=?", (medicare_key,)
        ).fetchone()
        return row["patient_id"] if row else new_pid


def create_referral(referral_data: dict) -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    medicare_key = referral_data.get("medicare", "").replace(" ", "")
    mod_code = _MODALITY_CODE.get(referral_data.get("modality", ""), "OTH")
    study_seq = _next_study_seq(medicare_key)
    with _conn() as conn:
        pid_row = conn.execute(
            "SELECT patient_id FROM patients WHERE medicare=?", (medicare_key,)
        ).fetchone()
    pid_str = pid_row["patient_id"] if (pid_row and pid_row["patient_id"]) else None
    if pid_str:
        parts = pid_str.split("-")
        yr_seq = f"{parts[1]}-{parts[2]}" if len(parts) >= 3 else "0000-0000"
    else:
        yr_seq = datetime.now().strftime("%Y") + "-0000"
    accession_number = referral_data.get("accession_number") or (
        f"R2U-{yr_seq}-{study_seq:03d}-{mod_code}"
    )
    internal_id = str(uuid.uuid4())
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO referrals VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                internal_id,
                medicare_key,
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
            ),
        )
    return accession_number


def get_worklist(
    status: str = "All",
    urgency: str = "All",
    modality: str = "All",
    status_in: list | None = None,
) -> list[dict]:
    query = """
        SELECT
            r.referral_id,
            r.accession_number,
            COALESCE(p.patient_id, '—') AS patient_id,
            COALESCE(p.lastname || ', ' || p.firstname, '—') AS patient_name,
            COALESCE(p.dob, '—') AS dob,
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
    elif status_in:
        placeholders = ",".join("?" * len(status_in))
        query += f" AND r.status IN ({placeholders})"
        params.extend(status_in)
    if urgency != "All":
        query += " AND r.urgency = ?"
        params.append(urgency)
    if modality != "All":
        query += " AND r.modality = ?"
        params.append(modality)

    query += """
        ORDER BY
            CASE r.urgency
                WHEN 'Emergency (same day)' THEN 1
                WHEN 'Urgent (within 7 days)' THEN 2
                WHEN 'Semi-urgent (within 30 days)' THEN 3
                ELSE 4
            END,
            r.referral_date ASC
    """
    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_referral_by_id(identifier: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT r.*, p.lastname, p.firstname, p.dob, p.gender,
                   p.ihi, p.interpreter, p.language, p.indigenous,
                   p.dva, p.concession, p.patient_id
            FROM referrals r
            LEFT JOIN patients p ON r.medicare = p.medicare
            WHERE r.accession_number = ? OR r.referral_id = ?
            """,
            (identifier, identifier),
        ).fetchone()
        return dict(row) if row else None


def search_worklist(query: str) -> list[dict]:
    like = f"%{query.strip()}%"
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT
                r.referral_id,
                r.accession_number,
                COALESCE(p.patient_id, '—') AS patient_id,
                COALESCE(p.lastname || ', ' || p.firstname, '—') AS patient_name,
                COALESCE(p.dob, '—') AS dob,
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
            WHERE
                p.firstname LIKE ?
             OR p.lastname LIKE ?
             OR p.dob LIKE ?
             OR p.patient_id LIKE ?
             OR p.medicare LIKE ?
             OR r.accession_number LIKE ?
            ORDER BY
                CASE r.urgency
                    WHEN 'Emergency (same day)' THEN 1
                    WHEN 'Urgent (within 7 days)' THEN 2
                    WHEN 'Semi-urgent (within 30 days)' THEN 3
                    ELSE 4
                END,
                r.referral_date ASC
            """,
            (like, like, like, like, like, like),
        ).fetchall()
        return [dict(r) for r in rows]


def update_referral_status(referral_id: str, status: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE referrals SET status = ? WHERE referral_id = ?",
            (status, referral_id),
        )


def update_referral(referral_id: str, fields: dict) -> None:
    allowed = {
        "to_clinic", "modality", "body_region", "urgency",
        "referral_date", "valid_until", "clinical_indication",
        "relevant_history", "medications", "allergies",
        "investigations", "special_requirements",
        "referring_doctor", "provider_number", "practice",
        "doctor_phone", "doctor_email", "status",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{col} = ?" for col in updates)
    with _conn() as conn:
        conn.execute(
            f"UPDATE referrals SET {set_clause} WHERE referral_id = ?",
            (*updates.values(), referral_id),
        )


def search_patients(query: str) -> list[dict]:
    like = f"%{query.strip()}%"
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM patients
            WHERE lastname LIKE ? OR firstname LIKE ?
               OR medicare LIKE ? OR patient_id LIKE ?
            ORDER BY lastname, firstname
            """,
            (like, like, like, like),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_patients() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM patients ORDER BY lastname, firstname"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_patient(medicare: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM referrals WHERE medicare = ?", (medicare,))
        conn.execute("DELETE FROM patients WHERE medicare = ?", (medicare,))


def delete_referral(referral_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM referrals WHERE referral_id = ?", (referral_id,))


def get_patient_referrals(medicare: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM referrals WHERE medicare = ?
            ORDER BY date_created DESC
            """,
            (medicare,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_patient(medicare: str, patient_data: dict) -> None:
    with _conn() as conn:
        conn.execute(
            """
            UPDATE patients SET
                irn=?, lastname=?, firstname=?, dob=?, gender=?,
                indigenous=?, medicare_expiry=?, dva=?, concession=?,
                address=?, phone=?, email=?, ihi=?, interpreter=?, language=?
            WHERE medicare=?
            """,
            (
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
            ),
        )


def save_doctor(doctor_data: dict) -> str:
    doctor_id = str(uuid.uuid4())[:8].upper()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO doctors VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
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
            ),
        )
    return doctor_id


def update_doctor(doctor_id: str, doctor_data: dict) -> None:
    with _conn() as conn:
        conn.execute(
            """
            UPDATE doctors SET
                title=?, firstname=?, lastname=?, provider_number=?,
                hpii=?, practice=?, address=?, suburb=?, state=?,
                postcode=?, phone=?, fax=?, email=?, specialty=?, notes=?
            WHERE doctor_id=?
            """,
            (
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
            ),
        )


def delete_doctor(doctor_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM doctors WHERE doctor_id = ?", (doctor_id,))


def search_doctors(query: str) -> list[dict]:
    like = f"%{query.strip()}%"
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM doctors
            WHERE lastname LIKE ? OR firstname LIKE ?
               OR provider_number LIKE ? OR practice LIKE ?
            ORDER BY lastname, firstname
            """,
            (like, like, like, like),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_doctors() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM doctors ORDER BY lastname, firstname"
        ).fetchall()
        return [dict(r) for r in rows]


def get_doctor_by_id(doctor_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM doctors WHERE doctor_id = ?", (doctor_id,)
        ).fetchone()
        return dict(row) if row else None


def save_document_metadata(document_data: dict) -> str:
    document_id = str(uuid.uuid4())
    uploaded_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO documents (
                document_id, referral_id, medicare, accession_number,
                file_name, mime_type, file_size_bytes, category,
                drive_file_id, drive_web_link, uploaded_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                document_id,
                document_data.get("referral_id") or "",
                document_data.get("medicare") or "",
                document_data.get("accession_number") or "",
                document_data.get("file_name") or "",
                document_data.get("mime_type") or "",
                int(document_data.get("file_size_bytes") or 0),
                document_data.get("category") or "supporting_document",
                document_data.get("drive_file_id") or "",
                document_data.get("drive_web_link") or "",
                uploaded_at,
            ),
        )
    return document_id


def get_documents_for_referral(referral_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM documents
            WHERE referral_id = ?
            ORDER BY uploaded_at DESC
            """,
            (referral_id,),
        ).fetchall()
        return [dict(r) for r in rows]
