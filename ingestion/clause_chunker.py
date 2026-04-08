"""Clause-aware chunking for FIDIC-style construction contracts.

CONTRACT documents have structured clause numbering (e.g. "8.4.1 Contractor's
General Obligations") that must be preserved as section_ref so that downstream
citations can reference the clause directly. Other document types fall back to
paragraph/page-aware chunking.

Constants are imported from pipeline (single source of truth).
"""

from __future__ import annotations

import re
from typing import Iterable

import tiktoken

# Matches "8.4.1 " or "20.1 " at start of line — FIDIC-style clause numbering.
CLAUSE_PATTERN = re.compile(r"^(\d+\.[\d\.]*)\s+")

# Locked tokenizer — must match the one used to count for embeddings.
_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _detect_clause(line: str) -> str | None:
    """Return the clause number for a line, or None if it isn't a clause header."""
    match = CLAUSE_PATTERN.match(line.strip())
    if match:
        return match.group(1).rstrip(".")
    return None


def chunk_contract_pages(
    pages: list[dict],
    *,
    target_tokens: int,
    overlap_tokens: int,
    max_tokens: int,
    min_tokens: int,
) -> list[dict]:
    """Clause-aware chunking for CONTRACT documents.

    Strategy:
      - Walk lines page by page; track current clause number when we hit a header.
      - Accumulate lines into a buffer; flush at target_tokens, hard-flush at max_tokens.
      - Always flush at clause boundaries to keep chunks clause-pure when feasible.
      - Each emitted chunk carries page_number (first page it touches) and section_ref
        (current clause number at flush time).
      - Overlap: prepend the last `overlap_tokens` worth of text from the previous
        chunk so that retrieval can stitch context across the boundary.
    """
    chunks: list[dict] = []
    buffer: list[str] = []
    buffer_tokens = 0
    buffer_first_page: int | None = None
    current_clause: str | None = None
    last_overlap = ""
    chunk_index = 0

    def flush(force: bool) -> None:
        nonlocal buffer, buffer_tokens, buffer_first_page, last_overlap, chunk_index
        if not buffer:
            return
        text = "\n".join(buffer).strip()
        if not text:
            buffer = []
            buffer_tokens = 0
            buffer_first_page = None
            return
        token_count = _count_tokens(text)
        if not force and token_count < min_tokens:
            return
        chunks.append(
            {
                "chunk_index": chunk_index,
                "chunk_text": text,
                "page_number": buffer_first_page,
                "section_ref": current_clause,
                "token_count": token_count,
            }
        )
        chunk_index += 1
        # Build overlap from the tail of this chunk.
        tail_tokens = _ENCODING.encode(text)[-overlap_tokens:]
        last_overlap = _ENCODING.decode(tail_tokens) if overlap_tokens > 0 else ""
        buffer = [last_overlap] if last_overlap else []
        buffer_tokens = len(tail_tokens)
        buffer_first_page = None

    for page in pages:
        page_number = page["page_number"]
        for raw_line in page["text"].splitlines():
            line = raw_line.rstrip()
            if not line:
                continue

            new_clause = _detect_clause(line)
            if new_clause is not None:
                # Clause boundary — flush whatever we have so the previous clause
                # ends cleanly, then start the new clause.
                flush(force=True)
                current_clause = new_clause

            if buffer_first_page is None:
                buffer_first_page = page_number

            buffer.append(line)
            buffer_tokens += _count_tokens(line) + 1  # rough approximation

            if buffer_tokens >= target_tokens:
                flush(force=False)
            if buffer_tokens >= max_tokens:
                flush(force=True)

    flush(force=True)
    return chunks


def chunk_freeform_pages(
    pages: list[dict],
    *,
    target_tokens: int,
    overlap_tokens: int,
    max_tokens: int,
    min_tokens: int,
) -> list[dict]:
    """Paragraph/page-aware chunking for non-contract documents.

    No clause detection. Section_ref left None. page_number is the first page
    the chunk touches.
    """
    chunks: list[dict] = []
    buffer: list[str] = []
    buffer_tokens = 0
    buffer_first_page: int | None = None
    chunk_index = 0
    last_overlap = ""

    def flush(force: bool) -> None:
        nonlocal buffer, buffer_tokens, buffer_first_page, last_overlap, chunk_index
        if not buffer:
            return
        text = "\n\n".join(buffer).strip()
        if not text:
            buffer = []
            buffer_tokens = 0
            buffer_first_page = None
            return
        token_count = _count_tokens(text)
        if not force and token_count < min_tokens:
            return
        chunks.append(
            {
                "chunk_index": chunk_index,
                "chunk_text": text,
                "page_number": buffer_first_page,
                "section_ref": None,
                "token_count": token_count,
            }
        )
        chunk_index += 1
        tail_tokens = _ENCODING.encode(text)[-overlap_tokens:]
        last_overlap = _ENCODING.decode(tail_tokens) if overlap_tokens > 0 else ""
        buffer = [last_overlap] if last_overlap else []
        buffer_tokens = len(tail_tokens)
        buffer_first_page = None

    for page in pages:
        page_number = page["page_number"]
        # Split each page on blank lines into paragraphs.
        paragraphs: Iterable[str] = (p.strip() for p in re.split(r"\n\s*\n", page["text"]))
        for para in paragraphs:
            if not para:
                continue
            if buffer_first_page is None:
                buffer_first_page = page_number
            buffer.append(para)
            buffer_tokens += _count_tokens(para)
            if buffer_tokens >= target_tokens:
                flush(force=False)
            if buffer_tokens >= max_tokens:
                flush(force=True)

    flush(force=True)
    return chunks
