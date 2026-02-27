import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.routers import jobs, cv, letter, scoring, pipeline
from app.security import require_basic_auth
from app.services.reminder import build_reminder_scheduler

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

is_prod = config.APP_ENV == "production"

app = FastAPI(
    title="Joe v2",
    version="0.1.0",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_reminder_scheduler = build_reminder_scheduler()


@app.on_event("startup")
async def _startup_scheduler() -> None:
    if _reminder_scheduler and not _reminder_scheduler.running:
        _reminder_scheduler.start()
        logging.getLogger(__name__).info(
            "Reminder scheduler started (%02d:%02d %s)",
            config.REMINDER_HOUR,
            config.REMINDER_MINUTE,
            config.TIMEZONE,
        )


@app.on_event("shutdown")
async def _shutdown_scheduler() -> None:
    if _reminder_scheduler and _reminder_scheduler.running:
        _reminder_scheduler.shutdown(wait=False)
        logging.getLogger(__name__).info("Reminder scheduler stopped")


@app.middleware("http")
async def security_headers_and_auth(request: Request, call_next):
    if request.method == "OPTIONS":
        response = await call_next(request)
    else:
        try:
            await require_basic_auth(request)
        except Exception as exc:
            if hasattr(exc, "status_code"):
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": getattr(exc, "detail", "Unauthorized")},
                    headers=getattr(exc, "headers", {}) or {},
                )
            raise
        response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(cv.router, prefix="/api/cv", tags=["cv"])
app.include_router(letter.router, prefix="/api/letter", tags=["letter"])
app.include_router(scoring.router, prefix="/api/scoring", tags=["scoring"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
