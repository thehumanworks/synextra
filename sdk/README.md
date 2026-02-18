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

sx = Synextra(openai_api_key="...")

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

The CLI lives in the separate `cli/` workspace and depends on this package.
