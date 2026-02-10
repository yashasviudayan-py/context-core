# Architecture

Context Core is built in three layered phases, each building on the previous.

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                            │
│                                                                    │
│  vault add    vault ingest    vault search    vault chat -i        │
│  vault stats  vault peek      vault delete    vault watch start    │
└────────┬──────────┬──────────────┬───────────────┬────────────────┘
         │          │              │               │
         ▼          ▼              ▼               ▼
┌─────────────┐ ┌────────┐ ┌───────────┐ ┌──────────────────┐
│   ingest.py │ │vault.py│ │ search.py │ │     rag.py       │
│             │ │        │ │           │ │                  │
│ read_file() │ │ add()  │ │search_    │ │ RAGPipeline      │
│ chunk_text()│ │query() │ │vault()    │ │  .query()        │
│ read_file_  │ │delete()│ │           │ │  .query_stream() │
│  chunked()  │ │ stats()│ │           │ │                  │
└──────┬──────┘ └───┬────┘ └─────┬─────┘ └────────┬─────────┘
       │            │            │                 │
       ▼            ▼            ▼                 ▼
┌──────────────────────────────────┐    ┌──────────────────┐
│           ChromaDB               │    │  ollama_client.py│
│                                  │    │                  │
│  PersistentClient                │    │ list_models()    │
│  OllamaEmbeddingFunction        │    │ detect_chat_     │
│  Collection (cosine similarity)  │    │   model()        │
│  Upsert (dedup via content hash) │    │ chat_stream()    │
└──────────────┬───────────────────┘    │ chat()           │
               │                        └────────┬─────────┘
               ▼                                 ▼
┌──────────────────────────────────────────────────────────┐
│                      Ollama Server                        │
│                  (localhost:11434)                         │
│                                                            │
│  nomic-embed-text (embeddings)    llama3.1 (chat/RAG)     │
└──────────────────────────────────────────────────────────┘
```

## Phase 1: The Vault

The foundation layer — a vector database for storing and retrieving documents.

### Data Flow: Ingestion

```
File on disk
  → read_file_chunked()         # Read + validate extension/size
  → _chunk_text()               # Split at line boundaries (6000 chars, 200 overlap)
  → Document(content, metadata) # Wrap with metadata (source, path, extension)
  → generate_id()               # SHA-256 content hash → deterministic doc ID
  → vault.add()                 # ChromaDB upsert (dedup by content hash)
  → OllamaEmbeddingFunction    # nomic-embed-text generates 768-dim vector
  → ChromaDB PersistentClient   # Stored to disk (cosine similarity index)
```

### Data Flow: Search

```
User query string
  → search_vault()              # Apply metadata filters (source_type, extension)
  → vault.query()               # ChromaDB vector similarity search
  → OllamaEmbeddingFunction     # Embed query → 768-dim vector
  → Cosine similarity ranking   # ChromaDB returns top-N matches
  → list[SearchResult]          # Content + metadata + similarity score
```

### Key Design Decisions

- **Content-hash IDs**: `doc_{sha256[:16]}` ensures identical content = same ID = automatic dedup via upsert
- **Chunking**: Line-boundary splitting with overlap preserves code structure and function boundaries
- **Frozen config**: `VaultConfig` is immutable to prevent runtime mutation

## Phase 2: The Watcher

A background daemon that automatically feeds the vault from three input sources.

### Component Architecture

```
┌─────────────────────────────────────────────┐
│              WatcherDaemon                   │
│                                              │
│  Signal handlers (SIGTERM/SIGINT)            │
│  _running flag for clean shutdown            │
│                                              │
│  ┌──────────────┐ ┌───────────────────────┐ │
│  │ FileWatcher   │ │ ClipboardMonitor      │ │
│  │               │ │                       │ │
│  │ watchdog      │ │ pbpaste polling (5s)  │ │
│  │ Observer      │ │ SHA-256 dedup         │ │
│  │ 2s debounce   │ │ 10-50k char filter   │ │
│  │ content-hash  │ │                       │ │
│  │ initial_scan()│ │                       │ │
│  └──────┬───────┘ └───────────┬───────────┘ │
│         │                     │              │
│  ┌──────▼─────────────────────▼───────────┐ │
│  │          HistoryIngestor               │ │
│  │                                        │ │
│  │  ~/.zsh_history polling (30s)          │ │
│  │  Extended + plain format parsing       │ │
│  │  Skip common commands (ls, cd, etc.)   │ │
│  │  Batch 20 commands per vault.add()     │ │
│  └────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │   WatcherState    │
         │   (SQLite + WAL)  │
         │                   │
         │ watched_directories│
         │ file_state        │
         │ clipboard_state   │
         │ history_state     │
         │ daemon_state      │
         └───────────────────┘
```

### Daemon Lifecycle

- **Start**: `subprocess.Popen` with `start_new_session=True` (detached process)
- **Stop**: `SIGTERM` → 10s grace period → `SIGKILL` fallback
- **Status**: `os.kill(pid, 0)` for process existence check, auto-clears stale PIDs
- **Foreground mode**: `--foreground` flag for debugging (runs in current process)

## Phase 3: The Oracle

RAG (Retrieval-Augmented Generation) interface that combines vault context with an LLM.

### RAG Pipeline

```
User question
  │
  ▼
search_vault(query, n=5)          # 1. Retrieve relevant documents
  │
  ▼
format_context(results, 8000)     # 2. Format into numbered context block
  │                                #    with character budget
  ▼
build_messages(query, context,    # 3. Assemble message list:
               history)           #    system prompt + context + history + query
  │
  ▼
ollama_client.chat_stream()       # 4. Stream to Ollama /api/chat
  │                                #    NDJSON response parsing
  ▼
Token-by-token output             # 5. Stream to terminal via Rich
```

### Interactive REPL

The REPL maintains conversation history for multi-turn context:

```
User input → query_stream(text, model, history)
           → stream tokens to terminal
           → append user + assistant messages to history
           → /sources shows last retrieval results
           → /clear resets history
```

## Data Models

```python
DocumentMetadata    # source_type, timestamp, file_path, extension, tags, content_hash
Document            # content + metadata + deterministic ID
SearchResult        # content + metadata + distance + similarity + document_id
ChatMessage         # role (system/user/assistant) + content
ChatResponse        # content + model + context_ids + context_count
```

## Dependencies

| Dependency | Purpose | Why chosen |
|---|---|---|
| chromadb | Vector store | Embedded, no server needed, persistent storage |
| click | CLI framework | Composable groups, type validation, auto-help |
| rich | Terminal output | Syntax highlighting, tables, panels, streaming |
| watchdog | File monitoring | Cross-platform, battle-tested, event-driven |
| httpx | HTTP client | Streaming support for Ollama NDJSON responses |
| ollama (pip) | Ollama SDK | Required by ChromaDB's OllamaEmbeddingFunction |

All other functionality uses Python stdlib (sqlite3, subprocess, threading, hashlib, json, signal).
