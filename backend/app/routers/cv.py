"""CV router — tailor resume for a specific JD."""

import logging

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, HTMLResponse

from app.security import require_internal_api_key
from modules.cv.tailor import tailor_cv
from app.services.cv_docx import render_tailored_cv_pdf, render_canonical_cv_pdf
from app.services.pdf_generator import (
    build_tailored_preview_html,
    generate_canonical_cv_pdf,
    generate_cv_pdf_from_markdown,
)

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


class TailoredCvPdfRequest(BaseModel):
    tailored_cv: str
    company: str = ""
    role: str = ""


class TailoredCvPreviewRequest(BaseModel):
    tailored_cv: str


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


@router.get("/canonical-pdf")
def canonical_pdf(
    company: str = Query(default=""),
    role: str = Query(default=""),
    _: None = Depends(require_internal_api_key),
):
    try:
        pdf_bytes = generate_canonical_cv_pdf()
    except Exception as e:
        logger.error("Canonical template PDF generation failed: %s", e)
        raise HTTPException(500, f"PDF generation failed: {e}")
    suffix = "_".join(part for part in [company, role] if part).replace(" ", "_")
    filename = f"CV_CANON_{suffix}.pdf" if suffix else "CV_CANON.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/tailored-pdf")
def tailored_pdf(req: TailoredCvPdfRequest, _: None = Depends(require_internal_api_key)):
    try:
        pdf_bytes = generate_cv_pdf_from_markdown(req.tailored_cv)
    except Exception as e:
        logger.error("Tailored template PDF generation failed: %s", e)
        raise HTTPException(500, f"PDF generation failed: {e}")
    suffix = "_".join(part for part in [req.company, req.role] if part).replace(" ", "_")
    filename = f"CV_{suffix}.pdf" if suffix else "CV_tailored.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/tailored-preview-html", response_class=HTMLResponse)
def tailored_preview_html(req: TailoredCvPreviewRequest, _: None = Depends(require_internal_api_key)):
    try:
        html = build_tailored_preview_html(req.tailored_cv)
    except Exception as e:
        logger.error("Tailored preview generation failed: %s", e)
        raise HTTPException(500, f"Preview generation failed: {e}")
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")
