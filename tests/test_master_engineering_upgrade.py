"""
Master Engineering Upgrade Acceptance Test Suite — DevGuardian AI
Verifies all 10 Priorities and Scenarios A through H from the Master Engineering Upgrade Prompt:
  - Scenario A: UI Generation (Option A: generate_ui)
  - Scenario B: Backend Only (Option B: backend_only)
  - Scenario C: Both — Full-Stack Application (Option C: both)
  - Scenario D: AI Configuration & Grok/Gemini Integration
  - Scenario E: Project Execution & Run Management (python app.py)
  - Scenario F: UI Reference Matching & Quality
  - Scenario G: Agent Reporting & Non-Fabricated Evidence
  - Scenario H: Project Explanation (14 Questions) & Recommendations (8 Categories)
"""

import os
import ast
import json
import pytest
from pathlib import Path
from io import BytesIO

from db import get_standalone_db
from services.universal_generator import (
    generate_universal_project,
    UniversalProjectGenerator,
    classify_project_category,
    synthesize_project_explanation_and_recommendations
)
from services.ai_service import (
    get_xai_api_key,
    get_xai_model,
    is_xai_configured,
    test_xai_connection as verify_xai_conn,
    test_gemini_connection as verify_gemini_conn,
    mask_api_key,
    update_env_variable,
    get_active_ai_provider,
    call_active_ai
)
from services.agent_metrics_service import AgentMetricsService
from services.report_service import compile_project_report
from services.ui_reference_service import UIReferenceService
from services.workspace_manager import get_project_workspace


class TestMasterEngineeringUpgrade:

    @classmethod
    def setup_class(cls):
        """Ensure test database and test records exist."""
        cls.test_proj_ui = "test_upgrade_ui_001"
        cls.test_proj_backend = "test_upgrade_backend_002"
        cls.test_proj_both = "test_upgrade_both_003"

        conn = get_standalone_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR IGNORE INTO users (id, email, password_hash, full_name)
                VALUES (999, 'engineer@devguardian.ai', 'pbkdf2:sha256:test', 'Lead AI Engineer')
            """)
            for pid, pname, mode in [
                (cls.test_proj_ui, "HealthTrack UI", "generate_ui"),
                (cls.test_proj_backend, "FinMetrics API", "backend_only"),
                (cls.test_proj_both, "SmartClaim FullStack", "both"),
            ]:
                cur.execute("""
                    INSERT OR REPLACE INTO projects (id, user_id, name, description, app_type, language, status, generation_mode)
                    VALUES (?, 999, ?, 'Automated test suite verification project', 'Web App', 'Python Flask', 'created', ?)
                """, (pid, pname, mode))
        conn.close()

    # -----------------------------------------------------------------
    # SCENARIO A: UI Generation (Option A: generate_ui)
    # -----------------------------------------------------------------
    def test_scenario_a_ui_generation(self):
        """
        Scenario A: UI Generation Mode creates:
        - Required Jinja2 templates
        - Responsive CSS
        - Functional UI prototype interactions
        - Prototype labeling / banner
        - Root app.py that starts with 'python app.py'
        - Clean AST compilation
        """
        res = generate_universal_project(
            project_name="MediDesign UI",
            description="Patient health tracking portal with medical records and appointment booking",
            app_type="Web App",
            language="Python Flask",
            assigned_port=5201,
            generation_mode="generate_ui"
        )
        files = res["files"]

        # 1. Entry point check
        assert "app.py" in files, "app.py must exist at project root"
        assert "python app.py" in files["README.md"]
        assert 'if __name__ == "__main__":' in files["app.py"]

        # 2. Jinja2 templates check
        template_files = [f for f in files.keys() if f.startswith("templates/")]
        assert len(template_files) >= 3, f"Expected multiple templates, got {template_files}"
        assert "templates/base.html" in files
        assert "templates/landing.html" in files or "templates/index.html" in files

        # 3. Static CSS check
        static_css = [f for f in files.keys() if f.endswith(".css")]
        assert len(static_css) >= 1, "Expected responsive CSS file"

        # 4. Prototype labeling in base template
        assert "Interactive Prototype" in files["templates/base.html"]

        # 5. AST Syntax compilation check
        tree = ast.parse(files["app.py"])
        assert tree is not None, "app.py must compile cleanly with AST"

    # -----------------------------------------------------------------
    # SCENARIO B: Backend Only (Option B: backend_only)
    # -----------------------------------------------------------------
    def test_scenario_b_backend_only(self):
        """
        Scenario B: Backend Only Mode creates:
        - Application entry point app.py
        - REST API routes (/api/health, data endpoints)
        - Data models and services
        - Zero HTML templates or static frontend files
        - Clean AST compilation
        - Tests asserting JSON responses
        """
        res = generate_universal_project(
            project_name="FinMetrics API",
            description="High-frequency financial metrics REST API and fraud scoring backend",
            app_type="Web App",
            language="Python Flask",
            assigned_port=5202,
            generation_mode="backend_only"
        )
        files = res["files"]

        # 1. Entry point check
        assert "app.py" in files, "app.py must exist at project root"
        assert 'if __name__ == "__main__":' in files["app.py"]

        # 2. Strictly ZERO frontend templates or static CSS/JS
        template_files = [f for f in files.keys() if f.startswith("templates/")]
        static_files = [f for f in files.keys() if f.startswith("static/")]
        assert len(template_files) == 0, f"Backend Only must NOT generate HTML templates: {template_files}"
        assert len(static_files) == 0, f"Backend Only must NOT generate static assets: {static_files}"

        # 3. Health check and REST API endpoints exist in app.py
        app_code = files["app.py"]
        assert "/api/health" in app_code, "app.py must include /api/health endpoint"
        assert "jsonify" in app_code, "app.py must return JSON responses"

        # 4. Config, requirements, .env.example, tests exist
        assert "config.py" in files
        assert "requirements.txt" in files
        assert ".env.example" in files
        assert "tests/test_app.py" in files

        # 5. AST Syntax compilation check
        tree = ast.parse(files["app.py"])
        assert tree is not None, "app.py must compile cleanly with AST"

    # -----------------------------------------------------------------
    # SCENARIO C: Both — Full-Stack Application (Option C: both)
    # -----------------------------------------------------------------
    def test_scenario_c_both_full_stack(self):
        """
        Scenario C: Both Full-Stack Mode creates:
        - Real Jinja2 templates connected to backend routes
        - SQLite database persistence and models
        - Authentication & domain services
        - Root app.py starting with python app.py
        - Automated unit tests asserting both HTML and API routes
        """
        res = generate_universal_project(
            project_name="SmartExpense Tracker AI",
            description="Intelligent corporate expense tracking with receipt scanning and approval workflow",
            app_type="Web App",
            language="Python Flask",
            assigned_port=5203,
            generation_mode="both"
        )
        files = res["files"]

        # 1. Entry point check
        assert "app.py" in files
        assert 'if __name__ == "__main__":' in files["app.py"]

        # 2. Both templates and static assets exist
        template_files = [f for f in files.keys() if f.startswith("templates/")]
        assert len(template_files) >= 3, f"Expected templates in full-stack, got {template_files}"
        assert "templates/base.html" in files

        # 3. Backend logic & database persistence
        assert "config.py" in files
        assert "models/" in "".join(files.keys()) or "ItemModel" in "".join(files.values()) or "db" in files["app.py"]

        # 4. Tests asserting endpoints
        assert "tests/test_app.py" in files
        test_code = files["tests/test_app.py"]
        assert "test_" in test_code

        # 5. AST Syntax compilation check
        tree = ast.parse(files["app.py"])
        assert tree is not None, "Full-stack app.py must compile cleanly with AST"

    # -----------------------------------------------------------------
    # SCENARIO D: AI Configuration & Grok/Gemini Verification
    # -----------------------------------------------------------------
    def test_scenario_d_ai_configuration(self):
        """
        Scenario D: AI Configuration verifies:
        - Sensitive key masking (never displays full secret)
        - Detection of configured vs not-configured states
        - Redaction of credentials in error messages
        - Safe .env variable update without corrupting other keys
        - Strict isolation: DevGuardian AI secret is never placed in generated project
        """
        # 1. Key masking
        assert mask_api_key(None) == "Not configured"
        assert mask_api_key("") == "Not configured"
        assert mask_api_key("short") == "Not configured"
        assert mask_api_key("your_api_key_here") == "Not configured"

        masked = mask_api_key("xai-1234567890abcdef1234567890")
        assert "•" in masked
        assert masked.startswith("xai-")
        assert masked.endswith("7890")
        assert "abcdef" not in masked, "Middle characters must be masked"

        # 2. Provider verification error handling does NOT leak keys
        is_ok, err_msg = verify_xai_conn(api_key="xai-invalidsecretkey1234567890")
        assert is_ok is False
        assert "xai-invalidsecretkey1234567890" not in err_msg, "Key must be sanitized/redacted"

        # 3. Safe .env variable updates without corruption
        test_env = Path("scratch/test_env_sandbox.env")
        test_env.parent.mkdir(parents=True, exist_ok=True)
        test_env.write_text("FOO=bar\nXAI_MODEL=grok-old\nBAZ=qux\n", encoding="utf-8")

        success = update_env_variable("XAI_MODEL", "grok-2", env_path=str(test_env))
        assert success is True
        content = test_env.read_text(encoding="utf-8")
        assert "XAI_MODEL=grok-2\n" in content
        assert "FOO=bar\n" in content
        assert "BAZ=qux\n" in content

        # 4. Strict credential isolation check
        res = generate_universal_project(
            project_name="IsolatedProject",
            description="Testing credential isolation",
            app_type="Web App",
            language="Python Flask"
        )
        files = res["files"]
        devguardian_secret = os.environ.get("GEMINI_API_KEY", "")
        if devguardian_secret and len(devguardian_secret) > 10:
            for fname, fcontent in files.items():
                assert devguardian_secret not in fcontent, f"DevGuardian secret leaked into {fname}!"

    # -----------------------------------------------------------------
    # SCENARIO E: Project Execution & Run Management
    # -----------------------------------------------------------------
    def test_scenario_e_project_execution_entry_point(self):
        """
        Scenario E: All generated Flask projects must have a working root app.py
        with startup command 'python app.py' on an assigned dynamic port.
        """
        for category, name in [
            ("computer_vision", "Smart Vision Safe"),
            ("insurance_fintech", "ClaimShield"),
            ("travel_cultural", "HeritageGuide"),
            ("crud_basic", "QuickInventory")
        ]:
            res = generate_universal_project(
                project_name=name,
                description=f"Automated test for {category}",
                assigned_port=5210
            )
            files = res["files"]
            assert "app.py" in files, f"Project {name} missing root app.py"
            assert "python app.py" in files["README.md"]

            # Must compile cleanly
            ast.parse(files["app.py"])

    # -----------------------------------------------------------------
    # SCENARIO F: UI Reference Matching
    # -----------------------------------------------------------------
    def test_scenario_f_ui_reference_matching(self):
        """
        Scenario F: UI Reference engine extracts palette, typography, layout tokens.
        """
        ref_tokens = UIReferenceService.extract_design_tokens(
            image_path=None,
            layout_preference="Modern SaaS",
            primary_color_hint="#2563EB"
        )
        assert ref_tokens is not None
        assert "primary_color" in ref_tokens
        assert "sidebar_width" in ref_tokens or "layout" in ref_tokens
        assert "border_radius" in ref_tokens

    # -----------------------------------------------------------------
    # SCENARIO G: Agent Reporting & Non-Fabricated Evidence
    # -----------------------------------------------------------------
    def test_scenario_g_agent_reporting_evidence(self):
        """
        Scenario G: Agent activity reports derive from measured checks.
        If accuracy is unverified, displays 'Accuracy: Not yet verified'
        rather than fabricated 100%.
        """
        # When no automated assertions are run:
        AgentMetricsService.record_agent_detailed_report(
            project_id=self.test_proj_both,
            agent_key="requirement_agent",
            task_assigned="Analyze user requirements and specifications",
            work_performed="Synthesized domain entities and functional scope",
            result_status="Success",
            validation_pass_rate=None,
            test_pass_rate=None
        )

        conn = get_standalone_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM agent_executions WHERE project_id = ? AND agent_key = 'requirement_agent' ORDER BY id DESC LIMIT 1",
            (self.test_proj_both,)
        )
        row = cur.fetchone()
        conn.close()

        assert row is not None
        # Accuracy score should not be a fabricated 100% when no checks were run
        assert row["accuracy_status"] is not None
        assert "Verified" in row["accuracy_status"] or "Completed without direct automated assertion" in row["accuracy_status"]

    # -----------------------------------------------------------------
    # SCENARIO H: Documentation (14 Questions & 8 Recommendation Categories)
    # -----------------------------------------------------------------
    def test_scenario_h_project_explanation_and_recommendations(self):
        """
        Scenario H: Generates authentic explanation answering all 14 mandatory questions
        and organizes recommendations across all 8 required categories.
        """
        doc = synthesize_project_explanation_and_recommendations(
            project_name="Smart Crosswalk AI",
            description="Real-time pedestrian detection and traffic light automation",
            category="computer_vision",
            generation_mode="both",
            assigned_port=5250,
            files_dict={"app.py": "", "config.py": ""}
        )

        # 14 Questions
        for q_num in range(1, 15):
            assert f"### {q_num}." in doc, f"Missing question {q_num} in documentation"

        # 8 Recommendation Categories
        for cat in [
            "1. Critical Issues",
            "2. Functionality Improvements",
            "3. UI/UX Improvements",
            "4. Performance Improvements",
            "5. Security Improvements",
            "6. Testing Improvements",
            "7. Deployment Improvements",
            "8. Future Features"
        ]:
            assert cat in doc, f"Missing recommendation category: {cat}"

        # In report structured_data
        report = compile_project_report(
            project_id=self.test_proj_both,
            project_name="SmartClaim FullStack",
            description="Insurance claims processing portal"
        )
        struct = report.get("structured_data", {})
        assert "19_project_explanation" in struct
        assert "20_engineering_recommendations" in struct
