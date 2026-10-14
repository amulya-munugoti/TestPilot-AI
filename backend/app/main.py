import json
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .ai import analyze_failure
from .database import Base, engine, get_db, SessionLocal
from .models import Analysis, Project, TestRun
from .runner import run_sample_tests
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
origins = [x.strip() for x in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])
_sensitive_requests = defaultdict(deque)


@app.middleware("http")
async def limit_sensitive_requests(request: Request, call_next):
    if request.method == "POST" and ("test-runs" in request.url.path):
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
    return {"status": "ok", "ai_configured": bool(os.getenv("GEMINI_API_KEY")), "demo_mode": True}


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    runs = db.scalars(select(TestRun).order_by(TestRun.created_at.desc()).limit(10)).all()
    totals = db.execute(select(func.count(TestRun.id), func.coalesce(func.sum(TestRun.passed), 0), func.coalesce(func.sum(TestRun.failed), 0))).one()
    total, passed, failed = totals
    bug_runs = [run for run in runs if run.failed or run.errors]
    return {"total_test_runs": total, "passed_tests": passed, "failed_tests": failed,
            "pass_rate": round(passed * 100 / max(passed + failed, 1), 1) if total else 0,
            "recent_runs": [RunOut.model_validate(x) for x in runs], "recent_bugs": [RunOut.model_validate(x) for x in bug_runs[:5]]}


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
    return db.scalars(select(TestRun).options(selectinload(TestRun.analyses)).order_by(TestRun.created_at.desc()).limit(limit)).all()


@app.get("/api/test-runs/{run_id}", response_model=RunOut)
def get_test_run(run_id: int, db: Session = Depends(get_db)):
    run = db.scalar(select(TestRun).options(selectinload(TestRun.analyses)).where(TestRun.id == run_id))
    if not run:
        raise HTTPException(404, "Test run not found")
    return run


async def save_analysis(run_id: int, generate_tests: bool, db: Session):
    run = db.get(TestRun, run_id)
    if not run:
        raise HTTPException(404, "Test run not found")
    if not (run.failed or run.errors):
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
    return json.loads(RunOut.model_validate(run).model_dump_json())


@app.get("/api/settings")
def settings():
    return {"ai_configured": bool(os.getenv("GEMINI_API_KEY")), "ai_model": os.getenv("AI_MODEL", "gemini-3.8-flash"), "demo_mode": True}

