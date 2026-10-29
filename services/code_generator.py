import os
import ast
import zipfile
import io
from pathlib import Path
from typing import Dict, Any, List, Tuple
from db import get_standalone_db
from services.workspace_manager import (
    GENERATED_PROJECTS_DIR,
    get_project_workspace
)

WORKSPACE_ROOT = GENERATED_PROJECTS_DIR

def get_project_dir(project_id: str) -> Path:
    """Return verified workspace directory for the specific project via centralized workspace manager."""
    return get_project_workspace(project_id)

def validate_python_code(content: str, filename: str) -> Tuple[bool, str]:
    """Validate Python code using AST parser."""
    if not filename.endswith(".py"):
        return True, "Non-python file syntax check skipped"
    try:
        ast.parse(content)
        return True, "AST syntax check passed"
    except SyntaxError as e:
        return False, f"Syntax Error on line {e.lineno}: {e.msg}"

def save_project_files(project_id: str, files: Dict[str, str]) -> List[Dict[str, Any]]:
    """Save generated files to disk and sync into SQLite project_files table."""
    project_dir = get_project_dir(project_id)
    saved_records = []
    
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        for rel_path, content in files.items():
            # Path traversal prevention
            clean_rel_path = os.path.normpath(rel_path).lstrip(r"\/")
            if ".." in clean_rel_path.split(os.sep):
                continue
            
            file_path = project_dir / clean_rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            extension = file_path.suffix.lstrip(".").lower() or "txt"
            size = len(content.encode("utf-8"))
            
            cursor.execute("""
                SELECT id FROM project_files WHERE project_id = ? AND filename = ?
            """, (project_id, clean_rel_path))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE project_files 
                    SET file_content = ?, file_size = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (content, size, existing["id"]))
            else:
                cursor.execute("""
                    INSERT INTO project_files (project_id, filename, filepath, file_content, file_extension, file_size)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (project_id, clean_rel_path, str(file_path), content, extension, size))
                
            saved_records.append({
                "filename": clean_rel_path,
                "extension": extension,
                "size": size,
                "path": str(file_path)
            })
            
    conn.close()
    return saved_records

def get_project_files_from_db(project_id: str) -> List[Dict[str, Any]]:
    """Retrieve all files associated with a project from database."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, filename, filepath, file_content, file_extension, file_size, created_at, updated_at
        FROM project_files
        WHERE project_id = ?
        ORDER BY filename ASC
    """, (project_id,))
    rows = cursor.fetchall()
    files = [dict(row) for row in rows]
    conn.close()
    return files

def get_file_content(project_id: str, filename: str) -> Tuple[bool, str]:
    """Fetch content of a single project file."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT file_content FROM project_files WHERE project_id = ? AND filename = ?
    """, (project_id, filename))
    row = cursor.fetchone()
    conn.close()
    if row:
        return True, row["file_content"]
    return False, "File not found"

def create_project_zip(project_id: str, project_name: str) -> io.BytesIO:
    """Create in-memory ZIP bundle containing all generated files for the project."""
    files = get_project_files_from_db(project_id)
    safe_name = "".join([c if c.isalnum() or c in ('-', '_') else '_' for c in project_name])
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_info in files:
            zip_path = f"{safe_name}/{file_info['filename']}"
            zip_file.writestr(zip_path, file_info["file_content"])
            
    zip_buffer.seek(0)
    return zip_buffer
