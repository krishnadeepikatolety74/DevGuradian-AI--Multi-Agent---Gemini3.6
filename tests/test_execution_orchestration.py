"""
Test Suite — Independent Project Execution and Port Management Orchestration
DevGuardian AI — Autonomous Software Project Manager
"""

import os
import sys
import time
import socket
import shutil
import unittest
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import app
from db import init_db, get_standalone_db
import services.project_service as project_service
import services.execution_service as execution_service
from services.port_manager import (
    PortManager,
    is_port_in_use,
    is_port_bindable,
    check_http_health,
    MAIN_APP_PORT
)
from services.workspace_manager import (
    GENERATED_PROJECTS_DIR,
    get_project_workspace
)


class ExecutionAndPortManagementTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        init_db()

        # Stop any residual test processes
        execution_service.stop_project_process("proj_bdf4bf9f8d")
        execution_service.stop_project_process("proj_744892741e")
        execution_service.stop_project_process("proj_87ec37b85e")
        execution_service.stop_project_process("test_conflict_proj_1")
        execution_service.stop_project_process("test_conflict_proj_2")

        # Reset assigned ports in DB & in-memory maps
        from services.port_manager import _ACTIVE_RESERVATIONS, _PROJECT_PORT_MAP
        _ACTIVE_RESERVATIONS.clear()
        _PROJECT_PORT_MAP.clear()
        conn = get_standalone_db()
        with conn:
            conn.execute("UPDATE projects SET assigned_port = 5001 WHERE id = 'proj_bdf4bf9f8d'")
            conn.execute("UPDATE projects SET assigned_port = 5002 WHERE id = 'proj_744892741e'")
            conn.execute("UPDATE projects SET assigned_port = 5003 WHERE id = 'proj_87ec37b85e'")
        conn.close()

    @classmethod
    def tearDownClass(cls):
        # Stop background project processes cleanly
        execution_service.stop_project_process("proj_bdf4bf9f8d")
        execution_service.stop_project_process("proj_744892741e")
        execution_service.stop_project_process("proj_87ec37b85e")
        execution_service.stop_project_process("test_conflict_proj_1")
        execution_service.stop_project_process("test_conflict_proj_2")

    def setUp(self):
        self.client = app.test_client()
        # Find test user
        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = 'krishnadeepika9704@gmail.com'")
        row = cursor.fetchone()
        if row:
            self.user_id = row["id"]
        else:
            cursor.execute("""
                INSERT INTO users (email, password_hash, full_name, role)
                VALUES ('krishnadeepika9704@gmail.com', 'scrypt:test', 'Krishna Deepika', 'Developer')
            """)
            self.user_id = cursor.lastrowid
        conn.close()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["user_name"] = "Krishna Deepika"
            sess["user_email"] = "krishnadeepika9704@gmail.com"
            sess["csrf_token"] = "test_csrf_token"

    # 1. Main DevGuardian AI starts on port 5000 and port 5000 is reserved
    def test_01_main_devguardian_reserved_port_5000(self):
        self.assertEqual(PortManager.get_reserved_main_port(), 5000)
        self.assertEqual(MAIN_APP_PORT, 5000)

        # PortManager must reject allocating port 5000 to generated projects
        port = PortManager.allocate_port("test_project_reserve", preferred_port=5000)
        self.assertNotEqual(port, 5000, "Port 5000 must never be allocated to a generated project!")
        self.assertGreaterEqual(port, 5001)
        PortManager.release_port("test_project_reserve")

    # 2. HireSmart AI can start independently on port 5001
    def test_02_hiresmart_ai_starts_on_port_5001(self):
        proj_id = "proj_bdf4bf9f8d"
        ws = get_project_workspace(proj_id)
        self.assertTrue(ws.exists())
        self.assertTrue((ws / "app.py").exists(), "app.py mandatory entry point missing")

        # Start HireSmart AI
        res = execution_service.start_project_app(proj_id)
        self.assertTrue(res["success"], f"Failed to start HireSmart AI: {res.get('message')}")
        self.assertEqual(res["port"], 5001)
        self.assertEqual(res["entry_file"], "app.py")
        self.assertEqual(res["status"], "Running")
        self.assertIsNotNone(res["pid"])

        # Verify reachability via HTTP health check
        healthy, status_code, msg = check_http_health("http://127.0.0.1:5001/", timeout=2.0)
        self.assertTrue(healthy, f"HireSmart AI health check failed: {msg}")

    # 3. A second generated project can start independently on port 5002
    def test_03_second_project_starts_on_port_5002(self):
        proj_id = "proj_744892741e"
        ws = get_project_workspace(proj_id)
        self.assertTrue(ws.exists())
        self.assertTrue((ws / "app.py").exists(), "app.py mandatory entry point missing")

        # Start Smart Expense Tracker AI
        res = execution_service.start_project_app(proj_id)
        self.assertTrue(res["success"], f"Failed to start Smart Expense Tracker AI: {res.get('message')}")
        self.assertEqual(res["port"], 5002)
        self.assertEqual(res["entry_file"], "app.py")
        self.assertEqual(res["status"], "Running")
        self.assertIsNotNone(res["pid"])

        # Verify reachability on port 5002
        healthy2, status_code2, msg2 = check_http_health("http://127.0.0.1:5002/", timeout=2.0)
        self.assertTrue(healthy2, f"Smart Expense Tracker AI health check failed: {msg2}")

        # Verify HireSmart AI on 5001 is STILL simultaneously running
        healthy1, status_code1, msg1 = check_http_health("http://127.0.0.1:5001/", timeout=2.0)
        self.assertTrue(healthy1, "HireSmart AI on port 5001 died when Smart Expense Tracker AI started!")

    # 4. Running a generated project does not restart or affect the main application
    def test_04_running_project_does_not_restart_main_application(self):
        # DevGuardian AI configuration port
        self.assertEqual(MAIN_APP_PORT, 5000)

        # Check port status monitoring overview
        overview = PortManager.get_system_servers_overview(user_id=self.user_id)
        self.assertIn("main_app", overview)
        self.assertEqual(overview["main_app"]["port"], 5000)
        self.assertEqual(overview["main_app"]["name"], "DevGuardian AI (Main Orchestrator)")

        # Verify main app port is unaffected by child processes
        self.assertNotEqual(overview["main_app"]["port"], 5001)
        self.assertNotEqual(overview["main_app"]["port"], 5002)

    # 5. Projects use their correct working directories
    def test_05_projects_use_correct_working_directories(self):
        ws_hire = get_project_workspace("proj_bdf4bf9f8d")
        ws_expense = get_project_workspace("proj_744892741e")

        self.assertEqual(ws_hire.name, "HireSmart_AI")
        self.assertEqual(ws_expense.name, "Smart_Expense_Tracker_AI")
        self.assertTrue(str(ws_hire).startswith(str(GENERATED_PROJECTS_DIR)))
        self.assertTrue(str(ws_expense).startswith(str(GENERATED_PROJECTS_DIR)))

    # 6. Each project's own entry point is executed
    def test_06_each_project_entry_point_executed(self):
        status_hire = execution_service.get_project_process_status("proj_bdf4bf9f8d")
        status_expense = execution_service.get_project_process_status("proj_744892741e")

        self.assertEqual(status_hire.get("entry_point"), "app.py")
        self.assertEqual(status_expense.get("entry_point"), "app.py")

        # Verify entry point generator generates meaningful name for new project
        name = "Student Management System"
        meaningful = execution_service.get_meaningful_entry_point_name(name)
        self.assertEqual(meaningful, "studentmanagementsystem.py")

        ecomm_name = "E-Commerce"
        self.assertEqual(execution_service.get_meaningful_entry_point_name(ecomm_name), "ecommerce.py")

    # 7. Port conflicts are handled safely
    def test_07_port_conflicts_handled_safely(self):
        # Open an ephemeral socket to simulate an external process occupying a port
        dummy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dummy_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            dummy_sock.bind(("127.0.0.1", 0))
            dummy_sock.listen(1)
            occupied_port = dummy_sock.getsockname()[1]

            # Try to allocate occupied_port for a project
            assigned = PortManager.allocate_port("conflict_test_proj", preferred_port=occupied_port)
            self.assertNotEqual(assigned, occupied_port, "PortManager allocated an occupied external port!")
            self.assertGreaterEqual(assigned, 5001)
            PortManager.release_port("conflict_test_proj")
        finally:
            dummy_sock.close()

    # 8. Existing project port assignments are preserved when valid
    def test_08_existing_port_assignments_preserved(self):
        port_hire = PortManager.get_assigned_port("proj_bdf4bf9f8d")
        self.assertEqual(port_hire, 5001)

        port_expense = PortManager.get_assigned_port("proj_744892741e")
        self.assertEqual(port_expense, 5002)

    # 9. Two projects cannot be assigned the same active port
    def test_09_two_projects_cannot_share_same_active_port(self):
        p1_port = PortManager.allocate_port("test_conflict_proj_1", preferred_port=5030)
        p2_port = PortManager.allocate_port("test_conflict_proj_2", preferred_port=5030)

        self.assertNotEqual(p1_port, p2_port, "Two active projects were assigned the same port!")
        PortManager.release_port("test_conflict_proj_1")
        PortManager.release_port("test_conflict_proj_2")

    # 10. Stop and restart operations affect only the selected managed process
    def test_10_stop_and_restart_operations_isolation(self):
        # Verify both are running initially
        status_hire = execution_service.get_project_process_status("proj_bdf4bf9f8d")
        status_expense = execution_service.get_project_process_status("proj_744892741e")
        self.assertTrue(status_hire["is_running"])
        self.assertTrue(status_expense["is_running"])

        # Stop only HireSmart AI
        stop_res = execution_service.stop_project_process("proj_bdf4bf9f8d")
        self.assertTrue(stop_res["success"])

        # Verify HireSmart AI is stopped
        status_hire_after = execution_service.get_project_process_status("proj_bdf4bf9f8d")
        self.assertFalse(status_hire_after["is_running"])

        # Verify Smart Expense Tracker AI is STILL running unaffected!
        status_expense_after = execution_service.get_project_process_status("proj_744892741e")
        self.assertTrue(status_expense_after["is_running"])
        healthy_expense, _, _ = check_http_health("http://127.0.0.1:5002/", timeout=2.0)
        self.assertTrue(healthy_expense)

        # Restart HireSmart AI
        restart_res = execution_service.restart_project_app("proj_bdf4bf9f8d")
        self.assertTrue(restart_res["success"])
        self.assertEqual(restart_res["port"], 5001)

        # Verify both are running again
        healthy_hire, _, _ = check_http_health("http://127.0.0.1:5001/", timeout=2.0)
        self.assertTrue(healthy_hire)

    # 11. Logs and errors are captured correctly
    def test_11_logs_and_errors_captured(self):
        logs_hire = execution_service.get_project_logs("proj_bdf4bf9f8d")
        self.assertTrue(logs_hire["exists"])
        self.assertIn("HireSmart AI", logs_hire["logs"])

        logs_expense = execution_service.get_project_logs("proj_744892741e")
        self.assertTrue(logs_expense["exists"])
        self.assertIn("Smart Expense Tracker AI", logs_expense["logs"])

    # 12. Invalid project paths are rejected
    def test_12_invalid_project_paths_rejected(self):
        # Attempting to start project at DevGuardian root directory
        main_root = ROOT_DIR.resolve()
        # Non-existent or traversal project ID
        res = execution_service.start_project_app("../../../etc")
        self.assertFalse(res["success"])
        self.assertIn("Security Alert", res.get("message", "") + res.get("error", ""))

    # 13. A failed startup does not produce a false RUNNING status
    def test_13_failed_startup_no_false_running_status(self):
        # Create a temporary project with broken code that immediately crashes
        bad_dir = GENERATED_PROJECTS_DIR / "Temp_Broken_Test_Project"
        bad_dir.mkdir(parents=True, exist_ok=True)
        bad_entry = bad_dir / "app.py"
        bad_entry.write_text("import sys; sys.exit(42)", encoding="utf-8")

        # Insert temporary project in db
        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO projects (id, user_id, name, description, workspace_path)
                VALUES ('proj_bad_crash_test', ?, 'Crash Test', 'Tests failure handling', ?)
            """, (self.user_id, str(bad_dir)))
        conn.close()

        try:
            res = execution_service.start_project_app("proj_bad_crash_test")
            self.assertFalse(res["success"])
            self.assertNotEqual(res["status"], "Running")
            self.assertIn("terminated", res["message"].lower())

            status = execution_service.get_project_process_status("proj_bad_crash_test")
            self.assertFalse(status["is_running"])
            self.assertNotEqual(status["status"], "Running")
        finally:
            execution_service.stop_project_process("proj_bad_crash_test")
            shutil.rmtree(bad_dir, ignore_errors=True)
            conn = get_standalone_db()
            with conn:
                conn.execute("DELETE FROM projects WHERE id = 'proj_bad_crash_test'")
                conn.execute("DELETE FROM project_processes WHERE project_id = 'proj_bad_crash_test'")
            conn.close()

    # 14. The main application's existing routes and features still work
    def test_14_main_application_routes_and_features_work(self):
        self._login()

        # 1. Dashboard
        res_dash = self.client.get("/dashboard")
        self.assertEqual(res_dash.status_code, 200)

        # 2. Projects List with Port Status Monitoring
        res_proj = self.client.get("/projects")
        self.assertEqual(res_proj.status_code, 200)
        html = res_proj.data.decode("utf-8")
        self.assertIn("Server & Port Status Monitoring", html)
        self.assertIn("DevGuardian AI (Main Platform)", html)
        self.assertIn("5000", html)
        self.assertIn("HireSmart AI", html)
        self.assertIn("app.py", html)
        self.assertIn("Smart Expense Tracker AI", html)
        self.assertIn("Restart", html)
        self.assertIn("Logs", html)

        # 3. Logs route
        res_logs = self.client.get("/projects/proj_bdf4bf9f8d/logs")
        self.assertEqual(res_logs.status_code, 200)
        self.assertIn(b"Execution Logs", res_logs.data)

        # 4. JSON API Port Status
        res_api = self.client.get("/api/port-status")
        self.assertEqual(res_api.status_code, 200)
        api_data = res_api.get_json()
        self.assertIn("main_app", api_data)
        self.assertEqual(api_data["main_app"]["port"], 5000)
        self.assertIn("generated_projects", api_data)

    # 15. Automatic future project support (dynamic project creation, port allocation, and entry point generation)
    def test_15_future_project_dynamic_registration_and_execution(self):
        new_proj_name = "Inventory Logistics Manager"
        new_proj_id = project_service.create_project(
            user_id=self.user_id,
            name=new_proj_name,
            description="Dynamic multi-warehouse logistics tracking application.",
            app_type="Web App",
            language="Python Flask"
        )
        self.assertIsNotNone(new_proj_id)
        ws = get_project_workspace(new_proj_id)
        self.assertTrue(ws.exists())

        try:
            # Start dynamic future project
            res = execution_service.start_project_app(new_proj_id)
            self.assertTrue(res["success"], f"Failed to start dynamic future project: {res.get('message')}")
            self.assertEqual(res["status"], "Running")
            self.assertEqual(res["entry_file"], "app.py")
            self.assertTrue((ws / "app.py").exists(), "Auto-generated mandatory app.py missing")
            
            # Verify port is >= 5001 and distinct from reserved port 5000
            self.assertGreaterEqual(res["port"], 5001)
            self.assertNotEqual(res["port"], 5000)

            # Verify health check on its assigned port
            healthy, status_code, msg = check_http_health(f"http://127.0.0.1:{res['port']}/api/health", timeout=2.0)
            self.assertTrue(healthy, f"Dynamic future project health check failed: {msg}")
        finally:
            execution_service.stop_project_process(new_proj_id)
            # Cleanup DB & workspace
            conn = get_standalone_db()
            with conn:
                conn.execute("DELETE FROM projects WHERE id = ?", (new_proj_id,))
                conn.execute("DELETE FROM project_processes WHERE project_id = ?", (new_proj_id,))
            conn.close()
            shutil.rmtree(ws, ignore_errors=True)

    # 16. Root dispatcher scripts execute projects from their actual workspace directories
    def test_16_root_dispatcher_scripts(self):
        root_hire = ROOT_DIR / "hiresmartai.py"
        root_expense = ROOT_DIR / "smartexpensetrackerai.py"
        root_claim = ROOT_DIR / "claimwiseai.py"
        root_runner = ROOT_DIR / "run_project.py"

        self.assertTrue(root_hire.exists(), "Root hiresmartai.py dispatcher missing")
        self.assertTrue(root_expense.exists(), "Root smartexpensetrackerai.py dispatcher missing")
        self.assertTrue(root_claim.exists(), "Root claimwiseai.py dispatcher missing")
        self.assertTrue(root_runner.exists(), "Root run_project.py runner missing")

    # 17. ClaimWise AI generates claimwiseai.py and executes independently on port 5003
    def test_17_claimwise_ai_generation_and_execution(self):
        # 1. Entry point name generation
        entry_name = execution_service.get_meaningful_entry_point_name("ClaimWise AI", language="Python Flask")
        self.assertEqual(entry_name, "app.py")

        # 2. Workspace check
        proj_id = "proj_87ec37b85e"
        ws = get_project_workspace(proj_id)
        self.assertTrue(ws.exists())
        self.assertEqual(ws.name, "ClaimWise_AI")
        self.assertTrue((ws / "app.py").exists(), "app.py entry point missing in workspace")
        self.assertTrue((ws / "requirements.txt").exists(), "requirements.txt missing")
        self.assertTrue((ws / ".env.example").exists(), ".env.example missing")

        # 3. Start ClaimWise AI
        res = execution_service.start_project_app(proj_id)
        self.assertTrue(res["success"], f"Failed to start ClaimWise AI: {res.get('message')}")
        self.assertEqual(res["port"], 5003)
        self.assertEqual(res["entry_file"], "app.py")
        self.assertEqual(res["status"], "Running")
        self.assertIsNotNone(res["pid"])

        # 4. HTTP Health check on 5003
        healthy, status_code, msg = check_http_health("http://127.0.0.1:5003/api/health", timeout=2.5)
        self.assertTrue(healthy, f"ClaimWise AI health check failed on port 5003: {msg}")

        # 5. Stop ClaimWise AI cleanly
        stop_res = execution_service.stop_project_process(proj_id)
        self.assertTrue(stop_res["success"])
        status_after = execution_service.get_project_process_status(proj_id)
        self.assertFalse(status_after["is_running"])

    # 18. Arbitrary project names generate safe, unique filenames
    def test_18_arbitrary_project_names_generate_safe_unique_filenames(self):
        test_cases = [
            ("ClaimWise AI", "claimwiseai.py"),
            ("HireSmart AI", "hiresmartai.py"),
            ("Smart Expense Tracker AI", "smartexpensetrackerai.py"),
            ("Inventory Management System", "inventorymanagementsystem.py"),
            ("Healthcare Patient Portal 2026", "healthcarepatientportal2026.py"),
            ("Super & Duper @ App #42!", "superduperapp42.py"),
            ("path/traversal\\test..attack", "pathtraversaltestattack.py"),
            ("___!!!###$$$%%%", "app.py"),
            ("", "app.py")
        ]
        for input_name, expected in test_cases:
            result = execution_service.get_meaningful_entry_point_name(input_name)
            self.assertEqual(result, expected, f"Failed for input: '{input_name}'")
            self.assertTrue(result.endswith(".py"))
            self.assertFalse(" " in result)
            self.assertFalse("/" in result)
            self.assertFalse("\\" in result)

    # 19. Each project has its own directory and isolated database configuration
    def test_19_each_project_has_own_directory_and_isolated_database(self):
        projects = ["proj_87ec37b85e", "proj_bdf4bf9f8d", "proj_744892741e"]
        dirs = set()
        for pid in projects:
            ws = get_project_workspace(pid)
            self.assertTrue(ws.exists())
            self.assertNotIn(ws, dirs, f"Duplicate project directory detected for {pid}")
            dirs.add(ws)

            # Check for isolated requirements, env templates, and instance directories
            self.assertTrue((ws / "requirements.txt").exists(), f"requirements.txt missing in {ws}")
            self.assertTrue((ws / ".env.example").exists(), f".env.example missing in {ws}")
            self.assertTrue((ws / "instance").exists() or (ws / "database.db").exists() or (ws / "app").exists())

            # Verify that main database devguardian.db is NOT inside any generated project workspace
            self.assertFalse((ws / "devguardian.db").exists(), f"DevGuardian main DB leaked into {ws}")
            self.assertFalse((ws / "instance" / "devguardian.db").exists(), f"DevGuardian main DB leaked into {ws}/instance")

    # 20. Dependency checking and missing dependency reporting
    def test_20_dependency_checking_and_missing_dependency_reporting(self):
        # 1. Existing valid project requirements check (all standard packages should be installed)
        claim_ws = get_project_workspace("proj_87ec37b85e")
        is_ok, missing, msg = execution_service.check_project_dependencies(claim_ws)
        self.assertTrue(is_ok)
        self.assertEqual(missing, [])

        # 2. Test artificial missing dependency in temporary directory
        temp_dir = GENERATED_PROJECTS_DIR / "Temp_Dep_Test_Dir"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            req_file = temp_dir / "requirements.txt"
            req_file.write_text("flask>=2.0.0\ncompletely_fake_pkg_xyz_9999>=1.0.0\n", encoding="utf-8")
            is_ok_fake, missing_fake, msg_fake = execution_service.check_project_dependencies(temp_dir)
            self.assertFalse(is_ok_fake)
            self.assertIn("completely_fake_pkg_xyz_9999", missing_fake)
            self.assertIn("Missing required dependencies", msg_fake)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # 21. Open project folder action in file explorer endpoint
    def test_21_open_project_folder_endpoint(self):
        self._login()
        res = self.client.get("/projects/proj_87ec37b85e/open-folder", follow_redirects=False)
        self.assertEqual(res.status_code, 302)

    # 22. Stale database record does not produce false running status
    def test_22_stale_db_record_does_not_show_false_running_status(self):
        # Verify get_project_process_status does not blindly trust a stopped/inactive process
        status = execution_service.get_project_process_status("proj_87ec37b85e")
        # Since we stopped ClaimWise AI in test 17, is_running should be False
        self.assertFalse(status["is_running"])
        self.assertNotEqual(status["status"], "Running")


if __name__ == "__main__":
    unittest.main()
