import hashlib
import urllib.request


def content_hash(text: str) -> str:
    """SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text for display, preserving word boundaries."""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated + "..."


def check_ollama_running(url: str = "http://localhost:11434") -> bool:
    """Check if Ollama server is reachable."""
    try:
        urllib.request.urlopen(url, timeout=2)  # nosec B310  # Only used for localhost health check
        return True
    except Exception:
        return False
