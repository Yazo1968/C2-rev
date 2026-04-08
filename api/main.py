"""c2-api FastAPI app (Task 4.5).

Endpoints:
  POST /api/v1/query                       — SSE-streamed agent response
  POST /api/v1/ingest                      — proxy to c2-ingestion
  GET  /api/v1/projects                    — projects accessible to caller
  GET  /api/v1/project/{project_id}/documents
  GET  /api/v1/audit/{project_id}

All endpoints require a Firebase ID token. Project authorisation is checked
via api/auth.py against the project_members table.

The /query endpoint is the only streaming endpoint. We use sse-starlette so
the response interleaves token deltas with a final `done` event that the
client uses to flush citations and trigger audit log write.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery
import httpx
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

import claude_client
from audit import write_audit_log
from auth import AuthUser, require_project_access, get_user_project_ids, verify_firebase_jwt
from config import CORS_ALLOWED_ORIGINS, DATASET, GCP_PROJECT
from embeddings import embed_query
from prompts import AGENT_SYSTEM_PROMPTS, build_grounded_prompt
from routing import route_query
from sessions import create_session, get_session_context, update_session_context
from vector_search import vector_search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("c2-api")

app = FastAPI(title="c2-api", version="1.0")

if CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )


# --- Schemas ------------------------------------------------------------

class QueryRequest(BaseModel):
    project_id: str
    query: str
    session_id: str | None = None
    layer_filter: str = Field(default="ALL", description="ALL, L1, L2A")
    top_k: int = Field(default=8, ge=1, le=20)


class IngestRequest(BaseModel):
    project_id: str
    layer: str
    document_type: str
    gcs_uri: str
    file_name: str


# --- Helpers ------------------------------------------------------------

def _bq() -> bigquery.Client:
    return bigquery.Client(project=GCP_PROJECT)


# --- Endpoints ----------------------------------------------------------

@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/api/v1/query")
async def query(req: QueryRequest, user: AuthUser = Depends(verify_firebase_jwt)) -> EventSourceResponse:
    require_project_access(user, req.project_id)

    domains = route_query(req.query)
    primary_domain = domains[0]
    system_prompt = AGENT_SYSTEM_PROMPTS[primary_domain]

    started = time.perf_counter()
    query_embedding = embed_query(req.query)
    chunks = vector_search(
        query_embedding,
        project_id=req.project_id,
        layer_filter=req.layer_filter,
        top_k=req.top_k,
    )
    user_prompt = build_grounded_prompt(req.query, chunks, primary_domain)

    # Session: create if missing, otherwise pull recent history.
    session_id = req.session_id or create_session(req.project_id, user.uid, primary_domain)
    history = get_session_context(session_id) if req.session_id else []

    citations = [
        {
            "chunk_id": c["chunk_id"],
            "file_name": c.get("file_name"),
            "page_number": c.get("page_number"),
            "section_ref": c.get("section_ref"),
            "layer": c.get("layer"),
            "document_id": c.get("document_id"),
            "distance": c.get("distance"),
        }
        for c in chunks
    ]

    async def generate():
        # First event: metadata so the client can render badges and citations.
        yield {
            "event": "meta",
            "data": _json({
                "session_id": session_id,
                "domain": primary_domain,
                "domains": domains,
                "citations": citations,
                "model": claude_client.model_id(),
            }),
        }

        full_response_chunks: list[str] = []
        try:
            async for delta in claude_client.stream_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                history=history,
            ):
                full_response_chunks.append(delta)
                yield {"event": "token", "data": delta}
        except Exception as exc:  # noqa: BLE001
            logger.exception("stream failed")
            yield {"event": "error", "data": str(exc)}
            return

        full_response = "".join(full_response_chunks)
        latency_ms = int((time.perf_counter() - started) * 1000)

        # Persist the turn to the session context.
        try:
            update_session_context(session_id, {"role": "user", "content": req.query})
            update_session_context(session_id, {"role": "assistant", "content": full_response})
        except Exception:  # noqa: BLE001
            logger.exception("session update failed")

        # Audit write — must succeed; failures are visible to the operator.
        try:
            await write_audit_log(
                project_id=req.project_id,
                session_id=session_id,
                user_id=user.uid,
                user_email=user.email or "",
                action="QUERY",
                domain=primary_domain.upper(),
                query_text=req.query,
                chunks_retrieved=len(chunks),
                model_used=claude_client.model_id(),
                latency_ms=latency_ms,
            )
        except Exception:  # noqa: BLE001
            logger.exception("audit write failed")

        yield {"event": "done", "data": _json({"latency_ms": latency_ms})}

    return EventSourceResponse(generate())


@app.post("/api/v1/ingest")
async def ingest(req: IngestRequest, user: AuthUser = Depends(verify_firebase_jwt)) -> dict:
    require_project_access(user, req.project_id)
    # Forward to c2-ingestion. Both services run in the same project so we
    # can mint an ID token for service-to-service auth.
    from audit import _id_token_for  # local import keeps top-level deps lean
    import os
    ingestion_url = os.environ.get("INGESTION_URL", "")
    if not ingestion_url:
        raise HTTPException(status_code=503, detail="INGESTION_URL not configured")
    token = _id_token_for(ingestion_url)
    async with httpx.AsyncClient(timeout=900.0) as client:
        resp = await client.post(
            f"{ingestion_url}/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json=req.model_dump(),
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


@app.get("/api/v1/projects")
def get_projects(user: AuthUser = Depends(verify_firebase_jwt)) -> dict:
    project_ids = get_user_project_ids(user.uid)
    if not project_ids:
        return {"projects": []}
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ArrayQueryParameter("ids", "STRING", project_ids),
    ])
    rows = _bq().query(
        f"""SELECT project_id, project_name, client_name, contract_type, jurisdiction
            FROM `{GCP_PROJECT}.{DATASET}.projects`
            WHERE project_id IN UNNEST(@ids) AND is_active = TRUE
            ORDER BY project_name""",
        job_config=job_config,
    ).result()
    return {"projects": [dict(row) for row in rows]}


@app.get("/api/v1/project/{project_id}/documents")
def get_documents(project_id: str, user: AuthUser = Depends(verify_firebase_jwt)) -> dict:
    require_project_access(user, project_id)
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("pid", "STRING", project_id),
    ])
    rows = _bq().query(
        f"""SELECT document_id, layer, document_type, file_name,
                   page_count, processing_method, ingested_at
            FROM `{GCP_PROJECT}.{DATASET}.documents`
            WHERE project_id = @pid AND status = 'ACTIVE'
            ORDER BY layer, document_type, file_name""",
        job_config=job_config,
    ).result()
    return {"documents": [dict(row) for row in rows]}


@app.get("/api/v1/audit/{project_id}")
def get_audit_log(project_id: str, user: AuthUser = Depends(verify_firebase_jwt), limit: int = 200) -> dict:
    require_project_access(user, project_id)
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("pid", "STRING", project_id),
        bigquery.ScalarQueryParameter("lim", "INT64", limit),
    ])
    rows = _bq().query(
        f"""SELECT log_id, session_id, user_email, action, domain,
                   query_text, chunks_retrieved, model_used, latency_ms, logged_at
            FROM `{GCP_PROJECT}.{DATASET}.audit_log`
            WHERE project_id = @pid
            ORDER BY logged_at DESC
            LIMIT @lim""",
        job_config=job_config,
    ).result()
    return {"entries": [dict(row) for row in rows]}


# --- Internal ----------------------------------------------------------

def _json(obj: dict) -> str:
    import json
    return json.dumps(obj, default=str)
