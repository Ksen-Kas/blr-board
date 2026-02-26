"""PDF rendering service — markdown/text → styled PDF bytes via WeasyPrint."""

import re

import markdown
from bs4 import BeautifulSoup


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _fallback_pdf(text: str, title: str | None = None) -> bytes:
    """Fallback PDF renderer that avoids system deps (no WeasyPrint)."""
    from fpdf import FPDF

    def _safe_text(value: str) -> str:
        value = (
            value.replace("\u2014", "-")
            .replace("\u2013", "-")
            .replace("\u2012", "-")
            .replace("\u2011", "-")
            .replace("\u00a0", " ")
        )
        return value.encode("latin-1", errors="ignore").decode("latin-1")

    def _break_long_tokens(value: str, max_len: int = 40) -> str:
        parts: list[str] = []
        for token in value.split(" "):
            if len(token) <= max_len:
                parts.append(token)
                continue
            chunks = [token[i : i + max_len] for i in range(0, len(token), max_len)]
            parts.extend(chunks)
        return " ".join(parts)

    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    def _mc(h: int, txt: str) -> None:
        """multi_cell with cursor reset — fpdf2 doesn't auto-reset x."""
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, h, txt)

    if title:
        pdf.set_font("Helvetica", style="B", size=12)
        _mc(6, _safe_text(title))
        pdf.ln(2)
        pdf.set_font("Helvetica", size=11)

    safe_body = _break_long_tokens(_safe_text(text))
    for line in safe_body.splitlines():
        if not line.strip():
            pdf.ln(4)
            continue
        cleaned = _break_long_tokens(line.replace("\t", " ").strip())
        if not cleaned:
            pdf.ln(4)
            continue
        try:
            _mc(5, cleaned)
        except Exception:
            for word in cleaned.split(" "):
                try:
                    _mc(5, word if word else " ")
                except Exception:
                    pass

    return bytes(pdf.output())


def _prepare_cv_markdown(md: str) -> str:
    """Pre-process CV markdown so the name renders as h1.

    The canonical resume uses **Name** (bold paragraph) instead of # Name.
    This converts the first bold-only line to a proper h1 heading, and strips
    internal section markers like '## Header' and '---' dividers.
    """
    lines = md.strip().splitlines()
    result: list[str] = []
    name_done = False

    for line in lines:
        stripped = line.strip()

        # Skip '## Header' marker — it's structural, not visible
        if stripped.lower() == "## header":
            continue

        # Skip horizontal rules
        if re.fullmatch(r"-{3,}", stripped):
            continue

        # Convert first **Name** line to # Name
        if not name_done:
            m = re.fullmatch(r"\*\*(.+?)\*\*\s*", stripped)
            if m:
                result.append(f"# {m.group(1)}")
                name_done = True
                continue

        result.append(line)

    return "\n".join(result)


# ─── CSS ──────────────────────────────────────────────────────────────────────
# Matches the reference layout: Andrey_Kasyanov_PMC_Specialist_RE_CV.pdf
# A4, 1-inch margins, Arial, clean bullets, no decorative rules.

CV_CSS = """
@page {
    size: A4;
    margin: 1.8cm 2.2cm;
}
body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 10.5pt;
    line-height: 1.3;
    color: #000;
}
h1 {
    font-size: 22pt;
    font-weight: bold;
    margin: 0 0 3pt;
    color: #000;
    line-height: 1.15;
}
h2 {
    font-size: 12pt;
    font-weight: bold;
    margin: 16pt 0 5pt;
    color: #000;
}
h3 {
    font-size: 10.5pt;
    font-weight: bold;
    margin: 10pt 0 1pt;
    color: #000;
}
p {
    margin: 1pt 0;
}
ul {
    margin: 2pt 0;
    padding-left: 18pt;
    list-style-type: disc;
}
li {
    margin: 1pt 0;
    padding-left: 2pt;
}
strong {
    color: #000;
    font-weight: bold;
}
a {
    color: #1155cc;
    text-decoration: none;
}
hr {
    border: none;
    height: 0;
    margin: 0;
}
"""

LETTER_CSS = """
@page {
    size: A4;
    margin: 2.54cm 2.54cm;
}
body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 10.5pt;
    line-height: 1.5;
    color: #000;
}
.subject {
    font-size: 12pt;
    font-weight: bold;
    margin-bottom: 16pt;
    color: #000;
}
.body p {
    margin: 0 0 10pt;
    text-align: left;
}
"""


def render_cv_pdf(markdown_text: str, company: str, role: str) -> bytes:
    """Convert markdown CV to styled PDF bytes."""
    cleaned_md = _prepare_cv_markdown(markdown_text)
    html_body = markdown.markdown(cleaned_md, extensions=["tables", "sane_lists"])

    try:
        from weasyprint import HTML

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{CV_CSS}</style></head>
<body>{html_body}</body></html>"""
        return HTML(string=html).write_pdf()
    except Exception:
        text = _html_to_text(html_body)
        return _fallback_pdf(text, title=f"{company} - {role}")


def render_letter_pdf(subject: str, body: str, company: str, role: str) -> bytes:
    """Convert cover letter text to styled PDF bytes."""
    try:
        from weasyprint import HTML
        from html import escape

        paragraphs = "".join(
            f"<p>{escape(p)}</p>" for p in body.split("\n\n") if p.strip()
        )
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{LETTER_CSS}</style></head>
<body>
<div class="subject">{escape(subject)}</div>
<div class="body">{paragraphs}</div>
</body></html>"""
        return HTML(string=html).write_pdf()
    except Exception:
        return _fallback_pdf(body, title=subject)
