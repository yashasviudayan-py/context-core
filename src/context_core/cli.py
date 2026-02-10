import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel

from context_core.config import DEFAULT_CONFIG
from context_core.vault import Vault
from context_core.ingest import create_manual_document, ingest_directory
from context_core.search import search_vault
from context_core.utils import truncate_text, check_ollama_running

console = Console()


def get_vault() -> Vault:
    """Initialize Vault with Ollama health check."""
    if not check_ollama_running():
        console.print(
            "[bold red]Error:[/] Ollama is not running. Start it with: ollama serve",
            highlight=False,
        )
        raise SystemExit(1)
    return Vault()


@click.group()
@click.version_option(version="0.1.0", prog_name="context-core")
def cli():
    """Context Core - Your personal AI memory vault."""
    pass


@cli.command()
@click.argument("content")
@click.option("--tags", "-t", default=None, help="Comma-separated tags")
@click.option("--source", "-s", default="manual", help="Source type label (default: manual)")
def add(content: str, tags: str | None, source: str):
    """Add a text snippet or code to the vault."""
    vault = get_vault()
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    doc = create_manual_document(content, tags=tag_list, source_type=source)
    vault.add([doc])
    console.print(f"[green]Added:[/] {doc.id}")


@cli.command()
@click.argument("directory", type=click.Path(exists=True, path_type=Path))
@click.option("--recursive/--no-recursive", default=True, help="Recurse into subdirectories")
def ingest(directory: Path, recursive: bool):
    """Ingest all supported files from a directory."""
    vault = get_vault()
    console.print(f"Ingesting from [bold]{directory}[/]...")
    ingested, skipped = ingest_directory(directory, vault, recursive=recursive)
    console.print(f"[green]Done:[/] {ingested} files ingested, {skipped} skipped")


@cli.command()
@click.argument("query")
@click.option("--n", "-n", default=10, help="Number of results")
@click.option("--type", "-t", "source_type", default=None, help="Filter by source type")
@click.option("--ext", "-e", default=None, help="Filter by file extension (e.g. .py)")
@click.option("--min-score", default=0.0, help="Minimum similarity score (0-1)")
def search(query: str, n: int, source_type: str | None, ext: str | None, min_score: float):
    """Search the vault with a natural language query."""
    vault = get_vault()
    results = search_vault(
        vault, query, n_results=n,
        source_type=source_type,
        file_extension=ext,
        min_similarity=min_score,
    )

    if not results:
        console.print("[yellow]No results found.[/]")
        return

    for i, result in enumerate(results, 1):
        source = result.metadata.get("source_type", "unknown")
        score = f"{result.similarity:.3f}"
        file_path = result.metadata.get("file_path", "")
        header = f"[{i}] Score: {score} | Source: {source}"
        if file_path:
            header += f" | {file_path}"

        ext_val = result.metadata.get("file_extension", "")
        lang = ext_val.lstrip(".") if ext_val else "text"

        content_preview = truncate_text(result.content, 500)
        panel = Panel(
            Syntax(content_preview, lang, theme="monokai", word_wrap=True),
            title=header,
            title_align="left",
            border_style="dim",
        )
        console.print(panel)
        console.print()


@cli.command()
def stats():
    """Show vault statistics."""
    vault = get_vault()
    info = vault.stats()
    table = Table(title="Vault Statistics")
    table.add_column("Property", style="bold")
    table.add_column("Value")
    for key, value in info.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    console.print(table)


@cli.command()
@click.option("--n", "-n", default=5, help="Number of documents to preview")
def peek(n: int):
    """Preview documents in the vault."""
    vault = get_vault()
    data = vault.peek(n=n)
    if not data or not data.get("ids"):
        console.print("[yellow]Vault is empty.[/]")
        return

    for i, doc_id in enumerate(data["ids"]):
        content = truncate_text(data["documents"][i], 300)
        meta = data["metadatas"][i] if data["metadatas"] else {}
        console.print(f"[bold cyan]{doc_id}[/]")
        console.print(f"  Metadata: {meta}")
        console.print(f"  Content:  {content}")
        console.print()


@cli.command()
@click.argument("document_id")
def delete(document_id: str):
    """Delete a document by its ID."""
    vault = get_vault()
    vault.delete([document_id])
    console.print(f"[green]Deleted:[/] {document_id}")


# --- Chat / Oracle ---

@cli.command()
@click.argument("query", required=False, default=None)
@click.option("--model", "-m", default=None, help="Ollama model (auto-detected if omitted)")
@click.option("--context", "-c", default=5, help="Number of context documents to retrieve")
@click.option("--interactive", "-i", is_flag=True, help="Start interactive REPL mode")
def chat(query: str | None, model: str | None, context: int, interactive: bool):
    """Query the vault with an LLM (The Oracle)."""
    from context_core.rag import RAGPipeline, format_context
    from context_core.ollama_client import detect_chat_model
    from context_core.models import ChatMessage
    from context_core.config import VaultConfig

    vault = get_vault()

    # Resolve model
    if not model:
        model = detect_chat_model()
        if not model:
            console.print(
                "[bold red]Error:[/] No chat models found in Ollama.\n"
                "Install one with: [bold]ollama pull llama3[/]",
                highlight=False,
            )
            raise SystemExit(1)
        console.print(f"[dim]Using model: {model}[/]")

    config = VaultConfig(chat_context_results=context)
    pipeline = RAGPipeline(vault, config)

    if interactive:
        _chat_repl(pipeline, model)
    elif query:
        _chat_single(pipeline, model, query)
    else:
        console.print("[bold red]Error:[/] Provide a query or use --interactive (-i)")
        raise SystemExit(1)


def _chat_single(pipeline, model: str, query: str):
    """Handle a single chat query with streaming output."""
    stream, results = pipeline.query_stream(query, model)
    console.print()
    for token in stream:
        console.print(token, end="", highlight=False)
    console.print("\n")

    if results:
        console.print(f"[dim]({len(results)} context documents used)[/]")


def _chat_repl(pipeline, model: str):
    """Interactive REPL mode."""
    from context_core.models import ChatMessage
    from context_core.rag import format_context

    console.print(f"[bold cyan]The Oracle[/] - Interactive mode (model: {model})")
    console.print("[dim]Commands: /clear, /sources, exit[/]\n")

    history: list[ChatMessage] = []
    last_results = []

    while True:
        try:
            user_input = console.input("[bold green]You>[/] ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/]")
            break

        text = user_input.strip()
        if not text:
            continue

        if text.lower() in ("exit", "quit"):
            console.print("[dim]Goodbye.[/]")
            break

        if text == "/clear":
            history.clear()
            last_results = []
            console.print("[dim]Conversation cleared.[/]\n")
            continue

        if text == "/sources":
            if not last_results:
                console.print("[yellow]No sources from last query.[/]\n")
            else:
                for i, r in enumerate(last_results, 1):
                    source = r.metadata.get("source_type", "unknown")
                    score = f"{r.similarity:.3f}"
                    fp = r.metadata.get("file_path", "")
                    label = f"[{i}] {score} | {source}"
                    if fp:
                        label += f" | {fp}"
                    console.print(f"  {label}")
                console.print()
            continue

        # Stream response
        console.print()
        stream, last_results = pipeline.query_stream(text, model, history=history)
        response_parts = []
        for token in stream:
            console.print(token, end="", highlight=False)
            response_parts.append(token)
        console.print("\n")

        # Update conversation history
        history.append(ChatMessage(role="user", content=text))
        history.append(ChatMessage(role="assistant", content="".join(response_parts)))


# --- Watch subgroup ---

@cli.group()
def watch():
    """Manage the background watcher daemon."""
    pass


@watch.command()
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground (for debugging)")
def start(foreground: bool):
    """Start the watcher daemon."""
    from context_core.watcher.daemon import start_daemon

    if not foreground and not check_ollama_running():
        console.print(
            "[bold red]Error:[/] Ollama is not running. Start it with: ollama serve",
            highlight=False,
        )
        raise SystemExit(1)

    try:
        pid = start_daemon(foreground=foreground)
        if not foreground:
            console.print(f"[green]Watcher started[/] (PID: {pid})")
    except RuntimeError as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1)


@watch.command()
def stop():
    """Stop the watcher daemon."""
    from context_core.watcher.daemon import stop_daemon

    if stop_daemon():
        console.print("[green]Watcher stopped.[/]")
    else:
        console.print("[yellow]Watcher is not running.[/]")


@watch.command()
def status():
    """Show watcher daemon status."""
    from context_core.watcher.daemon import daemon_status

    info = daemon_status()
    table = Table(title="Watcher Status")
    table.add_column("Property", style="bold")
    table.add_column("Value")

    status_style = "[green]" if info.get("status") == "running" else "[red]"
    table.add_row("Status", f"{status_style}{info.get('status', 'unknown')}[/]")
    table.add_row("PID", str(info.get("pid", "N/A")))
    table.add_row("Started At", str(info.get("started_at", "N/A")))
    table.add_row("Watched Dirs", str(info.get("watched_directories", 0)))

    if info.get("note"):
        table.add_row("Note", f"[yellow]{info['note']}[/]")

    console.print(table)


@watch.command("add")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--no-recursive", is_flag=True, help="Don't watch subdirectories")
def add_dir(directory: Path, no_recursive: bool):
    """Add a directory to watch."""
    from context_core.watcher.state import WatcherState

    state = WatcherState()
    resolved = str(directory.resolve())
    try:
        state.add_directory(resolved, recursive=not no_recursive)
        console.print(f"[green]Now watching:[/] {resolved}")
        console.print("[dim]Restart the watcher for changes to take effect.[/]")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1)
    finally:
        state.close()


@watch.command("remove")
@click.argument("directory", type=click.Path(path_type=Path))
def remove_dir(directory: Path):
    """Remove a directory from the watch list."""
    from context_core.watcher.state import WatcherState

    state = WatcherState()
    resolved = str(directory.resolve())
    if state.remove_directory(resolved):
        console.print(f"[green]Removed:[/] {resolved}")
        console.print("[dim]Restart the watcher for changes to take effect.[/]")
    else:
        console.print(f"[yellow]Not found:[/] {resolved}")
    state.close()


@watch.command("list")
def list_dirs():
    """List all watched directories."""
    from context_core.watcher.state import WatcherState

    state = WatcherState()
    dirs = state.list_directories()
    state.close()

    if not dirs:
        console.print("[yellow]No directories being watched.[/]")
        console.print("Add one with: [bold]vault watch add <directory>[/]")
        return

    table = Table(title="Watched Directories")
    table.add_column("#", style="dim")
    table.add_column("Path", style="bold")
    table.add_column("Recursive")
    table.add_column("Added")

    for i, d in enumerate(dirs, 1):
        table.add_row(
            str(i),
            d.path,
            "Yes" if d.recursive else "No",
            d.added_at,
        )
    console.print(table)
