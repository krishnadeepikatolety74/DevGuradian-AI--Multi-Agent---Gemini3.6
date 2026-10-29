import os
import re
import uuid
import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from db import get_standalone_db

# Central configurable parent directory for all generated projects
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "generated_projects"
GENERATED_PROJECTS_DIR = Path(os.environ.get("GENERATED_PROJECTS_DIR") or _DEFAULT_ROOT).resolve()
GENERATED_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

def validate_project_name(name: str) -> Tuple[bool, str]:
    """Validate that the project name is secure, non-empty, and free of path traversal."""
    if not name or not isinstance(name, str):
        return False, "Project name is required."
    
    clean = name.strip()
    if len(clean) < 2:
        return False, "Project name must be at least 2 characters."
    if len(clean) > 100:
        return False, "Project name cannot exceed 100 characters."
    
    # Path traversal detection
    if ".." in clean or "/" in clean or "\\" in clean or "\x00" in clean:
        return False, "Security Alert: Invalid characters or directory traversal detected in project name."
    
    # Windows reserved filenames
    if clean.upper() in RESERVED_NAMES:
        return False, f"Project name '{clean}' is a reserved system name."
    
    return True, "Valid"

def sanitize_folder_name(name: str) -> str:
    """
    Convert a user-facing project name to a clean, filesystem-safe folder name.
    Example: 'HireSmart AI' -> 'HireSmart_AI'
             'Smart Expense Tracker AI' -> 'Smart_Expense_Tracker_AI'
    """
    if not name:
        return f"Project_{uuid.uuid4().hex[:6]}"
    
    # Replace non-alphanumeric characters (except hyphens and underscores) with underscores
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip())
    # Collapse consecutive underscores
    clean = re.sub(r"_+", "_", clean)
    # Strip leading/trailing underscores and hyphens
    clean = clean.strip("_-")
    
    if not clean or clean.upper() in RESERVED_NAMES:
        clean = f"Project_{uuid.uuid4().hex[:6]}"
        
    return clean

def generate_project_id() -> str:
    """Generate a unique, stable project ID."""
    return f"proj_{uuid.uuid4().hex[:10]}"

def ensure_safe_path(target_path: Path) -> Path:
    """
    Ensure the resolved path is strictly located within GENERATED_PROJECTS_DIR.
    Raises ValueError on directory traversal attempts.
    """
    resolved_target = target_path.resolve()
    resolved_root = GENERATED_PROJECTS_DIR.resolve()
    
    try:
        resolved_target.relative_to(resolved_root)
    except ValueError:
        raise ValueError(f"Security Alert: Directory traversal detected! Path '{resolved_target}' escapes '{resolved_root}'")
        
    return resolved_target

def allocate_project_workspace(project_id: str, project_name: str) -> Path:
    """
    Allocate and create a dedicated workspace directory for a new project
    under GENERATED_PROJECTS_DIR, and persist its path to the database.
    """
    is_valid, msg = validate_project_name(project_name)
    if not is_valid:
        raise ValueError(msg)
        
    folder_name = sanitize_folder_name(project_name)
    candidate_dir = GENERATED_PROJECTS_DIR / folder_name
    
    # If a folder with this name already exists, check if it belongs to this project
    if candidate_dir.exists():
        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM projects WHERE workspace_path = ? OR id = ?", (str(candidate_dir), project_id))
        row = cursor.fetchone()
        conn.close()
        
        # If folder belongs to a different project, use an unambiguous name with project_id
        if row and row["id"] != project_id:
            candidate_dir = GENERATED_PROJECTS_DIR / f"{folder_name}_{project_id}"
    
    safe_dir = ensure_safe_path(candidate_dir)
    safe_dir.mkdir(parents=True, exist_ok=True)
    
    # Ensure complete structure & entry point
    try:
        ensure_project_structure(safe_dir, project_name, project_id)
    except Exception:
        pass

    # Persist workspace path to projects table
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE projects SET workspace_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (str(safe_dir), project_id))
    conn.close()
    
    return safe_dir

def ensure_project_structure(
    project_dir: Path,
    project_name: str,
    project_id: Optional[str] = None,
    assigned_port: Optional[int] = None
) -> Dict[str, Any]:
    """
    Ensure every project has its own complete, isolated directory structure:
    - Dedicated Python entry-point file (<normalized_name>.py)
    - requirements.txt
    - .env.example with configuration placeholders
    - .env with local runtime defaults
    - README.md with standalone running instructions
    - instance/ folder for isolated SQLite database persistence
    - templates/ folder
    - static/ folder
    """
    project_dir = Path(project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    # 1. Essential subdirectories
    (project_dir / "instance").mkdir(parents=True, exist_ok=True)
    (project_dir / "templates").mkdir(parents=True, exist_ok=True)
    (project_dir / "static" / "css").mkdir(parents=True, exist_ok=True)
    (project_dir / "static" / "js").mkdir(parents=True, exist_ok=True)
    (project_dir / "static" / "images").mkdir(parents=True, exist_ok=True)
    (project_dir / "static" / "uploads").mkdir(parents=True, exist_ok=True)
    (project_dir / "tests").mkdir(parents=True, exist_ok=True)

    # Ensure python package directories or module files exist without shadowing
    for mod_name in ["models", "services", "database"]:
        root_py = project_dir / f"{mod_name}.py"
        mod_dir = project_dir / mod_name
        if root_py.exists():
            # If root module exists (e.g. models.py), do NOT shadow it with an empty folder
            if mod_dir.exists() and mod_dir.is_dir():
                items = [x.name for x in mod_dir.iterdir() if x.name != "__pycache__"]
                if items in [[], ["__init__.py"]]:
                    shutil.rmtree(mod_dir, ignore_errors=True)
        else:
            mod_dir.mkdir(parents=True, exist_ok=True)
            init_file = mod_dir / "__init__.py"
            if not init_file.exists():
                init_file.write_text(f'"""{project_name} - {mod_name} module package."""\n', encoding="utf-8")

    slug = re.sub(r"[^a-zA-Z0-9_]", "_", project_name.lower()).strip("_") or "app"

    # Determine assigned port
    if not assigned_port:
        from services.port_manager import PortManager
        assigned_port = PortManager.allocate_port(project_id or f"temp_{slug}", project_name=project_name)

    # 2. requirements.txt if not present
    req_file = project_dir / "requirements.txt"
    if not req_file.exists():
        req_content = "Flask>=3.0.0\nWerkzeug>=3.0.0\npytest>=8.0.0\npython-dotenv>=1.0.0\n"
        req_file.write_text(req_content, encoding="utf-8")

    # 3. .env.example if not present
    example_env = project_dir / ".env.example"
    if not example_env.exists():
        example_content = (
            f"# {project_name} Environment Configuration\n"
            f"PORT={assigned_port}\n"
            f"SECRET_KEY=replace-with-a-secure-secret-key\n"
            f"FLASK_ENV=development\n"
            f"DATABASE_URL=sqlite:///instance/{slug}.db\n"
        )
        example_env.write_text(example_content, encoding="utf-8")

    # 4. .env if not present
    env_file = project_dir / ".env"
    if not env_file.exists():
        import secrets
        safe_key = f"{slug}-secret-key-{secrets.token_hex(8)}"
        env_content = (
            f"# {project_name} Local Runtime Environment\n"
            f"PORT={assigned_port}\n"
            f"SECRET_KEY={safe_key}\n"
            f"FLASK_ENV=development\n"
            f"DATABASE_URL=sqlite:///instance/{slug}.db\n"
        )
        env_file.write_text(env_content, encoding="utf-8")

    # 5. .gitignore if not present
    gitignore_file = project_dir / ".gitignore"
    if not gitignore_file.exists():
        gitignore_content = "__pycache__/\n*.pyc\ninstance/\n*.db\n.env\nvenv/\n.pytest_cache/\n"
        gitignore_file.write_text(gitignore_content, encoding="utf-8")

    # 6. Dedicated mandatory app.py entry-point file
    from services.execution_service import (
        get_meaningful_entry_point_name,
        detect_or_create_project_entry_point
    )
    entry_filename = get_meaningful_entry_point_name(project_name)

    entry_info = detect_or_create_project_entry_point(
        project_dir=project_dir,
        project_name=project_name,
        project_id=project_id,
        assigned_port=assigned_port
    )

    # 7. README.md if not present or needs standard startup command
    readme_file = project_dir / "README.md"
    if not readme_file.exists():
        actual_entry = entry_info.get("entry_file", "app.py")
        readme_content = (
            f"# {project_name}\n\n"
            f"An independent software application generated and orchestrated by DevGuardian AI.\n\n"
            f"## Project Structure\n"
            f"- `app.py`: Mandatory Flask application entry point and route configuration.\n"
            f"- `config.py`: Central application configuration.\n"
            f"- `requirements.txt`: Python package requirements.\n"
            f"- `.env.example`: Environment variables template.\n"
            f"- `.gitignore`: Git ignore patterns.\n"
            f"- `instance/`: Isolated SQLite database storage.\n"
            f"- `templates/`: HTML user interface templates (`base.html`, `landing.html`, `login.html`, `signup.html`, `dashboard.html`).\n"
            f"- `static/`: Static stylesheets and assets (`static/css/style.css`, `static/js/`, `static/images/`, `static/uploads/`).\n"
            f"- `models/`: Domain data models.\n"
            f"- `services/`: Business logic and multi-agent services.\n"
            f"- `database/`: Database schema and persistence helpers.\n"
            f"- `tests/`: Automated unit and integration tests (`tests/test_app.py`).\n\n"
            f"## Running the Application Standalone\n"
            f"To run this project independently on port {assigned_port}:\n\n"
            f"```bash\n"
            f"cd generated_projects/{project_dir.name}\n"
            f"python app.py\n"
            f"```\n\n"
            f"Local Application URL:\n"
            f"http://127.0.0.1:{assigned_port}\n"
        )
        readme_file.write_text(readme_content, encoding="utf-8")

    return {
        "workspace_dir": str(project_dir),
        "entry_point": entry_info.get("entry_file", "app.py"),
        "assigned_port": assigned_port
    }

def get_project_workspace(project_id: str) -> Path:
    """
    Resolve verified workspace directory for a specific project.
    Always checks database record first, then filesystem fallbacks.
    Guarantees path traversal protection.
    """
    if not project_id or not isinstance(project_id, str):
        raise ValueError("Invalid project_id provided.")
        
    # Check for direct path traversal in project_id itself
    if ".." in project_id or "/" in project_id or "\\" in project_id:
        raise ValueError(f"Security Alert: Directory traversal detected for project {project_id}")
    
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, workspace_path FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        stored_path = row["workspace_path"]
        project_name = row["name"]
        
        # 1. Use stored workspace_path if valid
        if stored_path:
            p = Path(stored_path)
            try:
                safe_p = ensure_safe_path(p)
                if safe_p.exists():
                    return safe_p
            except ValueError:
                pass
                
        # 2. Check sanitized folder name
        if project_name:
            folder_name = sanitize_folder_name(project_name)
            named_p = GENERATED_PROJECTS_DIR / folder_name
            if named_p.exists():
                safe_p = ensure_safe_path(named_p)
                # Update DB for future fast lookup
                _update_stored_workspace_path(project_id, safe_p)
                return safe_p
            
            # Check folder_name_project_id
            suffixed_p = GENERATED_PROJECTS_DIR / f"{folder_name}_{project_id}"
            if suffixed_p.exists():
                safe_p = ensure_safe_path(suffixed_p)
                _update_stored_workspace_path(project_id, safe_p)
                return safe_p
                
    # 3. Check legacy project_id directory
    legacy_p = GENERATED_PROJECTS_DIR / project_id
    if legacy_p.exists():
        safe_p = ensure_safe_path(legacy_p)
        _update_stored_workspace_path(project_id, safe_p)
        return safe_p

    # 4. If directory doesn't exist yet, allocate according to project name or project_id
    if row and row["name"]:
        folder_name = sanitize_folder_name(row["name"])
        target_dir = GENERATED_PROJECTS_DIR / folder_name
    else:
        target_dir = GENERATED_PROJECTS_DIR / project_id
        
    safe_dir = ensure_safe_path(target_dir)
    safe_dir.mkdir(parents=True, exist_ok=True)
    _update_stored_workspace_path(project_id, safe_dir)
    return safe_dir

def _update_stored_workspace_path(project_id: str, path: Path):
    """Internal helper to sync workspace path in SQLite."""
    try:
        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE projects SET workspace_path = ? WHERE id = ?", (str(path.resolve()), project_id))
        conn.close()
    except Exception:
        pass

def organize_existing_projects() -> List[Dict[str, Any]]:
    """
    Organize existing projects in the database and filesystem.
    Ensures projects have clean, named directories under GENERATED_PROJECTS_DIR
    while preserving all files, preventing duplicates, and maintaining stable IDs.
    """
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, workspace_path FROM projects ORDER BY created_at ASC")
    projects = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    results = []
    
    for p in projects:
        project_id = p["id"]
        project_name = p["name"]
        stored_path = p.get("workspace_path")
        
        target_folder = sanitize_folder_name(project_name)
        target_dir = (GENERATED_PROJECTS_DIR / target_folder).resolve()
        
        # Locate current source directory on disk
        source_dir = None
        if stored_path and Path(stored_path).exists():
            source_dir = Path(stored_path).resolve()
        elif (GENERATED_PROJECTS_DIR / project_id).exists():
            source_dir = (GENERATED_PROJECTS_DIR / project_id).resolve()
        elif target_dir.exists():
            source_dir = target_dir
            
        action_taken = "unchanged"
        final_path = source_dir or target_dir
        
        # Check if already in destination
        if source_dir and source_dir == target_dir:
            _update_stored_workspace_path(project_id, target_dir)
            _sync_project_files_filepath(project_id, target_dir)
            action_taken = "already_correct"
            final_path = target_dir
        elif source_dir and source_dir.exists():
            # Source exists, but is in old location (e.g. proj_bdf4bf9f8d)
            if not target_dir.exists():
                try:
                    shutil.move(str(source_dir), str(target_dir))
                    _update_stored_workspace_path(project_id, target_dir)
                    _sync_project_files_filepath(project_id, target_dir)
                    action_taken = "moved"
                    final_path = target_dir
                except Exception:
                    try:
                        shutil.copytree(str(source_dir), str(target_dir), dirs_exist_ok=True)
                        _update_stored_workspace_path(project_id, target_dir)
                        _sync_project_files_filepath(project_id, target_dir)
                        action_taken = "copied_and_organized"
                        final_path = target_dir
                        try:
                            shutil.rmtree(str(source_dir), ignore_errors=True)
                        except Exception:
                            pass
                    except Exception as e:
                        _update_stored_workspace_path(project_id, source_dir)
                        action_taken = f"organize_failed: {str(e)}"
                        final_path = source_dir
            else:
                # Target already exists
                try:
                    shutil.copytree(str(source_dir), str(target_dir), dirs_exist_ok=True)
                except Exception:
                    pass
                _update_stored_workspace_path(project_id, target_dir)
                _sync_project_files_filepath(project_id, target_dir)
                action_taken = "organized_to_existing_target"
                final_path = target_dir
        else:
            # Directory doesn't exist on disk yet; create target_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            _update_stored_workspace_path(project_id, target_dir)
            action_taken = "created_target"
            final_path = target_dir
            
        results.append({
            "project_id": project_id,
            "project_name": project_name,
            "workspace_path": str(final_path),
            "action": action_taken
        })
        
    return results

def _sync_project_files_filepath(project_id: str, new_dir: Path):
    """Update filepath column in project_files table after workspace move."""
    try:
        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, filename FROM project_files WHERE project_id = ?", (project_id,))
            rows = cursor.fetchall()
            for row in rows:
                clean_rel = row["filename"].replace("\\", "/")
                new_abs = str((new_dir / clean_rel).resolve())
                cursor.execute("UPDATE project_files SET filepath = ? WHERE id = ?", (new_abs, row["id"]))
        conn.close()
    except Exception:
        pass
