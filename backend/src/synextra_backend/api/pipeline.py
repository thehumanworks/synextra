from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.datastructures import UploadFile
from synextra.schemas.pipeline import (
    PipelineAgentOutputEnvelope,
    PipelineAgentRunRequest,
    PipelineBm25SearchRequest,
    PipelineEvidenceResponse,
    PipelineParallelSearchRequest,
    PipelineReadDocumentRequest,
    PipelineRunSpec,
)
from synextra.services.pipeline_runtime import PipelineRuntime

from synextra_backend.schemas.errors import ApiErrorResponse, error_response


def _get_pipeline_runtime(request: Request) -> PipelineRuntime:
    runtime = getattr(request.app.state, "pipeline_runtime", None)
    if runtime is None:  # pragma: no cover
        raise RuntimeError("Pipeline runtime not configured")
    return cast(PipelineRuntime, runtime)


PIPELINE_RUNTIME_DEP = Depends(_get_pipeline_runtime)


def build_pipeline_router() -> APIRouter:
    router = APIRouter(prefix="/v1/pipeline", tags=["pipeline"])

    @router.post(
        "/tools/bm25-search",
        response_model=PipelineEvidenceResponse,
        status_code=200,
        summary="Run BM25 search tool",
    )
    async def bm25_search(
        body: PipelineBm25SearchRequest,
        runtime: PipelineRuntime = PIPELINE_RUNTIME_DEP,
    ) -> PipelineEvidenceResponse:
        evidence = runtime.bm25_search(
            query=body.query,
            top_k=body.top_k,
            document_ids=body.document_ids,
        )
        return PipelineEvidenceResponse(evidence=evidence)

    @router.post(
        "/tools/read-document",
        response_model=PipelineEvidenceResponse,
        status_code=200,
        summary="Run read_document tool",
    )
    async def read_document(
        body: PipelineReadDocumentRequest,
        runtime: PipelineRuntime = PIPELINE_RUNTIME_DEP,
    ) -> PipelineEvidenceResponse:
        evidence = runtime.read_document(
            page=body.page,
            start_line=body.start_line,
            end_line=body.end_line,
            document_id=body.document_id,
        )
        return PipelineEvidenceResponse(evidence=evidence)

    @router.post(
        "/tools/parallel-search",
        response_model=PipelineEvidenceResponse,
        status_code=200,
        summary="Run parallel_search tool",
    )
    async def parallel_search(
        body: PipelineParallelSearchRequest,
        runtime: PipelineRuntime = PIPELINE_RUNTIME_DEP,
    ) -> PipelineEvidenceResponse:
        evidence = await runtime.parallel_search(body)
        return PipelineEvidenceResponse(evidence=evidence)

    @router.post(
        "/agents/run",
        response_model=PipelineAgentOutputEnvelope,
        status_code=200,
        summary="Run an agent step using upstream evidence and agent outputs",
    )
    async def run_agent(
        body: PipelineAgentRunRequest,
        runtime: PipelineRuntime = PIPELINE_RUNTIME_DEP,
    ) -> PipelineAgentOutputEnvelope:
        return runtime.run_agent(body)

    @router.post(
        "/runs/stream",
        response_model=None,
        status_code=200,
        responses={400: {"model": ApiErrorResponse}},
        summary="Execute a pipeline DAG and stream per-node lifecycle events (NDJSON)",
    )
    async def run_stream(
        request: Request,
        runtime: PipelineRuntime = PIPELINE_RUNTIME_DEP,
    ) -> StreamingResponse | JSONResponse:
        form = await request.form()
        spec_value = form.get("spec")
        if not isinstance(spec_value, str):
            error_payload = error_response(
                code="pipeline_spec_required",
                message="Form field 'spec' must contain JSON",
                recoverable=True,
            )
            return JSONResponse(status_code=400, content=error_payload.model_dump())

        try:
            spec_data = json.loads(spec_value)
            spec = PipelineRunSpec.model_validate(spec_data)
        except Exception as exc:
            error_payload = error_response(
                code="pipeline_spec_invalid",
                message=f"Invalid pipeline spec: {exc}",
                recoverable=True,
            )
            return JSONResponse(status_code=400, content=error_payload.model_dump())

        files_by_node: dict[str, tuple[str, str | None, bytes]] = {}
        for key, value in form.multi_items():
            if not key.startswith("file:"):
                continue
            if not isinstance(value, UploadFile):
                continue
            node_id = key.removeprefix("file:")
            file_bytes = await value.read()
            files_by_node[node_id] = (
                value.filename or "upload",
                value.content_type,
                file_bytes,
            )

        async def stream_events() -> AsyncIterator[str]:
            async for event in runtime.run_stream(spec=spec, files_by_node=files_by_node):
                yield event.model_dump_json() + "\n"

        return StreamingResponse(
            stream_events(),
            media_type="application/x-ndjson",
            headers={
                "cache-control": "no-cache",
                "x-accel-buffering": "no",
            },
        )

    return router
