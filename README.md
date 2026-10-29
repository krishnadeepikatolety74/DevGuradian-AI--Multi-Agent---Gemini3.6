# DevGuardian AI — Autonomous Software Project Manager

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Flask 3.1](https://img.shields.io/badge/flask-3.1-black.svg)](https://flask.palletsprojects.com/)
[![LangGraph 1.2](https://img.shields.io/badge/orchestrator-LangGraph%201.2-purple.svg)](https://github.com/langchain-ai/langgraph)
[![SQLite3](https://img.shields.io/badge/database-SQLite3-green.svg)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**DevGuardian AI** is a production-grade, multi-agent autonomous software development platform. Given a software idea in plain English (e.g., *"Build a food recognition application that allows users to upload food images and identify the food item with nutrition details"*), DevGuardian AI processes the request through eight specialized AI agents orchestrated via **LangGraph**, generating complete executable source code, running isolated tests, performing AST security audits, evaluating code maintainability, preparing Docker deployment artifacts, and compiling executive PDF delivery reports.

---

## 📸 User Interface & Visual Design

The application implements the **Minimalist Grey and White SaaS Dashboard** design system:
- **Palette:** Soft background (`#F4F5F7`), Crisp card surfaces (`#FFFFFF`), Primary charcoal buttons (`#24272D`), Thin borders (`#E1E4E8`), Code editor (`#1E2126`), Restrained success (`#368568`).
- **Interactive Animated Robot:** Pure CSS/SVG animated companion perched on a 3D circular podium with floating movement, smiling cyan eyes, waving gesture, glowing chest core, and 6 orbiting monochrome satellite badges (`</>`, checklist, cloud, shield, gear, analytics).
- **Zero Frontend JS Framework Overhead:** 100% server-side rendered with pure Python, Flask, Jinja2, and Vanilla CSS. No React, Node.js, npm, or external frontend servers.

---

## 🤖 The 8 Specialized AI Agents

DevGuardian AI coordinates eight specialized agents sequentially:

| Order | Agent | Role & Responsibility | Core Output |
|---|---|---|---|
| **1** | **Requirement Agent** | Extracts functional (FR) & non-functional (NFR) requirements, inputs/outputs, and acceptance criteria. | Formal Software Requirements Specification (SRS) |
| **2** | **Architecture Agent** | Designs layered architecture, SQLite schema, REST endpoints, and file manifest. | System Architecture Specification |
| **3** | **Coding Agent** | Generates complete, executable source code (`app.py`, `model.py`, `services.py`, templates). | Real Project Workspace Files |
| **4** | **Testing Agent** | Scans Python syntax via AST and runs unittests in an isolated subprocess sandbox. | Automated Test Logs & Pass/Fail Metrics |
| **5** | **Security Agent** | Inspects code for SQL injection, `eval`/`exec`, shell injection, and leaked secrets. | AST Security Audit Findings by Severity |
| **6** | **Code Review Agent** | Audits cyclomatic structure, PEP 8 standards, docstring depth, and error handling. | Maintainability Score (/10) & Actionable Fixes |
| **7** | **Deployment Agent** | Creates multi-stage Dockerfiles with healthchecks, docker-compose, and environment guides. | Container Artifacts & Deployment Runbook |
| **8** | **Project Manager Agent** | Consolidates all actual agent milestone outputs into an executive delivery report. | Final Project Report & ReportLab PDF |

---

## 🏗️ Technology Stack

- **Backend:** Python 3.11+, Flask 3.1, Werkzeug, Flask Sessions, Python Dotenv
- **Orchestration:** LangGraph 1.2 (`StateGraph` pipeline with explicit state management)
- **AI Models:** Google Gemini API (`gemini-1.5-flash`, `gemini-1.5-pro`, `gemini-2.5-flash`) + Intelligent Local Offline Engine for Demo Mode
- **Database:** SQLite 3 with atomic transactions, parameterized queries, and foreign-key integrity
- **PDF Generation:** ReportLab 4.2 (Pure Python vector PDF compilation)
- **Code Validation:** Python AST syntax checking, isolated `subprocess.run` execution sandboxing
- **Frontend:** Server-side rendered HTML5, Jinja2 templates, pure modern CSS3, SVG vector graphics

---

## 📂 Project Directory Structure

```text
DevGuardian-AI/
|-- app.py                    # Single application entry point & Flask routes
|-- db.py                     # SQLite connection manager & schema initialization
|-- requirements.txt          # Python dependencies
|-- .env                      # Environment configuration
|-- .env.example              # Environment variables template
|-- .gitignore                # Git ignore rules
|-- README.md                 # Complete documentation
|
|-- services/
|   |-- ai_service.py         # Gemini API integration & fallback demo engine
|   |-- project_service.py    # Project queries, ownership, and live dashboard stats
|   |-- code_generator.py     # Source file generation, AST validation, ZIP packaging
|   |-- testing_service.py    # Isolated subprocess test runner & log parser
|   |-- security_service.py   # Static AST security scanner & vulnerability rules
|   |-- review_service.py     # Code quality & maintainability evaluation
|   |-- deployment_service.py # Dockerfile & deployment runbook generator
|   |-- report_service.py     # Executive report compilation & ReportLab PDF generator
|   |-- workflow_service.py   # LangGraph StateGraph 8-agent orchestration pipeline
|
|-- templates/
|   |-- base.html             # Common layout shell & navigation sidebar
|   |-- landing.html          # Landing page with hero & animated robot
|   |-- register.html         # Split-screen Sign Up with animated robot & feature cards
|   |-- login.html            # Sign In card
|   |-- dashboard.html        # Live statistics & recent projects list
|   |-- new_project.html      # 4-Step project creation wizard
|   |-- agents.html           # 8 AI Agents catalog grid
|   |-- agent_detail.html     # Individual agent specifications & execution logs
|   |-- projects.html         # Projects list with filters and actions
|   |-- project_detail.html   # Project overview hub
|   |-- project_progress.html # Workspace with stepper, terminal console & progress bar
|   |-- code_output.html      # Coding Agent workspace with dark charcoal editor
|   |-- testing_results.html  # Isolated test run metrics and console logs
|   |-- security_results.html # Security vulnerability audit breakdown
|   |-- code_review.html      # Maintainability rating and recommendations
|   |-- deployment.html       # Containerization checklist & Dockerfile viewer
|   |-- reports.html          # Reports catalog
|   |-- report_detail.html    # Executive final report with PDF/ZIP downloads
|   |-- settings.html         # Gemini API key configuration & connection test
|   |-- profile.html          # User profile & password management
|   |-- 404.html              # Custom 404 error page
|   |-- 500.html              # Custom 500 error page
|
|-- static/
|   |-- css/
|   |   |-- style.css         # Design system tokens, robot animations, split signup
|   |   |-- dashboard.css     # Two-column layout, sidebar, stats cards
|   |   |-- components.css    # Steppers, terminal logs, dark code viewer, pills
|   |-- images/
|       |-- logo.svg          # Brand vector icon
|
|-- instance/
|   |-- devguardian.db        # SQLite database (auto-created on startup)
|
|-- generated_projects/       # Isolated storage directory for generated code
|   |-- .gitkeep
|
|-- tests/
    |-- __init__.py
    |-- test_devguardian.py   # 10 automated unit and integration tests
```

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12 installed on your machine.
- Git (optional, for cloning).

### 2. Setup Virtual Environment
Open your terminal in the project directory:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
# Windows:
copy .env.example .env
# Linux/macOS:
cp .env.example .env
```

Open `.env` and configure your settings:
```ini
SECRET_KEY=devguardian_super_secret_session_key_2026
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
FLASK_ENV=development
PORT=5000
```
> **Note on Demo Mode:** If `GEMINI_API_KEY` is not provided, the application runs seamlessly in **DEMO MODE**, utilizing the deterministic offline generation engine to build realistic, syntactically clean, runnable projects. You can add your API key anytime in `.env` or via the in-app **Settings** page!

### 5. Launch the Application
Start the server using the single required command:
```bash
python app.py
```

Navigate to:
```text
http://127.0.0.1:5000
```

---

## 🧪 Automated Testing

DevGuardian AI includes a test suite covering registration, login, CSRF validation, user project isolation, database persistence, the 8-agent LangGraph pipeline, isolated unittest execution, AST security scanning, ReportLab PDF generation, and ZIP bundling.

Run the test suite with:
```bash
python -m unittest discover -s tests -v
```

All 10 tests will execute and report:
```text
Ran 10 tests in 1.014s
OK
```

---

## 🔒 Security & Safe Execution Design

1. **Password Hashing:** Passwords are never stored in plain text; salted SHA-256 hashes are generated using `werkzeug.security`.
2. **Session CSRF Protection:** All POST forms validate unique session tokens against cross-site request forgery.
3. **Subprocess Isolation:** Generated code and tests are executed inside dedicated project workspaces in separate Python subprocesses with a 12-second execution timeout. Untrusted code is **never** executed inside the main Flask process.
4. **Path Traversal Protection:** All project file access enforces boundary checks inside `generated_projects/{project_id}`.
5. **No Hardcoded API Keys:** API keys are read from environment variables or encrypted session state and never sent to the browser.
6. **OAuth State Verification:** Cryptographically secure state tokens (`secrets.token_urlsafe`) protect OAuth callback routes against Login CSRF and token replay attacks.
7. **Protected Account Linking:** Email-matching OAuth logins require explicit password authentication before associating external provider IDs to existing accounts.

---

## 🔑 Google Cloud OAuth 2.0 Configuration Guide

To enable genuine Google Sign In and Sign Up in DevGuardian AI:

### 1. Create or Select a Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown in the top navigation bar and select **New Project** (or pick an existing project).
3. Name your project (e.g., `devguardian-ai-prod`) and click **Create**.

### 2. Configure the OAuth Consent Screen
1. In the Google Cloud Console, navigate to **APIs & Services** > **OAuth consent screen**.
2. Select User Type:
   - **External**: Suitable for testing with personal Gmail accounts or public users.
   - **Internal**: If your application is restricted to users within your Google Workspace organization.
3. Complete the App Information:
   - **App name**: `DevGuardian AI`
   - **User support email**: Select your verified support or administrator email.
   - **Developer contact information**: Enter your contact email.
4. Click **Save and Continue**.

### 3. Configure Required OAuth Scopes
1. On the **Scopes** step, click **Add or Remove Scopes**.
2. Select the three required OpenID Connect scopes:
   - `openid` (Authenticate user identity)
   - `.../auth/userinfo.email` (Retrieve verified Google Account email address)
   - `.../auth/userinfo.profile` (Retrieve user display name and profile info)
3. Click **Update** and then **Save and Continue**.

### 4. Add Test Users (If Consent Screen is in Testing Mode)
1. If your OAuth consent screen publishing status is **Testing**, add the Google email addresses of designated testers.
2. Click **Save and Continue**.

### 5. Create OAuth 2.0 Client Credentials
1. Navigate to **APIs & Services** > **Credentials**.
2. Click **Create Credentials** > **OAuth client ID**.
3. Set **Application type** to **Web application**.
4. Name: `DevGuardian AI Web Client`.
5. Under **Authorized redirect URIs**, click **Add URI** and enter the exact callback URL:
   - **Local Development**:
     ```text
     http://localhost:5000/auth/callback/google
     ```
     *(Optional alias: `http://127.0.0.1:5000/auth/callback/google`)*
   - **Production Deployment**:
     ```text
     https://<your-domain>/auth/callback/google
     ```
   > ⚠️ **Important:** Google Cloud strictly requires character-for-character matching between the registered redirect URI and the redirect URI sent in authentication requests.
6. Click **Create**.
7. Copy the generated **Client ID** and **Client Secret**.

### 6. Configure Environment Variables
Add the credentials to your `.env` file:
```ini
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/callback/google
```

---

## 🐙 GitHub OAuth Application Configuration Guide

To enable genuine GitHub Sign In and Sign Up in DevGuardian AI:

### 1. Create a GitHub OAuth Application
1. Log in to [GitHub](https://github.com/) and go to **Settings** > **Developer settings** > **OAuth Apps**.
   - Direct link: [GitHub Developer Settings](https://github.com/settings/developers)
2. Click **New OAuth App** (or **Register a new application**).

### 2. Configure Application Details
1. **Application name**: `DevGuardian AI`
2. **Homepage URL**:
   - Local Development:
     ```text
     http://localhost:5000
     ```
   - Production:
     ```text
     https://<your-domain>
     ```
3. **Application description**: `DevGuardian AI Autonomous Software Project Manager OAuth Integration`
4. **Authorization callback URL**:
   - Local Development:
     ```text
     http://localhost:5000/auth/callback/github
     ```
   - Production:
     ```text
     https://<your-domain>/auth/callback/github
     ```
   > ⚠️ **Important:** GitHub strictly enforces exact URI matching. Do not add trailing slashes or mismatches in port or protocol.
5. Click **Register application**.

### 3. Generate Client Secret
1. On the registered app page, copy your **Client ID**.
2. Under **Client secrets**, click **Generate a new client secret**.
3. Copy the generated **Client Secret** immediately (GitHub only displays it once).

### 4. Configure Environment Variables
Add the credentials to your `.env` file:
```ini
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_REDIRECT_URI=http://localhost:5000/auth/callback/github
```

### 5. Private Email & Verification Support
DevGuardian AI requests the `read:user user:email` OAuth scopes. When a user has configured a private email on GitHub, DevGuardian AI automatically queries the authenticated `/user/emails` endpoint to extract their primary verified email address, guaranteeing account integrity without exposing unverified emails.

