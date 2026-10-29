import os
import sys
import unittest
import json
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import app
from db import init_db, get_standalone_db
import services.project_service as project_service
import services.ui_service as ui_service
from services.workspace_manager import get_project_workspace

class UIPreviewSystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        init_db()

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
                
            # Verify existing projects
            cursor.execute("SELECT id, name FROM projects WHERE user_id = ?", (self.user_id,))
            self.user_projects = {r["name"]: r["id"] for r in cursor.fetchall()}
        conn.close()

        self.smart_expense_id = self.user_projects.get("Smart Expense Tracker AI")
        self.hiresmart_id = self.user_projects.get("HireSmart AI")

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["user_name"] = "Krishna Deepika"
            sess["user_email"] = "krishnadeepika9704@gmail.com"
            sess["csrf_token"] = "test_csrf_token"

    # 1. Test preview rendering for base.html
    def test_01_preview_rendering_base_html(self):
        for pid in [self.smart_expense_id, self.hiresmart_id]:
            if pid:
                success, html = ui_service.render_preview_page(pid, "templates/base.html")
                self.assertTrue(success, f"Failed rendering base.html for {pid}")
                self.assertNotIn("'current_user' is undefined", html)
                self.assertNotIn("Template Rendering Error", html)
                self.assertTrue(len(html) > 500)

    # 2. Test preview rendering for login.html
    def test_02_preview_rendering_login_html(self):
        for pid in [self.smart_expense_id, self.hiresmart_id]:
            if pid:
                success, html = ui_service.render_preview_page(pid, "templates/login.html")
                self.assertTrue(success, f"Failed rendering login.html for {pid}")
                self.assertNotIn("'current_user' is undefined", html)
                self.assertIn("password", html.lower())

    # 3. Test preview rendering for dashboard.html / index.html
    def test_03_preview_rendering_dashboard_html(self):
        # HireSmart AI has dashboard.html
        if self.hiresmart_id:
            success, html = ui_service.render_preview_page(self.hiresmart_id, "templates/dashboard.html", auth_mode="authenticated")
            self.assertTrue(success, "Failed rendering dashboard.html for HireSmart AI")
            self.assertNotIn("'current_user' is undefined", html)
            self.assertNotIn("Template Rendering Error", html)

        # Smart Expense Tracker has index.html
        if self.smart_expense_id:
            success, html = ui_service.render_preview_page(self.smart_expense_id, "templates/index.html", auth_mode="authenticated")
            self.assertTrue(success, "Failed rendering index.html for Smart Expense Tracker")
            self.assertNotIn("'current_user' is undefined", html)

    # 4. Test preview rendering for settings.html
    def test_04_preview_rendering_settings_html(self):
        if self.hiresmart_id:
            success, html = ui_service.render_preview_page(self.hiresmart_id, "templates/settings.html")
            self.assertTrue(success, "Failed rendering settings.html for HireSmart AI")
            self.assertNotIn("'current_user' is undefined", html)
            self.assertIn("Settings", html)

    # 5. Test a template that uses current_user (verify both guest & authenticated modes)
    def test_05_template_using_current_user(self):
        pid = self.hiresmart_id or self.smart_expense_id
        self.assertIsNotNone(pid)

        # Guest mode: current_user.is_authenticated == False -> should display Sign In / Sign Up
        success_guest, html_guest = ui_service.render_preview_page(pid, "landing.html", auth_mode="guest")
        self.assertTrue(success_guest)
        self.assertNotIn("'current_user' is undefined", html_guest)
        self.assertIn("Sign In", html_guest)

        # Authenticated mode: current_user.is_authenticated == True
        success_auth, html_auth = ui_service.render_preview_page(
            pid, "landing.html", auth_mode="authenticated", current_user_info={"name": "Jane Tester", "email": "jane@test.com"}
        )
        self.assertTrue(success_auth)
        self.assertNotIn("'current_user' is undefined", html_auth)

    # 6. Test a template with missing optional data
    def test_06_template_missing_optional_data(self):
        pid = self.hiresmart_id or self.smart_expense_id
        # Render candidate_analysis or reports without explicit candidate list passed
        success, html = ui_service.render_preview_page(pid, "templates/reports.html")
        self.assertTrue(success)
        self.assertNotIn("Template Rendering Error", html)
        self.assertNotIn("is undefined", html)

    # 7. Test responsive preview routes
    def test_07_responsive_preview_routes(self):
        self._login()
        pid = self.hiresmart_id or self.smart_expense_id
        
        # 1. UI Preview studio main page
        res = self.client.get(f"/projects/{pid}/ui-preview")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Generated Page Catalog", res.data)
        self.assertIn(b"Desktop", res.data)
        self.assertIn(b"Tablet", res.data)
        self.assertIn(b"Mobile", res.data)
        self.assertIn(b"Full View", res.data)

        # 2. Raw render endpoint with query param
        render_res = self.client.get(f"/projects/{pid}/ui-preview/render?page=templates/landing.html&auth=guest")
        self.assertEqual(render_res.status_code, 200)
        self.assertIn("text/html", render_res.content_type)
        self.assertNotIn(b"'current_user' is undefined", render_res.data)

        # 3. Path alias endpoint
        path_res = self.client.get(f"/projects/{pid}/ui-preview/render/templates/landing.html")
        self.assertEqual(path_res.status_code, 200)

        # 4. Static asset serving endpoint
        asset_res = self.client.get(f"/projects/{pid}/preview/asset/css/style.css")
        self.assertIn(asset_res.status_code, [200, 404])
        if asset_res.status_code == 200:
            self.assertIn("text/css", asset_res.content_type)

    # 8. Test invalid template paths and path traversal rejection
    def test_08_invalid_template_paths(self):
        self._login()
        pid = self.hiresmart_id or self.smart_expense_id
        
        # Invalid template name
        res = self.client.get(f"/projects/{pid}/ui-preview/render?page=non_existent_file_xyz.html")
        self.assertEqual(res.status_code, 404)
        self.assertIn(b"Template Not Found", res.data)

        # Path traversal attack
        traversal_res = self.client.get(f"/projects/{pid}/preview/asset/../../.env")
        self.assertIn(traversal_res.status_code, [403, 404])

        # Sensitive file extension block
        secret_res = self.client.get(f"/projects/{pid}/preview/asset/app.py")
        self.assertEqual(secret_res.status_code, 403)

    # 9. Test project isolation
    def test_09_project_isolation(self):
        self._login()
        # Verify unauthorized user cannot access project preview
        with self.client.session_transaction() as sess:
            sess["user_id"] = 99999 # Non-owner
            
        pid = self.hiresmart_id or self.smart_expense_id
        res = self.client.get(f"/projects/{pid}/ui-preview")
        self.assertEqual(res.status_code, 404)

    # 10. Test UI/UX recommendation system across 15 categories
    def test_10_recommendation_system(self):
        pid = self.smart_expense_id or self.hiresmart_id
        recs = ui_service.get_project_ui_recommendations(pid)
        self.assertTrue(len(recs) > 0, "No recommendations generated")
        
        # Verify structure
        sample = recs[0]
        self.assertIn("id", sample)
        self.assertIn("title", sample)
        self.assertIn("category", sample)
        self.assertIn("priority", sample)
        self.assertIn("evidence", sample)
        self.assertIn("suggested_improvement", sample)
        self.assertIn("expected_benefit", sample)
        self.assertIn("status", sample)

    # 11. Test that applying a recommendation produces a valid result with backup
    def test_11_apply_recommendation_safely(self):
        pid = self.smart_expense_id or self.hiresmart_id
        recs = ui_service.get_project_ui_recommendations(pid)
        pending_recs = [r for r in recs if r["status"] == "pending"]
        if not pending_recs:
            ui_service.analyze_project_ui_ux(pid)
            recs = ui_service.get_project_ui_recommendations(pid)
            pending_recs = [r for r in recs if r["status"] == "pending"]
            
        self.assertTrue(len(pending_recs) > 0)
        target_rec = pending_recs[0]
        
        # Apply
        res = ui_service.apply_ui_recommendation(pid, target_rec["id"])
        self.assertTrue(res["success"], f"Failed to apply: {res.get('error')}")
        self.assertTrue(Path(res["backup_path"]).exists(), "Backup was not created")

        # Verify status in database
        updated_recs = ui_service.get_project_ui_recommendations(pid)
        matched = next(r for r in updated_recs if r["id"] == target_rec["id"])
        self.assertEqual(matched["status"], "applied")

    # 12. Test dismiss recommendation
    def test_12_dismiss_recommendation(self):
        pid = self.smart_expense_id or self.hiresmart_id
        recs = ui_service.get_project_ui_recommendations(pid)
        pending = [r for r in recs if r["status"] == "pending"]
        if pending:
            target = pending[0]
            d_res = ui_service.dismiss_ui_recommendation(pid, target["id"])
            self.assertTrue(d_res["success"])
            updated = ui_service.get_project_ui_recommendations(pid)
            matched = next(r for r in updated if r["id"] == target["id"])
            self.assertEqual(matched["status"], "dismissed")

    # 13. Test ClaimWise AI Claims Management page renders with injected CSS and InsurTech UI
    def test_13_claimwise_claims_management_rendering_and_styles(self):
        pid = "proj_87ec37b85e"
        success, html = ui_service.render_preview_page(pid, "templates/claims_management.html")
        self.assertTrue(success, "Failed to render claims_management.html for ClaimWise AI")
        
        # Verify styling injection
        self.assertIn('id="preview-injected-styles"', html, "CSS stylesheet was not injected into preview <head>")
        self.assertIn("ClaimWise AI", html)
        self.assertIn("Enterprise InsurTech", html)
        
        # Verify no placeholder content
        self.assertNotIn("Module Ready", html, "claims_management.html still contains 'Module Ready' placeholder")
        self.assertNotIn("Auto-generated custom interface component", html)
        
        # Verify real InsurTech table & KPIs
        self.assertIn("claimsDataTable", html)
        self.assertIn("Total Active Claims", html)
        self.assertIn("Pending Intake", html)
        self.assertIn("Under Review", html)
        self.assertIn("Flagged for Fraud", html)
        self.assertIn("CLM-2026-", html)

    # 14. Test ClaimWise AI asset serving endpoint returns proper CSS and blocks path traversal
    def test_14_claimwise_asset_serving_and_mime_type(self):
        pid = "proj_87ec37b85e"
        token = ui_service.get_preview_asset_token(pid)
        
        # Test valid CSS asset request
        res = self.client.get(f"/projects/{pid}/preview/asset/css/style.css?token={token}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/css", res.headers.get("Content-Type", ""))
        self.assertIn("ClaimWise AI", res.data.decode("utf-8", errors="ignore"))
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "*")
        
        # Test security: directory traversal blocked
        traversal_res = self.client.get(f"/projects/{pid}/preview/asset/../../.env?token={token}")
        self.assertIn(traversal_res.status_code, [403, 404])
        
        # Test security: python source code blocked
        py_res = self.client.get(f"/projects/{pid}/preview/asset/app.py?token={token}")
        self.assertIn(py_res.status_code, [403, 404])

    # 15. Test all 24 ClaimWise AI templates render successfully without generic placeholders
    def test_15_all_24_claimwise_templates_render_without_placeholders(self):
        pid = "proj_87ec37b85e"
        templates = ui_service.resolve_project_templates(pid)
        self.assertGreaterEqual(len(templates), 24, "ClaimWise AI should have at least 24 templates")
        
        required_templates = [
            "templates/dashboard.html",
            "templates/claims_management.html",
            "templates/submit_claim.html",
            "templates/claim_details.html",
            "templates/agent_monitoring.html",
            "templates/document_analysis.html",
            "templates/fraud_risk_assessment.html",
            "templates/claim_review.html",
            "templates/policy_management.html",
            "templates/user_management.html",
            "templates/audit_trail.html",
            "templates/analytics_dashboard.html",
            "templates/notifications.html",
            "templates/workflow_monitor.html",
            "templates/evidence_verification.html",
            "templates/compliance_center.html",
            "templates/system_health.html",
            "templates/reports.html",
            "templates/settings.html",
            "templates/landing.html",
            "templates/login.html",
            "templates/register.html",
            "templates/projects.html"
        ]
        
        for tmpl in required_templates:
            success, rendered = ui_service.render_preview_page(pid, tmpl)
            self.assertTrue(success, f"Template {tmpl} failed to render")
            self.assertNotIn("Module Ready", rendered, f"{tmpl} contains 'Module Ready'")
            self.assertNotIn("Auto-generated custom interface component", rendered, f"{tmpl} contains generic boilerplate")
            self.assertIn('id="preview-injected-styles"', rendered, f"{tmpl} missing injected CSS stylesheet")

if __name__ == "__main__":
    unittest.main()

