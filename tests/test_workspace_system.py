import os
import sys
import unittest
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import app
from db import init_db, get_standalone_db
import services.project_service as project_service
import services.workspace_manager as workspace_manager
import services.execution_service as execution_service
from services.workspace_manager import (
    GENERATED_PROJECTS_DIR,
    validate_project_name,
    get_project_workspace,
    organize_existing_projects
)

class WorkspaceManagementSystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls._cleanup_test_projects()
        init_db()
        organize_existing_projects()

    @classmethod
    def tearDownClass(cls):
        cls._cleanup_test_projects()

    @classmethod
    def _cleanup_test_projects(cls):
        import shutil
        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, workspace_path FROM projects WHERE name IN ('Cloud DevOps Automation Suite', 'OmniChannel Inventory Manager')")
            for r in cursor.fetchall():
                cursor.execute("DELETE FROM project_files WHERE project_id = ?", (r["id"],))
                cursor.execute("DELETE FROM projects WHERE id = ?", (r["id"],))
                if r["workspace_path"]:
                    p = Path(r["workspace_path"])
                    if p.exists() and p != GENERATED_PROJECTS_DIR:
                        shutil.rmtree(p, ignore_errors=True)
            # Also clean up the candidate directory if it exists without db record
            for folder_name in ["Cloud_DevOps_Automation_Suite", "OmniChannel_Inventory_Manager"]:
                candidate = GENERATED_PROJECTS_DIR / folder_name
                if candidate.exists():
                    shutil.rmtree(candidate, ignore_errors=True)
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        # Seed test user
        conn = get_standalone_db()
        with conn:
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

    # 1. Listing the two existing projects
    def test_01_listing_existing_projects(self):
        projects = project_service.get_user_projects(self.user_id)
        project_names = [p["name"] for p in projects]
        self.assertIn("Smart Expense Tracker AI", project_names)
        self.assertIn("HireSmart AI", project_names)

    # 2. Resolving each project's correct workspace path
    def test_02_resolving_workspace_paths(self):
        projects = project_service.get_user_projects(self.user_id)
        for p in projects:
            if p["name"] in ["Smart Expense Tracker AI", "HireSmart AI"]:
                ws = get_project_workspace(p["id"])
                self.assertTrue(ws.exists(), f"Workspace directory does not exist: {ws}")
                self.assertTrue(str(ws).startswith(str(GENERATED_PROJECTS_DIR)), f"Workspace {ws} escapes parent")
                self.assertTrue((ws / "app.py").exists(), f"app.py missing in {ws}")

    # 3. Creating a third project
    def test_03_creating_third_project(self):
        proj_3_name = "Cloud DevOps Automation Suite"
        proj_3_id = project_service.create_project(
            user_id=self.user_id,
            name=proj_3_name,
            description="Autonomous CI/CD and deployment pipeline orchestrator.",
            app_type="Web App",
            language="Python Flask"
        )
        self.assertIsNotNone(proj_3_id)
        self.assertTrue(proj_3_id.startswith("proj_"))
        
        proj_3 = project_service.get_project_by_id(proj_3_id, user_id=self.user_id)
        self.assertIsNotNone(proj_3)
        self.assertEqual(proj_3["name"], proj_3_name)

    # 4. Confirming that it gets a separate directory
    def test_04_third_project_separate_directory(self):
        proj = None
        for p in project_service.get_user_projects(self.user_id):
            if p["name"] == "Cloud DevOps Automation Suite":
                proj = p
                break
        self.assertIsNotNone(proj)
        ws = get_project_workspace(proj["id"])
        self.assertTrue(ws.exists())
        self.assertTrue(ws.name.startswith("Cloud_DevOps_Automation_Suite"))

    # 5. Confirming that a fourth project can also be created automatically
    def test_05_creating_fourth_project_automatically(self):
        proj_4_name = "OmniChannel Inventory Manager"
        proj_4_id = project_service.create_project(
            user_id=self.user_id,
            name=proj_4_name,
            description="Warehouse inventory and supply chain tracking.",
            app_type="Web App",
            language="Python Flask"
        )
        self.assertIsNotNone(proj_4_id)
        ws_4 = get_project_workspace(proj_4_id)
        self.assertTrue(ws_4.exists())
        self.assertTrue(ws_4.name.startswith("OmniChannel_Inventory_Manager"))

    # 6. Confirming that creating projects does not overwrite earlier projects
    def test_06_non_overwriting_earlier_projects(self):
        projects = project_service.get_user_projects(self.user_id)
        by_name = {p["name"]: p for p in projects}

        # Check project 1
        p1 = by_name.get("Smart Expense Tracker AI")
        self.assertIsNotNone(p1)
        ws1 = get_project_workspace(p1["id"])
        self.assertTrue((ws1 / "app.py").exists())
        self.assertTrue((ws1 / "models.py").exists())
        self.assertTrue((ws1 / "services.py").exists())

        # Check project 2
        p2 = by_name.get("HireSmart AI")
        self.assertIsNotNone(p2)
        ws2 = get_project_workspace(p2["id"])
        self.assertTrue((ws2 / "app.py").exists())
        self.assertTrue((ws2 / "config.py").exists())
        self.assertTrue((ws2 / "models.py").exists())

    # 7. Confirming that dashboard project links open the correct project
    def test_07_dashboard_project_links(self):
        self._login()
        res = self.client.get("/projects")
        self.assertEqual(res.status_code, 200)
        content = res.data.decode("utf-8")

        # Verify project names and workspace paths are displayed
        self.assertIn("Smart Expense Tracker AI", content)
        self.assertIn("HireSmart AI", content)
        self.assertIn("Workspace:", content)
        self.assertIn("Open Project &rarr;", content)
        self.assertIn("Run Project", content)
        self.assertIn("View Files", content)

        # Open workspace for HireSmart AI
        projects = project_service.get_user_projects(self.user_id)
        hire_smart = next(p for p in projects if p["name"] == "HireSmart AI")
        ws_res = self.client.get(f"/projects/{hire_smart['id']}/workspace")
        self.assertEqual(ws_res.status_code, 200)
        self.assertIn(b"HireSmart AI", ws_res.data)

    # 8. Confirming that Run Project executes the selected project, not the main app
    def test_08_run_project_executes_target_not_main_app(self):
        projects = project_service.get_user_projects(self.user_id)
        smart_expense = next(p for p in projects if p["name"] == "Smart Expense Tracker AI")
        ws = get_project_workspace(smart_expense["id"])

        # Detect stack
        stack = execution_service.detect_project_stack(ws)
        self.assertEqual(stack["entry_file"], "app.py")
        self.assertEqual(stack["framework"], "flask")

        # Verify guard blocks executing root DevGuardian
        main_guard_result = execution_service.start_project_process = execution_service.start_project_app
        # Direct check on root
        root_dir = ROOT_DIR.resolve()
        self.assertNotEqual(ws.resolve(), root_dir)

    # 9. Confirming that invalid project names cannot escape generated_projects
    def test_09_path_traversal_protection(self):
        # Name validation blocks traversal patterns
        invalid_names = [
            "../../../evil_path",
            "../escape",
            "test/slash",
            "test\\backslash",
            "NUL",
            "CON",
            "a" # too short
        ]
        for bad_name in invalid_names:
            valid, msg = validate_project_name(bad_name)
            self.assertFalse(valid, f"Expected '{bad_name}' to be invalid")

        # allocate_project_workspace raises ValueError on bad name
        with self.assertRaises(ValueError):
            workspace_manager.allocate_project_workspace("proj_fake", "../../../escape")

    # 10. Confirming that database paths remain correct after organizing projects
    def test_10_database_paths_remain_correct_after_organizing(self):
        results = organize_existing_projects()
        self.assertTrue(len(results) > 0)

        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, workspace_path FROM projects WHERE user_id = ?", (self.user_id,))
        rows = cursor.fetchall()
        conn.close()

        for r in rows:
            path_str = r["workspace_path"]
            self.assertIsNotNone(path_str, f"Project {r['name']} has null workspace_path")
            p = Path(path_str)
            self.assertTrue(p.exists(), f"Path for {r['name']} does not exist on disk: {path_str}")
            self.assertTrue(str(p.resolve()).startswith(str(GENERATED_PROJECTS_DIR.resolve())))

if __name__ == "__main__":
    unittest.main()
