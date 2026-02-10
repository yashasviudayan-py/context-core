from context_core.vault import Vault
from context_core.models import SearchResult


def search_vault(
    vault: Vault,
    query: str,
    n_results: int = 10,
    source_type: str | None = None,
    file_extension: str | None = None,
    min_similarity: float = 0.0,
) -> list[SearchResult]:
    """High-level search with optional filters."""
    where = {}
    if source_type:
        where["source_type"] = source_type
    if file_extension:
        if not file_extension.startswith("."):
            file_extension = f".{file_extension}"
        where["file_extension"] = file_extension

    results = vault.query(
        query_text=query,
        n_results=n_results,
        where=where if where else None,
    )

    if min_similarity > 0:
        results = [r for r in results if r.similarity >= min_similarity]

    return results
