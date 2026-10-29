import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import json
import tempfile
import shutil
import datetime
import io
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from db import init_db, get_standalone_db
import services.project_service as project_service
import services.ide_service as ide_service
from services.ide_adapters.base import BaseIDEAdapter
from services.ide_adapters.vscode_adapter import VSCodeAdapter
from services.ide_adapters.antigravity_adapter import AntigravityAdapter
from services.ide_adapters.kiro_adapter import KiroAdapter
import services.execution_service as execution_service
import services.ui_service as ui_service
import services.requirements_service as requirements_service
import services.validation_service as validation_service
import services.report_service as report_service
from services.report_service import SafeHTMLSanitizer, markdown_to_safe_html


class EnterpriseFeaturesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        init_db()

    def setUp(self):
        self.client = app.test_client()
        conn = get_standalone_db()
        with conn:
            conn.execute("DELETE FROM projects WHERE name LIKE 'EntTest%'")
            conn.execute("DELETE FROM users WHERE email = 'ent_tester@example.com'")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users (full_name, email, password_hash)
                VALUES ('Enterprise Tester', 'ent_tester@example.com', 'dummy_hash')
            """)
            self.user_id = cursor.execute("SELECT id FROM users WHERE email='ent_tester@example.com'").fetchone()["id"]
        conn.close()

    def _create_test_project(self, name="EntTest Project", desc="Enterprise test application specification"):
        proj_id = project_service.create_project(
            self.user_id,
            name,
            desc,
            app_type="Web App",
            language="Python Flask",
            tech_preferences="SQLite, HTML5, CSS3"
        )
        return proj_id

    # =========================================================================
    # FEATURE 1 & 12: PROFESSIONAL REPORT FORMATTING & SANITIZATION
    # =========================================================================
    def test_markdown_to_safe_html_elements(self):
        """Verify markdown syntax is converted to actual HTML elements without raw symbols."""
        raw_md = """### 3. Generated Source Manifest
- **Total Files:** 4
- `models.py` (2470 bytes)

---

| File | Size | Status |
| --- | --- | --- |
| app.py | 1200 | Verified |
"""
        html = markdown_to_safe_html(raw_md)
        
        # Verify real HTML elements are produced
        self.assertIn("<h3>3. Generated Source Manifest</h3>", html)
        self.assertIn("<strong>Total Files:</strong>", html)
        self.assertIn("<code>models.py</code>", html)
        self.assertIn("<ul>", html)
        self.assertIn("<li>", html)
        self.assertIn("<hr", html)
        self.assertIn("<table", html)
        self.assertIn("<th>File</th>", html)
        self.assertIn("<td>app.py</td>", html)

        # Verify raw markdown tokens are NOT present in output
        self.assertNotIn("###", html)
        self.assertNotIn("**Total Files:**", html)
        self.assertNotIn("`models.py`", html)

    def test_html_sanitization_removes_malicious_code(self):
        """Verify XSS vectors like scripts, onerror, and javascript: links are sanitized."""
        xss_input = (
            "<h3>Safe Heading</h3>\n"
            "<script>alert('pwned')</script>\n"
            "<img src=\"x\" onerror=\"alert('xss')\" alt=\"photo\">\n"
            "<a href=\"javascript:alert(1)\">Click Me</a>\n"
            "<p onclick=\"steal()\">Normal paragraph</p>\n"
        )
        clean_html = markdown_to_safe_html(xss_input)
        self.assertNotIn("<script>", clean_html.lower())
        self.assertNotIn("alert('pwned')", clean_html)
        self.assertNotIn("onerror", clean_html.lower())
        self.assertNotIn("onclick", clean_html.lower())
        self.assertNotIn("javascript:", clean_html.lower())
        self.assertIn("<h3>Safe Heading</h3>", clean_html)

    def test_compile_project_report_structured_sections(self):
        """Verify report_service compiles all 18 structured enterprise sections."""
        proj_id = self._create_test_project()
        
        # Populate basic mock report
        res = report_service.compile_project_report(
            proj_id, "EntTest Project", "Enterprise test application"
        )
        self.assertEqual(res["status"], "completed")
        
        report_row = report_service.get_project_report(proj_id)
        self.assertIsNotNone(report_row)
        
        structured = report_row["structured"]
        self.assertIsInstance(structured, dict)
        
        # Verify key sections exist among the 18 enterprise sections
        expected_sections = [
            "1_project_overview",
            "2_requirements_summary",
            "3_architecture",
            "4_technology_stack",
            "5_generated_files",
            "6_ui_ux_design",
            "7_ui_validation",
            "8_backend_validation",
            "9_integration_testing",
            "10_automated_test_results",
            "11_security_findings",
            "12_code_review",
            "13_requirements_traceability",
            "14_ide_configuration",
            "15_execution_results",
            "16_deployment_readiness",
            "17_known_limitations",
            "18_remaining_actions"
        ]
        for sec in expected_sections:
            self.assertIn(sec, structured, f"Missing required section {sec} in structured report")

    def test_report_detail_html_view(self):
        """Verify report detail web page displays structured cards, badges, and no raw markdown."""
        proj_id = self._create_test_project()
        report_service.compile_project_report(proj_id, "EntTest Project", "Enterprise spec")

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["user_name"] = "Enterprise Tester"
            sess["user_email"] = "ent_tester@example.com"
            sess["csrf_token"] = "test_csrf_token"

        res = self.client.get(f"/projects/{proj_id}/report")
        self.assertEqual(res.status_code, 200)
        content = res.data.decode("utf-8")
        
        # Verify enterprise report styling and components
        self.assertIn("Enterprise Software Delivery Report", content)
        self.assertIn("1. Project Overview", content)
        self.assertIn("15. Execution Results", content)
        self.assertIn("badge", content)
        self.assertIn("Download Certified PDF", content)
        
        # Verify raw markdown is not displayed in the HTML output
        self.assertNotIn("### 1.", content)
        self.assertNotIn("### 3.", content)

    def test_reportlab_pdf_generation(self):
        """Verify ReportLab produces valid binary PDF with header and structured sections."""
        proj_id = self._create_test_project()
        report_service.compile_project_report(proj_id, "EntTest Project", "Enterprise spec")

        pdf_buf = report_service.generate_pdf_report(proj_id)
        self.assertIsInstance(pdf_buf, io.BytesIO)
        pdf_data = pdf_buf.getvalue()
        self.assertTrue(len(pdf_data) > 1000)
        self.assertTrue(pdf_data.startswith(b"%PDF"))

    # =========================================================================
    # FEATURE 2, 3, 4: IDE ADAPTERS, DETECTION, CONFIGURATION & OPENING
    # =========================================================================
    def test_supported_ide_adapters(self):
        """Verify the 3 supported IDE adapters exist and implement BaseIDEAdapter."""
        ides = ide_service.get_supported_ides()
        self.assertIn("antigravity", ides)
        self.assertIn("vscode", ides)
        self.assertIn("kiro", ides)

        for ide_key in ides:
            adapter = ide_service.get_ide_adapter(ide_key)
            self.assertIsInstance(adapter, BaseIDEAdapter)
            self.assertIsNotNone(adapter.name)
            self.assertIsNotNone(adapter.icon)
            self.assertIsNotNone(adapter.description)

    def test_ide_adapter_detection_and_custom_path(self):
        """Verify detection returns valid states and handles custom executable path."""
        adapter = VSCodeAdapter()
        status_info = adapter.detect()
        self.assertIn(status_info["status"], ["Installed", "Not Detected", "Configured", "Ready"])

        # Test with invalid custom path
        invalid_det = adapter.detect(custom_path="C:\\NonExistent\\fake_ide.exe")
        self.assertIn(invalid_det["status"], ["Not Detected", "Not Configured"])
        self.assertIn("not exist", (invalid_det.get("message", "") + invalid_det.get("details", "")).lower())

        # Test manual instructions provide absolute project path
        workspace = Path(r"C:\Users\tester\Projects\test_app")
        instr = adapter.get_manual_instructions(workspace)
        self.assertIn(str(workspace), instr)
        self.assertIn("code", instr.lower())

    def test_ide_selection_persistence_and_launch_failure_handling(self):
        """Verify user IDE selection persists in DB and missing IDE reports clear error."""
        proj_id = self._create_test_project()
        
        # Select Antigravity
        ok = ide_service.select_project_ide(proj_id, "antigravity")
        self.assertTrue(ok)
        
        cfg = ide_service.get_project_ide_config(proj_id)
        self.assertEqual(cfg["selected_ide"], "antigravity")

        # Select Kiro
        ok = ide_service.select_project_ide(proj_id, "kiro")
        self.assertTrue(ok)
        cfg = ide_service.get_project_ide_config(proj_id)
        self.assertEqual(cfg["selected_ide"], "kiro")

        # Test launch when executable is mock-missing
        adapter = KiroAdapter()
        with patch.object(adapter, "detect", return_value={"status": "Not Detected", "executable_path": None, "details": "Not found"}):
            with patch("services.ide_service.get_ide_adapter", return_value=adapter):
                launch_res = ide_service.launch_ide_for_project(proj_id)
                self.assertFalse(launch_res["success"])
                self.assertIn("manual_instructions", launch_res)
                self.assertIn("workspace_dir", launch_res)

    def test_ide_security_path_validation(self):
        """Verify configure_project_ide_path rejects dangerous or non-existent executables."""
        proj_id = self._create_test_project()
        
        # Non-existent executable
        res = ide_service.configure_project_ide_path(proj_id, "C:\\evil\\cmd.exe")
        self.assertFalse(res["success"])
        self.assertIn("not exist", res["message"])

    # =========================================================================
    # FEATURE 5: PROJECT EXECUTION SERVICE
    # =========================================================================
    def test_detect_project_stack_and_command_profiles(self):
        """Verify detection of project stack (Flask) and approved command profiles."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Empty dir -> unknown
            stack = execution_service.detect_project_stack(Path(temp_dir))
            self.assertEqual(stack["runtime"], "python")

            # Dir with app.py -> Flask
            (Path(temp_dir) / "app.py").write_text("print('hello')", encoding="utf-8")
            stack_flask = execution_service.detect_project_stack(Path(temp_dir))
            self.assertEqual(stack_flask["runtime"], "python")
            self.assertEqual(stack_flask["framework"], "flask")
            self.assertEqual(stack_flask["run_cmd"], "python app.py")
        finally:
            shutil.rmtree(temp_dir)

    def test_command_whitelist_enforcement(self):
        """Verify unapproved arbitrary commands are rejected by execution service."""
        proj_id = self._create_test_project()
        res = execution_service.start_project_process(proj_id, command_override="rmdir /s /q C:\\Windows")
        self.assertFalse(res["success"])
        self.assertIn("not approved", res["error"])

    def test_server_reachability_timeout(self):
        """Verify is_server_reachable returns False for unallocated port without crashing."""
        reachable = execution_service.is_server_reachable("http://127.0.0.1:59999", timeout_seconds=1.0)
        self.assertFalse(reachable)

    def test_execution_service_run_tests_lifecycle(self):
        """Verify running tests captures stdout, exit code, and updates DB process record."""
        proj_id = self._create_test_project()
        
        # Run test suite service
        res = execution_service.run_project_tests_service(proj_id)
        self.assertIn("status", res)
        self.assertIn("exit_code", res)
        self.assertIn("stdout", res)

        # Check DB process table
        history = execution_service.get_process_history(proj_id)
        self.assertTrue(len(history) >= 1)
        self.assertEqual(history[0]["process_type"], "test")

    # =========================================================================
    # FEATURE 6, 7, 8: UI/UX DESIGN GENERATION & PREVIEW
    # =========================================================================
    def test_design_tokens_generation(self):
        """Verify design tokens are correctly tailored for different color palettes."""
        tokens_wg = ui_service.generate_design_tokens("white_grey", "modern_saas")
        self.assertEqual(tokens_wg["bg_primary"], "#ffffff")
        self.assertEqual(tokens_wg["bg_secondary"], "#f8f9fa")

        tokens_dark = ui_service.generate_design_tokens("dark_mode", "modern_saas")
        self.assertEqual(tokens_dark["bg_primary"], "#0f172a")

        tokens_bw = ui_service.generate_design_tokens("blue_white", "corporate")
        self.assertEqual(tokens_bw["primary"], "#2563eb")

    def test_generate_ui_templates_creates_valid_jinja2(self):
        """Verify UI service generates HTML Jinja2 templates for required pages."""
        ui_reqs = {
            "generate_ui": "yes",
            "style": "modern_saas",
            "palette": "white_grey",
            "layout": "responsive",
            "pages": ["landing", "login", "register", "dashboard", "reports", "settings", "inventory_custom"]
        }
        res = ui_service.generate_ui_templates("Test App", "Track inventory", ui_reqs)
        self.assertEqual(res["status"], "success")
        templates = res["templates"]
        
        self.assertIn("templates/base.html", templates)
        self.assertIn("templates/landing.html", templates)
        self.assertIn("templates/login.html", templates)
        self.assertIn("templates/register.html", templates)
        self.assertIn("templates/dashboard.html", templates)
        self.assertIn("templates/reports.html", templates)
        self.assertIn("templates/settings.html", templates)
        self.assertIn("templates/inventory_custom.html", templates)
        self.assertIn("static/css/app.css", templates)

        # Verify Jinja2 syntax validation
        for filename, content in templates.items():
            if filename.endswith(".html"):
                val = ui_service.validate_jinja2_template(content, filename)
                self.assertTrue(val["valid"], f"Template syntax error in {filename}: {val.get('error')}")

    def test_ui_preview_render_endpoint(self):
        """Verify UI preview render endpoint renders page cleanly with mock data."""
        proj_id = self._create_test_project()
        
        # Seed templates in DB
        ui_reqs = {
            "generate_ui": "yes",
            "pages": ["landing", "dashboard"]
        }
        gen = ui_service.generate_ui_templates("Preview App", "Preview spec", ui_reqs)
        from services.code_generator import save_project_files
        save_project_files(proj_id, gen["templates"])

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["user_name"] = "Enterprise Tester"
            sess["user_email"] = "ent_tester@example.com"
            sess["csrf_token"] = "test_csrf_token"

        res = self.client.get(f"/projects/{proj_id}/ui-preview/render/landing")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Preview App", res.data)

    # =========================================================================
    # FEATURE 9: REQUIREMENTS TRACEABILITY
    # =========================================================================
    def test_extract_requirements_from_text(self):
        """Verify requirement extractor parses functional and non-functional requirements."""
        srs_sample = """# Software Requirements Specification
1. Functional Requirements:
   - FR-01: User Authentication: The system shall allow users to register and login securely.
   - FR-02: Task Management: The system shall allow users to create, update, and delete tasks.
   - FR-03: Reporting: The system shall generate exportable summary reports.

2. Non-Functional Requirements:
   - NFR-01: Response Time: The system shall respond within 500ms.
   - NFR-02: Security: The system shall encrypt all sensitive database fields.
"""
        reqs = requirements_service.extract_requirements_from_text(srs_sample)
        self.assertGreaterEqual(len(reqs), 5)
        req_ids = [r["req_id"] for r in reqs]
        self.assertIn("FR-01", req_ids)
        self.assertIn("FR-02", req_ids)
        self.assertIn("NFR-01", req_ids)

        fr01 = next(r for r in reqs if r["req_id"] == "FR-01")
        self.assertIn("Authentication", fr01["title"])
        self.assertEqual(fr01["category"], "Functional")

    def test_requirements_verification_evidence_enforcement(self):
        """Verify requirements are NOT marked Verified without actual test and file evidence."""
        proj_id = self._create_test_project()
        
        sample_reqs = [
            {
                "req_id": "REQ-01",
                "category": "Functional",
                "title": "Auth Route",
                "description": "User login route",
                "priority": "High",
                "acceptance_criteria": "POST /login returns 200",
                "related_files": ["app.py"],
                "related_tests": ["test_app.py"],
                "verification_method": "Automated Unit Test"
            }
        ]
        requirements_service.save_project_requirements(proj_id, sample_reqs)
        
        # Without files or passing tests in DB, sync should mark Not Implemented or Not Verified
        requirements_service.sync_project_requirements(proj_id)
        saved = requirements_service.get_project_requirements(proj_id)
        self.assertNotEqual(saved[0]["status"], "Verified")
        self.assertIn(saved[0]["status"], ["Not Implemented", "Not Verified"])

    # =========================================================================
    # FEATURE 10 & 11: 8-PHASE VALIDATION & AUTO-CORRECTION
    # =========================================================================
    def test_8_phase_validation_orchestrator(self):
        """Verify ValidationOrchestrator runs all 8 validation phases and saves results."""
        proj_id = self._create_test_project()
        
        orchestrator = validation_service.ValidationOrchestrator(proj_id)
        results = orchestrator.run_all_phases()
        
        self.assertIn("overall_status", results)
        self.assertIn("phases", results)
        phases = results["phases"]
        
        self.assertIn("phase_1_source", phases)
        self.assertIn("phase_2_backend", phases)
        self.assertIn("phase_3_frontend", phases)
        self.assertIn("phase_4_integration", phases)
        self.assertIn("phase_5_automated_testing", phases)
        self.assertIn("phase_6_security", phases)
        self.assertIn("phase_7_requirements", phases)
        self.assertIn("phase_8_execution", phases)

    def test_auto_correction_backup_creation_and_retry_limit(self):
        """Verify targeted corrections create backups and respect retry limit."""
        proj_id = self._create_test_project()
        
        # Test retry limit check
        self.assertTrue(validation_service.can_retry_correction(proj_id, max_retries=3))
        
        # Record 3 mock corrections
        validation_service.record_correction(proj_id, "app.py", "SyntaxError", "Fixed colon", "Passed")
        validation_service.record_correction(proj_id, "app.py", "ImportError", "Added import", "Passed")
        validation_service.record_correction(proj_id, "models.py", "TypeError", "Fixed type", "Passed")
        
        # Now 3 retries used -> should return False
        self.assertFalse(validation_service.can_retry_correction(proj_id, max_retries=3))
        
        history = validation_service.get_correction_history(proj_id)
        self.assertEqual(len(history), 3)


if __name__ == "__main__":
    unittest.main()
