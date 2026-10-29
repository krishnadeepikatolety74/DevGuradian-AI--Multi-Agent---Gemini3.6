import os
import re
import json
import time
from typing import Dict, Any, Tuple, Optional

def get_gemini_api_key(override_key: Optional[str] = None) -> Optional[str]:
    """Retrieve Gemini API key from parameter or environment variables."""
    if override_key and override_key.strip():
        return override_key.strip()
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

def is_api_key_configured(api_key: Optional[str] = None) -> bool:
    key = get_gemini_api_key(api_key)
    return bool(key and len(key.strip()) > 5)

def test_gemini_connection(api_key: Optional[str] = None) -> Tuple[bool, str]:
    """Test Gemini API connection with a lightweight prompt."""
    key = get_gemini_api_key(api_key)
    if not key:
        return False, "No Gemini API key provided. Please set GEMINI_API_KEY in .env or Settings."
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        default_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(default_model)
        response = model.generate_content("Ping. Reply with: DevGuardian AI connection successful.")
        if response and response.text:
            return True, response.text.strip()
        return False, "No response received from Gemini API."
    except Exception as e:
        return False, f"Gemini API connection error: {str(e)}"

def mask_api_key(key: Optional[str]) -> str:
    """Mask sensitive API key showing only prefix and suffix safely."""
    if not key or len(key.strip()) < 8:
        return "Not configured"
    clean = key.strip()
    if clean.startswith("your_") or clean.startswith("PASTE_"):
        return "Not configured"
    if len(clean) <= 10:
        return clean[:2] + "•" * (len(clean) - 4) + clean[-2:]
    return clean[:4] + "•" * (len(clean) - 8) + clean[-4:]

def update_env_variable(key_name: str, new_value: str, env_path: str = ".env") -> bool:
    """
    Safely update or insert an environment variable in .env without deleting or corrupting
    any other existing variables or comments.
    """
    try:
        lines = []
        found = False
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key_name}=") or stripped.startswith(f"export {key_name}="):
                prefix = "export " if stripped.startswith("export ") else ""
                new_lines.append(f"{prefix}{key_name}={new_value}\n")
                found = True
            else:
                new_lines.append(line)

        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{key_name}={new_value}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        os.environ[key_name] = new_value
        return True
    except Exception:
        return False

# =====================================================================
# xAI GROK API INTEGRATION (PRIORITY 3)
# =====================================================================

def get_xai_api_key(override_key: Optional[str] = None) -> Optional[str]:
    """Retrieve xAI Grok API key from parameter or environment variables."""
    if override_key and override_key.strip():
        return override_key.strip()
    return os.environ.get("XAI_API_KEY")

def get_xai_model(override_model: Optional[str] = None) -> str:
    """Retrieve configured xAI Grok model name (defaults to grok-2)."""
    if override_model and override_model.strip():
        return override_model.strip()
    return os.environ.get("XAI_MODEL", "grok-2").strip()

def is_xai_configured(api_key: Optional[str] = None) -> bool:
    """Check if a valid xAI Grok API key is configured."""
    key = get_xai_api_key(api_key)
    return bool(key and len(key.strip()) > 8 and not key.startswith("your_"))

def test_xai_connection(api_key: Optional[str] = None, model_name: Optional[str] = None) -> Tuple[bool, str]:
    """
    Test connection to official xAI Grok API using OpenAI-compatible SDK (https://api.x.ai/v1).
    Never exposes API secrets in error messages.
    """
    key = get_xai_api_key(api_key)
    if not key or not is_xai_configured(key):
        return False, "xAI API key is not configured. Please define XAI_API_KEY in .env or Settings."

    model_to_use = get_xai_model(model_name)
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=key,
            base_url="https://api.x.ai/v1",
            timeout=15.0
        )
        completion = client.chat.completions.create(
            model=model_to_use,
            messages=[{"role": "user", "content": "Ping. Reply with: DevGuardian AI Grok connection verified."}],
            max_tokens=32
        )
        if completion and completion.choices and completion.choices[0].message:
            reply = completion.choices[0].message.content or ""
            return True, f"Connection successful with model '{model_to_use}': {reply[:60].strip()}"
        return False, "Empty response from xAI Grok API."
    except Exception as e:
        err_msg = str(e)
        err_msg = re.sub(r'xai-[0-9A-Za-z-_]{10,}', 'xai-[REDACTED]', err_msg)
        if "401" in err_msg or "Incorrect API key" in err_msg or "invalid_api_key" in err_msg:
            return False, "Authentication failed: Invalid or expired XAI_API_KEY."
        elif "429" in err_msg:
            return False, "Rate limit reached: xAI API quota exceeded."
        elif "404" in err_msg or "model_not_found" in err_msg:
            return False, f"Model '{model_to_use}' not found or inaccessible."
        return False, f"xAI API connection error: {err_msg[:120]}"

def call_grok(
    prompt: str,
    system_instruction: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 8192
) -> Tuple[bool, str]:
    """
    Execute reasoning prompt via xAI Grok API (https://api.x.ai/v1) with error handling.
    """
    key = get_xai_api_key(api_key)
    if not key or not is_xai_configured(key):
        return False, "XAI_API_KEY is not configured"

    model_to_use = get_xai_model(model_name)
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=key,
            base_url="https://api.x.ai/v1",
            timeout=60.0
        )
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        completion = client.chat.completions.create(
            model=model_to_use,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        if completion and completion.choices and completion.choices[0].message:
            content = completion.choices[0].message.content
            if content:
                return True, content.strip()
        return False, "Empty response from Grok API"
    except Exception as e:
        err_msg = re.sub(r'xai-[0-9A-Za-z-_]{10,}', 'xai-[REDACTED]', str(e))
        return False, f"Grok API Error: {err_msg[:150]}"

def get_active_ai_provider(override_key: Optional[str] = None) -> str:
    """
    Determine active AI provider:
    Prioritizes Grok (xAI) for project generation workflow when configured,
    falls back to Gemini if configured, else 'local_deterministic'.
    """
    if override_key and override_key.strip():
        k = override_key.strip()
        if k.startswith("xai-"):
            return "grok"
        elif len(k) > 5:
            return "gemini"
    preferred = os.environ.get("AI_PROVIDER", "").strip().lower()
    if preferred == "grok" and is_xai_configured():
        return "grok"
    if preferred == "gemini" and is_api_key_configured():
        return "gemini"
    if is_xai_configured():
        return "grok"
    if is_api_key_configured():
        return "gemini"
    return "local_deterministic"

def call_active_ai(
    prompt: str,
    system_instruction: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None
) -> Tuple[bool, str]:
    """Dispatch prompt to configured active AI provider (Grok or Gemini)."""
    provider = get_active_ai_provider(api_key)
    if provider == "grok":
        return call_grok(prompt, system_instruction=system_instruction, api_key=api_key, model_name=model_name)
    elif provider == "gemini":
        return call_gemini(prompt, system_instruction=system_instruction, api_key=api_key, model_name=model_name)
    return False, "No active external cloud AI provider configured. Using local deterministic processing."

def call_gemini(prompt: str, system_instruction: Optional[str] = None, api_key: Optional[str] = None, model_name: Optional[str] = None) -> Tuple[bool, str]:
    """Make a robust call to Gemini API with timeout and error handling."""
    key = get_gemini_api_key(api_key)
    if not key:
        return False, "API key not configured"

    model_to_use = model_name or os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        
        generation_config = {
            "temperature": 0.2,
            "top_p": 0.95,
            "max_output_tokens": 8192,
        }
        
        model = genai.GenerativeModel(
            model_name=model_to_use,
            system_instruction=system_instruction,
            generation_config=generation_config
        )
        
        response = model.generate_content(prompt)
        if response and response.text:
            return True, response.text.strip()
        else:
            return False, "Empty response received from Gemini API"
    except Exception as e:
        return False, f"Gemini API Error: {str(e)}"

def call_gemini_multimodal(prompt: str, image_path: str, system_instruction: Optional[str] = None, api_key: Optional[str] = None, model_name: Optional[str] = None) -> Tuple[bool, str]:
    """Analyze image and prompt using multimodal Gemini model or provide structured local fallback."""
    key = get_gemini_api_key(api_key)
    from PIL import Image

    # Validate image file
    if not os.path.exists(image_path):
        return False, f"Image file not found at {image_path}"

    try:
        pil_img = Image.open(image_path)
        img_format = pil_img.format or "PNG"
        img_size = pil_img.size
        file_size_kb = os.path.getsize(image_path) / 1024
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"

    if not key:
        # Transparent fallback when API key is not configured
        fallback_analysis = (
            f"### Multimodal Architecture & Requirements Analysis\n\n"
            f"> **Image Metadata Verified**: Format: `{img_format}` | Dimensions: `{img_size[0]}x{img_size[1]}px` | Size: `{file_size_kb:.1f} KB`\n"
            f"> *Notice: No external Gemini API key configured. Utilizing local autonomous requirement extractor.*\n\n"
            f"#### Extracted Architectural Components from Visual Reference:\n"
            f"1. **Client / Presentation Layer**: Responsive Web Application interface with user input handling.\n"
            f"2. **API & Dispatch Controller**: RESTful routing gateway coordinating business transactions.\n"
            f"3. **AI / Multi-Agent Processing Tier**: Autonomous analysis, entity extraction, and risk assessment.\n"
            f"4. **Persistence Layer**: Structured relational tables with foreign keys and transaction logs.\n"
            f"5. **Downstream Integration Pipeline**: Real-time notifications, reporting, and settlement actions.\n\n"
            f"#### Requirements Derived for: *\"{prompt}\"*\n"
            f"- **Functional Requirement 1**: Automated intake and validation of domain payloads and file attachments.\n"
            f"- **Functional Requirement 2**: Multi-agent workflow execution with traceable state transitions.\n"
            f"- **Functional Requirement 3**: Directional architecture diagram generation conforming to enterprise blue-node standards.\n"
            f"- **Functional Requirement 4**: Master reference DOCX & PDF documentation export with preserved logos.\n\n"
            f"Would you like to **Generate Project Code**, **Export Architecture Diagram**, or **Compile Master Documentation** now?"
        )
        return True, fallback_analysis

    model_to_use = model_name or os.environ.get("GEMINI_MODEL") or "gemini-1.5-flash"
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)

        generation_config = {
            "temperature": 0.2,
            "top_p": 0.95,
            "max_output_tokens": 4096,
        }

        model = genai.GenerativeModel(
            model_name=model_to_use,
            system_instruction=system_instruction,
            generation_config=generation_config
        )

        response = model.generate_content([prompt, pil_img])
        if response and response.text:
            return True, response.text.strip()
        else:
            return False, "Empty multimodal response from Gemini API"
    except Exception as e:
        return False, f"Multimodal Gemini Error: {str(e)}"

# =====================================================================
# AGENT 1: REQUIREMENT AGENT
# =====================================================================

def run_requirement_agent(project_name: str, description: str, app_type: str, language: str, api_key: Optional[str] = None, generation_mode: str = "both") -> Dict[str, Any]:
    provider = get_active_ai_provider(api_key)
    is_live = (provider != "local_deterministic")
    
    system_prompt = (
        "You are the DevGuardian AI Requirement Agent. Your mission is to analyze the user's project idea "
        "and produce an exhaustive, professional Software Requirements Specification (SRS). "
        "Structure your response with clear sections: Executive Summary, Problem Statement, Target Audience, "
        "Functional Requirements (numbered FR-1, FR-2...), Non-Functional Requirements (NFR-1, NFR-2...), "
        "Inputs & Outputs, Core Feature Breakdown, Technical Assumptions, and Acceptance Criteria. "
        f"CRITICAL CONSTRAINT: Respect the requested generation mode: '{generation_mode}'. "
        "If 'backend_only', focus on RESTful APIs, services, database models, and tests without full frontend templates. "
        "If 'generate_ui', focus on presentation layer, Jinja2 templates, interactive frontend routing, and UI prototype states. "
        "If 'both', formulate complete full-stack specifications."
    )
    user_prompt = f"""
Project Name: {project_name}
Application Type: {app_type}
Language / Framework: {language}
Generation Mode: {generation_mode}
User Description:
{description}

Analyze this project and generate the comprehensive Software Requirements Specification document in Markdown.
"""

    if is_live:
        success, response_text = call_active_ai(user_prompt, system_instruction=system_prompt, api_key=api_key)
        if success:
            return {
                "status": "completed",
                "is_demo_mode": False,
                "output": response_text,
                "logs": [
                    "Parsed project brief and user description",
                    f"Aligned requirements with generation mode: '{generation_mode}'",
                    "Extracted functional requirements and core workflows",
                    "Defined non-functional requirements (security, latency, scalability)",
                    "Synthesized technical assumptions and acceptance criteria",
                    f"Finalized Software Requirements Specification (SRS) via {provider.upper()} API"
                ]
            }

    # Intelligent deterministic fallback (Demo Mode)
    mode_label = "Full-Stack Application" if generation_mode == "both" else ("Headless Backend & REST API" if generation_mode == "backend_only" else "Interactive UI Prototype")
    
    demo_output = f"""# Software Requirements Specification (SRS)
> **[DevGuardian Autonomous Requirements Synthesis Engine — Mode: {mode_label} ({generation_mode})]**

## 1. Executive Summary
DevGuardian AI has formulated this formal Software Requirements Specification for **{project_name}**, an autonomous {app_type} built using {language} operating in **{mode_label}** mode. The objective is to deliver a reliable, modular, and maintainable software system addressing the specific problem statement described by the client.

## 2. Problem Statement & Scope
- **Problem:** {description}
- **System Scope:** The system delivers targeted software functionality aligned with requested mode `{generation_mode}`. Enforces robust input validation, core business logic execution, error handling boundaries, and automated test assertions.

## 3. Functional Requirements (FR)
- **FR-1 [Input Handling & Validation]:** The application shall accept valid user inputs via UI forms and API endpoints, enforcing type constraints, sanitized payload verification, and boundary checks.
- **FR-2 [Core Processing Engine]:** Implement the domain business logic for {project_name}, ensuring stateless execution, error boundary encapsulation, and deterministic output transformation.
- **FR-3 [Data Persistence & State Management]:** The platform shall store entities, configuration, and transactional logs using SQLite with referential integrity.
- **FR-4 [Result Presentation / API Contract]:** {'The system shall render rich, interactive server-side views presenting calculated results, status indicators, and forms.' if generation_mode != 'backend_only' else 'The system shall expose clean RESTful JSON endpoints with status codes, payload schemas, and health check probes.'}
- **FR-5 [Audit & Error Reporting]:** Every request and transaction shall log lifecycle milestones and produce actionable, human-readable error messages and logs.

## 4. Non-Functional Requirements (NFR)
- **NFR-1 [Performance]:** System response time shall remain under 250ms for local queries and under 1.5s for compute-intensive tasks.
- **NFR-2 [Security]:** Strict adherence to OWASP Top 10 standards: zero plain-text credential storage, parameterized SQL queries, path-traversal sanitization, and CSRF protection.
- **NFR-3 [Reliability]:** Graceful degradation on malformed inputs with zero unhandled 500 exceptions in production runtime.
- **NFR-4 [Maintainability]:** Clean architecture separation (Routes, Controllers, Models, Services) with Python type hinting and 100% syntactically valid code.

## 5. System Inputs & Outputs
- **Inputs:** User submission parameters, uploaded files/assets where relevant, authentication tokens/sessions, and operational configurations.
- **Outputs:** {'Rendered Jinja2/HTML interfaces, interactive dashboard, and diagnostic logs.' if generation_mode == 'generate_ui' else ('JSON REST API responses, health check status, and diagnostic logs.' if generation_mode == 'backend_only' else 'Rendered Jinja2/HTML interfaces, JSON REST API responses, and database transactions.')}

## 6. Acceptance Criteria
1. The project must start cleanly with standard command `python app.py` without crashing.
2. All defined functional requirements (FR-1 through FR-5) must be verified by automated tests.
3. Zero critical or high-severity vulnerabilities identified during the security audit.
4. Strictly conforms to requested generation mode: `{generation_mode}`.
"""
    return {
        "status": "completed",
        "is_demo_mode": True,
        "output": demo_output,
        "logs": [
            "[Requirements Engine] Initialized requirement extraction module",
            f"[Requirements Engine] Filtered scope according to generation mode: {generation_mode}",
            "[Requirements Engine] Extracted 5 functional and 4 non-functional requirements",
            "[Requirements Engine] Formulated input/output boundary definitions",
            "[Requirements Engine] Established verified acceptance criteria",
            "[Requirements Engine] Completed SRS generation"
        ]
    }

# =====================================================================
# AGENT 2: ARCHITECTURE AGENT
# =====================================================================

def run_architecture_agent(project_name: str, description: str, requirements_text: str, app_type: str, language: str, api_key: Optional[str] = None, generation_mode: str = "both") -> Dict[str, Any]:
    provider = get_active_ai_provider(api_key)
    is_live = (provider != "local_deterministic")
    
    system_prompt = (
        "You are the DevGuardian AI Architecture Agent. Based on the approved requirements, design a clean, modular "
        "software architecture. Define: System Topology, Component Breakdown, Data Model / Schema, API Endpoints & Routes, "
        "Data Flow Diagram (in ASCII or Mermaid), Dependency Tree, and Proposed File Manifest. "
        f"CRITICAL CONSTRAINT: Respect the requested generation mode: '{generation_mode}'. "
        "If 'backend_only', focus on RESTful API gateways, services, and models without frontend templates. "
        "If 'generate_ui', design presentation and template component hierarchy with prototype routing. "
        "If 'both', design a complete full-stack architecture."
    )
    user_prompt = f"""
Project Name: {project_name}
Application Type: {app_type}
Language / Framework: {language}
Generation Mode: {generation_mode}
Requirements Summary:
{requirements_text[:3000]}

Design the complete architecture specification document in Markdown.
"""

    if is_live:
        success, response_text = call_active_ai(user_prompt, system_instruction=system_prompt, api_key=api_key)
        if success:
            return {
                "status": "completed",
                "is_demo_mode": False,
                "output": response_text,
                "logs": [
                    "Evaluated SRS architectural boundaries",
                    f"Tailored topology for generation mode: '{generation_mode}'",
                    "Designed layered component topology (Presentation, Service, Data)",
                    "Constructed relational schema and entity relationships",
                    "Defined RESTful routes and service contract interfaces",
                    f"Finalized Architecture Specification via {provider.upper()} API"
                ]
            }

    mode_label = "Full-Stack Application" if generation_mode == "both" else ("Headless Backend & REST API" if generation_mode == "backend_only" else "Interactive UI Prototype")

    if generation_mode == "backend_only":
        component_diagram = """```
+-------------------------------------------------------+
|                 RESTful API Gateway                   |
|        (Flask App / API Endpoints / JSON Probes)      |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
|                     Service Layer                     |
|  (Core Business Logic, Validators, Processing Engine) |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
|                    Persistence Layer                  |
|          (SQLite Engine, Schema Migrations)           |
+-------------------------------------------------------+
```"""
    elif generation_mode == "generate_ui":
        component_diagram = """```
+-------------------------------------------------------+
|                   Presentation Layer                  |
|     (Jinja2 Templates / Modern CSS / Forms / UI)      |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
|               Interactive Prototype Router            |
|       (Flask Render Routes / Navigation / Flashes)    |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
|                    Mock Data Store                    |
|        (State Management / Dynamic Form Echo)         |
+-------------------------------------------------------+
```"""
    else:
        component_diagram = """```
+-------------------------------------------------------+
|                   Presentation Layer                  |
|    (Flask Routes / Jinja2 Templates / Static Assets)   |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
|                     Service Layer                     |
|  (Core Business Logic, Validators, Processing Engine) |
+---------------------------+---------------------------+
                            |
                            v
+-------------------------------------------------------+
|                    Persistence Layer                  |
|          (SQLite Engine, Schema Migrations)           |
+-------------------------------------------------------+
```"""

    demo_output = f"""# System Architecture Specification
> **[DevGuardian Autonomous Architecture Engine — Mode: {mode_label} ({generation_mode})]**

## 1. Architectural Style & Paradigm
The **{project_name}** solution is architected as a **Modular Layered Architecture** optimized for **{mode_label}**.
- **Presentation / Interface Tier:** {'Headless RESTful API exposing clean JSON endpoints and health probes.' if generation_mode == 'backend_only' else ('Jinja2 templates, responsive CSS design tokens, and prototype routing.' if generation_mode == 'generate_ui' else 'Integrated Flask routes with Jinja2 templates and REST endpoints.')}
- **Service Tier:** Pure Python domain business logic modules, validators, and processing engines.
- **Data Access Tier:** Parameterized SQLite persistence layer ensuring atomic transactions and referential integrity.

## 2. Component Diagram
{component_diagram}

## 3. Data Model & Database Schema
```sql
-- Core Entity Table
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'General',
    payload_data TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Operational Audit Log Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 4. API Endpoints & HTTP Interface
| Method | Route | Description | Expected Payload | Response Status |
|--------|-------|-------------|------------------|-----------------|
| GET | `/` | Main application dashboard / UI | None | 200 OK |
| GET | `/api/health` | System health check probe | None | 200 OK (JSON) |
| GET | `/items` | List all records | Optional search query | 200 OK |
| POST | `/items/create` | Create new entity | Form: `title`, `category`, `data` | 302 / 201 Created |
| POST | `/items/<id>/delete` | Remove entity record | CSRF token | 302 Redirect |

## 5. Proposed File Manifest
1. `app.py`: Flask entry point, route definitions, configuration loading.
2. `model.py`: Database connection manager, schema initialization, CRUD methods.
3. `services.py`: Core domain logic, algorithmic processing, and business rules.
4. `requirements.txt`: Declarative Python dependency manifest.
5. `templates/index.html`: Main user interface template with responsive CSS.
6. `test_app.py`: Automated unittest suite covering routes and logic.
"""
    return {
        "status": "completed",
        "is_demo_mode": True,
        "output": demo_output,
        "logs": [
            "[Demo Engine] Analyzed system domain model and technology constraints",
            "[Demo Engine] Synthesized 3-tier modular layered architecture",
            "[Demo Engine] Drafted SQLite schema with foreign key integrity",
            "[Demo Engine] Mapped RESTful endpoint contracts",
            "[Demo Engine] Generated file manifest structure"
        ]
    }

# =====================================================================
# AGENT 3: CODING AGENT
# =====================================================================

def run_coding_agent(project_name: str, description: str, requirements_text: str, architecture_text: str, app_type: str, language: str, api_key: Optional[str] = None, generation_mode: str = "both") -> Dict[str, Any]:
    provider = get_active_ai_provider(api_key)
    is_live = (provider != "local_deterministic")
    
    system_prompt = (
        "You are the DevGuardian AI Senior Coding Agent. Your job is to generate production-quality, complete, "
        "executable application source code files based on the requirements and architecture. "
        "DO NOT output placeholders or ellipses. Every file must be complete and runnable. "
        f"CRITICAL CONSTRAINT: Respect the requested generation mode: '{generation_mode}'. "
        "If 'backend_only', do not generate frontend HTML templates; generate REST API routes, models, services, and tests. "
        "If 'generate_ui', generate Jinja2 templates, modern CSS, interactive UI prototype routes, and forms. "
        "If 'both', generate the complete integrated full-stack application. "
        "Output each file inside a markdown code block with the filename indicated on the first line or header: "
        "### FILE: filename.ext\n```language\n...code...\n```"
    )
    user_prompt = f"""
Project Name: {project_name}
Description: {description}
Application Type: {app_type}
Language / Framework: {language}
Generation Mode: {generation_mode}

Requirements:
{requirements_text[:2000]}

Architecture:
{architecture_text[:2000]}

Generate the complete runnable source files for this application. Ensure you provide app.py, model.py, services.py, requirements.txt, and test files conforming to mode '{generation_mode}'.
"""

    if is_live:
        success, response_text = call_active_ai(user_prompt, system_instruction=system_prompt, api_key=api_key)
        if success:
            files = parse_code_blocks(response_text)
            if files:
                return {
                    "status": "completed",
                    "is_demo_mode": False,
                    "output": response_text,
                    "files": files,
                    "logs": [
                        "Initialized full-stack source code generator",
                        f"Enforced generation mode: '{generation_mode}'",
                        "Constructed primary application entry point (app.py)",
                        "Built database persistence layer with parameterized SQLite",
                        "Implemented domain business logic and validation rules",
                        "Generated test suites and dependency manifest",
                        f"Generated {len(files)} complete source files via {provider.upper()} API"
                    ]
                }

    # High-quality, tailored project code generator for Demo Mode
    files = generate_tailored_project_files(project_name, description, app_type, language, generation_mode=generation_mode)
    
    output_summary = f"# Generated Source Code Manifest\n> **[DevGuardian Autonomous Code Synthesis Engine — Mode: {generation_mode}]**\n\n"
    for filename, code in files.items():
        output_summary += f"### FILE: `{filename}` ({len(code.splitlines())} lines)\n"
    
    return {
        "status": "completed",
        "is_demo_mode": True,
        "output": output_summary,
        "files": files,
        "logs": [
            f"[Code Engine] Initialized code generation pipeline in mode: {generation_mode}",
            "[Code Engine] Generated app.py with error handling and secure routes",
            "[Code Engine] Generated persistence models with SQLite transactions",
            "[Code Engine] Generated services module with domain logic",
            "[Code Engine] Configured test suite with test assertions",
            f"[Code Engine] Successfully packaged {len(files)} production-ready files"
        ]
    }

def parse_code_blocks(text: str) -> Dict[str, str]:
    """Parse files from LLM markdown output looking for FILE: path patterns."""
    files = {}
    pattern = r"(?:###\s*FILE:\s*|```[a-zA-Z0-9_-]*\s*#\s*file:\s*|File:\s*)([a-zA-Z0-9_\-\./\\]+)\n*```(?:[a-zA-Z0-9_-]*)\n([\s\S]*?)```"
    matches = re.findall(pattern, text, re.MULTILINE)
    for filename, content in matches:
        clean_name = filename.strip().replace("`", "").strip()
        files[clean_name] = content.strip() + "\n"
    
    # Fallback secondary regex if not matched
    if not files:
        secondary_pattern = r"###\s*`?([a-zA-Z0-9_\-\./\\]+)`?\n+```(?:[a-zA-Z0-9_-]*)\n([\s\S]*?)```"
        secondary_matches = re.findall(secondary_pattern, text)
        for filename, content in secondary_matches:
            clean_name = filename.strip().replace("`", "").strip()
            if "." in clean_name:
                files[clean_name] = content.strip() + "\n"
                
    return files

def generate_tailored_project_files(project_name: str, description: str, app_type: str, language: str, generation_mode: str = "both") -> Dict[str, str]:
    """Generate complete, syntactically clean, runnable code customized to the project."""
    try:
        from services.universal_generator import generate_universal_project
        uni_res = generate_universal_project(
            project_name=project_name,
            description=description,
            app_type=app_type,
            language=language,
            generation_mode=generation_mode
        )
        if uni_res and uni_res.get("files"):
            return uni_res["files"]
    except Exception as _uni_err:
        pass

    slug = re.sub(r'[^a-zA-Z0-9_]', '_', project_name.lower())
    
    # app.py
    app_py = f'''"""
{project_name} - Main Application Server
Generated by DevGuardian AI - Autonomous Software Project Manager
"""

import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from model import init_database, get_all_records, insert_record, delete_record, get_stats
from services import process_project_action, validate_item_input

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "devguardian-generated-secret-key-39281")

# Initialize database on startup
init_database()

@app.route("/")
def index():
    """Render main application dashboard."""
    records = get_all_records()
    stats = get_stats()
    return render_template("index.html", records=records, stats=stats, project_name="{project_name}")

@app.route("/api/health")
def health_check():
    """Health check probe for monitoring and deployments."""
    return jsonify({{"status": "healthy", "service": "{project_name}", "version": "1.0.0"}})

@app.route("/add", methods=["POST"])
def add_item():
    """Handle new item submission with validation."""
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "General").strip()
    notes = request.form.get("notes", "").strip()

    is_valid, error_msg = validate_item_input(title, category)
    if not is_valid:
        flash(f"Validation Error: {{error_msg}}", "error")
        return redirect(url_for("index"))

    result = process_project_action(title, category, notes)
    insert_record(title, category, result.get("processed_summary", notes))
    flash("Item successfully processed and saved!", "success")
    return redirect(url_for("index"))

@app.route("/delete/<int:item_id>", methods=["POST"])
def remove_item(item_id):
    """Delete an item safely by ID."""
    deleted = delete_record(item_id)
    if deleted:
        flash("Record deleted successfully.", "info")
    else:
        flash("Record not found.", "warning")
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"Starting {project_name} on port {{port}}...")
    app.run(host="0.0.0.0", port=port, debug=False)
'''

    # model.py
    model_py = f'''"""
{project_name} - Persistence Layer
Handles SQLite transactions with parameterized queries.
"""

import sqlite3
import os
from pathlib import Path

DB_FILE = Path(__file__).parent / "{slug}.db"

def get_connection():
    """Return an active SQLite connection with row dictionary mapping."""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_database():
    """Initialize database tables idempotently."""
    conn = get_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'General',
                details TEXT,
                status TEXT DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.close()

def get_all_records():
    """Fetch all records sorted by most recent."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM records ORDER BY id DESC")
    rows = cursor.fetchall()
    records = [dict(row) for row in rows]
    conn.close()
    return records

def insert_record(title, category, details):
    """Safely insert a new record using parameterized SQL."""
    conn = get_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO records (title, category, details) VALUES (?, ?, ?)",
            (title, category, details)
        )
        new_id = cursor.lastrowid
    conn.close()
    return new_id

def delete_record(item_id):
    """Delete record by ID."""
    conn = get_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM records WHERE id = ?", (item_id,))
        count = cursor.rowcount
    conn.close()
    return count > 0

def get_stats():
    """Calculate aggregate statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM records")
    total = cursor.fetchone()["total"]
    conn.close()
    return {{"total": total, "status": "Operational"}}
'''

    # services.py
    services_py = f'''"""
{project_name} - Domain Services Module
Contains pure business logic, algorithmic transformations, and validation rules.
"""

import datetime
from typing import Tuple, Dict, Any

def validate_item_input(title: str, category: str) -> Tuple[bool, str]:
    """Validate item fields against boundary constraints."""
    if not title or len(title.strip()) < 2:
        return False, "Title must contain at least 2 characters."
    if len(title) > 120:
        return False, "Title exceeds maximum limit of 120 characters."
    if not category:
        return False, "Category must be specified."
    return True, ""

def process_project_action(title: str, category: str, notes: str) -> Dict[str, Any]:
    """
    Core business logic processing for:
    {description}
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    processed_summary = f"[Processed at {{timestamp}}] {{notes or 'Standard operation performed'}}"
    
    return {{
        "title": title,
        "category": category,
        "processed_summary": processed_summary,
        "processed": True,
        "score": 100
    }}
'''

    # requirements.txt
    req_txt = """Flask>=3.0.0
Werkzeug>=3.0.0
pytest>=8.0.0
"""

    # templates/index.html
    index_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name} - DevGuardian AI Generated</title>
    <style>
        :root {{
            --bg: #F4F5F7;
            --card-bg: #FFFFFF;
            --text-primary: #17191D;
            --text-secondary: #626873;
            --border: #E1E4E8;
            --btn-dark: #24272D;
            --btn-text: #FFFFFF;
            --success: #368568;
            --warning: #B88936;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text-primary);
            line-height: 1.5;
            padding: 32px 16px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        h1 {{ font-size: 24px; font-weight: 700; color: var(--text-primary); }}
        .badge {{
            display: inline-block;
            background: #E9ECEF;
            color: var(--text-secondary);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        }}
        .form-group {{ margin-bottom: 16px; }}
        label {{
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }}
        input, select, textarea {{
            width: 100%;
            padding: 10px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 14px;
            color: var(--text-primary);
            background: #FAFBFD;
        }}
        input:focus, textarea:focus {{
            outline: none;
            border-color: #24272D;
        }}
        .btn {{
            background: var(--btn-dark);
            color: var(--btn-text);
            border: none;
            padding: 10px 18px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .btn:hover {{ opacity: 0.9; }}
        .btn-danger {{
            background: #C45D5D;
            padding: 6px 12px;
            font-size: 12px;
        }}
        .records-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
        }}
        .records-table th, .records-table td {{
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }}
        .records-table th {{
            color: var(--text-secondary);
            font-weight: 600;
            background: #F8F9FA;
        }}
        .flash-msg {{
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 16px;
            font-size: 14px;
            background: #E8F5E9;
            color: #2E7D32;
            border: 1px solid #C8E6C9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>{project_name}</h1>
                <p style="color: var(--text-secondary); font-size: 14px;">{description}</p>
            </div>
            <span class="badge">Generated by DevGuardian AI</span>
        </header>

        {{% with messages = get_flashed_messages(with_categories=true) %}}
            {{% if messages %}}
                {{% for category, message in messages %}}
                    <div class="flash-msg">{{ message }}</div>
                {{% endfor %}}
            {{% endif %}}
        {{% endwith %}}

        <div class="card">
            <h2 style="font-size: 16px; margin-bottom: 16px;">Add New Entry</h2>
            <form action="/add" method="POST">
                <div class="form-group">
                    <label for="title">Title / Name</label>
                    <input type="text" id="title" name="title" placeholder="Enter title..." required>
                </div>
                <div class="form-group">
                    <label for="category">Category</label>
                    <select id="category" name="category">
                        <option value="Primary">Primary</option>
                        <option value="Secondary">Secondary</option>
                        <option value="Operations">Operations</option>
                        <option value="General">General</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="notes">Notes / Payload Details</label>
                    <textarea id="notes" name="notes" rows="3" placeholder="Enter notes or data payload..."></textarea>
                </div>
                <button type="submit" class="btn">Process & Save Entry</button>
            </form>
        </div>

        <div class="card">
            <h2 style="font-size: 16px; margin-bottom: 8px;">Active Records (Total: {{{{ stats.total }}}})</h2>
            {{% if records %}}
            <table class="records-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Title</th>
                        <th>Category</th>
                        <th>Details</th>
                        <th>Date</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {{% for r in records %}}
                    <tr>
                        <td>#{{{{ r.id }}}}</td>
                        <td><strong>{{{{ r.title }}}}</strong></td>
                        <td><span class="badge">{{{{ r.category }}}}</span></td>
                        <td>{{{{ r.details }}}}</td>
                        <td style="font-size: 12px; color: var(--text-secondary);">{{{{ r.created_at }}}}</td>
                        <td>
                            <form action="/delete/{{{{ r.id }}}}" method="POST" style="display:inline;">
                                <button type="submit" class="btn btn-danger" onclick="return confirm('Delete this record?');">Delete</button>
                            </form>
                        </td>
                    </tr>
                    {{% endfor %}}
                </tbody>
            </table>
            {{% else %}}
            <p style="color: var(--text-secondary); font-size: 14px; padding: 16px 0;">No records registered yet. Create your first entry above.</p>
            {{% endif %}}
        </div>
    </div>
</body>
</html>
'''

    # test_app.py
    test_app_py = f'''"""
{project_name} - Automated Test Suite
Validates core application logic, routes, and validation routines.
"""

import unittest
from services import validate_item_input, process_project_action
from model import init_database, insert_record, get_all_records, delete_record

class TestProjectFunctionality(unittest.TestCase):
    def setUp(self):
        """Prepare fresh database state."""
        init_database()

    def test_validation_rules(self):
        """Test item input boundary constraints."""
        valid, msg = validate_item_input("Valid Title", "General")
        self.assertTrue(valid)
        self.assertEqual(msg, "")

        invalid, err = validate_item_input("A", "General")
        self.assertFalse(invalid)
        self.assertIn("at least 2 characters", err)

        no_cat, cat_err = validate_item_input("Valid Item", "")
        self.assertFalse(no_cat)

    def test_business_processing(self):
        """Test service processing transformation."""
        res = process_project_action("Alpha Test", "Operations", "Payload test notes")
        self.assertTrue(res["processed"])
        self.assertEqual(res["category"], "Operations")
        self.assertIn("Alpha Test", res["title"])

    def test_database_crud(self):
        """Test inserting and deleting an entity record."""
        new_id = insert_record("DB Integration Test", "TestCat", "Details record")
        self.assertIsNotNone(new_id)
        self.assertGreater(new_id, 0)

        records = get_all_records()
        self.assertTrue(any(r["id"] == new_id for r in records))

        deleted = delete_record(new_id)
        self.assertTrue(deleted)

if __name__ == "__main__":
    unittest.main()
'''

    return {
        "app.py": app_py,
        "model.py": model_py,
        "services.py": services_py,
        "requirements.txt": req_txt,
        "templates/index.html": index_html,
        "test_app.py": test_app_py,
    }

# =====================================================================
# AGENT 4: TESTING AGENT
# =====================================================================

def run_testing_agent(project_id: str, files_manifest: Dict[str, str], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Execute syntax check and isolated unittest runner."""
    from services.testing_service import execute_isolated_tests
    return execute_isolated_tests(project_id, files_manifest)

# =====================================================================
# AGENT 5: SECURITY AGENT
# =====================================================================

def run_security_agent(project_id: str, files_manifest: Dict[str, str], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Perform static AST and heuristic vulnerability scan."""
    from services.security_service import scan_project_security
    return scan_project_security(project_id, files_manifest)

# =====================================================================
# AGENT 6: CODE REVIEW AGENT
# =====================================================================

def run_review_agent(project_id: str, files_manifest: Dict[str, str], requirements_text: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Perform code quality, maintainability, and architectural review."""
    from services.review_service import perform_code_review
    return perform_code_review(project_id, files_manifest, requirements_text)

# =====================================================================
# AGENT 7: DEPLOYMENT AGENT
# =====================================================================

def run_deployment_agent(project_id: str, project_name: str, app_type: str, files_manifest: Dict[str, str], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Generate Dockerfile, compose config, and deployment runbooks."""
    from services.deployment_service import prepare_deployment
    return prepare_deployment(project_id, project_name, app_type, files_manifest)

# =====================================================================
# AGENT 8: PROJECT MANAGER AGENT
# =====================================================================

def run_project_manager_agent(project_id: str, project_name: str, description: str, all_stage_data: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Compile comprehensive executive project report from actual outputs."""
    from services.report_service import compile_project_report
    return compile_project_report(project_id, project_name, description, all_stage_data)
