"""
Test Suite — Project Startup Connection Error Fix & Response Standardization
DevGuardian AI — Autonomous Software Project Manager
"""

import os
import sys
import json
import shutil
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import app
from db import init_db, get_standalone_db
import services.execution_service as execution_service
from services.port_manager import PortManager
from services.workspace_manager import GENERATED_PROJECTS_DIR


class ProjectStartupFixTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        init_db()

        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = 'startup_fix_tester@devguardian.local'")
            row = cursor.fetchone()
            if row:
                cls.user_id = row['id']
            else:
                cursor.execute("""
                    INSERT INTO users (full_name, email, password_hash, role)
                    VALUES ('Startup Fix Tester', 'startup_fix_tester@devguardian.local', 'hash123', 'Developer')
                """)
                cls.user_id = cursor.lastrowid
        conn.close()

        cls.project_id = 'test_startup_fix_proj'
        cls.project_dir = GENERATED_PROJECTS_DIR / cls.project_id
        if cls.project_dir.exists():
            shutil.rmtree(cls.project_dir, ignore_errors=True)
        cls.project_dir.mkdir(parents=True, exist_ok=True)

        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM projects WHERE id = ?', (cls.project_id,))
            cursor.execute("""
                INSERT INTO projects (id, user_id, name, description, status, language)
                VALUES (?, ?, 'Startup Fix App', 'A test app for startup connection fix', 'in_progress', 'Python Flask')
            """, (cls.project_id, cls.user_id))
        conn.close()

        app_py_code = """import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>Startup Fix App Home</h1>'

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'ready': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5065))
    app.run(host='127.0.0.1', port=port, debug=False)
"""
        (cls.project_dir / 'app.py').write_text(app_py_code, encoding='utf-8')
        (cls.project_dir / 'requirements.txt').write_text("flask\n", encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        try:
            execution_service.stop_project_process(cls.project_id)
        except Exception:
            pass
        if cls.project_dir.exists():
            shutil.rmtree(cls.project_dir, ignore_errors=True)
        conn = get_standalone_db()
        with conn:
            conn.execute('DELETE FROM projects WHERE id = ?', (cls.project_id,))
            conn.execute('DELETE FROM users WHERE id = ?', (cls.user_id,))
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['user_email'] = 'startup_fix_tester@devguardian.local'
            sess['user_name'] = 'Startup Fix Tester'

    def tearDown(self):
        try:
            execution_service.stop_project_process(self.project_id)
        except Exception:
            pass

    def test_1_valid_startup_returns_structured_json(self):
        """Verifies valid startup request returns standardized JSON with success: true."""
        resp = self.client.post(
            f"/projects/{self.project_id}/run-project",
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.is_json, "Response Content-Type must be application/json")
        data = resp.get_json()

        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("status"), "running")
        self.assertEqual(data.get("project_id"), self.project_id)
        self.assertEqual(data.get("project_name"), "Startup Fix App")
        self.assertIn("message", data)
        self.assertTrue(data.get("local_url", "").startswith("http://127.0.0.1:"))
        self.assertIsNotNone(data.get("port"))
        self.assertNotEqual(data.get("port"), 5000, "Assigned port must not conflict with main app port 5000")

    def test_2_startup_failure_returns_structured_json(self):
        """Verifies startup failure returns structured JSON with success: false and error object."""
        # Create a failing project with missing entry point
        fail_proj_id = "test_fail_startup_proj"
        fail_dir = GENERATED_PROJECTS_DIR / fail_proj_id
        if fail_dir.exists():
            shutil.rmtree(fail_dir, ignore_errors=True)
        fail_dir.mkdir(parents=True, exist_ok=True)

        conn = get_standalone_db()
        with conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (fail_proj_id,))
            conn.execute("""
                INSERT INTO projects (id, user_id, name, description, status, language)
                VALUES (?, ?, 'Fail App', 'App destined to fail startup', 'in_progress', 'Node.js')
            """, (fail_proj_id, self.user_id))
        conn.close()

        try:
            resp = self.client.post(
                f"/projects/{fail_proj_id}/run-project",
                headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
            )
            self.assertTrue(resp.is_json, "Failure response Content-Type must be application/json")
            data = resp.get_json()
            self.assertFalse(data.get("success"), "Success must be false on failure")
            self.assertEqual(data.get("status"), "failed")
            self.assertIn("error", data)
            self.assertIn("code", data["error"])
            self.assertIn("message", data["error"])
        finally:
            if fail_dir.exists():
                shutil.rmtree(fail_dir, ignore_errors=True)
            conn = get_standalone_db()
            with conn:
                conn.execute("DELETE FROM projects WHERE id = ?", (fail_proj_id,))
            conn.close()

    def test_3_incorrect_endpoint_returns_json_for_api_requests(self):
        """Verifies 404 on API requests returns structured JSON rather than an HTML error page."""
        resp = self.client.get(
            f"/projects/{self.project_id}/run-project-nonexistent-endpoint",
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(resp.is_json, "404 on API must be JSON, not HTML")
        data = resp.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("error", {}).get("code"), "NOT_FOUND")

    def test_4_method_not_allowed_returns_json_for_api_requests(self):
        """Verifies 405 on API requests returns structured JSON rather than HTML."""
        resp = self.client.delete(
            f"/projects/{self.project_id}/run-project",
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(resp.is_json, "405 on API must be JSON, not HTML")
        data = resp.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("error", {}).get("code"), "METHOD_NOT_ALLOWED")

    def test_5_authentication_failures_return_401_json(self):
        """Verifies unauthenticated requests to API endpoints return 401 JSON, not 302 login HTML redirect."""
        unauth_client = app.test_client()
        resp = unauth_client.post(
            f"/projects/{self.project_id}/run-project",
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(resp.is_json, "Unauthenticated API request must return 401 JSON")
        data = resp.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("error", {}).get("code"), "UNAUTHORIZED")

    def test_6_frontend_modal_script_robustness(self):
        """Verifies launch_modal.html handles content-type and prevents uncaught JSON exceptions."""
        modal_file = ROOT_DIR / 'templates' / 'components' / 'launch_modal.html'
        self.assertTrue(modal_file.exists())
        content = modal_file.read_text(encoding='utf-8')

        # Verifies inspecting response Content-Type
        self.assertIn('res.headers.get("content-type")', content)
        self.assertIn('contentType.includes("application/json")', content)

        # Verifies handling unexpected HTML response without JSON parse crash
        self.assertIn('UNEXPECTED_HTML_RESPONSE', content)
        self.assertIn('Server returned unexpected HTML response', content)

        # Verifies safe logging without exposing full HTML
        self.assertIn('textBody.substring(0, 300)', content)

        # Verifies fallback JSON call is guarded by active launch state
        self.assertIn('if (isLaunching)', content)

    def test_7_get_run_project_status(self):
        """Verifies GET /projects/<id>/run-project returns status JSON."""
        resp = self.client.get(
            f"/projects/{self.project_id}/run-project",
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.is_json)
        data = resp.get_json()
        self.assertIn("status", data)
        self.assertIn("project_name", data)

    def test_8_existing_features_continue_working(self):
        """Verifies Run Tests and status-json routes continue working."""
        # 1. status-json
        resp_status = self.client.get(f"/projects/{self.project_id}/status-json")
        self.assertEqual(resp_status.status_code, 200)
        self.assertTrue(resp_status.is_json)

        # 2. launch-status alias
        resp_launch = self.client.get(f"/projects/{self.project_id}/launch-status")
        self.assertEqual(resp_launch.status_code, 200)
        self.assertTrue(resp_launch.is_json)
        self.assertIn("ready", resp_launch.get_json())
        self.assertIn("state", resp_launch.get_json())


if __name__ == '__main__':
    unittest.main()
