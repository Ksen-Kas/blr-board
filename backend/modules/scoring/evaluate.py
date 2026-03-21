"""Scoring module — uses the SAME system prompt and output format as the Telegram bot's joe.py.

The bot's joe_system_prompt.txt is loaded from CLIENT_SPACE parent (shared).
Output is parsed line-by-line just like the bot does.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.services.claude import call_claude
from app.services.canon import get_canonical_resume
from app.models.job import sanitize_flags

logger = logging.getLogger(__name__)

# Load the bot's system prompt
_PROMPT_PATHS = [
    # Direct reference to the bot's prompt file
    Path("/Users/sizovaka/Documents/AI_LAB/02_projects/02_Joe-Bot_vacancy log/joe_system_prompt.txt"),
    # Fallback: local copy
    Path(__file__).parent / "joe_system_prompt.txt",
]

SYSTEM_PROMPT = ""
for p in _PROMPT_PATHS:
    if p.exists():
        SYSTEM_PROMPT = p.read_text(encoding="utf-8")
        break

# Same output format as the bot
OUTPUT_FORMAT = """
Формат ответа (строго):

COMPANY: [название или Unknown]
ROLE: [название роли]
REGION: [страна/город]
SENIORITY: [Senior / Principal / Other]
OPERATOR: [Operator / Contractor]
CHANNEL: [LinkedIn / Portal / Recruiter / Other]

STOP_FLAGS: [visa_required, citizenship через запятую — или NONE. ONLY these 2 flags are valid.]
ROLE_FIT: [Strong / Partial / Stretch]
CV_READY: [YES / NEEDS_WORK]
CV_NOTE: [одна строка — почему нужна доработка, или пусто]

SUMMARY: [2-3 строки свободного текста — ключевые совпадения или расхождения]
"""


def _parse_response(text: str) -> dict:
    """Parse structured response — same logic as the bot's joe._parse_response."""
    result = {
        "company": "Unknown",
        "role": "",
        "region": "",
        "seniority": "",
        "operator": "",
        "channel": "",
        "stop_flags": "NONE",
        "role_fit": "",
        "cv_ready": "",
        "cv_note": "",
        "summary": "",
    }

    FIELD_MAP = {
        "COMPANY:": "company",
        "ROLE:": "role",
        "REGION:": "region",
        "SENIORITY:": "seniority",
        "OPERATOR:": "operator",
        "CHANNEL:": "channel",
        "STOP_FLAGS:": "stop_flags",
        "ROLE_FIT:": "role_fit",
        "CV_READY:": "cv_ready",
        "CV_NOTE:": "cv_note",
    }

    summary_lines: list[str] = []
    in_summary = False

    for line in text.strip().splitlines():
        if line.startswith("SUMMARY:"):
            in_summary = True
            val = line[len("SUMMARY:"):].strip()
            if val:
                summary_lines.append(val)
            continue

        if in_summary:
            summary_lines.append(line)
            continue

        for prefix, field in FIELD_MAP.items():
            if line.startswith(prefix):
                result[field] = line[len(prefix):].strip()
                break

    result["summary"] = "\n".join(summary_lines).strip()
    # Sanitize flags — remove invalid ones (geo, contractor, etc.)
    result["stop_flags"] = sanitize_flags(result.get("stop_flags", ""))
    if not result["stop_flags"]:
        result["stop_flags"] = "NONE"
    return result


def evaluate_fit(jd_text: str, source_url: str | None = None) -> dict:
    """Evaluate JD — produces the same dict format as the bot's joe.evaluate."""
    user_content = jd_text
    if source_url:
        user_content = f"Источник: {source_url}\n\n{jd_text}"

    raw = call_claude(
        SYSTEM_PROMPT + "\n" + OUTPUT_FORMAT,
        user_content,
        max_tokens=700,
    )

    result = _parse_response(raw)
    result["stop_flags"] = _validate_stop_flags(jd_text, result.get("stop_flags", ""))
    result["source_url"] = source_url or ""
    return result


def _validate_stop_flags(jd_text: str, stop_flags: str) -> str:
    """Keep only explicit hard-stop eligibility flags for non-RU citizenship / visa."""
    text = jd_text.lower()

    has_non_ru_citizenship_req = _has_explicit_non_ru_citizenship_requirement(text)
    has_visa_req = _has_explicit_visa_requirement(text)

    flags = [f.strip() for f in (stop_flags or "").split(",") if f.strip()]
    kept = set()
    for f in flags:
        if f == "citizenship" and has_non_ru_citizenship_req:
            kept.add("citizenship")
        elif f == "visa_required" and has_visa_req:
            kept.add("visa_required")

    # Enforce explicit constraints even if model forgot to return a flag.
    if has_non_ru_citizenship_req:
        kept.add("citizenship")
    if has_visa_req:
        kept.add("visa_required")

    ordered = [f for f in ("citizenship", "visa_required") if f in kept]
    return ", ".join(ordered) if ordered else "NONE"


def _has_explicit_non_ru_citizenship_requirement(text: str) -> bool:
    base_markers = [
        "citizenship",
        "citizen",
        "nationals only",
        "national only",
        "only nationals",
        "only citizens",
        "must be a citizen",
        "must be citizen",
        "citizens only",
        "nationality",
    ]
    if not any(m in text for m in base_markers):
        return False

    non_ru_markers = [
        "us citizen",
        "u.s. citizen",
        "american citizen",
        "eu citizen",
        "eu citizenship",
        "uk citizen",
        "british citizen",
        "saudi national",
        "saudi nationals",
        "uae national",
        "emirati",
        "emiratis only",
        "qatari national",
        "kuwaiti national",
        "omani national",
        "bahraini national",
        "gcc nationals",
        "local nationals",
        "local national",
    ]
    if any(m in text for m in non_ru_markers):
        return True

    russian_markers = [
        "russian citizen",
        "russian citizenship",
        "citizenship of russia",
        "citizen of russia",
        "russian federation",
    ]

    country_citizen = re.findall(r"\b([a-z][a-z-]{2,30})\s+citizen(?:s)?\b", text)
    for country in country_citizen:
        if country not in {"russian"}:
            return True

    citizen_of_country = re.findall(
        r"\bcitizen(?:s)?\s+of\s+([a-z][a-z\s-]{2,30})\b",
        text,
    )
    for country_phrase in citizen_of_country:
        country = country_phrase.strip().split()[0]
        if country not in {"russia", "russian"}:
            return True

    # If only RU markers are present, no stop flag.
    if any(m in text for m in russian_markers):
        return False

    return False


def _has_explicit_visa_requirement(text: str) -> bool:
    visa_markers = [
        "no visa sponsorship",
        "visa sponsorship not",
        "cannot sponsor",
        "does not sponsor",
        "visa not available",
        "work visa not available",
        "must have work authorization",
        "must be authorized to work",
        "requires work authorization",
        "no sponsorship",
        "work visa required",
        "visa required",
        "requires visa",
        "must hold a valid visa",
        "valid visa required",
        "residence visa required",
        "residence permit required",
    ]
    return any(m in text for m in visa_markers)
