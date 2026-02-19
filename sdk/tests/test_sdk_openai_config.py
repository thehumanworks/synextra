from __future__ import annotations

import os

import pytest

import synextra.client as client_module
from synextra import Synextra, SynextraConfigurationError


def _clear_openai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "AZURE_OPENAI_BASE_URL",
        "AZURE_OPENAI_ENDPOINT",
        "SYNEXTRA_OPENAI_API",
    ):
        monkeypatch.delenv(name, raising=False)


def test_synextra_accepts_azure_key_env_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test-key")

    client = Synextra(openai_api_key=None)
    client._ensure_openai_key()

    assert os.getenv("OPENAI_API_KEY") == "azure-test-key"


def test_synextra_sets_openai_base_url_from_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_openai_env(monkeypatch)

    _ = Synextra(
        openai_api_key="test-key",
        openai_base_url=" https://example-resource.openai.azure.com/openai/v1/ ",
    )

    assert os.getenv("OPENAI_BASE_URL") == "https://example-resource.openai.azure.com/openai/v1/"


def test_synextra_derives_base_url_from_azure_endpoint_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example-resource.openai.azure.com")

    _ = Synextra(openai_api_key="test-key")

    assert os.getenv("OPENAI_BASE_URL") == "https://example-resource.openai.azure.com/openai/v1/"


def test_synextra_rejects_invalid_openai_api_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SYNEXTRA_OPENAI_API", "invalid-mode")

    with pytest.raises(SynextraConfigurationError, match="Invalid OpenAI API mode"):
        _ = Synextra(openai_api_key=None)


def test_synextra_configures_openai_api_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    captured: dict[str, str] = {}

    def _fake_set_default_openai_api(value: str) -> None:
        captured["value"] = value

    monkeypatch.setattr(client_module, "set_default_openai_api", _fake_set_default_openai_api)

    _ = Synextra(openai_api_key=None, openai_api="chat_completions")

    assert captured["value"] == "chat_completions"
