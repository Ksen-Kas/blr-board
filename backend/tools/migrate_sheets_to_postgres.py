"""One-shot migration from Google Sheets storage to Postgres storage.

Usage:
  PYTHONPATH=. ./.venv/bin/python tools/migrate_sheets_to_postgres.py
"""

from __future__ import annotations

from collections import defaultdict
import json
import sys

from app.services.postgres import postgres_service
from app.services.sheets import sheets_service


def _load_events_by_job_id() -> dict[int, list[dict]]:
    events_by_job_id: dict[int, list[dict]] = defaultdict(list)
    ws = sheets_service.get_events_ws()
    all_rows = ws.get_all_values()
    if len(all_rows) < 2:
        return events_by_job_id

    for row in all_rows[1:]:
        if len(row) < 4:
            continue
        raw_job_id = str(row[0]).strip()
        if not raw_job_id.isdigit():
            continue
        job_id = int(raw_job_id)
        events_by_job_id[job_id].append(
            {
                "job_id": job_id,
                "timestamp": row[1],
                "event_type": row[2],
                "data": row[3],
            }
        )
    return events_by_job_id


def main() -> int:
    if not postgres_service.enabled:
        print("ERROR: DATABASE_URL is missing. Postgres is not enabled.")
        return 1

    jobs = sheets_service.get_all_jobs()
    print(f"Found jobs in Sheets: {len(jobs)}")
    events_by_job_id = _load_events_by_job_id()

    upserted_jobs = 0
    migrated_events = 0

    for job in jobs:
        postgres_service.upsert_job(job)
        # Preserve existing values that are not covered by add_row mapping.
        postgres_service.update_job(
            job.row_num,
            {
                "status": job.status,
                "submission_count": job.submission_count,
                "reapply_reason": job.reapply_reason,
                "applied_date": job.applied_date,
                "followup_1": job.followup_1,
                "followup_2": job.followup_2,
                "response_date": job.response_date,
                "days_to_response": job.days_to_response,
                "contact": job.contact,
                "cv": job.cv,
                "cl": job.cl,
                "comment": job.comment,
                "role_fit": job.role_fit,
                "stop_flags": job.stop_flags,
            },
        )
        upserted_jobs += 1

        events = events_by_job_id.get(job.row_num, [])
        for event in events:
            postgres_service.upsert_event(
                job_id=job.row_num,
                timestamp=str(event.get("timestamp", "")),
                event_type=str(event.get("event_type", "")),
                data=str(event.get("data", "{}")),
            )
            migrated_events += 1

    health = postgres_service.health()
    print(
        json.dumps(
            {
                "upserted_jobs": upserted_jobs,
                "migrated_events": migrated_events,
                "postgres_health": health,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
