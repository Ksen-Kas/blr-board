"""URL parser — Jina Reader API primary, BeautifulSoup fallback."""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


JINA_JUNK_MARKERS = [
    "returned error 404",
    "returned error 403",
    "returned error 401",
    "Oops, you've gone too far",
    "لم يتم العثور",  # LinkedIn arabic 404
    "Sign in to LinkedIn",
    "Page not found",
]

LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def is_safe_public_url(url: str) -> bool:
    """Block local/private URLs to reduce SSRF risk."""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.username or parsed.password:
        return False

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host or host in LOCAL_HOSTNAMES:
        return False

    try:
        ip = ipaddress.ip_address(host)
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return True


def is_linkedin_url(url: str) -> bool:
    host = (urlparse(url.strip()).hostname or "").lower()
    return "linkedin.com" in host


def parse_url_jina(url: str) -> str | None:
    """Parse JD via Jina Reader API (https://r.jina.ai/{url})."""
    try:
        resp = httpx.get(
            f"https://r.jina.ai/{url}",
            headers={"Accept": "text/plain"},
            timeout=20,
        )
        resp.raise_for_status()
        text = resp.text.strip()
        if len(text) < 200:
            return None
        # Filter out junk responses (404 pages, login walls, etc.)
        for marker in JINA_JUNK_MARKERS:
            if marker in text[:1000]:
                logger.warning("Jina returned junk for %s (marker: %s)", url, marker)
                return None
        return text
    except Exception as e:
        logger.warning("Jina Reader failed for %s: %s", url, e)
        return None


def parse_url_bs4(url: str) -> str | None:
    """Fallback: fetch URL and extract main text via BeautifulSoup."""
    try:
        resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("BS4 fetch failed for %s: %s", url, e)
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


def parse_url(url: str) -> str | None:
    """Parse JD from URL — Jina Reader first, BS4 fallback.

    LinkedIn URLs are blocked — they return login pages, not JD content.
    """
    if not is_safe_public_url(url):
        logger.warning("Blocked unsafe URL: %s", url)
        return None
    if is_linkedin_url(url):
        logger.info("LinkedIn URL blocked: %s", url)
        return None
    result = parse_url_jina(url)
    if result:
        return result
    logger.info("Jina failed, falling back to BS4 for %s", url)
    return parse_url_bs4(url)
