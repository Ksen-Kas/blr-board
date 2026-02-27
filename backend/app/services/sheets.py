"""Google Sheets service — reads the same 'Pipeline' sheet the Telegram bot writes to.

Auth: uses GOOGLE_CREDENTIALS_JSON_CONTENT (JSON string in env),
same as the bot's sheets.py.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

from app import config
from app.models.job import Job

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Must match the bot's COLUMN_ORDER exactly
COLUMNS = [
    ("Company", "company"),
    ("Role", "role"),
    ("Region", "region"),
    ("Seniority", "seniority"),
    ("Operator vs Contractor", "operator_vs_contractor"),
    ("Status", "status"),
    ("Submission #", "submission_count"),
    ("Reapply Reason", "reapply_reason"),
    ("Applied Date", "applied_date"),
    ("Follow-up 1", "followup_1"),
    ("Follow-up 2", "followup_2"),
    ("Response Date", "response_date"),
    ("Days to First Response", "days_to_response"),
    ("Source", "source"),
    ("Channel", "channel"),
    ("Role Fit", "role_fit"),
    ("Stop Flags", "stop_flags"),
    ("Contact", "contact"),
    ("CV", "cv"),
    ("CL", "cl"),
    ("Comment", "comment"),
]

FIELD_NAMES = [c[1] for c in COLUMNS]
FIELD_TO_COL = {field: idx + 1 for idx, (_, field) in enumerate(COLUMNS)}

FOLLOWUP_DAYS = 4  # Applied + N days without response = needs_followup


def _get_worksheet(name: str = "Pipeline") -> gspread.Worksheet:
    """Connect to a worksheet — same auth as the bot."""
    info = json.loads(config.GOOGLE_CREDENTIALS_JSON_CONTENT)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(config.GOOGLE_SHEET_ID).worksheet(name)


def _compute_needs_followup(job: Job) -> bool:
    """Applied + FOLLOWUP_DAYS without response or followup → needs follow-up."""
    if job.status.lower() not in ("applied", "waiting"):
        return False
    if job.response_date:
        return False
    if not job.applied_date:
        return False
    try:
        applied = datetime.strptime(job.applied_date.strip(), "%Y-%m-%d")
        return datetime.now() - applied >= timedelta(days=FOLLOWUP_DAYS)
    except ValueError:
        return False


def _compute_duplicates(jobs: list[Job]) -> None:
    """Mark possible duplicates: exact URL match or fuzzy company+role+region."""
    url_map: dict[str, list[int]] = defaultdict(list)
    fuzzy_map: dict[str, list[int]] = defaultdict(list)

    for i, j in enumerate(jobs):
        if j.source:
            url_map[j.source.strip()].append(i)
        key = f"{j.company.strip().lower()}|{j.role.strip().lower()}|{j.region.strip().lower()}"
        fuzzy_map[key].append(i)

    def _mark_group(indices: list[int]) -> None:
        if len(indices) <= 1:
            return
        for idx in indices:
            jobs[idx].possible_duplicate = True
            # Point to the other entries in the group
            others = [i for i in indices if i != idx]
            refs = [f"Row {jobs[i].row_num}: {jobs[i].company} — {jobs[i].role}" for i in others]
            jobs[idx].duplicate_of = "; ".join(refs)

    for indices in url_map.values():
        _mark_group(indices)

    for indices in fuzzy_map.values():
        _mark_group(indices)


class SheetsService:
    def __init__(self):
        self._cache: list[Job] = []
        self._cache_valid = False

    def invalidate_cache(self):
        self._cache_valid = False

    def get_all_jobs(self) -> list[Job]:
        if self._cache_valid:
            return self._cache

        ws = _get_worksheet()
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return []

        data_rows = all_values[1:]  # skip header

        jobs = []
        for row_idx, row in enumerate(data_rows):
            job_data: dict = {"row_num": row_idx + 2}  # 1-indexed + header
            for col_idx, (_, field) in enumerate(COLUMNS):
                val = row[col_idx] if col_idx < len(row) else ""
                job_data[field] = str(val).strip()
            if not job_data.get("company") and not job_data.get("role"):
                continue
            job = Job(**job_data)
            job.needs_followup = _compute_needs_followup(job)
            jobs.append(job)

        _compute_duplicates(jobs)

        self._cache = jobs
        self._cache_valid = True
        return jobs

    def get_job_by_row(self, row_num: int) -> Job | None:
        jobs = self.get_all_jobs()
        return next((j for j in jobs if j.row_num == row_num), None)

    def find_job(self, company: str, role: str) -> Job | None:
        """Duplicate check — same logic as bot's sheets.check_duplicate."""
        jobs = self.get_all_jobs()
        c = company.strip().lower()
        r = role.strip().lower()
        for j in jobs:
            if j.company.strip().lower() == c and j.role.strip().lower() == r:
                return j
        return None

    def find_by_url(self, url: str) -> Job | None:
        """Exact URL duplicate check."""
        url = url.strip()
        if not url:
            return None
        jobs = self.get_all_jobs()
        for j in jobs:
            if j.source.strip() == url:
                return j
        return None

    def add_row(self, data: dict) -> None:
        """Append a row — same format as the bot's sheets.add_row."""
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
            "Contact": data.get("contact", ""),
            "CV": "",
            "CL": "",
            "Comment": data.get("summary", ""),
        }

        row = [row_map[col[0]] for col in COLUMNS]
        ws = _get_worksheet()
        ws.append_row(row, value_input_option="USER_ENTERED")
        self.invalidate_cache()

    def update_cell(self, row_num: int, field: str, value: str):
        ws = _get_worksheet()
        col_idx = FIELD_NAMES.index(field) + 1
        ws.update_cell(row_num, col_idx, value)
        self.invalidate_cache()

    def update_job(self, row_num: int, updates: dict) -> Job | None:
        valid_updates = {
            field: str(value)
            for field, value in updates.items()
            if field in FIELD_NAMES and value is not None
        }
        if not valid_updates:
            return self.get_job_by_row(row_num)

        ws = _get_worksheet()
        # Avoid immediate read-after-write from Sheets to prevent caching stale values.
        for field, value in valid_updates.items():
            ws.update_cell(row_num, FIELD_TO_COL[field], value)

        if self._cache_valid:
            for idx, job in enumerate(self._cache):
                if job.row_num != row_num:
                    continue
                updated = job.model_copy(update=valid_updates)
                updated.needs_followup = _compute_needs_followup(updated)
                self._cache[idx] = updated
                _compute_duplicates(self._cache)
                return updated

        self.invalidate_cache()
        return self.get_job_by_row(row_num)

    # ─── Events worksheet ─────────────────────────────────────────────────

    def get_events_ws(self) -> gspread.Worksheet:
        """Get or create the Events worksheet."""
        try:
            return _get_worksheet("Events")
        except gspread.WorksheetNotFound:
            info = json.loads(config.GOOGLE_CREDENTIALS_JSON_CONTENT)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(config.GOOGLE_SHEET_ID)
            ws = spreadsheet.add_worksheet("Events", rows=1000, cols=4)
            ws.append_row(["job_id", "timestamp", "event_type", "data"])
            return ws

    def log_event(self, job_id: int, event_type: str, data: str = "{}"):
        """Write an event row to the Events sheet."""
        ws = self.get_events_ws()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([job_id, timestamp, event_type, data], value_input_option="USER_ENTERED")
        logger.info("Event logged: job=%d type=%s", job_id, event_type)

    def get_events(self, job_id: int) -> list[dict]:
        """Get all events for a job."""
        ws = self.get_events_ws()
        all_rows = ws.get_all_values()
        if len(all_rows) < 2:
            return []
        events = []
        for row in all_rows[1:]:
            if len(row) >= 4 and str(row[0]).strip() == str(job_id):
                events.append({
                    "job_id": int(row[0]),
                    "timestamp": row[1],
                    "event_type": row[2],
                    "data": row[3],
                })
        return events


sheets_service = SheetsService()
