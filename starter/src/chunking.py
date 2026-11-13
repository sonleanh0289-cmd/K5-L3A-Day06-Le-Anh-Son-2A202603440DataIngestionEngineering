"""Fixed-size and structure-aware (paragraph) chunking strategies."""
from __future__ import annotations

from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Split normalized page text into overlapping fixed-size character windows."""
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")

    text = page.text.strip()
    if not text:
        return []

    chunks: list[Chunk] = []
    step = size - overlap
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + size, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(
                Chunk(
                    chunk_id=f"{page.document_id}::p{page.page:03d}::fixed::{idx:03d}",
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=piece,
                    metadata={**page.metadata, "chunk_index": idx, "strategy_type": "fixed_size"},
                )
            )
            idx += 1
        if end >= len(text):
            break
        start += step
    return chunks


def _split_oversized(paragraph: str, max_size: int) -> list[str]:
    """Split a paragraph exceeding max_size along sentence or word boundaries."""
    parts: list[str] = []
    remaining = paragraph.strip()
    while len(remaining) > max_size:
        cut = remaining.rfind(". ", 0, max_size)
        if cut < max_size // 3:
            cut = remaining.rfind("; ", 0, max_size)
        if cut < max_size // 3:
            cut = remaining.rfind(" ", 0, max_size)
        if cut <= 0:
            cut = max_size
        else:
            cut += 1  # include punctuation/space boundary
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def by_paragraph(page: DocumentPage, max_size: int = 600) -> list[Chunk]:
    """Group logical paragraphs up to max_size, splitting oversized paragraphs cleanly."""
    if max_size <= 0:
        raise ValueError("max_size must be positive")

    raw_paragraphs = [p.strip() for p in page.text.split("\n\n") if p.strip()]
    units: list[str] = []
    for para in raw_paragraphs:
        if len(para) <= max_size:
            units.append(para)
        else:
            units.extend(_split_oversized(para, max_size))

    grouped: list[str] = []
    current = ""
    for unit in units:
        if not current:
            current = unit
        elif len(current) + 2 + len(unit) <= max_size:
            current = f"{current}\n\n{unit}"
        else:
            grouped.append(current)
            current = unit
    if current:
        grouped.append(current)

    return [
        Chunk(
            chunk_id=f"{page.document_id}::p{page.page:03d}::para::{idx:03d}",
            document_id=page.document_id,
            source=page.source,
            page=page.page,
            text=text_piece,
            metadata={**page.metadata, "chunk_index": idx, "strategy_type": "by_paragraph"},
        )
        for idx, text_piece in enumerate(grouped)
    ]
