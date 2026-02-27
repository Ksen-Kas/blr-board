"""CV router — tailor resume for a specific JD."""

import logging

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.security import require_internal_api_key
from modules.cv.tailor import tailor_cv
from app.services.cv_docx import render_tailored_cv_pdf, render_canonical_cv_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


class TailorRequest(BaseModel):
    jd_text: str


class CvPdfRequest(BaseModel):
    tailored_cv: str
    company: str
    role: str


class CanonicalCvPdfRequest(BaseModel):
    company: str
    role: str


@router.post("/tailor")
def tailor(req: TailorRequest, _: None = Depends(require_internal_api_key)) -> dict:
    try:
        return tailor_cv(req.jd_text)
    except Exception as e:
        logger.error("CV tailoring failed: %s", e)
        raise HTTPException(500, f"CV tailoring failed: {e}")


@router.post("/pdf")
def cv_pdf(req: CvPdfRequest, _: None = Depends(require_internal_api_key)):
    try:
        pdf_bytes = render_tailored_cv_pdf(req.tailored_cv)
    except Exception as e:
        logger.error("CV PDF generation failed: %s", e)
        raise HTTPException(500, f"PDF generation failed: {e}")
    filename = f"CV_{req.company}_{req.role}.pdf".replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/pdf/canonical")
def cv_pdf_canonical(req: CanonicalCvPdfRequest, _: None = Depends(require_internal_api_key)):
    try:
        pdf_bytes = render_canonical_cv_pdf()
    except Exception as e:
        logger.error("Canonical CV PDF generation failed: %s", e)
        raise HTTPException(500, f"PDF generation failed: {e}")
    filename = f"CV_CANON_{req.company}_{req.role}.pdf".replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
