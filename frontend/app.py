import json
import os
from datetime import datetime, timezone

import requests
import streamlit as st


API_URL = os.getenv("TESTPILOT_API_URL", "http://127.0.0.1:8000/api").rstrip("/")
st.set_page_config(page_title="TestPilot AI", page_icon="✳", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --ink:#17231f; --muted:#718079; --line:#e8eeea; --green:#28765c; --wash:#f6f8f6; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; color:var(--ink); }
.stApp { background:#f7f9f7; }
header[data-testid="stHeader"] { background:transparent; }
.block-container { padding-top:2rem; padding-bottom:3rem; max-width:1440px; }
[data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--line); }
[data-testid="stSidebar"] .block-container { padding-top:1.6rem; }
h1,h2,h3 { font-family:'Manrope',sans-serif !important; letter-spacing:-.035em; color:var(--ink); }
h1 { font-size:2rem !important; font-weight:800 !important; }
h2 { font-size:1.35rem !important; font-weight:700 !important; }
h3 { font-size:1rem !important; font-weight:700 !important; }
p, label, .stCaption { color:var(--muted); }
div[data-testid="stMetric"] { background:white; border:1px solid var(--line); border-radius:14px; padding:18px 20px; }
div[data-testid="stMetricLabel"] { color:#718079; font-weight:600; font-size:.84rem; }
div[data-testid="stMetricValue"] { font-family:'Manrope',sans-serif; font-weight:800; letter-spacing:-.04em; }
.eyebrow { text-transform:uppercase; letter-spacing:.12em; font-size:.7rem; font-weight:700; color:var(--green); margin-bottom:.4rem; }
.subhead { color:var(--muted); font-size:.94rem; margin-top:-.7rem; margin-bottom:1.4rem; }
.panel { background:white; border:1px solid var(--line); border-radius:16px; padding:20px 22px; margin-bottom:14px; }
.run-row { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:15px 0; border-bottom:1px solid #eff2ef; }
.run-row:last-child { border-bottom:0; padding-bottom:0; }
.run-title { font-weight:700; color:var(--ink); }
.run-meta { color:var(--muted); font-size:.82rem; margin-top:4px; }
.pill { display:inline-block; border-radius:99px; padding:5px 10px; font-size:.73rem; font-weight:700; white-space:nowrap; }
.pill-passed { background:#e8f5ed; color:#25734d; }
.pill-failed { background:#fff0ed; color:#ba4c3b; }
.pill-other { background:#f0f2f1; color:#68746d; }
.brand { font-family:'Manrope',sans-serif; font-size:1.25rem; font-weight:800; letter-spacing:-.04em; padding:3px 0 24px; }
.brand span { color:#2f8766; }
.stButton > button { border-radius:9px; font-weight:700; min-height:2.65rem; }
.stButton > button[kind="primary"] { background:#28765c; border-color:#28765c; }
.stButton > button[kind="primary"]:hover { background:#1f624a; border-color:#1f624a; }
div[data-testid="stTabs"] button { font-weight:600; }
div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
.stAlert { border-radius:10px; }
</style>
""", unsafe_allow_html=True)


class APIError(Exception):
    pass


def api(method, path, **kwargs):
    try:
        response = requests.request(method, f"{API_URL}{path}", timeout=25, **kwargs)
    except requests.RequestException as exc:
        raise APIError(f"Could not reach the TestPilot API at {API_URL}. Start the backend and check TESTPILOT_API_URL.") from exc
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise APIError(str(detail) or f"Request failed ({response.status_code})")
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def call_or_warn(method, path, **kwargs):
    try:
        return api(method, path, **kwargs)
    except APIError as exc:
        st.error(str(exc))
        return None


def pretty_time(value):
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%b %d, %Y · %I:%M %p")
    except (ValueError, TypeError):
        return value


def status_pill(status):
    kind = "passed" if status == "passed" else "failed" if status in ("failed", "error") else "other"
    return f'<span class="pill pill-{kind}">{status.replace("_", " ").title()}</span>'


def show_runs(runs, limit=None):
    if not runs:
        st.info("No test runs yet. Start a run to see results and history here.")
        return
    for run in (runs[:limit] if limit else runs):
        st.markdown(f'''<div class="run-row"><div><div class="run-title">Run #{run["id"]} · {run.get("summary") or "Test suite completed"}</div><div class="run-meta">{pretty_time(run.get("created_at"))} &nbsp;·&nbsp; {run.get("duration_ms", 0) / 1000:.2f}s &nbsp;·&nbsp; {run.get("passed", 0)} passed &nbsp;·&nbsp; {run.get("failed", 0)} failed</div></div>{status_pill(run.get("status", "unknown"))}</div>''', unsafe_allow_html=True)


def heading(title, subtitle, eyebrow="TESTPILOT WORKSPACE"):
    st.markdown(f'<div class="eyebrow">{eyebrow}</div><h1>{title}</h1><div class="subhead">{subtitle}</div>', unsafe_allow_html=True)


def refresh():
    st.cache_data.clear()
    st.rerun()


def main():
    if st.session_state.pop("go_to_runs", False):
        st.session_state["nav_page"] = "Test runs"
    with st.sidebar:
        st.markdown('<div class="brand">✳ TestPilot <span>AI</span></div>', unsafe_allow_html=True)
        page = st.radio("WORKSPACE", ["Overview", "Projects", "Test runs", "Settings"], label_visibility="visible", key="nav_page")
        st.divider()
        health = call_or_warn("GET", "/health")
        if health:
            st.markdown("**System status**")
            st.caption("● API online" + (" · AI ready" if health.get("ai_configured") else " · AI not configured"))
            st.caption("Controlled demo environment")
        st.divider()
        st.caption("TESTPILOT AI  ·  v1.0")

    if page == "Overview":
        overview()
    elif page == "Projects":
        projects_page()
    elif page == "Test runs":
        runs_page()
    else:
        settings_page()


def overview():
    heading("Your testing, at a glance", "A clear view of suite health, recent runs, and the next action to take.")
    data = call_or_warn("GET", "/dashboard")
    if data is None:
        return
    projects = call_or_warn("GET", "/projects") or []
    left, right = st.columns([1.7, 1], gap="large")
    with left:
        st.markdown("### Workspace health")
        total, passed, failed, rate = st.columns(4)
        total.metric("Total runs", data.get("total_test_runs", 0))
        passed.metric("Tests passed", data.get("passed_tests", 0))
        failed.metric("Tests failed", data.get("failed_tests", 0), delta=None)
        rate.metric("Pass rate", f'{data.get("pass_rate", 0)}%')
        st.markdown("### Recent activity")
        show_runs(data.get("recent_runs", []), limit=7)
    with right:
        st.markdown("### Run a test suite")
        st.markdown('<div class="panel"><div class="eyebrow">CONTROLLED PYTEST SUITE</div><strong>TestPilot Sample</strong><p style="margin:.5rem 0 1rem">Run the bundled examples and inspect real results, tracebacks, and AI explanations.</p></div>', unsafe_allow_html=True)
        sample = next((p for p in projects if p["name"] == "TestPilot Sample"), None)
        if sample and st.button("▶  Run test suite", type="primary", use_container_width=True):
            with st.spinner("Running the controlled Pytest suite…"):
                result = call_or_warn("POST", f'/projects/{sample["id"]}/test-runs')
            if result:
                st.success(f'Run #{result["id"]} finished · {result.get("passed", 0)} passed · {result.get("failed", 0)} failed')
                st.session_state["selected_run"] = result["id"]
                st.session_state["go_to_runs"] = True
                st.cache_data.clear()
                st.rerun()
        st.markdown("### Needs attention")
        bugs = data.get("recent_bugs", [])
        if bugs:
            show_runs(bugs, limit=4)
        else:
            st.success("No failing runs in recent activity.")
        st.caption(f"{len(projects)} project{'s' if len(projects) != 1 else ''} in this workspace")


def projects_page():
    heading("Projects", "Organize test suites and keep their execution history together.", "WORKSPACE / PROJECTS")
    projects = call_or_warn("GET", "/projects")
    if projects is None:
        return
    add, listing = st.columns([.85, 1.6], gap="large")
    with add:
        st.markdown("### Add a project")
        with st.form("new_project", clear_on_submit=True):
            name = st.text_input("Project name", placeholder="e.g. Payments API")
            description = st.text_area("Description", placeholder="What does this project cover?", height=100)
            submitted = st.form_submit_button("Create project", type="primary", use_container_width=True)
        if submitted:
            result = call_or_warn("POST", "/projects", json={"name": name, "description": description, "project_type": "python-pytest"})
            if result:
                st.success(f'{result["name"]} added to your workspace.')
                st.cache_data.clear()
                st.rerun()
        st.info("Execution is currently enabled for the bundled TestPilot Sample suite. Other project types are saved for workspace organization.")
    with listing:
        st.markdown(f"### All projects <span style='color:#718079;font-size:.9rem'>({len(projects)})</span>", unsafe_allow_html=True)
        if not projects:
            st.info("No projects yet.")
        for project in projects:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{project['name']}**")
                    st.caption(project.get("description") or "No description provided")
                    st.caption(f"Python · Pytest  ·  Added {pretty_time(project.get('created_at'))}")
                with col2:
                    if project["name"] != "TestPilot Sample" and st.button("Remove", key=f'remove_{project["id"]}'):
                        try:
                            api("DELETE", f'/projects/{project["id"]}')
                            st.cache_data.clear()
                            st.rerun()
                        except APIError as exc:
                            st.error(str(exc))


def runs_page():
    heading("Test runs", "Browse executions, open a run, and investigate failures with context.", "WORKSPACE / TEST RUNS")
    runs = call_or_warn("GET", "/test-runs?limit=100")
    if runs is None:
        return
    if not runs:
        st.info("Your run history is empty. Visit Overview to launch the sample suite.")
        return
    statuses = ["All statuses"] + sorted({r.get("status", "unknown") for r in runs})
    filters = st.columns([1, 1, 3])
    selected_status = filters[0].selectbox("Status", statuses)
    query = filters[1].text_input("Find run", placeholder="# or summary")
    filtered = [r for r in runs if (selected_status == "All statuses" or r.get("status") == selected_status) and (not query or query.lower().replace("#", "") in str(r.get("id", "")).lower() or query.lower() in r.get("summary", "").lower())]
    filters[2].markdown(f"<div style='padding-top:2rem;color:#718079'>{len(filtered)} of {len(runs)} runs</div>", unsafe_allow_html=True)
    if not filtered:
        st.info("No runs match these filters.")
        return
    options = {f'Run #{r["id"]} · {r.get("status", "unknown").title()} · {pretty_time(r.get("created_at"))}': r["id"] for r in filtered}
    selected = st.selectbox("Select a run to inspect", list(options), index=next((i for i, x in enumerate(options.values()) if x == st.session_state.get("selected_run")), 0))
    run_id = options[selected]
    show_runs([r for r in filtered if r["id"] == run_id])
    run = call_or_warn("GET", f"/test-runs/{run_id}")
    if not run:
        return
    metrics = st.columns(5)
    for col, label, value in zip(metrics, ["Passed", "Failed", "Skipped", "Errors", "Duration"], [run.get("passed", 0), run.get("failed", 0), run.get("skipped", 0), run.get("errors", 0), f'{run.get("duration_ms", 0) / 1000:.2f}s']):
        col.metric(label, value)
    results_tab, analysis_tab = st.tabs(["Execution output", "AI investigation"])
    with results_tab:
        st.markdown("#### Run summary")
        st.write(run.get("summary") or "No summary available.")
        st.markdown("#### Pytest output")
        st.code(run.get("output") or "No output captured.", language="text", line_numbers=True)
        report = call_or_warn("GET", f"/test-runs/{run_id}/report")
        if report:
            st.download_button("Download run report (JSON)", data=json.dumps(report, indent=2), file_name=f"testpilot-run-{run_id}.json", mime="application/json")
    with analysis_tab:
        st.markdown("#### Understand this failure")
        st.caption("AI analysis is advisory and does not change the recorded test result.")
        if run.get("failed", 0) or run.get("errors", 0) or run.get("status") != "passed":
            ai1, ai2 = st.columns(2)
            with ai1:
                if st.button("Explain failure", type="primary", use_container_width=True):
                    with st.spinner("Reviewing the failure…"):
                        result = call_or_warn("POST", f"/test-runs/{run_id}/analyze")
                    if result:
                        st.session_state[f"analysis_{run_id}"] = {**result, "kind": "analysis"}
            with ai2:
                if st.button("Suggest additional tests", use_container_width=True):
                    with st.spinner("Generating test ideas…"):
                        result = call_or_warn("POST", f"/test-runs/{run_id}/generate-tests")
                    if result:
                        st.session_state[f"analysis_{run_id}"] = {**result, "kind": "generated_tests"}
            analyses = run.get("analyses", [])
            prior = st.session_state.get(f"analysis_{run_id}")
            if prior and not analyses:
                analyses = [prior]
            if analyses:
                for analysis in analyses:
                    with st.container(border=True):
                        st.caption(f'{analysis.get("kind", "analysis").replace("_", " ").title()} · {pretty_time(analysis.get("created_at"))}')
                        st.markdown(analysis.get("content") or analysis.get("message") or "No analysis text returned.")
            else:
                st.info("Choose an investigation action to get started.")
        else:
            st.success("This run passed. AI investigation is available for failed runs.")


def settings_page():
    heading("Settings", "Check your API connection and AI provider readiness.", "WORKSPACE / SETTINGS")
    settings = call_or_warn("GET", "/settings")
    if settings is None:
        return
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("### API connection")
        health = call_or_warn("GET", "/health")
        with st.container(border=True):
            st.markdown("**TestPilot backend**")
            if health and health.get("status") == "ok":
                st.success("Connected · API is responding")
            else:
                st.error("Backend unavailable")
            st.caption(API_URL)
            st.caption("Execution mode: controlled sample suite")
    with c2:
        st.markdown("### Gemini integration")
        with st.container(border=True):
            st.markdown("**AI failure analysis**")
            st.caption(f'Model · {settings.get("ai_model", "not specified")}')
            if settings.get("ai_configured"):
                st.success("API key configured on the backend")
            else:
                st.warning("No Gemini API key configured")
            st.caption("The key stays on the backend and is never sent to this dashboard.")
            if st.button("Test Gemini connection", use_container_width=True):
                with st.spinner("Checking provider connection…"):
                    result = call_or_warn("POST", "/settings/gemini-test")
                if result:
                    if result.get("status") == "connected":
                        st.success(result.get("message", "Gemini connection verified."))
                    elif result.get("status") == "not_configured":
                        st.info(result.get("message", "Gemini is not configured."))
                    else:
                        st.error(result.get("message", "Could not connect to Gemini."))
    st.markdown("### About this workspace")
    st.markdown('<div class="panel">TestPilot executes a fixed, bundled test suite for this demo. It does not run uploaded code or arbitrary commands. AI explanations and generated test ideas are suggestions for review.</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
