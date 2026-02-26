"""Letter router — generate cover letter for a JD."""

import logging

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.security import require_internal_api_key
from modules.letter.generate import generate_letter
from app.services.pdf import render_letter_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


class LetterRequest(BaseModel):
    jd_text: str
    notes: str = ""


class LetterPdfRequest(BaseModel):
    subject: str
    body: str
    company: str
    role: str


@router.post("/generate")
def generate(req: LetterRequest, _: None = Depends(require_internal_api_key)) -> dict:
    try:
        return generate_letter(req.jd_text, req.notes)
    except Exception as e:
        logger.error("Letter generation failed: %s", e)
        raise HTTPException(500, f"Letter generation failed: {e}")


@router.post("/pdf")
def letter_pdf(req: LetterPdfRequest, _: None = Depends(require_internal_api_key)):
    pdf_bytes = render_letter_pdf(req.subject, req.body, req.company, req.role)
    filename = f"CL_{req.company}_{req.role}.pdf".replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
