"""FastAPI entrypoint for the c2-ingestion Cloud Run service.

Single endpoint: POST /ingest. Synchronous — Cloud Run timeout is 900s
(set in deploy.sh) which is enough headroom for one document.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from pipeline import ingest_document

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="c2-ingestion")


class IngestRequest(BaseModel):
    project_id: str = Field(..., description="Owning project_id, or 'GLOBAL_STANDARDS' for L2B")
    layer: str = Field(..., description="L1, L2A, or L2B")
    document_type: str = Field(..., description="CONTRACT, CORRESPONDENCE, PROGRAMME, POLICY, STANDARD, DRAWING")
    gcs_uri: str = Field(..., description="gs://bucket/path/file.pdf")
    file_name: str


class IngestResponse(BaseModel):
    document_id: str
    chunk_count: int
    processing_method: str
    run_id: str


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest) -> IngestResponse:
    try:
        result = ingest_document(
            project_id=req.project_id,
            layer=req.layer,
            document_type=req.document_type,
            gcs_uri=req.gcs_uri,
            file_name=req.file_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return IngestResponse(**result)
