"""Thin wrapper around Ollama's HTTP API for chat operations."""

import json
from collections.abc import Generator

import httpx

from context_core.models import ChatMessage

# Models that are embedding-only and should not be used for chat
EMBEDDING_ONLY_MODELS = frozenset({
    "nomic-embed-text",
    "all-minilm",
    "mxbai-embed-large",
    "snowflake-arctic-embed",
    "bge-m3",
    "bge-large",
})

_TIMEOUT = httpx.Timeout(10.0, read=120.0)  # Long read timeout for generation


def list_models(base_url: str = "http://localhost:11434") -> list[dict]:
    """Fetch available models from Ollama."""
    resp = httpx.get(f"{base_url}/api/tags", timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("models", [])


def detect_chat_model(base_url: str = "http://localhost:11434") -> str | None:
    """Auto-detect the first available chat model (skipping embedding-only models)."""
    models = list_models(base_url)
    for model in models:
        name = model.get("name", "")
        # Strip tag suffix (e.g. "llama3:latest" -> "llama3")
        base_name = name.split(":")[0]
        if base_name not in EMBEDDING_ONLY_MODELS:
            return name
    return None


def chat_stream(
    base_url: str,
    model: str,
    messages: list[ChatMessage],
    temperature: float = 0.7,
) -> Generator[str, None, None]:
    """Stream chat response tokens from Ollama. Yields content strings."""
    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": True,
        "options": {"temperature": temperature},
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        with client.stream("POST", f"{base_url}/api/chat", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break


def chat(
    base_url: str,
    model: str,
    messages: list[ChatMessage],
    temperature: float = 0.7,
) -> str:
    """Non-streaming chat. Returns the full response text."""
    parts = list(chat_stream(base_url, model, messages, temperature))
    return "".join(parts)
