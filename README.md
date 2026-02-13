# Context Core

**Your personal AI memory vault** — a local-first knowledge base with semantic search and RAG-powered chat, running entirely on your machine.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-144%20passing-brightgreen.svg)]()

---

## What is Context Core?

Context Core turns your local files, clipboard history, and terminal commands into a searchable, AI-queryable knowledge base. Everything runs locally — no cloud, no API keys, no cost.

**Key features:**
- **Semantic search** over all your ingested content using vector embeddings
- **RAG chat** — ask questions about your code, notes, and history using a local LLM
- **Background watcher** — automatically indexes file changes, clipboard copies, and terminal commands
- **100% local** — powered by [Ollama](https://ollama.com) + [ChromaDB](https://www.trychroma.com), your data never leaves your machine

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    CLI (Click)                       │
│  vault add | ingest | search | chat | watch | stats  │
└──────────┬──────────────────────┬───────────────────┘
           │                      │
     ┌─────▼─────┐         ┌─────▼─────┐
     │  The Vault │         │ The Oracle│
     │  (Phase 1) │         │ (Phase 3) │
     │            │         │           │
     │ ChromaDB   │◄────────│ RAG       │
     │ Embeddings │         │ Pipeline  │
     │ Ingest     │         │ Ollama LLM│
     └─────▲─────┘         └───────────┘
           │
     ┌─────┴──────┐
     │ The Watcher │
     │  (Phase 2)  │
     │             │
     │ File Watch  │
     │ Clipboard   │
     │ Zsh History │
     │ SQLite State│
     └─────────────┘
```

### Module Overview

| Module | Purpose |
|---|---|
| `vault.py` | ChromaDB vector store wrapper with upsert/query/delete |
| `ingest.py` | File reading, chunking, and document creation |
| `search.py` | Semantic search with metadata filters |
| `ollama_client.py` | Thin httpx wrapper for Ollama API (models, chat, streaming) |
| `rag.py` | RAG pipeline — retrieval + context formatting + LLM query |
| `cli.py` | Click CLI with all commands and interactive REPL |
| `config.py` | Centralized configuration (VaultConfig dataclass) |
| `models.py` | Data models (Document, SearchResult, ChatMessage, etc.) |
| `watcher/` | Background daemon with file, clipboard, and history monitors |

## Prerequisites

- **Python 3.12+**
- **[Ollama](https://ollama.com)** installed and running

```bash
# Install Ollama (macOS)
brew install ollama

# Pull required models
ollama pull nomic-embed-text    # embeddings (274 MB)
ollama pull llama3.1            # chat model (pick any chat model you prefer)

# Start Ollama server
ollama serve
```

## Installation

```bash
# Clone the repo
git clone https://github.com/yashasviudayan-py/context-core.git
cd context-core

# Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick Start

```bash
# 1. Activate the environment
source .venv/bin/activate

# 2. Ingest some files
vault ingest ~/Projects/my-app

# 3. Search your vault
vault search "database connection"

# 4. Chat with your knowledge base
vault chat "how does the auth system work?"

# 5. Interactive chat session
vault chat -i
```

## Usage

### Adding Content

```bash
# Ingest a directory (recursive by default)
vault ingest ~/Projects/my-app
vault ingest ~/Documents/notes --no-recursive

# Add a manual text snippet
vault add "Redis uses skip lists for sorted sets" -t redis,data-structures
vault add "$(cat snippet.py)" -s code
```

### Searching

```bash
# Semantic search
vault search "error handling patterns"

# Filter by source type or file extension
vault search "authentication" --type file --ext .py

# Adjust result count and minimum score
vault search "docker" -n 20 --min-score 0.5
```

### Chatting (The Oracle)

```bash
# Single question (streams response)
vault chat "explain the main design patterns in my code"

# Interactive REPL mode
vault chat -i

# Specify model and context count
vault chat "summarize my notes" --model llama3.1 -c 10
```

**REPL commands:**
| Command | Action |
|---|---|
| `/sources` | Show context documents used in last response |
| `/clear` | Reset conversation history |
| `exit` / `quit` | Exit the REPL |

### Background Watcher

```bash
# Add directories to monitor
vault watch add ~/Projects
vault watch add ~/Documents/notes

# Start the background daemon
vault watch start

# Check status
vault watch status

# Stop the daemon
vault watch stop

# List watched directories
vault watch list

# Remove a directory
vault watch remove ~/Documents/notes
```

The watcher automatically indexes:
- **File changes** — new/modified files in watched directories (watchdog + debounce)
- **Clipboard** — text copied to clipboard via `pbpaste` (macOS)
- **Terminal history** — zsh commands from `~/.zsh_history`

### Vault Management

```bash
# View statistics
vault stats

# Preview stored documents
vault peek -n 10

# Delete a specific document
vault delete doc_abc123
```

## Configuration

All settings are in `src/context_core/config.py` via the `VaultConfig` dataclass:

| Setting | Default | Description |
|---|---|---|
| `chroma_path` | `./chroma_data` | ChromaDB storage directory |
| `embedding_model` | `nomic-embed-text` | Ollama embedding model |
| `max_file_size_bytes` | `1048576` (1 MB) | Maximum file size for ingestion |
| `max_chunk_chars` | `6000` | Characters per chunk (~1500 tokens) |
| `chat_model` | `None` (auto-detect) | Ollama chat model |
| `chat_context_results` | `5` | Documents retrieved for RAG context |
| `chat_temperature` | `0.7` | LLM response temperature |
| `chat_max_context_chars` | `8000` | Max characters in RAG context window |

## Supported File Types

`.py` `.md` `.txt` `.js` `.ts` `.jsx` `.tsx` `.json` `.yaml` `.yml` `.toml` `.sh` `.bash` `.css` `.html` `.sql` `.rs` `.go` `.java`

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=context_core

# Lint
ruff check src/ tests/
```

### Project Structure

```
context-core/
├── src/context_core/
│   ├── __init__.py
│   ├── cli.py              # Click CLI (all commands)
│   ├── config.py            # VaultConfig dataclass
│   ├── models.py            # Document, SearchResult, ChatMessage
│   ├── vault.py             # ChromaDB vector store
│   ├── ingest.py            # File reading + chunking
│   ├── search.py            # Semantic search with filters
│   ├── ollama_client.py     # Ollama HTTP API wrapper
│   ├── rag.py               # RAG pipeline
│   ├── utils.py             # Utilities (hashing, Ollama health check)
│   └── watcher/
│       ├── state.py         # SQLite state database
│       ├── daemon.py        # Daemon lifecycle management
│       ├── file_watcher.py  # watchdog file monitor
│       ├── clipboard_monitor.py  # Clipboard polling
│       └── history_ingestor.py   # Zsh history parser
├── tests/                   # 144 tests
├── pyproject.toml
└── README.md
```

## Tech Stack

| Component | Technology |
|---|---|
| Vector database | [ChromaDB](https://www.trychroma.com) |
| Embeddings | [Ollama](https://ollama.com) + nomic-embed-text |
| LLM chat | Ollama + any chat model (llama3.1, mistral, etc.) |
| CLI framework | [Click](https://click.palletsprojects.com) |
| Terminal UI | [Rich](https://rich.readthedocs.io) |
| File watching | [watchdog](https://python-watchdog.readthedocs.io) |
| HTTP client | [httpx](https://www.python-httpx.org) |
| State management | SQLite (stdlib) |
| Testing | pytest |

## License

[MIT](LICENSE)

## Smoke test (convenience)

This repo includes a small convenience script to run a quick end-to-end smoke test that:
- starts Ollama in the background,
- waits for it to accept connections,
- runs `vault stats` and a non-interactive `vault chat "hello"`,
- then attempts to stop Ollama.

Run it from the repository root:

```bash
chmod +x scripts/smoke_test.sh
./scripts/smoke_test.sh
```

Note: the script uses `nohup` to start Ollama and will attempt to kill the process it started; if you already have a running Ollama server, skip the script and instead run the CLI commands directly.
