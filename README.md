# TestPilot AI

**A focused workspace for running tests, reviewing failures, and learning what to investigate next.**

TestPilot AI pairs a FastAPI service with a Streamlit dashboard. Run the bundled Pytest examples, inspect execution output and history, export JSON reports, and optionally ask Gemini to explain a failure or suggest additional tests.

> **Demo scope:** TestPilot currently runs its bundled sample suite only. It does not accept uploaded code or execute arbitrary commands. AI-generated guidance is advisory and does not change test results.

## What you can do

- **Monitor suite health:** See run totals, pass rate, failures, and recent activity at a glance.
- **Keep projects organized:** Create and review projects in one workspace.
- **Investigate runs:** Filter history, inspect captured Pytest output, and download a JSON report.
- **Explore failures:** Request an AI explanation or additional test ideas when Gemini is configured.
- **Check system readiness:** View backend and Gemini connection status in Settings.

## Built with

| Area | Technology |
| --- | --- |
| Dashboard | Streamlit |
| API | FastAPI |
| Test execution | Pytest |
| Data and migrations | SQLAlchemy, Alembic |
| Database | SQLite locally; PostgreSQL supported |
| Optional AI | Google Gemini |

## Run locally

Requirements: Python 3.12 recommended.

### 1. Install dependencies

From the project root, in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .\backend\.env.example .\backend\.env
Copy-Item .\frontend\.env.example .\frontend\.env
```

### 2. Start the API

In a terminal at the project root:

```powershell
Set-Location .\backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API health endpoint is `http://127.0.0.1:8000/api/health`; interactive API docs are at `http://127.0.0.1:8000/docs`.

### 3. Start the dashboard

Open a second terminal at the project root:

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location .\frontend
python -m streamlit run app.py
```

Open `http://localhost:8501`. The dashboard reads `TESTPILOT_API_URL`, which defaults to `http://127.0.0.1:8000/api`.

## Optional Gemini setup

Add your key to `backend/.env`:

```dotenv
GEMINI_API_KEY=your-key
AI_MODEL=gemini-3.8-flash
```

Use a model available to your account. Keep the key on the backend; never put it in frontend settings or commit it to source control. Without a key, all test execution and reporting features remain available.

## Project layout

```text
backend/
  app/                 FastAPI routes, data models, test runner, and AI integration
  migrations/          Alembic database migrations
  sample_project/      Controlled Pytest examples
  tests/               Backend test suite
frontend/
  app.py               Streamlit dashboard
  requirements.txt     Dashboard dependencies
requirements.txt       Shared local install entry point
render.yaml            Render service blueprint
```

## Deployment

`render.yaml` defines backend and dashboard services. Before deploying, configure a persistent PostgreSQL database, set the backend `DATABASE_URL` and `FRONTEND_ORIGIN`, and point the dashboard's `TESTPILOT_API_URL` at the deployed API plus `/api`. The project is not currently deployed publicly. Review the hosting provider's current filesystem and service limits before relying on hosted persistence.

## Security and current limits

- Only the bundled sample suite is executable.
- Execution uses a configured timeout and bounded output capture.
- Rate limiting is process-local and intended as a basic safeguard.
- The demo does not provide authentication or per-user workspace isolation.
- Do not submit private source code, credentials, or sensitive logs to AI analysis.

## Author

All Rights Are Reserved By Amulya Munugoti
