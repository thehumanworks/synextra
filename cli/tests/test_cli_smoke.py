from __future__ import annotations

from typer.testing import CliRunner

from synextra_cli.main import app


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
