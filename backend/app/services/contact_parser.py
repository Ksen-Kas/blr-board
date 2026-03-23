"""Parse contact info from raw text — email, LinkedIn, phone, name."""

import re

_LINKEDIN_PROFILE_RE = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?",
    re.IGNORECASE,
)
_LINKEDIN_PROFILE_SHORT_RE = re.compile(
    r"(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?",
    re.IGNORECASE,
)
_LINKEDIN_MARKDOWN_PROFILE_RE = re.compile(
    r"\[([^\]\n]{2,120})\]\((https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?(?:\?[^)]*)?)\)",
    re.IGNORECASE,
)


def _normalize_profile_url(value: str) -> str:
    url = (value or "").strip()
    if not url:
        return ""
    if not url.lower().startswith("http"):
        url = f"https://{url}"
    return url


def _extract_name_from_text(text: str) -> str:
    patterns = [
        r"View\s+([A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){0,3})['’]s profile",
        r"Posted by[:\s]+([A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){0,3})",
        r"Hiring team[:\s]+([A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){0,3})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    return ""


def extract_linkedin_poster_contact(text: str) -> str:
    """Extract LinkedIn poster/recruiter from parsed JD text.

    Returns "Name | https://linkedin.com/in/..." or profile URL only.
    """
    if not text or not text.strip():
        return ""

    markdown_match = _LINKEDIN_MARKDOWN_PROFILE_RE.search(text)
    if markdown_match:
        name = markdown_match.group(1).strip()
        profile_url = _normalize_profile_url(markdown_match.group(2).split("?", 1)[0])
        if name and profile_url:
            return f"{name} | {profile_url}"

    # Prefer full profile URLs; fallback to short form without scheme.
    match = _LINKEDIN_PROFILE_RE.search(text) or _LINKEDIN_PROFILE_SHORT_RE.search(text)
    if not match:
        return ""

    profile_url = _normalize_profile_url(match.group(0))
    if not profile_url:
        return ""

    name = _extract_name_from_text(text)
    if name:
        return f"{name} | {profile_url}"
    return profile_url


def parse_contact(text: str) -> str:
    """Extract contact details from free-form text.

    Returns formatted string: "Name | email | linkedin | phone"
    Only includes parts that were found.
    """
    if not text or not text.strip():
        return ""

    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]

    email = re.search(r"\b[\w.-]+@[\w.-]+\.\w+\b", text)
    linkedin = _LINKEDIN_PROFILE_SHORT_RE.search(text)
    phone = re.search(r"\+?[\d\s()\-]{7,}", text)

    parts: list[str] = []

    # Name = first line that isn't purely email/url/phone
    for line in lines:
        line_lower = line.lower()
        if "@" in line_lower:
            continue
        if "linkedin.com" in line_lower:
            continue
        if re.fullmatch(r"\+?[\d\s()\-]{7,}", line):
            continue
        if line_lower.startswith("http"):
            continue
        # Likely a name or label — take it
        parts.append(line)
        break

    if email:
        parts.append(email.group())
    if linkedin:
        parts.append(linkedin.group())
    if phone:
        parts.append(phone.group().strip())

    return " | ".join(parts)
