"""Vector search via the BigQuery Python client (Task 4.1).

This is the reason MCP Toolbox cannot host vector search: tools.yaml cannot
parameterise an ARRAY<FLOAT64> embedding literal. We build the SQL string
with the embedding inlined as a literal and pass scalar parameters for the
rest. The embedding values are floats produced by Vertex AI — no injection
risk — but we still validate the dimension before interpolating.

The query has two CTEs:
  project_results  — top_k chunks scoped to (project_id, layer_filter), excluding L2B
  standards_results — top 4 chunks from GLOBAL_STANDARDS / L2B (always included)

Both CTEs join `documents` to surface file_name + document_type and filter
status='ACTIVE' so superseded/deleted documents never enter retrieval.
"""

from __future__ import annotations

from google.cloud import bigquery

from config import DATASET, EMBEDDING_DIMS, GCP_PROJECT


def _embedding_literal(embedding: list[float]) -> str:
    if len(embedding) != EMBEDDING_DIMS:
        raise ValueError(f"Embedding must be {EMBEDDING_DIMS}-d, got {len(embedding)}")
    # Float repr is finite ASCII — no injection vector. Validation above
    # guarantees we're working with floats only.
    return "[" + ",".join(repr(float(v)) for v in embedding) + "]"


def vector_search(
    query_embedding: list[float],
    project_id: str,
    layer_filter: str = "ALL",
    top_k: int = 8,
) -> list[dict]:
    """Returns top_k project chunks merged with top-4 GLOBAL_STANDARDS chunks,
    sorted by ascending cosine distance, joined with documents for citations.
    """
    bq = bigquery.Client(project=GCP_PROJECT)
    embedding_literal = _embedding_literal(query_embedding)

    query = f"""
    WITH project_results AS (
      SELECT
        base.chunk_id, base.chunk_text, base.layer, base.page_number,
        base.section_ref, base.document_id, base.project_id, distance
      FROM VECTOR_SEARCH(
        TABLE `{GCP_PROJECT}.{DATASET}.chunks`,
        'embedding',
        (SELECT {embedding_literal} AS embedding),
        top_k => @top_k,
        distance_type => 'COSINE'
      )
      WHERE base.project_id = @project_id
        AND base.layer != 'L2B'
        AND (@layer_filter = 'ALL' OR base.layer = @layer_filter)
    ),
    standards_results AS (
      SELECT
        base.chunk_id, base.chunk_text, base.layer, base.page_number,
        base.section_ref, base.document_id, base.project_id, distance
      FROM VECTOR_SEARCH(
        TABLE `{GCP_PROJECT}.{DATASET}.chunks`,
        'embedding',
        (SELECT {embedding_literal} AS embedding),
        top_k => 4,
        distance_type => 'COSINE'
      )
      WHERE base.project_id = 'GLOBAL_STANDARDS'
        AND base.layer = 'L2B'
    )
    SELECT
      r.chunk_id, r.chunk_text, r.layer, r.page_number, r.section_ref,
      r.document_id, r.project_id, r.distance,
      d.file_name, d.document_type
    FROM (SELECT * FROM project_results UNION ALL SELECT * FROM standards_results) r
    JOIN `{GCP_PROJECT}.{DATASET}.documents` d ON r.document_id = d.document_id
    WHERE d.status = 'ACTIVE'
    ORDER BY r.distance ASC
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("project_id", "STRING", project_id),
            bigquery.ScalarQueryParameter("layer_filter", "STRING", layer_filter),
            bigquery.ScalarQueryParameter("top_k", "INT64", top_k),
        ]
    )
    rows = bq.query(query, job_config=job_config).result()
    return [dict(row) for row in rows]
