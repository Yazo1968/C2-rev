"""query_sessions CRUD (Task 4.4).

Sessions live in BigQuery. context_json holds the last 10 turns serialised
as a JSON array of {role, content} dicts. expires_at = started_at + 4 hours.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from google.cloud import bigquery

from config import DATASET, GCP_PROJECT

MAX_TURNS = 10
SESSION_TTL_HOURS = 4


def _bq() -> bigquery.Client:
    return bigquery.Client(project=GCP_PROJECT)


def create_session(project_id: str, user_id: str, domain: str) -> str:
    session_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    expires_at = started_at + timedelta(hours=SESSION_TTL_HOURS)
    rows = [{
        "session_id": session_id,
        "project_id": project_id,
        "user_id": user_id,
        "started_at": started_at.isoformat(),
        "last_active_at": started_at.isoformat(),
        "turn_count": 0,
        "domain": domain,
        "expires_at": expires_at.isoformat(),
        "context_json": "[]",
    }]
    errs = _bq().insert_rows_json(f"{GCP_PROJECT}.{DATASET}.query_sessions", rows)
    if errs:
        raise RuntimeError(f"create_session failed: {errs}")
    return session_id


def get_session_context(session_id: str) -> list[dict]:
    """Returns last MAX_TURNS turns. [] if session not found or expired."""
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("sid", "STRING", session_id),
    ])
    rows = list(
        _bq().query(
            f"""SELECT context_json, expires_at
                FROM `{GCP_PROJECT}.{DATASET}.query_sessions`
                WHERE session_id = @sid
                ORDER BY started_at DESC
                LIMIT 1""",
            job_config=job_config,
        ).result()
    )
    if not rows:
        return []
    row = rows[0]
    if row.expires_at and row.expires_at < datetime.now(timezone.utc):
        return []
    try:
        return json.loads(row.context_json or "[]")[-MAX_TURNS:]
    except json.JSONDecodeError:
        return []


def update_session_context(session_id: str, turn: dict) -> None:
    """Append a turn, trim to MAX_TURNS, bump turn_count and last_active_at."""
    context = get_session_context(session_id)
    context.append(turn)
    context = context[-MAX_TURNS:]
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("sid", "STRING", session_id),
        bigquery.ScalarQueryParameter("ctx", "STRING", json.dumps(context)),
    ])
    _bq().query(
        f"""UPDATE `{GCP_PROJECT}.{DATASET}.query_sessions`
            SET context_json = @ctx,
                last_active_at = CURRENT_TIMESTAMP(),
                turn_count = turn_count + 1
            WHERE session_id = @sid""",
        job_config=job_config,
    ).result()
