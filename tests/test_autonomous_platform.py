"""
Test Suite for DevGuardian AI Autonomous Software Engineering Platform
Validates:
1. Universal Project Generation across distinct categories (CV, Travel/Cultural, InsurTech, CRUD).
2. Complete, stack-authentic file and folder structures.
3. Project-Specific File Explorer & Path Traversal Security.
4. UI Reference Replication Engine & Visual Validation.
5. Login, Signup, and Preview Routing Isolation (No DevGuardian UI leak).
6. Autonomous AI Agent Orchestration, Evidence-Based Reports, & Live Timeline.
"""

import os
import ast
import json
import pytest
from pathlib import Path
from io import BytesIO

from db import get_standalone_db
from services.universal_generator import (
    UniversalProjectGenerator,
    classify_project_category
)
from services.file_explorer_service import FileExplorerService
from services.ui_reference_service import UIReferenceService
from services.agent_metrics_service import AgentMetricsService
from services.ui_service import render_preview_page, mock_url_for
from services.workspace_manager import get_project_workspace


class TestAutonomousPlatform:

    @classmethod
    def setup_class(cls):
        cls.test_proj_cv = "test_auton_cv_001"
        cls.test_proj_travel = "test_auton_travel_002"
        cls.test_proj_claim = "test_auton_claim_003"
        cls.test_proj_crud = "test_auton_crud_004"

        # Ensure database tables and test project records exist
        conn = get_standalone_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR IGNORE INTO users (id, email, password_hash, full_name)
                VALUES (1, 'tester@devguardian.ai', 'pbkdf2:sha256:test', 'Platform Tester')
            """)
            for pid, pname in [
                (cls.test_proj_cv, "Smart Crosswalk Safety System"),
                (cls.test_proj_travel, "CultureLens"),
                (cls.test_proj_claim, "ClaimWise AI"),
                (cls.test_proj_crud, "Inventory Manager"),
            ]:
                cur.execute("""
                    INSERT OR REPLACE INTO projects (id, user_id, name, description, status)
                    VALUES (?, 1, ?, 'Automated test project', 'completed')
                """, (pid, pname))
        conn.close()

    # =========================================================================
    # 1. UNIVERSAL PROJECT GENERATION ENGINE & CATEGORY CLASSIFIER
    # =========================================================================

    def test_category_classifier_distinct_domains(self):
        """Verify the generator correctly categorizes different requirements without a single template."""
        assert classify_project_category("Smart Crosswalk Safety System with camera detection") == "computer_vision"
        assert classify_project_category("CultureLens Cultural Travel Guide and Itinerary Planner") == "travel_cultural"
        assert classify_project_category("ClaimWise AI Insurance Claim Adjudication and Fraud") == "insurance_fintech"
        assert classify_project_category("Simple CRUD task manager application") == "crud_basic"
        assert classify_project_category("Knowledge Base Vector Search and Document Chunking RAG") == "rag_document"
        assert classify_project_category("Hospital Electronic Health Records and Patient Triage") == "healthcare"

    # =========================================================================
    # 2. TEST A: SMART CROSSWALK SAFETY SYSTEM (COMPUTER VISION)
    # =========================================================================

    def test_smart_crosswalk_cv_project_generation(self):
        """
        Verify Smart Crosswalk generates dedicated CV architecture:
        - models/detector.py, models/preprocessing.py
        - services/detection_service.py, alert_service.py, report_service.py
        - templates/live_camera.html, upload_image.html, analytics.html
        - tests/test_routes.py, tests/test_detection.py
        """
        files = UniversalProjectGenerator.generate_project(
            project_id=self.test_proj_cv,
            project_name="Smart Crosswalk Safety System",
            description="Autonomous pedestrian safety detection with live camera alerts and violation analytics",
            target_framework="flask",
            selected_ide="vscode"
        )

        filenames = [f["filename"] for f in files]

        # Verify critical computer vision modules
        assert "models/detector.py" in filenames
        assert "models/preprocessing.py" in filenames
        assert "services/detection_service.py" in filenames
        assert "services/alert_service.py" in filenames
        assert "services/report_service.py" in filenames

        # Verify CV specific templates & auth
        assert "templates/live_camera.html" in filenames
        assert "templates/upload_image.html" in filenames
        assert "templates/upload_video.html" in filenames
        assert "templates/analytics.html" in filenames
        assert "templates/login.html" in filenames
        assert "templates/signup.html" in filenames
        assert "templates/dashboard.html" in filenames

        # Verify test suites
        assert "tests/test_routes.py" in filenames
        assert "tests/test_detection.py" in filenames

        # Verify Python AST syntax correctness for all generated python files
        for f in files:
            if f["filename"].endswith(".py"):
                try:
                    ast.parse(f["content"], filename=f["filename"])
                except SyntaxError as e:
                    pytest.fail(f"Syntax error in generated file {f['filename']}: {e}")

        # Verify CrosswalkSafetyDetector class logic exists in detector.py
        det_file = next(f for f in files if f["filename"] == "models/detector.py")
        assert "class CrosswalkSafetyDetector" in det_file["content"]
        assert "detect_frame" in det_file["content"]
        assert "danger_score" in det_file["content"]

    # =========================================================================
    # 3. TEST B: CULTURELENS (TRAVEL / CULTURAL MULTI-AGENT)
    # =========================================================================

    def test_culturelens_travel_multiagent_generation(self):
        """
        Verify CultureLens generates travel and multi-agent specific modules:
        - agents/cultural_agent.py, agents/translation_agent.py, agents/itinerary_agent.py
        - services/destination_service.py
        - templates/destinations.html, culture_guide.html, translator.html, itinerary.html
        - NOT computer vision models!
        """
        files = UniversalProjectGenerator.generate_project(
            project_id=self.test_proj_travel,
            project_name="CultureLens",
            description="AI Cultural Travel Assistant with multilingual etiquette translation and personalized itineraries",
            target_framework="flask",
            selected_ide="vscode"
        )

        filenames = [f["filename"] for f in files]

        # Travel & Cultural agents
        assert "agents/cultural_agent.py" in filenames
        assert "agents/translation_agent.py" in filenames
        assert "agents/itinerary_agent.py" in filenames
        assert "services/destination_service.py" in filenames

        # Templates
        assert "templates/destinations.html" in filenames
        assert "templates/culture_guide.html" in filenames
        assert "templates/translator.html" in filenames
        assert "templates/itinerary.html" in filenames

        # Must NOT include CV models
        assert "models/detector.py" not in filenames
        assert "templates/live_camera.html" not in filenames

        # AST syntax validation
        for f in files:
            if f["filename"].endswith(".py"):
                ast.parse(f["content"], filename=f["filename"])

    # =========================================================================
    # 4. TEST C: CLAIMWISE AI (FINTECH / INSURANCE)
    # =========================================================================

    def test_claimwise_insurance_project_generation(self):
        """
        Verify ClaimWise AI generates insurance and claim adjudication architecture:
        - services/claim_service.py, services/fraud_detection_service.py
        - templates/new_claim.html, templates/dashboard.html
        - tests/test_claims.py
        """
        files = UniversalProjectGenerator.generate_project(
            project_id=self.test_proj_claim,
            project_name="ClaimWise AI",
            description="Automated Insurance Claim Processing with Fraud Risk Assessment",
            target_framework="flask",
            selected_ide="vscode"
        )

        filenames = [f["filename"] for f in files]

        assert "services/claim_service.py" in filenames
        assert "services/fraud_detection_service.py" in filenames
        assert "templates/new_claim.html" in filenames
        assert "templates/dashboard.html" in filenames
        assert "tests/test_claims.py" in filenames

        for f in files:
            if f["filename"].endswith(".py"):
                ast.parse(f["content"], filename=f["filename"])

    # =========================================================================
    # 5. TEST D: SIMPLE CRUD APPLICATION (CLEAN ARCHITECTURE)
    # =========================================================================

    def test_simple_crud_clean_architecture(self):
        """
        Verify simple CRUD does NOT add unneeded AI agents, CV detectors, or heavy dependencies.
        """
        files = UniversalProjectGenerator.generate_project(
            project_id=self.test_proj_crud,
            project_name="Inventory Manager",
            description="Simple warehouse item inventory tracking and CRUD dashboard",
            target_framework="flask",
            selected_ide="vscode"
        )

        filenames = [f["filename"] for f in files]

        # Verify clean basic structure
        assert "app.py" in filenames
        assert "database/db.py" in filenames
        assert "database/models.py" in filenames
        assert "templates/create_item.html" in filenames
        assert "tests/test_crud.py" in filenames

        # No AI agents, CV models, or complex multi-agent frameworks
        assert "models/detector.py" not in filenames
        assert "agents/cultural_agent.py" not in filenames
        assert "services/fraud_detection_service.py" not in filenames

        for f in files:
            if f["filename"].endswith(".py"):
                ast.parse(f["content"], filename=f["filename"])

    # =========================================================================
    # 6. FILE EXPLORER & PATH TRAVERSAL SECURITY
    # =========================================================================

    def test_file_explorer_nested_tree_and_traversal_protection(self):
        """Verify the file explorer displays the real directory tree and prevents path traversal."""
        tree = FileExplorerService.get_project_tree(self.test_proj_cv)
        assert tree["name"] in (self.test_proj_cv, "Smart_Crosswalk_Safety_System")
        assert tree["type"] == "directory"
        assert len(tree["children"]) > 0

        # Verify child folders exist
        child_names = [c["name"] for c in tree["children"]]
        assert "models" in child_names or "templates" in child_names or "app.py" in child_names

        # Verify reading real file content
        ok, details, msg = FileExplorerService.get_file_details(self.test_proj_cv, "models/detector.py")
        assert ok is True
        assert "CrosswalkSafetyDetector" in details["content"]
        assert details["syntax_ok"] is True

        # Verify Path Traversal Attack is blocked
        ok, details, msg = FileExplorerService.get_file_details(self.test_proj_cv, "../../app.py")
        assert ok is False
        assert "Security Alert" in msg

    # =========================================================================
    # 7. UI REFERENCE REPLICATION & FIDELITY AUDIT
    # =========================================================================

    def test_ui_reference_preservation_and_fidelity(self):
        """Verify UI reference images can be uploaded, stored per project, and analyzed."""
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(37, 99, 235))
        buf = BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        ref = UIReferenceService.save_reference_image(
            project_id=self.test_proj_cv,
            page_name="dashboard",
            file_bytes=png_bytes,
            original_filename="sample_dashboard_mockup.png"
        )

        assert ref["id"] is not None
        assert ref["page_name"] == "dashboard"
        assert Path(ref["image_path"]).exists()
        assert "color_palette" in ref["analysis"]
        assert "primary" in ref["analysis"]["color_palette"]

        # Run comparison with project template
        comp = UIReferenceService.compare_preview_with_reference(
            project_id=self.test_proj_cv,
            page_name="dashboard"
        )
        assert comp["fidelity_score"] > 0
        assert isinstance(comp["matching_tokens"], list)
        assert isinstance(comp["differences"], list)

    # =========================================================================
    # 8. PREVIEW ISOLATION & FIX LOGIN/SIGNUP DEVGUARDIAN LEAK
    # =========================================================================

    def test_preview_isolation_does_not_render_devguardian(self):
        """
        Verify preview rendering never loads DevGuardian AI Studio UI inside the iframe,
        and rewrites relative links to keep the user inside the generated project.
        """
        ok, html = render_preview_page(self.test_proj_cv, "templates/login.html")
        assert ok is True
        # Must contain project login content
        assert "Smart Crosswalk" in html or "Sign In" in html or "Login" in html
        # Must NOT contain DevGuardian main nav items
        assert "Dashboard Topbar" not in html
        assert "AI Multi-Agent Studio" not in html

        # Verify mock_url_for routes to render endpoint, not DevGuardian studio
        url = mock_url_for(self.test_proj_cv, "login")
        assert "ui-preview/render" in url
        assert "templates/login.html" in url

    # =========================================================================
    # 9. AGENT OBSERVABILITY & EVIDENCE-BASED NON-FABRICATED ACCURACY
    # =========================================================================

    def test_agent_metrics_transparency_and_timeline(self):
        """
        Verify agent executions record concrete operations, files, validation passes,
        and do not fabricate arbitrary accuracy scores.
        """
        AgentMetricsService.record_timeline_event(
            project_id=self.test_proj_cv,
            agent_key="coding",
            event_type="files_created",
            title="Generated 24 Files for Smart Crosswalk",
            details="Created detection services, models, and templates",
            file_path="models/detector.py"
        )

        AgentMetricsService.record_agent_detailed_report(
            project_id=self.test_proj_cv,
            agent_key="coding",
            task_assigned="Generate computer vision crosswalk architecture",
            work_performed="Implemented detector, preprocessing, and video alert services",
            files_created=["models/detector.py", "services/detection_service.py", "app.py"],
            validation_performed="AST Syntax Check across all 8 Python modules",
            result_status="Success",
            validation_pass_rate=100.0,
            test_pass_rate=100.0,
            requirements_coverage=100.0
        )

        reports = AgentMetricsService.get_agent_reports_for_project(self.test_proj_cv)
        assert len(reports) > 0
        coding_report = next(r for r in reports if r["agent_key"] == "coding")
        assert coding_report["accuracy_status"] == "Verified from 2 empirical validation checks"
        assert coding_report["accuracy_score"] == 100.0
        assert "models/detector.py" in coding_report["files_created"]

        timeline = AgentMetricsService.get_timeline_events(self.test_proj_cv)
        assert len(timeline) > 0
        assert any(t["agent_key"] == "coding" for t in timeline)
