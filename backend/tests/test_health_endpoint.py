import importlib

import pytest
from httpx import AsyncClient

from synextra_backend.app import create_app, main

app_module = importlib.import_module("synextra_backend.app")


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok_payload(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "synextra-test"}


@pytest.mark.asyncio
async def test_health_endpoint_allows_query_params_without_breaking(
    client: AsyncClient,
) -> None:
    response = await client.get("/health?probe=true")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_endpoint_rejects_post(client: AsyncClient) -> None:
    response = await client.post("/health")

    assert response.status_code == 405


@pytest.mark.asyncio
async def test_unknown_route_returns_not_found(client: AsyncClient) -> None:
    response = await client.get("/not-a-real-route")

    assert response.status_code == 404


def test_create_app_rejects_blank_service_name() -> None:
    with pytest.raises(ValueError, match="service_name must not be empty"):
        create_app(service_name="  ")


def test_main_uses_safe_default_server_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SYNEXTRA_BACKEND_HOST", raising=False)
    monkeypatch.delenv("SYNEXTRA_BACKEND_PORT", raising=False)
    run_call: dict[str, object] = {}

    def fake_run(
        app_location: str,
        *,
        host: str,
        port: int,
        reload: bool,
    ) -> None:
        run_call["app_location"] = app_location
        run_call["host"] = host
        run_call["port"] = port
        run_call["reload"] = reload

    monkeypatch.setattr(app_module.uvicorn, "run", fake_run)

    main()

    assert run_call == {
        "app_location": "synextra_backend.app:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": False,
    }


def test_main_uses_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNEXTRA_BACKEND_HOST", "0.0.0.0")
    monkeypatch.setenv("SYNEXTRA_BACKEND_PORT", "9001")
    run_call: dict[str, object] = {}

    def fake_run(
        app_location: str,
        *,
        host: str,
        port: int,
        reload: bool,
    ) -> None:
        run_call["app_location"] = app_location
        run_call["host"] = host
        run_call["port"] = port
        run_call["reload"] = reload

    monkeypatch.setattr(app_module.uvicorn, "run", fake_run)

    main()

    assert run_call["host"] == "0.0.0.0"
    assert run_call["port"] == 9001
    assert run_call["reload"] is False


def test_main_rejects_non_positive_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNEXTRA_BACKEND_PORT", "0")

    with pytest.raises(ValueError, match="must be greater than zero"):
        main()
