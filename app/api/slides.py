from fastapi import APIRouter, HTTPException
from app.models.rag_model import (
    SlidesGPTRequest, SlidesGPTResponse,
    TemplateSlidesRequest, TemplateSlidesResponse
)
from app.core.config import SLIDES_BASE_URL, SLIDESGPT_API_KEY
import requests, uuid, os
from pydantic import BaseModel
from app.repositories.content_repository import ContentRepository

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

class SlidesGPTFromContentRequest(BaseModel):
    content_id: str
    created_by: str | None = None

@router.post("/gpt", response_model=SlidesGPTResponse)
def create_with_slidesgpt_from_content(req: SlidesGPTFromContentRequest):
    """
    Tạo slide qua SlidesGPT bằng content_id.
    Hệ thống tự lấy content_text đã sinh làm prompt.
    """
    # Load content
    crepo = ContentRepository()
    doc = crepo.get_by_id(req.content_id)
    if not doc:
        raise HTTPException(status_code=404, detail="content_id not found")
    prompt = doc.get("content_text", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="content_text is empty for this content_id")

    # Call SlidesGPT
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
            json={"prompt": prompt},
            timeout=120,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=f"SlidesGPT error: {r.text}")
        data = r.json()
        resp = {
            "id": data.get("id", uuid.uuid4().hex),
            "embed": data.get("embed"),
            "download": data.get("download"),
        }
        # Save to DB under this content_id
        crepo.save_slidesgpt(req.content_id, resp, created_by=req.created_by)
        return resp
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


