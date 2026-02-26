"""Canon service — loads CLIENT_SPACE files as context for AI modules."""

from __future__ import annotations

from pathlib import Path

from app import config


def _read_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def get_canonical_resume() -> str:
    file_val = _read_file(Path(config.CLIENT_SPACE_PATH) / "canonical_resume.md")
    return file_val or config.CANONICAL_RESUME_CONTENT


def get_strategy() -> str:
    file_val = _read_file(Path(config.CLIENT_SPACE_PATH) / "JOE_Strategy_v2.md")
    return file_val or config.CANON_STRATEGY_CONTENT


def get_letter_rules() -> str:
    file_val = _read_file(Path(config.CLIENT_SPACE_PATH) / "JOE_Process_Letter_v2.md")
    return file_val or config.CANON_LETTER_RULES_CONTENT


def get_full_canon() -> str:
    """All canon files concatenated for scoring/analysis."""
    parts = [
        "# CANONICAL RESUME\n" + get_canonical_resume(),
        "# STRATEGY\n" + get_strategy(),
        "# LETTER RULES\n" + get_letter_rules(),
    ]
    return "\n\n---\n\n".join(parts)
