"""Write audit log entries via the c2-toolbox MCP service.

We deliberately route writes through Toolbox (rather than calling BigQuery
directly from c2-api) so that the audit path matches the verification
path Claude Chat uses. If Toolbox is down, audit writes fail loudly —
that's acceptable: we treat audit failures as build-stoppers.
"""

from __future__ import annotations

import logging
import uuid

import google.auth
import google.auth.transport.requests
import google.oauth2.id_token
import httpx

from config import TOOLBOX_URL

logger = logging.getLogger(__name__)


def _id_token_for(audience: str) -> str:
    """Mint an ID token for an authenticated Cloud Run -> Cloud Run call.

    On Cloud Run, fetch_id_token uses the metadata server, which is the
    correct path for service-to-service auth.
    """
    auth_req = google.auth.transport.requests.Request()
    return google.oauth2.id_token.fetch_id_token(auth_req, audience)


async def write_audit_log(
    *,
    project_id: str,
    session_id: str,
    user_id: str,
    user_email: str,
    action: str,
    domain: str,
    query_text: str,
    chunks_retrieved: int,
    model_used: str,
    latency_ms: int,
) -> None:
    if not TOOLBOX_URL:
        logger.warning("TOOLBOX_URL not set — skipping audit write")
        return

    payload = {
        "log_id": str(uuid.uuid4()),
        "project_id": project_id,
        "session_id": session_id,
        "user_id": user_id,
        "user_email": user_email,
        "action": action,
        "domain": domain,
        "query_text": query_text,
        "chunks_retrieved": chunks_retrieved,
        "model_used": model_used,
        "latency_ms": latency_ms,
    }

    try:
        token = _id_token_for(TOOLBOX_URL)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to mint ID token for toolbox")
        raise

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{TOOLBOX_URL}/api/tool/write_audit_log/invoke",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        resp.raise_for_status()
