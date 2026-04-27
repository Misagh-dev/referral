"""Direct local file-system storage for patient/visit documents.

Files are written to STORAGE_ROOT (env var or st.secrets key), which should be
a directory mounted as a Docker volume so data persists across container restarts.
Defaults to a `ris_storage/` folder next to this file when nothing is configured.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import streamlit as st


def _get_storage_root() -> Path:
    """Return the storage root directory, creating it if needed."""
    root = ""
    try:
        root = st.secrets.get("storage_root", "").strip()
    except Exception:
        pass
    if not root:
        root = os.getenv("STORAGE_ROOT", "").strip()
    if not root:
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ris_storage")
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_local_storage_configured() -> bool:
    """Always True — direct file I/O works without any external service."""
    return True


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
    """Write a file to local storage and return its metadata dict."""
    root = _get_storage_root()
    folder = root / str(patient_id) / str(accession_number)
    folder.mkdir(parents=True, exist_ok=True)

    # Build a safe, timestamped filename to avoid collisions
    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_" for c in filename
    )
    storage_key = f"{patient_id}/{accession_number}/{int(time.time())}_{safe_name}"
    dest = root / storage_key

    # Prevent path traversal
    if not dest.resolve().is_relative_to(root.resolve()):
        raise ValueError("Invalid storage path")

    dest.write_bytes(file_bytes)

    return {
        "id": storage_key,
        "name": filename,
        "mimeType": mime_type,
        "size": len(file_bytes),
        "webViewLink": "",
    }


def download_document(storage_file_id: str, api_token: str = "") -> bytes | None:
    """Read a file from local storage. Returns bytes or None if not found."""
    root = _get_storage_root()
    target = (root / storage_file_id).resolve()

    # Prevent path traversal
    if not target.is_relative_to(root.resolve()):
        return None

    if not target.exists():
        return None

    return target.read_bytes()
