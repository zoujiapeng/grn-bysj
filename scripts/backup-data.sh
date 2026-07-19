#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$ROOT/backups}"
mkdir -p "$DEST"
NAME="grn-data-$(date +%Y%m%d-%H%M%S).tar.gz"
tar -czf "$DEST/$NAME" -C "$ROOT" data
printf 'Backup written to %s\n' "$DEST/$NAME"
