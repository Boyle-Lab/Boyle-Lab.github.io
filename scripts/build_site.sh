#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/build_publications.py --strict
python3 -m unittest discover -s tests -v
JEKYLL_ENV=production bundle exec jekyll build --trace "$@"
