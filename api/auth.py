"""Firebase JWT verification + project_members authorisation (Task 6.1).

This is the only authorization layer. BigQuery RLS is not used because
SESSION_USER() returns the service account, not the Firebase UID.

The cache is intentionally short-lived: 5 minutes. We accept stale reads
for that window in exchange for not hitting BigQuery on every request.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import firebase_admin
from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth as firebase_auth
from google.cloud import bigquery

from config import GCP_PROJECT, DATASET

# Initialise the Firebase Admin SDK once at import time. On Cloud Run the
# service account credentials are picked up automatically — no key file.
if not firebase_admin._apps:
    firebase_admin.initialize_app()


@dataclass
class AuthUser:
    uid: str
    email: Optional[str]


def verify_firebase_jwt(authorization: str = Header(default="")) -> AuthUser:
    """FastAPI dependency. Extracts and verifies a Firebase ID token.

    Header format: `Authorization: Bearer <id_token>`.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization[len("Bearer ") :].strip()
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception as exc:  # noqa: BLE001 — surface verifier errors as 401
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}") from exc
    return AuthUser(uid=decoded["uid"], email=decoded.get("email"))


# --- project_members cache ---------------------------------------------

# Manual TTL cache (functools.lru_cache has no expiry).
_CACHE_TTL_SECONDS = 300
_PROJECT_CACHE: dict[str, tuple[float, list[str]]] = {}


def _bq() -> bigquery.Client:
    return bigquery.Client(project=GCP_PROJECT)


def get_user_project_ids(user_id: str) -> list[str]:
    """Returns project_ids the user can access. Cached for 5 minutes."""
    now = time.time()
    cached = _PROJECT_CACHE.get(user_id)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("uid", "STRING", user_id)]
    )
    rows = _bq().query(
        f"SELECT project_id FROM `{GCP_PROJECT}.{DATASET}.project_members` WHERE user_id = @uid",
        job_config=job_config,
    ).result()
    project_ids = [row.project_id for row in rows]
    _PROJECT_CACHE[user_id] = (now, project_ids)
    return project_ids


def user_has_project_access(user_id: str, project_id: str) -> bool:
    # GLOBAL_STANDARDS (L2B reference layer) is open to every authenticated user.
    if project_id == "GLOBAL_STANDARDS":
        return True
    return project_id in get_user_project_ids(user_id)


def require_project_access(user: AuthUser, project_id: str) -> None:
    if not user_has_project_access(user.uid, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this project")
