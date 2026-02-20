from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def parse_url(url: str) -> str | None:
    """Fetch URL and extract main text content.

    Returns cleaned text, or None if content is too short or request fails.
    Note: LinkedIn URLs will return a login page — check for linkedin.com
    in bot.py BEFORE calling this function.
    """
    try:
        resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup.find_all(["nav", "footer", "header", "script", "style", "aside"]):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id="main")
        or soup.find(id="content")
        or soup.body
    )

    raw = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    cleaned = "\n".join(lines)

    if len(cleaned) < 200:
        return None

    return cleaned
