"""PostgreSQL storage service for jobs/events."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from app import config
from app.models.job import Job
from app.services.sheets import _compute_duplicates, _compute_needs_followup

logger = logging.getLogger(__name__)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


class PostgresService:
    def __init__(self) -> None:
        self._schema_ready = False
        self._enabled = bool(config.DATABASE_URL)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _connect(self):
        if not self._enabled:
            raise RuntimeError("Postgres is not enabled (DATABASE_URL is empty)")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except Exception as exc:
            raise RuntimeError("psycopg is not installed") from exc
        return psycopg.connect(config.DATABASE_URL, autocommit=True, row_factory=dict_row)

    def _ensure_schema(self) -> None:
        if not self._enabled or self._schema_ready:
            return
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY,
                    company TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT '',
                    region TEXT NOT NULL DEFAULT '',
                    seniority TEXT NOT NULL DEFAULT '',
                    operator_vs_contractor TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'New',
                    submission_count TEXT NOT NULL DEFAULT '',
                    reapply_reason TEXT NOT NULL DEFAULT '',
                    applied_date TEXT NOT NULL DEFAULT '',
                    followup_1 TEXT NOT NULL DEFAULT '',
                    followup_2 TEXT NOT NULL DEFAULT '',
                    response_date TEXT NOT NULL DEFAULT '',
                    days_to_response TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    channel TEXT NOT NULL DEFAULT '',
                    role_fit TEXT NOT NULL DEFAULT '',
                    stop_flags TEXT NOT NULL DEFAULT '',
                    contact TEXT NOT NULL DEFAULT '',
                    cv TEXT NOT NULL DEFAULT '',
                    cl TEXT NOT NULL DEFAULT '',
                    comment TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS job_events (
                    id BIGSERIAL PRIMARY KEY,
                    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    data TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company_role ON jobs(company, role);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events(job_id);")
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_job_events_dedupe
                ON job_events(job_id, timestamp, event_type, data);
                """
            )
        self._schema_ready = True
        logger.info("Postgres schema ensured")

    @staticmethod
    def _row_to_job(row: dict[str, Any]) -> Job:
        data = {
            "row_num": _safe_int(row.get("id")),
            "company": row.get("company", "") or "",
            "role": row.get("role", "") or "",
            "region": row.get("region", "") or "",
            "seniority": row.get("seniority", "") or "",
            "operator_vs_contractor": row.get("operator_vs_contractor", "") or "",
            "status": row.get("status", "New") or "New",
            "submission_count": row.get("submission_count", "") or "",
            "reapply_reason": row.get("reapply_reason", "") or "",
            "applied_date": row.get("applied_date", "") or "",
            "followup_1": row.get("followup_1", "") or "",
            "followup_2": row.get("followup_2", "") or "",
            "response_date": row.get("response_date", "") or "",
            "days_to_response": row.get("days_to_response", "") or "",
            "source": row.get("source", "") or "",
            "channel": row.get("channel", "") or "",
            "role_fit": row.get("role_fit", "") or "",
            "stop_flags": row.get("stop_flags", "") or "",
            "contact": row.get("contact", "") or "",
            "cv": row.get("cv", "") or "",
            "cl": row.get("cl", "") or "",
            "comment": row.get("comment", "") or "",
        }
        job = Job(**data)
        job.needs_followup = _compute_needs_followup(job)
        return job

    def _next_row_num(self) -> int:
        self._ensure_schema()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(id), 1) + 1 AS next_id FROM jobs")
            row = cur.fetchone() or {}
            return _safe_int(row.get("next_id"), 2)

    def get_all_jobs(self) -> list[Job]:
        self._ensure_schema()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM jobs ORDER BY id ASC;")
            rows = cur.fetchall() or []
        jobs = [self._row_to_job(r) for r in rows]
        _compute_duplicates(jobs)
        return jobs

    def get_job_by_row(self, row_num: int) -> Job | None:
        self._ensure_schema()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM jobs WHERE id = %s;", (row_num,))
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_job(row)

    def find_job(self, company: str, role: str) -> Job | None:
        self._ensure_schema()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM jobs
                WHERE lower(company) = lower(%s) AND lower(role) = lower(%s)
                ORDER BY id ASC LIMIT 1;
                """,
                (company.strip(), role.strip()),
            )
            row = cur.fetchone()
        return self._row_to_job(row) if row else None

    def find_by_url(self, url: str) -> Job | None:
        value = (url or "").strip()
        if not value:
            return None
        self._ensure_schema()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM jobs WHERE source = %s ORDER BY id ASC LIMIT 1;", (value,))
            row = cur.fetchone()
        return self._row_to_job(row) if row else None

    def add_row(self, data: dict, row_num: int | None = None) -> int:
        self._ensure_schema()
        new_id = row_num or self._next_row_num()
        stop_flags_raw = data.get("stop_flags", "NONE") or "NONE"
        stop_flags_val = "" if stop_flags_raw == "NONE" else stop_flags_raw
        payload = {
            "id": new_id,
            "company": data.get("company", ""),
            "role": data.get("role", ""),
            "region": data.get("region", ""),
            "seniority": data.get("seniority", ""),
            "operator_vs_contractor": data.get("operator", ""),
            "status": "New",
            "submission_count": str(data.get("submission_num", 1)),
            "reapply_reason": data.get("reapply_reason", ""),
            "applied_date": "",
            "followup_1": "",
            "followup_2": "",
            "response_date": "",
            "days_to_response": "",
            "source": data.get("source_url", ""),
            "channel": data.get("channel", ""),
            "role_fit": data.get("role_fit", ""),
            "stop_flags": stop_flags_val,
            "contact": data.get("contact", ""),
            "cv": "",
            "cl": "",
            "comment": data.get("summary", ""),
        }
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (
                    id, company, role, region, seniority, operator_vs_contractor, status,
                    submission_count, reapply_reason, applied_date, followup_1, followup_2,
                    response_date, days_to_response, source, channel, role_fit, stop_flags,
                    contact, cv, cl, comment, created_at, updated_at
                ) VALUES (
                    %(id)s, %(company)s, %(role)s, %(region)s, %(seniority)s, %(operator_vs_contractor)s, %(status)s,
                    %(submission_count)s, %(reapply_reason)s, %(applied_date)s, %(followup_1)s, %(followup_2)s,
                    %(response_date)s, %(days_to_response)s, %(source)s, %(channel)s, %(role_fit)s, %(stop_flags)s,
                    %(contact)s, %(cv)s, %(cl)s, %(comment)s, now(), now()
                )
                ON CONFLICT (id) DO UPDATE SET
                    company = EXCLUDED.company,
                    role = EXCLUDED.role,
                    region = EXCLUDED.region,
                    seniority = EXCLUDED.seniority,
                    operator_vs_contractor = EXCLUDED.operator_vs_contractor,
                    status = EXCLUDED.status,
                    submission_count = EXCLUDED.submission_count,
                    reapply_reason = EXCLUDED.reapply_reason,
                    applied_date = EXCLUDED.applied_date,
                    followup_1 = EXCLUDED.followup_1,
                    followup_2 = EXCLUDED.followup_2,
                    response_date = EXCLUDED.response_date,
                    days_to_response = EXCLUDED.days_to_response,
                    source = EXCLUDED.source,
                    channel = EXCLUDED.channel,
                    role_fit = EXCLUDED.role_fit,
                    stop_flags = EXCLUDED.stop_flags,
                    contact = EXCLUDED.contact,
                    cv = EXCLUDED.cv,
                    cl = EXCLUDED.cl,
                    comment = EXCLUDED.comment,
                    updated_at = now();
                """,
                payload,
            )
        return new_id

    def upsert_job(self, job: Job) -> int:
        return self.add_row(
            {
                "company": job.company,
                "role": job.role,
                "region": job.region,
                "seniority": job.seniority,
                "operator": job.operator_vs_contractor,
                "source_url": job.source,
                "channel": job.channel,
                "role_fit": job.role_fit,
                "stop_flags": job.stop_flags or "NONE",
                "summary": job.comment,
                "submission_num": job.submission_count or "1",
                "contact": job.contact,
                "reapply_reason": job.reapply_reason,
            },
            row_num=job.row_num,
        )

    def update_job(self, row_num: int, updates: dict) -> Job | None:
        valid_fields = {
            "status",
            "role_fit",
            "stop_flags",
            "applied_date",
            "followup_1",
            "followup_2",
            "response_date",
            "contact",
            "cv",
            "cl",
            "comment",
            "submission_count",
            "reapply_reason",
        }
        clean_updates = {k: str(v) for k, v in updates.items() if k in valid_fields and v is not None}
        if not clean_updates:
            return self.get_job_by_row(row_num)

        assigns = ", ".join(f"{field} = %({field})s" for field in clean_updates.keys())
        clean_updates["id"] = row_num
        query = f"""
            UPDATE jobs
            SET {assigns}, updated_at = now()
            WHERE id = %(id)s
            RETURNING *;
        """
        self._ensure_schema()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(query, clean_updates)
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_job(row)

    def invalidate_cache(self) -> None:
        return

    def log_event(self, job_id: int, event_type: str, data: str = "{}", timestamp: str = "") -> None:
        self._ensure_schema()
        ts = (timestamp or "").strip() or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_events (job_id, timestamp, event_type, data)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (job_id, ts, event_type, data or "{}"),
            )

    def upsert_event(self, job_id: int, timestamp: str, event_type: str, data: str = "{}") -> None:
        self.log_event(job_id=job_id, timestamp=timestamp, event_type=event_type, data=data)

    def get_events(self, job_id: int) -> list[dict]:
        self._ensure_schema()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_id, timestamp, event_type, data
                FROM job_events
                WHERE job_id = %s
                ORDER BY id DESC;
                """,
                (job_id,),
            )
            rows = cur.fetchall() or []
        result: list[dict] = []
        for row in rows:
            result.append(
                {
                    "job_id": _safe_int(row.get("job_id"), 0),
                    "timestamp": row.get("timestamp", "") or "",
                    "event_type": row.get("event_type", "") or "",
                    "data": row.get("data", "{}") or "{}",
                }
            )
        return result

    def health(self) -> dict[str, Any]:
        if not self._enabled:
            return {"enabled": False, "ok": False, "reason": "DATABASE_URL missing"}
        try:
            self._ensure_schema()
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM jobs;")
                row = cur.fetchone() or {"c": 0}
            return {"enabled": True, "ok": True, "jobs": _safe_int(row.get("c"), 0)}
        except Exception as exc:
            logger.error("Postgres health check failed: %s", exc)
            return {"enabled": True, "ok": False, "reason": str(exc)}


postgres_service = PostgresService()
