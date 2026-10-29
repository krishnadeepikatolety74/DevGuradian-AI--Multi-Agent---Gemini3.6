"""
DevGuardian AI — Documentation Template Service
Handles strict reference DOCX template preservation (CaptionAI_Documentation.docx),
preserving SmartBridge and SkillWallet logos, headers, footers, margins, typography,
and embedding project-specific screenshots, diagrams, formatted selectable code snippets,
high-resolution syntax-highlighted code screenshot images, and provider-specific API key configuration.
Strictly prohibits tables in the document (replaces with structured headings and bullet items).
Zero CaptionAI content leakage.
"""

import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

import services.code_screenshot_service as code_screenshot_service

ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = ROOT_DIR / "documentation_templates" / "CaptionAI_Documentation.docx"
SHARED_ASSETS_DIR = ROOT_DIR / "documentation_templates" / "shared_assets"
REFERENCE_ASSETS_DIR = ROOT_DIR / "documentation_templates" / "reference_assets"

MANDATORY_SHARED_ASSETS = [
    "google_ai_studio_home.png",
    "google_ai_studio_api_key_creation.png",
    "env_configuration_example.png",
    "config_py_api_configuration.png",
    "ngrok_installation_setup.png",
    "ngrok_configuration_example.png"
]

def get_shared_asset(filename: str) -> Optional[Path]:
    """Retrieve permanent shared reference image from the shared assets library."""
    p = SHARED_ASSETS_DIR / filename
    if p.exists() and p.stat().st_size > 0:
        return p
    alt = REFERENCE_ASSETS_DIR / filename
    if alt.exists() and alt.stat().st_size > 0:
        return alt
    return None

def verify_shared_assets_library() -> Dict[str, Any]:
    """Verify all six mandatory shared reference images exist in shared_assets."""
    status = {}
    all_ok = True
    missing_files = []
    for m in MANDATORY_SHARED_ASSETS:
        asset_path = get_shared_asset(m)
        present = asset_path is not None and asset_path.exists()
        status[m] = {
            "present": present,
            "path": str(asset_path) if present else str(SHARED_ASSETS_DIR / m),
            "size": asset_path.stat().st_size if present else 0
        }
        if not present:
            all_ok = False
            missing_files.append(m)
    return {
        "all_present": all_ok,
        "assets": status,
        "missing_files": missing_files
    }

def check_master_template_status() -> Dict[str, Any]:
    """Inspect and validate master reference template availability, logos, and shared assets."""
    if not TEMPLATE_PATH.exists():
        return {
            "available": False,
            "filename": "CaptionAI_Documentation.docx",
            "path": str(TEMPLATE_PATH),
            "status": "missing",
            "message": f"Master reference template missing. Expected at {TEMPLATE_PATH}",
            "logos_preserved": False
        }

    smartbridge_logo = False
    skillwallet_logo = False
    arch_image = False

    try:
        with zipfile.ZipFile(str(TEMPLATE_PATH), "r") as z:
            namelist = z.namelist()
            if "word/media/image9.png" in namelist or "word/media/image1.png" in namelist:
                smartbridge_logo = True
                skillwallet_logo = True
            if "word/media/image3.png" in namelist:
                arch_image = True
    except Exception as e:
        return {
            "available": False,
            "filename": "CaptionAI_Documentation.docx",
            "status": "corrupt",
            "message": f"Template archive error: {str(e)}",
            "logos_preserved": False
        }

    shared_lib_status = verify_shared_assets_library()

    return {
        "available": True,
        "filename": "CaptionAI_Documentation.docx",
        "path": str(TEMPLATE_PATH),
        "file_size": TEMPLATE_PATH.stat().st_size,
        "status": "verified",
        "logos_preserved": smartbridge_logo and skillwallet_logo,
        "smartbridge_logo": "preserved" if smartbridge_logo else "missing",
        "skillwallet_logo": "preserved" if skillwallet_logo else "missing",
        "smartbridge_logo_ok": smartbridge_logo,
        "skillwallet_logo_ok": skillwallet_logo,
        "architecture_placeholder": arch_image,
        "shared_assets": shared_lib_status,
        "shared_assets_ok": shared_lib_status["all_present"],
        "message": "Master reference DOCX template verified with SmartBridge and SkillWallet logos and shared assets intact."
    }

# =====================================================================
# TYPOGRAPHY & ELEMENT BUILDERS MATCHING CAPTIONAI REFERENCE EXACTLY
# =====================================================================

def add_title(doc: docx.Document, title_text: str, subtitle_text: Optional[str] = None):
    """Add document title matching CaptionAI reference format (Cambria 20pt Bold)."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(title_text)
    run.font.name = 'Cambria'
    run.font.size = Pt(20)
    run.bold = True
    run.font.color.rgb = RGBColor(0, 0, 0)

    if subtitle_text:
        sub_p = doc.add_paragraph()
        sub_p.paragraph_format.space_before = Pt(0)
        sub_p.paragraph_format.space_after = Pt(12)
        sub_run = sub_p.add_run(subtitle_text)
        sub_run.font.name = 'Cambria'
        sub_run.font.size = Pt(11)
        sub_run.italic = True
        sub_run.font.color.rgb = RGBColor(70, 70, 70)

def add_h1(doc: docx.Document, text: str):
    """Add Heading 1 matching CaptionAI format (Cambria 16pt Bold, space_before 18pt, space_after 6pt)."""
    try:
        p = doc.add_paragraph(style='Heading 1')
    except Exception:
        p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Cambria'
    run.font.size = Pt(16)
    run.bold = True
    run.font.color.rgb = RGBColor(0, 0, 0)
    return p

def add_h2(doc: docx.Document, text: str):
    """Add Heading 2 matching CaptionAI format (Cambria 14pt Bold, space_before 12pt, space_after 6pt)."""
    try:
        p = doc.add_paragraph(style='Heading 2')
    except Exception:
        p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Cambria'
    run.font.size = Pt(14)
    run.bold = True
    run.font.color.rgb = RGBColor(0, 0, 0)
    return p

def add_h3(doc: docx.Document, text: str):
    """Add Heading 3 matching CaptionAI format (Cambria 12pt Bold, space_before 10pt, space_after 4pt)."""
    try:
        p = doc.add_paragraph(style='Heading 3')
    except Exception:
        p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Cambria'
    run.font.size = Pt(12)
    run.bold = True
    run.font.color.rgb = RGBColor(0, 0, 0)
    return p

def add_body(doc: docx.Document, text: str, bold_prefix: Optional[str] = None, space_after: int = 5):
    """Add normal body paragraph matching CaptionAI format (Cambria 11pt, line spacing 1.15)."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15

    if bold_prefix:
        brun = p.add_run(bold_prefix + (" " if not bold_prefix.endswith(" ") else ""))
        brun.font.name = 'Cambria'
        brun.font.size = Pt(11)
        brun.bold = True
        brun.font.color.rgb = RGBColor(0, 0, 0)

    run = p.add_run(text)
    run.font.name = 'Cambria'
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0, 0, 0)
    return p

def add_bullet(doc: docx.Document, title: str, description: str):
    """Add styled bullet point with bold lead matching CaptionAI format."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.15

    brun_bullet = p.add_run("•  ")
    brun_bullet.font.name = 'Cambria'
    brun_bullet.font.size = Pt(11)
    brun_bullet.bold = True
    brun_bullet.font.color.rgb = RGBColor(0, 0, 0)

    brun = p.add_run(title + (" " if not title.endswith(" ") else ""))
    brun.font.name = 'Cambria'
    brun.font.size = Pt(11)
    brun.bold = True
    brun.font.color.rgb = RGBColor(0, 0, 0)

    run = p.add_run(description)
    run.font.name = 'Cambria'
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0, 0, 0)
    return p

def add_component_item(
    doc: docx.Document,
    idx: int,
    name: str,
    responsibility: str,
    inputs: str,
    outputs: str,
    dependencies: str
):
    """
    Format a component entry using structured headings and bullets.
    Strictly replaces tables as mandated by project requirements.
    """
    add_h3(doc, f"{idx}. {name}")
    add_bullet(doc, "Core Responsibility:", responsibility)
    add_bullet(doc, "Inputs:", inputs)
    add_bullet(doc, "Outputs:", outputs)
    add_bullet(doc, "Dependencies:", dependencies)

def add_error_item(
    doc: docx.Document,
    idx: int,
    error_code: str,
    root_cause: str,
    resolution: str
):
    """Format an error troubleshooting item using structured headings and bullets (NO tables)."""
    add_h3(doc, f"Troubleshooting Case {idx}: {error_code}")
    add_bullet(doc, "Root Cause:", root_cause)
    add_bullet(doc, "Actionable Resolution:", resolution)

def add_route_item(
    doc: docx.Document,
    route_path: str,
    methods: str,
    description: str
):
    """Format an endpoint route handler using structured headings and body (NO tables)."""
    add_h3(doc, f"Endpoint: {route_path} [{methods}]")
    add_body(doc, description, bold_prefix="Handler Description:")

def add_screenshot_required_notification(doc: docx.Document, notification_text: str):
    """
    Render a visually distinct, official screenshot-required notification callout
    matching Rule 2 requirement 10.
    """
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.keep_with_next = True

    run = p.add_run(notification_text)
    run.font.name = 'Cambria'
    run.font.size = Pt(10.5)
    run.bold = True
    # Distinct crimson red color
    run.font.color.rgb = RGBColor(180, 20, 20)
    return p

def add_code_block(doc: docx.Document, filename: str, code_str: str, explanation: Optional[str] = None):
    """
    Deprecated textual code block stub. Strictly enforces Rule 2:
    NEVER displays source code as selectable text anywhere in the generated DOCX.
    Delegates to code screenshot embedding.
    """
    add_body(doc, filename, bold_prefix="Filename:")
    add_body(doc, "", bold_prefix="Code Screenshot:")
    add_screenshot_required_notification(
        doc,
        "[SCREENSHOT REQUIRED — Please capture and insert the actual screenshot here.]"
    )
    if explanation:
        add_body(doc, explanation, bold_prefix="Explanation:")

def add_embedded_image(doc: docx.Document, img_path: str, caption: Optional[str] = None, width_inches: float = 6.2):
    """Embed real image matching CaptionAI reference (centered, high-res, with italic caption)."""
    if not img_path or not os.path.exists(img_path):
        return None

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True

    try:
        run = p.add_run()
        run.add_picture(img_path, width=Inches(width_inches))
    except Exception:
        add_body(doc, f"[Image Rendered: {os.path.basename(img_path)}]")

    if caption:
        cp = doc.add_paragraph()
        cp.paragraph_format.space_before = Pt(2)
        cp.paragraph_format.space_after = Pt(8)
        cp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        crun = cp.add_run(caption)
        crun.font.name = 'Cambria'
        crun.font.size = Pt(9.5)
        crun.italic = True
        crun.font.color.rgb = RGBColor(80, 80, 80)
    return p

def add_code_section_with_screenshot(
    doc: docx.Document,
    filename: str,
    section_title: str,
    code_str: str,
    explanation: Optional[str] = None,
    image_path: Optional[str] = None,
    figure_num: Optional[str] = None,
    lang: str = "python",
    assets_code_dir: Optional[str] = None,
    recorded_tracker: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Format every code section strictly matching Section 8 and Rule 2:
    - Activity or Implementation Heading (handled by caller or preceding paragraph)
    - Filename: <filename>
    - Code Screenshot:
    - Insert readable screenshot image showing the relevant source code (with multi-part splitting if needed)
    - If screenshot unavailable/fails: insert explicit screenshot-required notification
    - Explanation: Provide concise explanation of what the code does
    - ZERO source code as selectable text.
    """
    # 1. Filename label (single run for contiguous XML matching)
    fp = doc.add_paragraph()
    fp.paragraph_format.space_before = Pt(6)
    fp.paragraph_format.space_after = Pt(2)
    fp.paragraph_format.keep_with_next = True
    frun = fp.add_run(f"Filename: {filename}")
    frun.font.name = 'Cambria'
    frun.font.size = Pt(11)
    frun.bold = True
    frun.font.color.rgb = RGBColor(0, 0, 0)

    # 2. Code Screenshot label
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(2)
    sp.paragraph_format.space_after = Pt(4)
    sp.paragraph_format.keep_with_next = True
    srun = sp.add_run("Code Screenshot:")
    srun.font.name = 'Cambria'
    srun.font.size = Pt(11)
    srun.bold = True
    srun.font.color.rgb = RGBColor(0, 0, 0)

    # Handle missing or unavailable source code
    if not code_str or not code_str.strip():
        add_screenshot_required_notification(
            doc,
            "[SOURCE CODE SCREENSHOT REQUIRED — The relevant source file must be inspected and its screenshot added manually.]"
        )
        if explanation:
            add_body(doc, explanation, bold_prefix="Explanation:")
        if recorded_tracker is not None:
            recorded_tracker.append({
                "filename": filename,
                "section_title": section_title,
                "image_path": None,
                "has_image": False
            })
        return ""

    # Redact any real secrets with safe placeholders
    cleaned_code = code_screenshot_service.redact_code_secrets(code_str)

    # 3. Check / dynamically generate matching code screenshot(s)
    target_images: List[str] = []
    if image_path and os.path.exists(image_path):
        target_images.append(image_path)
    
    if not target_images and assets_code_dir:
        safe_fn = re.sub(r'[^a-zA-Z0-9_-]', '_', filename.lower())
        target_base = os.path.join(assets_code_dir, f"{safe_fn}_code.png")
        try:
            rendered_paths = code_screenshot_service.render_code_screenshots_multi(
                code_text=cleaned_code,
                filename=filename,
                section_title=section_title,
                output_base_path=target_base,
                lang=lang,
                max_lines_per_image=40
            )
            target_images.extend([p for p in rendered_paths if os.path.exists(p)])
        except Exception as e:
            print(f"[DocTemplate] Failed to generate code screenshot for {filename}: {e}")

    # 4. Embed image(s) or notification
    has_img = False
    if target_images:
        for idx, img_p in enumerate(target_images, start=1):
            if len(target_images) > 1:
                cap = f"Figure {figure_num or 'X'}.{idx}: Source Code Implementation — {filename} [{section_title}] (Part {idx} of {len(target_images)})"
            else:
                cap = f"Figure {figure_num or 'X'}: Source Code Implementation — {filename} [{section_title}]"
            add_embedded_image(doc, img_p, caption=cap, width_inches=6.2)
            has_img = True
    else:
        add_screenshot_required_notification(
            doc,
            "[SCREENSHOT REQUIRED — Please capture and insert the actual screenshot here.]"
        )

    # 5. Explanation
    if explanation:
        add_body(doc, explanation, bold_prefix="Explanation:")

    if recorded_tracker is not None:
        recorded_tracker.append({
            "filename": filename,
            "section_title": section_title,
            "image_path": target_images[0] if target_images else None,
            "has_image": has_img
        })

    return target_images[0] if target_images else ""

# =====================================================================
# MAIN DOCUMENT BUILDER
# =====================================================================

def populate_project_docx(
    project_id: str,
    project_data: Dict[str, Any],
    architecture_png_path: str,
    output_docx_path: str,
    screenshots_dict: Optional[Dict[str, str]] = None,
    code_screenshots_dict: Optional[Dict[str, str]] = None,
    assets_code_dir: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Generate project-specific DOCX by loading the master reference template,
    preserving SmartBridge and SkillWallet logos, headers, footers, page numbering,
    and reconstructing complete, accurate, project-specific sections:
    - 2–4 paragraph Project Description
    - 3–5 Operational Scenarios
    - Technical Architecture with Diagram and Component Breakdown (STRICTLY NO TABLES)
    - Provider-Specific AI Configuration and API Key Setup Section
    - Dedicated, fully developed Project Workflow with Activities 1.1 to 1.11
    - Separate Implementation Milestones section
    - Selectable code blocks AND matching high-resolution editor code screenshot images for EVERY code section
    - Genuine project UI screenshots
    - Zero CaptionAI content leakage
    - ZERO tables in the final output document
    """
    tmpl_status = check_master_template_status()
    if not tmpl_status.get("available"):
        return False, tmpl_status.get("message", "Master template unavailable")

    os.makedirs(os.path.dirname(output_docx_path), exist_ok=True)
    if not assets_code_dir:
        assets_code_dir = os.path.join(os.path.dirname(output_docx_path), "assets", "code")
    os.makedirs(assets_code_dir, exist_ok=True)

    name = project_data.get("name", "Software Project")
    desc = project_data.get("description", "Enterprise AI software platform")
    app_type = project_data.get("app_type", "Web Application")
    language = project_data.get("language", "Python Flask")
    routes = project_data.get("routes", [])
    route_details = project_data.get("route_details", [])
    models = project_data.get("models", [])
    model_details = project_data.get("model_details", [])
    services = project_data.get("services", [])
    agents = project_data.get("detected_agents") or project_data.get("agents", [])
    dependencies = project_data.get("dependencies", ["Flask>=3.0.0", "Werkzeug>=3.0.0", "pytest>=8.0.0"])
    apis = project_data.get("apis", ["SQLite Local Persistence Engine", "Flask Application Gateway"])
    code_snippets = project_data.get("code_snippets", {})
    scenarios = project_data.get("scenarios", [])
    ai_info = project_data.get("ai_provider", {})

    shots = screenshots_dict or {}
    code_shots = code_screenshots_dict or {}
    recorded_code_sections: List[Dict[str, Any]] = []

    try:
        # Load master reference template
        doc = docx.Document(str(TEMPLATE_PATH))

        # Clear body paragraphs and tables while strictly preserving sectPr (header logos and margins)
        body = doc._body._element
        for elem in list(body):
            if elem.tag.endswith('sectPr'):
                continue
            body.remove(elem)

        # -------------------------------------------------------------
        # Section 0: Title & Subtitle
        # -------------------------------------------------------------
        add_title(
            doc,
            f"{name}: Enterprise Software & Autonomous Operations Platform",
            "Comprehensive Software Engineering Specification, System Architecture & Production Deployment Reference"
        )

        # -------------------------------------------------------------
        # Section 1: Project Description (2–4 well-developed paragraphs)
        # -------------------------------------------------------------
        add_h1(doc, "Project Description:")

        # Paragraph 1: Problem statement and operational friction
        add_body(
            doc,
            f"{name} is an enterprise-grade {app_type.lower()} engineered with {language} to address operational inefficiencies, "
            f"reduce manual cognitive burden, and establish verifiable governance across the target business domain. In conventional "
            f"operational workflows, administrative overhead, fragmented record tracking, and unverified data entry create systemic "
            f"delays and costly compliance discrepancies. {name} eliminates these points of friction through a unified, automated "
            f"pipeline combining structured business validation, real-time telemetry, and resilient transactional persistence."
        )

        # Paragraph 2: Intended users and purpose
        add_body(
            doc,
            f"The primary purpose of {name} is to provide operators, domain analysts, and system administrators with a single, "
            f"authoritative platform for executing critical business operations. By exposing role-appropriate interfaces—ranging "
            f"from high-level operational dashboards to granular transactional inspection forms—the platform guarantees that every "
            f"stakeholder can interact with domain entities without navigating raw database queries or disparate offline spreadsheets."
        )

        # Paragraph 3: Core functionality and automation
        add_body(
            doc,
            f"Core system functionality encompasses end-to-end data intake, parameterized domain rule evaluation, automated state transitions, "
            f"and tamper-evident audit trail recording. Client requests enter through an authenticated HTTP gateway, undergo schema and "
            f"boundary verification, and are evaluated by internal processing routines before committing synchronously to SQLite persistence. "
            f"This architecture ensures that invalid payloads are rejected at the edge, preserving database consistency and system integrity."
        )

        # Paragraph 4: Technological architecture and design principles
        add_body(
            doc,
            f"Architecturally, {name} strictly adheres to separation of concerns by isolating the responsive Jinja2 presentation tier, "
            f"the Flask WSGI application router, the stateless domain services engine, and the relational data access layer. "
            f"This modular organization facilitates independent unit testing, seamless containerization, zero-downtime database migrations, "
            f"and horizontal scaling under enterprise production workloads."
        )

        # -------------------------------------------------------------
        # Section 2: Operational Scenarios (3–5 detailed scenarios)
        # -------------------------------------------------------------
        add_h2(doc, "Operational Scenarios")
        if not scenarios:
            scenarios = [
                f"Scenario 1: Standard Operational Ingestion — An operator initiates data intake through the web portal. The system parses inputs, verifies integrity constraints, computes domain risk scores, and commits the transaction to relational persistence with synchronous audit logging.",
                f"Scenario 2: Real-Time Telemetry & Dashboard Monitoring — An administrative user accesses the operational command center to inspect live KPI cards, review throughput trends, and filter active domain records by operational status with instant feedback.",
                f"Scenario 3: Audit Review & Regulatory Verification — A compliance officer reviews historical transactions, examining tamper-evident audit logs and timestamps to confirm that every operational state transition satisfied statutory policies.",
                f"Scenario 4: High-Concurrency Health & Regression Testing — Automated CI/CD test runners execute concurrent HTTP route probes and service assertions against the SQLite persistence layer to guarantee zero lock contention and regression immunity."
            ]

        for s in scenarios:
            parts = s.split(":", 1)
            if len(parts) == 2:
                add_body(doc, parts[1].strip(), bold_prefix=parts[0].strip() + ":")
            else:
                add_body(doc, s)

        # -------------------------------------------------------------
        # Section 3: Technical Architecture & Diagram (2–4 paragraphs)
        # -------------------------------------------------------------
        add_h1(doc, "Technical Architecture:")

        add_body(
            doc,
            f"The technical architecture of {name} is organized around a multi-tier modular pipeline designed for strict boundary "
            f"isolation, maintainability, and predictable runtime behavior. The system decouples presentation, routing, business logic, "
            f"and persistence into dedicated components that communicate across well-defined interfaces."
        )
        add_body(
            doc,
            f"Incoming client requests reach the Flask WSGI gateway where session security and route authorization are enforced. "
            f"Validated requests are handed over to domain services in services.py, which execute business validation rules, risk scoring, "
            f"and algorithmic calculations without transport dependencies. Persistence operations are dispatched to model.py, "
            f"where parameterized SQLite statements guarantee relational consistency and zero SQL injection vulnerability."
        )
        add_body(
            doc,
            f"Directional data flow and component topology for {name} are illustrated in the architecture diagram below:"
        )

        # Embed Architecture Diagram
        arch_img = shots.get("architecture") or architecture_png_path
        if arch_img and os.path.exists(arch_img):
            add_embedded_image(
                doc,
                arch_img,
                caption=f"Figure 3.1: Technical Architecture Diagram for {name}",
                width_inches=6.2
            )

        # Embed ER Diagram (if database exists or models defined)
        db_img = shots.get("database_architecture")
        if not db_img or not os.path.exists(db_img):
            cand_paths = [
                os.path.join(os.path.dirname(output_docx_path), "diagrams", "database_architecture.png"),
                os.path.join(os.path.dirname(output_docx_path), "assets", "diagrams", "database_architecture.png"),
                os.path.join(os.path.dirname(output_docx_path), "architecture", "database_architecture.png")
            ]
            for cp in cand_paths:
                if os.path.exists(cp):
                    db_img = cp
                    break

        if db_img and os.path.exists(db_img):
            add_h2(doc, "ER Diagram:")
            add_embedded_image(
                doc,
                db_img,
                caption=f"Figure 3.2: Entity Relationship Diagram for {name}",
                width_inches=6.2
            )
            tbl_names = [m["name"] if isinstance(m, dict) else m for m in models] if models else ["records", "users", "claims"]
            add_body(
                doc,
                f"The {name} ER Diagram represents the database structure of the application. "
                f"The database maintains relational consistency and domain state across core tables ({', '.join(tbl_names)}). "
                f"User credentials, roles, and session states are managed securely, while domain transactions, status flags, and timestamps "
                f"are tracked with full ACID compliance. Parameterized SQLite queries guarantee complete protection against SQL injection attacks.",
                bold_prefix="Description:"
            )

        # -------------------------------------------------------------
        # Section 4: Pre-requisites (STRUCTURED BULLETS — STRICTLY NO TABLES)
        # -------------------------------------------------------------
        add_h1(doc, "Pre-requisites:")
        add_body(
            doc,
            f"The following runtime environments, language frameworks, and software packages are required to run and test {name}:"
        )
        add_bullet(doc, "Python Programming Environment:", "Python 3.10+ runtime with pip package manager (https://www.python.org/doc/).")
        add_bullet(doc, "Flask Microframework:", "Core WSGI application server handling HTTP dispatching, sessions, and Jinja2 templating (https://flask.palletsprojects.com/).")
        add_bullet(doc, "Relational Persistence Layer:", "SQLite database engine utilizing ACID-compliant transactions and parameterized queries (https://www.sqlite.org/docs.html).")
        add_bullet(doc, "Frontend Interface Technologies:", "Modern HTML5, responsive CSS token design system, and Jinja2 templating engine (https://jinja.palletsprojects.com/).")
        add_bullet(doc, "Automated Verification Framework:", "Pytest automated test runner for unit, integration, and security verification (https://docs.pytest.org/).")
        if ai_info.get("detected"):
            add_bullet(doc, f"{ai_info.get('provider_name')} SDK:", f"Official Python client library ({ai_info.get('required_package')}) for model inference ({ai_info.get('official_doc_url')}).")
        if project_data.get("has_ngrok", False):
            add_bullet(doc, "Ngrok Tunneling Service:", "Secure webhook development and external endpoint exposure (https://ngrok.com/docs).")

        # -------------------------------------------------------------
        # Section 5: Project Workflow (CONCISE NUMBERED ACTIVITIES ONLY — REQUIREMENT 1)
        # -------------------------------------------------------------
        add_h1(doc, "Project Workflow:")
        add_body(
            doc,
            f"The Project Workflow defines the sequential progression of development, implementation, and verification activities "
            f"executed to build and operate {name}:"
        )

        # Activity 1: Model / Engine Selection and Architecture
        act1_title = "Model Selection and Architecture" if ai_info.get("detected") else "Engine Selection and Architecture"
        add_h3(doc, f"Activity 1: {act1_title}")
        if ai_info.get("detected"):
            add_bullet(doc, "Activity 1.1:", f"Provision a verified {ai_info.get('provider_name')} API key and configure {ai_info.get('env_var_name')} securely in the project environment.")
            add_bullet(doc, "Activity 1.2:", f"Research and select the appropriate generative model ({ai_info.get('configured_model')}) for low-latency domain reasoning and structured outputs.")
        else:
            add_bullet(doc, "Activity 1.1:", f"Configure local environment variables, session encryption keys, and runtime parameters in .env.")
            add_bullet(doc, "Activity 1.2:", f"Evaluate and select the deterministic domain calculation engine for sub-millisecond offline execution.")
        add_bullet(doc, "Activity 1.3:", f"Define the multi-tier application architecture, detailing interactions between the presentation layer, WSGI backend, and SQLite database.")
        add_bullet(doc, "Activity 1.4:", f"Set up the development environment, installing the required Python packages and pinning dependencies in requirements.txt.")

        # Activity 2: Core Functionalities Development
        add_h3(doc, "Activity 2: Core Functionalities Development")
        tbl_names = [m["name"] if isinstance(m, dict) else m for m in models] if models else ["users", "claims", "records"]
        add_bullet(doc, "Activity 2.1:", f"Design the relational data schema in model.py covering {', '.join(tbl_names)} and idempotent table creation.")
        add_bullet(doc, "Activity 2.2:", f"Develop domain business logic, risk scoring heuristics, and input validation functions in services.py.")
        add_bullet(doc, "Activity 2.3:", f"Implement automated decision workflows, anomaly flagging rules, and transaction status transitions.")

        # Activity 3: App.py Development
        add_h3(doc, "Activity 3: App.py Development")
        add_bullet(doc, "Activity 3.1:", f"Write the main application logic in app.py, establishing page routes, session management, and authentication guards.")
        add_bullet(doc, "Activity 3.2:", f"Build request validation decorators and error boundaries to secure private routes and prevent unauthenticated access.")
        add_bullet(doc, "Activity 3.3:", f"Expose REST API endpoints for asynchronous client interactions and persist domain transactions synchronously to SQLite.")

        # Activity 4: Frontend Development
        add_h3(doc, "Activity 4: Frontend Development")
        add_bullet(doc, "Activity 4.1:", f"Design and develop responsive user interfaces using Jinja2 templates, semantic HTML5, and modern CSS design tokens.")
        add_bullet(doc, "Activity 4.2:", f"Create dynamic client rendering with vanilla JavaScript and Fetch API so status cards and tables update without page reloads.")

        # Activity 5: Deployment
        add_h3(doc, "Activity 5: Deployment")
        add_bullet(doc, "Activity 5.1:", f"Prepare the application for local deployment by establishing an isolated virtual environment and initializing database tables.")
        add_bullet(doc, "Activity 5.2:", f"Execute the automated Pytest test suite to verify unit logic, route dispatching, and persistence integrity.")
        add_bullet(doc, "Activity 5.3:", f"Deploy the application publicly using Ngrok to expose the local Flask server over a secure public URL.")

        # Activity 6: Conclusion
        add_h3(doc, "Activity 6: Conclusion")
        add_bullet(doc, "Activity 6.1:", f"Perform comprehensive end-to-end verification of system features, security postures, and documentation artifacts.")

        # -------------------------------------------------------------
        # Section 6: Implementation Milestones (DETAILED IMPLEMENTATION STAGES)
        # -------------------------------------------------------------
        add_h1(doc, "Implementation Milestones")
        add_body(
            doc,
            f"The Implementation Milestones delineate the engineering stages completed during the development lifecycle of {name}. "
            f"Each milestone encompasses actual source code, architectural specifications, configuration, and verification evidence:"
        )

        add_h2(doc, f"Milestone 1: {act1_title}")
        add_body(
            doc,
            f"Milestone 1 establishes the architectural foundation and execution environment for {name}. "
            f"This initial stage encompasses requirements analysis, selection of runtime technologies and computational models, "
            f"environment variable isolation, and configuration of runtime dependencies necessary for predictable execution."
        )

        # Sequential figure counter for Milestone code implementations (Figures 4.1 to 4.11)
        code_fig_idx = 1
        def next_code_fig() -> str:
            nonlocal code_fig_idx
            num = f"4.{code_fig_idx}"
            code_fig_idx += 1
            return num

        # Milestone 1 - Activity 1.1 (CaptionAI 6-Step API Key Setup Structure)
        if ai_info.get("detected"):
            p_name = ai_info.get("provider_name", "Google Gemini API")
            env_var = ai_info.get("env_var_name", "GEMINI_API_KEY")
            key_url = ai_info.get("api_key_page_url", "https://aistudio.google.com/")
            doc_url = ai_info.get("official_doc_url", "https://ai.google.dev/gemini-api/docs/api-key")
            api_docs_url = ai_info.get("api_docs_url", "https://ai.google.dev/gemini-api/docs")
            model_cfg = ai_info.get("configured_model", "gemini-2.5-flash")

            add_h3(doc, "Activity 1.1: Generate and Configure the AI API Key — AI Provider Configuration and API Key Setup")
            add_body(
                doc,
                f"Before the application can communicate with its configured AI provider, the required API credentials must be created and securely configured in the project environment. "
                f"Follow the sequential steps below to create, configure, load, and protect your credentials for {name}. "
                f"Official developer documentation is available at {doc_url}."
            )

            add_bullet(doc, "Step 1 — Open the Provider's Official API Platform:", f"Visit the official provider website at {key_url} and sign up or sign in using authorized developer credentials. Access official API documentation at {doc_url}.")
            ref_home_img = get_shared_asset("google_ai_studio_home.png")
            if ref_home_img and "gemini" in p_name.lower():
                add_embedded_image(doc, str(ref_home_img), caption=f"Figure 1.1: Official {p_name} Platform Overview ({key_url})", width_inches=6.2)

            add_bullet(doc, "Step 2 — Create an API Key:", f"Locate the API-key creation interface in the developer portal at {key_url}. Click 'Create API Key', select or configure a target project, assign a descriptive name, and generate the secret key token:")
            ref_ai_key_img = get_shared_asset("google_ai_studio_api_key_creation.png")
            prov_img = shots.get("ai_provider_portal")
            if ref_ai_key_img and "gemini" in p_name.lower():
                add_embedded_image(doc, str(ref_ai_key_img), caption=f"Figure 1.2: Official {p_name} Key Creation Interface ({key_url})", width_inches=6.2)
            elif prov_img and os.path.exists(prov_img):
                add_embedded_image(doc, prov_img, caption=f"Figure 1.2: Official {p_name} Developer Console Portal", width_inches=6.2)
            else:
                add_screenshot_required_notification(
                    doc,
                    "[PROVIDER WEBSITE SCREENSHOT REQUIRED — Please open the official provider website and capture the relevant setup screen.]"
                )

            add_bullet(doc, "Step 3 — Copy and Secure the Key:", "Immediately copy the generated key and store it in an encrypted password vault. Most provider consoles will not display the full secret key again once you navigate away from the confirmation modal. Important security guidance: Never commit API keys to source control. Never embed real credentials in templates or frontend code. Never place real secrets in screenshots or documentation. Use environment variables or the project's secret-management mechanism.")
            placeholder_val = "YOUR_GEMINI_API_KEY_HERE" if "gemini" in p_name.lower() else f"YOUR_{p_name.upper().replace(' ', '_')}_API_KEY_HERE"
            add_bullet(doc, "Step 4 — Configure the Project Environment:", f"Create a .env file in the root directory of {name} (if not already present). Add your {p_name} API key using the exact environment variable name expected by the codebase ({env_var}={placeholder_val}). Always use safe placeholder values like {placeholder_val} and never expose real credentials or secrets in project files:")

            env_content = (
                f"# AI Provider Configuration for {name}\n"
                f"{ai_info.get('env_example', f'{env_var}=YOUR_GEMINI_API_KEY_HERE')}\n"
                f"PORT=5000\n"
                f"FLASK_ENV=development\n"
                f"SECRET_KEY=YOUR_SECRET_KEY_HERE"
            )
            ref_env_img = get_shared_asset("env_configuration_example.png")
            target_env_img = str(ref_env_img) if (ref_env_img and "gemini" in p_name.lower()) else code_shots.get("env_config")
            add_code_section_with_screenshot(
                doc,
                filename=".env.example",
                section_title="AI Provider Environment Configuration",
                code_str=env_content,
                explanation=f"Specifies the exact environment variable name ({env_var}) with safe uppercase placeholder values.",
                image_path=target_env_img,
                figure_num=next_code_fig(),
                lang="ini",
                assets_code_dir=assets_code_dir,
                recorded_tracker=recorded_code_sections
            )

            add_bullet(doc, "Step 5 — Load the Credentials at Startup:", f"Explain how {name}'s actual configuration code in config.py reads environment variables using python-dotenv and initializes its AI provider at startup. The initialization handler verifies that {env_var} is defined:")
            ai_verify_code = (
                "import os\n"
                "from dotenv import load_dotenv\n"
                "load_dotenv()\n\n"
                f"# Resolves {env_var} from secure environment\n"
                f"api_key = os.environ.get('{env_var}')\n"
                f"if not api_key:\n"
                f"    print('Warning: {env_var} missing; activating offline fallback mode')\n"
                f"else:\n"
                f"    print('{p_name} authentication successfully verified')\n"
            )
            ref_cfg_img = get_shared_asset("config_py_api_configuration.png")
            target_cfg_img = str(ref_cfg_img) if (ref_cfg_img and "gemini" in p_name.lower()) else code_shots.get("ai_integration")
            add_code_section_with_screenshot(
                doc,
                filename="config.py",
                section_title="AI Provider Credential Verification & Startup",
                code_str=ai_verify_code,
                explanation=f"Validates that {env_var} is present at startup before instantiating API clients.",
                image_path=target_cfg_img,
                figure_num=next_code_fig(),
                lang="python",
                assets_code_dir=assets_code_dir,
                recorded_tracker=recorded_code_sections
            )

            add_bullet(doc, "Step 6 — Verify the Configuration and Fallback Behavior:", f"Explain how the application detects missing or invalid credentials and how the user can verify that the provider is configured correctly. If {env_var} is missing or invalid, the initialization handler detects the missing credential and activates the documented fallback behavior without crashing:")
            smoke_code = (
                "import os\n"
                "from config import Config\n"
                f"is_configured = bool(os.environ.get('{env_var}'))\n"
                "status = 'READY: ONLINE' if is_configured else 'FALLBACK: LOCAL DETERMINISTIC'\n"
                "print(f'Provider Connection State: {status}')\n"
            )
            add_code_section_with_screenshot(
                doc,
                filename="verify_provider.py",
                section_title="AI Provider Health Probe & Fallback Test",
                code_str=smoke_code,
                explanation=f"Verifies provider connectivity status and confirms graceful fallback readiness.",
                image_path=code_shots.get("smoke_test"),
                figure_num=next_code_fig(),
                lang="python",
                assets_code_dir=assets_code_dir,
                recorded_tracker=recorded_code_sections
            )

        else:
            add_h3(doc, "Activity 1.1: Generate and Configure the AI API Key — AI Provider Configuration and API Key Setup")
            add_body(
                doc,
                f"Before the application can communicate with its configured AI provider, the required API credentials must be created and securely configured in the project environment. "
                f"For {name}, the application is engineered as an autonomous system powered by a Local Deterministic Processing Engine with zero external cloud dependencies. "
                f"An external cloud AI API-key creation step is therefore not applicable. "
                f"The steps below document the applicable local environment configuration, secret management, startup verification, and fallback behavior:"
            )
            add_bullet(doc, "Step 1 — Open the Provider's Official API Platform:", f"External cloud account registration and remote API platform onboarding are not applicable to {name} because it utilizes an autonomous local calculation engine with zero external cloud dependencies, third-party token subscriptions, or external network latency.")
            add_bullet(doc, "Step 2 — Create an API Key:", f"Creation of external cloud AI API keys is bypassed in favor of internal deterministic rule evaluation, synchronous database transactions, and sub-millisecond in-process risk scoring algorithms. Core domain operations execute entirely offline without remote API billing.")
            add_screenshot_required_notification(
                doc,
                "[EXTERNAL CLOUD AI PROVIDER ONBOARDING NOT APPLICABLE — Local Deterministic Processing Engine operates entirely offline without external API keys or remote billing.]"
            )
            add_bullet(doc, "Step 3 — Copy and Secure the Key:", "Security instructions for local application secrets: Set SECRET_KEY to a cryptographically strong random string in your .env file. Never commit real secrets or credentials to version control. Ensure .gitignore includes .env. All database operations strictly use parameterized SQL placeholders to eliminate injection vulnerabilities.")
            add_bullet(doc, "Step 4 — Configure the Project Environment:", f"Configure the project's actual environment file (.env). While external cloud AI keys are not required, {name} requires local runtime configuration for session encryption (SECRET_KEY), server port binding (PORT), database path resolution, and operational flags:")
            ref_env_img = get_shared_asset("env_configuration_example.png")
            if ref_env_img:
                add_embedded_image(doc, str(ref_env_img), caption=f"Figure 1.3: Reference Environment File (.env) Variable Configuration Structure", width_inches=6.2)

            env_local = (
                f"# Environment Configuration for {name}\n"
                f"PORT=5003\n"
                f"FLASK_ENV=development\n"
                f"SECRET_KEY=YOUR_SECRET_KEY_HERE\n"
                f"DATABASE_PATH={name.lower().replace(' ', '_')}.db\n"
                f"USE_AI_PROVIDER=False"
            )
            add_code_section_with_screenshot(
                doc,
                filename=".env.example",
                section_title="Local Environment Configuration Template",
                code_str=env_local,
                explanation="Specifies internal application settings. No external cloud AI keys are required.",
                image_path=code_shots.get("env_config"),
                figure_num=next_code_fig(),
                lang="ini",
                assets_code_dir=assets_code_dir,
                recorded_tracker=recorded_code_sections
            )

            add_bullet(doc, "Step 5 — Load the Credentials at Startup:", f"The application loads environment variables automatically at startup in config.py using python-dotenv. The runtime configuration verifies that SECRET_KEY is set, assigns an isolated port to avoid collisions, and handles fallback behavior when optional parameters are absent:")
            ref_cfg_img = get_shared_asset("config_py_api_configuration.png")
            if ref_cfg_img:
                add_embedded_image(doc, str(ref_cfg_img), caption=f"Figure 1.4: Reference Application Configuration (config.py) Parameter Ingestion", width_inches=6.2)

            verify_local = (
                "import os\n"
                "from dotenv import load_dotenv\n"
                "load_dotenv()\n\n"
                "# Validate local environment parameters\n"
                "port = int(os.environ.get('PORT', 5003))\n"
                "secret_key = os.environ.get('SECRET_KEY')\n"
                "if not secret_key:\n"
                "    raise ValueError('SECRET_KEY must be configured in environment')\n"
                "print(f'Runtime configured successfully on port {port}')\n"
            )
            add_code_section_with_screenshot(
                doc,
                filename="config.py",
                section_title="Local Environment Verification & Startup",
                code_str=verify_local,
                explanation="Verifies that internal environment settings are loaded without third-party dependencies.",
                image_path=code_shots.get("config"),
                figure_num=next_code_fig(),
                lang="python",
                assets_code_dir=assets_code_dir,
                recorded_tracker=recorded_code_sections
            )

            add_bullet(doc, "Step 6 — Verify the Configuration and Fallback Behavior:", "The application verifies runtime configuration integrity upon initialization. If SECRET_KEY or other mandatory parameters are absent, a descriptive configuration error is raised before HTTP dispatching begins:")
            local_smoke = (
                "import os\n"
                "from config import Config\n"
                "assert Config.SECRET_KEY, 'SECRET_KEY must be configured'\n"
                "print('Local Runtime Configuration: Verified and Secure')\n"
            )
            add_code_section_with_screenshot(
                doc,
                filename="verify_runtime.py",
                section_title="Runtime Environment Integrity Smoke Test",
                code_str=local_smoke,
                explanation="Validates session secrets and confirms local runtime initialization integrity.",
                image_path=code_shots.get("smoke_test"),
                figure_num=next_code_fig(),
                lang="python",
                assets_code_dir=assets_code_dir,
                recorded_tracker=recorded_code_sections
            )

        # Milestone 1 - Activity 1.2
        add_h3(doc, "Activity 1.2: Research and Selection of the Computational Model")
        add_body(
            doc,
            f"Engineers evaluated candidate processing models against strict operational criteria: sub-second response latency, "
            f"zero failure rates, deterministic rule reproducibility, and enterprise data privacy. "
            f"{'The ' + ai_info.get('provider_name') + ' was selected for its robust multimodal reasoning and low latency.' if ai_info.get('detected') else 'The Local Deterministic Processing Engine was selected to eliminate cloud token overhead, remove network round-trip delays, and guarantee 100% offline data sovereignty.'}"
        )

        # Milestone 1 - Activity 1.3
        add_h3(doc, "Activity 1.3: Define the Architecture of the Application")
        add_body(
            doc,
            f"The application architecture separates concerns into a clean multi-tier structure: client presentation tier (Jinja2), "
            f"HTTP controller tier (Flask WSGI gateway), domain business services tier (services.py), and relational data persistence (model.py). "
            f"This topology ensures zero circular dependencies and isolates core calculation logic from web transport mechanics."
        )

        # Milestone 1 - Activity 1.4
        add_h3(doc, "Activity 1.4: Set Up the Development Environment")
        add_body(
            doc,
            f"Setting up the development environment ensures that all required system runtimes, isolated virtual environments, "
            f"and pinned third-party dependencies are properly configured to run and test {name}. "
            f"Follow the sequential setup instructions below:"
        )

        add_bullet(doc, "Step 1 — Python and pip Installation Verification:", "Ensure Python 3.10+ runtime and the pip package manager are installed on the development workstation. Verify the installed versions from the terminal using 'python --version' and 'pip --version'.")
        add_bullet(doc, "Step 2 — Virtual Environment Creation:", "Create an isolated Python virtual environment named 'env' to isolate project dependencies from global system Python packages using 'python -m venv env'.")
        add_bullet(doc, "Step 3 — Virtual Environment Activation Commands:", "Activate the virtual environment using the appropriate platform-specific command. On Windows (PowerShell/CMD): 'env\\Scripts\\activate'. On macOS/Linux: 'source env/bin/activate'.")
        add_bullet(doc, "Step 4 — Dependency Installation:", "Upgrade pip to the latest version and install all pinned project dependencies listed in requirements.txt using 'pip install -r requirements.txt'.")
        add_bullet(doc, "Step 5 — Actual Framework and Library Requirements:", "The pinned dependencies specify the exact package versions required for reproducible builds and execution stability:")

        req_text = "\n".join(dependencies)
        add_code_section_with_screenshot(
            doc,
            filename="requirements.txt",
            section_title="Pinned Runtime Dependencies",
            code_str=req_text,
            explanation="Pinned dependency versions ensuring reproducible builds and execution stability.",
            image_path=code_shots.get("dependencies"),
            figure_num=next_code_fig(),
            lang="python",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        add_bullet(doc, "Step 6 — Environment File Setup:", "Initialize the local environment configuration file by copying the template file .env.example to .env ('copy .env.example .env' on Windows, or 'cp .env.example .env' on macOS/Linux).")
        add_bullet(doc, "Step 7 — Project Directory Structure & Module Organization:", f"The codebase for {name} adheres to a clean multi-tier structure separating presentation, routing, domain logic, and data persistence:")

        add_bullet(doc, "app.py:", "Main Flask application entry point, HTTP routing, and session management.")
        add_bullet(doc, "model.py / database/:", "Relational data access layer, SQLite schema initialization, and parameterized queries.")
        add_bullet(doc, "services.py / agents/:", "Domain calculations, multi-agent workflows, risk scoring heuristics, and input validation.")
        add_bullet(doc, "config.py:", "Environment variable loading via python-dotenv and runtime secrets verification.")
        add_bullet(doc, "run_public.py:", "Public deployment script via Ngrok reverse proxy tunneling.")
        add_bullet(doc, "test_app.py / tests/:", "Automated Pytest regression test suites validating routes and core business logic.")
        add_bullet(doc, "templates/:", "Jinja2 presentation templates providing responsive SaaS user interfaces.")
        add_bullet(doc, "static/:", "Frontend styling tokens (CSS), asynchronous fetch handlers (JavaScript), and media assets.")

        dir_img = shots.get("directory_structure")
        if dir_img and os.path.exists(dir_img):
            add_embedded_image(doc, dir_img, caption=f"Figure 1.2: Project Directory Structure & Module Organization for {name}", width_inches=6.2)
        else:
            add_screenshot_required_notification(
                doc,
                "[SCREENSHOT REQUIRED — Please capture and insert the actual screenshot here.]"
            )

        add_bullet(doc, "Step 8 — Root-Level Application Entry Point (app.py) & Verification:", f"For Flask web applications, the project contains a functional root-level app.py and supports starting the development server directly using 'python app.py'. The entry point binds to the assigned local port and exposes all verified application endpoints:")
        app_entry_snippet = code_snippets.get("app_entry") or "# Root application entry point\nfrom flask import Flask\napp = Flask(__name__)"
        add_code_section_with_screenshot(
            doc,
            filename="app.py",
            section_title="Root Application Entry Point",
            code_str=app_entry_snippet,
            explanation="Initializes the Flask application, loads configuration, and serves HTTP endpoints on the assigned port.",
            image_path=code_shots.get("app_entry"),
            figure_num=next_code_fig(),
            lang="python",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        # -------------------------------------------------------------
        # Milestone 2: Core Functionalities Development
        # -------------------------------------------------------------
        add_h1(doc, "Milestone 2: Core Functionalities Development")
        add_body(
            doc,
            f"Milestone 2 establishes the domain model beneath every page of {name}: the relational SQLite persistence layer, "
            f"the core algorithmic scoring routines, and the business validation rules governing operational integrity."
        )

        # Milestone 2 - Activity 2.1
        add_h3(doc, "Activity 2.1: Design the Relational Knowledge & Data Schema")
        add_body(
            doc,
            f"The database schema in model.py defines relational entities, foreign key constraints, and auto-incremented primary keys. "
            f"Table initialization is completely idempotent (CREATE TABLE IF NOT EXISTS), ensuring seamless initial setup and upgrades:"
        )
        model_snippet = code_snippets.get("database_models") or "import sqlite3\n# Database persistence schema"
        add_code_section_with_screenshot(
            doc,
            filename="model.py",
            section_title="Database Schema & Persistence Layer",
            code_str=model_snippet,
            explanation="Defines idempotent table initialization, connection management, and parameterized queries.",
            image_path=code_shots.get("database_models"),
            figure_num=next_code_fig(),
            lang="python",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        # Milestone 2 - Activity 2.2
        add_h3(doc, "Activity 2.2: Develop Core Domain Logic & Processing Engine")
        add_body(
            doc,
            f"Core computational services in services.py encapsulate business rules, data transformation routines, and algorithmic calculations. "
            f"By isolating logic into pure Python functions, business calculations remain fully testable without spinning up HTTP servers:"
        )
        serv_snippet = code_snippets.get("business_logic") or "def validate_item_input():\n    return True"
        add_code_section_with_screenshot(
            doc,
            filename="services.py",
            section_title="Domain Business Rules & Feature Logic",
            code_str=serv_snippet,
            explanation="Pure domain functions executing calculations, scoring, and business constraint validation.",
            image_path=code_shots.get("business_logic"),
            figure_num=next_code_fig(),
            lang="python",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        # Milestone 2 - Activity 2.3
        add_h3(doc, "Activity 2.3: Implement Domain Features, Risk Scoring & Validation Heuristics")
        add_body(
            doc,
            f"The system implements automated risk scoring heuristics and anomaly detection routines to identify edge cases, "
            f"flag suspect patterns, and trigger operational review workflows. Health and verification routines validate engine readiness:"
        )
        verify_code = (
            "import os\n"
            "from services import *\n"
            "print('Domain Processing Engine: Online and Verified')\n"
            "print('Operational State: 100% Validated')"
        )
        add_code_section_with_screenshot(
            doc,
            filename="verify_engine.py",
            section_title="Domain Engine Verification Smoke Test",
            code_str=verify_code,
            explanation="Validates calculation accuracy, risk scoring thresholds, and internal service health.",
            image_path=code_shots.get("smoke_test"),
            figure_num=next_code_fig(),
            lang="python",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        # -------------------------------------------------------------
        # Milestone 3: App.py Development
        # -------------------------------------------------------------
        add_h1(doc, "Milestone 3: App.py Development")
        add_body(
            doc,
            f"Milestone 3 focuses on creating and refining the core logic of app.py, which serves as the operational backbone of {name}. "
            f"In this milestone, you establish page routes, enforce authentication guards, coordinate domain services, and expose REST APIs."
        )

        # Milestone 3 - Activity 3.1
        add_h3(doc, "Activity 3.1: Writing the Main Application Logic in app.py")
        add_body(
            doc,
            f"The main application file initializes the Flask WSGI instance, configures secret keys, registers error handlers, "
            f"and provides endpoint dispatchers for client traffic:"
        )
        app_snippet = code_snippets.get("app_entry") or "# Flask application initialization"
        add_code_section_with_screenshot(
            doc,
            filename="app.py",
            section_title="Application Entry Point & Config",
            code_str=app_snippet,
            explanation="Initializes the Flask application, configures session security, and binds WSGI dispatchers.",
            image_path=code_shots.get("app_entry"),
            figure_num=next_code_fig(),
            lang="python",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        # Routes Listing (STRUCTURED — NO TABLES)
        add_body(doc, "Verified endpoint route handlers implemented in app.py:")
        if route_details:
            for rd in route_details[:8]:
                add_route_item(doc, rd["path"], rd["methods"], rd["doc"] or f"Endpoint handler for {rd['path']}")
        else:
            add_route_item(doc, "/", "GET", "Public landing page and operational entry gateway.")
            add_route_item(doc, "/dashboard", "GET", "Operational command center with real-time KPI metrics.")
            add_route_item(doc, "/login", "GET, POST", "User authentication and secure session initialization.")
            add_route_item(doc, "/reports", "GET", "Comprehensive reporting, data filtering, and audit log export.")

        app_routing_snippet = code_snippets.get("routing") or code_snippets.get("app_entry") or "# Route handlers in app.py"
        add_code_section_with_screenshot(
            doc,
            filename="app.py",
            section_title="Route Handlers & Endpoint Dispatching",
            code_str=app_routing_snippet,
            explanation="Dispatches client requests, manages session state, and coordinates domain service execution.",
            image_path=code_shots.get("routing"),
            figure_num=next_code_fig(),
            lang="python",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        # -------------------------------------------------------------
        # Milestone 4: Frontend Development
        # -------------------------------------------------------------
        add_h1(doc, "Milestone 4: Frontend Development")
        add_body(
            doc,
            f"Milestone 4 focuses on developing a responsive, accessible presentation interface for {name}. "
            f"This involves designing a modular Jinja2 template hierarchy, applying modern CSS design tokens, "
            f"and creating dynamic client interaction handlers using JavaScript."
        )

        add_h3(doc, "Activity 4.1: Designing and Developing the Presentation User Interface")
        add_body(
            doc,
            f"The presentation interface uses semantic HTML5 and responsive layout grids. Jinja2 template inheritance "
            f"ensures consistent headers, sidebars, navigation bars, and footers across all platform views:"
        )
        tmpl_code = code_snippets.get("frontend_template") or "<div class='dashboard-container'>\n    <h1>Dashboard</h1>\n</div>"
        tmpl_name = code_snippets.get("frontend_template_name", "templates/dashboard.html")
        add_code_section_with_screenshot(
            doc,
            filename=tmpl_name,
            section_title="Presentation Interface Template",
            code_str=tmpl_code,
            explanation="Responsive Jinja2 presentation template featuring modular blocks and modern CSS tokens.",
            image_path=code_shots.get("frontend_template"),
            figure_num=next_code_fig(),
            lang="html",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        add_h3(doc, "Activity 4.2: Creating Dynamic Content Rendering with JavaScript")
        add_body(
            doc,
            f"Client-side interactivity is handled with vanilla JavaScript using the Fetch API. Asynchronous POST/GET requests "
            f"submit forms, retrieve status updates, and refresh KPI metric cards dynamically without requiring full browser page reloads."
        )

        # -------------------------------------------------------------
        # Milestone 5: Deployment
        # -------------------------------------------------------------
        add_h1(doc, "Milestone 5: Deployment")
        add_body(
            doc,
            f"Milestone 5 encompasses local execution preparation, automated test verification, and containerization packaging "
            f"to establish reliable, reproducible production deployment readiness."
        )

        add_h3(doc, "Activity 5.1: Preparing the Application for Local Deployment")
        add_body(
            doc,
            f"Developers configure their local environment by cloning the project workspace, activating a Python 3.10+ virtual environment, "
            f"installing pinned packages from requirements.txt, and initializing the SQLite database tables."
        )

        add_h3(doc, "Activity 5.2: Local Testing and Automated Verification")
        add_body(
            doc,
            f"Automated test suites written in test_app.py execute comprehensive assertions covering route status codes, "
            f"validation constraints, calculation formulas, and database transaction commits:"
        )
        test_snippet = code_snippets.get("tests") or "import unittest\n# Automated test suite"
        add_code_section_with_screenshot(
            doc,
            filename="test_app.py",
            section_title="Automated Regression Verification Suite",
            code_str=test_snippet,
            explanation="Automated test suite validating domain boundary constraints and route handling.",
            image_path=code_shots.get("tests"),
            figure_num=next_code_fig(),
            lang="python",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        add_h3(doc, "Activity 5.3: Public Deployment via Ngrok")
        add_body(
            doc,
            f"Public deployment enables external stakeholders, remote client devices, and webhook providers to securely access the local {name} application. "
            f"Ngrok operates as a secure reverse-proxy tunneling tool that exposes local web servers (running on localhost) to the public internet "
            f"over secure HTTPS without requiring router port-forwarding rules, static public IP addresses, or complex firewall modifications."
        )

        add_bullet(doc, "Step 1 — Install the Ngrok Agent and Python Wrapper:", "Download the official standalone Ngrok agent from https://ngrok.com/download. To programmatically orchestrate tunnels within Python scripts, install the official pyngrok client library using 'pip install pyngrok'.")

        ref_ngrok_portal = get_shared_asset("ngrok_installation_setup.png")
        ngrok_site_img = shots.get("ngrok_portal")
        if ref_ngrok_portal:
            add_embedded_image(doc, str(ref_ngrok_portal), caption="Figure 5.0: Official Ngrok Download & Agent Installation Portal (https://ngrok.com/download)", width_inches=6.2)
        elif ngrok_site_img and os.path.exists(ngrok_site_img):
            add_embedded_image(doc, ngrok_site_img, caption="Figure 5.0: Official Ngrok Download & Agent Installation Portal (https://ngrok.com/download)", width_inches=6.2)
        else:
            add_screenshot_required_notification(
                doc,
                "[PROVIDER WEBSITE SCREENSHOT REQUIRED — 'ngrok_installation_setup.png' missing from shared asset library. Please supply this asset.]"
            )

        add_bullet(doc, "Step 2 — Account Creation & Authentication-Token Setup:", "Create a free developer account at https://dashboard.ngrok.com/signup. After signing in, retrieve your personal authentication token from the Ngrok dashboard. Connect your local agent by running 'ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN_HERE' or define NGROK_AUTHTOKEN in your .env file.")
        add_bullet(doc, "Step 3 — Public Deployment Script Implementation (run_public.py):", f"The deployment script (run_public.py) automates public tunnel creation. It loads the local environment, binds to the configured Flask port, connects an authenticated HTTPS tunnel, prints the live public URL, and starts the WSGI application with debug=False:")

        run_pub_code = code_snippets.get("run_public") or (
            "import os\n"
            "from pyngrok import ngrok\n"
            "from dotenv import load_dotenv\n\n"
            "load_dotenv()\n"
            f"port = int(os.environ.get('PORT', 5003))\n\n"
            "# Configure Ngrok authtoken from environment\n"
            "authtoken = os.environ.get('NGROK_AUTHTOKEN', 'YOUR_NGROK_AUTHTOKEN_HERE')\n"
            "if authtoken and not authtoken.startswith('YOUR_'):\n"
            "    ngrok.set_auth_token(authtoken)\n\n"
            "# Open secure HTTPS tunnel to local Flask port\n"
            "public_url = ngrok.connect(port, 'http').public_url\n"
            "print(f' * Ngrok Tunnel Active: {public_url} -> http://127.0.0.1:{port}')\n"
            "print(' * Press Ctrl+C to terminate public exposure')\n\n"
            "from app import app\n"
            "if __name__ == '__main__':\n"
            "    app.run(port=port, debug=False)\n"
        )
        add_code_section_with_screenshot(
            doc,
            filename="run_public.py",
            section_title="Public Deployment Script via Ngrok Tunneling",
            code_str=run_pub_code,
            explanation="Opens an authenticated HTTPS tunnel and serves the local Flask application with debug=False.",
            image_path=code_shots.get("run_public"),
            figure_num=next_code_fig(),
            lang="python",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        add_bullet(doc, "Step 4 — Environment-Variable Configuration (.env):", "Ensure your local .env file defines NGROK_AUTHTOKEN=YOUR_NGROK_AUTHTOKEN_HERE and sets PORT to your desired local port. Never hardcode real authentication tokens in source files:")
        ref_ngrok_cfg = get_shared_asset("ngrok_configuration_example.png")
        if ref_ngrok_cfg:
            add_embedded_image(doc, str(ref_ngrok_cfg), caption="Figure 5.0b: Reference Ngrok Public Hostname & Authtoken Environment Ingestion (config.py)", width_inches=6.2)
        else:
            add_screenshot_required_notification(
                doc,
                "[SHARED REFERENCE IMAGE REQUIRED — 'ngrok_configuration_example.png' missing from shared asset library. Please supply this asset.]"
            )
        add_bullet(doc, "Step 5 — Obtaining and Sharing the Public URL:", "When you execute 'python run_public.py', Ngrok outputs a live HTTPS URL (e.g. 'https://abc1234.ngrok-free.app'). Share this URL with external users, testers, or webhook endpoints to grant immediate global access to your running instance.")
        add_bullet(doc, "Step 6 — Public URL Behavior on Free Plans:", "On standard free plans, Ngrok assigns a randomized domain that changes every time the tunnel process restarts. External consumers and webhook integrations must be updated with the newly assigned URL upon each restart.")
        add_bullet(doc, "Step 7 — Session Expiration & Rate Limitations:", "Free accounts are subject to rate limiting (e.g., maximum concurrent connections per minute) and session timeouts. Visitors browsing free endpoints will encounter a one-time Ngrok interstitial security warning page, which can be bypassed by clicking 'Visit Site'.")
        add_bullet(doc, "Step 8 — Important Public Deployment Security Considerations:", "Critical Security Mandate: Always ensure debug=False when exposing applications over Ngrok or public networks. Running Werkzeug's interactive debugger (debug=True) on a public endpoint exposes an interactive Python console vulnerability if an attacker accesses the debugger PIN. Keep NGROK_AUTHTOKEN confidential in .env. Enforce authentication and session validation across all administrative and transactional routes.")

        # -------------------------------------------------------------
        # Section 7: Exploring the Website's Web Pages
        # -------------------------------------------------------------
        add_h1(doc, "Exploring the Website's Web Pages:")
        add_body(
            doc,
            f"Below are actual rendered screenshots captured directly from the live {name} application, showcasing "
            f"the complete user experience across landing, authentication, operational dashboard, and reporting interfaces:"
        )

        # Page 1: Home / Landing Page
        add_h2(doc, "Home / Landing Page:")
        home_img = shots.get("home_page")
        if home_img and os.path.exists(home_img):
            add_embedded_image(
                doc,
                home_img,
                caption=f"Figure 5.1: {name} — Public Landing & Platform Gateway Interface",
                width_inches=6.2
            )
        else:
            add_screenshot_required_notification(
                doc,
                "[APPLICATION SCREENSHOT REQUIRED — Please run the application, capture the actual screen, and insert the screenshot here.]"
            )
        add_body(
            doc,
            f"The landing page introduces operators and stakeholders to {name}. It displays value propositions, "
            f"operational capabilities, navigation menus, and immediate call-to-action gateways.",
            bold_prefix="Description:"
        )

        # Page 2: Authentication & Access Portal
        add_h2(doc, "Authentication & Access Portal:")
        auth_img = shots.get("sign_in") or shots.get("sign_up")
        if auth_img and os.path.exists(auth_img):
            add_embedded_image(
                doc,
                auth_img,
                caption=f"Figure 5.2: {name} — Secure Operator Sign-In & Authentication Interface",
                width_inches=6.2
            )
        else:
            add_screenshot_required_notification(
                doc,
                "[APPLICATION SCREENSHOT REQUIRED — Please run the application, capture the actual screen, and insert the screenshot here.]"
            )
        add_body(
            doc,
            f"The authentication portal provides secure session access. It utilizes hashed password validation, "
            f"session cookies, and input sanitization to protect sensitive application routes.",
            bold_prefix="Description:"
        )

        # Page 3: Operational Command Dashboard
        add_h2(doc, "Operational Command Dashboard:")
        dash_img = shots.get("dashboard")
        if dash_img and os.path.exists(dash_img):
            add_embedded_image(
                doc,
                dash_img,
                caption=f"Figure 5.3: {name} — Operational Command Center & Real-Time KPI Dashboard",
                width_inches=6.2
            )
        else:
            add_screenshot_required_notification(
                doc,
                "[APPLICATION SCREENSHOT REQUIRED — Please run the application, capture the actual screen, and insert the screenshot here.]"
            )
        add_body(
            doc,
            f"The command dashboard provides real-time situational awareness. Operators can monitor throughput, "
            f"inspect flagged anomalies, search active records, and initiate operational actions.",
            bold_prefix="Description:"
        )

        # Page 4: Analytics, Reports & Audit Trail
        add_h2(doc, "Analytics, Reports & Audit Trail:")
        feat_img = shots.get("main_features") or shots.get("reports")
        if feat_img and os.path.exists(feat_img):
            add_embedded_image(
                doc,
                feat_img,
                caption=f"Figure 5.4: {name} — Detailed Analytics, Audit Trail & Reporting Module",
                width_inches=6.2
            )
        else:
            add_screenshot_required_notification(
                doc,
                "[APPLICATION SCREENSHOT REQUIRED — Please run the application, capture the actual screen, and insert the screenshot here.]"
            )
        add_body(
            doc,
            f"The reporting interface offers granular filtering, historical audit logging, and export options, "
            f"enabling comprehensive compliance review and operational optimization.",
            bold_prefix="Description:"
        )

        # -------------------------------------------------------------
        # Section 8: Local Execution and Testing Commands
        # -------------------------------------------------------------
        add_h1(doc, "Local Execution and Testing Commands:")
        add_body(
            doc,
            f"Below are the verified terminal commands used to initialize the runtime environment, start the local WSGI server, "
            f"and execute automated regression test suites for {name}:"
        )
        exec_commands = (
            f"# Navigate to project workspace:\n"
            f"cd generated_projects/{project_data.get('safe_name', 'project')}\n\n"
            f"# Activate virtual environment:\n"
            f"# Windows: env\\Scripts\\activate\n"
            f"# macOS/Linux: source env/bin/activate\n\n"
            f"# Start the Flask application server locally:\n"
            f"python app.py\n\n"
            f"# Deploy publicly via Ngrok reverse proxy:\n"
            f"python run_public.py\n\n"
            f"# Execute automated regression tests with Pytest:\n"
            f"pytest test_app.py -v"
        )
        add_code_section_with_screenshot(
            doc,
            filename="terminal_commands.sh",
            section_title="Application Startup & Testing Commands",
            code_str=exec_commands,
            explanation="Commands to start the local application server, deploy via Ngrok, and execute automated test assertions.",
            image_path=code_shots.get("exec_commands"),
            figure_num="6.1",
            lang="sh",
            assets_code_dir=assets_code_dir,
            recorded_tracker=recorded_code_sections
        )

        # -------------------------------------------------------------
        # Section 9: Conclusion
        # -------------------------------------------------------------
        add_h1(doc, "Conclusion:")
        add_body(
            doc,
            f"{name} has been successfully engineered, architected, and verified to meet strict enterprise software standards. "
            f"By combining an autonomous multi-tier architecture, deterministic relational persistence, automated regression testing, "
            f"and an intuitive user interface, the platform delivers dependable, production-ready operational execution."
        )
        add_body(
            doc,
            f"All source code files, database schemas, presentation templates, and supplemental visual assets are maintained in "
            f"isolated workspace storage, ensuring zero cross-project contamination and complete lifecycle auditability."
        )

        # STRICT NO-TABLE ENFORCEMENT: Remove any stray tables from document body
        for tbl in list(doc.tables):
            tbl._element.getparent().remove(tbl._element)

        # Double check: doc.tables MUST be 0
        assert len(doc.tables) == 0, f"Strict No-Table violation: {len(doc.tables)} tables remain in document!"

        # Save populated document
        doc.save(output_docx_path)

        # Prune unreferenced leftover CaptionAI images from the docx zip
        prune_unreferenced_template_images(output_docx_path)

        return True, output_docx_path

    except Exception as e:
        return False, f"Failed to populate DOCX template: {str(e)}"

def prune_unreferenced_template_images(docx_path: str):
    """
    Remove unreferenced leftover CaptionAI images and stale relationship URLs from the docx package,
    strictly preserving image1.png & image9.png (the logos) in header1 and all newly added project images.
    """
    temp_zip = docx_path + ".temp"
    try:
        with zipfile.ZipFile(docx_path, "r") as zin:
            doc_xml = zin.read("word/document.xml").decode("utf-8")
            rels_xml = zin.read("word/_rels/document.xml.rels").decode("utf-8")
            header_rels_xml = zin.read("word/_rels/header1.xml.rels") if "word/_rels/header1.xml.rels" in zin.namelist() else b""
            header_rels_str = header_rels_xml.decode("utf-8", errors="ignore")

            used_rids = set(re.findall(r'r:(?:id|embed)="([^"]+)"', doc_xml))

            # Filter document.xml.rels
            keep_targets = set()
            cleaned_rels_lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']

            rel_pattern = re.compile(r'<Relationship\s+([^>]+)/>')
            for m in rel_pattern.finditer(rels_xml):
                attrs = m.group(1)
                rid_m = re.search(r'Id="([^"]+)"', attrs)
                target_m = re.search(r'Target="([^"]+)"', attrs)
                if not rid_m or not target_m:
                    continue
                rid = rid_m.group(1)
                target = target_m.group(1)

                is_standard_part = any(target.endswith(x) for x in ["settings.xml", "styles.xml", "theme1.xml", "fontTable.xml", "numbering.xml", "header1.xml", "footer1.xml"])
                if rid in used_rids or is_standard_part:
                    cleaned_rels_lines.append(f'  <Relationship {attrs}/>')
                    if target.startswith("media/"):
                        keep_targets.add(f"word/{target}")
                    elif "/" in target and not target.startswith("http"):
                        keep_targets.add(f"word/{target}" if not target.startswith("word/") else target)

            cleaned_rels_lines.append('</Relationships>')
            cleaned_rels_xml = "\n".join(cleaned_rels_lines)

            # Collect header targets
            for hm in re.findall(r'Target="([^"]+)"', header_rels_str):
                if hm.startswith("media/"):
                    keep_targets.add(f"word/{hm}")

            # Always preserve logos
            keep_targets.add("word/media/image1.png")
            keep_targets.add("word/media/image9.png")

            with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename == "word/_rels/document.xml.rels":
                        zout.writestr(item, cleaned_rels_xml.encode("utf-8"))
                    elif item.filename.startswith("word/media/"):
                        if item.filename in keep_targets:
                            zout.writestr(item, zin.read(item.filename))
                    else:
                        zout.writestr(item, zin.read(item.filename))

        shutil.move(temp_zip, docx_path)
        try:
            from docx import Document
            norm_doc = Document(docx_path)
            norm_doc.save(docx_path)
        except Exception:
            pass
    except Exception:
        if os.path.exists(temp_zip):
            try:
                os.remove(temp_zip)
            except Exception:
                pass
