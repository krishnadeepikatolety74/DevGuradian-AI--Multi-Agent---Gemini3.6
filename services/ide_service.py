import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from db import get_standalone_db
from services.code_generator import get_project_dir
from services.ide_adapters import (
    BaseIDEAdapter,
    VSCodeAdapter,
    AntigravityAdapter,
    KiroAdapter
)

ADAPTER_REGISTRY: Dict[str, BaseIDEAdapter] = {
    "vscode": VSCodeAdapter(),
    "antigravity": AntigravityAdapter(),
    "kiro": KiroAdapter(),
}

DEFAULT_IDE = "vscode"

def get_ide_adapter(ide_key: str) -> BaseIDEAdapter:
    """Retrieve adapter for specified IDE key."""
    key = (ide_key or DEFAULT_IDE).lower().strip()
    if key not in ADAPTER_REGISTRY:
        raise ValueError(f"Unsupported IDE '{ide_key}'. Supported environments: {', '.join(ADAPTER_REGISTRY.keys())}")
    return ADAPTER_REGISTRY[key]

def list_supported_ides(selected_ide: Optional[str] = None, custom_path_map: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """
    List all three supported IDE cards with real hardware detection status.
    Returns structured data for template rendering.
    """
    custom_map = custom_path_map or {}
    active_key = (selected_ide or DEFAULT_IDE).lower().strip()

    ide_cards = []
    # Order: Antigravity, Visual Studio Code, Kiro (as specified in Feature 2)
    ordered_keys = ["antigravity", "vscode", "kiro"]

    for key in ordered_keys:
        adapter = ADAPTER_REGISTRY[key]
        custom_path = custom_map.get(key)
        detection = adapter.detect(custom_path=custom_path)

        status = detection["status"]
        if detection["is_available"] and status in ("Installed", "Configured"):
            status = "Ready" if key == active_key else status

        ide_cards.append({
            "key": adapter.key,
            "name": adapter.name,
            "icon_svg": adapter.icon_svg,
            "description": adapter.description,
            "status": status,
            "is_available": detection["is_available"],
            "executable_path": detection.get("executable_path"),
            "message": detection.get("message", ""),
            "instructions": detection.get("instructions", ""),
            "is_selected": (key == active_key),
            "custom_path": custom_path or ""
        })

    return ide_cards

def get_project_ide_config(project_id: str) -> Dict[str, Any]:
    """Retrieve saved IDE selection and custom path from project record."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT selected_ide, ide_custom_path FROM projects WHERE id = ?
    """, (project_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "selected_ide": row["selected_ide"] or DEFAULT_IDE,
            "ide_custom_path": row["ide_custom_path"] or ""
        }
    return {
        "selected_ide": DEFAULT_IDE,
        "ide_custom_path": ""
    }

def save_project_ide_preference(project_id: str, selected_ide: str, custom_path: Optional[str] = None) -> Dict[str, Any]:
    """Validate and persist project IDE preference in SQLite."""
    clean_ide = (selected_ide or DEFAULT_IDE).lower().strip()
    if clean_ide not in ADAPTER_REGISTRY:
        raise ValueError(f"Invalid IDE key '{selected_ide}'.")

    adapter = ADAPTER_REGISTRY[clean_ide]
    clean_custom = (custom_path or "").strip()

    # Validate custom path if provided
    if clean_custom:
        valid, msg = adapter.validate_executable(clean_custom)
        if not valid:
            raise ValueError(f"Invalid custom executable: {msg}")

    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE projects
            SET selected_ide = ?, ide_custom_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (clean_ide, clean_custom if clean_custom else None, project_id))
    conn.close()

    return {
        "selected_ide": clean_ide,
        "ide_custom_path": clean_custom
    }

def launch_project_in_ide(project_id: str, ide_key: Optional[str] = None, custom_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Launch verified project workspace in the selected IDE.
    Security: Validates project workspace path traversal, only launches approved adapters.
    """
    # 1. Validate project directory path
    try:
        project_dir = get_project_dir(project_id)
    except ValueError as e:
        return {
            "success": False,
            "status": "Launch Failed",
            "message": f"Security violation: {str(e)}",
            "project_dir": "",
            "manual_instructions": ""
        }

    if not project_dir.exists():
        return {
            "success": False,
            "status": "Launch Failed",
            "message": f"Project workspace directory does not exist at: {project_dir}",
            "project_dir": str(project_dir),
            "manual_instructions": ""
        }

    # 2. Determine IDE to use
    saved_config = get_project_ide_config(project_id)
    effective_ide = (ide_key or saved_config["selected_ide"] or DEFAULT_IDE).lower().strip()
    effective_custom = custom_path if custom_path is not None else saved_config.get("ide_custom_path")

    if effective_ide not in ADAPTER_REGISTRY:
        return {
            "success": False,
            "status": "Launch Failed",
            "message": f"Unsupported IDE '{effective_ide}'.",
            "project_dir": str(project_dir),
            "manual_instructions": ""
        }

    adapter = get_ide_adapter(effective_ide)

    # 3. Detect and verify launcher before execution
    detection = adapter.detect(custom_path=effective_custom)
    is_available = detection.get("is_available") or (detection.get("status") in ("Installed", "Configured", "Ready") and bool(detection.get("executable_path")))
    if not is_available or not detection.get("executable_path"):
        det_status = detection.get("status", "Not Detected")
        det_msg = detection.get("message") or detection.get("details") or f"{adapter.name} is not detected on this machine."
        return {
            "success": False,
            "status": "Not Detected" if det_status == "Not Detected" else "Not Configured",
            "message": f"Cannot launch {adapter.name}: {det_msg}",
            "project_dir": str(project_dir.resolve()),
            "manual_instructions": adapter.get_manual_instructions(project_dir)
        }

    # 4. Launch using verified adapter
    success, launch_msg = adapter.launch(project_dir, custom_path=effective_custom)

    if success:
        return {
            "success": True,
            "status": "Ready",
            "message": launch_msg,
            "ide_name": adapter.name,
            "project_dir": str(project_dir.resolve()),
            "workspace_dir": str(project_dir.resolve()),
            "manual_instructions": adapter.get_manual_instructions(project_dir)
        }
    else:
        return {
            "success": False,
            "status": "Launch Failed",
            "message": launch_msg,
            "ide_name": adapter.name,
            "project_dir": str(project_dir.resolve()),
            "workspace_dir": str(project_dir.resolve()),
            "manual_instructions": adapter.get_manual_instructions(project_dir)
        }

def get_supported_ides() -> List[str]:
    """Return list of supported IDE keys."""
    return ["antigravity", "vscode", "kiro"]

def select_project_ide(project_id: str, ide_key: str) -> bool:
    """Save selected IDE for project."""
    try:
        save_project_ide_preference(project_id, ide_key)
        return True
    except Exception:
        return False

def configure_project_ide_path(project_id: str, custom_path: str) -> Dict[str, Any]:
    """Validate and configure custom executable path for project IDE."""
    cfg = get_project_ide_config(project_id)
    adapter = get_ide_adapter(cfg.get("selected_ide", DEFAULT_IDE))
    valid, msg = adapter.validate_executable(custom_path)
    if not valid:
        return {"success": False, "message": msg}
    try:
        save_project_ide_preference(project_id, cfg.get("selected_ide", DEFAULT_IDE), custom_path=custom_path)
        return {"success": True, "message": "Custom IDE path configured successfully."}
    except Exception as e:
        return {"success": False, "message": str(e)}

def launch_ide_for_project(project_id: str, ide_key: Optional[str] = None, custom_path: Optional[str] = None) -> Dict[str, Any]:
    """Launch project workspace in IDE with fallback manual instructions."""
    res = launch_project_in_ide(project_id, ide_key=ide_key, custom_path=custom_path)
    if "project_dir" in res and "workspace_dir" not in res:
        res["workspace_dir"] = res["project_dir"]
    return res

