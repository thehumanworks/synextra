#!/usr/bin/env bash
set -euo pipefail

uv --directory backend run --frozen ruff check .
uv --directory backend run --frozen ruff format --check .

uv --directory sdk run --frozen ruff check .
uv --directory sdk run --frozen ruff format --check .

uv --directory cli run --frozen ruff check .
uv --directory cli run --frozen ruff format --check .

npm --prefix frontend run lint
