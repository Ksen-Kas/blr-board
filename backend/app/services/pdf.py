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
    """Pre-process CV markdown before rendering.

    - Ensures only the first heading is h1 (the name)
    - Demotes any extra h1 lines after the name to bold paragraphs
    - Strips structural markers: '## Header', '---'
    """
    lines = md.strip().splitlines()
    result: list[str] = []
    h1_done = False

    # Strip canonical-resume metadata block at the top
    # Lines like "# Canonical Resume — ...", "**Version:** ...", "**Status:** ..."
    skip_meta = True

    for line in lines:
        if skip_meta:
            stripped_low = line.strip().lower()
            # Skip the meta title (h1 with "canonical resume" or "resume")
            if stripped_low.startswith("# canonical"):
                continue
            # Skip **Version:** and **Status:** lines
            if stripped_low.startswith("**version:**") or stripped_low.startswith("**status:**"):
                continue
            # Skip blank lines and --- while still in meta block
            if not line.strip() or re.fullmatch(r"-{3,}", line.strip()):
                continue
            # First real content line — stop skipping
            skip_meta = False
        stripped = line.strip()

        # Skip '## Header' marker — structural, not visible
        if stripped.lower() == "## header":
            continue

        # Skip horizontal rules (---) — they add visual noise in PDF
        if re.fullmatch(r"-{3,}", stripped):
            continue

        # Convert first **Name** line to # Name (from canonical format)
        if not h1_done:
            m = re.fullmatch(r"\*\*(.+?)\*\*\s*", stripped)
            if m:
                result.append(f"# {m.group(1)}")
                h1_done = True
                continue

        # If line is already # heading — keep first as h1, demote rest
        if stripped.startswith("# ") and not stripped.startswith("## "):
            if not h1_done:
                h1_done = True
                result.append(line)
            else:
                # Demote extra h1 to bold paragraph
                text = stripped[2:].strip()
                result.append(f"**{text}**")
            continue

        result.append(line)

    return "\n".join(result)


def _postprocess_cv_html(html_body: str) -> str:
    """Post-process converted HTML to style the header block.

    Identifies the name (h1), subtitle, tagline, and contact line.
    Wraps them in a .header-block div with semantic classes for CSS.
    """
    soup = BeautifulSoup(html_body, "html.parser")

    h1 = soup.find("h1")
    if not h1:
        return str(soup)

    # Collect all elements from h1 until the first h2
    header_elements = [h1]
    node = h1.next_sibling
    while node:
        next_node = node.next_sibling
        if getattr(node, "name", None) == "h2":
            break
        header_elements.append(node)
        node = next_node

    # Create wrapper div and insert before h1
    header_div = soup.new_tag("div", attrs={"class": "header-block"})
    h1.insert_before(header_div)

    # Move all header elements into the div
    for el in header_elements:
        header_div.append(el.extract() if hasattr(el, "extract") else el)

    # Tag the subtitle (first <p> with <strong> inside header block)
    for p in header_div.find_all("p"):
        if p.find("strong"):
            p["class"] = p.get("class", []) + ["subtitle"]
            break

    # Tag the contact line (paragraph containing '@' — email indicator)
    for p in header_div.find_all("p"):
        text = p.get_text()
        if "@" in text and "|" in text:
            p["class"] = p.get("class", []) + ["contact"]
            break

    return str(soup)


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
    font-size: 16pt;
    font-weight: bold;
    margin: 0 0 1pt;
    color: #000;
    line-height: 1.2;
}
.subtitle {
    font-size: 11pt;
    font-weight: bold;
    margin: 0 0 1pt;
    color: #333;
    line-height: 1.2;
}
.contact {
    font-size: 9pt;
    color: #444;
    margin: 2pt 0 8pt;
    line-height: 1.3;
}
.header-block {
    margin-bottom: 6pt;
}
.header-block p {
    margin: 1pt 0;
    line-height: 1.25;
}
h2 {
    font-size: 12pt;
    font-weight: bold;
    margin: 14pt 0 4pt;
    color: #000;
    break-after: avoid;
}
h3 {
    font-size: 10.5pt;
    font-weight: bold;
    margin: 10pt 0 1pt;
    color: #000;
    break-after: avoid;
}
h3 + p, h3 + ul {
    break-before: avoid;
}
p {
    margin: 1pt 0;
}
ul {
    margin: 2pt 0;
    padding-left: 14pt;
    list-style-type: none;
}
li {
    margin: 1pt 0;
    padding-left: 0;
    position: relative;
    page-break-inside: avoid;
}
li::before {
    content: "\\2022\\00a0";
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
    html_body = _postprocess_cv_html(html_body)

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
