import json
import logging

import gspread
from google.oauth2.service_account import Credentials

import config

logger = logging.getLogger(__name__)

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
    logger.info("sheets.get_sheet: parsing GOOGLE_CREDENTIALS_JSON_CONTENT")
    info = json.loads(config.GOOGLE_CREDENTIALS_JSON_CONTENT)
    logger.info("sheets.get_sheet: building Credentials for %s", info.get("client_email", "?"))
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    logger.info("sheets.get_sheet: authorizing gspread client")
    client = gspread.authorize(creds)
    logger.info("sheets.get_sheet: opening sheet %s", config.GOOGLE_SHEET_ID)
    sheet = client.open_by_key(config.GOOGLE_SHEET_ID).worksheet("Pipeline")
    logger.info("sheets.get_sheet: connected to worksheet '%s'", sheet.title)
    return sheet


def check_duplicate(company: str, role: str) -> dict:
    """Return {'found': True, 'max_submission': N} or {'found': False}."""
    logger.info("sheets.check_duplicate: company=%r role=%r", company, role)
    sheet = get_sheet()
    logger.info("sheets.check_duplicate: fetching all records")
    records = sheet.get_all_records()
    logger.info("sheets.check_duplicate: got %d records", len(records))

    company_norm = company.strip().lower()
    role_norm = role.strip().lower()

    matches = [
        r
        for r in records
        if str(r.get("Company", "")).strip().lower() == company_norm
        and str(r.get("Role", "")).strip().lower() == role_norm
    ]

    if not matches:
        logger.info("sheets.check_duplicate: no duplicate found")
        return {"found": False}

    max_sub = max(int(r.get("Submission #", 1) or 1) for r in matches)
    logger.info("sheets.check_duplicate: duplicate found, max_submission=%d", max_sub)
    return {"found": True, "max_submission": max_sub}


def add_row(data: dict) -> None:
    """Append a row to the Pipeline sheet in strict column order."""
    logger.info("sheets.add_row: start, company=%r role=%r", data.get("company"), data.get("role"))

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
    logger.info("sheets.add_row: row built (%d cells), calling get_sheet()", len(row))

    sheet = get_sheet()
    logger.info("sheets.add_row: calling append_row")
    sheet.append_row(row, value_input_option="USER_ENTERED")
    logger.info("sheets.add_row: done")
