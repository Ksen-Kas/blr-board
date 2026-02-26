"""Pipeline router — dashboard stats and overview."""

from collections import Counter
from fastapi import APIRouter

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
