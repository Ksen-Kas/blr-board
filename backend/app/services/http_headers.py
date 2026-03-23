from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote


def _ascii_filename(value: str, fallback: str = "download.pdf") -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_only).strip("._")
    if not safe:
        safe = fallback
    if not safe.lower().endswith(".pdf"):
        safe = f"{safe}.pdf"
    return safe[:180]


def content_disposition_attachment(filename: str, fallback: str = "download.pdf") -> str:
    # RFC 6266 + RFC 5987:
    # - filename= uses ASCII fallback for broad client compatibility.
    # - filename*= keeps original UTF-8 name for modern clients.
    ascii_name = _ascii_filename(filename, fallback=fallback)
    utf8_name = quote(filename or fallback, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
