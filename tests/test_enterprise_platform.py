import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import json
import tempfile
import io
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from db import init_db, get_standalone_db
import services.project_service as project_service
import services.architecture_generator as architecture_generator
import services.documentation_service as documentation_service
import services.documentation_template_service as documentation_template_service
import services.documentation_validation_service as documentation_validation_service


class EnterprisePlatformTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        init_db()

    def setUp(self):
        self.client = app.test_client()
        conn = get_standalone_db()
        with conn:
            conn.execute("DELETE FROM projects WHERE name LIKE 'PlatformTest%'")
            conn.execute("DELETE FROM users WHERE email = 'platform_test@example.com'")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users (full_name, email, password_hash)
                VALUES ('Platform Tester', 'platform_test@example.com', 'dummy_hash')
            """)
            self.user_id = cursor.execute("SELECT id FROM users WHERE email='platform_test@example.com'").fetchone()["id"]
        conn.close()

        # Login session
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["user_name"] = "Platform Tester"
            sess["user_email"] = "platform_test@example.com"
            sess["user_role"] = "Developer"
            sess["csrf_token"] = "test_csrf_token_1234"

    def _create_test_project(self, name="PlatformTest AI", desc="AI Autonomous Healthcare Platform"):
        return project_service.create_project(
            user_id=self.user_id,
            name=name,
            description=desc,
            app_type="Web App",
            language="Python Flask",
            tech_preferences="SQLite, HTML5, CSS3, Gemini"
        )

    # =========================================================================
    # 1. SIDEBAR & NAVIGATION TESTS
    # =========================================================================

    def test_sidebar_mandatory_pages_open_successfully(self):
        """All 8 mandatory sidebar pages must return HTTP 200."""
        routes = [
            "/dashboard",
            "/chat",
            "/projects/new",
            "/projects",
            "/architecture",
            "/documentation",
            "/history",
            "/settings"
        ]
        for route in routes:
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200, f"Route {route} failed with {resp.status_code}")
            html = resp.get_data(as_text=True)
            self.assertIn("DevGuardian AI", html)
            # Ensure sidebar items are present
            self.assertIn("Architecture", html)
            self.assertIn("Documentation", html)
            self.assertIn("Project History", html)
            self.assertIn("AI Chat", html)

    def test_generate_alias_redirects_to_new_project(self):
        """Route /generate must redirect to /projects/new."""
        resp = self.client.get("/generate")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.location.endswith("/projects/new"))

    # =========================================================================
    # 2. AI CHAT COPILOT TESTS
    # =========================================================================

    def test_chat_page_and_send_message(self):
        """Test sending a text message in chat and receiving an AI response."""
        proj_id = self._create_test_project()
        
        # Send a message
        with patch("services.ai_service.call_gemini", return_value=(True, "I have analyzed your healthcare platform request.")):
            resp = self.client.post("/chat/send", data={
                "csrf_token": "test_csrf_token_1234",
                "project_id": proj_id,
                "message": "Build a healthcare management application."
            }, headers={"X-Requested-With": "XMLHttpRequest"})
            
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertIn("assistant_message", data)
            self.assertIn("healthcare", data["assistant_message"]["content"].lower())

        # Verify chat message is stored in database
        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chat_messages WHERE user_id = ?", (self.user_id,))
        messages = cursor.fetchall()
        conn.close()
        self.assertGreaterEqual(len(messages), 2)  # User message + Assistant message

    def test_chat_multimodal_image_upload(self):
        """Test uploading an image in chat triggers multimodal analysis."""
        from PIL import Image
        img_io = io.BytesIO()
        img = Image.new("RGB", (100, 100), color=(73, 109, 137))
        img.save(img_io, format="PNG")
        img_io.seek(0)

        with patch("services.ai_service.call_gemini_multimodal", return_value=(True, "Multimodal Analysis: Detected 3 microservices and 1 database.")):
            resp = self.client.post("/chat/send", data={
                "csrf_token": "test_csrf_token_1234",
                "message": "Analyze this architecture image.",
                "image": (img_io, "test_arch.png")
            }, headers={"X-Requested-With": "XMLHttpRequest"})

            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertIn("Multimodal Analysis", data["assistant_message"]["content"])
            self.assertIsNotNone(data["user_message"]["image_path"])

    def test_chat_clear_history(self):
        """Test clearing chat history for user."""
        proj_id = self._create_test_project()
        # Seed message
        conn = get_standalone_db()
        with conn:
            conn.execute("INSERT INTO chat_messages (user_id, project_id, role, content) VALUES (?, ?, 'user', 'Hello')", (self.user_id, proj_id))
        conn.close()

        resp = self.client.post("/chat/clear", data={
            "csrf_token": "test_csrf_token_1234",
            "project_id": proj_id
        }, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 200)

        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM chat_messages WHERE user_id = ? AND project_id = ?", (self.user_id, proj_id))
        cnt = cursor.fetchone()["cnt"]
        conn.close()
        self.assertEqual(cnt, 0)

    # =========================================================================
    # 3. ARCHITECTURE GENERATOR TESTS
    # =========================================================================

    def test_architecture_generation_and_exports(self):
        """Test architecture diagram generation, SVG, PNG, and source JSON."""
        proj_id = self._create_test_project("PlatformTest FinTech", "Six-agent financial fraud detection")

        # Generate architecture via POST
        resp = self.client.post(f"/architecture/{proj_id}/generate", data={
            "csrf_token": "test_csrf_token_1234",
            "diagram_type": "system"
        }, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertGreater(data["data"]["components_count"], 0)
        self.assertTrue(os.path.exists(data["data"]["png_path"]))
        self.assertTrue(os.path.exists(data["data"]["svg_path"]))

        # Test PNG export route
        png_resp = self.client.get(f"/architecture/{proj_id}/export/png")
        self.assertEqual(png_resp.status_code, 200)
        self.assertEqual(png_resp.content_type, "image/png")
        self.assertGreater(len(png_resp.data), 1000)

        # Test SVG export route
        svg_resp = self.client.get(f"/architecture/{proj_id}/export/svg")
        self.assertEqual(svg_resp.status_code, 200)
        self.assertEqual(svg_resp.content_type, "image/svg+xml; charset=utf-8")
        self.assertIn(b"<svg", svg_resp.data)

        # Test source JSON endpoint
        src_resp = self.client.get(f"/architecture/{proj_id}/source")
        self.assertEqual(src_resp.status_code, 200)
        src_data = src_resp.get_json()
        self.assertIn("mermaid_source", src_data)
        self.assertIn("components", src_data)

    # =========================================================================
    # 4. STRICT MASTER DOCUMENTATION GENERATION TESTS
    # =========================================================================

    def test_master_template_status_and_logo_preservation(self):
        """Verify master template CaptionAI_Documentation.docx is detected with logos."""
        status = documentation_template_service.check_master_template_status()
        self.assertTrue(status["available"])
        self.assertEqual(status["smartbridge_logo"], "preserved")
        self.assertEqual(status["skillwallet_logo"], "preserved")

    def test_documentation_generation_and_downloads(self):
        """Test documentation generation, DOCX creation, PDF creation, and download routes."""
        proj_id = self._create_test_project("PlatformTest MedCare", "Full HIPAA medical records app")

        # Generate documentation
        gen_resp = self.client.post(
            f"/documentation/{proj_id}/generate",
            data={"csrf_token": "test_csrf_token_1234"},
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(gen_resp.status_code, 200)
        res_data = gen_resp.get_json()
        self.assertTrue(res_data["success"])
        self.assertTrue(os.path.exists(res_data["docx_path"]))
        self.assertTrue(os.path.exists(res_data["pdf_path"]))
        self.assertGreater(res_data["docx_size"], 50000)
        self.assertGreater(res_data["pdf_size"], 10000)

        # Test DOCX download route
        docx_resp = self.client.get(f"/documentation/{proj_id}/download/docx")
        self.assertEqual(docx_resp.status_code, 200)
        self.assertEqual(docx_resp.content_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertGreater(len(docx_resp.data), 50000)

        # Test PDF download route
        pdf_resp = self.client.get(f"/documentation/{proj_id}/download/pdf")
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertEqual(pdf_resp.content_type, "application/pdf")
        self.assertTrue(pdf_resp.data.startswith(b"%PDF"))

        # Test Validation Route
        val_resp = self.client.post(f"/documentation/{proj_id}/validate", data={"csrf_token": "test_csrf_token_1234"}, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(val_resp.status_code, 200)
        val_data = val_resp.get_json()
        self.assertTrue(val_data["valid"])
        self.assertEqual(val_data["validation_score"], 100)
        self.assertTrue(val_data["checks_dict"]["SmartBridge & SkillWallet Logos Preserved"])
        self.assertTrue(val_data["checks_dict"]["Architecture Diagram Embedded"])
        self.assertTrue(val_data["checks_dict"]["Required Document Sections Present"])
        self.assertTrue(val_data["checks_dict"]["PDF Export Generated & Valid"])

    # =========================================================================
    # 5. PROJECT HISTORY & ACTIVITY AUDIT TRAIL TESTS
    # =========================================================================

    def test_history_page_and_activity_logging(self):
        """Test logging activity events and rendering /history."""
        proj_id = self._create_test_project("PlatformTest Logs", "Test project for logging")

        project_service.log_project_activity(
            proj_id, "test_action", "Automated Test Suite Completed",
            "Executed 25 unit tests with 100% pass rate", "success"
        )

        resp = self.client.get(f"/history?project_id={proj_id}")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Automated Test Suite Completed", html)
        self.assertIn("Executed 25 unit tests", html)


if __name__ == "__main__":
    unittest.main()
