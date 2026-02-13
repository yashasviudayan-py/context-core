#!/usr/bin/env bash
# Simple smoke test for Context Core that starts Ollama, runs a couple of CLI commands,
# then attempts to stop Ollama. Intended for local development only.

set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"
OLLAMA_LOG="$ROOT_DIR/ollama.smoke.log"

echo "Starting Ollama in background (logs -> $OLLAMA_LOG)"
# Start Ollama in background; use nohup so it doesn't block this shell.
nohup ollama serve > "$OLLAMA_LOG" 2>&1 &
OLLAMA_PID=$!

echo "Waiting for Ollama to accept connections..."
# Wait up to 30 seconds for /api/tags to respond
for i in {1..30}; do
  if curl -sS http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "Ollama is up"
    break
  fi
  sleep 1
done

if ! curl -sS http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama did not start in time. See $OLLAMA_LOG"
  exit 1
fi

echo "Running vault stats"
"$VENV_PY" -c "import sys; sys.argv=['vault','stats']; from context_core.cli import cli; cli()"

echo "Running vault chat 'hello'"
"$VENV_PY" - <<PY
import sys
from context_core.cli import cli
sys.argv=['vault','chat','hello']
cli()
PY

echo "Stopping Ollama (PID: $OLLAMA_PID)"
kill $OLLAMA_PID || true
sleep 1
if ps -p $OLLAMA_PID >/dev/null 2>&1; then
  echo "Ollama did not exit; you may need to stop it manually. See $OLLAMA_LOG"
else
  echo "Ollama stopped"
fi

echo "Smoke test completed"
