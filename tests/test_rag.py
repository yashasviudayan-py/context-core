import pytest
from unittest.mock import patch, MagicMock

from context_core.rag import format_context, build_messages, RAGPipeline, SYSTEM_PROMPT
from context_core.models import SearchResult, ChatMessage, ChatResponse
from context_core.config import VaultConfig


def _make_result(content: str, source: str = "file", score: float = 0.9, doc_id: str = "doc_1"):
    return SearchResult(
        content=content,
        metadata={"source_type": source, "file_path": f"/test/{doc_id}.py"},
        distance=1.0 - score,
        similarity=score,
        document_id=doc_id,
    )


class TestFormatContext:
    def test_formats_results(self):
        results = [
            _make_result("def foo(): pass", doc_id="doc_1"),
            _make_result("def bar(): pass", doc_id="doc_2"),
        ]
        ctx = format_context(results)
        assert "[1]" in ctx
        assert "[2]" in ctx
        assert "def foo(): pass" in ctx
        assert "def bar(): pass" in ctx

    def test_empty_results(self):
        ctx = format_context([])
        assert "No relevant context" in ctx

    def test_respects_char_budget(self):
        results = [
            _make_result("A" * 100, doc_id="doc_1"),
            _make_result("B" * 100, doc_id="doc_2"),
            _make_result("C" * 100, doc_id="doc_3"),
        ]
        ctx = format_context(results, max_chars=200)
        assert "A" * 100 in ctx
        # Second one may or may not fit, but third should be cut
        assert "C" * 100 not in ctx

    def test_includes_metadata_in_header(self):
        result = _make_result("code", source="terminal", score=0.85, doc_id="doc_1")
        ctx = format_context([result])
        assert "terminal" in ctx
        assert "0.850" in ctx


class TestBuildMessages:
    def test_basic_messages(self):
        msgs = build_messages("what is foo?", "context here")
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert SYSTEM_PROMPT in msgs[0].content
        assert "context here" in msgs[0].content
        assert msgs[1].role == "user"
        assert msgs[1].content == "what is foo?"

    def test_with_history(self):
        history = [
            ChatMessage(role="user", content="hello"),
            ChatMessage(role="assistant", content="hi there"),
        ]
        msgs = build_messages("follow up?", "ctx", history=history)
        assert len(msgs) == 4  # system + 2 history + user
        assert msgs[1].role == "user"
        assert msgs[1].content == "hello"
        assert msgs[2].role == "assistant"
        assert msgs[3].role == "user"
        assert msgs[3].content == "follow up?"


class TestRAGPipeline:
    @patch("context_core.rag.ollama_client.chat")
    @patch("context_core.rag.search_vault")
    def test_query_returns_chat_response(self, mock_search, mock_chat):
        mock_search.return_value = [
            _make_result("def foo(): pass", doc_id="doc_abc"),
        ]
        mock_chat.return_value = "foo is a function that does nothing."

        config = VaultConfig(chat_context_results=3)
        vault = MagicMock()
        pipeline = RAGPipeline(vault, config)

        resp = pipeline.query("what is foo?", model="llama3")
        assert isinstance(resp, ChatResponse)
        assert resp.content == "foo is a function that does nothing."
        assert resp.model == "llama3"
        assert resp.context_count == 1
        assert "doc_abc" in resp.context_ids

    @patch("context_core.rag.ollama_client.chat")
    @patch("context_core.rag.search_vault")
    def test_query_with_history(self, mock_search, mock_chat):
        mock_search.return_value = []
        mock_chat.return_value = "I don't know."

        vault = MagicMock()
        pipeline = RAGPipeline(vault)

        history = [ChatMessage(role="user", content="hi")]
        resp = pipeline.query("follow up", model="llama3", history=history)
        assert resp.content == "I don't know."

        # Verify messages passed to chat include history
        call_args = mock_chat.call_args
        messages = call_args[0][2]  # third positional arg
        roles = [m.role for m in messages]
        assert "user" in roles  # history user + current user

    @patch("context_core.rag.ollama_client.chat_stream")
    @patch("context_core.rag.search_vault")
    def test_query_stream(self, mock_search, mock_stream):
        results = [_make_result("content", doc_id="doc_x")]
        mock_search.return_value = results
        mock_stream.return_value = iter(["Hello", " ", "world"])

        vault = MagicMock()
        pipeline = RAGPipeline(vault)

        stream, ctx_results = pipeline.query_stream("test query", model="llama3")
        tokens = list(stream)
        assert tokens == ["Hello", " ", "world"]
        assert len(ctx_results) == 1
        assert ctx_results[0].document_id == "doc_x"

    @patch("context_core.rag.ollama_client.chat")
    @patch("context_core.rag.search_vault")
    def test_empty_vault(self, mock_search, mock_chat):
        mock_search.return_value = []
        mock_chat.return_value = "Vault is empty, but I can help."

        vault = MagicMock()
        pipeline = RAGPipeline(vault)
        resp = pipeline.query("anything?", model="llama3")
        assert resp.context_count == 0
        assert resp.content == "Vault is empty, but I can help."
