"""Pipeline router — dashboard stats and overview."""

from collections import Counter
from fastapi import APIRouter, Depends

from app.security import require_internal_api_key
from app.services.reminder import daily_followup_check, get_reminder_runtime_status
from app.services.sheets import sheets_service

router = APIRouter()


@router.get("/stats")
def get_stats():
    jobs = sheets_service.get_all_jobs()
    status_counts = Counter(j.status for j in jobs)
    return {
        "total": len(jobs),
        "by_status": dict(status_counts),
    }


@router.get("/reminders/status")
def reminders_status(_: None = Depends(require_internal_api_key)):
    return get_reminder_runtime_status()


@router.post("/reminders/run-now")
async def reminders_run_now(_: None = Depends(require_internal_api_key)):
    await daily_followup_check()
    return {"status": "ok"}
