"""Python-only Streamlit interface for TestPilot AI."""

from __future__ import annotations

import json
import html
import os
import re
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


def apply_theme(dark: bool) -> None:
    """Apply a quiet, consistent workspace theme without adding frontend dependencies."""
    if dark:
        page_bg, panel_bg, text, muted, border, sidebar = "#101827", "#182335", "#edf3fb", "#9aa9bd", "#2b3a50", "#0c1421"
        input_bg = "#111c2c"
    else:
        page_bg, panel_bg, text, muted, border, sidebar = "#f5f7fb", "#ffffff", "#172033", "#69758a", "#e5eaf2", "#111c32"
        input_bg = "#ffffff"
    st.markdown(
        f"""
        <style>
        :root {{ --tp-bg:{page_bg}; --tp-panel:{panel_bg}; --tp-text:{text}; --tp-muted:{muted}; --tp-border:{border}; --tp-sidebar:{sidebar}; }}
        body,[data-testid="stAppViewContainer"] {{ background:var(--tp-bg); color:var(--tp-text); }}
        [data-testid="stMarkdownContainer"],[data-testid="stText"] {{ color:var(--tp-text); }}
        [data-testid="stHeader"] {{ background:transparent; }}
        [data-testid="stMain"] .block-container {{ max-width:1320px; padding:2rem 3rem 4rem; }}
        [data-testid="stSidebar"] {{ background:var(--tp-sidebar); border-right:1px solid rgba(255,255,255,.07); }}
        [data-testid="stSidebar"] * {{ color:#e8eef8; }}
        [data-testid="stSidebar"] [data-testid="stRadio"] label {{ border-radius:10px; padding:.48rem .6rem; transition:background .15s ease; }}
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{ background:rgba(255,255,255,.07); }}
        [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{ background:rgba(111,137,255,.2); outline:1px solid rgba(145,167,255,.22); }}
        [data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"] {{ display:none; }}
        h1,h2,h3 {{ color:var(--tp-text); letter-spacing:-.035em; }}
        h1 {{ font-size:2rem !important; font-weight:700 !important; margin-bottom:.25rem !important; }}
        h2 {{ font-size:1.25rem !important; font-weight:650 !important; margin-top:1.6rem !important; }}
        [data-testid="stCaptionContainer"] {{ color:var(--tp-muted); }}
        [data-testid="stMetric"] {{ background:var(--tp-panel); border:1px solid var(--tp-border); border-radius:15px; padding:1rem 1.15rem; box-shadow:0 4px 14px rgba(24,39,75,.045); }}
        [data-testid="stMetricLabel"] {{ color:var(--tp-muted); font-size:.83rem; }}
        [data-testid="stMetricValue"] {{ color:var(--tp-text); font-size:1.8rem; font-weight:700; }}
        [data-testid="stExpander"] {{ background:var(--tp-panel); border:1px solid var(--tp-border); border-radius:12px; }}
        [data-testid="stVerticalBlockBorderWrapper"] {{ background:var(--tp-panel); border-color:var(--tp-border) !important; border-radius:14px; }}
        [data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,[data-testid="stSelectbox"] [data-baseweb="select"] > div {{ background:{input_bg}; border-color:var(--tp-border); border-radius:9px; }}
        [data-testid="stButton"] button,[data-testid="stDownloadButton"] button {{ border-radius:9px; font-weight:600; min-height:2.55rem; }}
        [data-testid="stButton"] button[kind="primary"] {{ background:#536dfc; color:white; border:1px solid #536dfc; box-shadow:0 5px 15px rgba(83,109,252,.28); }}
        [data-testid="stButton"] button[kind="primary"]:hover {{ background:#4058e8; border-color:#4058e8; }}
        [data-testid="stAlert"] {{ border-radius:11px; }}
        .tp-kicker {{ color:#5679d8; font-size:.75rem; text-transform:uppercase; letter-spacing:.12em; font-weight:700; margin-bottom:.25rem; }}
        .tp-sidebar-brand {{ font-size:1.08rem; font-weight:750; letter-spacing:-.035em; margin:.3rem 0 0; display:flex; align-items:center; }}
        .tp-sidebar-mark {{ display:inline-grid; place-items:center; width:2.15rem; height:2.15rem; border-radius:10px; background:linear-gradient(145deg,#8298ff,#536dfc); color:white; font-weight:800; margin-right:.6rem; box-shadow:0 5px 14px rgba(83,109,252,.3); }}
        .tp-brand-ai {{ color:#aebcff; font-size:.65rem; letter-spacing:.1em; margin-left:.4rem; align-self:flex-start; }}
        .tp-hero-kicker {{ color:#aebcff; font-size:.72rem; text-transform:uppercase; letter-spacing:.15em; font-weight:750; margin-bottom:.6rem; }}
        .tp-hero-title {{ color:#fff; font-size:1.9rem; line-height:1.15; letter-spacing:-.045em; font-weight:750; margin-bottom:.55rem; }}
        .tp-hero-copy {{ color:#c6d0e2; font-size:.93rem; line-height:1.6; max-width:760px; }}
        .st-key-tp-hero {{ background:linear-gradient(115deg,#172744 0%,#233d70 58%,#334e8c 100%); border-radius:20px; padding:1.4rem 1.5rem; box-shadow:0 12px 28px rgba(30,51,91,.16); }}
        .st-key-tp-hero [data-testid="stButton"] {{ padding-top:.6rem; }}
        .tp-step-number {{ color:#536dfc; font-size:.7rem; letter-spacing:.12em; font-weight:800; text-transform:uppercase; margin-bottom:.5rem; }}
        .tp-step-card {{ height:100%; background:var(--tp-panel); border:1px solid var(--tp-border); border-radius:14px; padding:1rem 1.1rem; box-shadow:0 3px 12px rgba(24,39,75,.035); }}
        .tp-table-scroll {{ width:100%; overflow-x:auto; border:1px solid var(--tp-border); border-radius:14px; background:var(--tp-panel); }}
        .tp-run-table {{ border-collapse:collapse; min-width:720px; width:100%; font-size:.84rem; }}
        .tp-run-table th {{ color:var(--tp-muted); text-align:left; padding:.85rem .9rem; font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; border-bottom:1px solid var(--tp-border); background:rgba(110,128,160,.05); }}
        .tp-run-table td {{ color:var(--tp-text); padding:.82rem .9rem; border-bottom:1px solid var(--tp-border); white-space:nowrap; }}
        .tp-run-table tr:last-child td {{ border-bottom:0; }}
        .tp-run-table tbody tr:hover {{ background:rgba(83,109,252,.045); }}
        .tp-status {{ display:inline-block; padding:.23rem .55rem; border-radius:99px; font-size:.72rem; font-weight:700; }}
        .tp-status-failed {{ background:#fff0ee; color:#c24136; }}
        .tp-status-passed {{ background:#e9f8f0; color:#17804f; }}
        .tp-status-error {{ background:#fff4df; color:#986500; }}
        .tp-sidebar-note {{ color:#9eacc2 !important; font-size:.78rem; line-height:1.5; }}
        .tp-section-note {{ color:var(--tp-muted); margin-top:-.6rem; margin-bottom:1rem; }}
        @media (max-width: 800px) {{ [data-testid="stMain"] .block-container {{ padding:1.4rem 1rem 3rem; }} h1 {{ font-size:1.7rem !important; }} }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(section: str, title: str, description: str) -> None:
    st.markdown(f'<div class="tp-kicker">{section}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="tp-section-note">{description}</div>', unsafe_allow_html=True)


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


def display_counts(run: dict[str, Any]) -> dict[str, int]:
    counts = {key: int(run.get(key, 0) or 0) for key in ("passed", "failed", "skipped", "errors")}
    if not any(counts.values()):
        for count, kind in re.findall(r"\b(\d+)\s+(passed|failed|skipped|errors?)\b", run.get("output", ""), re.IGNORECASE):
            key = "errors" if kind.lower().startswith("error") else kind.lower()
            counts[key] = int(count)
    return counts


def run_table(runs: list[dict[str, Any]]) -> None:
    if not runs:
        st.info("No test runs yet. Run the bundled sample suite to create your first report.")
        return
    rows = []
    for run in runs:
        counts = display_counts(run)
        result = "Passed" if run["status"] == "passed" else ("Failed" if run["status"] == "failed" else "Could not run")
        result_class = "passed" if run["status"] == "passed" else ("failed" if run["status"] == "failed" else "error")
        cells = (
            f"<td><strong>#{run['id']}</strong></td>",
            f'<td><span class="tp-status tp-status-{result_class}">{result}</span></td>',
            f"<td>{counts['passed']}</td>",
            f"<td>{counts['failed']}</td>",
            f"<td>{counts['skipped']}</td>",
            f"<td>{counts['errors']}</td>",
            f"<td>{int(run['duration_ms']):,} ms</td>",
            f"<td>{html.escape(format_time(run.get('created_at')))}</td>",
        )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    headers = "".join(f"<th scope='col'>{label}</th>" for label in ("Run", "Result", "Passed", "Failed", "Skipped", "Errors", "Duration", "Date"))
    st.markdown(
        '<div class="tp-table-scroll"><table class="tp-run-table"><thead><tr>' + headers +
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>",
        unsafe_allow_html=True,
    )


def show_run_detail(run: dict[str, Any], key_prefix: str = "detail") -> None:
    counts = display_counts(run)
    has_issues = counts["failed"] or counts["errors"] or run["status"] != "passed"
    st.subheader(f"Run #{run['id']} · {run['status'].title()}")
    if counts["failed"] or counts["errors"]:
        result_summary = f"{counts['passed']} passed · {counts['failed']} failed · {counts['skipped']} skipped · {counts['errors']} errors"
    else:
        result_summary = run.get("summary", "No summary was recorded.")
    st.caption(f"{format_time(run.get('created_at'))} · {run['duration_ms']:,} ms · {result_summary}")
    if run["status"] == "failed":
        st.info("The suite finished and found a failing check. This demo includes one deliberately failing example so you can see how TestPilot records and explains a failure.")
    elif run["status"] == "error":
        st.error("The test runner could not complete. Check the output below for a setup, timeout, or runner error.")
    columns = st.columns(4)
    for column, label, value in zip(
        columns,
        ("Passed", "Failed", "Skipped", "Errors"),
        (counts["passed"], counts["failed"], counts["skipped"], counts["errors"]),
    ):
        column.metric(label, value)

    with st.expander("What Pytest printed", expanded=bool(has_issues)):
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

    if has_issues:
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
                st.success("Gemini analysis complete")
            else:
                st.warning("Gemini is disabled because GEMINI_API_KEY is missing. Add it to backend/.env and restart the backend. Test results and reports still work without it.")
            st.markdown(analysis.get("content", "No analysis content was returned."))
        analysis_error = st.session_state.get(f"analysis-error-{run['id']}")
        if analysis_error:
            st.warning(analysis_error)
        st.caption("AI suggestions are advisory. Review them manually; the shared demo never changes files or test results.")


def dashboard() -> None:
    with st.container(key="tp-hero"):
        hero, action = st.columns([6, 2], gap="large", vertical_alignment="center")
        with hero:
            st.markdown(
                """
                <div class="tp-hero-kicker">TESTPILOT AI · TEST INTELLIGENCE</div>
                <div class="tp-hero-title">Know what passed.<br>Understand what failed.</div>
                <div class="tp-hero-copy">Run the bundled Python test suite, review the real Pytest report, then ask AI for an explanation. One check is intentionally failing to demonstrate the workflow.</div>
                """,
                unsafe_allow_html=True,
            )
        with action:
            run_clicked = st.button("Run 2 demo checks", type="primary", icon="▶", use_container_width=True)
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

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    steps = st.columns(3, gap="medium")
    for column, title, detail in zip(
        steps,
        ("01 · Execute", "02 · Inspect", "03 · Get insight"),
        (
            "Runs the fixed two-check Python demo suite.",
            "See saved pass/fail counts and the real Pytest traceback.",
            "If Gemini is configured, request a plain-language explanation. AI never changes the test result.",
        ),
    ):
        with column:
            st.markdown(
                f'<div class="tp-step-card"><div class="tp-step-number">{title}</div><div>{html.escape(detail)}</div></div>',
                unsafe_allow_html=True,
            )

    if run_clicked:
        try:
            projects = api_request("GET", "/projects")
            sample = next((project for project in projects if project["name"] == "TestPilot Sample"), None)
            if sample is None:
                st.error("The bundled sample project is missing.")
            else:
                with st.spinner("Running the real Pytest sample suite…"):
                    run = api_request("POST", f"/projects/{sample['id']}/test-runs")
                st.session_state["latest-run-id"] = run["id"]
                st.success("Test run finished and saved to history.")
                st.rerun()
        except ApiError as exc:
            show_api_error(exc)

    st.subheader("Recent test runs")
    run_table(data.get("recent_runs", []))
    st.subheader("Failed runs to inspect")
    bugs = data.get("recent_bugs", [])
    latest_run_id = st.session_state.pop("latest-run-id", None)
    if bugs:
        for run in bugs:
            counts = display_counts(run)
            issue_count = counts["failed"] + counts["errors"]
            with st.expander(
                f"Run #{run['id']} · {issue_count} failing check(s) · {format_time(run.get('created_at'))}",
                expanded=run["id"] == latest_run_id,
            ):
                show_run_detail(run, "dashboard")
    else:
        st.info("No failing runs yet. Run the demo suite to see its intentional failure and the captured traceback.")


def projects_page() -> None:
    page_header("Workspace / Projects", "Projects", "Project entries are for organizing the demo. At the moment, only the bundled TestPilot Sample project can run tests; creating a project does not upload or execute its code.")
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
    page_header("Workspace / Activity", "Test history", "Browse recorded runs, inspect tracebacks, and download reports.")
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
    page_header("Workspace / Configuration", "Settings", "Check the API connection and review the demo configuration.")
    st.code(API_BASE, language="text")
    try:
        settings = api_request("GET", "/settings")
        st.success("Backend API connected")
        if settings["ai_configured"]:
            st.write("Gemini: Configured")
        else:
            st.warning("Gemini analysis is disabled until you add a key to backend/.env and restart the backend.")
            st.code("GEMINI_API_KEY=your-gemini-api-key", language="text")
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
    st.markdown('<div class="tp-sidebar-brand"><span class="tp-sidebar-mark">TP</span>TestPilot <span class="tp-brand-ai">AI</span></div>', unsafe_allow_html=True)
    st.markdown('<p class="tp-sidebar-note">Test automation &amp; failure insight</p>', unsafe_allow_html=True)
    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    page = st.radio("Navigation", ("Overview", "Projects", "Test history", "Settings"), label_visibility="collapsed")
    st.divider()
    dark_mode = st.toggle("Dark appearance", value=False)
    st.markdown('<p class="tp-sidebar-note">Safe demo · Python · Pytest</p>', unsafe_allow_html=True)

apply_theme(dark_mode)

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

