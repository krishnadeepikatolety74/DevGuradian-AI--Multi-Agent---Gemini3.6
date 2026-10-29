import os
import sys
import unittest
from unittest.mock import patch
import json
import io
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from db import init_db, get_standalone_db
import services.project_service as project_service
import services.ai_service as ai_service
import services.code_generator as code_generator
import services.testing_service as testing_service
import services.security_service as security_service
import services.review_service as review_service
import services.deployment_service as deployment_service
import services.report_service as report_service
import services.workflow_service as workflow_service

class DevGuardianIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test client and ensure database initialized."""
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        init_db()

    def setUp(self):
        self.client = app.test_client()
        # Seed test user
        conn = get_standalone_db()
        with conn:
            conn.execute("DELETE FROM projects WHERE name LIKE 'Test%'")
            conn.execute("DELETE FROM users WHERE email = 'test_dev@example.com'")
            conn.execute("DELETE FROM users WHERE email = 'user_b@example.com'")
            conn.execute("DELETE FROM oauth_accounts WHERE provider_email IN ('test_google_user@gmail.com', 'test_octocat@github.com')")
            conn.execute("DELETE FROM users WHERE email IN ('test_google_user@gmail.com', 'test_octocat@github.com')")
        conn.close()

    def test_01_landing_page_renders(self):
        """Verify landing page loads successfully with 200 OK and robot markup."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"DevGuardian AI", res.data)
        self.assertIn(b"Autonomous Software Project Manager", res.data)
        self.assertIn(b"robot-stage-container", res.data)
        self.assertIn(b"robot-head", res.data)
        self.assertIn(b"robot-eye", res.data)

    def test_02_registration_and_login_flow(self):
        """Test user registration and subsequent login."""
        # 1. Register User
        with self.client.session_transaction() as sess:
            token = sess["csrf_token"] = "test_csrf_token"

        reg_data = {
            "csrf_token": "test_csrf_token",
            "full_name": "Test Developer",
            "email": "test_dev@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        res = self.client.post("/register", data=reg_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Welcome to DevGuardian AI", res.data)

        # 2. Verify Session
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_email"), "test_dev@example.com")
            user_id = sess.get("user_id")
            self.assertIsNotNone(user_id)

        # 3. Logout
        res_logout = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(res_logout.status_code, 200)

        # 4. Login with correct credentials
        with self.client.session_transaction() as sess:
            token = sess["csrf_token"] = "test_csrf_token"

        login_data = {
            "csrf_token": "test_csrf_token",
            "email": "test_dev@example.com",
            "password": "Password123!"
        }
        res_login = self.client.post("/login", data=login_data, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"Welcome back", res_login.data)

    def test_03_project_creation_and_database_persistence(self):
        """Test creating a project and verifying DB persistence and live stats."""
        # Register and login
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "test_csrf_token"

        self.client.post("/register", data={
            "csrf_token": "test_csrf_token",
            "full_name": "Project Tester",
            "email": "test_dev@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })

        with self.client.session_transaction() as sess:
            user_id = sess["user_id"]
            sess["csrf_token"] = "test_csrf_token"

        # Create project via POST
        proj_data = {
            "csrf_token": "test_csrf_token",
            "name": "Test Food Recognition App",
            "description": "Build an image classifier application that identifies food items and calories.",
            "app_type": "Web App",
            "language": "Python Flask",
            "tech_preferences": "SQLite, Pillow"
        }
        res = self.client.post("/projects/create", data=proj_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Test Food Recognition App", res.data)

        # Verify in SQLite database
        projects = project_service.get_user_projects(user_id)
        self.assertTrue(any(p["name"] == "Test Food Recognition App" for p in projects))
        project_id = [p["id"] for p in projects if p["name"] == "Test Food Recognition App"][0]

        # Verify 8 agent executions were initialized
        executions = project_service.get_project_agent_executions(project_id)
        self.assertEqual(len(executions), 8)
        self.assertEqual(executions[0]["agent_key"], "requirement")

        # Verify live stats
        stats = project_service.get_dashboard_stats(user_id)
        self.assertGreaterEqual(stats["total_projects"], 1)

    def test_04_user_isolation_security(self):
        """Verify User A cannot view User B's private project."""
        # Create Project for User A
        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (full_name, email, password_hash) VALUES ('User A', 'usera@example.com', 'hash')")
            user_a_id = cursor.execute("SELECT id FROM users WHERE email='usera@example.com'").fetchone()["id"]
            cursor.execute("INSERT OR IGNORE INTO users (full_name, email, password_hash) VALUES ('User B', 'userb@example.com', 'hash')")
            user_b_id = cursor.execute("SELECT id FROM users WHERE email='userb@example.com'").fetchone()["id"]
        conn.close()

        proj_id_a = project_service.create_project(user_a_id, "User A Secret Project", "Classified spec")

        # Try to access as User B
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_b_id
            sess["user_name"] = "User B"
            sess["user_email"] = "userb@example.com"
            sess["csrf_token"] = "test_csrf_token"

        res = self.client.get(f"/projects/{proj_id_a}/workspace")
        self.assertEqual(res.status_code, 404)

    def test_05_eight_agent_langgraph_pipeline_execution(self):
        """Verify the full 8-agent LangGraph workflow execution from end to end."""
        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (full_name, email, password_hash) VALUES ('Pipeline Dev', 'pipeline@example.com', 'hash')")
            user_id = cursor.execute("SELECT id FROM users WHERE email='pipeline@example.com'").fetchone()["id"]
        conn.close()

        proj_id = project_service.create_project(
            user_id,
            "Test Full Pipeline App",
            "A complete task tracker web application with categories and status flags."
        )

        # Run complete 8-agent pipeline
        workflow_state = workflow_service.run_full_workflow(proj_id, api_key=None)
        
        self.assertIsNone(workflow_state.get("error_info"))
        self.assertEqual(workflow_state["current_stage"], "completed")
        self.assertEqual(workflow_state["status"], "completed")

        # 1. Requirements Agent output verification
        self.assertIsNotNone(workflow_state.get("requirements"))
        self.assertIn("Software Requirements Specification", workflow_state["requirements"])

        # 2. Architecture Agent output verification
        self.assertIsNotNone(workflow_state.get("architecture"))
        self.assertIn("Architecture", workflow_state["architecture"])

        files = code_generator.get_project_files_from_db(proj_id)
        self.assertGreaterEqual(len(files), 4)
        file_names = [f["filename"] for f in files]
        self.assertTrue(any(f.endswith(".py") for f in file_names), "Expected Python files in manifest")
        self.assertTrue(any("model" in f or "task" in f or "app" in f for f in file_names), "Expected core domain files in manifest")

        # 4. AST Syntax validation on generated Python files
        for f in files:
            if f["filename"].endswith(".py"):
                valid, msg = code_generator.validate_python_code(f["file_content"], f["filename"])
                self.assertTrue(valid, f"Syntax Error in {f['filename']}: {msg}")

        # 5. Testing Agent verification
        test_res = testing_service.get_latest_test_results(proj_id)
        self.assertGreater(test_res["total_tests"], 0)
        self.assertIn(test_res["overall_result"], ["passed", "completed"])

        # 6. Security Agent audit verification
        findings = security_service.get_project_security_findings(proj_id)
        self.assertGreaterEqual(len(findings), 1)
        # Verify no Critical SQL injection or eval in clean generated code
        has_critical = any(f["severity"] == "Critical" for f in findings)
        self.assertFalse(has_critical)

        # 7. Code Review Agent score verification
        review = review_service.get_project_code_review(proj_id)
        self.assertGreaterEqual(review["overall_score"], 7)
        self.assertEqual(review["status"], "approved")

        # 8. Deployment Agent verification
        deployment = deployment_service.get_project_deployment(proj_id)
        self.assertEqual(deployment["readiness_status"], "ready")
        self.assertIn("FROM python", deployment["dockerfile_content"])

        # 9. Project Manager Report verification
        report = report_service.get_project_report(proj_id)
        self.assertIsNotNone(report)
        self.assertIn("Final Project Execution Report", report["final_output"])

    def test_06_pdf_and_zip_downloads(self):
        """Verify ReportLab PDF generation and ZIP download endpoints."""
        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (full_name, email, password_hash) VALUES ('Download User', 'downloader@example.com', 'hash')")
            user_id = cursor.execute("SELECT id FROM users WHERE email='downloader@example.com'").fetchone()["id"]
        conn.close()

        proj_id = project_service.create_project(
            user_id,
            "Download Test Project",
            "Application built for testing download endpoints."
        )
        workflow_service.run_full_workflow(proj_id, api_key=None)

        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["user_name"] = "Downloader"
            sess["user_email"] = "downloader@example.com"
            sess["csrf_token"] = "test_csrf_token"

        # 1. Download ZIP
        res_zip = self.client.get(f"/projects/{proj_id}/download/zip")
        self.assertEqual(res_zip.status_code, 200)
        self.assertEqual(res_zip.mimetype, "application/zip")
        self.assertTrue(len(res_zip.data) > 100)
        # Verify ZIP header PK\x03\x04
        self.assertTrue(res_zip.data.startswith(b"PK\x03\x04"))

        # 2. Download PDF
        res_pdf = self.client.get(f"/projects/{proj_id}/download/pdf")
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.mimetype, "application/pdf")
        self.assertTrue(len(res_pdf.data) > 500)
        # Verify PDF header %PDF
        self.assertTrue(res_pdf.data.startswith(b"%PDF"))

    def test_07_security_scanner_detects_flaws(self):
        """Verify the security service accurately identifies SQL injection and eval risks."""
        insecure_manifest = {
            "vulnerable.py": """
import sqlite3
def bad_func(user_input):
    eval(user_input)
    cursor.execute(f"SELECT * FROM users WHERE name = '{user_input}'")
"""
        }
        res = security_service.scan_project_security("sec_test_dummy", insecure_manifest)
        self.assertEqual(res["status"], "failed")
        critical_count = res["counts"]["Critical"]
        self.assertGreaterEqual(critical_count, 2)
        rules = [f["rule_id"] for f in res["findings"]]
        self.assertIn("SEC-R001", rules)  # eval/exec
        self.assertIn("SEC-R002", rules)  # SQL injection

    def test_08_invalid_login_rejection(self):
        """Verify invalid credentials return error message and do not create session."""
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "test_csrf_token"

        res = self.client.post("/login", data={
            "csrf_token": "test_csrf_token",
            "email": "nonexistent@example.com",
            "password": "WrongPassword!"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Invalid email or password", res.data)

    def test_09_path_traversal_protection(self):
        """Verify that directory traversal attempts in file fetching are blocked."""
        with self.assertRaises(ValueError):
            code_generator.get_project_dir("../../../evil_path")

    def test_10_csrf_protection_enforcement(self):
        """Verify POST requests without CSRF token are blocked."""
        res = self.client.post("/login", data={
            "email": "test@example.com",
            "password": "pass"
        })
        self.assertEqual(res.status_code, 403)

    def test_11_landing_page_smooth_scroll_and_sections(self):
        """Verify landing page includes all sections (Home, Features, Agents, Workflow, About) and smooth scrolling."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        content = res.data.decode("utf-8")
        
        # Verify navigation links
        self.assertIn('href="#home"', content)
        self.assertIn('href="#features"', content)
        self.assertIn('href="#agents"', content)
        self.assertIn('href="#workflow"', content)
        self.assertIn('href="#about"', content)

        # Verify section elements
        self.assertIn('id="home"', content)
        self.assertIn('id="features"', content)
        self.assertIn('id="agents"', content)
        self.assertIn('id="workflow"', content)
        self.assertIn('id="about"', content)

        # Verify agent titles exist in content
        self.assertIn("Requirement Agent", content)
        self.assertIn("Architecture Agent", content)
        self.assertIn("Coding Agent", content)
        self.assertIn("Testing Agent", content)
        self.assertIn("Security Agent", content)
        self.assertIn("Code Review Agent", content)
        self.assertIn("Deployment Agent", content)
        self.assertIn("Project Manager Agent", content)

        # Verify smooth scroll script
        self.assertIn("smooth", content)

    @patch("services.oauth_service.exchange_google_code")
    @patch("services.oauth_service.verify_google_identity")
    @patch("services.oauth_service.exchange_github_code")
    @patch("services.oauth_service.get_github_identity")
    def test_12_google_and_github_oauth_authentication(self, mock_gh_id, mock_gh_ex, mock_g_id, mock_g_ex):
        """Verify Google and GitHub OAuth authentication creates session and redirects to dashboard."""
        os.environ["GOOGLE_CLIENT_ID"] = "test_g_id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test_g_secret"
        os.environ["GITHUB_CLIENT_ID"] = "test_gh_id"
        os.environ["GITHUB_CLIENT_SECRET"] = "test_gh_secret"

        # 1. Google OAuth flow
        mock_g_ex.return_value = {"id_token": "mock_id_token"}
        mock_g_id.return_value = {
            "provider": "google",
            "provider_user_id": "google-dev-1234",
            "email": "test_google_user@gmail.com",
            "email_verified": True,
            "full_name": "Google Tester"
        }
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state_g"

        res_google = self.client.get("/auth/callback/google?code=code_g&state=state_g", follow_redirects=True)
        self.assertEqual(res_google.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_email"), "test_google_user@gmail.com")
            self.assertEqual(sess.get("user_name"), "Google Tester")
            self.assertEqual(sess.get("auth_provider"), "google")

        # 2. Logout
        self.client.get("/logout")

        # 3. GitHub OAuth flow
        mock_gh_ex.return_value = "gh_token_123"
        mock_gh_id.return_value = {
            "provider": "github",
            "provider_user_id": "gh-dev-5678",
            "email": "test_octocat@github.com",
            "email_verified": True,
            "full_name": "Octocat Tester"
        }
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state_gh"

        res_github = self.client.get("/auth/callback/github?code=code_gh&state=state_gh", follow_redirects=True)
        self.assertEqual(res_github.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_email"), "test_octocat@github.com")
            self.assertEqual(sess.get("user_name"), "Octocat Tester")
            self.assertEqual(sess.get("auth_provider"), "github")

    def test_13_settings_page_no_api_key(self):
        """Verify settings page contains no API key password inputs or missing key warnings."""
        # Login first
        with self.client.session_transaction() as sess:
            sess["user_id"] = 18
            sess["user_email"] = "krishna@example.com"
            sess["user_name"] = "Krishna Deepika"
            sess["user_role"] = "Developer"

        res = self.client.get("/settings")
        self.assertEqual(res.status_code, 200)
        content = res.data.decode("utf-8")

        # Verify no API key inputs or warnings
        self.assertNotIn('name="gemini_api_key"', content)
        self.assertNotIn('Enter your Gemini API key below', content)
        self.assertIn("AI Model & Orchestrator Configuration", content)
        self.assertIn("Auto-Fix Limit", content)

        # Verify saving settings works without API key
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "test_csrf_token"

        res_save = self.client.post("/settings/save", data={
            "csrf_token": "test_csrf_token",
            "model_name": "gemini-1.5-pro",
            "auto_fix_limit": "5",
            "sandbox_timeout": "120",
            "security_strictness": "strict",
            "default_framework": "FastAPI"
        }, follow_redirects=True)
        self.assertEqual(res_save.status_code, 200)
        self.assertIn(b"Orchestration and model preferences updated successfully", res_save.data)

    def test_14_login_and_register_pages_contain_all_8_agents_and_oauth_links(self):
        """Verify login and register templates feature all 8 project agents and 1-click OAuth."""
        # 1. Login page check
        res_login = self.client.get("/login")
        self.assertEqual(res_login.status_code, 200)
        login_html = res_login.data.decode("utf-8")

        # Must have direct 1-click links to /auth/google and /auth/github
        self.assertIn('href="/auth/google"', login_html)
        self.assertIn('href="/auth/github"', login_html)
        # Must NOT contain the alert popups from the screenshots
        self.assertNotIn("OAuth provider requires client ID configuration", login_html)
        self.assertNotIn("GitHub OAuth requires client credentials", login_html)

        # All 8 agents must be present in the arc badges
        agents = [
            "Requirements",
            "Architecture",
            "Coding",
            "Testing",
            "Security",
            "Code Review",
            "Deployment",
            "Project Manager"
        ]
        for agent in agents:
            self.assertIn(agent, login_html, f"Agent '{agent}' missing from login.html")

        # 2. Register page check
        res_register = self.client.get("/register")
        self.assertEqual(res_register.status_code, 200)
        register_html = res_register.data.decode("utf-8")

        self.assertIn('href="/auth/google"', register_html)
        self.assertIn('href="/auth/github"', register_html)
        self.assertNotIn("OAuth provider requires client ID configuration", register_html)
        self.assertNotIn("GitHub OAuth requires client credentials", register_html)

        for agent in agents:
            self.assertIn(agent, register_html, f"Agent '{agent}' missing from register.html")

if __name__ == "__main__":
    unittest.main()

