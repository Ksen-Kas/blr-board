"""Letter router — generate cover letter for a JD."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.security import require_internal_api_key
from app.services.parser import is_linkedin_url, is_safe_public_url, parse_url
from modules.letter.generate import generate_letter
from app.services.pdf import render_letter_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


class LetterRequest(BaseModel):
    jd_text: str
    notes: str = ""
    source_url: str = ""


class LetterPdfRequest(BaseModel):
    subject: str
    body: str
    company: str
    role: str


@router.post("/generate")
def generate(req: LetterRequest, _: None = Depends(require_internal_api_key)) -> dict:
    jd_text = (req.jd_text or "").strip()
    source_url = (req.source_url or "").strip()

    if not jd_text and source_url:
        if is_safe_public_url(source_url) and not is_linkedin_url(source_url):
            parsed = parse_url(source_url)
            if parsed:
                jd_text = parsed.strip()

    if not jd_text:
        raise HTTPException(
            422,
            "JD text is required. Add JD text in card comment/description or provide a parseable source URL.",
        )

    try:
        result = generate_letter(jd_text, req.notes)
        result["jd_text_used"] = jd_text
        return result
    except Exception as e:
        logger.error("Letter generation failed: %s", e)
        raise HTTPException(500, f"Letter generation failed: {e}")


@router.post("/pdf")
def letter_pdf(req: LetterPdfRequest, _: None = Depends(require_internal_api_key)):
    try:
        pdf_bytes = render_letter_pdf(req.subject, req.body, req.company, req.role)
    except Exception as e:
        logger.error("Letter PDF generation failed: %s", e)
        raise HTTPException(500, f"PDF generation failed: {e}")
    filename = f"CL_{req.company}_{req.role}.pdf".replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
