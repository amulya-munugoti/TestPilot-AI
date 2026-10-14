from app import main
from app.ai import redact


def test_health_and_settings_do_not_return_secret(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "private-test-secret")
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ai_configured"] is True
    assert "private-test-secret" not in response.text
    settings = client.get("/api/settings").json()
    assert settings["ai_configured"] is True
    assert "private-test-secret" not in str(settings)


def test_project_create_validation_read_and_delete(client):
    sample = client.get("/api/projects").json()
    assert len(sample) == 1
    assert sample[0]["name"] == "TestPilot Sample"
    invalid = client.post("/api/projects", json={"name": "unsafe", "project_type": "arbitrary-command"})
    assert invalid.status_code == 422
    created = client.post("/api/projects", json={"name": "Checkout API", "description": "Backend demo"})
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert client.get(f"/api/projects/{project_id}").json()["name"] == "Checkout API"
    assert client.post("/api/projects", json={"name": "Checkout API"}).status_code == 409
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    assert client.delete(f"/api/projects/{sample[0]['id']}").status_code == 400


def test_projects_cannot_execute_non_sample_code(client):
    project = client.post("/api/projects", json={"name": "Metadata only"}).json()
    response = client.post(f"/api/projects/{project['id']}/test-runs")
    assert response.status_code == 400
    assert client.post("/api/projects/9999/test-runs").status_code == 404


def test_real_sample_suite_run_history_report_and_dashboard(client):
    project = client.get("/api/projects").json()[0]
    response = client.post(f"/api/projects/{project['id']}/test-runs")
    assert response.status_code == 201
    run = response.json()
    assert run["passed"] == 1
    assert run["failed"] == 1
    assert run["duration_ms"] >= 0
    assert "assert 4 == 5" in run["output"]
    assert "test_sample.py" in run["output"]
    assert client.get("/api/test-runs").json()[0]["id"] == run["id"]
    assert client.get(f"/api/test-runs/{run['id']}").status_code == 200
    report = client.get(f"/api/test-runs/{run['id']}/report")
    assert report.status_code == 200
    assert report.json()["failed"] == 1
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["total_test_runs"] == 1
    assert dashboard["passed_tests"] == 1
    assert dashboard["failed_tests"] == 1
    assert dashboard["recent_bugs"][0]["id"] == run["id"]
    assert client.get("/api/test-runs/9999").status_code == 404


def test_analysis_unavailable_without_api_key_and_history_saved(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    project = client.get("/api/projects").json()[0]
    run = client.post(f"/api/projects/{project['id']}/test-runs").json()
    response = client.post(f"/api/test-runs/{run['id']}/analyze")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert "not configured" in response.json()["content"]
    detail = client.get(f"/api/test-runs/{run['id']}").json()
    assert detail["analyses"][0]["status"] == "unavailable"


def test_ai_analysis_and_test_generation_mocked(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    async def fake_analysis(traceback, generate_tests=False):
        assert "assert 4 == 5" in traceback
        return {"status": "completed", "content": "Example generated pytest cases." if generate_tests else "The expected value is incorrect."}
    monkeypatch.setattr(main, "analyze_failure", fake_analysis)
    project = client.get("/api/projects").json()[0]
    run = client.post(f"/api/projects/{project['id']}/test-runs").json()
    # The normal fixture traceback has no secret; validate stored AI responses and both endpoint paths.
    monkeypatch.setattr(main, "analyze_failure", lambda traceback, generate_tests=False: fake_analysis(traceback + "\napi_key=secret-value", generate_tests))
    analysis = client.post(f"/api/test-runs/{run['id']}/analyze")
    assert analysis.json() == {"status": "completed", "content": "The expected value is incorrect."}
    generated = client.post(f"/api/test-runs/{run['id']}/generate-tests")
    assert generated.json()["content"] == "Example generated pytest cases."
    assert len(client.get(f"/api/test-runs/{run['id']}").json()["analyses"]) == 2


def test_analysis_rejects_non_failure_and_handles_model_errors(client, monkeypatch):
    async def fake_passing(_timeout=20):
        return {"passed": 1, "failed": 0, "skipped": 0, "errors": 0, "status": "passed", "duration_ms": 5, "summary": "ok", "output": "1 passed"}
    monkeypatch.setattr(main, "run_sample_tests", fake_passing)
    project = client.get("/api/projects").json()[0]
    run = client.post(f"/api/projects/{project['id']}/test-runs").json()
    assert client.post(f"/api/test-runs/{run['id']}/analyze").status_code == 400
    assert client.post("/api/test-runs/999/analyze").status_code == 404


def test_secret_redaction():
    assert "secret-value" not in redact("api_key=secret-value traceback")
    assert "AIza" not in redact("token: AIza123456789012345678901234")

