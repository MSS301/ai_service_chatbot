from fastapi import APIRouter, HTTPException
from app.models.rag_model import (
    SlidesGPTRequest, SlidesGPTResponse,
    TemplateSlidesRequest, TemplateSlidesResponse
)
from app.core.config import SLIDES_BASE_URL, SLIDESGPT_API_KEY, OPENAI_API_KEY
import requests, uuid, os
from pydantic import BaseModel
from app.repositories.content_repository import ContentRepository
from openai import OpenAI
import re
import yaml

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


class TemplateYAMLFromContentRequest(BaseModel):
    content_id: str
    created_by: str | None = None


class TemplateYAMLResponse(BaseModel):
    yaml: str


@router.post("/template/yaml", response_model=TemplateYAMLResponse)
def generate_template_yaml_from_content(req: TemplateYAMLFromContentRequest):
    """
    Sinh YAML slide từ content_id theo schema:
    slides: [ {layout, title, bullets: [...] } ]
    meta: { deck_title, author }
    """
    crepo = ContentRepository()
    doc = crepo.get_by_id(req.content_id)
    if not doc:
        raise HTTPException(status_code=404, detail="content_id not found")
    content_text = doc.get("content_text", "")
    if not content_text:
        raise HTTPException(status_code=400, detail="content_text is empty for this content_id")
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    client = OpenAI(api_key=OPENAI_API_KEY)
    system_msg = "Chỉ trả về YAML hợp lệ theo schema yêu cầu, không giải thích, không code block."
    user_msg = (
        "Chuyển nội dung sau thành YAML tạo slide theo schema:\n\n"
        "slides:\n"
        "  - layout: title_content\n"
        "    title: \"Tiêu đề\"\n"
        "    bullets:\n"
        "      - \"Bullet 1\"\n"
        "      - \"  - Sub-bullet\"\n"
        "meta:\n"
        "  deck_title: \"Bài giảng\"\n"
        "  author: \"\"\n\n"
        "YÊU CẦU:\n"
        "- layout mặc định: title_content\n"
        "- Sub-bullet bắt đầu bằng hai space + '- '\n"
        "- Giữ tiếng Việt, rõ ràng, không dùng code block\n\n"
        "Nội dung cần chuyển:\n"
        f"{content_text}\n"
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
    )
    yaml_text = resp.choices[0].message.content or ""
    # Loại bỏ code fences nếu có
    yaml_text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", yaml_text.strip(), flags=re.MULTILINE)

    # Chuẩn hoá bullets về danh sách phẳng các chuỗi (sub-bullet dùng '  - ')
    def flatten_bullets(node, level=0):
        lines = []
        if isinstance(node, list):
            for it in node:
                lines.extend(flatten_bullets(it, level))
        elif isinstance(node, dict):
            # Nếu LLM trả dict {text, children} không mong muốn -> chuyển text và duyệt children
            text = node.get("text")
            children = node.get("children")
            if text is not None:
                prefix = ("  - " * level) if level > 0 else ""
                lines.append(f"{prefix}{str(text).strip()}")
            if children:
                lines.extend(flatten_bullets(children, level + 1))
        elif isinstance(node, str):
            s = node.strip()
            # Giữ nguyên nếu đã có sub-bullet tiền tố
            if level == 0:
                lines.append(s)
            else:
                prefix = "  - " * level
                # nếu đã có tiền tố, giữ nguyên
                if re.match(r"^\s{2}-\s+", s):
                    lines.append(s)
                else:
                    lines.append(f"{prefix}{s}")
        else:
            # Các kiểu khác -> ép thành chuỗi
            val = str(node)
            prefix = ("  - " * level) if level > 0 else ""
            lines.append(f"{prefix}{val}")
        return lines

    try:
        data = yaml.safe_load(yaml_text) or {}
        slides = data.get("slides", [])
        for s in slides:
            bullets = s.get("bullets")
            if bullets is not None:
                s["bullets"] = flatten_bullets(bullets, level=0)
        # Bảo toàn meta nếu có, nếu không thì thêm khung trống
        if "meta" not in data:
            data["meta"] = {"deck_title": "Bài giảng", "author": ""}
        yaml_text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    except Exception:
        # Nếu parse lỗi, vẫn lưu nguyên văn đã strip codefence
        pass

    # Lưu vào DB vào field content_yaml
    crepo.save_content_yaml(req.content_id, yaml_text, created_by=req.created_by)
    return {"yaml": yaml_text}

