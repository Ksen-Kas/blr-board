"""Scoring router — evaluate JD, same output as Telegram bot.

Accepts JD text or URL. Returns the same structured dict the bot produces.
Optionally adds the result to the Pipeline sheet.
"""

import logging

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from app.services.contact_parser import parse_contact
from app.services.parser import is_linkedin_url, is_safe_public_url, parse_url
from app.security import require_internal_api_key
from app.services.sheets import sheets_service
from modules.scoring.evaluate import evaluate_fit

logger = logging.getLogger(__name__)

router = APIRouter()


class ScoreRequest(BaseModel):
    jd_text: str = ""
    source_url: str = ""
    contact: str = ""
    add_to_tracker: bool = False


@router.post("/evaluate")
def score_jd(req: ScoreRequest, _: None = Depends(require_internal_api_key)) -> dict:
    jd_text = req.jd_text

    # If URL provided and no text, parse it (Jina Reader → BS4 fallback)
    if req.source_url and not jd_text:
        if not is_safe_public_url(req.source_url):
            raise HTTPException(422, "Only public http(s) URLs are allowed.")
        if is_linkedin_url(req.source_url):
            raise HTTPException(422, "LinkedIn URLs cannot be parsed. Paste JD text instead.")
        parsed = parse_url(req.source_url)
        if not parsed:
            raise HTTPException(
                422,
                "Could not extract text from URL. The page may be behind a login or too short. "
                "Please paste the JD text manually.",
            )
        jd_text = parsed

    if not jd_text:
        raise HTTPException(400, "Provide jd_text or source_url")

    try:
        result = evaluate_fit(jd_text, source_url=req.source_url or None)
    except Exception as e:
        logger.error("Scoring failed: %s", e)
        raise HTTPException(500, f"Scoring failed: {e}")

    # Optionally write to sheet (same as bot's "Add to tracker" button)
    if req.add_to_tracker:
        # Check URL duplicate
        url_dup = sheets_service.find_by_url(req.source_url) if req.source_url else None
        # Check fuzzy duplicate
        fuzzy_dup = sheets_service.find_job(result.get("company", ""), result.get("role", ""))
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
            sheets_service.add_row(result)
            result["added_to_tracker"] = True

    return result
