"""Google Drive helpers for patient/visit document storage."""

from __future__ import annotations

import io
import re
from typing import Any

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

_FOLDER_MIME = "application/vnd.google-apps.folder"
_DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive"]


def _has_real_value(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and not text.startswith("REPLACE_")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._ -]+", "_", (value or "").strip())


def _get_service_account_dict() -> dict[str, Any] | None:
    cfg = st.secrets.get("gcp_service_account", {})
    required = {
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url",
    }
    if not cfg or any(not _has_real_value(cfg.get(k)) for k in required):
        return None

    normalized = dict(cfg)
    raw_key = str(normalized.get("private_key", ""))
    # Support both TOML styles: literal '\n' sequences or true multiline strings.
    key_text = raw_key.replace("\\n", "\n").replace("\r\n", "\n").strip()
    # Remove accidental indentation/spaces introduced by secrets editors.
    key_lines = [line.strip() for line in key_text.split("\n") if line.strip()]
    normalized["private_key"] = "\n".join(key_lines) + "\n"
    return normalized


def _get_oauth_dict() -> dict[str, Any] | None:
    cfg = st.secrets.get("google_oauth", {})
    required = {"client_id", "client_secret", "refresh_token", "token_uri"}
    if not cfg or any(not _has_real_value(cfg.get(k)) for k in required):
        return None
    return {k: str(v).strip() for k, v in dict(cfg).items()}


def _get_root_folder_id() -> str | None:
    gd_cfg = st.secrets.get("google_drive", {})
    folder_id = gd_cfg.get("root_folder_id", "")
    folder_id = str(folder_id).strip()
    return folder_id if _has_real_value(folder_id) else None


def is_drive_configured() -> bool:
    return bool((_get_oauth_dict() or _get_service_account_dict()) and _get_root_folder_id())


def _oauth_credentials() -> Credentials:
    oauth_cfg = _get_oauth_dict()
    if not oauth_cfg:
        raise RuntimeError("Google OAuth secrets are missing.")

    creds = Credentials(
        token=oauth_cfg.get("access_token") or None,
        refresh_token=oauth_cfg["refresh_token"],
        token_uri=oauth_cfg["token_uri"],
        client_id=oauth_cfg["client_id"],
        client_secret=oauth_cfg["client_secret"],
        scopes=_DRIVE_SCOPE,
    )
    if not creds.valid:
        creds.refresh(Request())
    return creds


@st.cache_resource(show_spinner=False)
def _drive_service():
    oauth_cfg = _get_oauth_dict()
    if oauth_cfg:
        creds = _oauth_credentials()
    else:
        svc_dict = _get_service_account_dict()
        if not svc_dict:
            raise RuntimeError(
                "Google Drive secrets are missing. Configure either google_oauth or gcp_service_account."
            )
        creds = service_account.Credentials.from_service_account_info(
            svc_dict,
            scopes=_DRIVE_SCOPE,
        )
    return build("drive", "v3", credentials=creds)


def _find_folder(service, parent_id: str, folder_name: str) -> str | None:
    escaped = folder_name.replace("'", "\\'")
    query = (
        f"mimeType='{_FOLDER_MIME}' and trashed=false and "
        f"name='{escaped}' and '{parent_id}' in parents"
    )
    response = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id,name)", pageSize=1)
        .execute()
    )
    files = response.get("files", [])
    return files[0]["id"] if files else None


def _ensure_folder(service, parent_id: str, folder_name: str) -> str:
    existing_id = _find_folder(service, parent_id, folder_name)
    if existing_id:
        return existing_id

    metadata = {
        "name": folder_name,
        "mimeType": _FOLDER_MIME,
        "parents": [parent_id],
    }
    created = (
        service.files()
        .create(body=metadata, fields="id")
        .execute()
    )
    return created["id"]


def upload_document(
    *,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    patient_id: str,
    patient_name: str,
    accession_number: str,
    category: str,
) -> dict[str, Any]:
    """Upload one file into Drive and return file metadata."""
    if not is_drive_configured():
        raise RuntimeError("Google Drive is not configured in secrets.")

    root_folder_id = _get_root_folder_id()
    if not root_folder_id:
        raise RuntimeError("Google Drive root folder ID is missing.")

    service = _drive_service()

    patient_folder_name = _safe_name(f"{patient_id}_{patient_name}") or "Unknown Patient"
    visit_folder_name = _safe_name(accession_number) or "Unassigned Visit"

    patient_folder_id = _ensure_folder(service, root_folder_id, patient_folder_name)
    visit_folder_id = _ensure_folder(service, patient_folder_id, visit_folder_name)

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
    metadata = {
        "name": _safe_name(filename) or "document",
        "parents": [visit_folder_id],
    }
    created = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,name,mimeType,size,webViewLink,webContentLink",
        )
        .execute()
    )
    created["category"] = category
    created["folder_id"] = visit_folder_id
    return created
