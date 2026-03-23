"""HTML template based CV rendering service (Jinja2 + WeasyPrint)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from jinja2 import Template

from app.services.canon import get_canonical_resume

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
RESUME_TEMPLATE_PATH = TEMPLATES_DIR / "resume_template.html"
RESUME_STYLES_PATH = TEMPLATES_DIR / "resume_styles.css"

SECTION_MAP = {
    "professional summary": "summary",
    "core competencies": "skills",
    "experience": "experience",
    "technical toolkit": "toolkit",
    "education": "education",
}
DEFAULT_LINKEDIN_URL = "https://www.linkedin.com/in/andrey-kasyanov-94b948100/"


def _normalize(text: str) -> str:
    return " ".join(text.replace("\u2013", "-").replace("\u2014", "-").split()).strip().lower()


def _strip_md(text: str) -> str:
    clean = text.strip()
    clean = re.sub(r"^\*{1,2}(.+?)\*{1,2}$", r"\1", clean)
    clean = re.sub(r"^#{1,6}\s*", "", clean)
    clean = re.sub(r"^-+\s*", "", clean)
    clean = clean.replace("**", "")
    return clean.strip()


def _extract_sections(markdown_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {
        "header": [],
        "summary": [],
        "skills": [],
        "experience": [],
        "toolkit": [],
        "education": [],
    }

    current = "header"
    for raw in markdown_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("# canonical resume"):
            continue
        if low.startswith("**version:") or low.startswith("**status:"):
            continue
        if re.fullmatch(r"-{3,}", line):
            continue
        if line.startswith("## "):
            heading = _strip_md(line).lower()
            current = SECTION_MAP.get(heading, current)
            continue
        sections[current].append(line)
    return sections


def _parse_header(lines: list[str]) -> dict[str, str]:
    parsed = {
        "name": "",
        "title": "",
        "tagline": "",
        "location": "",
        "email": "",
        "linkedin_label": "",
        "linkedin_url": "",
        "phone": "",
    }
    clean = [_strip_md(x) for x in lines if _strip_md(x)]
    if clean:
        parsed["name"] = clean[0]
    if len(clean) > 1:
        parsed["title"] = clean[1]
    if len(clean) > 2:
        parsed["tagline"] = clean[2]
    if len(clean) > 3:
        parts = [p.strip() for p in clean[3].split("|")]
        if parts:
            parsed["location"] = parts[0] if len(parts) > 0 else ""
            parsed["email"] = parts[1] if len(parts) > 1 else ""
            parsed["linkedin_label"] = parts[2] if len(parts) > 2 else "LinkedIn"
            parsed["linkedin_url"] = DEFAULT_LINKEDIN_URL
            parsed["phone"] = parts[3] if len(parts) > 3 else ""
    if not parsed["linkedin_url"]:
        parsed["linkedin_label"] = "LinkedIn"
        parsed["linkedin_url"] = DEFAULT_LINKEDIN_URL
    return parsed


def _parse_experience(lines: list[str], added: set[str]) -> list[dict]:
    jobs: list[dict] = []
    current: dict | None = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            if current:
                jobs.append(current)
            company = _strip_md(line)
            current = {
                "company_line": company,
                "company_changed": _normalize(company) in added,
                "role": "",
                "role_changed": False,
                "bullets": [],
            }
            continue
        clean = _strip_md(line)
        if current is None:
            continue
        if line.startswith("- "):
            current["bullets"].append({"text": clean, "changed": _normalize(clean) in added})
            continue
        if not current["role"]:
            current["role"] = clean
            current["role_changed"] = _normalize(clean) in added
        else:
            current["bullets"].append({"text": clean, "changed": _normalize(clean) in added})
    if current:
        jobs.append(current)
    return jobs


def _parse_resume(markdown_text: str, added: set[str] | None = None) -> dict:
    sections = _extract_sections(markdown_text)
    changed = added or set()
    header = _parse_header(sections["header"])

    summary = " ".join(_strip_md(x) for x in sections["summary"]).strip()
    skills = [_strip_md(x) for x in sections["skills"] if _strip_md(x)]
    toolkit = [_strip_md(x) for x in sections["toolkit"] if _strip_md(x)]
    education = [_strip_md(x) for x in sections["education"] if _strip_md(x)]

    return {
        "name": header["name"],
        "title": header["title"],
        "tagline": header["tagline"],
        "tagline_changed": _normalize(header["tagline"]) in changed,
        "location": header["location"],
        "email": header["email"],
        "linkedin_label": header["linkedin_label"],
        "linkedin_url": header["linkedin_url"],
        "phone": header["phone"],
        "summary": summary,
        "summary_changed": _normalize(summary) in changed,
        "skills": [{"text": s, "changed": _normalize(s) in changed} for s in skills],
        "experience": _parse_experience(sections["experience"], changed),
        "toolkit": [{"text": s, "changed": _normalize(s) in changed} for s in toolkit],
        "education": [_parse_education_line(s, changed) for s in education],
    }


def _parse_education_line(line: str, changed: set[str]) -> dict:
    text = _strip_md(line)
    for sep in [" — ", " - "]:
        if sep in text:
            school, details = text.split(sep, 1)
            return {
                "text": text,
                "school": school.strip(),
                "details": details.strip(),
                "changed": _normalize(text) in changed,
            }
    return {"text": text, "school": "", "details": "", "changed": _normalize(text) in changed}


def _load_template() -> str:
    return RESUME_TEMPLATE_PATH.read_text(encoding="utf-8")


def _load_css() -> str:
    return RESUME_STYLES_PATH.read_text(encoding="utf-8")


def _render_html(data: dict, preview_mode: bool = False) -> str:
    template = Template(_load_template())
    payload = dict(data)
    payload["css"] = _load_css()
    payload["preview_mode"] = preview_mode
    return template.render(**payload)


def _safe_pdf_text(value: str) -> str:
    value = (
        value.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2012", "-")
        .replace("\u2011", "-")
        .replace("\u00a0", " ")
    )
    return value.encode("latin-1", errors="ignore").decode("latin-1")


def _minimal_pdf(text: str, title: str = "") -> bytes:
    def esc(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines = []
    if title:
        lines.append(title)
        lines.append("")
    lines.extend(text.splitlines())
    lines = [esc(_safe_pdf_text(line)) for line in lines if line is not None]

    y = 800
    content_parts = ["BT", "/F1 11 Tf", "50 800 Td"]
    first = True
    for line in lines:
        if not first:
            content_parts.append("0 -14 Td")
        content_parts.append(f"({line or ' '}) Tj")
        first = False
        y -= 14
        if y < 60:
            break
    content_parts.append("ET")
    content = "\n".join(content_parts).encode("latin-1", errors="ignore")

    objs = []
    objs.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n"
    )
    objs.append(b"4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
    objs.append(
        f"5 0 obj<< /Length {len(content)} >>stream\n".encode("latin-1")
        + content
        + b"\nendstream\nendobj\n"
    )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objs)+1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            f"trailer<< /Size {len(objs)+1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(pdf)


def _fallback_pdf(text: str, title: str = "") -> bytes:
    try:
        from fpdf import FPDF
    except Exception:
        return _minimal_pdf(text, title=title)

    def _break_long_tokens(value: str, max_len: int = 40) -> str:
        parts: list[str] = []
        for token in value.split(" "):
            if len(token) <= max_len:
                parts.append(token)
                continue
            chunks = [token[i : i + max_len] for i in range(0, len(token), max_len)]
            parts.extend(chunks)
        return " ".join(parts)

    def _mc(pdf_obj: FPDF, h: int, txt: str) -> None:
        pdf_obj.set_x(pdf_obj.l_margin)
        pdf_obj.multi_cell(0, h, txt)

    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    if title:
        pdf.set_font("Helvetica", style="B", size=12)
        _mc(pdf, 6, _safe_pdf_text(title))
        pdf.ln(2)
        pdf.set_font("Helvetica", size=11)

    for line in text.splitlines():
        if not line.strip():
            pdf.ln(3)
            continue
        cleaned = _break_long_tokens(_safe_pdf_text(line))
        if not cleaned:
            pdf.ln(3)
            continue
        try:
            _mc(pdf, 5, cleaned)
        except Exception:
            for word in cleaned.split(" "):
                try:
                    _mc(pdf, 5, word if word else " ")
                except Exception:
                    pass

    return bytes(pdf.output())


def _resume_data_to_text(data: dict) -> str:
    lines: list[str] = []

    header_bits = [data.get("name", ""), data.get("title", ""), data.get("tagline", "")]
    lines.extend([bit for bit in header_bits if bit])

    contact_bits = [
        data.get("location", ""),
        data.get("email", ""),
        data.get("linkedin_label", ""),
        data.get("phone", ""),
    ]
    if any(contact_bits):
        lines.append(" | ".join(bit for bit in contact_bits if bit))

    summary = data.get("summary", "")
    if summary:
        lines.extend(["", "PROFESSIONAL SUMMARY", summary])

    skills = data.get("skills", [])
    if skills:
        lines.append("")
        lines.append("CORE COMPETENCIES")
        for item in skills:
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            if text:
                lines.append(f"- {text}")

    experience = data.get("experience", [])
    if experience:
        lines.append("")
        lines.append("EXPERIENCE")
        for job in experience:
            company = job.get("company_line", "") if isinstance(job, dict) else ""
            role = job.get("role", "") if isinstance(job, dict) else ""
            if company:
                lines.append(company)
            if role:
                lines.append(role)
            for bullet in job.get("bullets", []) if isinstance(job, dict) else []:
                bullet_text = bullet.get("text", "") if isinstance(bullet, dict) else str(bullet)
                if bullet_text:
                    lines.append(f"- {bullet_text}")
            lines.append("")

    toolkit = data.get("toolkit", [])
    if toolkit:
        lines.append("TECHNICAL TOOLKIT")
        for item in toolkit:
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            if text:
                lines.append(f"- {text}")

    education = data.get("education", [])
    if education:
        lines.append("")
        lines.append("EDUCATION")
        for item in education:
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            if text:
                lines.append(f"- {text}")

    return "\n".join(lines).strip()


def generate_cv_pdf(data: dict) -> bytes:
    """Render resume data as a PDF using WeasyPrint."""
    html = _render_html(data=data, preview_mode=False)
    try:
        from weasyprint import HTML

        return HTML(string=html).write_pdf()
    except Exception:
        text = _resume_data_to_text(data)
        return _fallback_pdf(text, title=data.get("name", ""))


def generate_cv_pdf_from_markdown(markdown_text: str) -> bytes:
    parsed = _parse_resume(markdown_text)
    return generate_cv_pdf(parsed)


def build_tailored_preview_html(tailored_markdown: str) -> str:
    canonical = get_canonical_resume()
    preview = _build_track_changes_preview(canonical, tailored_markdown)
    added_lines = {
        _normalize(item["text"])
        for section in preview
        for item in section.get("lines", [])
        if item.get("type") == "added"
    }
    data = _parse_resume(tailored_markdown, added=added_lines)
    return _render_html(data=data, preview_mode=True)


def generate_canonical_cv_pdf() -> bytes:
    return generate_cv_pdf_from_markdown(get_canonical_resume())


def generate_text_fallback_pdf(text: str, title: str = "") -> bytes:
    """Public safe fallback PDF helper (never raises on missing render deps)."""
    return _fallback_pdf(text or "", title=title)


def _build_track_changes_preview(canonical_md: str, tailored_md: str) -> list[dict]:
    preview: list[dict] = []
    canonical_sections = _extract_sections(canonical_md)
    tailored_sections = _extract_sections(tailored_md)
    section_order = ["summary", "skills", "experience", "toolkit", "education"]

    for section in section_order:
        before = [_strip_md(x) for x in canonical_sections.get(section, []) if _strip_md(x)]
        after = [_strip_md(x) for x in tailored_sections.get(section, []) if _strip_md(x)]
        matcher = SequenceMatcher(a=before, b=after)
        lines: list[dict[str, str]] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                lines.extend({"type": "same", "text": s} for s in before[i1:i2])
            elif tag == "delete":
                lines.extend({"type": "removed", "text": s} for s in before[i1:i2])
            elif tag == "insert":
                lines.extend({"type": "added", "text": s} for s in after[j1:j2])
            else:
                lines.extend({"type": "removed", "text": s} for s in before[i1:i2])
                lines.extend({"type": "added", "text": s} for s in after[j1:j2])
        if lines:
            preview.append({"section": section, "lines": lines})

    return preview
