#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

for tool in uv pnpm; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf '缺少 %s，请先按 README 安装。\n' "$tool" >&2
    exit 1
  fi
done

uv sync --frozen
pnpm --dir web install --frozen-lockfile
pnpm --dir web build
exec .venv/bin/python -m askless "$@"
