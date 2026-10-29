"""
DevGuardian AI — Upgraded Documentation Quality Test Suite
Validates:
1. Actual high-resolution code screenshots generation & embedding.
2. Automatic AI provider detection (Gemini, Grok, OpenAI, Claude, Local).
3. Provider-specific API key configuration section & official documentation links.
4. Medium-length professional technical documentation with genuine project facts.
5. Preservation of original CaptionAI document format & SmartBridge/SkillWallet logos.
6. Absolute secret safety (zero exposed credentials, only safe placeholders).
"""

import os
import sys
import zipfile
import pytest
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from services.documentation_project_analyzer import (
    analyze_project_workspace,
    detect_project_ai_provider
)
from services.code_screenshot_service import (
    render_code_screenshot,
    generate_project_code_screenshots
)
from services.documentation_service import (
    generate_project_documentation,
    collect_project_documentation_data
)
from services.documentation_validation_service import validate_project_documentation

def test_ai_provider_detection_gemini():
    """Verify deep detection of Google Gemini API in HireSmart_AI."""
    ws = ROOT_DIR / "generated_projects" / "HireSmart_AI"
    assert ws.exists(), "HireSmart_AI project workspace must exist"

    report = analyze_project_workspace("proj_bdf4bf9f8d", str(ws))
    ai_info = report.get("ai_provider", {})

    assert ai_info.get("detected") is True
    assert ai_info.get("provider_key") == "gemini"
    assert "Google Gemini" in ai_info.get("provider_name")
    assert ai_info.get("env_var_name") in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]
    assert ai_info.get("official_doc_url") == "https://ai.google.dev/gemini-api/docs/api-key"
    assert ai_info.get("api_key_page_url") == "https://aistudio.google.com/"
    assert ai_info.get("api_docs_url") == "https://ai.google.dev/gemini-api/docs"
    assert "YOUR_GEMINI_API_KEY_HERE" in ai_info.get("env_example")
    assert "google-generativeai" in ai_info.get("required_package")
    assert "pip install google-generativeai" in ai_info.get("install_cmd")
    assert "gemini" in ai_info.get("configured_model").lower()

def test_ai_provider_detection_no_ai():
    """Verify detection of Local Deterministic Processing Engine in ClaimWise_AI."""
    ws = ROOT_DIR / "generated_projects" / "ClaimWise_AI"
    assert ws.exists(), "ClaimWise_AI project workspace must exist"

    report = analyze_project_workspace("proj_93f4e93b92", str(ws))
    ai_info = report.get("ai_provider", {})

    assert ai_info.get("is_cloud_ai") is False
    assert ai_info.get("provider_key") == "none"
    assert "Local Deterministic" in ai_info.get("provider_name")
    assert ai_info.get("official_doc_url") == "N/A (Built-in Local Deterministic Engine)"
    assert ai_info.get("api_key_page_url") == "N/A (Zero External Cloud API Keys Required)"
    assert "SECRET_KEY" in ai_info.get("env_var_name")

def test_ai_provider_detection_grok():
    """Verify detection of xAI Grok API via mock/fixture inspection."""
    req_grok = ["Flask>=3.0.0", "xai-sdk>=0.1.0", "python-dotenv"]
    env_grok = ["PORT", "XAI_API_KEY", "GROK_MODEL"]
    code_grok = {
        "services.py": """
import os
from xai_sdk import Client

client = Client(api_key=os.environ.get("XAI_API_KEY"))

def call_grok(prompt: str):
    response = client.chat.create(
        model="grok-2",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
"""
    }
    ai_info = detect_project_ai_provider(None, req_grok, env_grok, code_grok)

    assert ai_info.get("detected") is True
    assert ai_info.get("provider_key") == "grok"
    assert "xAI Grok" in ai_info.get("provider_name")
    assert ai_info.get("env_var_name") == "XAI_API_KEY"
    assert ai_info.get("official_doc_url") == "https://docs.x.ai/developers/quickstart"
    assert ai_info.get("api_key_page_url") == "https://console.x.ai/"
    assert ai_info.get("api_docs_url") == "https://docs.x.ai/"
    assert "YOUR_XAI_API_KEY_HERE" in ai_info.get("env_example")
    assert ai_info.get("configured_model") == "grok-2"

def test_code_screenshot_rendering_quality(tmp_path):
    """Verify that render_code_screenshot outputs a high-resolution, readable editor-style image."""
    code_sample = """def validate_user_access(user_id: int, role: str) -> bool:
    # Verifies user role constraints
    if not user_id or user_id <= 0:
        return False
    return role in ['Admin', 'Operator', 'Auditor']"""

    out_png = tmp_path / "test_screenshot.png"
    rendered_path = render_code_screenshot(
        code_text=code_sample,
        filename="auth_service.py",
        section_title="User Role Authorization & Validation",
        output_path=str(out_png),
        lang="python"
    )

    assert os.path.exists(rendered_path)
    assert os.path.getsize(rendered_path) > 10000

    # Verify image properties with Pillow
    with Image.open(rendered_path) as img:
        assert img.format == "PNG"
        assert img.width >= 1100
        assert img.height >= 120
        # Check DPI
        dpi = img.info.get("dpi")
        if dpi:
            assert dpi[0] >= 150

def test_project_code_screenshots_generation():
    """Verify that generate_project_code_screenshots creates images for all major sections."""
    ws = ROOT_DIR / "generated_projects" / "HireSmart_AI"
    report = analyze_project_workspace("proj_bdf4bf9f8d", str(ws))
    snippets = report.get("code_snippets", {})

    shots = generate_project_code_screenshots("proj_bdf4bf9f8d", str(ws), snippets)
    assert len(shots) >= 5
    assert "app_entry" in shots
    assert "routing" in shots
    assert "business_logic" in shots
    assert "database_models" in shots

    for key, path in shots.items():
        assert os.path.exists(path), f"Code screenshot {key} missing at {path}"
        assert os.path.getsize(path) > 10000, f"Code screenshot {key} too small"

def test_hiresmart_documentation_generation_and_validation():
    """Verify full end-to-end documentation generation and validation for HireSmart_AI."""
    res = generate_project_documentation("proj_bdf4bf9f8d")
    assert res.get("success") is True, f"Documentation generation failed: {res.get('error')}"

    docx_path = res.get("docx_path")
    pdf_path = res.get("pdf_path")
    assert os.path.exists(docx_path)
    assert os.path.getsize(docx_path) > 100000

    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 50000

    val = res.get("validation", {})
    assert val.get("score_percentage") == 100, f"Validation failed: {val.get('errors')}"
    assert val.get("checks_dict", {}).get("SmartBridge & SkillWallet Logos Preserved") is True
    assert val.get("checks_dict", {}).get("Actual Code Screenshots Embedded") is True
    assert val.get("checks_dict", {}).get("AI Provider Configuration & API Key Section Present") is True
    assert val.get("checks_dict", {}).get("No Tables Present (Strict No-Table Policy)") is True
    assert val.get("checks_dict", {}).get("Project Workflow & Milestones Separately Documented") is True
    assert val.get("checks_dict", {}).get("No Private Secrets Exposed") is True

    # Inspect DOCX XML for required sections and zero real secrets
    with zipfile.ZipFile(docx_path, "r") as z:
        doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "AI Provider Configuration and API Key Setup" in doc_xml
        assert "Google Gemini" in doc_xml
        assert "GEMINI_API_KEY" in doc_xml
        assert "https://ai.google.dev/gemini-api/docs/api-key" in doc_xml
        assert "https://aistudio.google.com/" in doc_xml
        assert "https://ai.google.dev/gemini-api/docs" in doc_xml
        assert "Filename: app.py" in doc_xml
        assert "Filename: services.py" in doc_xml

        # Assert STRICT NO-TABLE policy
        assert "<w:tbl" not in doc_xml, "Detected unwanted <w:tbl> in HireSmart DOCX XML!"

        # Assert Project Workflow & Milestones separation
        assert "Project Workflow" in doc_xml
        assert "Activity 1.1:" in doc_xml
        assert "Implementation Milestones" in doc_xml
        assert "Milestone 1:" in doc_xml

        # Assert no real secrets appear
        assert "YOUR_GEMINI_API_KEY_HERE" in doc_xml
        assert not any(x in doc_xml for x in ["AIzaSy", "sk-proj-", "xai-secret"])

def test_claimwise_documentation_generation_and_validation():
    """Verify full end-to-end documentation generation and validation for ClaimWise_AI (No-AI)."""
    res = generate_project_documentation("proj_93f4e93b92")
    assert res.get("success") is True, f"ClaimWise doc generation failed: {res.get('error')}"

    docx_path = res.get("docx_path")
    pdf_path = res.get("pdf_path")
    assert os.path.exists(docx_path)
    assert os.path.exists(pdf_path)

    val = res.get("validation", {})
    assert val.get("score_percentage") == 100, f"Validation failed: {val.get('errors')}"
    assert val.get("checks_dict", {}).get("No Tables Present (Strict No-Table Policy)") is True
    assert val.get("checks_dict", {}).get("Project Workflow & Milestones Separately Documented") is True

    with zipfile.ZipFile(docx_path, "r") as z:
        doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "AI Provider Configuration and API Key Setup" in doc_xml
        assert "Local Deterministic Processing Engine" in doc_xml
        assert "Zero Third-Party Cloud API Costs" in doc_xml
        assert "SECRET_KEY" in doc_xml

        # Assert STRICT NO-TABLE policy
        assert "<w:tbl" not in doc_xml, "Detected unwanted <w:tbl> in ClaimWise DOCX XML!"

        # Assert Project Workflow & Milestones separation & ER Diagram
        assert "Project Workflow" in doc_xml
        assert "Activity 1.1:" in doc_xml
        assert "Milestone 1:" in doc_xml
        assert "ER Diagram" in doc_xml
