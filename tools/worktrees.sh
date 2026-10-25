#!/usr/bin/env bash
# Task checkout lifecycle: fetch first, then fold only merged and clean trees.
# Python 3 and Git are required. --dry-run fetches but never removes a checkout.
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/worktrees.py" "$@"
