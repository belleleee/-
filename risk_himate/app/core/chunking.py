"""Text chunking utilities."""

from __future__ import annotations

import re

from .schemas import TextChunk


def chunk_text(raw_text: str, max_chars: int = 220) -> list[TextChunk]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", raw_text) if part.strip()]
    if not paragraphs:
        paragraphs = [raw_text.strip()] if raw_text.strip() else []

    chunks: list[TextChunk] = []
    chunk_index = 0

    for paragraph_index, paragraph in enumerate(paragraphs):
        sentences = [part.strip() for part in re.split(r"(?<=[。！？；;.!?])", paragraph) if part.strip()]
        if not sentences:
            sentences = [paragraph]

        buffer = ""
        for sentence in sentences:
            proposed = f"{buffer}{sentence}".strip()
            if buffer and len(proposed) > max_chars:
                chunks.append(
                    TextChunk(
                        chunk_id=f"chunk-{chunk_index:03d}",
                        text=buffer.strip(),
                        source_type="document",
                        paragraph_index=paragraph_index,
                    )
                )
                chunk_index += 1
                buffer = sentence
            else:
                buffer = proposed

        if buffer:
            chunks.append(
                TextChunk(
                    chunk_id=f"chunk-{chunk_index:03d}",
                    text=buffer.strip(),
                    source_type="document",
                    paragraph_index=paragraph_index,
                )
            )
            chunk_index += 1

    return chunks
