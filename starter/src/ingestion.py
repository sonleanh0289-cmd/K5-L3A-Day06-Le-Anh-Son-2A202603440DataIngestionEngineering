"""Read and normalize source PDF data while preserving page and chapter traceability."""
from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage

logger = logging.getLogger(__name__)

_CHAPTER_RE = re.compile(r"Chương\s+([IVXLC]+)\b")


def normalize_text(text: str) -> str:
    """Normalize Unicode (NFC), fix word-per-line PDF artifacts, and restore legal structure breaks."""
    text = unicodedata.normalize("NFC", text or "")
    # Collapse pypdf word-per-line breaks into single spaces
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    text = re.sub(r"[ \t]+", " ", text).strip()

    # Restore paragraph breaks before major legal structure markers for structure-aware chunking
    text = re.sub(r"\s+(Chương\s+[IVXLC]+\b)", r"\n\n\1", text)
    text = re.sub(r"\s+(Điều\s+\d+\.)", r"\n\n\1", text)
    text = re.sub(r"([.;:])\s+(\d+\.\s+)", r"\1\n\n\2", text)
    return text.strip()


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract each physical page, normalize text, log empty pages, and track current chapter."""
    if not path.exists():
        raise FileNotFoundError(f"Corpus PDF not found: {path}")

    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    current_chapter = "Chương I"
    empty_pages: list[int] = []

    for page_num, pdf_page in enumerate(reader.pages, start=1):
        try:
            raw_text = pdf_page.extract_text() or ""
        except Exception as exc:
            logger.error("Failed to extract page %d of %s: %s", page_num, path, exc)
            empty_pages.append(page_num)
            continue

        cleaned = normalize_text(raw_text)
        if not cleaned:
            logger.warning("Empty text on page %d of %s", page_num, path)
            empty_pages.append(page_num)
            continue

        # Update current chapter on actual chapter headings (including page-end headings like "Chương II" on p.7)
        matches = _CHAPTER_RE.findall(cleaned)
        heading_matches = re.findall(
            r"(?:^|\n)(Chương\s+[IVXLC]+)(?:\s+[A-ZĐÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴ]{2,}|\s*$)",
            cleaned,
        )
        if heading_matches:
            current_chapter = heading_matches[-1]
        elif page_num == 1 and matches:
            current_chapter = f"Chương {matches[0]}"

        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=page_num,
                text=cleaned,
                metadata={
                    "chapter": current_chapter,
                    "document_type": "luat",
                    "year": 2024,
                    "language": "vi",
                    "char_count": len(cleaned),
                },
            )
        )

    if empty_pages:
        logger.info("Empty/skipped pages in %s: %s", path.name, empty_pages)
    return pages
