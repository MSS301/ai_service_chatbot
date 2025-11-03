import json
from typing import Tuple, List
import numpy as np, faiss
from openai import OpenAI
from app.core.config import INDEX_PATH, META_PATH, CHAT_MODEL
from app.core.logger import get_logger
from app.services.embedder import embed_query

logger = get_logger(__name__)
client = OpenAI()

# MVP lesson DB
LESSONS = {
  "L8-ALG-CH2-BT3": {"name": "Phương trình bậc hai", "grade": 8, "chapter": "Chương 2"}
}

def _get_lesson(lesson_id: str):
    return LESSONS.get(lesson_id, {"name":"", "grade":"", "chapter":""})

def _load_index_meta():
    index = faiss.read_index(INDEX_PATH)
    import json as _json
    meta = _json.load(open(META_PATH, "r", encoding="utf-8"))
    return index, meta

def _build_prompt(chunks, lesson, teacher_notes):
    context = "\n\n".join([
        f"[Nguồn: {c['book']}, trang {c['page']}]\n{c['text'][:1200]}"
        for c in chunks[:5]
    ])
    prompt = f"""
Bạn là giáo viên Toán giỏi. Dựa vào nội dung SGK sau:

{context}

Hãy tạo outline bài giảng cho "{lesson['name']}" (Lớp {lesson['grade']}) với 5-10 mục.
Yêu cầu:
- Mỗi mục có: Tiêu đề + 3-5 bullet points
- Thêm ví dụ thực tế theo gợi ý: "{teacher_notes}"
- Format JSON:
{{
  "sections": [
    {{"title": "...", "bullets": ["..."], "examples": ["..."]}}
  ]
}}
"""
    return prompt

def _call_llm(prompt: str) -> dict:
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": "Bạn là trợ lý giáo viên Toán"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        response_format={"type": "json_object"}
    )
    return json.loads(resp.choices[0].message.content)

def rag_query(lesson_id: str, teacher_notes: str, k: int = 8) -> Tuple[dict, List[float], List[int]]:
    lesson = _get_lesson(lesson_id)
    q = f"{lesson['name']} {teacher_notes}".strip()
    qvec = np.array(embed_query(q), dtype="float32").reshape(1, -1)

    index, meta = _load_index_meta()
    distances, indices = index.search(qvec, k)
    idxs = indices[0].tolist()
    dists = distances[0].tolist()
    chunks = [meta["chunks"][i] for i in idxs]

    prompt = _build_prompt(chunks, lesson, teacher_notes)
    outline = _call_llm(prompt)

    outline["sources"] = [
        {
          "book": chunks[i]["book"],
          "pages": [chunks[i]["page"]],
          "confidence": round(1 - dists[i], 4)
        } for i in range(min(3, len(chunks)))
    ]
    return outline, dists, idxs
