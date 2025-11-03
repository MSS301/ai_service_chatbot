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
Bạn là giáo viên Toán. CHỈ sử dụng thông tin trong 'Nội dung SGK' bên dưới.

Nếu không đủ thông tin, trả về đúng JSON:
{{"sections": [], "note": "Không tìm thấy nội dung phù hợp trong SGK đã nạp."}}

Nội dung SGK:
{context}

Yêu cầu: Tạo outline cho "{lesson['name']}" (Lớp {lesson['grade']}) với 5-10 mục.
- Mỗi mục: Tiêu đề + 3-5 bullet + ví dụ gắn thực tế "{teacher_notes}"
- KHÔNG thêm kiến thức không xuất hiện trong 'Nội dung SGK'.
- Xuất **duy nhất** JSON object:
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
            {"role": "system", "content": "Bạn là trợ lý chỉ trích dẫn nội dung đã cho, không bịa."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,  # Giảm sáng tạo để bám chặt nội dung
        response_format={"type": "json_object"}
    )
    return json.loads(resp.choices[0].message.content)

def rag_query(lesson_id: str, teacher_notes: str, k: int = 8) -> Tuple[dict, List[float], List[int]]:
    lesson = _get_lesson(lesson_id)
    q = f"{lesson['name']} {teacher_notes}".strip()
    qvec = np.array(embed_query(q), dtype="float32").reshape(1, -1)

    index, meta = _load_index_meta()
    num_chunks = len(meta.get("chunks", []))
    
    # Adjust k if metadata has fewer chunks than requested
    if num_chunks == 0:
        logger.error("No chunks found in metadata")
        raise ValueError("No data available. Please ingest documents first.")
    
    k = min(k, num_chunks)
    distances, indices = index.search(qvec, k)
    idxs = indices[0].tolist()
    dists = distances[0].tolist()
    
    # Filter out invalid indices that exceed metadata length
    valid_pairs = [(idx, dist) for idx, dist in zip(idxs, dists) if idx < num_chunks]
    valid_pairs.sort(key=lambda x: x[1])  # L2: nhỏ hơn = gần hơn
    idxs = [idx for idx, _ in valid_pairs]
    dists = [dist for _, dist in valid_pairs]
    
    # Ngưỡng "đủ gần": 0.30-0.35 cho ada-002 + L2
    THRESH = 0.35
    if not idxs or dists[0] > THRESH:
        logger.info(f"No relevant content found (best distance: {dists[0] if idxs else 'N/A'})")
        return {
            "sections": [],
            "note": "Không tìm thấy nội dung phù hợp trong SGK đã nạp.",
            "sources": []
        }, dists, idxs
    
    chunks = [meta["chunks"][i] for i in idxs[:5]]

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
