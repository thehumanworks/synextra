from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from synextra import ResearchResult, Synextra
from synextra.schemas.rag_chat import ReasoningEffort

app = typer.Typer(add_completion=False, help="Synextra CLI (SDK-powered).")


def _require_api_key(provided: str | None) -> str:
    if provided and provided.strip():
        return provided.strip()
    env = os.getenv("OPENAI_API_KEY", "").strip()
    if env:
        return env
    raise typer.BadParameter(
        "Missing OpenAI API key. Provide --openai-api-key or set OPENAI_API_KEY."
    )


def _print_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str))


def _ingest_all(client: Synextra, documents: list[Path]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for document in documents:
        res = client.ingest(document)
        results.append(
            {
                "document_id": res.document_id,
                "filename": res.filename,
                "checksum_sha256": res.checksum_sha256,
                "page_count": res.page_count,
                "chunk_count": res.chunk_count,
                "indexed_chunk_count": res.indexed_chunk_count,
            }
        )
    return results


OptionalDocumentOption = Annotated[
    list[Path] | None,
    typer.Option(
        "--file",
        "--doc",
        "--document",
        "--pdf",
        exists=True,
        readable=True,
        dir_okay=False,
        help="Document(s) to ingest for this run (ephemeral store).",
    ),
]


@app.command()
def query(
    prompt: Annotated[str, typer.Argument(help="Question/prompt to answer.")],
    documents: Annotated[
        list[Path],
        typer.Option(
            "--file",
            "--doc",
            "--document",
            "--pdf",
            exists=True,
            readable=True,
            dir_okay=False,
            help="Document(s) to ingest for this query run (required, ephemeral store).",
        ),
    ],
    openai_api_key: Annotated[
        str | None,
        typer.Option("--openai-api-key", envvar="OPENAI_API_KEY", help="OpenAI API key."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="Override SYNEXTRA_CHAT_MODEL for this run."),
    ] = None,
    session_id: Annotated[
        str,
        typer.Option("--session-id", help="Conversation/session id."),
    ] = "cli",
    reasoning_effort: Annotated[
        ReasoningEffort,
        typer.Option(
            "--reasoning-effort",
            help="none|low|medium|high|xhigh (passed through to openai-agents).",
        ),
    ] = "medium",
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON output.")] = False,
) -> None:
    """Ingest required documents and run the full research->review->synthesize pipeline."""

    key = _require_api_key(openai_api_key)
    client = Synextra(openai_api_key=key, model=model)

    ingest_results = _ingest_all(client, documents)

    result = client.query(
        prompt,
        session_id=session_id,
        reasoning_effort=reasoning_effort,
    )

    if json_output:
        _print_json(
            {
                "ingested": ingest_results,
                "session_id": result.session_id,
                "mode": result.mode,
                "answer": result.answer,
                "tools_used": result.tools_used,
                "citations": [c.model_dump() for c in result.citations],
                "review": {
                    "verdict": result.review.verdict,
                    "iterations": result.review.iterations,
                    "feedback": result.review.feedback,
                    "citation_ok": result.review.citation_ok,
                    "citation_issues": result.review.citation_issues,
                },
            }
        )
        return

    typer.echo(result.answer)


@app.command()
def research(
    prompt: Annotated[str, typer.Argument(help="Question/prompt to research.")],
    documents: OptionalDocumentOption = None,
    openai_api_key: Annotated[
        str | None,
        typer.Option("--openai-api-key", envvar="OPENAI_API_KEY", help="OpenAI API key."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="Override SYNEXTRA_CHAT_MODEL for this run."),
    ] = None,
    session_id: Annotated[
        str,
        typer.Option("--session-id", help="Conversation/session id."),
    ] = "cli",
    reasoning_effort: Annotated[
        ReasoningEffort,
        typer.Option(
            "--reasoning-effort",
            help="none|low|medium|high|xhigh (passed through to openai-agents).",
        ),
    ] = "medium",
    max_citations: Annotated[int, typer.Option("--max-citations", min=1, max=50)] = 8,
    json_output: Annotated[bool, typer.Option("--json", help="Emit JSON output.")] = False,
) -> None:
    """Run research only (collect evidence + citations + agent events)."""

    key = _require_api_key(openai_api_key)
    client = Synextra(openai_api_key=key, model=model)

    ingest_results: list[dict[str, object]] = []
    if documents:
        ingest_results = _ingest_all(client, documents)

    res: ResearchResult = client.research(
        prompt,
        session_id=session_id,
        reasoning_effort=reasoning_effort,
    )

    review = client.review(res)
    citations = [c.model_dump() for c in res.citations[:max_citations]]

    if json_output:
        _print_json(
            {
                "ingested": ingest_results,
                "session_id": res.session_id,
                "mode": res.mode,
                "tools_used": res.tools_used,
                "citations": citations,
                "events": [e.model_dump() for e in res.events],
                "review": {
                    "verdict": review.verdict,
                    "iterations": review.iterations,
                    "feedback": review.feedback,
                    "citation_ok": review.citation_ok,
                    "citation_issues": review.citation_issues,
                },
            }
        )
        return

    typer.echo(f"Tools used: {', '.join(res.tools_used) if res.tools_used else '(none)'}")
    typer.echo(
        f"Review: {review.verdict} (iterations={review.iterations})"
        + (f"\nFeedback: {review.feedback}" if review.feedback else "")
    )
    typer.echo("\nTop citations:")
    for idx, citation in enumerate(citations, start=1):
        quote = str(citation.get("supporting_quote", ""))
        typer.echo(
            f"[{idx}] page={citation.get('page_number')} "
            f"tool={citation.get('source_tool')} score={citation.get('score')}\n"
            f"    {quote}"
        )


@app.command()
def synthesize(
    prompt: Annotated[str, typer.Argument(help="Question/prompt to answer.")],
    documents: OptionalDocumentOption = None,
    openai_api_key: Annotated[
        str | None,
        typer.Option("--openai-api-key", envvar="OPENAI_API_KEY", help="OpenAI API key."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="Override SYNEXTRA_CHAT_MODEL for this run."),
    ] = None,
    session_id: Annotated[
        str,
        typer.Option("--session-id", help="Conversation/session id."),
    ] = "cli",
    reasoning_effort: Annotated[
        ReasoningEffort,
        typer.Option(
            "--reasoning-effort",
            help="none|low|medium|high|xhigh (passed through to openai-agents).",
        ),
    ] = "medium",
) -> None:
    """Explicit pipeline: research -> synthesize (prints the final answer)."""

    key = _require_api_key(openai_api_key)
    client = Synextra(openai_api_key=key, model=model)

    if documents:
        _ = _ingest_all(client, documents)

    research_res = client.research(
        prompt,
        session_id=session_id,
        reasoning_effort=reasoning_effort,
    )

    synthesis = client.synthesize(prompt, research_res, reasoning_effort=reasoning_effort)
    typer.echo(synthesis.answer)


@app.command()
def chat(
    documents: Annotated[
        list[Path],
        typer.Option(
            "--file",
            "--doc",
            "--document",
            "--pdf",
            exists=True,
            readable=True,
            dir_okay=False,
            help="Document(s) to ingest before starting the chat (required).",
        ),
    ],
    openai_api_key: Annotated[
        str | None,
        typer.Option("--openai-api-key", envvar="OPENAI_API_KEY", help="OpenAI API key."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="Override SYNEXTRA_CHAT_MODEL for this session."),
    ] = None,
    session_id: Annotated[
        str,
        typer.Option("--session-id", help="Conversation/session id."),
    ] = "chat",
    reasoning_effort: Annotated[
        ReasoningEffort,
        typer.Option(
            "--reasoning-effort",
            help="none|low|medium|high|xhigh (passed through to openai-agents).",
        ),
    ] = "medium",
) -> None:
    """Interactive chat loop (keeps the in-memory store for multiple queries)."""

    key = _require_api_key(openai_api_key)
    client = Synextra(openai_api_key=key, model=model)

    ingested = _ingest_all(client, documents)
    typer.echo(f"Ingested {len(ingested)} document(s).")

    typer.echo("Enter prompts. Type 'exit' or 'quit' to leave.")

    while True:
        try:
            text = typer.prompt(">")
        except EOFError:
            typer.echo("\nBye.")
            raise typer.Exit(code=0) from None
        except KeyboardInterrupt:
            typer.echo("\nBye.")
            raise typer.Exit(code=0) from None

        if text.strip().lower() in {"exit", "quit"}:
            raise typer.Exit(code=0)

        res = client.query(
            text,
            session_id=session_id,
            reasoning_effort=reasoning_effort,
        )
        typer.echo(res.answer)
        typer.echo("")


if __name__ == "__main__":
    app()
