"""
tabs/constants.py
Shared lookup tables and constants used across all Radiology2u RIS modules.
Import from here — never duplicate these lists in individual tab files.
"""

URGENCY_ICON: dict[str, str] = {
    "Emergency (same day)":          "🔴",
    "Urgent (within 7 days)":        "🟠",
    "Semi-urgent (within 30 days)":  "🟡",
    "Routine":                        "🟢",
}

STATUS_ICON: dict[str, str] = {
    "Pending":     "⏳",
    "Scheduled":   "📅",
    "In Progress": "🔬",
    "Reported":    "✅",
    "Cancelled":   "❌",
}

ALL_STATUSES: list[str] = [
    "Pending",
    "Scheduled",
    "In Progress",
    "Reported",
    "Cancelled",
]

ALL_MODALITIES: list[str] = [
    "Ultrasound",
    "CT Scan",
    "MRI",
    "X-Ray (Plain Film)",
    "Nuclear Medicine",
    "PET Scan",
    "Fluoroscopy",
    "Mammography",
    "DXA (Bone Density)",
    "Interventional Radiology",
    "Other",
]

# Listed least → most urgent (reverse for UI urgency selectbox)
ALL_URGENCIES: list[str] = [
    "Routine",
    "Semi-urgent (within 30 days)",
    "Urgent (within 7 days)",
    "Emergency (same day)",
]

STATES: list[str] = ["", "NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]
