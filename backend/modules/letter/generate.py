"""Letter generation module — cover letters per Letter Canon rules."""

from __future__ import annotations

import logging

from app.services.claude import call_claude_json
from app.services.canon import get_canonical_resume, get_letter_rules

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_TEMPLATE = """You are the LETTER module of Joe v2.

Your task: generate a cover letter for a job application.

## Letter Rules
{letter_rules}

## Canonical Resume (source of truth for all facts)
{canon_resume}

## Output format
Return a JSON object with exactly two keys:
- "subject": email subject line (max 8-10 words)
- "body": the full letter text, paste-ready

IMPORTANT:
- Do NOT invent facts not in the resume
- Do NOT use banned phrases (see rules)
- Every claim must be traceable to the canonical resume
- If notes are provided, incorporate them while following all rules
- Return valid JSON only, no markdown fences
"""


def generate_letter(jd_text: str, notes: str = "") -> dict:
    logger.info("Generating letter for JD (%d chars), notes=%d chars", len(jd_text), len(notes))
    canon_resume = get_canonical_resume()
    letter_rules = get_letter_rules()

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        letter_rules=letter_rules,
        canon_resume=canon_resume,
    )

    user_msg = f"## Job Description\n{jd_text}"
    if notes:
        user_msg += f"\n\n## User Notes\n{notes}"
    user_msg += "\n\nGenerate the letter. Return JSON."

    try:
        result = call_claude_json(system_prompt, user_msg)
        word_count = len(result.get("body", "").split())
        logger.info("Letter generated: %d words", word_count)
        return result
    except Exception as e:
        logger.error("Letter generation failed: %s", e)
        raise
