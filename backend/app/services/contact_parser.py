"""Parse contact info from raw text — email, LinkedIn, phone, name."""

import re


def parse_contact(text: str) -> str:
    """Extract contact details from free-form text.

    Returns formatted string: "Name | email | linkedin | phone"
    Only includes parts that were found.
    """
    if not text or not text.strip():
        return ""

    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]

    email = re.search(r"\b[\w.-]+@[\w.-]+\.\w+\b", text)
    linkedin = re.search(r"linkedin\.com/in/[\w-]+", text)
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
