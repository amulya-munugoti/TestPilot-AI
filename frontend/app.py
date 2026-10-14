"""Python-only Streamlit interface for TestPilot AI."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))
API_BASE = os.getenv("TESTPILOT_API_URL", "").strip()
if not API_BASE:
    try:
        API_BASE = st.secrets.get("TESTPILOT_API_URL", "")
    except Exception:
        API_BASE = ""
API_BASE = (API_BASE or "http://127.0.0.1:8000/api").rstrip("/")
REQUEST_TIMEOUT_SECONDS = 35

st.set_page_config(page_title="TestPilot AI", page_icon="🧪", layout="wide", initial_sidebar_state="expanded")


class ApiError(RuntimeError):
    """A readable error returned by the backend API."""


def api_request(method: str, path: str, **kwargs: Any) -> Any:
    try:
        response = requests.request(method, f"{API_BASE}{path}", timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
    except requests.RequestException as exc:
        raise ApiError("The TestPilot API could not be reached. Start the backend or check TESTPILOT_API_URL.") from exc
    if not response.ok:
        try:
            detail = response.json().get("detail", response.reason)
        except (ValueError, AttributeError):
            detail = response.reason
        raise ApiError(f"API returned {response.status_code}: {detail}")
    if response.status_code == 204:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("The API returned an invalid response.") from exc


def show_api_error(error: Exception) -> None:
    st.error(str(error))


def format_time(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%b %d, %Y %I:%M %p")
    except ValueError:
        return value


def run_table(runs: list[dict[str, Any]]) -> None:
    if not runs:
        st.info("No test runs yet. Run the bundled sample suite to create your first report.")
        return
    rows = [
        {
            "Run": f"#{run['id']}",
            "Status": run["status"].title(),
            "Passed": run["passed"],
            "Failed": run["failed"],
            "Skipped": run["skipped"],
            "Errors": run["errors"],
            "Duration": f"{run['duration_ms']} ms",
            "Created": format_time(run.get("created_at")),
        }
        for run in runs
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def show_run_detail(run: dict[str, Any], key_prefix: str = "detail") -> None:
    st.subheader(f"Test run #{run['id']}")
    st.caption(f"{format_time(run.get('created_at'))} · {run['duration_ms']} ms · {run['summary']}")
    columns = st.columns(4)
    for column, label, value in zip(
        columns,
        ("Passed", "Failed", "Skipped", "Errors"),
        (run["passed"], run["failed"], run["skipped"], run["errors"]),
    ):
        column.metric(label, value)

    with st.expander("Pytest output and traceback", expanded=bool(run["failed"] or run["errors"])):
        st.code(run.get("output") or "No output was recorded.", language="text", wrap_lines=True)

    report = None
    try:
        report = api_request("GET", f"/test-runs/{run['id']}/report")
    except ApiError as exc:
        st.caption(f"Could not load report details: {exc}")
    if report is not None:
        st.download_button(
            "Download JSON report",
            data=json.dumps(report, indent=2),
            file_name=f"testpilot-run-{run['id']}.json",
            mime="application/json",
            key=f"{key_prefix}-download-{run['id']}",
        )

    if run["failed"] or run["errors"]:
        left, right = st.columns(2)
        if left.button("Analyze failure with Gemini", key=f"{key_prefix}-analyze-{run['id']}", use_container_width=True):
            with st.spinner("Asking the backend to analyze the real traceback…"):
                try:
                    result = api_request("POST", f"/test-runs/{run['id']}/analyze")
                    st.session_state[f"analysis-{run['id']}"] = result
                except ApiError as exc:
                    st.session_state[f"analysis-error-{run['id']}"] = str(exc)
        if right.button("Generate test ideas", key=f"{key_prefix}-generate-{run['id']}", use_container_width=True):
            with st.spinner("Requesting test ideas…"):
                try:
                    result = api_request("POST", f"/test-runs/{run['id']}/generate-tests")
                    st.session_state[f"analysis-{run['id']}"] = result
                except ApiError as exc:
                    st.session_state[f"analysis-error-{run['id']}"] = str(exc)

        analysis = st.session_state.get(f"analysis-{run['id']}")
        if not analysis and report:
            prior = report.get("analyses", [])
            analysis = prior[-1] if prior else None
        if analysis:
            if analysis.get("status") == "completed":
                st.success("Real Gemini response")
            else:
                st.warning("AI analysis unavailable. Test results and reports remain available.")
            st.markdown(analysis.get("content", "No analysis content was returned."))
        analysis_error = st.session_state.get(f"analysis-error-{run['id']}")
        if analysis_error:
            st.warning(analysis_error)
        st.caption("AI suggestions are advisory. Review them manually; the shared demo never changes files or test results.")


def dashboard() -> None:
    st.title("TestPilot AI")
    st.caption("A Python-first workspace for controlled test execution and beginner-friendly failure analysis.")
    try:
        data = api_request("GET", "/dashboard")
    except ApiError as exc:
        show_api_error(exc)
        return

    metrics = st.columns(4)
    metrics[0].metric("Test runs", data["total_test_runs"])
    metrics[1].metric("Passed tests", data["passed_tests"])
    metrics[2].metric("Failed tests", data["failed_tests"])
    metrics[3].metric("Pass rate", f"{data['pass_rate']}%")

    if st.button("Run bundled sample suite", type="primary", icon="▶"):
        try:
            projects = api_request("GET", "/projects")
            sample = next((project for project in projects if project["name"] == "TestPilot Sample"), None)
            if sample is None:
                st.error("The bundled sample project is missing.")
            else:
                with st.spinner("Running the real Pytest sample suite…"):
                    run = api_request("POST", f"/projects/{sample['id']}/test-runs")
                st.session_state["latest-run"] = run
                st.success("Test run finished and saved to history.")
                st.rerun()
        except ApiError as exc:
            show_api_error(exc)

    st.subheader("Recent test runs")
    run_table(data.get("recent_runs", []))
    st.subheader("Recent bug reports")
    bugs = data.get("recent_bugs", [])
    if bugs:
        for run in bugs:
            with st.expander(f"Run #{run['id']} · {run['failed'] + run['errors']} issue(s) · {format_time(run.get('created_at'))}"):
                show_run_detail(run, "dashboard")
    else:
        st.info("There are no bug reports yet. The failing demo test will appear here after execution.")

    latest = st.session_state.pop("latest-run", None)
    if latest:
        st.divider()
        show_run_detail(latest, "latest")


def projects_page() -> None:
    st.title("Projects")
    st.caption("Project records describe supported configurations. Test runs remain restricted to the reviewed sample.")
    with st.form("create-project", clear_on_submit=True):
        name = st.text_input("Project name", max_chars=100)
        description = st.text_area("Description", max_chars=500)
        st.caption("Supported configuration: Python · Pytest")
        submitted = st.form_submit_button("Create project", type="primary")
    if submitted:
        try:
            api_request("POST", "/projects", json={"name": name, "description": description, "project_type": "python-pytest"})
            st.success("Project created.")
            st.rerun()
        except ApiError as exc:
            show_api_error(exc)

    try:
        projects = api_request("GET", "/projects")
    except ApiError as exc:
        show_api_error(exc)
        return
    for project in projects:
        with st.container(border=True):
            heading, action = st.columns([5, 1])
            heading.markdown(f"### {project['name']}")
            heading.write(project.get("description") or "No description")
            heading.caption(f"Python · Pytest · Created {format_time(project.get('created_at'))}")
            if project["name"] == "TestPilot Sample":
                action.caption("Protected demo")
            elif action.button("Delete", key=f"delete-{project['id']}"):
                st.session_state["delete-project"] = project["id"]
                st.session_state["delete-project-name"] = project["name"]
                st.rerun()

    project_id = st.session_state.get("delete-project")
    if project_id:
        st.warning(f"Delete {st.session_state.get('delete-project-name')} and its associated run history?")
        yes, no = st.columns(2)
        if yes.button("Confirm delete", type="primary"):
            try:
                api_request("DELETE", f"/projects/{project_id}")
                st.session_state.pop("delete-project", None)
                st.session_state.pop("delete-project-name", None)
                st.success("Project deleted.")
                st.rerun()
            except ApiError as exc:
                show_api_error(exc)
        if no.button("Cancel"):
            st.session_state.pop("delete-project", None)
            st.session_state.pop("delete-project-name", None)
            st.rerun()


def history_page() -> None:
    st.title("Test history")
    st.caption("Recorded Pytest runs, tracebacks, AI analyses and downloadable reports.")
    try:
        runs = api_request("GET", "/test-runs?limit=100")
    except ApiError as exc:
        show_api_error(exc)
        return
    run_table(runs)
    if runs:
        runs_by_id = {run["id"]: run for run in runs}
        selected_id = st.selectbox(
            "Inspect a run",
            options=list(runs_by_id),
            format_func=lambda run_id: (
                f"Run #{run_id} · {runs_by_id[run_id]['status']} · "
                f"{format_time(runs_by_id[run_id].get('created_at'))}"
            ),
        )
        try:
            detail = api_request("GET", f"/test-runs/{selected_id}")
            st.divider()
            show_run_detail(detail, "history")
        except ApiError as exc:
            show_api_error(exc)


def settings_page() -> None:
    st.title("Settings")
    st.caption("Backend connection and safe demo configuration.")
    st.code(API_BASE, language="text")
    try:
        settings = api_request("GET", "/settings")
        st.success("Backend API connected")
        st.write(f"Gemini: {'Configured' if settings['ai_configured'] else 'Not configured'}")
        st.write(f"Model: `{settings['ai_model']}`")
        st.write("Execution mode: controlled public demo")
    except ApiError as exc:
        show_api_error(exc)
    st.divider()
    st.subheader("Demo safety")
    st.markdown(
        """
        - Visitors can run only the bundled, reviewed Pytest sample.
        - The API accepts no uploaded code, unrestricted shell commands or client file paths.
        - Test output is time-limited and capped. AI is optional and never determines pass/fail.
        - This demo has no login or per-user isolation. Do not enter private source code or secrets.
        - AI suggestions can be reviewed and exported; this shared workspace does not apply changes.
        """
    )
    st.info("Configure GEMINI_API_KEY privately in the backend environment. The key is never returned by the API or shown here.")


with st.sidebar:
    st.title("TestPilot AI")
    st.caption("Python testing workspace")
    page = st.radio("Navigation", ("Overview", "Projects", "Test history", "Settings"), label_visibility="collapsed")
    st.divider()
    dark_mode = st.toggle("Dark appearance", value=False)
    st.caption("Safe demo · Python · Pytest")

if dark_mode:
    st.markdown(
        "<style>[data-testid='stAppViewContainer'],[data-testid='stSidebar']{background:#171b24;color:#edf0f6}[data-testid='stHeader']{background:transparent}</style>",
        unsafe_allow_html=True,
    )

try:
    health = api_request("GET", "/health")
    st.sidebar.caption("API: connected")
except ApiError:
    st.sidebar.caption("API: unavailable")

if page == "Overview":
    dashboard()
elif page == "Projects":
    projects_page()
elif page == "Test history":
    history_page()
else:
    settings_page()

