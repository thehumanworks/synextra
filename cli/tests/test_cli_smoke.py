from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from typer.testing import CliRunner

import synextra_cli.main as main
from synextra_cli.main import _require_api_key, app


def test_ingest_command_removed() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["ingest", "notes.txt"])

    assert result.exit_code != 0
    assert "No such command 'ingest'" in result.output


def test_query_requires_file_option() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["query", "What changed?"])

    assert result.exit_code != 0
    assert "Missing option '--file'" in result.output


def test_chat_requires_file_option() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["chat"])

    assert result.exit_code != 0
    assert "Missing option '--file'" in result.output


def test_research_mode_option_removed() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["research", "What changed?", "--mode", "hybrid"])

    assert result.exit_code != 0
    assert "No such option: --mode" in result.output


def test_synthesize_mode_option_removed() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["synthesize", "What changed?", "--mode", "hybrid"])

    assert result.exit_code != 0
    assert "No such option: --mode" in result.output


def test_require_api_key_accepts_azure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")

    assert _require_api_key(None) == "azure-test-key"


def test_query_help_includes_openai_compatibility_options() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["query", "--help"])

    assert result.exit_code == 0
    assert "--openai-base-url" in result.output
    assert "--openai-api" in result.output


def test_query_passes_openai_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, str | None] = {}

    @dataclass(frozen=True)
    class _FakeCitation:
        document_id: str = "doc"
        chunk_id: str = "chunk"
        page_number: int = 0
        supporting_quote: str = "quote"
        source_tool: str = "bm25_search"
        score: float = 1.0

        def model_dump(self) -> dict[str, str | int | float]:
            return {
                "document_id": self.document_id,
                "chunk_id": self.chunk_id,
                "page_number": self.page_number,
                "supporting_quote": self.supporting_quote,
                "source_tool": self.source_tool,
                "score": self.score,
            }

    @dataclass(frozen=True)
    class _FakeReview:
        verdict: str = "unknown"
        iterations: int = 0
        feedback: str | None = None
        citation_ok: bool = True
        citation_issues: list[str] = field(default_factory=list)

    @dataclass(frozen=True)
    class _FakeQueryResult:
        session_id: str = "cli"
        mode: str = "hybrid"
        answer: str = "ok"
        tools_used: list[str] = field(default_factory=list)
        citations: list[_FakeCitation] = field(default_factory=list)
        review: _FakeReview = field(default_factory=_FakeReview)

    class _FakeSynextra:
        def __init__(
            self,
            openai_api_key: str | None = None,
            *,
            openai_base_url: str | None = None,
            openai_api: str | None = None,
            model: str | None = None,
        ) -> None:
            captured["openai_api_key"] = openai_api_key
            captured["openai_base_url"] = openai_base_url
            captured["openai_api"] = openai_api
            captured["model"] = model

        def query(
            self,
            prompt: str,
            *,
            session_id: str = "cli",
            reasoning_effort: str = "medium",
        ) -> _FakeQueryResult:
            _ = prompt
            _ = session_id
            _ = reasoning_effort
            return _FakeQueryResult(
                tools_used=["bm25_search"],
                citations=[_FakeCitation()],
                review=_FakeReview(citation_issues=[]),
            )

    monkeypatch.setattr(main, "Synextra", _FakeSynextra)
    monkeypatch.setattr(main, "_ingest_all", lambda _client, _documents: [])

    document = tmp_path / "notes.txt"
    document.write_text("hello", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "query",
            "What changed?",
            "--file",
            str(document),
            "--openai-api-key",
            "test-key",
            "--openai-base-url",
            "https://example-resource.openai.azure.com/openai/v1/",
            "--openai-api",
            "chat_completions",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured["openai_api_key"] == "test-key"
    assert captured["openai_base_url"] == "https://example-resource.openai.azure.com/openai/v1/"
    assert captured["openai_api"] == "chat_completions"
