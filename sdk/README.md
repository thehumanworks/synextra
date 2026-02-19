# Synextra SDK

This module provides the standalone **Python SDK** for document ingestion and grounded QA.

## Install (uv)

```bash
cd sdk
uv venv
uv sync --dev
```

## Python SDK

```python
from synextra import Synextra

sx = Synextra(
    openai_api_key="...",
    # Optional for Azure/OpenAI-compatible endpoints:
    # openai_base_url="https://<resource>.openai.azure.com/openai/v1/",
    # openai_api="chat_completions",  # or "responses"
)

# 1) Ingest a document (chunks + page text + BM25 index)
#    Supported: .pdf, .doc/.docx, .csv, .xlsx, .txt/.md, and code files.
ingest = sx.ingest("/path/to/paper.pdf")

# 2) Ask grounded questions
result = sx.query("What is the Transformer model described in the paper?")
print(result.answer)
print(result.citations)

# Or run the pipeline explicitly:
research = sx.research("What is the Transformer model described in the paper?")
review = sx.review(research)
final = sx.synthesize("What is the Transformer model described in the paper?", research)
print(final.answer)
```

## OpenAI/Azure configuration

Synextra uses `openai-agents` with OpenAI-compatible configuration.

- API key sources:
  - `OPENAI_API_KEY`
  - `AZURE_OPENAI_API_KEY` (alias)
- Base URL sources:
  - `OPENAI_BASE_URL`
  - `AZURE_OPENAI_BASE_URL` (alias)
  - `AZURE_OPENAI_ENDPOINT` (auto-converted to `/openai/v1/`)
- Optional API-shape override:
  - `SYNEXTRA_OPENAI_API` = `responses` or `chat_completions`
- Optional tracing safeguard for non-OpenAI keys:
  - `OPENAI_AGENTS_DISABLE_TRACING=1` (or configure a separate tracing export key)

Azure note: when calling models through Azure OpenAI, the `model` value must be your Azure deployment name.

The CLI lives in the separate `cli/` workspace and depends on this package.
