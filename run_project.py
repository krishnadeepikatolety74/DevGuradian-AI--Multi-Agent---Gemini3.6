"""
DevGuardian AI — Centralized CLI Project Runner
Usage:
    python run_project.py <project_name_or_id> [--port PORT]

Examples:
    python run_project.py "HireSmart AI"
    python run_project.py "Smart Expense Tracker AI"
    python run_project.py proj_bdf4bf9f8d
    python run_project.py --list
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from db import get_standalone_db
from services.port_manager import PortManager
from services.workspace_manager import GENERATED_PROJECTS_DIR, get_project_workspace
from services.execution_service import (
    detect_or_create_project_entry_point,
    detect_project_stack
)


def list_projects():
    """List all available generated projects with their status and ports."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, workspace_path, assigned_port, entry_point FROM projects ORDER BY created_at ASC")
    rows = cursor.fetchall()
    conn.close()

    print("\nAvailable Generated Projects:")
    print("-" * 75)
    print(f"{'Project ID':<16} | {'Port':<6} | {'Entry Point':<22} | {'Name'}")
    print("-" * 75)
    for r in rows:
        p_id = r["id"]
        p_name = r["name"]
        p_port = r["assigned_port"] or PortManager.get_assigned_port(p_id) or "N/A"
        p_entry = r["entry_point"] or "app.py"
        print(f"{p_id:<16} | {str(p_port):<6} | {p_entry:<22} | {p_name}")
    print("-" * 75 + "\n")


def find_project(query: str):
    """Find a project by exact ID or partial name match."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    # 1. Exact ID
    cursor.execute("SELECT * FROM projects WHERE id = ?", (query,))
    row = cursor.fetchone()
    if not row:
        # 2. Case-insensitive name match
        cursor.execute("SELECT * FROM projects WHERE LOWER(name) LIKE ? ORDER BY created_at ASC", (f"%{query.lower()}%",))
        row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def main():
    parser = argparse.ArgumentParser(description="DevGuardian AI Project Runner")
    parser.add_argument("project", nargs="?", help="Project ID or Name (e.g. 'HireSmart AI', 'proj_bdf4bf9f8d')")
    parser.add_argument("--port", "-p", type=int, help="Override port assignment")
    parser.add_argument("--list", "-l", action="store_true", help="List all generated projects")

    args = parser.parse_args()

    if args.list or not args.project:
        list_projects()
        if not args.project:
            print("Specify a project to run: python run_project.py <project_name>")
            return

    proj = find_project(args.project)
    if not proj:
        print(f"Error: Project matching '{args.project}' not found in DevGuardian database.")
        list_projects()
        sys.exit(1)

    project_id = proj["id"]
    project_name = proj["name"]

    # 1. Resolve workspace
    workspace = get_project_workspace(project_id)
    if not workspace.exists():
        print(f"Error: Workspace directory does not exist: {workspace}")
        sys.exit(1)

    # 2. Allocate or reuse port
    target_port = args.port or proj.get("assigned_port") or PortManager.allocate_port(project_id, project_name=project_name)

    # 3. Detect or create entry point
    entry_info = detect_or_create_project_entry_point(
        project_dir=workspace,
        project_name=project_name,
        project_id=project_id,
        assigned_port=target_port
    )
    entry_file = entry_info["entry_file"]
    full_entry_path = workspace / entry_file

    if not full_entry_path.exists():
        print(f"Error: Entry point file missing: {full_entry_path}")
        sys.exit(1)

    # 4. Prepare execution environment
    env = os.environ.copy()
    env["PORT"] = str(target_port)
    env["PYTHONPATH"] = str(workspace)
    env["PYTHONUNBUFFERED"] = "1"

    print("\n==========================================================")
    print(f" DevGuardian AI — Running Independent Project")
    print(f" Name: {project_name}")
    print(f" ID: {project_id}")
    print(f" Workspace: {workspace}")
    print(f" Entry Point: {entry_file}")
    print(f" Assigned Port: {target_port}")
    print(f" Local URL: http://127.0.0.1:{target_port}")
    print("==========================================================\n")

    cmd = [sys.executable, entry_file]
    try:
        proc = subprocess.run(cmd, cwd=str(workspace), env=env)
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        print(f"\n[{project_name}] Process terminated by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
