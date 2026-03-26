#!/usr/bin/env bash
# One-command sync for Claude Code plugins, skills and settings.
# Usage: ./install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Require python3
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required but not found in PATH." >&2
  exit 1
fi

# Require claude CLI
if ! command -v claude &>/dev/null; then
  echo "Error: claude CLI is required but not found in PATH." >&2
  echo "Install it from: https://claude.ai/code" >&2
  exit 1
fi

exec python3 "$SCRIPT_DIR/sync.py" "$@"
