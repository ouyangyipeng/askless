import time
from pathlib import Path

from fastapi.testclient import TestClient

from askless.api import create_app
from askless.llm import Settings
from askless.session import Run


def test_http_workflow_and_download_survive_restart(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path, Settings()), base_url="http://127.0.0.1:8765") as client:
        config = client.get("/api/config").json()
        headers = {"X-AskLess-Token": config["token"]}
        response = client.post("/api/runs", json={"title": "导入示例联系人", "csv_text": config["sample_csv"], "mode": "offline"}, headers=headers)
        assert response.status_code == 202
        run_id = response.json()["id"]
        run = wait_for(client, run_id, "ready")
        selected = {g.key: g.spec.options[0].value for g in run.groups if g.status == "pending"}
        response = client.post(f"/api/runs/{run_id}/answers", json={"answers": selected, "revision": run.revision}, headers=headers)
        assert response.status_code == 202
        completed = wait_for(client, run_id, "completed")
        assert len(completed.receipts) == 3
        downloaded = client.get(f"/api/runs/{run_id}/export")
        assert downloaded.status_code == 200
        assert downloaded.text.startswith("\ufeffemail,name")
        assert client.get(f"/api/runs/{run_id}/evidence").status_code == 200
    with TestClient(create_app(tmp_path, Settings()), base_url="http://127.0.0.1:8765") as client:
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "completed"


def wait_for(client: TestClient, run_id: str, expected: str) -> Run:
    for _ in range(100):
        data = Run.model_validate(client.get(f"/api/runs/{run_id}").json())
        if data.status == expected:
            return data
        assert data.status != "failed", data.error
        time.sleep(0.01)
    raise AssertionError(f"Run did not reach {expected}")


def test_cross_site_writes_and_missing_token_are_rejected(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path, Settings()), base_url="http://127.0.0.1:8765") as client:
        token = client.get("/api/config").json()["token"]
        assert client.post("/api/runs", json={}).status_code == 403
        assert client.post("/api/runs", json={}, headers={"X-AskLess-Token": token, "Origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/config", headers={"Host": "evil.example"}).status_code == 400


def test_unknown_runs_and_oversized_body_return_safe_errors(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path, Settings()), base_url="http://127.0.0.1:8765") as client:
        token = client.get("/api/config").json()["token"]
        assert client.get("/api/runs/missing").status_code == 404
        assert client.post("/api/runs", content="x" * 600_000, headers={"X-AskLess-Token": token}).status_code == 413
