"""Two-path PDF ingestion pipeline (Task 3.1).

Path A — DIGITAL: PyMuPDF native extraction. Stays GCC-resident. Flagged
GCC_NATIVE in the documents table.

Path B — SCANNED: Document AI OCR via the EU endpoint (no GCC option for
DocAI). Flagged EXTERNAL_OCR — UI surfaces a banner before upload.

After extraction:
  text -> chunk_text() -> embed (Vertex AI text-embedding-004, 768 dims)
       -> insert documents row + chunks rows in BigQuery.

The 768-dim assertion is non-negotiable: any silent dimension drift would
break VECTOR_SEARCH and the failure would only surface at query time.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Iterable

import fitz  # PyMuPDF
from google.cloud import bigquery, documentai, storage
from vertexai.language_models import TextEmbeddingModel

from clause_chunker import chunk_contract_pages, chunk_freeform_pages

logger = logging.getLogger(__name__)

# --- Locked constants (CLAUDE.md) ---------------------------------------
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMS = 768
CHUNK_TARGET_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50
CHUNK_MAX_TOKENS = 600
CHUNK_MIN_TOKENS = 50
EMBED_BATCH_SIZE = 5  # Vertex AI quota — do not raise without measuring

GCP_PROJECT = os.environ.get("GCP_PROJECT", "c2-intelligence")
DATASET = "c2_warehouse"
DOCAI_LOCATION = "eu"  # Document AI is not in GCC; locked to eu endpoint
DOCAI_PROCESSOR_ID = os.environ.get("DOCAI_PROCESSOR_ID")  # set in Secret Manager

# Detection threshold: a "DIGITAL" PDF should yield non-trivial text from
# fitz on its first page. Below this we route to OCR.
DIGITAL_TEXT_THRESHOLD_CHARS = 50


# --- GCS helpers --------------------------------------------------------

def _parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Not a GCS URI: {gcs_uri}")
    bucket, _, blob = gcs_uri[len("gs://") :].partition("/")
    if not bucket or not blob:
        raise ValueError(f"Malformed GCS URI: {gcs_uri}")
    return bucket, blob


def _download_to_tempfile(gcs_uri: str) -> str:
    bucket_name, blob_name = _parse_gcs_uri(gcs_uri)
    client = storage.Client(project=GCP_PROJECT)
    blob = client.bucket(bucket_name).blob(blob_name)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    blob.download_to_filename(path)
    return path


# --- PDF type detection -------------------------------------------------

def detect_pdf_type(gcs_uri: str) -> str:
    """Returns 'DIGITAL' or 'SCANNED'.

    Heuristic: download, open with fitz, check first page text length.
    Cheap because we only read one page.
    """
    path = _download_to_tempfile(gcs_uri)
    try:
        with fitz.open(path) as doc:
            if doc.page_count == 0:
                return "SCANNED"
            text = doc[0].get_text("text") or ""
            return "DIGITAL" if len(text.strip()) >= DIGITAL_TEXT_THRESHOLD_CHARS else "SCANNED"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# --- Path A: PyMuPDF (GCC-native) ---------------------------------------

def extract_text_pymupdf(gcs_uri: str) -> list[dict]:
    """Extract text page by page using PyMuPDF. Stays in GCC."""
    path = _download_to_tempfile(gcs_uri)
    try:
        pages: list[dict] = []
        with fitz.open(path) as doc:
            for i, page in enumerate(doc, start=1):
                pages.append({"page_number": i, "text": page.get_text("text") or ""})
        return pages
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# --- Path B: Document AI (EU OCR) ---------------------------------------

def extract_text_documentai(gcs_uri: str, project_id: str) -> list[dict]:
    """Extract text via Document AI OCR. Uses the eu regional endpoint
    explicitly so the request never lands in a US region.

    Requires DOCAI_PROCESSOR_ID env var (Task 3.2).
    """
    if not DOCAI_PROCESSOR_ID:
        raise RuntimeError("DOCAI_PROCESSOR_ID is not set")

    client_options = {"api_endpoint": f"{DOCAI_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=client_options)
    name = client.processor_path(project_id, DOCAI_LOCATION, DOCAI_PROCESSOR_ID)

    bucket_name, blob_name = _parse_gcs_uri(gcs_uri)
    storage_client = storage.Client(project=project_id)
    pdf_bytes = storage_client.bucket(bucket_name).blob(blob_name).download_as_bytes()

    raw_document = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    result = client.process_document(request=request)
    document = result.document

    pages: list[dict] = []
    for i, page in enumerate(document.pages, start=1):
        # Reconstruct page text from layout text anchors.
        text = ""
        if page.layout and page.layout.text_anchor and page.layout.text_anchor.text_segments:
            for segment in page.layout.text_anchor.text_segments:
                start = int(segment.start_index) if segment.start_index else 0
                end = int(segment.end_index) if segment.end_index else 0
                text += document.text[start:end]
        pages.append({"page_number": i, "text": text})
    return pages


# --- Chunking dispatcher ------------------------------------------------

def chunk_text(pages: list[dict], document_type: str) -> list[dict]:
    """Dispatch to clause-aware (CONTRACT) or paragraph (everything else)."""
    kwargs = dict(
        target_tokens=CHUNK_TARGET_TOKENS,
        overlap_tokens=CHUNK_OVERLAP_TOKENS,
        max_tokens=CHUNK_MAX_TOKENS,
        min_tokens=CHUNK_MIN_TOKENS,
    )
    if document_type == "CONTRACT":
        return chunk_contract_pages(pages, **kwargs)
    return chunk_freeform_pages(pages, **kwargs)


# --- Embedding ----------------------------------------------------------

def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Embed in batches of 5 (Vertex AI quota). Asserts every vector is 768d."""
    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    out: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        results = model.get_embeddings(batch)
        for r in results:
            values = list(r.values)
            if len(values) != EMBEDDING_DIMS:
                raise RuntimeError(
                    f"Embedding dim mismatch: expected {EMBEDDING_DIMS}, got {len(values)}"
                )
            out.append(values)
    return out


# --- BigQuery writes ----------------------------------------------------

def _bq() -> bigquery.Client:
    return bigquery.Client(project=GCP_PROJECT)


def _insert_run(run_id: str, project_id: str, gcs_uri: str) -> None:
    rows = [{
        "run_id": run_id,
        "project_id": project_id,
        "gcs_uri": gcs_uri,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "RUNNING",
    }]
    _bq().insert_rows_json(f"{GCP_PROJECT}.{DATASET}.ingestion_runs", rows)


def _finalise_run(
    run_id: str,
    *,
    document_id: str,
    chunks_created: int,
    processing_method: str,
    status: str,
    error: str | None = None,
) -> None:
    query = f"""
    UPDATE `{GCP_PROJECT}.{DATASET}.ingestion_runs`
    SET completed_at = CURRENT_TIMESTAMP(),
        status = @status,
        document_id = @document_id,
        chunks_created = @chunks_created,
        processing_method = @processing_method,
        error_message = @error
    WHERE run_id = @run_id
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("status", "STRING", status),
        bigquery.ScalarQueryParameter("document_id", "STRING", document_id),
        bigquery.ScalarQueryParameter("chunks_created", "INT64", chunks_created),
        bigquery.ScalarQueryParameter("processing_method", "STRING", processing_method),
        bigquery.ScalarQueryParameter("error", "STRING", error),
        bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
    ])
    _bq().query(query, job_config=job_config).result()


# --- Public entry point -------------------------------------------------

def ingest_document(
    project_id: str,
    layer: str,
    document_type: str,
    gcs_uri: str,
    file_name: str,
) -> dict:
    """Ingest a single PDF end-to-end.

    Returns: {document_id, chunk_count, processing_method, run_id}.
    Raises and marks the ingestion_runs row FAILED on any step failure.
    """
    run_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    _insert_run(run_id, project_id, gcs_uri)

    try:
        # Step 1: Detect PDF type
        pdf_type = detect_pdf_type(gcs_uri)
        processing_method = "GCC_NATIVE" if pdf_type == "DIGITAL" else "EXTERNAL_OCR"
        logger.info("ingest %s detected pdf_type=%s", gcs_uri, pdf_type)

        # Step 2: Extract text
        if pdf_type == "DIGITAL":
            pages = extract_text_pymupdf(gcs_uri)
        else:
            pages = extract_text_documentai(gcs_uri, GCP_PROJECT)

        page_count = len(pages)

        # Step 3: Chunk
        chunks = chunk_text(pages, document_type)
        if not chunks:
            raise RuntimeError("No chunks produced from extracted text")

        # Step 4: Embed (batched)
        texts = [c["chunk_text"] for c in chunks]
        embeddings = generate_embeddings(texts)
        assert len(embeddings) == len(chunks)

        # Step 5: documents row
        bq = _bq()
        doc_row = [{
            "document_id": document_id,
            "project_id": project_id,
            "layer": layer,
            "document_type": document_type,
            "file_name": file_name,
            "gcs_uri": gcs_uri,
            "page_count": page_count,
            "processing_method": processing_method,
            "ingestion_run_id": run_id,
            "status": "ACTIVE",
        }]
        errs = bq.insert_rows_json(f"{GCP_PROJECT}.{DATASET}.documents", doc_row)
        if errs:
            raise RuntimeError(f"documents insert failed: {errs}")

        # Step 6: chunks rows
        rows = [
            {
                "chunk_id": str(uuid.uuid4()),
                "document_id": document_id,
                "project_id": project_id,
                "layer": layer,
                "chunk_index": c["chunk_index"],
                "chunk_text": c["chunk_text"],
                "page_number": c["page_number"],
                "section_ref": c.get("section_ref"),
                "embedding": embeddings[i],
                "token_count": c["token_count"],
            }
            for i, c in enumerate(chunks)
        ]
        # BigQuery streaming insert max 500 rows / request — chunk if huge.
        for start in range(0, len(rows), 500):
            batch = rows[start : start + 500]
            errs = bq.insert_rows_json(f"{GCP_PROJECT}.{DATASET}.chunks", batch)
            if errs:
                raise RuntimeError(f"chunks insert failed: {errs}")

        _finalise_run(
            run_id,
            document_id=document_id,
            chunks_created=len(chunks),
            processing_method=processing_method,
            status="COMPLETE",
        )

        return {
            "document_id": document_id,
            "chunk_count": len(chunks),
            "processing_method": processing_method,
            "run_id": run_id,
        }

    except Exception as exc:
        logger.exception("ingestion failed run_id=%s", run_id)
        _finalise_run(
            run_id,
            document_id=document_id,
            chunks_created=0,
            processing_method="",
            status="FAILED",
            error=str(exc),
        )
        raise
