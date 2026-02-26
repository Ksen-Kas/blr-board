"""Scoring module — uses the SAME system prompt and output format as the Telegram bot's joe.py.

The bot's joe_system_prompt.txt is loaded from CLIENT_SPACE parent (shared).
Output is parsed line-by-line just like the bot does.
"""

from __future__ import annotations

import logging
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

STOP_FLAGS: [visa_required, citizenship, exp_gap, junior_role, strong_mismatch через запятую — или NONE. ONLY these 5 flags are valid.]
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
        max_tokens=1024,
    )

    result = _parse_response(raw)
    result["stop_flags"] = _validate_stop_flags(jd_text, result.get("stop_flags", ""))
    result["source_url"] = source_url or ""
    return result


def _validate_stop_flags(jd_text: str, stop_flags: str) -> str:
    """Drop visa/citizenship flags unless JD has explicit wording."""
    if not stop_flags or stop_flags == "NONE":
        return "NONE"

    text = jd_text.lower()

    citizenship_markers = [
        "citizenship",
        "citizen",
        "nationals only",
        "national only",
        "only nationals",
        "only citizens",
        "must be a citizen",
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
    ]

    has_citizenship = any(m in text for m in citizenship_markers)
    has_visa = any(m in text for m in visa_markers)

    flags = [f.strip() for f in stop_flags.split(",") if f.strip()]
    kept = []
    for f in flags:
        if f == "citizenship":
            if has_citizenship:
                kept.append(f)
        elif f == "visa_required":
            if has_visa:
                kept.append(f)
        else:
            kept.append(f)

    return ", ".join(kept) if kept else "NONE"
