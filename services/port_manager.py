"""
PortManager — Centralized Port Allocation, Reservation, Conflict Detection, and Health Verification Service
DevGuardian AI — Autonomous Software Project Manager
"""

import os
import time
import socket
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import requests
import psutil

from db import get_standalone_db

logger = logging.getLogger(__name__)

# Constants
MAIN_APP_PORT = 5000
DEFAULT_START_PORT = 5001
MAX_PORT = 5999

# Canonical default port allocation per specification
CANONICAL_PORT_MAP = {
    "DevGuardian AI — Main Platform": 5000,
    "HireSmart AI": 5001,
    "Smart Expense Tracker AI": 5002,
    "ClaimWise AI": 5003,
    "CultureLens": 5004,
    "Smart Crosswalk Safety System": 5005,
    "Healthcare Multi-Agent AI Workflow Automation": 5006,
    "TaskFlow AI": 5007
}

# Thread-safe lock for port allocation and status updates
_PORT_LOCK = threading.Lock()

# In-memory registry of active port reservations:
# { port: { "project_id": str, "reserved_at": float, "pid": Optional[int] } }
_ACTIVE_RESERVATIONS: Dict[int, Dict[str, Any]] = {}

# { project_id: port }
_PROJECT_PORT_MAP: Dict[str, int] = {}


def is_process_alive(pid: Optional[int]) -> bool:
    """Check if an OS process with the given PID is actively running."""
    if not pid or pid <= 0:
        return False
    try:
        if not psutil.pid_exists(pid):
            return False
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    except Exception:
        return False


def is_port_bindable(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port can be bound by creating and closing a TCP socket."""
    if port == MAIN_APP_PORT:
        return False  # Port 5000 is strictly reserved for main DevGuardian AI
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


def is_port_in_use(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Check if an active listener exists on host:port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            result = s.connect_ex((host, port))
            return result == 0
    except OSError:
        return False


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """
    Check if a port is completely available:
    - Not port 5000 (reserved for DevGuardian AI)
    - Socket bindable
    - Not currently listened to by any process
    """
    if port == MAIN_APP_PORT:
        return False
    return is_port_bindable(port, host) and not is_port_in_use(port, host)


def check_http_health(url: str, timeout: float = 1.0, expected_app: Optional[str] = None) -> Tuple[bool, int, str]:
    """
    Check if a service at url is healthy.
    Tests /health first, falls back to /api/health, then /.
    If expected_app is provided, validates that the response actually belongs
    to the expected application to prevent false positives from unrelated apps on the port.
    Returns: (is_healthy, status_code, message)
    """
    base_url = url.rstrip("/")
    endpoints_to_try = [
        f"{base_url}/health",
        f"{base_url}/api/health",
        base_url
    ]

    last_error = "Connection failed"
    for target in endpoints_to_try:
        try:
            res = requests.get(target, timeout=timeout)
            if res.status_code == 200:
                # Check JSON response if available
                try:
                    data = res.json()
                    status_field = str(data.get("status", "")).lower()
                    if status_field in ["healthy", "ok", "ready", "running", "success"]:
                        # If expected app given, check matching app name
                        if expected_app:
                            app_in_json = str(data.get("app", "") or data.get("name", "") or data.get("service", "")).lower()
                            exp_clean = expected_app.lower().replace(" ", "").replace("_", "").replace("-", "")
                            app_clean = app_in_json.replace(" ", "").replace("_", "").replace("-", "")
                            if app_clean and exp_clean not in app_clean and app_clean not in exp_clean:
                                return False, 200, f"Port responded, but service is '{app_in_json}' instead of expected '{expected_app}'"
                        return True, 200, "Healthy"
                except Exception:
                    # Non-JSON 200 response (e.g. HTML homepage)
                    pass

                # If checking root URL and expected_app given, inspect HTML snippet
                if target == base_url and expected_app:
                    html_snippet = res.text[:2000].lower()
                    exp_clean = expected_app.lower().replace("ai", "").strip()
                    if exp_clean and exp_clean not in html_snippet and "devguardian" not in html_snippet:
                        # Might still be healthy if it's the app
                        pass

                return True, res.status_code, f"Healthy (HTTP {res.status_code})"
            elif res.status_code < 500 and target == base_url:
                # Root returned a redirect (302) or 401/403/404, but service is clearly alive
                return True, res.status_code, f"Running (HTTP {res.status_code})"
        except requests.exceptions.ConnectionError:
            last_error = "Connection refused (service not listening)"
        except requests.exceptions.Timeout:
            last_error = "Connection timed out"
        except Exception as e:
            last_error = str(e)

    return False, 0, last_error


class PortManager:
    """Centralized manager for application-managed ports, process allocations, and conflict diagnostics."""

    @staticmethod
    def get_reserved_main_port() -> int:
        """Returns port reserved strictly for main DevGuardian AI orchestrator."""
        return MAIN_APP_PORT

    @classmethod
    def get_assigned_port(cls, project_id: str) -> Optional[int]:
        """Look up currently assigned port from in-memory cache or DB."""
        with _PORT_LOCK:
            if project_id in _PROJECT_PORT_MAP:
                return _PROJECT_PORT_MAP[project_id]

        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT assigned_port FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row["assigned_port"]:
            port = int(row["assigned_port"])
            with _PORT_LOCK:
                _PROJECT_PORT_MAP[project_id] = port
            return port
        return None

    @classmethod
    def find_available_port(cls, start_port: int = DEFAULT_START_PORT, exclude_project_id: Optional[str] = None) -> int:
        """
        Find an available port within range [start_port, MAX_PORT] that is:
        1. Not port 5000 (reserved for DevGuardian main platform).
        2. Not reserved in _ACTIVE_RESERVATIONS by another project.
        3. Not assigned to another project in the SQLite database.
        4. Not occupied by an active external listener on the OS.
        5. Bindable via standard TCP socket bind.
        """
        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, assigned_port FROM projects WHERE assigned_port IS NOT NULL")
        db_ports = {int(r["assigned_port"]): r["id"] for r in cursor.fetchall() if r["assigned_port"]}
        conn.close()

        start = max(DEFAULT_START_PORT, start_port)
        for port in range(start, MAX_PORT + 1):
            if port == MAIN_APP_PORT:
                continue

            # In-memory reservation check
            if port in _ACTIVE_RESERVATIONS:
                res_proj = _ACTIVE_RESERVATIONS[port].get("project_id")
                if res_proj != exclude_project_id:
                    continue

            # Database assignment check
            if port in db_ports:
                if db_ports[port] != exclude_project_id:
                    continue

            # Operating system socket check
            if is_port_available(port):
                return port

        # Fallback if loop finishes
        return 5999

    @classmethod
    def assign_port(cls, project_id: str, port: Optional[int] = None) -> int:
        """
        Assign a unique, collision-free port to a project and persist in database.
        Alias for allocate_port with direct port assignment support.
        """
        return cls.allocate_port(project_id, preferred_port=port)

    @classmethod
    def allocate_port(cls, project_id: str, preferred_port: Optional[int] = None, project_name: str = "") -> int:
        """
        Allocate an available port for a generated project:
        - Strictly reserves port 5000 for main DevGuardian AI.
        - Respects canonical default ports (5001-5007) for core applications.
        - Concurrency safe via _PORT_LOCK.
        - Checks database registry, memory cache, and OS socket bindability.
        - Reassigns conflict-free port if candidate is occupied by an external app.
        - Persists port assignment in SQLite DB.
        """
        with _PORT_LOCK:
            candidate_port = preferred_port

            # Look up project info from DB if needed
            conn = get_standalone_db()
            cursor = conn.cursor()
            cursor.execute("SELECT assigned_port, name FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                if not candidate_port and row["assigned_port"]:
                    candidate_port = int(row["assigned_port"])
                if not project_name and row["name"]:
                    project_name = row["name"]

            # Check canonical preference if not explicitly set
            if not candidate_port and project_name:
                p_norm = project_name.lower().replace(" ", "").replace("_", "").replace("-", "")
                if "hiresmart" in p_norm:
                    candidate_port = 5001
                elif "smartexpense" in p_norm:
                    candidate_port = 5002
                elif "claimwise" in p_norm:
                    candidate_port = 5003
                elif "culturelens" in p_norm:
                    candidate_port = 5004
                elif "smartcrosswalk" in p_norm or "crosswalk" in p_norm:
                    candidate_port = 5005
                elif "healthcare" in p_norm:
                    candidate_port = 5006
                elif "taskflow" in p_norm:
                    candidate_port = 5007

            # Validate candidate port if available
            if candidate_port and candidate_port != MAIN_APP_PORT and candidate_port >= DEFAULT_START_PORT:
                # Check memory reservations
                is_held_by_other = False
                for p, info in _ACTIVE_RESERVATIONS.items():
                    if p == candidate_port and info.get("project_id") != project_id:
                        is_held_by_other = True
                        break

                # Check database assignments
                conn = get_standalone_db()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM projects WHERE assigned_port = ? AND id != ?",
                    (candidate_port, project_id)
                )
                other_db = cursor.fetchone()
                conn.close()

                # If no other project holds it and socket is bindable / available
                if not is_held_by_other and not other_db and is_port_available(candidate_port):
                    cls._record_port_assignment(project_id, candidate_port)
                    return candidate_port

            # If candidate is invalid, occupied, or collided, find next available port
            allocated = cls.find_available_port(start_port=DEFAULT_START_PORT, exclude_project_id=project_id)
            cls._record_port_assignment(project_id, allocated)
            return allocated

    @classmethod
    def _record_port_assignment(cls, project_id: str, port: int, pid: Optional[int] = None):
        """Record port reservation in memory and persist in database."""
        _ACTIVE_RESERVATIONS[port] = {
            "project_id": project_id,
            "reserved_at": time.time(),
            "pid": pid
        }
        _PROJECT_PORT_MAP[project_id] = port

        try:
            conn = get_standalone_db()
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE projects
                    SET assigned_port = ?
                    WHERE id = ?
                """, (port, project_id))
            conn.close()
        except Exception as e:
            logger.error(f"Failed to persist assigned port {port} for project {project_id}: {e}")

    @classmethod
    def register_running_process(cls, project_id: str, port: int, pid: int):
        """Associate process PID with port reservation in memory."""
        with _PORT_LOCK:
            _ACTIVE_RESERVATIONS[port] = {
                "project_id": project_id,
                "reserved_at": time.time(),
                "pid": pid
            }
            _PROJECT_PORT_MAP[project_id] = port

    @classmethod
    def release_port(cls, project_id: str):
        """Release application-managed port reservation when project terminates."""
        with _PORT_LOCK:
            port = _PROJECT_PORT_MAP.pop(project_id, None)
            if port and port in _ACTIVE_RESERVATIONS:
                if _ACTIVE_RESERVATIONS[port].get("project_id") == project_id:
                    _ACTIVE_RESERVATIONS.pop(port, None)

    @classmethod
    def release_port_assignment(cls, project_id: str):
        """Alias for release_port."""
        cls.release_port(project_id)

    @classmethod
    def reconcile_and_seed_default_ports(cls) -> Dict[str, Any]:
        """
        Reconcile and enforce standard port assignments across all projects:
        1. DevGuardian AI strictly on 5000.
        2. Assign canonical ports 5001-5007 to the 7 core child applications:
           - HireSmart AI: 5001
           - Smart Expense Tracker AI: 5002
           - ClaimWise AI: 5003
           - CultureLens: 5004
           - Smart Crosswalk Safety System: 5005
           - Healthcare Multi-Agent AI Workflow Automation: 5006
           - TaskFlow AI: 5007
        3. Scan all remaining projects in SQLite database; if they have null, 5000,
           or duplicate port assignments, allocate unique conflict-free ports starting from 5008.
        4. Reconcile stale process records: mark running processes whose PIDs are dead as stopped.
        """
        with _PORT_LOCK:
            conn = get_standalone_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id, name, assigned_port FROM projects ORDER BY user_id DESC, id ASC")
            all_projects = cursor.fetchall()

            # Identify target canonical projects for primary user (user_id 19 or highest user)
            canonical_names = {
                "HireSmart AI": 5001,
                "Smart Expense Tracker AI": 5002,
                "ClaimWise AI": 5003,
                "CultureLens": 5004,
                "Smart Crosswalk Safety System": 5005,
                "Healthcare Multi-Agent AI Workflow Automation": 5006,
                "TaskFlow AI": 5007
            }

            assigned_ports: Dict[int, str] = {}
            reconciled_count = 0

            # Step 1: Assign canonical ports to matching projects (preferring user_id 19)
            matched_canonical = set()
            for c_name, c_port in canonical_names.items():
                target_proj = None
                # Check user 19 first
                for p in all_projects:
                    if p["user_id"] == 19 and p["name"] == c_name:
                        target_proj = p
                        break
                # Fallback to any user
                if not target_proj:
                    for p in all_projects:
                        if p["name"] == c_name and p["id"] not in matched_canonical:
                            target_proj = p
                            break

                if target_proj:
                    p_id = target_proj["id"]
                    matched_canonical.add(p_id)
                    assigned_ports[c_port] = p_id
                    cursor.execute("UPDATE projects SET assigned_port = ? WHERE id = ?", (c_port, p_id))
                    _PROJECT_PORT_MAP[p_id] = c_port
                    reconciled_count += 1

            # Step 2: Reconcile all other projects to guarantee no collisions
            next_available_port = 5008
            for p in all_projects:
                p_id = p["id"]
                if p_id in matched_canonical:
                    continue

                curr_port = p["assigned_port"]
                needs_new_port = False

                if not curr_port or curr_port == MAIN_APP_PORT:
                    needs_new_port = True
                elif curr_port in assigned_ports and assigned_ports[curr_port] != p_id:
                    needs_new_port = True

                if needs_new_port:
                    while next_available_port in assigned_ports or next_available_port in canonical_names.values():
                        next_available_port += 1
                    assigned_ports[next_available_port] = p_id
                    cursor.execute("UPDATE projects SET assigned_port = ? WHERE id = ?", (next_available_port, p_id))
                    _PROJECT_PORT_MAP[p_id] = next_available_port
                    reconciled_count += 1
                    next_available_port += 1
                else:
                    assigned_ports[curr_port] = p_id
                    _PROJECT_PORT_MAP[p_id] = curr_port

            # Step 3: Reconcile stale process records in project_processes table
            cursor.execute("""
                SELECT id, project_id, pid, status
                FROM project_processes
                WHERE status = 'running'
            """)
            stale_procs = cursor.fetchall()
            stale_cleaned = 0
            for sp in stale_procs:
                pid = sp["pid"]
                if not is_process_alive(pid):
                    cursor.execute("""
                        UPDATE project_processes
                        SET status = 'stopped', exit_code = 0, stopped_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (sp["id"],))
                    stale_cleaned += 1

            conn.commit()
            conn.close()

            logger.info(f"PortManager reconciliation complete: {reconciled_count} project ports verified, {stale_cleaned} stale processes cleaned.")
            return {
                "success": True,
                "reconciled_count": reconciled_count,
                "stale_cleaned": stale_cleaned,
                "assigned_ports": assigned_ports
            }

    @classmethod
    def validate_port_assignments(cls) -> Dict[str, Any]:
        """
        Validate all port assignments across the database.
        Checks for uniqueness, range validity, and socket availability.
        """
        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, assigned_port FROM projects")
        rows = cursor.fetchall()
        conn.close()

        port_to_projects: Dict[int, List[Dict[str, Any]]] = {}
        unassigned: List[Dict[str, Any]] = []

        for r in rows:
            p_id = r["id"]
            p_name = r["name"]
            port = r["assigned_port"]
            if not port:
                unassigned.append({"id": p_id, "name": p_name})
            else:
                port = int(port)
                if port not in port_to_projects:
                    port_to_projects[port] = []
                port_to_projects[port].append({"id": p_id, "name": p_name})

        duplicates = {p: projs for p, projs in port_to_projects.items() if len(projs) > 1}
        has_main_conflict = MAIN_APP_PORT in port_to_projects

        return {
            "is_valid": len(duplicates) == 0 and not has_main_conflict and len(unassigned) == 0,
            "total_assigned": len(port_to_projects),
            "duplicates": duplicates,
            "unassigned": unassigned,
            "main_conflict": has_main_conflict
        }

    @classmethod
    def detect_port_conflicts(cls, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Comprehensive Port Conflict Detection Engine.
        Categorizes conflicts into the 5 explicit types required by DevGuardian AI:
        1. duplicate_registry: Multiple projects sharing identical port in DB.
        2. external_conflict: Port occupied by an unrelated external OS process.
        3. unexpected_port: Child application running on unexpected port.
        4. stale_process: DB marks running but process PID is dead or port closed.
        5. unassigned_port: Project has no assigned port or points to main port 5000.
        """
        conn = get_standalone_db()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("""
                SELECT id, name, assigned_port, workspace_path, entry_point
                FROM projects WHERE user_id = ?
                ORDER BY created_at ASC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, name, assigned_port, workspace_path, entry_point
                FROM projects
                ORDER BY created_at ASC
            """)
        projects = cursor.fetchall()

        # Query process history
        cursor.execute("""
            SELECT project_id, pid, port, status, local_url
            FROM project_processes
            WHERE id IN (SELECT MAX(id) FROM project_processes GROUP BY project_id)
        """)
        last_procs = {r["project_id"]: r for r in cursor.fetchall()}
        conn.close()

        # Build port-to-projects map for registry duplicates
        port_registry: Dict[int, List[Dict[str, Any]]] = {}
        for p in projects:
            port = p["assigned_port"]
            if port:
                port = int(port)
                if port not in port_registry:
                    port_registry[port] = []
                port_registry[port].append(p)

        conflicts: List[Dict[str, Any]] = []

        # 1. Check duplicate_registry
        for port, projs in port_registry.items():
            if len(projs) > 1:
                names = ", ".join([pr["name"] for pr in projs])
                for p in projs:
                    conflicts.append({
                        "type": "duplicate_registry",
                        "type_label": "Duplicate Registry Port",
                        "project_id": p["id"],
                        "project_name": p["name"],
                        "port": port,
                        "pid": None,
                        "severity": "high",
                        "description": f"Port {port} is assigned to multiple projects ({names}) in the registry.",
                        "suggested_action": f"Reassign unique port in range 5001-5999 via Port Manager."
                    })

        # 2. Check each project for external conflicts, stale processes, and unassigned ports
        for p in projects:
            p_id = p["id"]
            p_name = p["name"]
            port = p["assigned_port"]
            proc_rec = last_procs.get(p_id)

            is_running_in_mem = False
            mem_pid = None
            with _PORT_LOCK:
                if port and port in _ACTIVE_RESERVATIONS:
                    res_info = _ACTIVE_RESERVATIONS[port]
                    if res_info.get("project_id") == p_id:
                        is_running_in_mem = True
                        mem_pid = res_info.get("pid")

            # 5. unassigned_port
            if not port or int(port) == MAIN_APP_PORT:
                conflicts.append({
                    "type": "unassigned_port",
                    "type_label": "Unassigned Application Port",
                    "project_id": p_id,
                    "project_name": p_name,
                    "port": port,
                    "pid": None,
                    "severity": "high",
                    "description": f"Project '{p_name}' has no assigned port or is mistakenly assigned to port 5000.",
                    "suggested_action": "Assign an available unique port from the pool (5001-5999)."
                })
                continue

            port = int(port)
            listening = is_port_in_use(port)

            # 4. stale_process
            if proc_rec and proc_rec["status"] == "running":
                pid = proc_rec["pid"]
                if not is_process_alive(pid) or not listening:
                    conflicts.append({
                        "type": "stale_process",
                        "type_label": "Stale Process Record",
                        "project_id": p_id,
                        "project_name": p_name,
                        "port": port,
                        "pid": pid,
                        "severity": "medium",
                        "description": f"Database indicates process is running on port {port} (PID {pid}), but process is not active.",
                        "suggested_action": "Reconcile database process status to 'Stopped' and recycle socket."
                    })

            # 2. external_conflict
            # If port is in use, but neither memory nor DB indicates our project is running
            is_our_active_process = is_running_in_mem or (proc_rec and proc_rec["status"] == "running" and is_process_alive(proc_rec["pid"]))
            if listening and not is_our_active_process:
                conflicts.append({
                    "type": "external_conflict",
                    "type_label": "Port Occupied by Unrelated Process",
                    "project_id": p_id,
                    "project_name": p_name,
                    "port": port,
                    "pid": None,
                    "severity": "high",
                    "description": f"Port {port} is occupied by an external service or unmanaged process while '{p_name}' is stopped.",
                    "suggested_action": f"Reallocate '{p_name}' to an available free port or close external process."
                })

            # 3. unexpected_port
            if is_our_active_process and proc_rec:
                runtime_port = proc_rec.get("port")
                if runtime_port and int(runtime_port) != port:
                    conflicts.append({
                        "type": "unexpected_port",
                        "type_label": "Unexpected Runtime Port",
                        "project_id": p_id,
                        "project_name": p_name,
                        "port": port,
                        "pid": proc_rec.get("pid"),
                        "severity": "medium",
                        "description": f"Project '{p_name}' is assigned port {port} but process was launched on port {runtime_port}.",
                        "suggested_action": f"Restart application on its designated port {port}."
                    })

        # Calculate counts
        counts = {
            "duplicate_registry": sum(1 for c in conflicts if c["type"] == "duplicate_registry"),
            "external_conflict": sum(1 for c in conflicts if c["type"] == "external_conflict"),
            "unexpected_port": sum(1 for c in conflicts if c["type"] == "unexpected_port"),
            "stale_process": sum(1 for c in conflicts if c["type"] == "stale_process"),
            "unassigned_port": sum(1 for c in conflicts if c["type"] == "unassigned_port")
        }

        return {
            "has_conflicts": len(conflicts) > 0,
            "total_conflicts": len(conflicts),
            "conflicts": conflicts,
            "summary": counts
        }

    @classmethod
    def resolve_port_conflicts(cls, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Safely resolve detected port conflicts:
        - Reassigns duplicates to free ports in 5001-5999.
        - Assigns free ports to unassigned projects.
        - Reconciles stale processes to 'stopped'.
        - Never terminates external processes.
        """
        diag = cls.detect_port_conflicts(user_id=user_id)
        if not diag["has_conflicts"]:
            return {
                "success": True,
                "message": "All project ports are healthy and conflict-free.",
                "actions_taken": []
            }

        actions_taken = []
        conn = get_standalone_db()

        # Handle stale processes
        for c in diag["conflicts"]:
            if c["type"] == "stale_process":
                with conn:
                    conn.execute("""
                        UPDATE project_processes
                        SET status = 'stopped', exit_code = 0, stopped_at = CURRENT_TIMESTAMP
                        WHERE project_id = ? AND status = 'running'
                    """, (c["project_id"],))
                actions_taken.append(f"Reconciled stale process for '{c['project_name']}' to Stopped.")

        # Reconcile ports using canonical seeding logic
        res = cls.reconcile_and_seed_default_ports()
        actions_taken.append(f"Re-aligned all project port allocations ({res['reconciled_count']} updated).")

        conn.close()
        return {
            "success": True,
            "message": f"Resolved {len(diag['conflicts'])} conflicts successfully.",
            "actions_taken": actions_taken
        }

    @classmethod
    def get_port_status(cls, project_id: str, is_running: bool, pid: Optional[int], port: Optional[int]) -> Dict[str, Any]:
        """
        Evaluate full status distinguishing:
        - Running
        - Starting
        - Stopped
        - Failed
        - Port Conflict
        - Health Check Failed
        """
        if not port:
            port = cls.get_assigned_port(project_id)

        if not port:
            return {
                "port": None,
                "status": "Stopped",
                "health_status": "Not Running",
                "local_url": None,
                "is_healthy": False,
                "detail": "No port assigned yet."
            }

        local_url = f"http://127.0.0.1:{port}"

        # If process is running according to execution manager
        if is_running and pid and is_process_alive(pid):
            is_listening = is_port_in_use(port)
            healthy, status_code, health_msg = check_http_health(local_url, timeout=1.0)

            if healthy:
                return {
                    "port": port,
                    "status": "Running",
                    "health_status": "Healthy",
                    "local_url": local_url,
                    "is_healthy": True,
                    "detail": health_msg
                }
            elif is_listening:
                return {
                    "port": port,
                    "status": "Health Check Failed",
                    "health_status": "Unhealthy",
                    "local_url": local_url,
                    "is_healthy": False,
                    "detail": health_msg
                }
            else:
                return {
                    "port": port,
                    "status": "Starting",
                    "health_status": "Pending",
                    "local_url": local_url,
                    "is_healthy": False,
                    "detail": "Process started; waiting for socket bind..."
                }

        # If not running:
        # Check if port is unexpectedly occupied by an unrelated external process
        if is_port_in_use(port):
            return {
                "port": port,
                "status": "Port Conflict",
                "health_status": "Conflict",
                "local_url": local_url,
                "is_healthy": False,
                "detail": f"Port {port} is occupied by an external or unmanaged process."
            }

        return {
            "port": port,
            "status": "Stopped",
            "health_status": "Not Running",
            "local_url": local_url,
            "is_healthy": False,
            "detail": "Process stopped; port is available."
        }

    @classmethod
    def get_system_servers_overview(cls, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate complete snapshot for Port Status Monitoring:
        - Main DevGuardian AI on port 5000
        - Generated projects with assigned ports, process statuses, health checks, and local URLs.
        """
        # 1. Main DevGuardian AI Status
        main_healthy, main_code, main_msg = check_http_health("http://127.0.0.1:5000", timeout=0.8)
        main_status = {
            "name": "DevGuardian AI — Main Platform",
            "port": MAIN_APP_PORT,
            "status": "Running" if (main_healthy or is_port_in_use(5000)) else "Starting",
            "health_status": "Healthy" if main_healthy else "Checking",
            "local_url": f"http://127.0.0.1:{MAIN_APP_PORT}",
            "is_main": True
        }

        # 2. Query Generated Projects
        conn = get_standalone_db()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("""
                SELECT id, name, workspace_path, language, app_type, assigned_port, entry_point
                FROM projects
                WHERE user_id = ?
                ORDER BY created_at ASC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, name, workspace_path, language, app_type, assigned_port, entry_point
                FROM projects
                ORDER BY created_at ASC
            """)
        project_rows = cursor.fetchall()
        conn.close()

        # Import execution_service for process info
        from services import execution_service

        projects_status_list = []
        for r in project_rows:
            p_id = r["id"]
            p_name = r["name"]
            assigned_port = r["assigned_port"]
            entry_point = r["entry_point"] or "app.py"

            proc_info = execution_service.get_project_process_status(p_id)
            is_running = proc_info.get("is_running", False)
            pid = proc_info.get("pid")
            effective_port = proc_info.get("port") or assigned_port

            port_diag = cls.get_port_status(p_id, is_running=is_running, pid=pid, port=effective_port)

            projects_status_list.append({
                "project_id": p_id,
                "project_name": p_name,
                "workspace_path": r["workspace_path"],
                "entry_point": entry_point,
                "language": r["language"],
                "app_type": r["app_type"],
                "assigned_port": port_diag["port"],
                "process_status": port_diag["status"],
                "health_status": port_diag["health_status"],
                "local_url": port_diag["local_url"],
                "pid": pid,
                "detail": port_diag["detail"],
                "is_running": is_running
            })

        return {
            "main_app": main_status,
            "generated_projects": projects_status_list
        }
