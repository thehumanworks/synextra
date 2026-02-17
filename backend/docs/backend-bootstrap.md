# Backend Bootstrap Notes

## Scope

Initial backend scaffold with a typed FastAPI app, `/health` endpoint, and async tests.

## Key References

- FastAPI path operations and response models: <https://fastapi.tiangolo.com/tutorial/path-operation-configuration/>
- HTTPX async client usage: <https://www.python-httpx.org/async/>
- pytest-asyncio concepts: <https://pytest-asyncio.readthedocs.io/en/latest/>
- Ruff rule selection and formatter configuration: <https://docs.astral.sh/ruff/>

## Why This Shape

- Use an app factory (`create_app`) to support test isolation and configurable service naming.
- Keep routing isolated in `api/health.py` for modular growth.
- Keep tests async-first using `httpx.ASGITransport` to avoid network-bound test flakiness.
