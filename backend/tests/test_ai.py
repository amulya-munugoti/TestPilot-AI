import asyncio
import importlib
from types import SimpleNamespace

from app.ai import analyze_failure


def test_ai_response_is_real_and_receives_redacted_traceback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    module = importlib.import_module("google.genai")
    seen = {}

    class Models:
        async def generate_content(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(text="The assertion's expected value is incorrect.")

    class Client:
        def __init__(self, api_key):
            assert api_key == "test-only-key"
            self.aio = SimpleNamespace(models=Models())

    monkeypatch.setattr(module, "Client", Client)
    result = asyncio.run(analyze_failure("api_key=visible-secret\nassert 4 == 5"))
    assert result == {"status": "completed", "content": "The assertion's expected value is incorrect."}
    assert "visible-secret" not in seen["contents"]
    assert "[REDACTED]" in seen["contents"]


def test_ai_provider_error_returns_unavailable_not_fake_analysis(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-key")
    module = importlib.import_module("google.genai")

    class Models:
        async def generate_content(self, **kwargs):
            raise TimeoutError("provider timeout")

    class Client:
        def __init__(self, api_key):
            self.aio = SimpleNamespace(models=Models())

    monkeypatch.setattr(module, "Client", Client)
    result = asyncio.run(analyze_failure("traceback"))
    assert result["status"] == "unavailable"
    assert "could not complete" in result["content"]
