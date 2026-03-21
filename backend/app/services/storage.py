"""Unified storage facade with feature flags for Sheets/Postgres."""

from __future__ import annotations

import logging
from typing import Any

from app import config
from app.models.job import Job
from app.services.postgres import postgres_service
from app.services.sheets import sheets_service

logger = logging.getLogger(__name__)

READ_SOURCES = {"sheets", "postgres"}
WRITE_MODES = {"sheets", "postgres", "both"}


def _read_source() -> str:
    value = (config.DATA_READ_SOURCE or "sheets").strip().lower()
    return value if value in READ_SOURCES else "sheets"


def _write_mode() -> str:
    value = (config.DATA_WRITE_MODE or "sheets").strip().lower()
    return value if value in WRITE_MODES else "sheets"


class StorageService:
    def _read_jobs(self) -> list[Job]:
        source = _read_source()
        if source == "postgres" and postgres_service.enabled:
            try:
                return postgres_service.get_all_jobs()
            except Exception as exc:
                logger.error("Postgres read failed, fallback to Sheets: %s", exc)
        return sheets_service.get_all_jobs()

    def get_all_jobs(self) -> list[Job]:
        return self._read_jobs()

    def get_job_by_row(self, row_num: int) -> Job | None:
        source = _read_source()
        if source == "postgres" and postgres_service.enabled:
            try:
                job = postgres_service.get_job_by_row(row_num)
                if job:
                    return job
            except Exception as exc:
                logger.error("Postgres read-by-id failed, fallback to Sheets: %s", exc)
        return sheets_service.get_job_by_row(row_num)

    def find_job(self, company: str, role: str) -> Job | None:
        source = _read_source()
        if source == "postgres" and postgres_service.enabled:
            try:
                found = postgres_service.find_job(company, role)
                if found:
                    return found
            except Exception as exc:
                logger.error("Postgres find_job failed, fallback to Sheets: %s", exc)
        return sheets_service.find_job(company, role)

    def find_by_url(self, url: str) -> Job | None:
        source = _read_source()
        if source == "postgres" and postgres_service.enabled:
            try:
                found = postgres_service.find_by_url(url)
                if found:
                    return found
            except Exception as exc:
                logger.error("Postgres find_by_url failed, fallback to Sheets: %s", exc)
        return sheets_service.find_by_url(url)

    def _latest_row_num_from_sheets(self) -> int:
        try:
            jobs = sheets_service.get_all_jobs()
            return max((j.row_num for j in jobs), default=0)
        except Exception:
            return 0

    def add_row(self, data: dict) -> int:
        mode = _write_mode()
        row_num = 0

        if mode in {"sheets", "both"}:
            sheets_service.add_row(data)
            sheets_service.invalidate_cache()
            row_num = self._latest_row_num_from_sheets()

        if mode in {"postgres", "both"}:
            if not postgres_service.enabled:
                raise RuntimeError("DATA_WRITE_MODE requires Postgres, but DATABASE_URL is not configured")
            row_num = postgres_service.add_row(data, row_num=row_num or None)

        return row_num

    def update_job(self, row_num: int, updates: dict) -> Job | None:
        mode = _write_mode()
        write_errors: list[str] = []

        if mode in {"sheets", "both"}:
            try:
                sheets_service.update_job(row_num, updates)
            except Exception as exc:
                write_errors.append(f"sheets: {exc}")

        if mode in {"postgres", "both"}:
            if not postgres_service.enabled:
                write_errors.append("postgres: DATABASE_URL missing")
            else:
                try:
                    postgres_service.update_job(row_num, updates)
                except Exception as exc:
                    write_errors.append(f"postgres: {exc}")

        if write_errors and mode != "both":
            raise RuntimeError("; ".join(write_errors))
        if write_errors and mode == "both":
            logger.error("Dual-write update had partial errors: %s", "; ".join(write_errors))

        return self.get_job_by_row(row_num)

    def invalidate_cache(self) -> None:
        sheets_service.invalidate_cache()
        try:
            postgres_service.invalidate_cache()
        except Exception:
            pass

    def log_event(self, job_id: int, event_type: str, data: str = "{}") -> None:
        mode = _write_mode()
        errs: list[str] = []
        if mode in {"sheets", "both"}:
            try:
                sheets_service.log_event(job_id, event_type, data)
            except Exception as exc:
                errs.append(f"sheets: {exc}")
        if mode in {"postgres", "both"}:
            if not postgres_service.enabled:
                errs.append("postgres: DATABASE_URL missing")
            else:
                try:
                    postgres_service.log_event(job_id, event_type, data)
                except Exception as exc:
                    errs.append(f"postgres: {exc}")
        if errs and mode != "both":
            raise RuntimeError("; ".join(errs))
        if errs and mode == "both":
            logger.error("Dual-write event had partial errors: %s", "; ".join(errs))

    def get_events(self, job_id: int) -> list[dict]:
        source = _read_source()
        if source == "postgres" and postgres_service.enabled:
            try:
                return postgres_service.get_events(job_id)
            except Exception as exc:
                logger.error("Postgres get_events failed, fallback to Sheets: %s", exc)
        return sheets_service.get_events(job_id)

    def update_event(self, job_id: int, event_id: int, event_type: str | None = None, data: str | None = None) -> bool:
        mode = _write_mode()
        source = _read_source()
        targets: list[str] = []
        if mode == "sheets":
            targets = ["sheets"]
        elif mode == "postgres":
            targets = ["postgres"]
        else:  # both
            targets = ["postgres", "sheets"] if source == "postgres" else ["sheets", "postgres"]

        success = False
        errors: list[str] = []

        for target in targets:
            try:
                if target == "postgres":
                    if not postgres_service.enabled:
                        errors.append("postgres: DATABASE_URL missing")
                        continue
                    ok = postgres_service.update_event(job_id, event_id, event_type, data)
                    success = success or ok
                    if not ok:
                        errors.append("postgres: event not found")
                else:
                    ok = sheets_service.update_event(job_id, event_id, event_type, data)
                    success = success or ok
                    if not ok:
                        errors.append("sheets: event not found")
            except Exception as exc:
                errors.append(f"{target}: {exc}")

        if not success and errors:
            raise RuntimeError("; ".join(errors))
        if errors and mode == "both":
            logger.warning("Dual-write event update had partial errors: %s", "; ".join(errors))
        return success

    def runtime_status(self) -> dict[str, Any]:
        return {
            "read_source": _read_source(),
            "write_mode": _write_mode(),
            "postgres": postgres_service.health(),
        }


storage_service = StorageService()
