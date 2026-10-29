"""
File Explorer Service — DevGuardian AI
Reads the real project filesystem, generates hierarchical collapsible directory trees,
provides secure source code inspection, metadata, editing, and download functionality.
"""

import os
import ast
import mimetypes
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from services.workspace_manager import get_project_workspace, ensure_safe_path
from db import get_standalone_db

IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", ".idea", ".vscode", "instance"}
IGNORED_EXTS = {".pyc", ".pyd", ".pyo"}

class FileExplorerService:
    @staticmethod
    def get_project_tree(project_id: str) -> Dict[str, Any]:
        """
        Build nested directory and file tree strictly from the project's actual filesystem.
        """
        workspace_dir = get_project_workspace(project_id)
        if not workspace_dir.exists():
            return {
                "name": workspace_dir.name,
                "path": "",
                "type": "directory",
                "children": [],
                "total_files": 0,
                "total_size": 0
            }

        def build_node(current_path: Path, rel_path: str = "") -> Dict[str, Any]:
            children = []
            try:
                entries = sorted(list(current_path.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
            except Exception:
                entries = []

            for entry in entries:
                if entry.name in IGNORED_DIRS or entry.suffix in IGNORED_EXTS:
                    continue

                child_rel = f"{rel_path}/{entry.name}".lstrip("/")
                if entry.is_dir():
                    child_node = build_node(entry, child_rel)
                    children.append(child_node)
                else:
                    try:
                        stat = entry.stat()
                        size = stat.st_size
                        mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        size = 0
                        mtime = "Unknown"

                    ext = entry.suffix.lstrip(".").lower()
                    children.append({
                        "name": entry.name,
                        "path": child_rel,
                        "type": "file",
                        "extension": ext or "txt",
                        "size": size,
                        "size_formatted": FileExplorerService.format_size(size),
                        "modified": mtime,
                        "is_generated": True
                    })

            return {
                "name": current_path.name,
                "path": rel_path,
                "type": "directory",
                "children": children
            }

        tree = build_node(workspace_dir, "")
        tree["root_path"] = str(workspace_dir)

        # Count total files and size
        file_count = 0
        total_size = 0
        def count_stats(node):
            nonlocal file_count, total_size
            if node["type"] == "file":
                file_count += 1
                total_size += node.get("size", 0)
            for ch in node.get("children", []):
                count_stats(ch)

        count_stats(tree)
        tree["total_files"] = file_count
        tree["total_size"] = total_size
        tree["total_size_formatted"] = FileExplorerService.format_size(total_size)
        return tree

    @staticmethod
    def get_file_details(project_id: str, relative_path: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        Safely fetch source code content, line count, syntax status, and metadata.
        """
        workspace_dir = get_project_workspace(project_id)
        clean_rel = os.path.normpath(relative_path).lstrip(r"\/")

        if ".." in clean_rel.split(os.sep) or clean_rel.startswith(("/", "\\")):
            return False, {}, "Security Alert: Path traversal detected!"

        target_file = (workspace_dir / clean_rel).resolve()
        try:
            target_file.relative_to(workspace_dir)
        except ValueError:
            return False, {}, "Security Alert: File escapes project workspace!"

        if not target_file.exists() or not target_file.is_file():
            return False, {}, f"File '{clean_rel}' not found in project workspace."

        try:
            content = target_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return False, {}, f"Failed to read file: {str(e)}"

        stat = target_file.stat()
        ext = target_file.suffix.lstrip(".").lower() or "txt"
        lines = content.splitlines()

        # AST syntax check for Python
        syntax_ok = True
        syntax_msg = "Syntax valid"
        if ext == "py":
            try:
                ast.parse(content)
            except SyntaxError as syn_err:
                syntax_ok = False
                syntax_msg = f"Syntax Error (line {syn_err.lineno}): {syn_err.msg}"

        mime, _ = mimetypes.guess_type(str(target_file))

        metadata = {
            "filename": target_file.name,
            "path": clean_rel,
            "extension": ext,
            "size": stat.st_size,
            "size_formatted": FileExplorerService.format_size(stat.st_size),
            "lines_count": len(lines),
            "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "content": content,
            "mime_type": mime or "text/plain",
            "syntax_ok": syntax_ok,
            "syntax_message": syntax_msg
        }

        return True, metadata, "Success"

    @staticmethod
    def save_file_content(project_id: str, relative_path: str, new_content: str) -> Tuple[bool, str]:
        """
        Safely update file content with AST verification for Python scripts.
        """
        workspace_dir = get_project_workspace(project_id)
        clean_rel = os.path.normpath(relative_path).lstrip(r"\/")

        if ".." in clean_rel.split(os.sep):
            return False, "Security Alert: Path traversal detected!"

        target_file = (workspace_dir / clean_rel).resolve()
        try:
            target_file.relative_to(workspace_dir)
        except ValueError:
            return False, "Security Alert: File escapes project workspace!"

        ext = target_file.suffix.lstrip(".").lower()
        if ext == "py":
            try:
                ast.parse(new_content)
            except SyntaxError as syn_err:
                return False, f"Validation Failed: Python Syntax Error on line {syn_err.lineno}: {syn_err.msg}"

        target_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            target_file.write_text(new_content, encoding="utf-8")
        except Exception as e:
            return False, f"Write error: {str(e)}"

        # Sync database project_files
        try:
            conn = get_standalone_db()
            with conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE project_files
                    SET file_content = ?, file_size = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE project_id = ? AND filename = ?
                """, (new_content, len(new_content.encode("utf-8")), project_id, clean_rel))
            conn.close()
        except Exception:
            pass

        return True, f"File '{clean_rel}' saved and verified successfully."

    @staticmethod
    def format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
