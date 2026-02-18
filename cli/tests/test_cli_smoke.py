from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from synextra_cli.main import app


def test_ingest_text_file(tmp_path: Path) -> None:
    runner = CliRunner()
    doc = tmp_path / "notes.txt"
    doc.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    result = runner.invoke(app, ["ingest", str(doc)])

    assert result.exit_code == 0
    assert "document_id=" in result.stdout
    assert "chunks=" in result.stdout
