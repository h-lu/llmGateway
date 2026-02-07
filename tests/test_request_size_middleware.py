from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from gateway.app.middleware.request_size import RequestSizeLimitMiddleware


def test_request_size_middleware_does_not_mask_exceptions():
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, max_body_size=1024)

    @app.post("/boom")
    async def boom(_: Request):
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/boom", json={"x": 1})

    # If middleware masks exceptions, this would be 413.
    assert resp.status_code == 500


def test_request_size_middleware_returns_json_413_on_oversize_body():
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, max_body_size=10)

    @app.post("/echo")
    async def echo(req: Request):
        return {"size": len(await req.body())}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/echo", content=b"x" * 11)

    assert resp.status_code == 413
    assert resp.headers.get("content-type", "").startswith("application/json")
    assert "detail" in resp.json()
