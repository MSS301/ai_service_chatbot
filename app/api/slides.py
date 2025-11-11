from fastapi import APIRouter, HTTPException
from app.models.rag_model import (
    SlidesGPTRequest, SlidesGPTResponse,
    TemplateSlidesRequest, TemplateSlidesResponse
)
from app.core.config import SLIDES_BASE_URL, SLIDESGPT_API_KEY
import requests, uuid, os

router = APIRouter()

@router.post("/slidesgpt", response_model=SlidesGPTResponse)
def create_with_slidesgpt(req: SlidesGPTRequest):
    """
    Tạo slide qua SlidesGPT (proxy).
    Body: { "prompt": "..." }
    Trả về: { id, embed, download }
    """
    base = SLIDES_BASE_URL.rstrip("/")
    api_key = SLIDESGPT_API_KEY or os.getenv("SLIDESGPT_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="SLIDESGPT_API_KEY not configured")

    url = f"{base}/v1/presentations/generate"
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"prompt": req.prompt},
            timeout=120,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=f"SlidesGPT error: {r.text}")
        data = r.json()
        return {
            "id": data.get("id", uuid.uuid4().hex),
            "embed": data.get("embed"),
            "download": data.get("download"),
        }
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"SlidesGPT request failed: {e}")


@router.post("/template", response_model=TemplateSlidesResponse)
def create_with_template(req: TemplateSlidesRequest):
    """
    Tạo slide theo khung template (JSON) để client render PPT/HTML.
    Body: { title, outline, theme? }
    """
    outline = req.outline or {}
    sections = outline.get("sections", [])
    slides = []
    slides.append({"type": "title", "title": req.title, "subtitle": req.theme or ""})
    for sec in sections:
        slides.append({
            "type": "content",
            "title": sec.get("title", ""),
            "bullets": sec.get("bullets", []),
            "examples": sec.get("examples", []),
        })
    slides.append({"type": "closing", "title": "Tổng kết", "bullets": ["Câu hỏi?", "Bài tập/vận dụng"]})
    return {"slides": slides}


