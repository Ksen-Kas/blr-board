"""Jobs router — CRUD for pipeline, reads/writes the same Google Sheet as the bot."""

from datetime import date
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.job import Job, JobCreate, JobUpdate, JobStatus
from app.security import require_internal_api_key
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/statuses")
def list_statuses() -> list[str]:
    """Return the canonical list of statuses — frontend should use this, not hardcode."""
    return [s.value for s in JobStatus]


@router.get("/")
def list_jobs() -> list[Job]:
    return storage_service.get_all_jobs()


@router.get("/{row_num}")
def get_job(row_num: int) -> Job:
    job = storage_service.get_job_by_row(row_num)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/")
def create_job(data: JobCreate, _: None = Depends(require_internal_api_key)) -> dict:
    """Add a job to the tracker — same format as the bot's sheets.add_row."""
    # Duplicate check (same logic as bot)
    existing = storage_service.find_job(data.company, data.role)
    if existing:
        return {
            "duplicate": True,
            "row_num": existing.row_num,
            "company": existing.company,
            "role": existing.role,
            "message": f"Already in tracker: row {existing.row_num}",
        }

    row_num = storage_service.add_row({
        "company": data.company,
        "role": data.role,
        "region": data.region,
        "seniority": data.seniority,
        "operator": data.operator_vs_contractor,
        "source_url": data.source,
        "channel": data.channel,
        "role_fit": data.role_fit,
        "stop_flags": data.stop_flags,
        "summary": data.comment,
        "submission_num": 1,
    })
    storage_service.invalidate_cache()
    if row_num:
        return {"added": True, "row_num": row_num}
    jobs = storage_service.get_all_jobs()
    return {"added": True, "row_num": jobs[-1].row_num if jobs else 0}


@router.patch("/{row_num}")
def update_job(row_num: int, data: JobUpdate, _: None = Depends(require_internal_api_key)) -> Job:
    job = storage_service.get_job_by_row(row_num)
    if not job:
        raise HTTPException(404, "Job not found")
    updates = data.model_dump(exclude_none=True)

    # Auto-log status change
    if "status" in updates and updates["status"] != job.status:
        try:
            storage_service.log_event(
                row_num,
                "status_change",
                json.dumps({"from": job.status, "to": updates["status"]}),
            )
        except Exception as e:
            logger.warning("Failed to log status_change event: %s", e)

    # Auto-fill Applied Date when status is moved to Applied and date is still empty.
    if (
        updates.get("status") == JobStatus.APPLIED.value
        and "applied_date" not in updates
        and not (job.applied_date or "").strip()
    ):
        updates["applied_date"] = date.today().isoformat()

    updated = storage_service.update_job(row_num, updates)
    if not updated:
        raise HTTPException(500, "Update failed")
    return updated


@router.post("/refresh")
def refresh_cache(_: None = Depends(require_internal_api_key)):
    """Force cache invalidation — call after bot writes new rows."""
    storage_service.invalidate_cache()
    return {"status": "cache invalidated"}


# ─── Events ───────────────────────────────────────────────────────────────────


class EventCreate(BaseModel):
    event_type: str
    data: str = "{}"


class EventUpdate(BaseModel):
    event_type: str | None = None
    data: str | None = None


@router.get("/{row_num}/events")
def get_events(row_num: int) -> list[dict]:
    return storage_service.get_events(row_num)


@router.post("/{row_num}/events")
def add_event(row_num: int, event: EventCreate, _: None = Depends(require_internal_api_key)):
    job = storage_service.get_job_by_row(row_num)
    if not job:
        raise HTTPException(404, "Job not found")
    storage_service.log_event(row_num, event.event_type, event.data)
    return {"status": "ok"}


@router.patch("/{row_num}/events/{event_id}")
def patch_event(
    row_num: int,
    event_id: int,
    event: EventUpdate,
    _: None = Depends(require_internal_api_key),
):
    job = storage_service.get_job_by_row(row_num)
    if not job:
        raise HTTPException(404, "Job not found")
    if event.event_type is None and event.data is None:
        raise HTTPException(400, "Nothing to update")
    try:
        ok = storage_service.update_event(
            job_id=row_num,
            event_id=event_id,
            event_type=event.event_type,
            data=event.data,
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "Event not found")
    return {"status": "ok"}
