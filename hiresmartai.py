"""
DevGuardian AI — HireSmart AI Root Dispatcher
Allows running HireSmart AI from the DevGuardian AI root directory:
    python hiresmartai.py

This automatically executes the project from its actual workspace:
    generated_projects/HireSmart_AI/hiresmartai.py
using its actual workspace directory as cwd and port 5001.
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
CANDIDATE_DIRS = [
    ROOT_DIR / "generated_projects" / "HireSmart_AI",
    ROOT_DIR / "generated_projects" / "HireSmartAI",
    ROOT_DIR / "generated_projects" / "proj_bdf4bf9f8d",
]

PROJECT_DIR = None
for c in CANDIDATE_DIRS:
    if c.exists() and (c / "hiresmartai.py").exists():
        PROJECT_DIR = c.resolve()
        break

if not PROJECT_DIR:
    # Query database for actual workspace path
    try:
        import sqlite3
        db_path = ROOT_DIR / "instance" / "devguardian.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT workspace_path FROM projects WHERE name LIKE '%HireSmart%' OR id = 'proj_bdf4bf9f8d'")
            row = cursor.fetchone()
            conn.close()
            if row and row[0] and Path(row[0]).exists():
                PROJECT_DIR = Path(row[0]).resolve()
    except Exception:
        pass

if not PROJECT_DIR or not (PROJECT_DIR / "hiresmartai.py").exists():
    print("Error: Could not locate HireSmart AI workspace or hiresmartai.py entry point.")
    sys.exit(1)

port = os.environ.get("PORT", "5001")
env = os.environ.copy()
env["PORT"] = str(port)
env["PYTHONPATH"] = str(PROJECT_DIR)
env["PYTHONUNBUFFERED"] = "1"

print("\n==========================================================")
print(" DevGuardian AI — Launching Independent Generated Project")
print(" Project: HireSmart AI")
print(f" Working Directory: {PROJECT_DIR}")
print(" Entry Point: hiresmartai.py")
print(f" Assigned Port: {port}")
print(f" Local URL: http://127.0.0.1:{port}")
print("==========================================================\n")

cmd = [sys.executable, "hiresmartai.py"] + sys.argv[1:]
try:
    proc = subprocess.run(cmd, cwd=str(PROJECT_DIR), env=env)
    sys.exit(proc.returncode)
except KeyboardInterrupt:
    print("\nHireSmart AI stopped.")
    sys.exit(0)
