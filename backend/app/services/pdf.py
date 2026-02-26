"""PDF rendering service — markdown/text → styled PDF bytes via WeasyPrint."""

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

    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    if title:
        pdf.set_font("Helvetica", style="B", size=12)
        pdf.multi_cell(0, 6, _safe_text(title))
        pdf.ln(2)
        pdf.set_font("Helvetica", size=11)

    safe_body = _safe_text(text)
    for line in safe_body.splitlines():
        if not line.strip():
            pdf.ln(4)
            continue
        cleaned = line.replace("\t", " ").strip()
        if not cleaned:
            pdf.ln(4)
            continue
        try:
            pdf.multi_cell(0, 5, cleaned)
        except Exception:
            for word in cleaned.split(" "):
                if not word:
                    pdf.multi_cell(0, 5, " ")
                else:
                    pdf.multi_cell(0, 5, word)

    return pdf.output(dest="S").encode("latin-1", errors="ignore")

CV_CSS = """
@page {
    size: A4;
    margin: 2cm 2.5cm;
}
body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #222;
}
h1 { font-size: 20pt; margin: 0 0 4pt; color: #111; }
h2 { font-size: 13pt; margin: 18pt 0 4pt; color: #333; border-bottom: 1px solid #ccc; padding-bottom: 3pt; }
h3 { font-size: 11pt; margin: 12pt 0 2pt; color: #444; }
p { margin: 4pt 0; }
ul { margin: 4pt 0 4pt 18pt; padding: 0; }
li { margin: 2pt 0; }
strong { color: #111; }
a { color: #1a5276; text-decoration: none; }
"""

LETTER_CSS = """
@page {
    size: A4;
    margin: 2.5cm 3cm;
}
body {
    font-family: Georgia, "Times New Roman", serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #222;
}
.subject {
    font-size: 13pt;
    font-weight: bold;
    margin-bottom: 18pt;
    color: #111;
}
.body p {
    margin: 0 0 10pt;
    text-align: left;
}
"""


def render_cv_pdf(markdown_text: str, company: str, role: str) -> bytes:
    """Convert markdown CV to styled PDF bytes."""
    # Import lazily so API startup does not crash when system libs are missing.
    try:
        from weasyprint import HTML
    except Exception:
        html_body = markdown.markdown(markdown_text, extensions=["tables", "sane_lists"])
        text = _html_to_text(html_body)
        return _fallback_pdf(text, title=f"{company} — {role}")

    html_body = markdown.markdown(markdown_text, extensions=["tables", "sane_lists"])
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{CV_CSS}</style></head>
<body>{html_body}</body></html>"""
    return HTML(string=html).write_pdf()


def render_letter_pdf(subject: str, body: str, company: str, role: str) -> bytes:
    """Convert cover letter text to styled PDF bytes."""
    # Import lazily so API startup does not crash when system libs are missing.
    try:
        from weasyprint import HTML
    except Exception:
        return _fallback_pdf(body, title=subject)

    # Convert plain-text paragraphs to HTML
    paragraphs = "".join(f"<p>{p}</p>" for p in body.split("\n\n") if p.strip())
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{LETTER_CSS}</style></head>
<body>
<div class="subject">{subject}</div>
<div class="body">{paragraphs}</div>
</body></html>"""
    return HTML(string=html).write_pdf()
