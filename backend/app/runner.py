import os
import re
import subprocess
import sys
import time
from pathlib import Path

SAMPLE_ROOT = Path(__file__).resolve().parent.parent / "sample_project"
MAX_OUTPUT = 20_000


def run_sample_tests(timeout_seconds: int = 20) -> dict:
    """Run only the bundled, reviewed sample suite. Never accepts a client path or command."""
    started = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=short", str(SAMPLE_ROOT)],
            cwd=SAMPLE_ROOT,
            capture_output=True,
            text=True,
            timeout=max(2, min(timeout_seconds, 60)),
            shell=False,
            env={key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME") if key in os.environ} | {"PYTHONIOENCODING": "utf-8"},
        )
        output = (result.stdout + "\n" + result.stderr)[-MAX_OUTPUT:]
        counts = {key: 0 for key in ("passed", "failed", "skipped", "errors")}
        for match in re.finditer(r"(?:(\d+)\s+passed)?\s*(?:(\d+)\s+failed)?\s*(?:(\d+)\s+skipped)?\s*(?:(\d+)\s+error(?:s)?)?", output):
            if match.group(0).strip():
                values = match.groups()
                if any(values):
                    for key, value in zip(counts, values):
                        if value:
                            counts[key] = int(value)
        unavailable = "No module named pytest" in output or "can't open file" in output
        status = "error" if unavailable or result.returncode not in (0, 1) else ("failed" if result.returncode else "passed")
        if unavailable:
            counts["errors"] = max(counts["errors"], 1)
        return {**counts, "status": status, "duration_ms": round((time.perf_counter() - started) * 1000),
                "summary": "Sample tests completed" if status != "error" else "Pytest could not start; install backend dependencies",
                "output": output.strip() or "Pytest returned no output."}
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") + (exc.stderr or ""))
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return {"passed": 0, "failed": 0, "skipped": 0, "errors": 1, "status": "error",
                "duration_ms": round((time.perf_counter() - started) * 1000), "summary": "Test run timed out",
                "output": (output[-MAX_OUTPUT:] + "\nExecution exceeded the configured timeout.")[-MAX_OUTPUT:]}
    except OSError as exc:
        return {"passed": 0, "failed": 0, "skipped": 0, "errors": 1, "status": "error",
                "duration_ms": round((time.perf_counter() - started) * 1000), "summary": "Unable to start Pytest",
                "output": str(exc)[:MAX_OUTPUT]}

