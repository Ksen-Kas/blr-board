import json

import gspread
from google.oauth2.service_account import Credentials

import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

COLUMN_ORDER = [
    "Company",
    "Role",
    "Region",
    "Seniority",
    "Operator vs Contractor",
    "Status",
    "Submission #",
    "Reapply Reason",
    "Applied Date",
    "Follow-up 1",
    "Follow-up 2",
    "Response Date",
    "Days to First Response",
    "Source",
    "Channel",
    "Role Fit",
    "Stop Flags",
    "Contact",
    "CV",
    "CL",
    "Comment",
]


def get_sheet() -> gspread.Worksheet:
    if config.GOOGLE_CREDENTIALS_JSON_CONTENT:
        info = json.loads(config.GOOGLE_CREDENTIALS_JSON_CONTENT)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_JSON, scopes=SCOPES
        )
    client = gspread.authorize(creds)
    return client.open_by_key(config.GOOGLE_SHEET_ID).worksheet("Pipeline")


def check_duplicate(company: str, role: str) -> dict:
    """Return {'found': True, 'max_submission': N} or {'found': False}."""
    sheet = get_sheet()
    records = sheet.get_all_records()

    company_norm = company.strip().lower()
    role_norm = role.strip().lower()

    matches = [
        r
        for r in records
        if str(r.get("Company", "")).strip().lower() == company_norm
        and str(r.get("Role", "")).strip().lower() == role_norm
    ]

    if not matches:
        return {"found": False}

    max_sub = max(
        int(r.get("Submission #", 1) or 1) for r in matches
    )
    return {"found": True, "max_submission": max_sub}


def add_row(data: dict) -> None:
    """Append a row to the Pipeline sheet in strict column order."""
    stop_flags_raw = data.get("stop_flags", "NONE") or "NONE"
    stop_flags_val = "" if stop_flags_raw == "NONE" else stop_flags_raw

    row_map = {
        "Company": data.get("company", ""),
        "Role": data.get("role", ""),
        "Region": data.get("region", ""),
        "Seniority": data.get("seniority", ""),
        "Operator vs Contractor": data.get("operator", ""),
        "Status": "New",
        "Submission #": data.get("submission_num", 1),
        "Reapply Reason": data.get("reapply_reason", ""),
        "Applied Date": "",
        "Follow-up 1": "",
        "Follow-up 2": "",
        "Response Date": "",
        "Days to First Response": "",
        "Source": data.get("source_url", ""),
        "Channel": data.get("channel", ""),
        "Role Fit": data.get("role_fit", ""),
        "Stop Flags": stop_flags_val,
        "Contact": "",
        "CV": "",
        "CL": "",
        "Comment": data.get("summary", ""),
    }

    row = [row_map[col] for col in COLUMN_ORDER]

    sheet = get_sheet()
    sheet.append_row(row, value_input_option="USER_ENTERED")
