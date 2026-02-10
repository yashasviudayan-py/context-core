"""RAG pipeline: retrieve vault context and query Ollama LLM."""

from collections.abc import Generator

from context_core.config import VaultConfig, DEFAULT_CONFIG
from context_core.models import ChatMessage, ChatResponse, SearchResult
from context_core.search import search_vault
from context_core.vault import Vault
from context_core import ollama_client

SYSTEM_PROMPT = (
    "You are The Oracle, a helpful AI assistant with access to a personal knowledge vault.\n"
    "Use the following context from the vault to answer the user's question.\n"
    "If the context doesn't contain relevant information, say so and answer from "
    "your general knowledge.\n"
    "Always cite which context sources were most relevant."
)


def format_context(results: list[SearchResult], max_chars: int = 8000) -> str:
    """Format search results into a numbered context block within a character budget."""
    if not results:
        return "(No relevant context found in the vault.)"

    parts = []
    chars_used = 0
    for i, r in enumerate(results, 1):
        source = r.metadata.get("source_type", "unknown")
        score = f"{r.similarity:.3f}"
        file_path = r.metadata.get("file_path", "")

        header = f"[{i}] Score: {score} | Source: {source}"
        if file_path:
            header += f" | {file_path}"

        block = f"{header}\n{r.content}\n"

        if chars_used + len(block) > max_chars and parts:
            break
        parts.append(block)
        chars_used += len(block)

    return "---\n".join(parts)


def build_messages(
    query: str,
    context: str,
    history: list[ChatMessage] | None = None,
) -> list[ChatMessage]:
    """Assemble the message list for the LLM."""
    system_content = f"{SYSTEM_PROMPT}\n\nCONTEXT FROM VAULT:\n{context}"
    messages = [ChatMessage(role="system", content=system_content)]

    if history:
        messages.extend(history)

    messages.append(ChatMessage(role="user", content=query))
    return messages


class RAGPipeline:
    """Orchestrates retrieval + generation."""

    def __init__(self, vault: Vault, config: VaultConfig = DEFAULT_CONFIG):
        self.vault = vault
        self.config = config

    def _retrieve(self, query: str) -> list[SearchResult]:
        return search_vault(self.vault, query, n_results=self.config.chat_context_results)

    def query(
        self,
        query_text: str,
        model: str,
        history: list[ChatMessage] | None = None,
    ) -> ChatResponse:
        """Full RAG pipeline: search -> format -> chat -> response."""
        results = self._retrieve(query_text)
        context = format_context(results, self.config.chat_max_context_chars)
        messages = build_messages(query_text, context, history)

        response_text = ollama_client.chat(
            self.config.ollama_base_url, model, messages, self.config.chat_temperature,
        )

        return ChatResponse(
            content=response_text,
            model=model,
            context_ids=[r.document_id for r in results],
            context_count=len(results),
        )

    def query_stream(
        self,
        query_text: str,
        model: str,
        history: list[ChatMessage] | None = None,
    ) -> tuple[Generator[str, None, None], list[SearchResult]]:
        """Streaming RAG pipeline. Returns (token_generator, search_results)."""
        results = self._retrieve(query_text)
        context = format_context(results, self.config.chat_max_context_chars)
        messages = build_messages(query_text, context, history)

        stream = ollama_client.chat_stream(
            self.config.ollama_base_url, model, messages, self.config.chat_temperature,
        )
        return stream, results
