import os
import uuid
import json
from typing import Dict, Any, List, Optional
from db import get_standalone_db

from services.workspace_manager import (
    validate_project_name,
    generate_project_id,
    allocate_project_workspace,
    get_project_workspace
)

def get_default_task_for_agent(
    agent_key: str,
    name: str,
    description: str,
    app_type: str = "Web App",
    ui_requirements: Optional[Dict[str, Any]] = None
) -> str:
    """Derive project-specific assigned task description based on requirements and scope."""
    ui_req = ui_requirements or {}
    pages = ui_req.get("required_pages", [])
    custom = ui_req.get("custom_pages", "")
    pages_desc = f"{len(pages)} UI pages ({', '.join(pages[:3])}...)" if pages else "UI views"
    if custom:
        pages_desc += f" including custom modules: {custom}"

    tasks = {
        "requirement": f"Analyze scope and synthesize structured functional and non-functional requirements specifications for {name} ({app_type}) based on: {description[:120]}...",
        "architecture": f"Design modular layered system architecture, component relations, SQLite schema, and API endpoint contracts for {name}.",
        "coding": f"Generate clean, runnable application code, database models, business logic services, and {pages_desc} for {name}.",
        "testing": f"Construct automated unit and route test assertions, verify HTTP responses, and run test suite in isolated sandbox for {name}.",
        "security": f"Execute static AST security scanner, verify zero critical vulnerabilities, credential leaks, or injection risks in {name}.",
        "review": f"Audit code quality, maintainability index, separation of concerns, and PEP 8 guidelines for {name}.",
        "deployment": f"Synthesize Dockerfile, containerization specifications, and local runtime startup command for {name}.",
        "project_manager": f"Coordinate agent execution, verify empirical metrics, and compile executive delivery report with 18 enterprise sections for {name}."
    }
    return tasks.get(agent_key, f"Execute operational tasks for {agent_key} on {name}.")

def create_project(user_id: int, name: str, description: str, app_type: str = "Web App",
                   language: str = "Python Flask", tech_preferences: str = "",
                   selected_ide: str = "vscode", ide_custom_path: Optional[str] = None,
                   ui_requirements: Optional[Dict[str, Any]] = None,
                   generation_mode: str = "both") -> str:
    """Create a new project record and initialize pending agent workflow with centralized workspace."""
    valid, msg = validate_project_name(name)
    if not valid:
        raise ValueError(msg)
        
    project_id = generate_project_id()
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    
    # Resolve generation mode
    gen_mode = (ui_requirements or {}).get("generation_mode") or generation_mode or "both"
    if ui_requirements:
        ui_requirements["generation_mode"] = gen_mode
    ui_req_json = json.dumps(ui_requirements) if ui_requirements else None
    
    # Allocate workspace directory under GENERATED_PROJECTS_DIR
    workspace_dir = allocate_project_workspace(project_id, name)
    
    # Automatically assign unique, conflict-free port upon registration
    from services.port_manager import PortManager
    assigned_port = PortManager.allocate_port(project_id, project_name=name)
    
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO projects (
                id, user_id, name, description, app_type, language,
                tech_preferences, selected_ide, ide_custom_path, ui_requirements,
                generation_mode, workspace_path, assigned_port, current_stage, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'requirements', 'in_progress')
        """, (
            project_id, user_id, name.strip(), description.strip(), app_type.strip(),
            language.strip(), tech_preferences.strip(), (selected_ide or "vscode").lower().strip(),
            ide_custom_path.strip() if ide_custom_path else None, ui_req_json,
            gen_mode, str(workspace_dir), assigned_port
        ))
        
        # 1. Create project generation run record linked to this project
        cursor.execute("""
            INSERT INTO project_generation_runs (id, project_id, status, trigger_type, started_at)
            VALUES (?, ?, 'pending', 'wizard', CURRENT_TIMESTAMP)
        """, (run_id, project_id))

        # 2. Pre-seed 8 agent execution rows with real assigned tasks linked to generation run
        agents = [
            "requirement",
            "architecture",
            "coding",
            "testing",
            "security",
            "review",
            "deployment",
            "project_manager"
        ]
        for key in agents:
            task_assigned = get_default_task_for_agent(
                agent_key=key,
                name=name.strip(),
                description=description.strip(),
                app_type=app_type.strip(),
                ui_requirements=ui_requirements
            )
            cursor.execute("""
                INSERT INTO agent_executions (
                    project_id, generation_run_id, agent_key, status, result_status,
                    task_assigned, work_performed, output_produced, validation_performed,
                    accuracy_score, accuracy_status, task_completion_score, validation_pass_rate,
                    test_pass_rate, overall_quality_score, started_at, completed_at
                )
                VALUES (?, ?, ?, 'pending', 'Pending', ?, NULL, NULL, NULL, NULL, 'Accuracy: Not yet verified', 0.0, NULL, NULL, NULL, NULL, NULL)
            """, (project_id, run_id, key, task_assigned))
            
    conn.close()
    return project_id

def get_project_by_id(project_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieve project by ID, optionally verifying ownership, with resolved workspace."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute("SELECT * FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
    else:
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        ws = get_project_workspace(d["id"])
        d["workspace_path"] = str(ws)
        d["workspace_dir_name"] = ws.name
    except Exception:
        pass
    return d

def get_user_projects(user_id: int) -> List[Dict[str, Any]]:
    """Fetch all projects owned by user, enriched with workspace path and file count."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*,
               (SELECT COUNT(*) FROM project_files pf WHERE pf.project_id = p.id) as files_count
        FROM projects p
        WHERE p.user_id = ?
        ORDER BY p.updated_at DESC, p.created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    projects = []
    for r in rows:
        d = dict(r)
        try:
            ws = get_project_workspace(d["id"])
            d["workspace_path"] = str(ws)
            d["workspace_dir_name"] = ws.name
        except Exception:
            d["workspace_path"] = d.get("workspace_path") or ""
            d["workspace_dir_name"] = os.path.basename(d["workspace_path"]) if d["workspace_path"] else d["id"]
        projects.append(d)
        
    return projects

def get_dashboard_stats(user_id: int) -> Dict[str, Any]:
    """Calculate real, live statistics strictly derived from the SQLite database."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM projects WHERE user_id = ?", (user_id,))
    total = cursor.fetchone()["total"]
    
    cursor.execute("SELECT COUNT(*) as in_progress FROM projects WHERE user_id = ? AND status = 'in_progress'", (user_id,))
    in_progress = cursor.fetchone()["in_progress"]
    
    cursor.execute("SELECT COUNT(*) as completed FROM projects WHERE user_id = ? AND status = 'completed'", (user_id,))
    completed = cursor.fetchone()["completed"]
    
    cursor.execute("SELECT COUNT(*) as failed FROM projects WHERE user_id = ? AND status = 'failed'", (user_id,))
    failed = cursor.fetchone()["failed"]
    
    # Count actual architecture diagrams generated
    cursor.execute("""
        SELECT COUNT(pa.id) as total_arch 
        FROM project_architecture pa
        JOIN projects p ON pa.project_id = p.id
        WHERE p.user_id = ?
    """, (user_id,))
    total_arch = cursor.fetchone()["total_arch"]
    
    # Count actual documentation generated
    cursor.execute("""
        SELECT COUNT(pd.id) as total_docs 
        FROM project_documentation pd
        JOIN projects p ON pd.project_id = p.id
        WHERE p.user_id = ?
    """, (user_id,))
    total_docs = cursor.fetchone()["total_docs"]
    
    # Fetch recent architectures
    cursor.execute("""
        SELECT pa.*, p.name as project_name
        FROM project_architecture pa
        JOIN projects p ON pa.project_id = p.id
        WHERE p.user_id = ?
        ORDER BY pa.updated_at DESC, pa.id DESC
        LIMIT 4
    """, (user_id,))
    recent_arch = [dict(r) for r in cursor.fetchall()]
    
    # Fetch recent documents
    cursor.execute("""
        SELECT pd.*, p.name as project_name
        FROM project_documentation pd
        JOIN projects p ON pd.project_id = p.id
        WHERE p.user_id = ?
        ORDER BY pd.updated_at DESC, pd.id DESC
        LIMIT 4
    """, (user_id,))
    recent_docs = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    # Calculate success rate
    closed = completed + failed
    if closed > 0:
        success_rate = int((completed / closed) * 100)
    elif total > 0:
        success_rate = int((completed / total) * 100)
    else:
        success_rate = 100
        
    return {
        "total_projects": total,
        "in_progress": in_progress,
        "completed": completed,
        "failed": failed,
        "success_rate": f"{success_rate}%",
        "total_architectures": total_arch,
        "total_documents": total_docs,
        "recent_architectures": recent_arch,
        "recent_documents": recent_docs
    }

def log_project_activity(project_id: str, action_type: str, title: str, details: str = "", status: str = "success") -> bool:
    """Record an audit trail event in project_activity_logs."""
    try:
        conn = get_standalone_db()
        with conn:
            conn.execute("""
                INSERT INTO project_activity_logs (project_id, action_type, title, details, status)
                VALUES (?, ?, ?, ?, ?)
            """, (project_id, action_type, title, details, status))
        conn.close()
        return True
    except Exception as e:
        print(f"Error logging activity for project {project_id}: {e}")
        return False

def get_project_activity_logs(project_id: Optional[str] = None, user_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve activity logs with optional project or user filter."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    if project_id:
        cursor.execute("""
            SELECT pal.*, p.name as project_name
            FROM project_activity_logs pal
            JOIN projects p ON pal.project_id = p.id
            WHERE pal.project_id = ?
            ORDER BY pal.created_at DESC, pal.id DESC
            LIMIT ?
        """, (project_id, limit))
    elif user_id is not None:
        cursor.execute("""
            SELECT pal.*, p.name as project_name
            FROM project_activity_logs pal
            JOIN projects p ON pal.project_id = p.id
            WHERE p.user_id = ?
            ORDER BY pal.created_at DESC, pal.id DESC
            LIMIT ?
        """, (user_id, limit))
    else:
        cursor.execute("""
            SELECT pal.*, p.name as project_name
            FROM project_activity_logs pal
            JOIN projects p ON pal.project_id = p.id
            ORDER BY pal.created_at DESC, pal.id DESC
            LIMIT ?
        """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_project_agent_executions(project_id: str) -> List[Dict[str, Any]]:
    """Get all 8 agent execution status items for a project in order."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            ae.id,
            ae.project_id,
            ae.generation_run_id,
            ae.agent_key,
            ae.status,
            ae.result_status,
            ae.task_assigned,
            ae.work_performed,
            ae.files_created,
            ae.files_modified,
            ae.output_produced,
            ae.validation_performed,
            ae.accuracy_score,
            ae.accuracy_status,
            ae.task_completion_score,
            ae.validation_pass_rate,
            ae.test_pass_rate,
            ae.overall_quality_score,
            ae.errors_or_limitations,
            ae.evidence_json,
            ae.input_data,
            ae.output_data,
            ae.step_logs,
            ae.error_message,
            ae.execution_time_ms,
            ae.started_at,
            ae.completed_at,
            a.name as agent_name,
            a.description as agent_description,
            a.icon as agent_icon,
            a.stage_order
        FROM agent_executions ae
        JOIN agents a ON ae.agent_key = a.key
        WHERE ae.project_id = ?
        ORDER BY a.stage_order ASC, ae.id DESC
    """, (project_id,))
    
    # Keep only the latest execution per agent key
    seen = set()
    ordered_list = []
    for row in cursor.fetchall():
        d = dict(row)
        if d["agent_key"] not in seen:
            seen.add(d["agent_key"])
            try:
                d["step_logs_list"] = json.loads(d["step_logs"] or "[]")
            except Exception:
                d["step_logs_list"] = []
            try:
                d["files_created"] = json.loads(d["files_created"] or "[]")
            except Exception:
                d["files_created"] = []
            try:
                d["files_modified"] = json.loads(d["files_modified"] or "[]")
            except Exception:
                d["files_modified"] = []
            try:
                d["evidence"] = json.loads(d["evidence_json"] or "{}")
            except Exception:
                d["evidence"] = {}
            ordered_list.append(d)
            
    conn.close()
    ordered_list.sort(key=lambda x: x["stage_order"])
    return ordered_list

def delete_project(project_id: str, user_id: int) -> bool:
    """Delete project and all associated cascading records."""
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
        count = cursor.rowcount
    conn.close()
    return count > 0
