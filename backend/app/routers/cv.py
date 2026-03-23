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
    generate_text_fallback_pdf,
)
from app.services.canon import get_canonical_resume

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


def _safe_cv_pdf(markdown_text: str, company: str = "", role: str = "") -> bytes:
    title = " ".join(part for part in [company.strip(), role.strip()] if part).strip()
    if not title:
        title = "CV"

    # Primary: template-based render
    try:
        return generate_cv_pdf_from_markdown(markdown_text)
    except Exception as primary_err:
        logger.warning("Primary template PDF failed, fallback to markdown renderer: %s", primary_err)

    # Secondary: markdown->HTML renderer with its own fallback
    try:
        from app.services.pdf import render_cv_pdf

        return render_cv_pdf(markdown_text, company=company, role=role)
    except Exception as secondary_err:
        logger.warning("Secondary markdown PDF failed, fallback to minimal PDF: %s", secondary_err)

    # Final: always-return fallback
    return generate_text_fallback_pdf(markdown_text, title=title)


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
        pdf_bytes = _safe_cv_pdf(req.tailored_cv, company=req.company, role=req.role)
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
        canonical_md = get_canonical_resume()
        if canonical_md and canonical_md.strip():
            pdf_bytes = _safe_cv_pdf(canonical_md, company=req.company, role=req.role)
        else:
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
        canonical_md = get_canonical_resume()
        if canonical_md and canonical_md.strip():
            pdf_bytes = _safe_cv_pdf(canonical_md, company=company, role=role)
        else:
            pdf_bytes = render_canonical_cv_pdf()
    except Exception as e:
        logger.warning("Canonical markdown/docx PDF failed, trying resilient fallback: %s", e)
        try:
            pdf_bytes = generate_text_fallback_pdf(
                "Canonical resume is temporarily unavailable. Please try again.",
                title="CV Canonical",
            )
        except Exception as docx_err:
            logger.error("Canonical PDF generation failed (all fallbacks): %s", docx_err)
            raise HTTPException(500, f"PDF generation failed: {docx_err}")
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
        pdf_bytes = _safe_cv_pdf(req.tailored_cv, company=req.company, role=req.role)
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
