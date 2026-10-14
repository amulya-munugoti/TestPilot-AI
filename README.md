# TestPilot AI — Intelligent Bug Detection and AI-Powered Test Analysis Platform

TestPilot AI is a Python-first project for running automated tests, understanding failures and keeping a clear test history. It combines a **Streamlit dashboard**, a **FastAPI backend**, **Pytest**, SQLAlchemy persistence and optional **Gemini** failure analysis.

## Project overview

When a developer runs the bundled sample suite, TestPilot records the real Pytest result, execution time and traceback. The dashboard presents run statistics and history. If Gemini is configured, a visitor can ask it to explain a failure in beginner-friendly language or suggest additional tests. AI output is clearly labelled and never changes the actual test result.

The project is designed as an internship portfolio demo: it demonstrates Python web development, REST APIs, database persistence, test automation, optional AI integration and safe handling of test execution. The public demo runs only a reviewed sample suite; it does not accept or execute visitor-uploaded code.

**Current deployment status:** prepared for deployment, but not deployed. No public demo URL is available yet.

**Public demo safety:** project records are metadata. Test execution is pinned to `backend/sample_project`; visitors cannot submit code, commands, or paths. The demo has no login or per-visitor isolation, so do not put private information in it. AI suggestions can be reviewed and exported, but the shared public app does not apply file changes.

## Architecture

- `frontend/app.py`: Streamlit UI written in Python. It provides the dashboard, project management, test history, run detail, settings and dark appearance toggle.
- `backend/app/`: FastAPI REST API, SQLAlchemy 2 models, controlled subprocess runner, optional Google GenAI client, CORS and simple in-memory request limits.
- `backend/migrations/`: Alembic configuration and initial schema migration.
- `backend/sample_project/`: two genuine Pytest cases: one passes and one intentionally fails to make a traceback visible.
- Local persistence defaults to SQLite. Set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL for hosted deployments.

## Language choice

Python is the only application language maintained in this project: FastAPI handles the API and test execution, while Streamlit renders the dashboard and calls that API with Python. There are no JavaScript or TypeScript app files or Node build steps. The remaining non-Python files are configuration, dependency lists and this documentation; Streamlit supplies its own browser interface.

## Features

- Real dashboard metrics and recent run/bug reports, loaded from API records.
- Create, view and delete project metadata. The sample project is protected.
- Run the bundled suite with Pytest; store pass/fail/skip/error counts, duration and capped output.
- Inspect history, tracebacks and AI analyses; export a run as JSON.
- Optional Gemini failure analysis and test suggestions. AI unavailable/quota errors are reported as unavailable; they never change test results.
- Settings show whether a key is configured without returning the key.
- Safe execution uses an argument list, fixed server-side path, timeout and 20 KB output cap. Sensitive-looking values are redacted from AI prompts.

## Requirements

- Windows 10/11, Git and Python 3.12.
- Python 3.12 recommended for the smoothest compatibility across dependencies. The pasted brief reported Python 3.14.4, but Python was not available on PATH in the inspected shell. Recent FastAPI, SQLAlchemy, pytest and Google GenAI support newer Python releases; if you use 3.14 and installation fails for a compiled dependency, use Python 3.12.
- PostgreSQL is optional locally; SQLite starts without a database server.

## Local setup (Windows PowerShell)

Open PowerShell in the project root:

```powershell
git --version
python --version
py -3.12 --version
```

If `py -3.12` is unavailable, install Python 3.12 from [python.org](https://www.python.org/downloads/windows/) and ensure the Python Launcher is included. Create a virtual environment and install backend dependencies:

```powershell
Set-Location .\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

The copied `.env` already selects local SQLite. You can leave `GEMINI_API_KEY` blank; the core app runs without AI. To use Gemini, create a key in Google AI Studio and enter it privately in `backend/.env`. Never paste it into frontend variables, source code, screenshots, GitHub, or chat. Keep `AI_MODEL=gemini-3.8-flash` unless your AI Studio account shows a different free-eligible model. The default model is listed with free standard input/output pricing today; per-project quotas vary, and free-tier prompt data may be used to improve Google's products. Do not send private source code or sensitive logs.

Run the backend from the `backend` directory:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API creates local tables and seeds `TestPilot Sample` at startup. Interactive API docs are at `http://127.0.0.1:8000/docs`.

In a second PowerShell window, start the Python UI:

```powershell
Set-Location .\frontend
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`. `TESTPILOT_API_URL` defaults to `http://127.0.0.1:8000/api` and can be changed in `frontend/.env`.

## Database and migrations

SQLite is used by default for local learning. Create the schema via Alembic when you want to exercise migrations:

```powershell
Set-Location .\backend
alembic upgrade head
```

The API also calls `create_all()` at startup to make first-run local setup straightforward. For PostgreSQL, create a database and set `DATABASE_URL` in the backend environment, for example:

```text
postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

Install the PostgreSQL driver before using that URL (`pip install psycopg[binary]`), then run `alembic upgrade head`. Keep the database URL private and URL-encode reserved password characters.

## Tests and build

From `backend`:

```powershell
python -m pytest
```

Tests cover health/settings, validation and project CRUD, rejecting non-sample execution, a real sample run and traceback, dashboard/history/report persistence, AI-unconfigured behavior, mocked AI responses, analysis validation, and secret redaction. They make no Gemini network call.

From `frontend`:

```powershell
python -m compileall -q app.py
```

## Deploy for a free demo

The included `render.yaml` describes two Python web services: the FastAPI backend and the Streamlit UI. Connect the repository in Render and deploy the blueprint; both services use the free plan. Create a Neon free PostgreSQL project (or another PostgreSQL host) and set backend `DATABASE_URL` to its SSL URL. Set the UI service's `TESTPILOT_API_URL` to the backend URL plus `/api`. Set `GEMINI_API_KEY` privately on the backend only, and leave it blank if you do not want AI. The Streamlit UI calls FastAPI from its Python server, so browser CORS is not used for those UI requests.

Deployment checklist:

1. Push this workspace to a GitHub repository you control.
2. Create the Neon Free database; copy its PostgreSQL connection string without sharing it.
3. In Render, create the two Python services from `render.yaml`.
4. Set backend `DATABASE_URL`, `FRONTEND_ORIGIN`, `APP_ENV=production`, and optionally `GEMINI_API_KEY` in the provider dashboard. Keep `AI_MODEL=gemini-3.8-flash`.
5. Set the UI's `TESTPILOT_API_URL=https://YOUR-API.onrender.com/api` and deploy both services.
6. Confirm `/api/health`, open the Streamlit UI, run the bundled tests, inspect the real failure and export a JSON report.

The Render free web service sleeps after 15 minutes idle and its filesystem is ephemeral, so SQLite is not suitable for hosted history. Expect a cold start after sleep. Free service-hours, bandwidth and build limits apply; do not enable billing or add a payment method for this project. Neon currently lists 1 GB storage and 100 compute-hours per project per month on Free, scaling compute to zero while idle; quotas and policies can change. Free services are suitable for a portfolio demo, not a production availability guarantee. The Gemini API free tier has model and rate limits that may be quota exhausted; AI gracefully becomes unavailable. Its current free tier may use submitted content to improve Google's products.

## Security and limits

- Do not advertise this as unrestricted code execution. No uploads, arbitrary paths, or shell commands are accepted.
- Run execution is limited to the controlled sample and configured timeout (default 20 seconds); output is capped at 20 KB.
- Public write/AI execution endpoints use a small process-local rate limit. This is a demo safeguard, not a substitute for authentication or a distributed API gateway.
- The demo has no sign-in, tenant isolation, or abuse-proofing. Do not expose it as a shared source-code analysis service.
- AI requests only contain the sample traceback in this demo, are capped and redacted; credentials and private code should never be submitted.
- AI suggestions are explanatory text, not verified patches. Review any change manually. Patch preview/application and automatic fix verification are not enabled in the public shared workspace.
- Do not put secrets in `.env.example`; keep real values in provider secret settings and local ignored `.env` files.

## Troubleshooting

- **`python`/`py` not found:** install Python 3.12 and reopen PowerShell. Check `py -0p` for installed versions.
- **Pytest could not start:** activate `backend/.venv` and run `pip install -r requirements.txt`.
- **UI cannot reach the API:** start Uvicorn, confirm backend health, and check `TESTPILOT_API_URL` in `frontend/.env`.
- **Dashboard shows no data:** start the API. A fresh SQLite file seeds the sample project; metrics stay zero until you run it.
- **Gemini unavailable:** verify the private backend key, model access and AI Studio quota. A 429/quota exhaustion is not a passing or fabricated analysis.
- **Hosted history disappears:** use PostgreSQL `DATABASE_URL`; hosted free web-service local files are ephemeral.
- **Migration command cannot find config:** run `alembic upgrade head` from `backend` with its virtual environment activated.

## Screenshots

No screenshots have been captured yet. Add dashboard, run-detail and mobile screenshots here after launching the app locally.

## Future improvements

- User accounts and per-user isolated workspaces with authentication and authorization.
- Dedicated isolated workers/containers for approved private repositories.
- Structured AI diagnosis and human-approved, isolated patch preview plus verified application.
- Persistent rate limiting, observability, audit log retention and more database migration coverage.
- CI workflow, accessibility audit and visual regression coverage.
