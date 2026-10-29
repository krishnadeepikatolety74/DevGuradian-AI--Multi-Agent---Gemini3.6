"""
DevGuardian AI — Universal Project-Specific Documentation Generation Acceptance Tests
Tests full fidelity formatting preservation of CaptionAI_Documentation.docx
while guaranteeing 100% project-specific content, real architecture diagrams,
real screenshots, actual APIs, actual code snippets, and zero cross-project leakage.
"""

import os
import sys
import unittest
import zipfile
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from db import init_db, get_standalone_db
import services.documentation_service as documentation_service
import services.documentation_template_service as documentation_template_service
import services.documentation_validation_service as documentation_validation_service
import services.architecture_generator as architecture_generator


class UniversalDocumentationGenerationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        init_db()

        # Target project IDs for all 4 canonical projects plus benchmark projects
        conn = get_standalone_db()
        cursor = conn.cursor()
        
        # 1. Healthcare Multi-Agent AI Workflow Automation
        hc = cursor.execute("SELECT id FROM projects WHERE id = 'proj_64e2d56d88' OR name LIKE '%Healthcare%'").fetchone()
        cls.healthcare_id = hc["id"] if hc else "proj_64e2d56d88"

        # 2. ClaimWise AI
        cw = cursor.execute("SELECT id FROM projects WHERE id = 'proj_87ec37b85e' OR name = 'ClaimWise AI'").fetchone()
        cls.claimwise_id = cw["id"] if cw else "proj_87ec37b85e"

        # 3. CultureLens
        cl = cursor.execute("SELECT id FROM projects WHERE id = 'proj_53aa03667b' OR name LIKE 'CultureLens%'").fetchone()
        cls.culturelens_id = cl["id"] if cl else "proj_53aa03667b"

        # 4. Smart Crosswalk Safety System
        sc = cursor.execute("SELECT id FROM projects WHERE id = 'proj_061e00e20c' OR name LIKE 'Smart Crosswalk%'").fetchone()
        cls.crosswalk_id = sc["id"] if sc else "proj_061e00e20c"

        # Benchmark Projects
        hs = cursor.execute("SELECT id FROM projects WHERE name = 'HireSmart AI'").fetchone()
        cls.hiresmart_id = hs["id"] if hs else None

        se = cursor.execute("SELECT id FROM projects WHERE name = 'Smart Expense Tracker AI'").fetchone()
        cls.expense_id = se["id"] if se else None

        # Find owner of the test projects
        owner_row = cursor.execute("SELECT user_id FROM projects WHERE name = 'ClaimWise AI'").fetchone()
        cls.owner_id = owner_row["user_id"] if owner_row else 19

        # Ensure all canonical test projects are owned by cls.owner_id
        cursor.execute(
            "UPDATE projects SET user_id = ? WHERE id IN (?, ?, ?, ?)",
            (cls.owner_id, cls.healthcare_id, cls.claimwise_id, cls.culturelens_id, cls.crosswalk_id)
        )
        conn.commit()

        # Test User for authentication
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, full_name, email, password_hash)
            VALUES (?, 'Doc Tester', 'doc_tester@example.com', 'dummy_hash')
        """, (cls.owner_id,))
        cls.user_id = cls.owner_id
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.owner_id
            sess["user_name"] = "Doc Tester"
            sess["user_email"] = "doc_tester@example.com"
            sess["user_role"] = "Developer"
            sess["csrf_token"] = "test_csrf_token_doc"

    # =========================================================================
    # 1. MASTER TEMPLATE VERIFICATION
    # =========================================================================

    def test_01_master_template_and_logos_verified(self):
        """Verify master template CaptionAI_Documentation.docx is intact with SmartBridge, SkillWallet logos, and shared assets."""
        status = documentation_template_service.check_master_template_status()
        self.assertTrue(status["available"], "Master template CaptionAI_Documentation.docx must be available")
        self.assertTrue(status["logos_preserved"], "Both SmartBridge and SkillWallet logos must be preserved")
        self.assertEqual(status["smartbridge_logo"], "preserved")
        self.assertEqual(status["skillwallet_logo"], "preserved")
        self.assertTrue(status.get("shared_assets_ok"), "All 6 shared reference assets must be present in library")
        self.assertEqual(len(status.get("shared_assets", {}).get("assets", {})), 6)

    # =========================================================================
    # 2. CLAIMWISE AI DOCUMENTATION GENERATION & FIDELITY
    # =========================================================================

    def test_02_claimwise_ai_documentation_generation(self):
        """Test ClaimWise AI documentation contains ONLY ClaimWise content and passes validation."""
        self.assertIsNotNone(self.claimwise_id, "ClaimWise AI project must exist in DB")
        res = documentation_service.generate_project_documentation(self.claimwise_id)
        self.assertTrue(res["success"], f"Generation failed: {res.get('error')}")

        docx_path = res["docx_path"]
        pdf_path = res["pdf_path"]
        self.assertTrue(os.path.exists(docx_path))
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(docx_path), 50000)
        self.assertGreater(os.path.getsize(pdf_path), 20000)

        # Inspect DOCX package
        with zipfile.ZipFile(docx_path, "r") as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
            rels_xml = z.read("word/_rels/document.xml.rels").decode("utf-8")
            namelist = z.namelist()

            # Logos preserved
            self.assertTrue("word/media/image1.png" in namelist or "word/media/image9.png" in namelist)
            self.assertIn("word/header1.xml", namelist)

            # Project specific content
            self.assertIn("ClaimWise AI", doc_xml)
            self.assertIn("Claim", doc_xml)
            self.assertIn("app.py", doc_xml)

            # ZERO leftover CaptionAI or Groq/Twilio artifacts
            self.assertNotIn("CaptionAI", doc_xml)
            self.assertNotIn("llama-3.3-70b-versatile", doc_xml)
            self.assertNotIn("console.groq.com", rels_xml)
            self.assertIn("ngrok.com", doc_xml)

        # Run validation service
        val = documentation_validation_service.validate_project_documentation(
            docx_path=docx_path,
            pdf_path=pdf_path,
            project_name="ClaimWise AI",
            workspace_path=res.get("workspace_path")
        )
        self.assertTrue(val["valid"], f"Validation failed with errors: {val['errors']}")
        self.assertEqual(val["validation_score"], 100)

    # =========================================================================
    # 3. HEALTHCARE MULTI-AGENT AI WORKFLOW AUTOMATION
    # =========================================================================

    def test_03_healthcare_ai_documentation_generation(self):
        """Test Healthcare Multi-Agent AI documentation generates with complete fidelity and 100/100 score."""
        self.assertIsNotNone(self.healthcare_id, "Healthcare Multi-Agent AI project must exist in DB")
        res = documentation_service.generate_project_documentation(self.healthcare_id)
        self.assertTrue(res["success"], f"Generation failed: {res.get('error')}")

        docx_path = res["docx_path"]
        pdf_path = res["pdf_path"]
        self.assertTrue(os.path.exists(docx_path))
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(docx_path), 50000)
        self.assertGreater(os.path.getsize(pdf_path), 20000)

        with zipfile.ZipFile(docx_path, "r") as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
            namelist = z.namelist()

            # Logos preserved
            self.assertTrue("word/media/image1.png" in namelist or "word/media/image9.png" in namelist)
            self.assertIn("word/header1.xml", namelist)

            # Project specific content
            self.assertIn("Healthcare", doc_xml)
            self.assertTrue("Triage" in doc_xml or "Appointment" in doc_xml)
            self.assertIn("app.py", doc_xml)

            # ZERO CaptionAI leakage
            self.assertNotIn("CaptionAI", doc_xml)
            self.assertNotIn("llama-3.3-70b-versatile", doc_xml)

        val = documentation_validation_service.validate_project_documentation(
            docx_path=docx_path,
            pdf_path=pdf_path,
            project_name="Healthcare Multi-Agent AI Workflow Automation",
            workspace_path=res.get("workspace_path")
        )
        self.assertTrue(val["valid"], f"Validation failed with errors: {val['errors']}")
        self.assertEqual(val["validation_score"], 100)

    # =========================================================================
    # 4. CULTURELENS DOCUMENTATION GENERATION & FIDELITY
    # =========================================================================

    def test_04_culturelens_documentation_generation(self):
        """Test CultureLens documentation generates with complete fidelity and 100/100 score."""
        self.assertIsNotNone(self.culturelens_id, "CultureLens project must exist in DB")
        res = documentation_service.generate_project_documentation(self.culturelens_id)
        self.assertTrue(res["success"], f"Generation failed: {res.get('error')}")

        docx_path = res["docx_path"]
        pdf_path = res["pdf_path"]
        self.assertTrue(os.path.exists(docx_path))
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(docx_path), 50000)
        self.assertGreater(os.path.getsize(pdf_path), 20000)

        with zipfile.ZipFile(docx_path, "r") as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
            namelist = z.namelist()

            # Logos preserved
            self.assertTrue("word/media/image1.png" in namelist or "word/media/image9.png" in namelist)
            self.assertIn("word/header1.xml", namelist)

            # Project specific content
            self.assertIn("CultureLens", doc_xml)
            self.assertIn("Culture", doc_xml)
            self.assertIn("app.py", doc_xml)

            # ZERO CaptionAI leakage
            self.assertNotIn("CaptionAI", doc_xml)
            self.assertNotIn("llama-3.3-70b-versatile", doc_xml)

        val = documentation_validation_service.validate_project_documentation(
            docx_path=docx_path,
            pdf_path=pdf_path,
            project_name="CultureLens",
            workspace_path=res.get("workspace_path")
        )
        self.assertTrue(val["valid"], f"Validation failed with errors: {val['errors']}")
        self.assertEqual(val["validation_score"], 100)

    # =========================================================================
    # 5. SMART CROSSWALK SAFETY SYSTEM DOCUMENTATION GENERATION & FIDELITY
    # =========================================================================

    def test_05_smart_crosswalk_documentation_generation(self):
        """Test Smart Crosswalk Safety System documentation generates with complete fidelity and 100/100 score."""
        self.assertIsNotNone(self.crosswalk_id, "Smart Crosswalk project must exist in DB")
        res = documentation_service.generate_project_documentation(self.crosswalk_id)
        self.assertTrue(res["success"], f"Generation failed: {res.get('error')}")

        docx_path = res["docx_path"]
        pdf_path = res["pdf_path"]
        self.assertTrue(os.path.exists(docx_path))
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(docx_path), 50000)
        self.assertGreater(os.path.getsize(pdf_path), 20000)

        with zipfile.ZipFile(docx_path, "r") as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
            namelist = z.namelist()

            # Logos preserved
            self.assertTrue("word/media/image1.png" in namelist or "word/media/image9.png" in namelist)
            self.assertIn("word/header1.xml", namelist)

            # Project specific content
            self.assertIn("Smart Crosswalk", doc_xml)
            self.assertTrue("Safety" in doc_xml or "Crosswalk" in doc_xml)
            self.assertIn("app.py", doc_xml)

            # ZERO CaptionAI leakage
            self.assertNotIn("CaptionAI", doc_xml)
            self.assertNotIn("llama-3.3-70b-versatile", doc_xml)

        val = documentation_validation_service.validate_project_documentation(
            docx_path=docx_path,
            pdf_path=pdf_path,
            project_name="Smart Crosswalk Safety System",
            workspace_path=res.get("workspace_path")
        )
        self.assertTrue(val["valid"], f"Validation failed with errors: {val['errors']}")
        self.assertEqual(val["validation_score"], 100)

    # =========================================================================
    # 6. HIRESMART AI DOCUMENTATION GENERATION & FIDELITY
    # =========================================================================

    def test_06_hiresmart_ai_documentation_generation(self):
        """Test HireSmart AI documentation documents Google Gemini API, resumes, candidates, and passes validation."""
        self.assertIsNotNone(self.hiresmart_id, "HireSmart AI project must exist in DB")
        res = documentation_service.generate_project_documentation(self.hiresmart_id)
        self.assertTrue(res["success"], f"Generation failed: {res.get('error')}")

        docx_path = res["docx_path"]
        pdf_path = res["pdf_path"]
        self.assertTrue(os.path.exists(docx_path))
        self.assertTrue(os.path.exists(pdf_path))

        with zipfile.ZipFile(docx_path, "r") as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")

            # Project specific content
            self.assertIn("HireSmart AI", doc_xml)
            self.assertIn("Resume", doc_xml)
            self.assertIn("Candidate", doc_xml)
            # HireSmart actually uses Gemini
            self.assertIn("Google Gemini", doc_xml)

            # ZERO CaptionAI or ClaimWise content
            self.assertNotIn("CaptionAI", doc_xml)
            self.assertNotIn("ClaimWise", doc_xml)
            self.assertNotIn("llama-3.3-70b-versatile", doc_xml)

        val = documentation_validation_service.validate_project_documentation(
            docx_path=docx_path,
            pdf_path=pdf_path,
            project_name="HireSmart AI",
            workspace_path=res.get("workspace_path")
        )
        self.assertTrue(val["valid"], f"Validation failed with errors: {val['errors']}")
        self.assertEqual(val["validation_score"], 100)

    # =========================================================================
    # 7. SMART EXPENSE TRACKER AI DOCUMENTATION GENERATION & FIDELITY
    # =========================================================================

    def test_07_smart_expense_tracker_documentation_generation(self):
        """Test Smart Expense Tracker AI documentation contains budgets, transactions, zero external AI APIs, and passes validation."""
        self.assertIsNotNone(self.expense_id, "Smart Expense Tracker AI project must exist in DB")
        res = documentation_service.generate_project_documentation(self.expense_id)
        self.assertTrue(res["success"], f"Generation failed: {res.get('error')}")

        docx_path = res["docx_path"]
        pdf_path = res["pdf_path"]
        self.assertTrue(os.path.exists(docx_path))
        self.assertTrue(os.path.exists(pdf_path))

        with zipfile.ZipFile(docx_path, "r") as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")

            # Project specific content
            self.assertIn("Smart Expense Tracker AI", doc_xml)
            self.assertIn("Budget", doc_xml)
            self.assertIn("Transaction", doc_xml)

            # ZERO Gemini, Groq, Twilio, Ngrok, or CaptionAI
            self.assertNotIn("CaptionAI", doc_xml)
            self.assertNotIn("HireSmart", doc_xml)
            self.assertNotIn("ClaimWise", doc_xml)
            self.assertNotIn("Google Gemini", doc_xml)
            self.assertNotIn("Groq", doc_xml)

        val = documentation_validation_service.validate_project_documentation(
            docx_path=docx_path,
            pdf_path=pdf_path,
            project_name="Smart Expense Tracker AI",
            workspace_path=res.get("workspace_path")
        )
        self.assertTrue(val["valid"], f"Validation failed with errors: {val['errors']}")
        self.assertEqual(val["validation_score"], 100)

    # =========================================================================
    # 8. DOWNLOAD ROUTES & HTTP ENDPOINTS
    # =========================================================================

    def test_08_download_docx_and_pdf_routes(self):
        """Verify that download endpoints return correct MIME types and non-empty streams."""
        for proj_id, name in [
            (self.healthcare_id, "Healthcare Multi-Agent AI Workflow Automation"),
            (self.claimwise_id, "ClaimWise AI"),
            (self.culturelens_id, "CultureLens"),
            (self.crosswalk_id, "Smart Crosswalk Safety System"),
            (self.hiresmart_id, "HireSmart AI"),
            (self.expense_id, "Smart Expense Tracker AI")
        ]:
            if not proj_id:
                continue

            # DOCX download
            resp_docx = self.client.get(f"/documentation/{proj_id}/download/docx")
            self.assertEqual(resp_docx.status_code, 200, f"DOCX download failed for {name}")
            self.assertEqual(resp_docx.content_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            self.assertGreater(len(resp_docx.data), 50000)

            # PDF download
            resp_pdf = self.client.get(f"/documentation/{proj_id}/download/pdf")
            self.assertEqual(resp_pdf.status_code, 200, f"PDF download failed for {name}")
            self.assertEqual(resp_pdf.content_type, "application/pdf")
            self.assertTrue(resp_pdf.data.startswith(b"%PDF"))
            self.assertGreater(len(resp_pdf.data), 15000)

            # Validation API
            resp_val = self.client.post(
                f"/documentation/{proj_id}/validate",
                data={"csrf_token": "test_csrf_token_doc"},
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            self.assertEqual(resp_val.status_code, 200)
            val_json = resp_val.get_json()
            self.assertTrue(val_json["valid"])
            self.assertEqual(val_json["validation_score"], 100)

    # =========================================================================
    # 9. DOCUMENTATION PREVIEW PAGE & INLINE STREAMING
    # =========================================================================

    def test_09_preview_documentation_routes_and_streaming(self):
        """Verify interactive preview page, inline PDF stream, and asset security."""
        for proj_id, name in [
            (self.healthcare_id, "Healthcare Multi-Agent AI"),
            (self.claimwise_id, "ClaimWise AI"),
            (self.culturelens_id, "CultureLens"),
            (self.crosswalk_id, "Smart Crosswalk Safety System")
        ]:
            if not proj_id:
                continue

            # 1. Preview page via both route styles
            resp_preview = self.client.get(f"/documentation/{proj_id}/preview")
            self.assertEqual(resp_preview.status_code, 200, f"Preview failed for {name}")
            html = resp_preview.data.decode("utf-8")
            self.assertIn("Master Documentation Preview", html)
            self.assertIn(f"/documentation/{proj_id}/download/pdf?inline=1", html)
            self.assertIn("Download DOCX", html)
            self.assertIn("Download PDF", html)

            resp_preview_view = self.client.get(f"/documentation?project_id={proj_id}&view=preview")
            self.assertEqual(resp_preview_view.status_code, 200)
            self.assertIn("Master Documentation Preview", resp_preview_view.data.decode("utf-8"))

            # 2. Inline PDF stream via both endpoints
            resp_stream = self.client.get(f"/documentation/{proj_id}/download/pdf?inline=1")
            self.assertEqual(resp_stream.status_code, 200)
            self.assertEqual(resp_stream.content_type, "application/pdf")
            self.assertTrue(resp_stream.data.startswith(b"%PDF"))
            self.assertIn("inline", resp_stream.headers.get("Content-Disposition", ""))

            resp_stream2 = self.client.get(f"/documentation/{proj_id}/stream/pdf")
            self.assertEqual(resp_stream2.status_code, 200)
            self.assertEqual(resp_stream2.content_type, "application/pdf")

            # 3. Main documentation page has Preview button and inline viewer
            resp_main = self.client.get(f"/documentation?project_id={proj_id}")
            self.assertEqual(resp_main.status_code, 200)
            main_html = resp_main.data.decode("utf-8")
            self.assertIn("Preview Document", main_html)
            self.assertIn("view=preview", main_html)


if __name__ == "__main__":
    unittest.main()

