from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


class _FakeRunResult:
    def __init__(self, final_output: str) -> None:
        self.final_output = final_output


@pytest.fixture(autouse=True)
def _stub_pipeline_model_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _default_runner_run(*_args: object, **_kwargs: object) -> _FakeRunResult:
        return _FakeRunResult("Model grounded answer.")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("agents.Runner.run", staticmethod(_default_runner_run))


@pytest.mark.asyncio
async def test_pipeline_tool_endpoints_use_ingested_documents(client: AsyncClient) -> None:
    ingest = await client.post(
        "/v1/rag/documents",
        files={
            "file": (
                "notes.md",
                b"# Attention\n\nTransformers use attention.",
                "text/markdown",
            )
        },
    )
    assert ingest.status_code == 201
    document_id = ingest.json()["document_id"]

    bm25 = await client.post(
        "/v1/pipeline/tools/bm25-search",
        json={"query": "attention", "top_k": 4},
    )
    assert bm25.status_code == 200
    bm25_body = bm25.json()
    assert isinstance(bm25_body["evidence"], list)
    assert len(bm25_body["evidence"]) >= 1

    read_document = await client.post(
        "/v1/pipeline/tools/read-document",
        json={"document_id": document_id, "page": 0},
    )
    assert read_document.status_code == 200
    read_body = read_document.json()
    assert len(read_body["evidence"]) >= 1
    assert "Page 0" in read_body["evidence"][0]["text"]


@pytest.mark.asyncio
async def test_pipeline_agent_endpoint_returns_structured_envelope(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/pipeline/agents/run",
        json={
            "prompt": "Answer the question",
            "evidence": [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "page_number": 0,
                    "text": "Evidence for the final answer.",
                    "score": 0.9,
                    "source_tool": "bm25_search",
                }
            ],
            "upstream_outputs": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Model grounded answer."
    assert body["tools_used"] == ["bm25_search"]
    assert len(body["citations"]) == 1
    assert body["citations"][0]["document_id"] == "doc-1"


@pytest.mark.asyncio
async def test_pipeline_agent_endpoint_prefers_model_answer_when_available(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def _fake_runner_run(*_args: object, **_kwargs: object) -> _FakeRunResult:
        nonlocal calls
        calls += 1
        return _FakeRunResult("Model grounded answer.")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("agents.Runner.run", staticmethod(_fake_runner_run))

    response = await client.post(
        "/v1/pipeline/agents/run",
        json={
            "prompt": "Answer the question",
            "reasoning_effort": "high",
            "evidence": [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "page_number": 0,
                    "text": "Evidence for the final answer.",
                    "score": 0.9,
                    "source_tool": "bm25_search",
                }
            ],
            "upstream_outputs": [],
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["answer"] == "Model grounded answer."
    assert calls == 1
    assert len(body["citations"]) == 1


@pytest.mark.asyncio
async def test_pipeline_agent_endpoint_falls_back_when_model_call_fails(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_runner_run(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("synthetic model failure")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("agents.Runner.run", staticmethod(_failing_runner_run))

    response = await client.post(
        "/v1/pipeline/agents/run",
        json={
            "prompt": "Answer fallback question",
            "reasoning_effort": "high",
            "evidence": [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "page_number": 0,
                    "text": "Evidence for fallback answer.",
                    "score": 0.9,
                    "source_tool": "bm25_search",
                }
            ],
            "upstream_outputs": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "agent_model_generation_failed" in body["tools_used"]
    assert "agent_model_generation_failed:model_call_failed" in body["tools_used"]
    assert "Model generation unavailable." in body["answer"]
    assert "Reason: The model call failed before a response was produced." in body["answer"]
    assert "Evidence-based summary:" in body["answer"]
    assert "- Evidence for fallback answer." in body["answer"]
    assert "Task: Answer fallback question" in body["answer"]
    assert len(body["citations"]) == 1


@pytest.mark.asyncio
async def test_pipeline_agent_endpoint_surfaces_missing_model_key_with_fallback_marker(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

    response = await client.post(
        "/v1/pipeline/agents/run",
        json={
            "prompt": "Answer keyless question",
            "evidence": [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "page_number": 0,
                    "text": "Evidence for keyless fallback answer.",
                    "score": 0.9,
                    "source_tool": "bm25_search",
                }
            ],
            "upstream_outputs": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "agent_model_generation_failed" in body["tools_used"]
    assert "agent_model_generation_failed:missing_openai_api_key" in body["tools_used"]
    assert "Model generation unavailable." in body["answer"]
    assert "Reason: No OpenAI API key is configured for the backend." in body["answer"]
    assert "Task: Answer keyless question" in body["answer"]


@pytest.mark.asyncio
async def test_pipeline_agent_endpoint_surfaces_empty_model_output_with_fallback_marker(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _empty_runner_run(*_args: object, **_kwargs: object) -> _FakeRunResult:
        return _FakeRunResult("")

    monkeypatch.setattr("agents.Runner.run", staticmethod(_empty_runner_run))

    response = await client.post(
        "/v1/pipeline/agents/run",
        json={
            "prompt": "Answer empty-output question",
            "evidence": [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "page_number": 0,
                    "text": "Evidence for empty output fallback answer.",
                    "score": 0.9,
                    "source_tool": "bm25_search",
                }
            ],
            "upstream_outputs": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "agent_model_generation_failed" in body["tools_used"]
    assert "agent_model_generation_failed:empty_model_output" in body["tools_used"]
    assert "Model generation unavailable." in body["answer"]
    assert "Reason: The model returned an empty output." in body["answer"]
    assert "Task: Answer empty-output question" in body["answer"]


@pytest.mark.asyncio
async def test_pipeline_agent_endpoint_classifies_quota_error(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _quota_runner_run(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("Error code: 429 insufficient_quota")

    monkeypatch.setattr("agents.Runner.run", staticmethod(_quota_runner_run))

    response = await client.post(
        "/v1/pipeline/agents/run",
        json={
            "prompt": "Answer quota question",
            "evidence": [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "page_number": 0,
                    "text": "Evidence for quota fallback answer.",
                    "score": 0.9,
                    "source_tool": "bm25_search",
                }
            ],
            "upstream_outputs": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "agent_model_generation_failed" in body["tools_used"]
    assert "agent_model_generation_failed:openai_quota_exhausted" in body["tools_used"]
    assert "Reason: OpenAI API quota is exhausted for the configured key." in body["answer"]


@pytest.mark.asyncio
async def test_pipeline_agent_endpoint_classifies_long_quota_error_without_truncation_loss(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_prefix = "x" * 260

    async def _quota_runner_run(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError(f"{long_prefix} insufficient_quota")

    monkeypatch.setattr("agents.Runner.run", staticmethod(_quota_runner_run))

    response = await client.post(
        "/v1/pipeline/agents/run",
        json={
            "prompt": "Answer long quota question",
            "evidence": [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "page_number": 0,
                    "text": "Evidence for long quota fallback answer.",
                    "score": 0.9,
                    "source_tool": "bm25_search",
                }
            ],
            "upstream_outputs": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "agent_model_generation_failed:openai_quota_exhausted" in body["tools_used"]


@pytest.mark.asyncio
async def test_pipeline_agent_endpoint_does_not_false_positive_on_generic_quota_text(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _generic_quota_runner_run(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("Disk quota exceeded while writing temp file")

    monkeypatch.setattr("agents.Runner.run", staticmethod(_generic_quota_runner_run))

    response = await client.post(
        "/v1/pipeline/agents/run",
        json={
            "prompt": "Answer generic quota question",
            "evidence": [
                {
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "page_number": 0,
                    "text": "Evidence for generic quota fallback answer.",
                    "score": 0.9,
                    "source_tool": "bm25_search",
                }
            ],
            "upstream_outputs": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "agent_model_generation_failed:model_call_failed" in body["tools_used"]
    assert "agent_model_generation_failed:openai_quota_exhausted" not in body["tools_used"]


@pytest.mark.asyncio
async def test_pipeline_agent_endpoint_uses_selected_tools_to_retrieve_evidence(
    client: AsyncClient,
) -> None:
    old_ingest = await client.post(
        "/v1/rag/documents",
        files={
            "file": (
                "old.md",
                b"# Old\n\nThis should not be cited by the new run.\n",
                "text/markdown",
            )
        },
    )
    assert old_ingest.status_code == 201

    ingest = await client.post(
        "/v1/rag/documents",
        files={
            "file": (
                "notes.md",
                b"# Notes\n\nAttention retrieves relevant context.\n",
                "text/markdown",
            )
        },
    )
    assert ingest.status_code == 201
    document_id = ingest.json()["document_id"]

    response = await client.post(
        "/v1/pipeline/agents/run",
        json={
            "prompt": "What does this document say about attention?",
            "tools": ["bm25_search", "read_document"],
            "document_ids": [document_id],
            "evidence": [],
            "upstream_outputs": [],
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert set(body["tools_used"]) >= {"bm25_search", "read_document"}
    assert len(body["evidence"]) >= 1
    assert len(body["citations"]) >= 1
    assert {chunk["document_id"] for chunk in body["evidence"]} == {document_id}
    assert {citation["document_id"] for citation in body["citations"]} == {document_id}


@pytest.mark.asyncio
async def test_pipeline_run_stream_executes_graph(client: AsyncClient) -> None:
    spec = {
        "query": "Summarize the document",
        "nodes": [
            {"id": "ing-1", "type": "ingest", "label": "Ingest", "config": {}},
            {
                "id": "search-1",
                "type": "bm25_search",
                "label": "BM25",
                "config": {"query_template": "{query}", "top_k": 4},
            },
            {
                "id": "agent-1",
                "type": "agent",
                "label": "Agent",
                "config": {"prompt_template": "Use evidence for: {query}"},
            },
            {"id": "out-1", "type": "output", "label": "Output", "config": {}},
        ],
        "edges": [
            {"source": "ing-1", "target": "search-1"},
            {"source": "search-1", "target": "agent-1"},
            {"source": "agent-1", "target": "out-1"},
        ],
    }

    response = await client.post(
        "/v1/pipeline/runs/stream",
        files=[
            ("spec", (None, json.dumps(spec))),
            ("file:ing-1", ("notes.md", b"# Notes\n\nAttention works well.\n", "text/markdown")),
        ],
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    lines = [line for line in response.text.splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]

    assert events[0]["event"] == "run_started"
    assert any(
        event["event"] == "node_completed" and event["node_id"] == "out-1" for event in events
    )
    assert events[-1]["event"] == "run_completed"


@pytest.mark.asyncio
async def test_pipeline_run_stream_agent_tools_can_retrieve_without_search_node(
    client: AsyncClient,
) -> None:
    old_ingest = await client.post(
        "/v1/rag/documents",
        files={
            "file": (
                "old.md",
                b"# Old\n\nThis should not be cited by the pipeline run.\n",
                "text/markdown",
            )
        },
    )
    assert old_ingest.status_code == 201

    spec = {
        "query": "Summarize attention",
        "nodes": [
            {"id": "ing-1", "type": "ingest", "label": "Ingest", "config": {}},
            {
                "id": "agent-1",
                "type": "agent",
                "label": "Agent",
                "config": {
                    "prompt_template": "Use tools for: {query}",
                    "tools": ["bm25_search", "read_document"],
                },
            },
            {"id": "out-1", "type": "output", "label": "Output", "config": {}},
        ],
        "edges": [
            {"source": "ing-1", "target": "agent-1"},
            {"source": "agent-1", "target": "out-1"},
        ],
    }

    response = await client.post(
        "/v1/pipeline/runs/stream",
        files=[
            ("spec", (None, json.dumps(spec))),
            (
                "file:ing-1",
                (
                    "notes.md",
                    b"# Notes\n\nAttention works with document context.\n",
                    "text/markdown",
                ),
            ),
        ],
    )

    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]
    ingest_completed = next(
        event
        for event in events
        if event["event"] == "node_completed" and event["node_id"] == "ing-1"
    )
    ingest_document_id = ingest_completed["output"]["documents"][0]["document_id"]

    agent_completed = next(
        event
        for event in events
        if event["event"] == "node_completed" and event["node_id"] == "agent-1"
    )
    assert agent_completed["output"]["evidence_count"] >= 1
    assert set(agent_completed["output"]["tools_used"]) >= {"bm25_search", "read_document"}
    agent_output = agent_completed["output"]["agent_output"]
    assert {chunk["document_id"] for chunk in agent_output["evidence"]} == {ingest_document_id}
    assert {citation["document_id"] for citation in agent_completed["output"]["citations"]} == {
        ingest_document_id
    }
    assert events[-1]["event"] == "run_completed"


@pytest.mark.asyncio
async def test_pipeline_run_stream_with_input_node_and_file(client: AsyncClient) -> None:
    spec = {
        "query": "Summarize the document",
        "nodes": [
            {
                "id": "input-1",
                "type": "input",
                "label": "Input",
                "config": {"prompt_text": "Summarize the document"},
            },
            {
                "id": "agent-1",
                "type": "agent",
                "label": "Agent",
                "config": {
                    "prompt_template": "Use evidence for: {query}",
                    "tools": ["bm25_search", "read_document"],
                },
            },
            {"id": "out-1", "type": "output", "label": "Output", "config": {}},
        ],
        "edges": [
            {"source": "input-1", "target": "agent-1"},
            {"source": "agent-1", "target": "out-1"},
        ],
    }

    response = await client.post(
        "/v1/pipeline/runs/stream",
        files=[
            ("spec", (None, json.dumps(spec))),
            (
                "file:input-1",
                ("notes.md", b"# Notes\n\nAttention mechanisms are powerful.\n", "text/markdown"),
            ),
        ],
    )

    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]

    assert events[0]["event"] == "run_started"

    input_completed = next(
        event
        for event in events
        if event["event"] == "node_completed" and event["node_id"] == "input-1"
    )
    assert input_completed["output"]["prompt_text"] == "Summarize the document"
    assert len(input_completed["output"]["documents"]) == 1

    assert any(
        event["event"] == "node_completed" and event["node_id"] == "out-1" for event in events
    )
    assert events[-1]["event"] == "run_completed"


@pytest.mark.asyncio
async def test_pipeline_run_stream_with_input_node_prompt_only(client: AsyncClient) -> None:
    spec = {
        "query": "What is attention?",
        "nodes": [
            {
                "id": "input-1",
                "type": "input",
                "label": "Input",
                "config": {"prompt_text": "What is attention?"},
            },
            {
                "id": "agent-1",
                "type": "agent",
                "label": "Agent",
                "config": {"prompt_template": "{query}"},
            },
            {"id": "out-1", "type": "output", "label": "Output", "config": {}},
        ],
        "edges": [
            {"source": "input-1", "target": "agent-1"},
            {"source": "agent-1", "target": "out-1"},
        ],
    }

    response = await client.post(
        "/v1/pipeline/runs/stream",
        files=[("spec", (None, json.dumps(spec)))],
    )

    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]

    assert events[0]["event"] == "run_started"

    input_completed = next(
        event
        for event in events
        if event["event"] == "node_completed" and event["node_id"] == "input-1"
    )
    assert input_completed["output"]["prompt_text"] == "What is attention?"
    assert "documents" not in input_completed["output"]

    assert events[-1]["event"] == "run_completed"


@pytest.mark.asyncio
async def test_pipeline_pause_returns_404_for_unknown_run(client: AsyncClient) -> None:
    response = await client.post("/v1/pipeline/runs/nonexistent-id/pause")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "run_not_found"


@pytest.mark.asyncio
async def test_pipeline_resume_returns_404_for_unknown_run(client: AsyncClient) -> None:
    response = await client.post("/v1/pipeline/runs/nonexistent-id/resume")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "run_not_found"


@pytest.mark.asyncio
async def test_pipeline_run_stream_emits_run_id_in_started_event(client: AsyncClient) -> None:
    spec = {
        "query": "Test run id",
        "nodes": [
            {
                "id": "input-1",
                "type": "input",
                "label": "Input",
                "config": {"prompt_text": "Test run id"},
            },
            {"id": "out-1", "type": "output", "label": "Output", "config": {}},
        ],
        "edges": [{"source": "input-1", "target": "out-1"}],
    }

    response = await client.post(
        "/v1/pipeline/runs/stream",
        files=[("spec", (None, json.dumps(spec)))],
    )
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]

    started = events[0]
    assert started["event"] == "run_started"
    assert isinstance(started["run_id"], str)
    assert len(started["run_id"]) > 0


@pytest.mark.asyncio
async def test_pipeline_run_stream_rejects_invalid_spec(client: AsyncClient) -> None:
    response = await client.post("/v1/pipeline/runs/stream", files=[("spec", (None, "{"))])
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "pipeline_spec_invalid"
