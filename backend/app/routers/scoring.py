"""Scoring router — evaluate JD and persist pipeline rows.

Accepts JD text or URL. For unparseable links the source is still saved
(night-engine style: no_description / blocked JD).
"""

import logging
import re
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.security import require_internal_api_key
from app.services.contact_parser import parse_contact
from app.services.parser import is_linkedin_url, is_safe_public_url, parse_url
from app.services.storage import storage_service
from modules.scoring.evaluate import evaluate_fit

logger = logging.getLogger(__name__)

router = APIRouter()


class ScoreRequest(BaseModel):
    jd_text: str = ""
    source_url: str = ""
    contact: str = ""
    add_to_tracker: bool = False


_CITY_HINTS = {
    "cairo": "Cairo",
    "egypt": "Egypt",
    "riyadh": "Riyadh",
    "jeddah": "Jeddah",
    "dhahran": "Dhahran",
    "saudi": "Saudi Arabia",
    "dubai": "Dubai",
    "abu-dhabi": "Abu Dhabi",
    "uae": "UAE",
    "qatar": "Qatar",
    "doha": "Doha",
    "kuwait": "Kuwait",
    "oman": "Oman",
    "bahrain": "Bahrain",
    "london": "London",
}


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _extract_vacancy_id(source_url: str) -> str:
    text = source_url.strip()
    if not text:
        return ""
    patterns = [
        r"/jobs/view/(\d{6,})",
        r"[?&](?:currentJobId|jobId|jk|vjk)=([A-Za-z0-9_-]{5,})",
        r"/vacanc(?:y|ies)/(\d{4,})",
        r"/jobs?/(\d{4,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _guess_role_from_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    path = unquote(parsed.path or "")
    tokens = re.split(r"[/_]", path)
    cleaned: list[str] = []
    for token in tokens:
        token = token.strip().lower()
        if not token or token.isdigit():
            continue
        if token in {"jobs", "job", "view", "vacancy", "vacancies", "career", "careers", "apply"}:
            continue
        token = token.replace("-", " ")
        if len(token) < 3:
            continue
        cleaned.append(token)
    if not cleaned:
        vacancy_id = _extract_vacancy_id(source_url)
        if vacancy_id:
            return f"Unparsed Vacancy #{vacancy_id}"
        return "Unparsed Vacancy"
    guess = max(cleaned, key=len).strip()
    guess = re.sub(r"\s+", " ", guess)
    guess = " ".join(word.capitalize() for word in guess.split())
    return guess if len(guess) >= 3 else "Unparsed Vacancy"


def _guess_region_from_url(source_url: str) -> str:
    text = unquote(source_url).lower()
    for marker, region in _CITY_HINTS.items():
        if marker in text:
            return region
    return "Unknown"


def _guess_channel_from_url(source_url: str) -> str:
    host = (urlparse(source_url).hostname or "").lower()
    if "linkedin.com" in host:
        return "LinkedIn"
    if "indeed." in host:
        return "Indeed"
    if "glassdoor." in host:
        return "Glassdoor"
    if host:
        return "Portal"
    return "Other"


def _guess_company_from_url(source_url: str) -> str:
    host = (urlparse(source_url).hostname or "").lower()
    if not host:
        return "Unknown"
    host = host.replace("www.", "")
    parts = [p for p in host.split(".") if p]
    if not parts:
        return "Unknown"
    return parts[0].capitalize()


def _build_comment_for_sheet(jd_text: str, source_url: str, jd_status: str) -> str:
    if jd_text.strip():
        return jd_text.strip()
    return (
        f"JD unavailable ({jd_status}).\n"
        f"Source saved for manual review:\n{source_url.strip()}"
    )


def _build_no_jd_result(source_url: str) -> dict:
    vacancy_id = _extract_vacancy_id(source_url)
    region = _guess_region_from_url(source_url)
    role = _guess_role_from_url(source_url)
    return {
        "company": _guess_company_from_url(source_url),
        "role": role,
        "region": region,
        "seniority": "Other",
        "operator": "",
        "channel": _guess_channel_from_url(source_url),
        "stop_flags": "NONE",
        "role_fit": "",
        "cv_ready": "NEEDS_WORK",
        "cv_note": "JD not available for parsing",
        "summary": "JD unavailable. Source link saved.",
        "source_url": source_url,
        "jd_status": "blocked",
        "match_score": None,
        "match_reason": "no_description",
        "vacancy_id": vacancy_id,
    }


@router.post("/evaluate")
def score_jd(req: ScoreRequest, _: None = Depends(require_internal_api_key)) -> dict:
    jd_text = (req.jd_text or "").strip()
    source_url = (req.source_url or "").strip()

    if source_url and not _is_http_url(source_url):
        raise HTTPException(422, "Only valid http(s) URLs are allowed.")

    # If URL provided and no text, try parsing. If parsing fails, keep the URL anyway.
    if source_url and not jd_text:
        can_parse = is_safe_public_url(source_url) and not is_linkedin_url(source_url)
        if can_parse:
            parsed = parse_url(source_url)
            if parsed:
                jd_text = parsed.strip()
        else:
            logger.info("Skipping URL parse (blocked/unsupported host): %s", source_url)

    if jd_text:
        try:
            result = evaluate_fit(jd_text, source_url=source_url or None)
        except Exception as e:
            logger.error("Scoring failed: %s", e)
            raise HTTPException(500, f"Scoring failed: {e}")
        region_hint = _guess_region_from_url(source_url) if source_url else "Unknown"
        region_val = (result.get("region") or "").strip().lower()
        if region_hint != "Unknown" and region_val in {"", "unknown", "usa", "us", "america", "north america"}:
            result["region"] = region_hint
        result["jd_status"] = "parsed"
        result["match_score"] = None
        result["match_reason"] = ""
        result["vacancy_id"] = _extract_vacancy_id(source_url) if source_url else ""
    elif source_url:
        result = _build_no_jd_result(source_url)
    else:
        raise HTTPException(400, "Provide jd_text or source_url")

    # Optionally write to sheet (same as bot's "Add to tracker" button)
    if req.add_to_tracker:
        # Check URL duplicate
        url_dup = storage_service.find_by_url(source_url) if source_url else None
        # Check fuzzy duplicate
        fuzzy_dup = storage_service.find_job(result.get("company", ""), result.get("role", ""))
        dup = url_dup or fuzzy_dup

        if dup:
            result["duplicate"] = {
                "found": True,
                "row_num": dup.row_num,
                "company": dup.company,
                "role": dup.role,
            }
        else:
            result["contact"] = parse_contact(req.contact)
            result["summary"] = _build_comment_for_sheet(
                jd_text=jd_text,
                source_url=source_url,
                jd_status=result.get("jd_status", "blocked"),
            )
            row_num = storage_service.add_row(result)
            if row_num:
                result["row_num"] = row_num
            result["added_to_tracker"] = True

    return result
