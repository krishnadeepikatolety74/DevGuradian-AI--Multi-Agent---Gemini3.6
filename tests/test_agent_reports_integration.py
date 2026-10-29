"""
Test Autonomous Agent Activity Reports & Verified Accuracy Pipeline Integration
"""
import pytest
import json
import uuid
from db import get_standalone_db, init_db
from services.project_service import (
    create_project,
    get_project_by_id,
    get_project_agent_executions
)
from services.agent_metrics_service import AgentMetricsService
from services.workflow_service import (
    record_agent_execution_start,
    record_agent_execution_complete,
    record_agent_execution_fail
)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_project_generation_creates_linked_execution_records():
    """Requirement 1, 2, 12, 15: Pre-seeded execution records linked to project & run ID with concrete tasks."""
    user_id = 1
    proj_name = f"HealthTracker Pro {uuid.uuid4().hex[:6]}"
    proj_desc = "A patient health tracking application with appointment scheduling, biometric vitals tracking, and medication reminders."
    
    project_id = create_project(
        user_id=user_id,
        name=proj_name,
        description=proj_desc,
        app_type="Web App",
        ui_requirements={"pages": ["Dashboard", "Vitals Log", "Appointments", "Medications"]}
    )
    
    assert project_id is not None
    
    # 1. Verify generation run was created
    conn = get_standalone_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM project_generation_runs WHERE project_id = ?", (project_id,))
    runs = [dict(r) for r in cur.fetchall()]
    assert len(runs) >= 1
    run_id = runs[0]["id"]
    assert run_id.startswith("run_")
    
    # 2. Verify all 8 canonical agent execution records pre-seeded and linked to run_id
    reports = AgentMetricsService.get_agent_reports_for_project(project_id)
    assert len(reports) == 8
    
    for r in reports:
        assert r["project_id"] == project_id
        assert r["generation_run_id"] == run_id
        assert r["status"] == "pending"
        assert r["result_status"] == "Pending"
        # Requirement 2: concrete task assigned based on project requirements
        assert r["task_assigned"] is not None and len(r["task_assigned"]) > 10
        assert proj_name in r["task_assigned"] or "HealthTracker" in r["task_assigned"] or "biometric" in r["task_assigned"] or "patient" in r["task_assigned"] or "web" in r["task_assigned"].lower()
        # Requirement 15: Not started / pending without pretending work performed
        assert r["work_performed"] is None or r["work_performed"] == ""
        # Requirement 6, 9, 10: 0% completion, no fabricated accuracy
        assert r["task_completion_score"] == 0.0
        assert r["validation_pass_rate"] is None
        assert r["test_pass_rate"] is None
        assert r["accuracy_status"] == "Accuracy: Not yet verified"
        assert r["overall_quality_score"] is None
    
    conn.close()


def test_agent_execution_updates_live_and_preserves_metrics():
    """Requirement 3, 5, 6, 7, 8, 9, 10: Real metrics recording upon execution."""
    user_id = 1
    proj_name = f"FinScan AI {uuid.uuid4().hex[:6]}"
    project_id = create_project(
        user_id=user_id,
        name=proj_name,
        description="Financial document analyzer and expense categorization engine.",
        app_type="Web App"
    )
    
    # Start Coding Agent execution
    exec_id = record_agent_execution_start(project_id, "coding")
    assert exec_id is not None
    
    # Check that status is running
    detail = AgentMetricsService.get_agent_report_detail(project_id, "coding")
    assert detail["status"] == "running"
    
    # Complete Coding Agent execution with empirical validation evidence
    files_created = ["app.py", "db.py", "services/expense_service.py", "templates/expenses.html"]
    record_agent_execution_complete(
        exec_id=exec_id,
        project_id=project_id,
        agent_key="coding",
        files_created=files_created,
        duration_ms=4520,
        result_status="Success",
        work_performed="Generated 4 source files including SQLite expense model and responsive dashboard.",
        output_produced="Synthesized full project tree with 4 production files.",
        validation_performed="AST syntax check validated 3/3 Python modules.",
        evidence={"ast_checks": 3, "syntax_valid": True},
        validation_pass_rate=100.0,
        test_pass_rate=None
    )
    
    # Retrieve report and verify
    detail = AgentMetricsService.get_agent_report_detail(project_id, "coding")
    assert detail["status"] == "completed"
    assert detail["result_status"] == "Success"
    assert detail["execution_duration_ms"] == 4520
    assert detail["task_completion_score"] == 100.0
    assert detail["validation_pass_rate"] == 100.0
    assert detail["files_created"] == files_created
    # Requirement 10: empirical accuracy verified
    assert detail["accuracy_score"] == 100.0
    assert "Verified from" in detail["accuracy_status"]
    # Requirement 9: quality score present when evidence exists
    assert detail["overall_quality_score"] is not None


def test_pipeline_failure_preserves_error_and_blocks_downstream():
    """Requirement 16: Failure displays actual error and marks downstream agents as Blocked."""
    user_id = 1
    project_id = create_project(
        user_id=user_id,
        name=f"FailingProj {uuid.uuid4().hex[:6]}",
        description="Project to test error handling.",
        app_type="Web App"
    )
    
    # Start and fail Architecture Agent
    record_agent_execution_start(project_id, "architecture")
    err_msg = "SyntaxError: invalid database schema configuration in model topology"
    record_agent_execution_fail(
        project_id=project_id,
        agent_key="architecture",
        error_message=err_msg
    )
    
    reports = AgentMetricsService.get_agent_reports_for_project(project_id)
    arch_report = next(r for r in reports if r["agent_key"] == "architecture")
    assert arch_report["status"] == "failed"
    assert arch_report["result_status"] == "Failed"
    assert err_msg in arch_report["errors_or_limitations"]
    
    # Downstream agents (e.g. coding, testing) should be Blocked
    coding_report = next(r for r in reports if r["agent_key"] == "coding")
    assert coding_report["result_status"] == "Blocked"
    assert "Blocked" in coding_report["errors_or_limitations"]


def test_project_isolation():
    """Requirement 13: Reports from one project are NEVER displayed as belonging to another."""
    user_id = 1
    proj_a_id = create_project(user_id=user_id, name="Project Alpha", description="Alpha desc")
    proj_b_id = create_project(user_id=user_id, name="Project Beta", description="Beta desc")
    
    # Record custom work for Project Alpha's requirement agent
    record_agent_execution_complete(
        project_id=proj_a_id,
        agent_key="requirement",
        work_performed="Alpha exclusive requirement work: High-frequency trading requirements.",
        result_status="Success"
    )
    
    # Verify Alpha report has it
    rep_a = AgentMetricsService.get_agent_report_detail(proj_a_id, "requirement")
    assert "Alpha exclusive" in rep_a["work_performed"]
    
    # Verify Beta report NEVER has Alpha's work
    rep_b = AgentMetricsService.get_agent_report_detail(proj_b_id, "requirement")
    assert "Alpha exclusive" not in (rep_b["work_performed"] or "")
    assert rep_b["project_id"] == proj_b_id
    assert rep_a["project_id"] == proj_a_id


def test_api_endpoints_and_ui_rendering():
    """Requirement 4, 11, 14, 17: Test HTTP API endpoints and HTML workspace page rendering."""
    from app import app
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    
    with app.test_client() as client:
        # Simulate authenticated session
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "IntegrationTester"
            sess["user_role"] = "Architect"
            sess["csrf_token"] = "mock_csrf_token"
        
        # 1. Create a test project
        proj_id = create_project(
            user_id=1,
            name="CloudAudit Sentinel",
            description="Automated AWS and GCP multi-cloud infrastructure compliance and security posture scanner.",
            app_type="Web App",
            ui_requirements={"pages": ["Overview", "Policy Scans", "Compliance Matrix"]}
        )
        assert proj_id is not None
        
        # 2. Call GET /api/projects/<id>/agents/reports
        resp = client.get(f"/api/projects/{proj_id}/agents/reports")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reports" in data
        assert len(data["reports"]) == 8
        assert data["progress_pct"] == 0
        
        # Verify initial pending state in API
        first_rep = data["reports"][0]
        assert first_rep["status"] == "pending"
        assert first_rep["task_completion_score"] == 0.0
        assert first_rep["accuracy_status"] == "Accuracy: Not yet verified"
        assert "CloudAudit Sentinel" in first_rep["task_assigned"] or "compliance" in first_rep["task_assigned"].lower() or "security" in first_rep["task_assigned"].lower()
        
        # 3. Simulate execution of Requirement and Architecture stages
        record_agent_execution_start(proj_id, "requirement")
        record_agent_execution_complete(
            project_id=proj_id,
            agent_key="requirement",
            work_performed="Synthesized ISO 27001 and CIS Benchmark cloud compliance rules.",
            result_status="Success",
            validation_performed="Taxonomy schema checks passed.",
            validation_pass_rate=100.0,
            duration_ms=2100
        )
        
        # Call single-agent inspection endpoint: GET /api/projects/<id>/agents/requirement
        detail_resp = client.get(f"/api/projects/{proj_id}/agents/requirement")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.get_json()
        assert "report" in detail_data
        rep = detail_data["report"]
        assert rep["status"] == "completed"
        assert rep["result_status"] == "Success"
        assert "ISO 27001" in rep["work_performed"]
        assert rep["task_completion_score"] == 100.0
        assert rep["execution_duration_ms"] == 2100
        
        # 4. Request the full Workspace HTML page: GET /projects/<id>/workspace
        html_resp = client.get(f"/projects/{proj_id}/workspace")
        assert html_resp.status_code == 200
        html = html_resp.get_data(as_text=True)
        
        # Check Section 8 rendered elements
        assert "Autonomous Agent Activity Reports &amp; Verified Accuracy" in html
        assert proj_id in html
        assert "CloudAudit Sentinel" in html
        assert "COMPLETED" in html
        assert "ISO 27001" in html
        assert "Inspect Details &rarr;" in html
        assert "agentInspectionModal" in html
        assert "openAgentInspection" in html

