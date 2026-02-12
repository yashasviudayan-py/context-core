import json
from unittest.mock import patch, MagicMock

from context_core.ollama_client import (
    list_models,
    detect_chat_model,
    chat_stream,
    chat,
)
from context_core.models import ChatMessage


def _mock_tags_response(model_names: list[str]):
    """Build a mock /api/tags response."""
    return {"models": [{"name": f"{n}:latest"} for n in model_names]}


class TestListModels:
    @patch("context_core.ollama_client.httpx.get")
    def test_returns_model_list(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mock_tags_response(["llama3", "mistral"])
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        models = list_models("http://localhost:11434")
        assert len(models) == 2
        assert models[0]["name"] == "llama3:latest"

    @patch("context_core.ollama_client.httpx.get")
    def test_empty_when_no_models(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        assert list_models() == []


class TestDetectChatModel:
    @patch("context_core.ollama_client.list_models")
    def test_skips_embedding_models(self, mock_list):
        mock_list.return_value = [
            {"name": "nomic-embed-text:latest"},
            {"name": "llama3:latest"},
        ]
        assert detect_chat_model() == "llama3:latest"

    @patch("context_core.ollama_client.list_models")
    def test_returns_none_when_only_embedding(self, mock_list):
        mock_list.return_value = [
            {"name": "nomic-embed-text:latest"},
            {"name": "all-minilm:latest"},
        ]
        assert detect_chat_model() is None

    @patch("context_core.ollama_client.list_models")
    def test_returns_none_when_empty(self, mock_list):
        mock_list.return_value = []
        assert detect_chat_model() is None

    @patch("context_core.ollama_client.list_models")
    def test_first_chat_model_returned(self, mock_list):
        mock_list.return_value = [
            {"name": "mistral:latest"},
            {"name": "llama3:latest"},
        ]
        assert detect_chat_model() == "mistral:latest"


class TestChatStream:
    @patch("context_core.ollama_client.httpx.Client")
    def test_yields_tokens(self, mock_client_cls):
        lines = [
            json.dumps({"message": {"content": "Hello"}, "done": False}),
            json.dumps({"message": {"content": " world"}, "done": True}),
        ]
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.raise_for_status = MagicMock()
        mock_stream.iter_lines.return_value = iter(lines)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.stream.return_value = mock_stream
        mock_client_cls.return_value = mock_client

        messages = [ChatMessage(role="user", content="Hi")]
        tokens = list(chat_stream("http://localhost:11434", "llama3", messages))
        assert tokens == ["Hello", " world"]

    @patch("context_core.ollama_client.httpx.Client")
    def test_skips_empty_tokens(self, mock_client_cls):
        lines = [
            json.dumps({"message": {"content": ""}, "done": False}),
            json.dumps({"message": {"content": "OK"}, "done": True}),
        ]
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.raise_for_status = MagicMock()
        mock_stream.iter_lines.return_value = iter(lines)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.stream.return_value = mock_stream
        mock_client_cls.return_value = mock_client

        messages = [ChatMessage(role="user", content="test")]
        tokens = list(chat_stream("http://localhost:11434", "llama3", messages))
        assert tokens == ["OK"]


class TestChat:
    @patch("context_core.ollama_client.chat_stream")
    def test_assembles_full_response(self, mock_stream):
        mock_stream.return_value = iter(["Hello", " ", "world!"])
        messages = [ChatMessage(role="user", content="Hi")]
        result = chat("http://localhost:11434", "llama3", messages)
        assert result == "Hello world!"
