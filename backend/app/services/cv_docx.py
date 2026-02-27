"""CV DOCX/PDF service based on canonical .docx template."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from docx import Document

from app import config
from app.services.canon import get_canonical_resume

SECTION_ORDER = [
    "Header",
    "Professional Summary",
    "Core Competencies",
    "Experience",
    "Technical Toolkit",
    "Education",
]


def _canonical_template_path() -> Path:
    path = Path(config.CLIENT_SPACE_PATH) / "canonical_resume.docx"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing template: {path}. Put canonical_resume.docx into CLIENT_SPACE."
        )
    return path


def _run_libreoffice_convert(input_docx: Path, output_dir: Path) -> Path:
    commands = [
        [
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(output_dir),
            str(input_docx),
        ],
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(output_dir),
            str(input_docx),
        ],
    ]

    last_error: Exception | None = None
    for cmd in commands:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            pdf_path = output_dir / f"{input_docx.stem}.pdf"
            if pdf_path.exists():
                return pdf_path
        except Exception as exc:  # pragma: no cover - environment-dependent
            last_error = exc

    raise RuntimeError(
        "LibreOffice conversion failed. Install libreoffice/soffice and ensure it is in PATH."
    ) from last_error


def _normalize_line(text: str) -> str:
    return " ".join(text.replace("\u2013", "-").replace("\u2014", "-").split()).strip()


def _clean_markdown_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^\*{2}(.+?)\*{2}$", r"\1", line)
    line = re.sub(r"^\*{1}(.+?)\*{1}$", r"\1", line)
    line = re.sub(r"^#{1,6}\s*", "", line)
    line = re.sub(r"^-+\s*", "", line)
    line = line.replace("**", "").strip()
    return line


def _extract_sections(markdown_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {name: [] for name in SECTION_ORDER}
    current = "Header"

    for raw in markdown_text.splitlines():
        line = raw.strip()
        if not line or re.fullmatch(r"-{3,}", line):
            continue
        low = line.lower()
        if low.startswith("**version:") or low.startswith("**status:"):
            continue

        if line.startswith("## "):
            heading = _clean_markdown_line(line)
            if heading in sections:
                current = heading
            continue

        cleaned = _clean_markdown_line(line)
        if cleaned:
            sections.setdefault(current, []).append(cleaned)

    return sections


def _to_flat_lines(sections: dict[str, list[str]]) -> list[str]:
    lines: list[str] = []
    for section in SECTION_ORDER:
        lines.extend(sections.get(section, []))
    return lines


def _build_replacements(canonical_md: str, tailored_md: str) -> dict[str, list[str]]:
    canonical = _to_flat_lines(_extract_sections(canonical_md))
    tailored = _to_flat_lines(_extract_sections(tailored_md))

    # Index-based replacement keeps the template structure stable.
    replacements: dict[str, list[str]] = defaultdict(list)
    limit = min(len(canonical), len(tailored))
    for i in range(limit):
        old = _normalize_line(canonical[i])
        new = tailored[i].strip()
        if old and old != _normalize_line(new):
            replacements[old].append(new)
    return replacements


def _replace_paragraph_text(paragraph, text: str) -> None:
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.text = text


def _apply_replacements(doc: Document, replacements: dict[str, list[str]]) -> None:
    if not replacements:
        return

    for paragraph in doc.paragraphs:
        key = _normalize_line(paragraph.text)
        if not key:
            continue
        queue = replacements.get(key)
        if queue:
            _replace_paragraph_text(paragraph, queue.pop(0))


def _render_docx_to_pdf_bytes(docx_path: Path) -> bytes:
    with tempfile.TemporaryDirectory(prefix="joe_cv_pdf_") as tmp:
        out_dir = Path(tmp)
        pdf_path = _run_libreoffice_convert(docx_path, out_dir)
        return pdf_path.read_bytes()


def render_canonical_cv_pdf() -> bytes:
    template = _canonical_template_path()
    return _render_docx_to_pdf_bytes(template)


def render_tailored_cv_pdf(tailored_markdown: str) -> bytes:
    template = _canonical_template_path()
    canonical_md = get_canonical_resume()
    replacements = _build_replacements(canonical_md, tailored_markdown)

    with tempfile.TemporaryDirectory(prefix="joe_cv_docx_") as tmp:
        tmp_dir = Path(tmp)
        docx_copy = tmp_dir / "tailored_resume.docx"
        shutil.copy2(template, docx_copy)

        doc = Document(str(docx_copy))
        _apply_replacements(doc, replacements)
        doc.save(str(docx_copy))

        return _render_docx_to_pdf_bytes(docx_copy)


def build_track_changes_preview(canonical_md: str, tailored_md: str) -> list[dict]:
    from difflib import SequenceMatcher

    preview: list[dict] = []
    canonical_sections = _extract_sections(canonical_md)
    tailored_sections = _extract_sections(tailored_md)

    for section in SECTION_ORDER:
        before = canonical_sections.get(section, [])
        after = tailored_sections.get(section, [])
        matcher = SequenceMatcher(a=before, b=after)
        lines: list[dict[str, str]] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                lines.extend({"type": "same", "text": s} for s in before[i1:i2])
            elif tag == "delete":
                lines.extend({"type": "removed", "text": s} for s in before[i1:i2])
            elif tag == "insert":
                lines.extend({"type": "added", "text": s} for s in after[j1:j2])
            else:  # replace
                lines.extend({"type": "removed", "text": s} for s in before[i1:i2])
                lines.extend({"type": "added", "text": s} for s in after[j1:j2])
        if lines:
            preview.append({"section": section, "lines": lines})
    return preview
