"""URL parser — Jina Reader API primary, BeautifulSoup fallback."""

from __future__ import annotations

import ipaddress
import json
import logging
import re
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

_LINKEDIN_PROFILE_RE = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?",
    re.IGNORECASE,
)
_LINKEDIN_MARKDOWN_PROFILE_RE = re.compile(
    r"\[([^\]\n]{2,120})\]\((https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?(?:\?[^)]*)?)\)",
    re.IGNORECASE,
)

_LINKEDIN_BODY_START_MARKERS = (
    "**about us**",
    "**position overview**",
    "**responsibilities**",
    "**qualifications",
    "about the job",
    "job description",
)

_LINKEDIN_BODY_END_MARKERS = (
    "show more",
    "show less",
    "### seniority level",
    "### employment type",
    "### job function",
    "### industries",
    "sign in to set job alerts",
    "similar jobs",
    "people also viewed",
    "referrals increase your chances",
    "set alert",
)

_LINKEDIN_NOISE_MARKERS = (
    "skip to main content",
    "linkedin",
    "sign in",
    "join now",
    "forgot password",
    "email or phone",
    "password",
    "clear text",
    "expand search",
    "user agreement",
    "privacy policy",
    "by clicking continue",
    "report this job",
    "save",
    "image",
    "trk=",
    "public_jobs_",
)


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


def is_hh_url(url: str) -> bool:
    host = (urlparse(url.strip()).hostname or "").lower()
    return host.endswith("hh.ru") or ".hh.ru" in host


def _compact_lines(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _strip_markdown_links_keep_text(line: str) -> str:
    return re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", line)


def _is_linkedin_noise_line(line: str) -> bool:
    line = line.strip()
    if not line:
        return True
    low = line.lower()
    if low.startswith("title:") or low.startswith("url source:") or low.startswith("markdown content:"):
        return True
    if low.startswith("![image"):
        return True
    if low in {"jobs", "people", "learning", "apply", "show", "or"}:
        return True
    if line.startswith("[") and "linkedin.com/jobs/view" in low:
        return True
    for marker in _LINKEDIN_NOISE_MARKERS:
        if marker in low:
            return True
    return False


def _find_linkedin_profile(lines: list[str]) -> tuple[str, str]:
    for line in lines:
        m = _LINKEDIN_MARKDOWN_PROFILE_RE.search(line)
        if not m:
            continue
        name = m.group(1).strip()
        url = m.group(2).strip().split("?", 1)[0]
        if not name or name.lower() in {"linkedin", "join now", "sign in"}:
            continue
        return name, url

    for idx, line in enumerate(lines):
        u = _LINKEDIN_PROFILE_RE.search(line)
        if not u:
            continue
        url = u.group(0).strip().split("?", 1)[0]
        name = ""
        for look_back in range(max(0, idx - 3), idx + 1):
            prev = lines[look_back].strip()
            if prev.startswith("### "):
                maybe = prev.replace("###", "").strip()
                if maybe and "linkedin" not in maybe.lower():
                    name = maybe
        return name, url
    return "", ""


def _extract_linkedin_title(lines: list[str]) -> str:
    for line in lines:
        if not line.startswith("#"):
            continue
        title = re.sub(r"^#+\s*", "", line).strip()
        low = title.lower()
        if not title or "linkedin" in low:
            continue
        if " hiring " in low and " in " in low:
            continue
        return title
    for line in lines:
        if not line.startswith("###"):
            continue
        title = re.sub(r"^#+\s*", "", line).strip()
        low = title.lower()
        if title and "linkedin" not in low and "join or sign in" not in low:
            return title
    return ""


def _extract_linkedin_company_location(lines: list[str]) -> tuple[str, str]:
    company = ""
    location = ""
    for line in lines:
        if "linkedin.com/company/" not in line.lower():
            continue
        m = re.search(r"\[([^\]]+)\]\((https?://[^)]+linkedin\.com/company/[^)]+)\)\s*(.*)", line, re.IGNORECASE)
        if not m:
            continue
        company = m.group(1).strip()
        tail = m.group(3).strip()
        tail = _strip_markdown_links_keep_text(tail)
        tail = re.sub(r"\s{2,}", " ", tail).strip()
        if tail:
            location = tail
        if company:
            break
    return company, location


def _extract_linkedin_body(lines: list[str]) -> list[str]:
    start_idx = -1
    for idx, line in enumerate(lines):
        low = line.strip().lower()
        if any(marker in low for marker in _LINKEDIN_BODY_START_MARKERS):
            start_idx = idx
            break
    if start_idx < 0:
        return []

    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        low = lines[idx].strip().lower()
        if any(marker in low for marker in _LINKEDIN_BODY_END_MARKERS):
            end_idx = idx
            break

    collected: list[str] = []
    seen: set[str] = set()
    for line in lines[start_idx:end_idx]:
        raw = line.strip()
        low = raw.lower()
        if _is_linkedin_noise_line(raw):
            continue
        if raw.startswith("**") and raw.endswith("**") and len(raw) > 4:
            raw = raw.strip("*").strip()
        if raw.startswith("*"):
            raw = "- " + re.sub(r"^\*\s*", "", raw)
        raw = _strip_markdown_links_keep_text(raw)
        raw = re.sub(r"\s{2,}", " ", raw).strip()
        if not raw:
            continue
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        collected.append(raw)
    return collected


def _clean_linkedin_jina_text(raw_text: str) -> str | None:
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        return None

    title = _extract_linkedin_title(lines)
    company, location = _extract_linkedin_company_location(lines)
    poster_name, poster_url = _find_linkedin_profile(lines)
    body_lines = _extract_linkedin_body(lines)

    if not body_lines:
        fallback: list[str] = []
        for ln in lines:
            if _is_linkedin_noise_line(ln):
                continue
            value = _strip_markdown_links_keep_text(ln)
            value = re.sub(r"\s{2,}", " ", value).strip()
            if value:
                fallback.append(value)
            if len(fallback) >= 120:
                break
        body_lines = fallback

    result_lines: list[str] = []
    if title:
        result_lines.append(f"# {title}")
    if company:
        result_lines.append(f"Company: {company}")
    if location:
        result_lines.append(f"Location: {location}")
    if poster_name or poster_url:
        if poster_name:
            result_lines.append(f"Posted by: {poster_name}")
        if poster_url:
            result_lines.append(poster_url)
    result_lines.append("")
    result_lines.append("Job Description:")
    result_lines.extend(body_lines)

    cleaned = _compact_lines("\n".join(result_lines))
    return cleaned if len(cleaned) >= 200 else None


def _extract_hh_description_from_jsonld(soup: BeautifulSoup) -> str:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            typ = str(item.get("@type", "")).lower()
            if typ != "jobposting":
                continue
            description_html = str(item.get("description", "")).strip()
            if not description_html:
                continue
            description_text = BeautifulSoup(description_html, "html.parser").get_text("\n", strip=True)
            description_text = _compact_lines(description_text)
            if len(description_text) >= 120:
                return description_text
    return ""


def parse_url_hh(url: str) -> str | None:
    """Targeted parser for hh.ru pages: vacancy title + clean JobPosting description."""
    try:
        resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=12)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("HH fetch failed for %s: %s", url, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    title_el = soup.select_one('[data-qa="vacancy-title"]') or soup.find("h1")
    company_el = soup.select_one('[data-qa="vacancy-company-name"]')
    location_el = soup.select_one('[data-qa="vacancy-view-raw-address"]')

    title = (title_el.get_text(" ", strip=True) if title_el else "").strip()
    company = (company_el.get_text(" ", strip=True) if company_el else "").strip()
    location = (location_el.get_text(" ", strip=True) if location_el else "").strip()

    desc_el = soup.select_one('[data-qa="vacancy-description"]')
    if desc_el:
        description = _compact_lines(desc_el.get_text("\n", strip=True))
    else:
        description = _extract_hh_description_from_jsonld(soup)

    if len(description) < 120:
        return None

    parts: list[str] = []
    if title:
        parts.append(f"# {title}")
    if company:
        parts.append(f"Компания: {company}")
    if location:
        parts.append(f"Локация: {location}")
    parts.append("")
    parts.append("Описание вакансии:")
    parts.append(description)

    result = "\n".join(parts).strip()
    return result if len(result) >= 200 else None


def parse_url_jina(url: str) -> str | None:
    """Parse JD via Jina Reader API (https://r.jina.ai/{url})."""
    try:
        resp = httpx.get(
            f"https://r.jina.ai/{url}",
            headers={"Accept": "text/plain"},
            timeout=10,
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
        resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=8)
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
    """
    if not is_safe_public_url(url):
        logger.warning("Blocked unsafe URL: %s", url)
        return None
    if is_linkedin_url(url):
        # LinkedIn pages are often login-protected in normal fetch.
        # Use Jina-only path to avoid pulling noisy BS4 login pages.
        linkedin_result = parse_url_jina(url)
        if linkedin_result:
            cleaned = _clean_linkedin_jina_text(linkedin_result)
            if cleaned:
                return cleaned
            return linkedin_result
        logger.info("LinkedIn parser could not extract JD for %s", url)
        return None
    if is_hh_url(url):
        hh_result = parse_url_hh(url)
        if hh_result:
            return hh_result
        logger.info("HH parser could not extract clean JD for %s", url)
        return None
    result = parse_url_jina(url)
    if result:
        return result
    logger.info("Jina failed, falling back to BS4 for %s", url)
    return parse_url_bs4(url)
