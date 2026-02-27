"""CV tailoring module — minimal adjustments to canonical resume."""

from __future__ import annotations

import logging
from pathlib import Path

from app.services.claude import call_claude_json
from app.services.canon import get_canonical_resume
from app.services.cv_docx import build_track_changes_preview

logger = logging.getLogger(__name__)

_CONFIG = (Path(__file__).parent / "config.md").read_text(encoding="utf-8")

SYSTEM_PROMPT = f"""You are the CV_TAILOR module of Joe v2.

Your task: make MINIMAL adjustments to a canonical resume to better match a specific job description.

## Rules
{_CONFIG}

## Output format
Return a JSON object with exactly three keys:
- "tailored_cv": the full adjusted resume in markdown
- "changes_summary": bullet list of what was changed and why
- "canon_check": one of OK | WARN | FAIL with explanation

IMPORTANT:
- Do NOT invent facts, numbers, dates, employers, tools, achievements
- Do NOT add experience with JD technologies not in the resume
- You may reorder skills, adjust summary accents, highlight relevant aspects of existing experience
- Every change must be traceable to both the resume AND the JD
- Return valid JSON only, no markdown fences
"""


def tailor_cv(jd_text: str) -> dict:
    logger.info("Tailoring CV for JD (%d chars)", len(jd_text))
    canon_resume = get_canonical_resume()

    user_msg = f"""## Job Description
{jd_text}

## Canonical Resume
{canon_resume}

Tailor the resume. Return JSON."""

    try:
        result = call_claude_json(SYSTEM_PROMPT, user_msg)
        tailored = str(result.get("tailored_cv", "")).strip()
        if tailored:
            result["track_changes"] = build_track_changes_preview(canon_resume, tailored)
        logger.info("CV tailored: canon_check=%s", result.get("canon_check", "?"))
        return result
    except Exception as e:
        logger.error("CV tailoring failed: %s", e)
        raise
