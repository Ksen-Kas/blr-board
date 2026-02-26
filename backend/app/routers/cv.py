"""CV router — tailor resume for a specific JD."""

import logging

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.security import require_internal_api_key
from modules.cv.tailor import tailor_cv
from app.services.pdf import render_cv_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


class TailorRequest(BaseModel):
    jd_text: str


class CvPdfRequest(BaseModel):
    tailored_cv: str
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
    pdf_bytes = render_cv_pdf(req.tailored_cv, req.company, req.role)
    filename = f"CV_{req.company}_{req.role}.pdf".replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
