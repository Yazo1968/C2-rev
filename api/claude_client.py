"""Claude on Vertex AI streaming wrapper.

Uses anthropic[vertex]. Region and model id are loaded from env (Secret
Manager). The model id is validated in config.py to refuse @latest.
"""

from __future__ import annotations

from typing import AsyncIterator

from anthropic import AsyncAnthropicVertex

from config import CLAUDE_MODEL_ID, GCP_PROJECT, REGION_VERTEX

_client = AsyncAnthropicVertex(region=REGION_VERTEX, project_id=GCP_PROJECT)


async def stream_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    history: list[dict] | None = None,
    max_tokens: int = 4096,
) -> AsyncIterator[str]:
    """Yield text deltas as they arrive from Claude.

    history is a list of {role, content} dicts representing prior turns
    (already trimmed by sessions.update_session_context).
    """
    messages: list[dict] = list(history or [])
    messages.append({"role": "user", "content": user_prompt})

    async with _client.messages.stream(
        model=CLAUDE_MODEL_ID,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


def model_id() -> str:
    return CLAUDE_MODEL_ID
