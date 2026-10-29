"""
DevGuardian AI — Documentation Assistant Chatbot Test Suite
Validates the conversational documentation assistant, real-time AST project analyzer,
CaptionAI master template generation pipeline, twin DOCX/PDF deliverables,
and persistent SQLite conversation sessions.
"""

import os
import io
import sys
import json
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from db import init_db, get_standalone_db
import services.documentation_chat_service as chat_service
import services.documentation_project_analyzer as project_analyzer
import services.documentation_service as documentation_service
import services.documentation_template_service as template_service
import services.documentation_validation_service as validation_service


class DocumentationAssistantTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        init_db()

        conn = get_standalone_db()
        cursor = conn.cursor()

        # Retrieve test project IDs
        cw = cursor.execute("SELECT id, user_id FROM projects WHERE name = 'ClaimWise AI'").fetchone()
        cls.claimwise_id = cw["id"] if cw else None
        cls.owner_id = cw["user_id"] if cw else 19

        hs = cursor.execute("SELECT id FROM projects WHERE name = 'HireSmart AI'").fetchone()
        cls.hiresmart_id = hs["id"] if hs else None

        # Ensure user exists for authentication
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, full_name, email, password_hash, role)
            VALUES (?, 'Doc Assistant Tester', 'assistant_tester@example.com', 'dummy_hash', 'Developer')
        """, (cls.owner_id,))
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.owner_id
            sess["user_name"] = "Doc Assistant Tester"
            sess["user_email"] = "assistant_tester@example.com"
            sess["user_role"] = "Developer"
            sess["csrf_token"] = "test_csrf_token_doc_assistant"

    # =========================================================================
    # 1. ROUTE ACCESS & AUTHENTICATION
    # =========================================================================

    def test_01_documentation_assistant_page_authenticated(self):
        """GET /documentation-assistant should return 200 with complete UI elements."""
        res = self.client.get(f"/documentation-assistant?project_id={self.claimwise_id}")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Documentation Assistant", html)
        self.assertIn("CaptionAI Master Standard", html)
        self.assertIn("SmartBridge Logo", html)
        self.assertIn("SkillWallet Logo", html)
        self.assertIn("Generate Documentation", html)
        self.assertIn("docChatInput", html)
        self.assertIn("btnSendChat", html)

    def test_02_documentation_assistant_page_unauthenticated_redirects(self):
        """Unauthenticated user accessing /documentation-assistant must be redirected to login."""
        anon_client = app.test_client()
        res = anon_client.get("/documentation-assistant")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    # =========================================================================
    # 2. REAL PROJECT SOURCE CODE AST ANALYZER
    # =========================================================================

    def test_03_project_analyzer_real_ast_extraction(self):
        """Analyzer must extract actual routes, models, agents, and test assertions from ClaimWise AI workspace."""
        if not self.claimwise_id:
            self.skipTest("ClaimWise AI project not present in database.")

        analysis = project_analyzer.analyze_project_source_code(self.claimwise_id)
        self.assertIsNotNone(analysis)
        self.assertEqual(analysis["project_name"], "ClaimWise AI")
        self.assertIn("Insurance", analysis["domain_summary"])
        self.assertGreater(len(analysis["routes"]), 5, "Must discover real routes from app.py")
        
        # Check actual ClaimWise routes
        routes = analysis["routes"]
        self.assertTrue(any("/claims" in r or "/dashboard" in r or "/login" in r for r in routes),
                        f"Expected core ClaimWise routes, got: {routes[:5]}")

        # Check discovered database models / tables
        self.assertGreaterEqual(len(analysis["models"]), 1, "Must discover database models")

        # Check detected autonomous agents
        agents = analysis["detected_agents"]
        self.assertTrue(any("Claim" in a or "Fraud" in a for a in agents),
                        f"Expected insurance/claim domain agents, got: {agents}")

    # =========================================================================
    # 3. CONVERSATIONAL INTENT: SOURCE INSPECTION
    # =========================================================================

    def test_04_chat_intent_analyze_source_code(self):
        """User asking to analyze or inspect source code must receive detailed project facts."""
        if not self.claimwise_id:
            self.skipTest("ClaimWise AI project not present in database.")

        res = self.client.post(
            "/documentation-assistant/chat",
            data={
                "project_id": self.claimwise_id,
                "message": "Inspect the source code, routes, and database schema",
                "csrf_token": "test_csrf_token_doc_assistant"
            },
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": "test_csrf_token_doc_assistant"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"), f"Chat response failed: {data}")
        self.assertIn("assistant_message", data)
        asst = data["assistant_message"]
        self.assertEqual(asst["metadata"]["action"], "analyzed")
        self.assertIn("Discovered Routes", asst["content"])
        self.assertIn("ClaimWise AI", asst["content"])

    # =========================================================================
    # 4. CONVERSATIONAL INTENT: FULL DOCUMENTATION GENERATION
    # =========================================================================

    def test_05_chat_intent_generate_full_documentation(self):
        """Conversational instruction to generate documentation must execute pipeline and produce DOCX/PDF."""
        if not self.claimwise_id:
            self.skipTest("ClaimWise AI project not present in database.")

        res = self.client.post(
            "/documentation-assistant/chat",
            data={
                "project_id": self.claimwise_id,
                "message": "Generate complete documentation for ClaimWise AI",
                "csrf_token": "test_csrf_token_doc_assistant"
            },
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": "test_csrf_token_doc_assistant"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"), f"Generation failed: {data}")
        asst = data["assistant_message"]
        self.assertEqual(asst["metadata"]["action"], "generated")
        self.assertEqual(asst["metadata"]["validation_score"], 100)
        self.assertTrue(os.path.exists(asst["metadata"]["docx_path"]))
        self.assertTrue(os.path.exists(asst["metadata"]["pdf_path"]))
        self.assertGreater(asst["metadata"]["docx_size"], 100000)
        self.assertGreater(asst["metadata"]["pdf_size"], 100000)

    # =========================================================================
    # 5. ONE-CLICK GENERATE ACTION & PREVIEW ENDPOINTS
    # =========================================================================

    def test_06_one_click_generation_action(self):
        """POST /documentation-assistant/generate triggers pipeline and returns JSON metadata."""
        if not self.claimwise_id:
            self.skipTest("ClaimWise AI project not present in database.")

        res = self.client.post(
            "/documentation-assistant/generate",
            data={
                "project_id": self.claimwise_id,
                "csrf_token": "test_csrf_token_doc_assistant"
            },
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": "test_csrf_token_doc_assistant"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

    def test_07_download_and_stream_endpoints(self):
        """Verify DOCX download, PDF download, and inline PDF stream endpoints."""
        if not self.claimwise_id:
            self.skipTest("ClaimWise AI project not present in database.")

        # PDF inline stream
        stream_res = self.client.get(f"/documentation/{self.claimwise_id}/stream/pdf")
        self.assertEqual(stream_res.status_code, 200)
        self.assertEqual(stream_res.mimetype, "application/pdf")
        self.assertIn("inline", stream_res.headers.get("Content-Disposition", ""))

        # PDF download
        pdf_res = self.client.get(f"/documentation/{self.claimwise_id}/download/pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.mimetype, "application/pdf")

        # DOCX download
        docx_res = self.client.get(f"/documentation/{self.claimwise_id}/download/docx")
        self.assertEqual(docx_res.status_code, 200)
        self.assertIn("wordprocessingml", docx_res.mimetype)

    # =========================================================================
    # 6. SESSIONS, PERSISTENCE & CLEARING
    # =========================================================================

    def test_08_conversation_session_lifecycle(self):
        """Test creating a new session, storing messages, and clearing chat history."""
        if not self.claimwise_id:
            self.skipTest("ClaimWise AI project not present in database.")

        # Create new session
        res = self.client.post(
            "/documentation-assistant/conversation/new",
            data={
                "project_id": self.claimwise_id,
                "csrf_token": "test_csrf_token_doc_assistant"
            },
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": "test_csrf_token_doc_assistant"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        conv_id = data.get("conversation_id")
        self.assertIsNotNone(conv_id)

        # Clear session messages
        clear_res = self.client.post(
            f"/documentation-assistant/conversation/{conv_id}/clear",
            data={"csrf_token": "test_csrf_token_doc_assistant"},
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": "test_csrf_token_doc_assistant"}
        )
        self.assertEqual(clear_res.status_code, 200)
        clear_data = clear_res.get_json()
        self.assertTrue(clear_data.get("success"))

        messages = chat_service.get_conversation_messages(conv_id)
        self.assertEqual(len(messages), 0, "Messages should be empty after clear")

    # =========================================================================
    # 7. FILE ATTACHMENT HANDLING
    # =========================================================================

    def test_09_chat_with_file_attachment(self):
        """User attaching a supporting project file should have it saved and referenced in the conversation."""
        if not self.claimwise_id:
            self.skipTest("ClaimWise AI project not present in database.")

        test_content = b"# Custom insurance policy configuration\npolicy_limit = 500000\ndeductible = 1000\n"
        attachment = (io.BytesIO(test_content), "insurance_policy.py")

        res = self.client.post(
            "/documentation-assistant/chat",
            data={
                "project_id": self.claimwise_id,
                "message": "Here is our updated insurance policy configuration. Please inspect it.",
                "attachment": attachment,
                "csrf_token": "test_csrf_token_doc_assistant"
            },
            headers={"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": "test_csrf_token_doc_assistant"},
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        user_msg = data.get("user_message")
        self.assertEqual(user_msg.get("attachment_name"), "insurance_policy.py")
        self.assertIsNotNone(user_msg.get("attachment_path"))

    # =========================================================================
    # 8. MULTI-PROJECT ISOLATION (ZERO CROSS-PROJECT LEAKAGE)
    # =========================================================================

    def test_10_multi_project_isolation(self):
        """HireSmart AI documentation must contain recruiting/HR domain content, not insurance or CaptionAI data."""
        if not self.hiresmart_id:
            self.skipTest("HireSmart AI project not present in database.")

        hs_analysis = project_analyzer.analyze_project_source_code(self.hiresmart_id)
        self.assertEqual(hs_analysis["project_name"], "HireSmart AI")
        self.assertTrue(any(k in hs_analysis["domain_summary"] for k in ["Talent", "Resume", "Candidate", "Hiring"]))

        # Discovered routes should belong to HireSmart AI
        self.assertTrue(any("/candidate" in r or "/resume" in r or "/dashboard" in r or "/login" in r for r in hs_analysis["routes"]))

        # Must not have claimwise routes
        self.assertFalse(any("/claim" in r for r in hs_analysis["routes"]))


if __name__ == "__main__":
    unittest.main()
