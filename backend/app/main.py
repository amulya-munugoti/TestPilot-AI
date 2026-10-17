import asyncio
import json
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from dotenv import load_dotenv

# Load backend settings from the project location, regardless of the directory
# from which Uvicorn was started. Existing process environment still wins.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .ai import analyze_failure
from .database import Base, engine, get_db, SessionLocal
from .models import Analysis, Project, TestRun
from .runner import parse_test_counts, run_sample_tests
from .schemas import ProjectCreate, ProjectOut, RunOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        sample = db.scalar(select(Project).where(Project.name == "TestPilot Sample"))
        if not sample:
            db.add(Project(name="TestPilot Sample", description="Controlled demo suite with passing and failing examples."))
            db.commit()
    yield


app = FastAPI(title="TestPilot AI API", version="1.0.0", lifespan=lifespan)
origins = [x.strip() for x in os.getenv("FRONTEND_ORIGIN", "http://localhost:8501").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])
_sensitive_requests = defaultdict(deque)


def effective_counts(run: TestRun) -> dict[str, int]:
    counts = {key: int(getattr(run, key) or 0) for key in ("passed", "failed", "skipped", "errors")}
    # Older runs may have status/output but zero counters from the previous summary parser.
    if not any(counts.values()):
        counts = parse_test_counts(run.output or "")
    return counts


def visible_run(run: TestRun) -> RunOut:
    return RunOut.model_validate(run).model_copy(update=effective_counts(run))


@app.middleware("http")
async def limit_sensitive_requests(request: Request, call_next):
    if request.method == "POST" and ("test-runs" in request.url.path or request.url.path.endswith("/settings/gemini-test")):
        address = request.client.host if request.client else "unknown"
        key = (address, request.url.path.rsplit("/", 1)[-1] if request.url.path.endswith(("/analyze", "/generate-tests")) else "run")
        now = time.monotonic()
        if len(_sensitive_requests) > 1024:
            for old_key, old_attempts in list(_sensitive_requests.items()):
                if not old_attempts or now - old_attempts[-1] > 60:
                    _sensitive_requests.pop(old_key, None)
        attempts = _sensitive_requests[key]
        while attempts and now - attempts[0] > 60:
            attempts.popleft()
        if len(attempts) >= 10:
            return JSONResponse(status_code=429, content={"detail": "Request limit reached. Please wait a minute before trying again."})
        attempts.append(now)
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()), "demo_mode": True}


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    runs = db.scalars(select(TestRun).order_by(TestRun.created_at.desc()).limit(10)).all()
    all_runs = db.scalars(select(TestRun)).all()

    total = len(all_runs)
    passed = sum(effective_counts(run)["passed"] for run in all_runs)
    failed = sum(effective_counts(run)["failed"] for run in all_runs)
    bug_runs = [run for run in runs if effective_counts(run)["failed"] or effective_counts(run)["errors"] or run.status != "passed"]
    return {"total_test_runs": total, "passed_tests": passed, "failed_tests": failed,
            "pass_rate": round(passed * 100 / max(passed + failed, 1), 1) if total else 0,
            "recent_runs": [visible_run(x) for x in runs], "recent_bugs": [visible_run(x) for x in bug_runs[:5]]}


@app.get("/api/projects", response_model=list[ProjectOut])
def projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.created_at.desc())).all()


@app.post("/api/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Project).where(Project.name == payload.name.strip())):
        raise HTTPException(409, "A project with this name already exists")
    project = Project(name=payload.name.strip(), description=payload.description.strip(), project_type=payload.project_type)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get("/api/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.name == "TestPilot Sample":
        raise HTTPException(400, "The bundled demo project cannot be deleted")
    db.delete(project)
    db.commit()


@app.post("/api/projects/{project_id}/test-runs", response_model=RunOut, status_code=201)
def create_test_run(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.name != "TestPilot Sample" or project.project_type != "python-pytest":
        raise HTTPException(400, "Only the bundled controlled sample suite can currently be executed")
    data = run_sample_tests(int(os.getenv("TEST_TIMEOUT_SECONDS", "20")))
    run = TestRun(project_id=project_id, **data)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@app.get("/api/test-runs", response_model=list[RunOut])
def test_runs(limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    runs = db.scalars(select(TestRun).options(selectinload(TestRun.analyses)).order_by(TestRun.created_at.desc()).limit(limit)).all()
    return [visible_run(run) for run in runs]


@app.get("/api/test-runs/{run_id}", response_model=RunOut)
def get_test_run(run_id: int, db: Session = Depends(get_db)):
    run = db.scalar(select(TestRun).options(selectinload(TestRun.analyses)).where(TestRun.id == run_id))
    if not run:
        raise HTTPException(404, "Test run not found")
    return visible_run(run)


async def save_analysis(run_id: int, generate_tests: bool, db: Session):
    run = db.get(TestRun, run_id)
    if not run:
        raise HTTPException(404, "Test run not found")
    counts = effective_counts(run)
    if not (counts["failed"] or counts["errors"] or run.status != "passed"):
        raise HTTPException(400, "This run has no failure to analyze")
    result = await analyze_failure(run.output, generate_tests)
    db.add(Analysis(run_id=run.id, kind="generated_tests" if generate_tests else "analysis", **result))
    db.commit()
    return result


@app.post("/api/test-runs/{run_id}/analyze")
async def analyze(run_id: int, db: Session = Depends(get_db)):
    return await save_analysis(run_id, False, db)


@app.post("/api/test-runs/{run_id}/generate-tests")
async def generate_tests(run_id: int, db: Session = Depends(get_db)):
    return await save_analysis(run_id, True, db)


@app.get("/api/test-runs/{run_id}/report")
def report(run_id: int, db: Session = Depends(get_db)):
    run = db.scalar(select(TestRun).options(selectinload(TestRun.analyses)).where(TestRun.id == run_id))
    if not run:
        raise HTTPException(404, "Test run not found")
    return json.loads(visible_run(run).model_dump_json())


@app.get("/api/settings")
def settings():
    return {"ai_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()), "ai_model": os.getenv("AI_MODEL", "gemini-3.8-flash"), "demo_mode": True}


@app.post("/api/settings/gemini-test")
async def test_gemini_connection():
    """Make a small provider request so Settings can distinguish a key from a working connection."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "gemini-3.8-flash").strip()
    if not api_key:
        return {"status": "not_configured", "message": "No Gemini API key is configured on the backend."}

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = await asyncio.wait_for(
            client.aio.models.generate_content(model=model, contents="Reply with OK."),
            timeout=20,
        )
        if not (response.text or "").strip():
            return {"status": "error", "message": "Gemini responded without text. Check the selected model."}
        return {"status": "connected", "message": "Gemini connection verified.", "model": model}
    except Exception as exc:
        # Surface useful provider guidance without returning request data or credentials.
        detail = str(exc).lower()
        if "429" in detail or "quota" in detail or "resource_exhausted" in detail:
            message = "Gemini rejected the request because the project quota or rate limit is exhausted."
        elif "401" in detail or "403" in detail or "api key" in detail or "permission" in detail:
            message = "Gemini rejected the API key or the key does not have access to this model."
        elif "404" in detail or "not found" in detail:
            message = f"The model '{model}' is unavailable to this API key. Check AI_MODEL and model access."
        elif isinstance(exc, asyncio.TimeoutError):
            message = "Gemini did not respond within 20 seconds. Try again shortly."
        else:
            message = "Gemini could not be reached. Check backend network access and try again."
        return {"status": "error", "message": message}

