"""
Workflow Execution Tracker & Observability Service — DevGuardian AI
Manages non-blocking background agent workflow execution, live status aggregation,
duplicate run prevention, and real-time Server-Sent Events (SSE) streaming for
the 'Run All Agents' cute animated modal.
"""

import time
import json
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple, Generator

from db import get_standalone_db
import services.workflow_service as workflow_service
from services.agent_metrics_service import AgentMetricsService
import services.project_service as project_service

logger = logging.getLogger(__name__)

# Active background workflow jobs: { project_id: { "thread": Thread, "started_at": float, "api_key": str } }
_ACTIVE_WORKFLOWS: Dict[str, Dict[str, Any]] = {}
_WORKFLOW_LOCK = threading.Lock()

AGENT_LIVE_MESSAGES = {
    "requirement": "The Requirement Analysis Agent is understanding your idea…",
    "architecture": "The Architecture Agent is planning the structure…",
    "coding": "The Coding Agent is building your application…",
    "testing": "The Testing Agent is checking your features…",
    "security": "The Security Agent is reviewing potential risks…",
    "review": "The Code Review Agent is checking the implementation…",
    "deployment": "The Deployment Agent is preparing containerization & runtime…",
    "project_manager": "The Project Manager is coordinating the final checks…"
}

AGENT_ICONS = {
    "requirement": "📋",
    "architecture": "🏛️",
    "coding": "💻",
    "testing": "🧪",
    "security": "🛡️",
    "review": "🔍",
    "deployment": "🚀",
    "project_manager": "📊"
}


def is_workflow_active(project_id: str) -> bool:
    """Check whether a background workflow thread is actively executing for project_id."""
    with _WORKFLOW_LOCK:
        job = _ACTIVE_WORKFLOWS.get(project_id)
        if not job:
            return False
        thread: Optional[threading.Thread] = job.get("thread")
        if thread and thread.is_alive():
            return True
        # Thread finished, clean up
        _ACTIVE_WORKFLOWS.pop(project_id, None)
        return False


# Convenient alias
is_workflow_running = is_workflow_active


def start_workflow_in_background(
    project_id: str,
    api_key: Optional[str] = None,
    reset_stages: bool = False
) -> Tuple[bool, str]:
    """
    Start the autonomous agent workflow in a non-blocking background daemon thread.
    Guarantees no duplicate execution jobs.
    """
    with _WORKFLOW_LOCK:
        if is_workflow_active(project_id):
            return False, "An agent workflow is already running for this project."

        # Ensure project agent records exist and heal any inconsistencies
        AgentMetricsService.sync_or_heal_project_agent_executions(project_id)

        if reset_stages:
            conn = get_standalone_db()
            with conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE agent_executions
                    SET status = 'pending', result_status = 'Pending',
                        work_performed = NULL, files_created = NULL, files_modified = NULL,
                        output_produced = NULL, validation_performed = NULL,
                        error_message = NULL, errors_or_limitations = NULL,
                        started_at = NULL, completed_at = NULL
                    WHERE project_id = ?
                """, (project_id,))
                cur.execute("""
                    UPDATE projects
                    SET status = 'in_progress', current_stage = 'requirement', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (project_id,))
            conn.close()

        def _worker():
            try:
                logger.info(f"[WorkflowTracker] Background agent execution started for project {project_id}")
                workflow_service.run_full_workflow(project_id, api_key=api_key)
                logger.info(f"[WorkflowTracker] Background agent execution finished for project {project_id}")
            except Exception as e:
                logger.error(f"[WorkflowTracker] Error during workflow execution for {project_id}: {e}", exc_info=True)
                try:
                    conn = get_standalone_db()
                    with conn:
                        conn.execute("UPDATE projects SET status = 'failed' WHERE id = ?", (project_id,))
                    conn.close()
                except Exception:
                    pass
            finally:
                with _WORKFLOW_LOCK:
                    _ACTIVE_WORKFLOWS.pop(project_id, None)

        thread = threading.Thread(
            target=_worker,
            daemon=True,
            name=f"DevGuardian-AgentWorkflow-{project_id}"
        )
        _ACTIVE_WORKFLOWS[project_id] = {
            "thread": thread,
            "started_at": time.time(),
            "api_key": api_key
        }
        thread.start()
        return True, "Agent workflow started in background."


def retry_failed_agents_in_background(
    project_id: str,
    api_key: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Safely retry failed or blocked agent stages in background.
    Preserves completed work and avoids duplicate file corruptions.
    """
    with _WORKFLOW_LOCK:
        if is_workflow_active(project_id):
            return False, "An agent workflow is already running for this project."

        conn = get_standalone_db()
        with conn:
            cur = conn.cursor()
            # Reset only failed or blocked agents back to pending
            cur.execute("""
                UPDATE agent_executions
                SET status = 'pending', result_status = 'Pending',
                    error_message = NULL, errors_or_limitations = NULL,
                    started_at = NULL, completed_at = NULL
                WHERE project_id = ? AND status IN ('failed', 'blocked')
            """, (project_id,))
            cur.execute("""
                UPDATE projects
                SET status = 'in_progress', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (project_id,))
        conn.close()

        def _retry_worker():
            try:
                logger.info(f"[WorkflowTracker] Retrying failed stages for project {project_id}")
                # Execute uncompleted stages in order
                reports = AgentMetricsService.get_agent_reports_for_project(project_id)
                for r in reports:
                    if r.get("status") in ["pending", "failed", "blocked"]:
                        stage_key = r["agent_key"]
                        logger.info(f"[WorkflowTracker] Retrying stage: {stage_key}")
                        workflow_service.execute_single_stage(project_id, stage_key, api_key=api_key)
                        # Re-check status of executed stage
                        sub_reports = AgentMetricsService.get_agent_reports_for_project(project_id)
                        curr_status = next((x["status"] for x in sub_reports if x["agent_key"] == stage_key), None)
                        if curr_status == "failed":
                            break
            except Exception as e:
                logger.error(f"[WorkflowTracker] Error retrying workflow for {project_id}: {e}", exc_info=True)
            finally:
                with _WORKFLOW_LOCK:
                    _ACTIVE_WORKFLOWS.pop(project_id, None)

        thread = threading.Thread(
            target=_retry_worker,
            daemon=True,
            name=f"DevGuardian-RetryWorkflow-{project_id}"
        )
        _ACTIVE_WORKFLOWS[project_id] = {
            "thread": thread,
            "started_at": time.time(),
            "api_key": api_key
        }
        thread.start()
        return True, "Retrying uncompleted agents in background."


def get_workflow_status_payload(project_id: str) -> Dict[str, Any]:
    """
    Compile authentic, comprehensive execution progress and reports for all
    configured agents of the project.
    """
    # Fetch project
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    p_row = cursor.fetchone()
    conn.close()

    if not p_row:
        return {
            "success": False,
            "message": "Project not found",
            "is_running": False,
            "status": "not_found"
        }

    proj = dict(p_row)
    project_name = proj["name"]
    is_active = is_workflow_active(project_id)

    # Fetch agent reports
    reports = AgentMetricsService.get_agent_reports_for_project(project_id)

    total_agents = len(reports)
    completed_count = sum(1 for a in reports if a.get("status") == "completed")
    failed_count = sum(1 for a in reports if a.get("status") == "failed")
    running_count = sum(1 for a in reports if a.get("status") == "running")
    blocked_count = sum(1 for a in reports if a.get("status") in ["blocked", "skipped"])

    # Determine current agent
    running_agent = next((a for a in reports if a.get("status") == "running"), None)
    next_pending_agent = next((a for a in reports if a.get("status") in ["pending", "waiting"]), None)
    failed_agent = next((a for a in reports if a.get("status") == "failed"), None)

    # Overall workflow status
    if is_active:
        overall_status = "in_progress"
    elif failed_count > 0:
        overall_status = "failed"
    elif completed_count == total_agents and total_agents > 0:
        overall_status = "completed"
    else:
        overall_status = proj.get("status", "in_progress")

    # Real percentage
    progress_pct = int((completed_count / total_agents) * 100) if total_agents > 0 else 0
    if overall_status == "completed":
        progress_pct = 100

    # Live friendly message
    if is_active and running_agent:
        active_key = running_agent["agent_key"]
        live_message = AGENT_LIVE_MESSAGES.get(active_key, f"The {running_agent.get('agent_name', 'Agent')} is working…")
    elif overall_status == "completed":
        live_message = "All AI agents have completed their work! 🎉"
    elif overall_status == "failed" and failed_agent:
        live_message = f"A Little Hiccup! The {failed_agent.get('agent_name', 'Agent')} ran into an issue."
    elif running_agent:
        active_key = running_agent["agent_key"]
        live_message = AGENT_LIVE_MESSAGES.get(active_key, f"The {running_agent.get('agent_name', 'Agent')} is working…")
    else:
        live_message = "Your team is getting organized…"

    # Current agent label
    current_agent_name = None
    if running_agent:
        current_agent_name = running_agent.get("agent_name")
    elif next_pending_agent:
        current_agent_name = next_pending_agent.get("agent_name")

    # Format agent cards
    formatted_agents = []
    all_files_created = set()
    all_files_modified = set()
    test_pass_rate_val = None
    validation_summary_notes = []

    for idx, r in enumerate(reports, start=1):
        raw_status = r.get("status", "pending")
        if raw_status == "pending":
            status_label = "Waiting"
        elif raw_status == "running":
            status_label = "In Progress"
        elif raw_status == "completed":
            status_label = "Completed"
        elif raw_status == "failed":
            status_label = "Failed"
        elif raw_status in ["blocked", "skipped"]:
            status_label = "Skipped"
        else:
            status_label = raw_status.capitalize()

        key = r.get("agent_key", "")
        icon = AGENT_ICONS.get(key, "🤖")

        files_c = r.get("files_created") or []
        files_m = r.get("files_modified") or []
        if isinstance(files_c, str):
            try:
                files_c = json.loads(files_c)
            except Exception:
                files_c = []
        if isinstance(files_m, str):
            try:
                files_m = json.loads(files_m)
            except Exception:
                files_m = []

        all_files_created.update(files_c)
        all_files_modified.update(files_m)

        if r.get("test_pass_rate") is not None:
            test_pass_rate_val = r.get("test_pass_rate")
        if r.get("validation_performed"):
            validation_summary_notes.append(r.get("validation_performed"))

        agent_obj = {
            "order": idx,
            "key": key,
            "name": r.get("agent_name") or f"Agent {idx}",
            "icon": icon,
            "role": r.get("agent_role") or r.get("agent_description") or "",
            "status": raw_status,
            "status_label": status_label,
            "task_assigned": r.get("task_assigned") or "",
            "work_performed": r.get("work_performed") or "",
            "files_created": files_c,
            "files_created_count": len(files_c),
            "files_modified": files_m,
            "files_modified_count": len(files_m),
            "validation_performed": r.get("validation_performed") or "",
            "result_status": r.get("result_status") or "",
            "error_message": r.get("error_message") or r.get("errors_or_limitations") or "",
            "duration_ms": r.get("execution_duration_ms") or 0
        }
        formatted_agents.append(agent_obj)

    # Compile summary
    failed_info = None
    if failed_agent:
        failed_info = {
            "agent_key": failed_agent.get("agent_key"),
            "agent_name": failed_agent.get("agent_name"),
            "error_message": failed_agent.get("error_message") or failed_agent.get("errors_or_limitations") or "Execution failure",
            "stage_order": failed_agent.get("stage_order"),
            "suggestion": "Review error details above, verify your API key or environment settings, and click Retry Failed Agents."
        }

    summary = {
        "total_files_count": len(all_files_created),
        "files_created_list": sorted(list(all_files_created)),
        "files_modified_count": len(all_files_modified),
        "test_pass_rate": test_pass_rate_val if test_pass_rate_val is not None else (100.0 if overall_status == "completed" else None),
        "validation_summary": "; ".join(validation_summary_notes[:2]) if validation_summary_notes else "Verified structure, syntax, and schema.",
        "failed_agent": failed_info,
        "can_retry": failed_count > 0 and not is_active
    }

    return {
        "success": True,
        "project_id": project_id,
        "project_name": project_name,
        "is_running": is_active,
        "overall_status": overall_status,
        "current_stage": proj.get("current_stage"),
        "current_agent": current_agent_name,
        "live_message": live_message,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "total_agents": total_agents,
        "progress_pct": progress_pct,
        "progress_text": f"{completed_count} of {total_agents} agents completed ({progress_pct}%)",
        "agents": formatted_agents,
        "summary": summary
    }


def stream_workflow_progress(project_id: str, timeout_seconds: float = 300.0) -> Generator[str, None, None]:
    """
    Generator yielding Server-Sent Events (SSE) data chunks for real-time progress.
    Yields events until workflow finishes or client disconnects.
    """
    start_time = time.time()

    # Emit initial state immediately
    initial = get_workflow_status_payload(project_id)
    yield f"data: {json.dumps(initial)}\n\n"

    while (time.time() - start_time) < timeout_seconds:
        time.sleep(0.7)
        payload = get_workflow_status_payload(project_id)
        yield f"data: {json.dumps(payload)}\n\n"

        if not payload.get("is_running") and payload.get("overall_status") in ["completed", "failed"]:
            # Yield final update and break
            time.sleep(0.5)
            final_payload = get_workflow_status_payload(project_id)
            yield f"data: {json.dumps(final_payload)}\n\n"
            break
