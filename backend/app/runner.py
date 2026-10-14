import os
import re
import subprocess
import sys
import time
from pathlib import Path

SAMPLE_ROOT = Path(__file__).resolve().parent.parent / "sample_project"
MAX_OUTPUT = 20_000
COUNT_PATTERN = re.compile(r"\b(?P<count>\d+)\s+(?P<kind>passed|failed|skipped|errors?)\b", re.IGNORECASE)
RESULT_PATTERN = re.compile(r"(?m)^.*::[^\s]+\s+(?P<kind>PASSED|FAILED|SKIPPED|ERROR)\b", re.IGNORECASE)
PROGRESS_PATTERN = re.compile(r"(?m)^\s*(?P<results>[.sFE]+)\s+\[\s*\d+%\]\s*$")


def parse_test_counts(output: str) -> dict[str, int]:
    """Read pytest summary counts or reconstruct them from per-test/progress output."""
    counts = {key: 0 for key in ("passed", "failed", "skipped", "errors")}
    for match in COUNT_PATTERN.finditer(output):
        kind = match.group("kind").lower()
        key = "errors" if kind.startswith("error") else kind
        counts[key] = int(match.group("count"))
    if any(counts.values()):
        return counts

    for match in RESULT_PATTERN.finditer(output):
        kind = match.group("kind").lower()
        key = "errors" if kind == "error" else kind
        counts[key] += 1
    if any(counts.values()):
        return counts

    progress = PROGRESS_PATTERN.search(output)
    if progress:
        results = progress.group("results")
        counts["passed"] = results.count(".")
        counts["failed"] = results.count("F")
        counts["skipped"] = results.count("s")
        counts["errors"] = results.count("E")
    return counts


def run_sample_tests(timeout_seconds: int = 20) -> dict:
    """Run only the bundled, reviewed sample suite. Never accepts a client path or command."""
    started = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-v", "--tb=short", str(SAMPLE_ROOT)],
            cwd=SAMPLE_ROOT,
            capture_output=True,
            text=True,
            timeout=max(2, min(timeout_seconds, 60)),
            shell=False,
            env={key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME") if key in os.environ} | {"PYTHONIOENCODING": "utf-8"},
        )
        output = (result.stdout + "\n" + result.stderr)[-MAX_OUTPUT:]
        counts = parse_test_counts(output)
        unavailable = "No module named pytest" in output or "can't open file" in output
        status = "error" if unavailable or result.returncode not in (0, 1) else ("failed" if result.returncode else "passed")
        if unavailable:
            counts["errors"] = max(counts["errors"], 1)
        total = sum(counts.values())
        if status == "error":
            summary = "Pytest could not start. Check the output below for setup details."
        elif counts["failed"] or counts["errors"]:
            summary = f"{total} tests ran; {counts['failed']} failed and {counts['errors']} had errors."
        else:
            summary = f"All {total} collected tests passed or were skipped."
        return {**counts, "status": status, "duration_ms": round((time.perf_counter() - started) * 1000),
                "summary": summary,
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

