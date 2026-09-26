import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from services.public.app.main import app
from services.shared import clients


def test_hosted_api_requires_code_and_only_forwards_dashboard_routes(monkeypatch):
    monkeypatch.setenv("DASHBOARD_ACCESS_CODE", "demo-secret")
    origin = FastAPI()
    seen = []
    @origin.api_route("/{path:path}", methods=["GET", "POST"])
    async def receive(path: str, request: Request):
        seen.append((path, request.method, await request.body()))
        return {"ok": True}
    clients.register_asgi("orchestrator", origin)
    tc = TestClient(app)
    auth = {"Authorization": "Bearer demo-secret"}
    try:
        assert tc.get("/dashboard/health").status_code == 401
        assert tc.post("/dashboard/transfers", json={}).status_code == 401
        assert tc.get("/dashboard/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert seen == []
        for path in ["health", "centers", "transfers/abcdef1234"]:
            response = tc.get("/dashboard/" + path, headers=auth)
            assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        for path in ["transfers", "transfers/abcdef1234/accept"]:
            assert tc.post("/dashboard/" + path, json={"demo": True}, headers=auth).status_code == 200
            assert seen[-1][1:] == ("POST", b'{"demo":true}')
        for path in ["call", "bridge", "outbox", "results", "twins", "transfers/not-a-transfer"]:
            assert tc.post("/dashboard/" + path, json={}, headers=auth).status_code == 404
        assert tc.post("/dashboard/transfers", content=b'x' * 65537, headers=auth).status_code == 413
        monkeypatch.delenv("DASHBOARD_ACCESS_CODE")
        assert tc.get("/dashboard/health", headers=auth).status_code == 401
    finally:
        clients.clear()


def test_hosted_api_returns_clear_failure_when_backend_is_offline(monkeypatch):
    from services.public.app import dashboard
    monkeypatch.setenv("DASHBOARD_ACCESS_CODE", "demo-secret")
    def offline(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(dashboard, "client", offline)
    response = TestClient(app).get("/dashboard/health", headers={"Authorization": "Bearer demo-secret"})
    assert response.status_code == 503 and "offline" in response.text
