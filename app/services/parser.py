import fitz  # PyMuPDF
from pdf2image import convert_from_bytes
import pytesseract
from typing import List, Dict
from app.core.logger import get_logger
from app.core.config import FORCE_OCR

logger = get_logger(__name__)

def _has_text_layer(doc: fitz.Document) -> bool:
    pages = min(3, len(doc))
    for i in range(pages):
        if doc[i].get_text().strip():
            return True
    return False

def parse_pdf_bytes(pdf_bytes: bytes, lang: str = "vie", prefer_text: bool = True) -> List[Dict]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    try:
        should_text = prefer_text and _has_text_layer(doc) and not FORCE_OCR
        if should_text:
            logger.info("Parsing as TEXT layer")
            for i in range(len(doc)):
                page = doc[i]
                text = page.get_text("text")
                blocks = page.get_text("dict").get("blocks", [])
                pages.append({"page_num": i+1, "text": text, "blocks": blocks})
        else:
            logger.info("Parsing with OCR (Tesseract)")
            images = convert_from_bytes(pdf_bytes, dpi=300)
            for i, img in enumerate(images):
                txt = pytesseract.image_to_string(img, lang=lang)
                pages.append({"page_num": i+1, "text": txt, "blocks": []})
        return pages
    finally:
        doc.close()
