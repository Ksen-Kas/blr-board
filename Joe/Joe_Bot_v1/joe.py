from __future__ import annotations

from pathlib import Path

import anthropic

import config

# ──────────────────────────────────────────────────────────────────────────────
# System prompt loaded from joe_system_prompt.txt
# ──────────────────────────────────────────────────────────────────────────────
_prompt_path = Path(__file__).parent / "joe_system_prompt.txt"
SYSTEM_PROMPT = _prompt_path.read_text(encoding="utf-8")

OUTPUT_FORMAT = """
Формат ответа (строго):

COMPANY: [название или Unknown]
ROLE: [название роли]
REGION: [страна/город]
SENIORITY: [Senior / Principal / Other]
OPERATOR: [Operator / Contractor]
CHANNEL: [LinkedIn / Portal / Recruiter / Other]

STOP_FLAGS: [level, geo, visa, contractor, exp через запятую — или NONE]
ROLE_FIT: [Strong / Partial / Stretch]
CV_READY: [YES / NEEDS_WORK]
CV_NOTE: [одна строка — почему нужна доработка, или пусто]

SUMMARY: [2-3 строки свободного текста — ключевые совпадения или расхождения]
"""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _parse_response(text: str) -> dict:
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
    return result


def evaluate(jd_text: str, source_url: str | None = None) -> dict:
    """Call Claude API to evaluate a job description. Returns structured dict."""
    user_content = jd_text
    if source_url:
        user_content = f"Источник: {source_url}\n\n{jd_text}"

    client = _get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT + "\n" + OUTPUT_FORMAT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = message.content[0].text
    result = _parse_response(raw)
    result["source_url"] = source_url or ""
    return result


def format_telegram_message(result: dict) -> str:
    """Format evaluation result as a Telegram message."""
    stop_flags = result.get("stop_flags", "NONE") or "NONE"
    role_fit = result.get("role_fit", "")

    if stop_flags == "NONE":
        icon = "🟢 Clean"
    elif role_fit == "Stretch":
        icon = "🔴 Flags"
    else:
        icon = "🟡 Check"

    company = result.get("company", "Unknown")
    role = result.get("role", "")
    region = result.get("region", "")
    operator = result.get("operator", "")
    seniority = result.get("seniority", "")
    cv_ready = result.get("cv_ready", "")
    cv_note = result.get("cv_note", "")
    summary = result.get("summary", "")

    lines = [
        f"{icon} {company} — {role} ({region})",
        f"Role Fit: {role_fit} | {operator} | {seniority}",
        "",
    ]

    if stop_flags and stop_flags != "NONE":
        lines.append(f"🚩 Стоп-факторы: {stop_flags}")
        lines.append("")

    if cv_ready == "YES":
        lines.append("CV: подаём шаблоном ✅")
    else:
        lines.append("CV: нужна доработка ⚠️")
        if cv_note:
            lines.append(cv_note)

    lines.append("")
    lines.append(summary)

    return "\n".join(lines).strip()
