import subprocess

from app import runner


def test_timeout_is_saved_as_execution_error(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=2, output="partial output")
    monkeypatch.setattr(runner.subprocess, "run", timeout)
    result = runner.run_sample_tests(timeout_seconds=2)
    assert result["status"] == "error"
    assert result["errors"] == 1
    assert "timed out" in result["summary"].lower()
    assert "partial output" in result["output"]


def test_malformed_pytest_output_is_not_reported_as_passed(monkeypatch):
    def malformed(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 5, stdout="not pytest output", stderr="")
    monkeypatch.setattr(runner.subprocess, "run", malformed)
    result = runner.run_sample_tests()
    assert result["status"] == "error"
    assert result["passed"] == 0

