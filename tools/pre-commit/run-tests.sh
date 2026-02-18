#!/usr/bin/env bash
set -euo pipefail

uv --directory backend run --frozen pytest
uv --directory sdk run --frozen pytest
uv --directory cli run --frozen pytest

npm --prefix frontend run test
