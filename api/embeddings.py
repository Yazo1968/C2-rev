"""Query embedding helper. Mirrors ingestion/pipeline.py constants exactly."""

from __future__ import annotations

from vertexai.language_models import TextEmbeddingModel

from config import EMBEDDING_DIMS, EMBEDDING_MODEL


def embed_query(text: str) -> list[float]:
    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    result = model.get_embeddings([text])
    embedding = list(result[0].values)
    if len(embedding) != EMBEDDING_DIMS:
        raise RuntimeError(
            f"Expected {EMBEDDING_DIMS} dims, got {len(embedding)}"
        )
    return embedding
