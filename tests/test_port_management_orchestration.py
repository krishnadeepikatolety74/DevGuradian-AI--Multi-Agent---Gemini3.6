"""
Test Suite: Port Management & Multi-Application Orchestration Verification
Verifies Tests A through L according to Master Prompt specification.
"""

import os
import sys
import time
import socket
import threading
import unittest
import requests
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from db import get_standalone_db
from services.port_manager import PortManager, is_port_in_use, is_port_bindable, is_port_available, check_http_health
from services import execution_service


class TestPortManagementOrchestration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()

        # Ensure default canonical ports are reconciled and seeded
        with app.app_context():
            PortManager.reconcile_and_seed_default_ports()

        # Retrieve user 19 projects
        cls.user_id = 19
        cls.overview = PortManager.get_system_servers_overview(user_id=cls.user_id)
        cls.projects = cls.overview["generated_projects"]
        cls.proj_map = {p["project_name"]: p for p in cls.projects}

    def tearDown(self):
        # Stop any active child processes started during test
        for p in self.projects:
            execution_service.stop_project_process(p["project_id"])

    # -------------------------------------------------------------
    # Test A: Unique port allocation
    # Verify that all 8 registered applications have unique assignments.
    # -------------------------------------------------------------
    def test_a_unique_port_allocation(self):
        expected_ports = {
            "DevGuardian AI — Main Platform": 5000,
            "HireSmart AI": 5001,
            "Smart Expense Tracker AI": 5002,
            "ClaimWise AI": 5003,
            "CultureLens": 5004,
            "Smart Crosswalk Safety System": 5005,
            "Healthcare Multi-Agent AI Workflow Automation": 5006,
            "TaskFlow AI": 5007
        }

        # Check main platform
        self.assertEqual(self.overview["main_app"]["port"], 5000)

        # Check child applications
        found_ports = [self.overview["main_app"]["port"]]
        for name, port in expected_ports.items():
            if name == "DevGuardian AI — Main Platform":
                continue
            self.assertIn(name, self.proj_map, f"Missing registered project: {name}")
            actual_port = self.proj_map[name]["assigned_port"]
            self.assertEqual(actual_port, port, f"Project {name} expected port {port}, got {actual_port}")
            found_ports.append(actual_port)

        # Verify all 8 ports are strictly unique
        self.assertEqual(len(found_ports), 8)
        self.assertEqual(len(set(found_ports)), 8, f"Found duplicate ports in allocation: {found_ports}")

    # -------------------------------------------------------------
    # Test B: Main platform stability
    # Verify that DevGuardian AI reserves port 5000 and never assigns 5000 to children.
    # -------------------------------------------------------------
    def test_b_main_platform_stability(self):
        self.assertEqual(PortManager.get_reserved_main_port(), 5000)
        # Attempting to check if 5000 is available for child apps must return False
        self.assertFalse(is_port_bindable(5000), "Port 5000 must never be bindable by child apps")
        self.assertFalse(is_port_available(5000), "Port 5000 must never be available for child allocation")

        # Allocating port with preferred 5000 must divert to >= 5001
        allocated = PortManager.allocate_port("test_proj_b", preferred_port=5000)
        self.assertNotEqual(allocated, 5000, "PortManager must never allocate port 5000 to a child project")
        self.assertGreaterEqual(allocated, 5001)

    # -------------------------------------------------------------
    # Test C: Individual startup
    # Start a child application and confirm that it uses its assigned port.
    # -------------------------------------------------------------
    def test_c_individual_startup(self):
        hire_smart = self.proj_map.get("HireSmart AI")
        self.assertIsNotNone(hire_smart)
        p_id = hire_smart["project_id"]

        result = execution_service.start_project_app(p_id)
        self.assertTrue(result.get("success"), f"Failed to start HireSmart AI: {result}")
        self.assertEqual(result.get("port"), 5001)
        self.assertEqual(result.get("status"), "Running")
        self.assertEqual(result.get("health_status"), "Healthy")

        # Verify HTTP response on assigned port
        resp = requests.get("http://127.0.0.1:5001/health", timeout=2.0)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertIn("HireSmart", data.get("app", ""))

        # Clean up
        execution_service.stop_project_process(p_id)

    # -------------------------------------------------------------
    # Test D: Multiple applications running simultaneously
    # Run at least two child applications simultaneously and verify both remain accessible.
    # -------------------------------------------------------------
    def test_d_multiple_applications(self):
        hire_smart = self.proj_map.get("HireSmart AI")
        expense = self.proj_map.get("Smart Expense Tracker AI")
        self.assertIsNotNone(hire_smart)
        self.assertIsNotNone(expense)

        res1 = execution_service.start_project_app(hire_smart["project_id"])
        self.assertTrue(res1.get("success"), f"Failed to start HireSmart AI: {res1}")

        res2 = execution_service.start_project_app(expense["project_id"])
        self.assertTrue(res2.get("success"), f"Failed to start Smart Expense Tracker AI: {res2}")

        # Verify both are running simultaneously on ports 5001 and 5002
        self.assertEqual(res1.get("port"), 5001)
        self.assertEqual(res2.get("port"), 5002)

        resp1 = requests.get("http://127.0.0.1:5001/health", timeout=2.0)
        resp2 = requests.get("http://127.0.0.1:5002/health", timeout=2.0)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)

        data1 = resp1.json()
        data2 = resp2.json()
        self.assertIn("HireSmart", data1.get("app", ""))
        self.assertIn("Expense", data2.get("app", ""))

        # Clean up both
        execution_service.stop_project_process(hire_smart["project_id"])
        execution_service.stop_project_process(expense["project_id"])

    # -------------------------------------------------------------
    # Test E: Duplicate Run action deduplication
    # Click Run twice for the same project and verify only one process is started.
    # -------------------------------------------------------------
    def test_e_duplicate_run_action(self):
        hire_smart = self.proj_map.get("HireSmart AI")
        p_id = hire_smart["project_id"]

        # First run
        res1 = execution_service.start_project_app(p_id)
        self.assertTrue(res1.get("success"))
        pid1 = res1.get("pid")

        # Second run attempt for already running application
        res2 = execution_service.start_project_app(p_id)
        self.assertTrue(res2.get("success"))
        pid2 = res2.get("pid")

        # Verify same PID (no duplicate spawned) and already_running flag
        self.assertEqual(pid1, pid2, "Duplicate process spawned on repeated Run action")
        self.assertTrue(res2.get("already_running"), "Expected already_running flag on duplicate Run action")

        execution_service.stop_project_process(p_id)

    # -------------------------------------------------------------
    # Test F: Port already occupied
    # Simulate an occupied port and verify that the application reports conflict or safely selects an alternative.
    # -------------------------------------------------------------
    def test_f_port_already_occupied(self):
        # Bind a mock socket to port 5009
        mock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mock_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mock_sock.bind(("127.0.0.1", 5009))
        mock_sock.listen(1)

        try:
            # Attempt to allocate port 5009
            allocated = PortManager.allocate_port("test_proj_occupied", preferred_port=5009)
            # Must safely avoid occupied port 5009
            self.assertNotEqual(allocated, 5009, "PortManager allocated an occupied port!")
            self.assertTrue(is_port_available(allocated), "Allocated port must be available")
        finally:
            mock_sock.close()

    # -------------------------------------------------------------
    # Test G: Invalid project directory
    # Verify that a missing directory produces a clear error rather than a silent failure.
    # -------------------------------------------------------------
    def test_g_invalid_project_directory(self):
        conn = get_standalone_db()
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO projects (id, user_id, name, description, workspace_path, assigned_port)
                VALUES ('proj_missing_dir_test', 19, 'Ghost Project', 'Test missing directory description', 'C:\\Nonexistent\\Directory\\Path', 5098)
            """)
        conn.close()

        events = list(execution_service.start_project_app_with_progress('proj_missing_dir_test'))
        failed_event = [e for e in events if e.get("stage") == "failed"]
        self.assertTrue(len(failed_event) > 0, "Missing directory did not trigger failure event")
        err_msg = failed_event[0].get("message", "")
        self.assertTrue("does not exist on disk" in err_msg or "not found" in err_msg.lower())

        # Cleanup DB record
        conn = get_standalone_db()
        with conn:
            conn.execute("DELETE FROM projects WHERE id = 'proj_missing_dir_test'")
        conn.close()

    # -------------------------------------------------------------
    # Test H: Dashboard restart state reconciliation
    # Restart reconciliation and verify project assignments persist and processes detected correctly.
    # -------------------------------------------------------------
    def test_h_dashboard_restart_reconciliation(self):
        # Start HireSmart
        hire_smart = self.proj_map.get("HireSmart AI")
        p_id = hire_smart["project_id"]
        res = execution_service.start_project_app(p_id)
        self.assertTrue(res.get("success"))

        # Simulate dashboard restart by re-running PortManager initialization
        reconcile_res = PortManager.reconcile_and_seed_default_ports()
        self.assertTrue(reconcile_res.get("success"))

        # Verify HireSmart is still running on port 5001
        status = execution_service.get_project_process_status(p_id)
        self.assertTrue(status.get("is_running"))
        self.assertEqual(status.get("port"), 5001)

        execution_service.stop_project_process(p_id)

    # -------------------------------------------------------------
    # Test I: Correct application routing
    # Open each application's displayed URL and confirm that the correct application responds.
    # -------------------------------------------------------------
    def test_i_correct_application_routing(self):
        # Start CultureLens (port 5004) and ClaimWise (port 5003)
        p_culture = self.proj_map.get("CultureLens")
        p_claim = self.proj_map.get("ClaimWise AI")
        self.assertIsNotNone(p_culture)
        self.assertIsNotNone(p_claim)

        execution_service.start_project_app(p_culture["project_id"])
        execution_service.start_project_app(p_claim["project_id"])

        # Health checks with expected_app verification
        h_ok1, _, msg1 = check_http_health("http://127.0.0.1:5004", expected_app="CultureLens")
        h_ok2, _, msg2 = check_http_health("http://127.0.0.1:5003", expected_app="ClaimWise AI")

        self.assertTrue(h_ok1, f"CultureLens routing error: {msg1}")
        self.assertTrue(h_ok2, f"ClaimWise routing error: {msg2}")

        # Cross-check: Probing port 5004 expecting ClaimWise must fail application verification
        cross_ok, _, cross_msg = check_http_health("http://127.0.0.1:5004", expected_app="ClaimWise AI")
        self.assertFalse(cross_ok, "Cross-routing should have detected mismatch between expected and actual app")

        execution_service.stop_project_process(p_culture["project_id"])
        execution_service.stop_project_process(p_claim["project_id"])

    # -------------------------------------------------------------
    # Test J: Stop and restart isolated to target child application
    # Stop a child application, verify that only that application stops, and then start it again.
    # -------------------------------------------------------------
    def test_j_stop_and_restart(self):
        p1 = self.proj_map.get("HireSmart AI")
        p2 = self.proj_map.get("Smart Expense Tracker AI")

        execution_service.start_project_app(p1["project_id"])
        execution_service.start_project_app(p2["project_id"])

        # Stop p1
        stop_res = execution_service.stop_project_process(p1["project_id"])
        self.assertTrue(stop_res.get("success"))

        # Verify p1 is stopped, but p2 is STILL running and healthy!
        p1_status = execution_service.get_project_process_status(p1["project_id"])
        p2_status = execution_service.get_project_process_status(p2["project_id"])
        self.assertFalse(p1_status.get("is_running"), "P1 should be stopped")
        self.assertTrue(p2_status.get("is_running"), "P2 should still be running!")

        # Restart p1
        start_res = execution_service.start_project_app(p1["project_id"])
        self.assertTrue(start_res.get("success"))
        self.assertTrue(execution_service.get_project_process_status(p1["project_id"]).get("is_running"))

        # Clean up
        execution_service.stop_project_process(p1["project_id"])
        execution_service.stop_project_process(p2["project_id"])

    # -------------------------------------------------------------
    # Test K: Log isolation between applications
    # Confirm that each application's Logs button displays only that application's logs.
    # -------------------------------------------------------------
    def test_k_log_isolation(self):
        p1 = self.proj_map.get("HireSmart AI")
        p2 = self.proj_map.get("TaskFlow AI")

        execution_service.start_project_app(p1["project_id"])
        execution_service.start_project_app(p2["project_id"])

        logs1 = execution_service.get_project_logs(p1["project_id"])
        logs2 = execution_service.get_project_logs(p2["project_id"])

        self.assertTrue(logs1.get("exists"))
        self.assertTrue(logs2.get("exists"))

        # Verify logs from p1 do not leak into p2
        self.assertNotIn(p1["project_id"], logs2.get("logs", ""))
        self.assertNotIn(p2["project_id"], logs1.get("logs", ""))

        execution_service.stop_project_process(p1["project_id"])
        execution_service.stop_project_process(p2["project_id"])

    # -------------------------------------------------------------
    # Test L: Concurrency / race condition safe port allocation
    # Trigger concurrent application start requests and verify no two receive the same port.
    # -------------------------------------------------------------
    def test_l_port_allocation_race_condition(self):
        allocated_ports = []
        errors = []

        def worker(idx):
            try:
                port = PortManager.allocate_port(f"proj_concurrent_{idx}", project_name=f"App {idx}")
                allocated_ports.append(port)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent allocation threw errors: {errors}")
        self.assertEqual(len(allocated_ports), 10)
        self.assertEqual(len(set(allocated_ports)), 10, f"Found duplicate ports in concurrent allocation: {allocated_ports}")

        # Cleanup DB
        conn = get_standalone_db()
        with conn:
            conn.execute("DELETE FROM projects WHERE id LIKE 'proj_concurrent_%'")
        conn.close()


if __name__ == "__main__":
    unittest.main()
