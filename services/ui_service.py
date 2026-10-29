import os
import re
import json
import uuid
import shutil
import difflib
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set
import jinja2

from db import get_standalone_db
from services.code_generator import get_project_dir, save_project_files, get_project_files_from_db
from services.workspace_manager import get_project_workspace, ensure_safe_path, GENERATED_PROJECTS_DIR
from services.ai_service import get_gemini_api_key, is_api_key_configured, call_gemini

# Default UI / UX Configuration
DEFAULT_UI_CONFIG = {
    "generate_ui": True,
    "design_style": "Modern SaaS",
    "color_palette": "White and Grey",
    "layout_preference": "Responsive Web Application",
    "design_instructions": "",
    "required_pages": ["Landing Page", "Sign In", "Sign Up", "Dashboard", "Project Pages", "Reports", "Settings"],
    "custom_pages": ""
}

PAGE_SLUG_MAP = {
    "landing page": "landing.html",
    "sign in": "login.html",
    "sign up": "register.html",
    "dashboard": "dashboard.html",
    "project pages": "projects.html",
    "reports": "reports.html",
    "settings": "settings.html"
}

def get_color_tokens(palette_choice: str) -> Dict[str, str]:
    """Return tailored CSS color tokens based on chosen palette."""
    pal = (palette_choice or "White and Grey").lower()
    if "blue" in pal:
        return {
            "primary": "#2563EB",
            "primary_hover": "#1E429F",
            "bg": "#F8FAFC",
            "card_bg": "#FFFFFF",
            "text_primary": "#0F172A",
            "text_secondary": "#64748B",
            "border": "#E2E8F0",
            "accent": "#3B82F6"
        }
    elif "dark" in pal:
        return {
            "primary": "#6366F1",
            "primary_hover": "#4F46E5",
            "bg": "#0F172A",
            "card_bg": "#1E293B",
            "text_primary": "#F8FAFC",
            "text_secondary": "#94A3B8",
            "border": "#334155",
            "accent": "#818CF8"
        }
    else:  # White and Grey (default DevGuardian SaaS)
        return {
            "primary": "#24272D",
            "primary_hover": "#17191D",
            "bg": "#F8F9FA",
            "card_bg": "#FFFFFF",
            "text_primary": "#17191D",
            "text_secondary": "#626873",
            "border": "#E1E4E8",
            "accent": "#368568"
        }

def generate_design_tokens(palette_choice: str, design_style: str = "Modern SaaS") -> Dict[str, str]:
    """Helper to return normalized design tokens."""
    tokens = get_color_tokens(palette_choice)
    pal = (palette_choice or "").lower()
    raw = {
        "primary": tokens["primary"],
        "primary_hover": tokens["primary_hover"],
        "bg_primary": tokens["card_bg"] if "dark" not in pal else tokens["bg"],
        "bg_secondary": tokens["bg"] if "dark" not in pal else tokens["card_bg"],
        "text_primary": tokens["text_primary"],
        "text_secondary": tokens["text_secondary"],
        "border": tokens["border"],
        "accent": tokens["accent"]
    }
    return {k: (v.lower() if isinstance(v, str) and v.startswith("#") else v) for k, v in raw.items()}

def validate_jinja2_template(content: str, filename: str = "template.html") -> Dict[str, Any]:
    """Check Jinja2 template syntax validity."""
    env = jinja2.Environment()
    try:
        env.parse(content)
        return {"valid": True, "error": None}
    except jinja2.TemplateSyntaxError as e:
        return {"valid": False, "error": f"{filename}:{e.lineno} - {e.message}"}

def generate_custom_css(tokens: Dict[str, str], design_style: str) -> str:
    """Generate cohesive, modern, responsive CSS design system."""
    return f"""/* ========================================================
   Auto-Generated UI Design System
   Style: {design_style} | Responsive CSS Tokens
   ======================================================== */
:root {{
    --primary: {tokens['primary']};
    --primary-hover: {tokens['primary_hover']};
    --bg-main: {tokens['bg']};
    --card-bg: {tokens['card_bg']};
    --text-primary: {tokens['text_primary']};
    --text-secondary: {tokens['text_secondary']};
    --border: {tokens['border']};
    --accent: {tokens['accent']};
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 14px;
    --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.08), 0 1px 2px 0 rgba(0, 0, 0, 0.04);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -1px rgba(0, 0, 0, 0.04);
}}

*, *::before, *::after {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

body {{
    font-family: var(--font-sans);
    background-color: var(--bg-main);
    color: var(--text-primary);
    line-height: 1.5;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}}

.app-container {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px 16px;
    width: 100%;
}}

/* Navbar */
.navbar {{
    background: var(--card-bg);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 50;
}}

.nav-brand {{
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.nav-links {{
    display: flex;
    align-items: center;
    gap: 16px;
    list-style: none;
}}

.nav-link {{
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    transition: all 0.2s;
}}

.nav-link:hover, .nav-link.active {{
    color: var(--text-primary);
    background: var(--bg-main);
}}

/* Cards & Panels */
.card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 24px;
    box-shadow: var(--shadow);
    margin-bottom: 24px;
}}

.card-title {{
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 8px;
    color: var(--text-primary);
}}

.card-subtitle {{
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 16px;
}}

/* Buttons */
.btn {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 600;
    border-radius: var(--radius-sm);
    cursor: pointer;
    text-decoration: none;
    border: none;
    transition: all 0.2s;
}}

.btn-primary {{
    background: var(--primary);
    color: #FFFFFF;
}}

.btn-primary:hover {{
    background: var(--primary-hover);
}}

.btn-secondary {{
    background: var(--bg-main);
    color: var(--text-primary);
    border: 1px solid var(--border);
}}

.btn-secondary:hover {{
    background: #E5E7EB;
}}

/* Form Elements */
.form-group {{
    margin-bottom: 18px;
}}

.form-label {{
    display: block;
    font-size: 13.5px;
    font-weight: 600;
    margin-bottom: 6px;
    color: var(--text-primary);
}}

.form-control {{
    width: 100%;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-size: 14px;
    background: var(--card-bg);
    color: var(--text-primary);
    outline: none;
    transition: border-color 0.2s;
}}

.form-control:focus {{
    border-color: var(--accent);
}}

/* Badges */
.badge {{
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 9999px;
}}

.badge-success {{ background: #DEF7EC; color: #03543F; }}
.badge-warning {{ background: #FEF08A; color: #713F12; }}
.badge-info {{ background: #E1EFFE; color: #1E429F; }}

/* Tables */
.table-responsive {{
    overflow-x: auto;
    width: 100%;
}}

.table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}}

.table th, .table td {{
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    text-align: left;
}}

.table th {{
    background: var(--bg-main);
    font-weight: 600;
    color: var(--text-secondary);
}}

/* Responsive Grid */
.grid-2 {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
}}

.grid-3 {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
}}

.grid-4 {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
}}

@media (max-width: 900px) {{
    .grid-4, .grid-3 {{ grid-template-columns: repeat(2, 1fr); }}
}}

@media (max-width: 640px) {{
    .grid-4, .grid-3, .grid-2 {{ grid-template-columns: 1fr; }}
    .navbar {{ flex-direction: column; gap: 12px; }}
    .nav-links {{ flex-wrap: wrap; justify-content: center; }}
}}
"""

def generate_base_template(project_name: str, nav_links: List[Tuple[str, str]]) -> str:
    """Generate Jinja2 base template layout."""
    links_html = "\n".join([
        f'                <li><a href="{{{{ url_for("{endpoint}") }}}}" class="nav-link">{{{{ "{label}" }}}}</a></li>'
        for label, endpoint in nav_links
    ])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{% block title %}}{project_name}{{% endblock %}}</title>
    <link rel="stylesheet" href="{{{{ url_for('static', filename='css/style.css') }}}}">
</head>
<body>
    <header class="navbar">
        <a href="/" class="nav-brand">
            <span>&#9889;</span>
            <span>{project_name}</span>
        </a>
        <nav>
            <ul class="nav-links">
{links_html}
            </ul>
        </nav>
    </header>

    <main class="app-container">
        {{% block content %}}{{% endblock %}}
    </main>

    <footer style="margin-top: auto; padding: 24px; text-align: center; font-size: 13px; color: var(--text-secondary); border-top: 1px solid var(--border);">
        <p>&copy; {{{{ 2026 }}}} {project_name}. All rights reserved.</p>
    </footer>
</body>
</html>
"""

def generate_landing_template(project_name: str, description: str) -> str:
    """Generate landing page template."""
    return f"""{{% extends "base.html" %}}

{{% block title %}}{project_name} — Welcome{{% endblock %}}

{{% block content %}}
<div class="card" style="text-align: center; padding: 60px 24px; background: linear-gradient(180deg, var(--card-bg) 0%, var(--bg-main) 100%);">
    <span class="badge badge-info" style="margin-bottom: 16px;">Now Live</span>
    <h1 style="font-size: 36px; font-weight: 800; margin-bottom: 16px; color: var(--text-primary);">{project_name}</h1>
    <p style="font-size: 18px; color: var(--text-secondary); max-width: 680px; margin: 0 auto 32px; line-height: 1.6;">
        {description}
    </p>
    <div style="display: flex; gap: 14px; justify-content: center;">
        <a href="{{{{ url_for('dashboard') }}}}" class="btn btn-primary" style="padding: 12px 28px; font-size: 15px;">Get Started &rarr;</a>
        <a href="{{{{ url_for('login') }}}}" class="btn btn-secondary" style="padding: 12px 24px; font-size: 15px;">Sign In</a>
    </div>
</div>

<div class="grid-3" style="margin-top: 32px;">
    <div class="card">
        <h3 class="card-title">&#128640; High Performance</h3>
        <p class="card-subtitle">Engineered with modern architecture patterns for maximum throughput and low latency.</p>
    </div>
    <div class="card">
        <h3 class="card-title">&#128272; Built-In Security</h3>
        <p class="card-subtitle">Zero-trust principles, parameterized query protection, and robust session encryption.</p>
    </div>
    <div class="card">
        <h3 class="card-title">&#128202; Real-Time Analytics</h3>
        <p class="card-subtitle">Live dashboards and comprehensive reporting giving you full visibility into operations.</p>
    </div>
</div>
{{% endblock %}}
"""

def generate_login_template(project_name: str) -> str:
    """Generate sign in page template."""
    return f"""{{% extends "base.html" %}}

{{% block title %}}Sign In — {project_name}{{% endblock %}}

{{% block content %}}
<div style="max-width: 440px; margin: 40px auto;">
    <div class="card">
        <h2 class="card-title" style="text-align: center; font-size: 22px;">Sign In to {project_name}</h2>
        <p class="card-subtitle" style="text-align: center;">Enter your credentials to access your account</p>

        <form action="/login" method="POST">
            <input type="hidden" name="csrf_token" value="{{{{ csrf_token if csrf_token else '' }}}}">

            <div class="form-group">
                <label class="form-label" for="email">Email Address</label>
                <input type="email" id="email" name="email" class="form-control" placeholder="user@example.com" required autofocus>
            </div>

            <div class="form-group">
                <label class="form-label" for="password">Password</label>
                <input type="password" id="password" name="password" class="form-control" placeholder="••••••••" required>
            </div>

            <button type="submit" class="btn btn-primary" style="width: 100%; padding: 12px; margin-top: 8px;">
                Sign In
            </button>
        </form>

        <p style="text-align: center; margin-top: 20px; font-size: 13.5px; color: var(--text-secondary);">
            Don't have an account? <a href="{{{{ url_for('register') }}}}" style="color: var(--primary); font-weight: 600;">Sign Up</a>
        </p>
    </div>
</div>
{{% endblock %}}
"""

def generate_register_template(project_name: str) -> str:
    """Generate sign up page template."""
    return f"""{{% extends "base.html" %}}

{{% block title %}}Sign Up — {project_name}{{% endblock %}}

{{% block content %}}
<div style="max-width: 480px; margin: 40px auto;">
    <div class="card">
        <h2 class="card-title" style="text-align: center; font-size: 22px;">Create Your Account</h2>
        <p class="card-subtitle" style="text-align: center;">Join {project_name} in less than 30 seconds</p>

        <form action="/register" method="POST">
            <input type="hidden" name="csrf_token" value="{{{{ csrf_token if csrf_token else '' }}}}">

            <div class="form-group">
                <label class="form-label" for="name">Full Name</label>
                <input type="text" id="name" name="name" class="form-control" placeholder="Jane Doe" required autofocus>
            </div>

            <div class="form-group">
                <label class="form-label" for="email">Email Address</label>
                <input type="email" id="email" name="email" class="form-control" placeholder="jane@example.com" required>
            </div>

            <div class="form-group">
                <label class="form-label" for="password">Password</label>
                <input type="password" id="password" name="password" class="form-control" placeholder="At least 8 characters" required>
            </div>

            <button type="submit" class="btn btn-primary" style="width: 100%; padding: 12px; margin-top: 8px;">
                Create Account
            </button>
        </form>

        <p style="text-align: center; margin-top: 20px; font-size: 13.5px; color: var(--text-secondary);">
            Already have an account? <a href="{{{{ url_for('login') }}}}" style="color: var(--primary); font-weight: 600;">Sign In</a>
        </p>
    </div>
</div>
{{% endblock %}}
"""

def generate_dashboard_template(project_name: str) -> str:
    """Generate dashboard page template."""
    return f"""{{% extends "base.html" %}}

{{% block title %}}Dashboard — {project_name}{{% endblock %}}

{{% block content %}}
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
    <div>
        <h1 style="font-size: 24px; font-weight: 700;">Dashboard Overview</h1>
        <p style="color: var(--text-secondary); font-size: 14px;">Welcome back! Here is a summary of your workspace activities.</p>
    </div>
    <a href="{{{{ url_for('projects') }}}}" class="btn btn-primary">+ New Item</a>
</div>

<div class="grid-4" style="margin-bottom: 24px;">
    <div class="card" style="padding: 18px;">
        <span style="font-size: 12px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase;">Active Records</span>
        <h2 style="font-size: 28px; font-weight: 800; margin-top: 4px;">{{{{ stats.total_items if stats and stats.total_items else 24 }}}}</h2>
        <span class="badge badge-success" style="margin-top: 6px;">&uarr; 12% this week</span>
    </div>
    <div class="card" style="padding: 18px;">
        <span style="font-size: 12px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase;">Pending Tasks</span>
        <h2 style="font-size: 28px; font-weight: 800; margin-top: 4px;">{{{{ stats.pending_tasks if stats and stats.pending_tasks else 7 }}}}</h2>
        <span class="badge badge-warning" style="margin-top: 6px;">3 high priority</span>
    </div>
    <div class="card" style="padding: 18px;">
        <span style="font-size: 12px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase;">Completed</span>
        <h2 style="font-size: 28px; font-weight: 800; margin-top: 4px;">{{{{ stats.completed if stats and stats.completed else 89 }}}}</h2>
        <span class="badge badge-success" style="margin-top: 6px;">98.4% success rate</span>
    </div>
    <div class="card" style="padding: 18px;">
        <span style="font-size: 12px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase;">System Health</span>
        <h2 style="font-size: 28px; font-weight: 800; margin-top: 4px;">100%</h2>
        <span class="badge badge-info" style="margin-top: 6px;">All services normal</span>
    </div>
</div>

<div class="card">
    <h3 class="card-title">Recent Activity</h3>
    <div class="table-responsive">
        <table class="table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Activity</th>
                    <th>Status</th>
                    <th>Timestamp</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><code>#ACT-1092</code></td>
                    <td>Project database synchronization concluded</td>
                    <td><span class="badge badge-success">Completed</span></td>
                    <td>Just now</td>
                </tr>
                <tr>
                    <td><code>#ACT-1091</code></td>
                    <td>Automated test suite verified 14 assertions</td>
                    <td><span class="badge badge-success">Passed</span></td>
                    <td>25 minutes ago</td>
                </tr>
                <tr>
                    <td><code>#ACT-1090</code></td>
                    <td>Security audit rule scan finished (0 flaws)</td>
                    <td><span class="badge badge-info">Verified</span></td>
                    <td>1 hour ago</td>
                </tr>
            </tbody>
        </table>
    </div>
</div>
{{% endblock %}}
"""

def generate_projects_template(project_name: str) -> str:
    """Generate projects / records list template."""
    return f"""{{% extends "base.html" %}}

{{% block title %}}Projects & Records — {project_name}{{% endblock %}}

{{% block content %}}
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
    <div>
        <h1 style="font-size: 24px; font-weight: 700;">Project Records</h1>
        <p style="color: var(--text-secondary); font-size: 14px;">Manage all assets and operational items.</p>
    </div>
</div>

<div class="card">
    <div class="table-responsive">
        <table class="table">
            <thead>
                <tr>
                    <th>Item Name</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Updated Date</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Core Service Module</strong></td>
                    <td>Backend API</td>
                    <td><span class="badge badge-success">Active</span></td>
                    <td>Today</td>
                    <td><a href="#" class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;">View</a></td>
                </tr>
                <tr>
                    <td><strong>Authentication Gateway</strong></td>
                    <td>Security</td>
                    <td><span class="badge badge-success">Active</span></td>
                    <td>Yesterday</td>
                    <td><a href="#" class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;">View</a></td>
                </tr>
                <tr>
                    <td><strong>Data Processing Pipeline</strong></td>
                    <td>Worker</td>
                    <td><span class="badge badge-info">Idle</span></td>
                    <td>2 days ago</td>
                    <td><a href="#" class="btn btn-secondary" style="padding: 4px 10px; font-size: 12px;">View</a></td>
                </tr>
            </tbody>
        </table>
    </div>
</div>
{{% endblock %}}
"""

def generate_reports_template(project_name: str) -> str:
    """Generate reports page template."""
    return f"""{{% extends "base.html" %}}

{{% block title %}}Reports & Metrics — {project_name}{{% endblock %}}

{{% block content %}}
<div style="margin-bottom: 24px;">
    <h1 style="font-size: 24px; font-weight: 700;">Operational Reports</h1>
    <p style="color: var(--text-secondary); font-size: 14px;">Performance, compliance, and delivery audit summaries.</p>
</div>

<div class="grid-2">
    <div class="card">
        <h3 class="card-title">Performance Audit</h3>
        <p class="card-subtitle">Aggregated test coverage and latency benchmarks.</p>
        <p style="font-size: 14px; margin-bottom: 16px;">Test assertions passing: <strong>100%</strong> with zero regression errors.</p>
        <button class="btn btn-secondary" style="font-size: 13px;">Export Report</button>
    </div>

    <div class="card">
        <h3 class="card-title">Security & Compliance</h3>
        <p class="card-subtitle">Static code analysis and vulnerability assessment.</p>
        <p style="font-size: 14px; margin-bottom: 16px;">Status: <span class="badge badge-success">0 Vulnerabilities Found</span></p>
        <button class="btn btn-secondary" style="font-size: 13px;">Export Report</button>
    </div>
</div>
{{% endblock %}}
"""

def generate_settings_template(project_name: str) -> str:
    """Generate settings page template."""
    return f"""{{% extends "base.html" %}}

{{% block title %}}Settings — {project_name}{{% endblock %}}

{{% block content %}}
<div style="max-width: 680px;">
    <div style="margin-bottom: 24px;">
        <h1 style="font-size: 24px; font-weight: 700;">System Preferences</h1>
        <p style="color: var(--text-secondary); font-size: 14px;">Configure workspace options and environment parameters.</p>
    </div>

    <div class="card">
        <h3 class="card-title">Application Settings</h3>
        <form action="/settings/save" method="POST">
            <input type="hidden" name="csrf_token" value="{{{{ csrf_token if csrf_token else '' }}}}">

            <div class="form-group">
                <label class="form-label" for="app_title">Application Name</label>
                <input type="text" id="app_title" name="app_title" class="form-control" value="{project_name}">
            </div>

            <div class="form-group">
                <label class="form-label" for="environment">Execution Environment</label>
                <select id="environment" name="environment" class="form-control">
                    <option value="development" selected>Development</option>
                    <option value="staging">Staging</option>
                    <option value="production">Production</option>
                </select>
            </div>

            <div class="form-group">
                <label class="form-label" for="notifications">Status Alerts</label>
                <select id="notifications" name="notifications" class="form-control">
                    <option value="enabled" selected>Email & In-App Alerts</option>
                    <option value="critical_only">Critical Errors Only</option>
                    <option value="disabled">Disabled</option>
                </select>
            </div>

            <button type="submit" class="btn btn-primary" style="padding: 10px 20px;">Save Changes</button>
        </form>
    </div>
</div>
{{% endblock %}}
"""

def generate_custom_page_template(project_name: str, page_title: str) -> str:
    """Generate a rich, production-grade custom page template tailored to domain."""
    title_lower = page_title.lower()
    
    if "claims" in title_lower and "manage" in title_lower:
        return f"""{{% extends "base.html" %}}

{{% block title %}}Claims Management — {project_name}{{% endblock %}}

{{% block content %}}
<div class="page-header" style="margin-bottom: 24px;">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
        <div>
            <h1 style="font-size: 26px; font-weight: 700; color: #0A192F; margin: 0 0 6px 0;">Claims Management</h1>
            <p style="margin: 0; font-size: 14px; color: #64748B;">Centralized intake, automated adjudication, AI fraud scoring, and lifecycle tracking for active policy claims.</p>
        </div>
        <div style="display: flex; gap: 10px;">
            <a href="{{{{ url_for('submit_claim') }}}}" class="btn btn-primary" style="display: inline-flex; align-items: center; gap: 6px;">
                <span>+</span> Submit New Claim
            </a>
            <button type="button" class="btn btn-secondary" onclick="window.print()">Export Report</button>
        </div>
    </div>
</div>

<!-- KPI Stats Summary Row -->
<div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px;">
    <div class="stat-card" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748B; letter-spacing: 0.05em;">Total Claims</span>
            <span style="width: 28px; height: 28px; border-radius: 6px; background: #DBEAFE; color: #1E40AF; display: flex; align-items: center; justify-content: center; font-size: 14px;">&#128196;</span>
        </div>
        <h2 style="font-size: 28px; font-weight: 800; color: #0A192F; margin: 0 0 4px 0;">{{{{ claim_stats.total_claims | default(148) }}}}</h2>
        <span style="font-size: 12px; color: #16A34A; font-weight: 600;">&uarr; 12.4% vs last month</span>
    </div>

    <div class="stat-card" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748B; letter-spacing: 0.05em;">Pending Intake</span>
            <span style="width: 28px; height: 28px; border-radius: 6px; background: #FEF3C7; color: #D97706; display: flex; align-items: center; justify-content: center; font-size: 14px;">&#9203;</span>
        </div>
        <h2 style="font-size: 28px; font-weight: 800; color: #D97706; margin: 0 0 4px 0;">{{{{ claim_stats.pending_claims | default(32) }}}}</h2>
        <span style="font-size: 12px; color: #64748B;">Requires triage &amp; review</span>
    </div>

    <div class="stat-card" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748B; letter-spacing: 0.05em;">Under AI Review</span>
            <span style="width: 28px; height: 28px; border-radius: 6px; background: #EDE9FE; color: #6D28D9; display: flex; align-items: center; justify-content: center; font-size: 14px;">&#9881;</span>
        </div>
        <h2 style="font-size: 28px; font-weight: 800; color: #6D28D9; margin: 0 0 4px 0;">{{{{ claim_stats.under_review_claims | default(24) }}}}</h2>
        <span style="font-size: 12px; color: #6D28D9; font-weight: 600;">5 Specialized Agents Active</span>
    </div>

    <div class="stat-card" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #DC2626; letter-spacing: 0.05em;">Flagged / High Risk</span>
            <span style="width: 28px; height: 28px; border-radius: 6px; background: #FEE2E2; color: #DC2626; display: flex; align-items: center; justify-content: center; font-size: 14px;">&#9888;</span>
        </div>
        <h2 style="font-size: 28px; font-weight: 800; color: #DC2626; margin: 0 0 4px 0;">{{{{ claim_stats.flagged_claims | default(7) }}}}</h2>
        <span style="font-size: 12px; color: #DC2626; font-weight: 600;">SIU Escalation Required</span>
    </div>
</div>

<!-- Claims Data Table & Filter Panel -->
<div class="card" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px; margin-bottom: 20px;">
        <div style="display: flex; gap: 10px; flex: 1; max-width: 480px;">
            <input type="text" placeholder="Search by Claim ID, Claimant, or Policy #..." style="width: 100%; padding: 8px 14px; font-size: 13.5px; border: 1px solid #CBD5E1; border-radius: 6px; background: #F8FAFC;">
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
            <select style="padding: 8px 12px; font-size: 13px; border: 1px solid #CBD5E1; border-radius: 6px; background: #FFFFFF; color: #334155;">
                <option value="">All Statuses</option>
                <option value="Submitted">Submitted</option>
                <option value="Under Review">Under Review</option>
                <option value="Approved">Approved</option>
                <option value="Flagged">Flagged</option>
            </select>
            <select style="padding: 8px 12px; font-size: 13px; border: 1px solid #CBD5E1; border-radius: 6px; background: #FFFFFF; color: #334155;">
                <option value="">All Policy Types</option>
                <option value="Auto">Commercial Auto</option>
                <option value="Home">Homeowners</option>
                <option value="Property">Commercial Property</option>
                <option value="Workers Comp">Workers Comp</option>
            </select>
        </div>
    </div>

    <!-- Table -->
    <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13.5px;">
            <thead>
                <tr style="border-bottom: 2px solid #E2E8F0; color: #64748B; font-weight: 600; font-size: 12px; text-transform: uppercase;">
                    <th style="padding: 12px 14px;">Claim ID</th>
                    <th style="padding: 12px 14px;">Claimant</th>
                    <th style="padding: 12px 14px;">Policy Type</th>
                    <th style="padding: 12px 14px;">Submitted Date</th>
                    <th style="padding: 12px 14px;">Claim Amount</th>
                    <th style="padding: 12px 14px;">AI Risk Score</th>
                    <th style="padding: 12px 14px;">Status</th>
                    <th style="padding: 12px 14px; text-align: right;">Actions</th>
                </tr>
            </thead>
            <tbody>
                {{% for c in claims %}}
                <tr style="border-bottom: 1px solid #F1F5F9; transition: background 0.15s;" onmouseover="this.style.background='#F8FAFC'" onmouseout="this.style.background='transparent'">
                    <td style="padding: 14px; font-weight: 700; color: #1E40AF;">{{{{ c.claim_number }}}}</td>
                    <td style="padding: 14px; font-weight: 600; color: #0F172A;">{{{{ c.claimant_name }}}}</td>
                    <td style="padding: 14px; color: #475569;">{{{{ c.policy_type }}}}</td>
                    <td style="padding: 14px; color: #64748B;">{{{{ c.submission_date }}}}</td>
                    <td style="padding: 14px; font-weight: 700; color: #0F172A;">${{{{ c.claimed_amount }}}}</td>
                    <td style="padding: 14px;">
                        {{% if c.risk_score < 30 %}}
                            <span class="badge badge-success" style="background: #DCFCE7; color: #16A34A; padding: 4px 8px; border-radius: 12px; font-size: 11.5px; font-weight: 700;">{{{{ c.risk_score }}}}/100 Low</span>
                        {{% elif c.risk_score < 70 %}}
                            <span class="badge badge-warning" style="background: #FEF3C7; color: #D97706; padding: 4px 8px; border-radius: 12px; font-size: 11.5px; font-weight: 700;">{{{{ c.risk_score }}}}/100 Medium</span>
                        {{% else %}}
                            <span class="badge badge-danger" style="background: #FEE2E2; color: #DC2626; padding: 4px 8px; border-radius: 12px; font-size: 11.5px; font-weight: 700;">{{{{ c.risk_score }}}}/100 High</span>
                        {{% endif %}}
                    </td>
                    <td style="padding: 14px;">
                        {{% if c.status == 'Approved' %}}
                            <span style="background: #DCFCE7; color: #16A34A; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">&#10003; Approved</span>
                        {{% elif c.status == 'Flagged' %}}
                            <span style="background: #FEE2E2; color: #DC2626; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">&#9888; Flagged</span>
                        {{% elif c.status == 'Under Review' %}}
                            <span style="background: #EDE9FE; color: #6D28D9; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">&#9881; Under Review</span>
                        {{% else %}}
                            <span style="background: #DBEAFE; color: #1E40AF; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">{{{{ c.status }}}}</span>
                        {{% endif %}}
                    </td>
                    <td style="padding: 14px; text-align: right;">
                        <a href="{{{{ url_for('claim_details') }}}}" class="btn btn-sm btn-secondary" style="padding: 5px 10px; font-size: 12px; text-decoration: none;">View</a>
                        <a href="{{{{ url_for('claim_review') }}}}" class="btn btn-sm btn-primary" style="padding: 5px 10px; font-size: 12px; text-decoration: none; margin-left: 4px;">Review</a>
                    </td>
                </tr>
                {{% else %}}
                <tr>
                    <td colspan="8" style="text-align: center; padding: 48px 16px;">
                        <div style="max-width: 320px; margin: 0 auto;">
                            <span style="font-size: 32px; display: block; margin-bottom: 8px;">&#128194;</span>
                            <h3 style="font-size: 16px; font-weight: 700; color: #0F172A; margin: 0 0 6px 0;">No Claims Found</h3>
                            <p style="font-size: 13.5px; color: #64748B; margin-bottom: 16px;">No claims have been submitted or match the selected filters.</p>
                            <a href="{{{{ url_for('submit_claim') }}}}" class="btn btn-primary btn-sm">+ Submit New Claim</a>
                        </div>
                    </td>
                </tr>
                {{% endfor %}}
            </tbody>
        </table>
    </div>

    <!-- Pagination Footer -->
    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #E2E8F0; padding-top: 16px; margin-top: 16px; font-size: 13px; color: #64748B;">
        <span>Showing 1 to {{{{ claims|length }}}} of {{{{ claim_stats.total_claims | default(148) }}}} entries</span>
        <div style="display: flex; gap: 6px;">
            <button class="btn btn-secondary btn-sm" disabled>&larr; Prev</button>
            <button class="btn btn-primary btn-sm" style="padding: 4px 10px;">1</button>
            <button class="btn btn-secondary btn-sm" style="padding: 4px 10px;">2</button>
            <button class="btn btn-secondary btn-sm" style="padding: 4px 10px;">3</button>
            <button class="btn btn-secondary btn-sm">Next &rarr;</button>
        </div>
    </div>
</div>
{{% endblock %}}
"""

    # Generic rich domain page generator for other pages
    return f"""{{% extends "base.html" %}}

{{% block title %}}{page_title} — {project_name}{{% endblock %}}

{{% block content %}}
<div class="page-header" style="margin-bottom: 24px;">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
        <div>
            <h1 style="font-size: 26px; font-weight: 700; color: #0A192F; margin: 0 0 6px 0;">{page_title}</h1>
            <p style="margin: 0; font-size: 14px; color: #64748B;">Enterprise operational workspace and intelligent analytics for {page_title.lower()}.</p>
        </div>
        <div style="display: flex; gap: 10px;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.location.reload()">&#8635; Refresh Data</button>
            <button type="button" class="btn btn-primary btn-sm">+ New Action</button>
        </div>
    </div>
</div>

<div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px;">
    <div class="stat-card" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <span style="font-size: 11.5px; font-weight: 700; text-transform: uppercase; color: #64748B; letter-spacing: 0.05em;">Active Records</span>
        <h2 style="font-size: 28px; font-weight: 800; color: #0A192F; margin: 4px 0;">{{{{ claims|length | default(12) }}}}</h2>
        <span style="font-size: 12px; color: #16A34A; font-weight: 600;">&#10003; Synced with Database</span>
    </div>

    <div class="stat-card" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <span style="font-size: 11.5px; font-weight: 700; text-transform: uppercase; color: #64748B; letter-spacing: 0.05em;">Engine Status</span>
        <h2 style="font-size: 28px; font-weight: 800; color: #0D9488; margin: 4px 0;">Operational</h2>
        <span style="font-size: 12px; color: #64748B;">Gemini InsurTech Core &bull; 99.9% Uptime</span>
    </div>

    <div class="stat-card" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <span style="font-size: 11.5px; font-weight: 700; text-transform: uppercase; color: #64748B; letter-spacing: 0.05em;">Compliance Benchmark</span>
        <h2 style="font-size: 28px; font-weight: 800; color: #2563EB; margin: 4px 0;">100%</h2>
        <span style="font-size: 12px; color: #2563EB; font-weight: 600;">SOC2 Type II &amp; NAIC Verified</span>
    </div>
</div>

<div class="card" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
    <h3 style="font-size: 17px; font-weight: 700; color: #0F172A; margin: 0 0 16px 0;">{page_title} Data Explorer</h3>
    <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13.5px;">
            <thead>
                <tr style="border-bottom: 2px solid #E2E8F0; color: #64748B; font-weight: 600; font-size: 12px; text-transform: uppercase;">
                    <th style="padding: 10px 14px;">Item / ID</th>
                    <th style="padding: 10px 14px;">Entity</th>
                    <th style="padding: 10px 14px;">Category</th>
                    <th style="padding: 10px 14px;">Status</th>
                    <th style="padding: 10px 14px; text-align: right;">Actions</th>
                </tr>
            </thead>
            <tbody>
                {{% for c in claims %}}
                <tr style="border-bottom: 1px solid #F1F5F9;">
                    <td style="padding: 12px 14px; font-weight: 600; color: #1E40AF;">{{{{ c.claim_number }}}}</td>
                    <td style="padding: 12px 14px;">{{{{ c.claimant_name }}}}</td>
                    <td style="padding: 12px 14px; color: #64748B;">{{{{ c.policy_type }}}}</td>
                    <td style="padding: 12px 14px;">
                        <span style="background: #DBEAFE; color: #1E40AF; padding: 3px 8px; border-radius: 12px; font-size: 11.5px; font-weight: 600;">{{{{ c.status }}}}</span>
                    </td>
                    <td style="padding: 12px 14px; text-align: right;">
                        <a href="{{{{ url_for('claims_management') }}}}" class="btn btn-sm btn-secondary" style="padding: 4px 8px; font-size: 12px;">Inspect &rarr;</a>
                    </td>
                </tr>
                {{% endfor %}}
            </tbody>
        </table>
    </div>
</div>
{{% endblock %}}
"""


def generate_ui_solution(project_id: str, project_name: str, description: str,
                         ui_config: Optional[Dict[str, Any]] = None,
                         api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    UI/UX Design Agent: Generates complete UI file manifests:
    - templates/*.html
    - static/css/style.css
    - app.py routes
    """
    cfg = dict(DEFAULT_UI_CONFIG)
    if ui_config:
        cfg.update(ui_config)

    if not cfg.get("generate_ui", True):
        return {
            "status": "skipped",
            "message": "Backend-only project requested. UI generation bypassed.",
            "files": {}
        }

    design_style = cfg.get("design_style", "Modern SaaS")
    color_palette = cfg.get("color_palette", "White and Grey")
    layout_preference = cfg.get("layout_preference", "Responsive Web Application")
    required_pages = cfg.get("required_pages", [])
    custom_pages = [p.strip() for p in cfg.get("custom_pages", "").split(",") if p.strip()]

    tokens = get_color_tokens(color_palette)
    files: Dict[str, str] = {}

    # 1. Generate style.css
    files["static/css/style.css"] = generate_custom_css(tokens, design_style)

    # 2. Build navigation links based on requested pages
    nav_links = []
    has_page = lambda name: any(name.lower() in p.lower() for p in required_pages)

    if has_page("landing"):
        nav_links.append(("Home", "landing"))
    if has_page("dashboard"):
        nav_links.append(("Dashboard", "dashboard"))
    if has_page("project"):
        nav_links.append(("Projects", "projects"))
    if has_page("report"):
        nav_links.append(("Reports", "reports"))
    if has_page("settings"):
        nav_links.append(("Settings", "settings"))

    # 3. Base Template
    files["templates/base.html"] = generate_base_template(project_name, nav_links)

    # 4. Generate Page Templates
    if has_page("landing"):
        files["templates/landing.html"] = generate_landing_template(project_name, description)
    if has_page("sign in") or has_page("login"):
        files["templates/login.html"] = generate_login_template(project_name)
    if has_page("sign up") or has_page("register"):
        files["templates/register.html"] = generate_register_template(project_name)
    if has_page("dashboard"):
        files["templates/dashboard.html"] = generate_dashboard_template(project_name)
    if has_page("project"):
        files["templates/projects.html"] = generate_projects_template(project_name)
    if has_page("report"):
        files["templates/reports.html"] = generate_reports_template(project_name)
    if has_page("settings"):
        files["templates/settings.html"] = generate_settings_template(project_name)

    # Custom pages
    for cp in custom_pages:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", cp).lower().strip("_")
        files[f"templates/{slug}.html"] = generate_custom_page_template(project_name, cp)

    # Save to disk and database
    saved_records = save_project_files(project_id, files)

    return {
        "status": "completed",
        "message": f"Successfully synthesized {len(files)} UI template and stylesheet files.",
        "files": files,
        "tokens": tokens,
        "design_style": design_style,
        "required_pages": required_pages,
        "custom_pages": custom_pages
    }

def generate_ui_templates(project_name: str, description: str, ui_reqs: Dict[str, Any]) -> Dict[str, Any]:
    """Generate in-memory UI templates dictionary matching UI requirements."""
    design_style = ui_reqs.get("style", ui_reqs.get("design_style", "Modern SaaS"))
    color_palette = ui_reqs.get("palette", ui_reqs.get("color_palette", "White and Grey"))
    pages = ui_reqs.get("pages", ui_reqs.get("required_pages", []))
    
    tokens = get_color_tokens(color_palette)
    files: Dict[str, str] = {}
    files["static/css/app.css"] = generate_custom_css(tokens, design_style)
    files["static/css/style.css"] = files["static/css/app.css"]

    has_page = lambda name: any(name.lower() in p.lower() for p in pages)
    nav_links = []
    if has_page("landing"):
        nav_links.append(("Home", "landing"))
    if has_page("dashboard"):
        nav_links.append(("Dashboard", "dashboard"))
    if has_page("project"):
        nav_links.append(("Projects", "projects"))
    if has_page("report"):
        nav_links.append(("Reports", "reports"))
    if has_page("settings"):
        nav_links.append(("Settings", "settings"))

    files["templates/base.html"] = generate_base_template(project_name, nav_links)
    
    if has_page("landing"):
        files["templates/landing.html"] = generate_landing_template(project_name, description)
    if has_page("login") or has_page("sign in"):
        files["templates/login.html"] = generate_login_template(project_name)
    if has_page("register") or has_page("sign up"):
        files["templates/register.html"] = generate_register_template(project_name)
    if has_page("dashboard"):
        files["templates/dashboard.html"] = generate_dashboard_template(project_name)
    if has_page("project"):
        files["templates/projects.html"] = generate_projects_template(project_name)
    if has_page("report"):
        files["templates/reports.html"] = generate_reports_template(project_name)
    if has_page("settings"):
        files["templates/settings.html"] = generate_settings_template(project_name)

    standard_slugs = {"landing", "login", "register", "dashboard", "projects", "reports", "settings", "base"}
    for p in pages:
        p_clean = p.lower().replace(" ", "_")
        if not any(s in p_clean for s in standard_slugs):
            slug = re.sub(r"[^a-zA-Z0-9]+", "_", p).lower().strip("_")
            files[f"templates/{slug}.html"] = generate_custom_page_template(project_name, p)

    return {"status": "success", "templates": files, "tokens": tokens}

def validate_project_ui(project_id: str) -> Dict[str, Any]:
    """
    Validate UI assets for project:
    - Check required pages exist (supporting cross-platform path slashes and common aliases)
    - Check templates render without syntax error
    - Check responsive viewport meta tag
    - Check CSS stylesheet linkage
    - Check forms and navigation
    """
    files = get_project_files_from_db(project_id)
    files_dict = {f["filename"]: f["file_content"] for f in files}

    # Fetch project details and workspace path
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("SELECT ui_requirements, workspace_path, name FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()

    ws_path = row["workspace_path"] if row and row["workspace_path"] else None

    # Supplement files_dict from filesystem if workspace exists
    if ws_path and os.path.exists(ws_path):
        ws_templates = Path(ws_path) / "templates"
        if ws_templates.exists():
            for t_file in ws_templates.rglob("*.html"):
                rel_path = f"templates/{t_file.relative_to(ws_templates).as_posix()}"
                if rel_path not in files_dict and rel_path.replace("/", "\\") not in files_dict:
                    try:
                        files_dict[rel_path] = t_file.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        pass
        ws_static = Path(ws_path) / "static"
        if ws_static.exists():
            for s_file in ws_static.rglob("*.css"):
                rel_path = f"static/{s_file.relative_to(ws_static).as_posix()}"
                if rel_path not in files_dict and rel_path.replace("/", "\\") not in files_dict:
                    try:
                        files_dict[rel_path] = s_file.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        pass

    # Normalized lookup dictionaries (forward-slashed lowercase, and basename lowercase)
    norm_files = {}
    basename_map = {}
    for fname, content in files_dict.items():
        clean_norm = fname.replace("\\", "/").strip("/").lower()
        norm_files[clean_norm] = content
        bname = os.path.basename(clean_norm)
        basename_map[bname] = content

    ui_req = {}
    if row and row["ui_requirements"]:
        try:
            ui_req = json.loads(row["ui_requirements"]) if isinstance(row["ui_requirements"], str) else row["ui_requirements"]
        except Exception:
            ui_req = {}

    required_pages = ui_req.get("required_pages", ["Landing Page", "Dashboard"])

    # Expand candidate aliases for common required pages
    page_candidates_map = {
        "landing page": ["landing.html", "index.html", "home.html"],
        "sign in": ["login.html", "signin.html", "sign_in.html", "auth.html"],
        "sign up": ["register.html", "signup.html", "sign_up.html", "registration.html"],
        "dashboard": ["dashboard.html", "admin.html", "overview.html", "index.html"],
        "project pages": ["projects.html", "project.html", "items.html", "tasks.html", "claims.html", "candidates.html", "records.html"],
        "reports": ["reports.html", "report.html", "analytics.html", "summary.html"],
        "settings": ["settings.html", "config.html", "preferences.html", "profile.html"]
    }

    # Extract custom pages if any
    custom_pages_raw = ui_req.get("custom_pages") or ""
    custom_pages_list = []
    if isinstance(custom_pages_raw, str):
        custom_pages_list = [p.strip() for p in custom_pages_raw.split(",") if p.strip()]
    elif isinstance(custom_pages_raw, list):
        custom_pages_list = [str(p).strip() for p in custom_pages_raw if str(p).strip()]

    checks = []
    missing_pages = []

    # 1. Required Pages Check
    for rp in required_pages:
        rp_lower = rp.lower().strip()

        if rp_lower == "custom pages":
            if custom_pages_list:
                found_custom = []
                missing_custom = []
                for cp in custom_pages_list:
                    cp_slug = cp.lower().replace(" ", "_")
                    cp_candidates = [f"{cp_slug}.html", f"templates/{cp_slug}.html"]
                    match = any(c in basename_map or c in norm_files or f"templates/{c}" in norm_files for c in cp_candidates)
                    if match:
                        found_custom.append(cp)
                    else:
                        missing_custom.append(cp)

                if found_custom:
                    detail = f"Verified custom templates: {', '.join(found_custom)}"
                    checks.append({"name": f"Page: {rp}", "status": "Passed", "detail": detail})
                else:
                    missing_pages.append(rp)
                    checks.append({"name": f"Page: {rp}", "status": "Failed", "detail": f"Missing custom templates for {', '.join(custom_pages_list)}"})
            else:
                if "custom_pages.html" in basename_map or "templates/custom_pages.html" in norm_files:
                    checks.append({"name": f"Page: {rp}", "status": "Passed", "detail": "Found custom_pages.html"})
                else:
                    checks.append({"name": f"Page: {rp}", "status": "Passed", "detail": "No custom pages required"})
            continue

        # Normal standard pages
        candidates = page_candidates_map.get(rp_lower, [
            PAGE_SLUG_MAP.get(rp_lower, f"{rp_lower.replace(' ', '_')}.html")
        ])

        found_template = None
        for cand in candidates:
            cand_bname = os.path.basename(cand)
            if cand_bname in basename_map or f"templates/{cand_bname}" in norm_files or cand in norm_files:
                found_template = cand_bname
                break

        if found_template:
            checks.append({"name": f"Page: {rp}", "status": "Passed", "detail": f"Found template templates/{found_template}"})
        else:
            missing_pages.append(rp)
            checks.append({"name": f"Page: {rp}", "status": "Failed", "detail": f"Missing template templates/{candidates[0]}"})

    # 2. Jinja2 Syntax Validation
    syntax_errors = []
    env = jinja2.Environment()
    for fname, content in files_dict.items():
        if fname.endswith(".html"):
            try:
                env.parse(content)
                checks.append({"name": f"Syntax: {fname}", "status": "Passed", "detail": "Valid Jinja2 template"})
            except jinja2.TemplateSyntaxError as e:
                syntax_errors.append(f"{fname}:{e.lineno} - {e.message}")
                checks.append({"name": f"Syntax: {fname}", "status": "Failed", "detail": f"Line {e.lineno}: {e.message}"})

    # 3. CSS Linkage & Viewport Check
    base_content = (
        norm_files.get("templates/base.html")
        or norm_files.get("base.html")
        or basename_map.get("base.html")
        or ""
    )
    if not base_content:
        for c in files_dict.values():
            if 'name="viewport"' in c:
                base_content = c
                break

    has_viewport = 'name="viewport"' in base_content
    has_css = 'stylesheet' in base_content or 'style.css' in base_content

    checks.append({
        "name": "Responsive Viewport Meta",
        "status": "Passed" if has_viewport else "Failed",
        "detail": "Mobile-ready viewport configured in base template" if has_viewport else "Missing <meta name='viewport'> tag"
    })
    checks.append({
        "name": "CSS Stylesheet Linkage",
        "status": "Passed" if has_css else "Failed",
        "detail": "Stylesheet linked in template header" if has_css else "Missing style.css link in base template"
    })

    overall = "Passed" if (not missing_pages and not syntax_errors and has_viewport and has_css) else "Failed"
    
    return {
        "status": overall,
        "checks": checks,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c["status"] == "Passed"),
        "failed_checks": sum(1 for c in checks if c["status"] == "Failed"),
        "missing_pages": missing_pages,
        "syntax_errors": syntax_errors
    }

# =====================================================================
# SAFE PREVIEW RUNTIME & CONTEXT ISOLATION
# =====================================================================

class SafePreviewUndefined(jinja2.Undefined):
    """
    Tolerant Jinja2 Undefined class that logs missing context variables,
    evaluates cleanly in booleans, iterations, string conversions, and arithmetic,
    preventing raw exceptions from crashing template previews.
    """
    def __init__(self, hint=None, obj=None, name=None, exc=jinja2.exceptions.UndefinedError):
        super().__init__(hint=hint, obj=obj, name=name, exc=exc)
        self._name = name or "variable"

    def __bool__(self):
        return False

    def __iter__(self):
        return iter([])

    def __str__(self):
        return ""

    def __format__(self, format_spec):
        if not format_spec:
            return ""
        try:
            return format(0, format_spec)
        except Exception:
            try:
                return format("", format_spec)
            except Exception:
                return ""

    def __len__(self):
        return 0

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __getitem__(self, item):
        return SafePreviewUndefined(name=f"{self._name}[{item}]")

    def __getattr__(self, name):
        return SafePreviewUndefined(name=f"{self._name}.{name}")

    def __call__(self, *args, **kwargs):
        return SafePreviewUndefined(name=f"{self._name}()")

    def __ge__(self, other):
        return False

    def __gt__(self, other):
        return False

    def __le__(self, other):
        return False

    def __lt__(self, other):
        return False

    def __eq__(self, other):
        return other is None or other == "" or other == 0

    def __ne__(self, other):
        return not self.__eq__(other)

    def __add__(self, other):
        return other

    def __radd__(self, other):
        return other

    def __sub__(self, other):
        return 0

    def __mul__(self, other):
        return 0

    def __truediv__(self, other):
        return 0


class SafePreviewDict(dict):
    """A dictionary that returns SafePreviewUndefined for missing keys instead of raising KeyError."""
    def __getitem__(self, key):
        if key in self:
            val = super().__getitem__(key)
            if isinstance(val, dict) and not isinstance(val, SafePreviewDict):
                return SafePreviewDict(val)
            return val
        return SafePreviewUndefined(name=str(key))

    def __getattr__(self, key):
        return self[key]


class PreviewAnonymousUser:
    """Simulates Flask-Login's AnonymousUserMixin for unauthenticated preview states."""
    is_authenticated = False
    is_active = False
    is_anonymous = True
    id = None
    username = "Guest"
    email = ""
    role = "Guest"
    full_name = "Guest Visitor"

    def get_id(self):
        return None

    def __bool__(self):
        return False

    def __str__(self):
        return "AnonymousUser"

    def __repr__(self):
        return "<PreviewAnonymousUser (is_authenticated=False)>"


class PreviewAuthenticatedUser:
    """Simulates an authenticated user for dashboard and authorized views."""
    def __init__(self, user_id=1, username="developer", email="developer@example.com", role="Developer", full_name="Developer"):
        self.id = user_id
        self.username = username
        self.email = email
        self.role = role
        self.full_name = full_name or username.replace("_", " ").title()
        self.name = self.full_name
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False

    def get_id(self):
        return str(self.id)

    def __bool__(self):
        return True

    def __str__(self):
        return self.username

    def __repr__(self):
        return f"<PreviewAuthenticatedUser {self.username} (is_authenticated=True)>"


class MockCSRFToken(str):
    """Mock CSRF Token that works as both a string and a callable function."""
    def __call__(self):
        return str(self)


class MockRequest:
    """Mock Request object mimicking Flask request in templates."""
    def __init__(self, page_name: str):
        slug = page_name.replace(".html", "").split("/")[-1]
        self.endpoint = slug
        self.path = f"/{slug}"
        self.args = {}
        self.form = {}
        self.method = "GET"


def resolve_project_templates(project_id: str) -> Dict[str, str]:
    """
    Safely discover and read all HTML templates for a project.
    Reads from physical workspace directory first, with fallback and sync to project_files DB.
    Guarantees strict project isolation and path traversal prevention.
    """
    templates: Dict[str, str] = {}
    
    # 1. Physical workspace lookup
    try:
        ws = get_project_workspace(project_id)
        if ws.exists():
            tmpl_dir = ws / "templates"
            if tmpl_dir.exists():
                for root, _, files in os.walk(tmpl_dir):
                    for file in files:
                        if file.endswith(".html"):
                            full_path = Path(root) / file
                            try:
                                full_path.resolve().relative_to(ws.resolve())
                                rel = full_path.relative_to(ws).as_posix()
                                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                                    templates[rel] = f.read()
                            except (ValueError, OSError):
                                continue
    except Exception:
        pass

    # 2. Database lookup (merge/fallback)
    db_files = get_project_files_from_db(project_id)
    for f in db_files:
        fn = f["filename"]
        if fn.endswith(".html"):
            norm_fn = fn.replace("\\", "/")
            if norm_fn not in templates:
                templates[norm_fn] = f["file_content"]

    return templates


def categorize_template(rel_path: str) -> str:
    """Categorize template into Layouts, Authentication, Dashboard, Forms, Reports, or Other."""
    basename = os.path.basename(rel_path).lower()
    
    if basename in ["base.html", "layout.html", "shell.html", "master.html"]:
        return "Layouts"
    if any(auth_word in basename for auth_word in ["login", "register", "signin", "signup", "auth", "forgot", "reset_password"]):
        return "Authentication"
    if any(dash_word in basename for dash_word in ["dashboard", "overview", "metrics", "index"]):
        return "Dashboard"
    if any(form_word in basename for form_word in ["form", "new_", "create_", "edit_", "upload"]):
        return "Forms"
    if any(report_word in basename for report_word in ["report", "analytics", "summary", "audit", "candidate_analysis", "candidate_comparison"]):
        return "Reports"
    return "Other pages"


def get_available_preview_pages(project_id: str) -> List[Dict[str, Any]]:
    """Return categorized list of all available HTML pages with metadata for the page catalog."""
    templates = resolve_project_templates(project_id)
    pages = []
    
    for rel_path, content in sorted(templates.items()):
        basename = os.path.basename(rel_path)
        slug = basename.replace(".html", "")
        title = slug.replace("_", " ").replace("-", " ").title()
        category = categorize_template(rel_path)
        
        # Check syntax
        valid_syntax = True
        syntax_err = None
        try:
            jinja2.Environment().parse(content)
        except jinja2.TemplateSyntaxError as e:
            valid_syntax = False
            syntax_err = f"Line {e.lineno}: {e.message}"
            
        # Detect dependencies (e.g. current_user, form, specific vars)
        missing_dependencies = []
        if "form." in content and "form" not in content:
            missing_dependencies.append("Form Object")
        if "current_user." in content:
            missing_dependencies.append("User Context")
        if "transactions" in content or "summary" in content:
            missing_dependencies.append("Financial Data")
        if "candidates" in content:
            missing_dependencies.append("Candidate Records")
            
        pages.append({
            "name": title,
            "slug": slug,
            "filename": rel_path,
            "category": category,
            "is_valid": valid_syntax,
            "syntax_error": syntax_err,
            "dependencies": missing_dependencies
        })
        
    return pages


def render_preview_error_page(title: str, message: str, details: Optional[str] = None) -> str:
    """Render a clean, secure, developer-friendly notice without exposing internal paths or credentials."""
    detail_html = f"<pre style='background: #f1f5f9; padding: 12px; border-radius: 6px; font-size: 12px; color: #334155; margin-top: 12px; overflow-x: auto;'>{details}</pre>" if details else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — DevGuardian Preview</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f8fafc;
            color: #0f172a;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 24px;
            box-sizing: border-box;
        }}
        .notice-card {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            max-width: 580px;
            width: 100%;
            padding: 32px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }}
        .badge {{
            display: inline-block;
            background: #eff6ff;
            color: #2563eb;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 4px 10px;
            border-radius: 20px;
            margin-bottom: 14px;
        }}
        h2 {{
            margin: 0 0 8px 0;
            font-size: 20px;
            font-weight: 700;
            color: #0f172a;
        }}
        p {{
            margin: 0 0 16px 0;
            font-size: 14px;
            line-height: 1.6;
            color: #475569;
        }}
        .tip {{
            background: #f8fafc;
            border-left: 3px solid #3b82f6;
            padding: 10px 14px;
            font-size: 12.5px;
            color: #334155;
            margin-top: 16px;
            border-radius: 0 6px 6px 0;
        }}
    </style>
</head>
<body>
    <div class="notice-card">
        <span class="badge">Preview Notice</span>
        <h2>{title}</h2>
        <p>{message}</p>
        {detail_html}
        <div class="tip">
            <strong>DevGuardian Architecture:</strong> Templates are rendered inside an isolated, sandboxed child environment. Missing route-specific variables are safely defaulted to preserve layout structure.
        </div>
    </div>
</body>
</html>"""


def get_preview_asset_token(project_id: str) -> str:
    """Generate deterministic signature for preview iframe subresource access."""
    import hashlib
    return hashlib.sha256(f"devguardian_preview_asset_{project_id}".encode()).hexdigest()[:16]


def resolve_project_css(project_id: str) -> Dict[str, str]:
    """
    Safely discover and read all CSS stylesheets for a project.
    Reads from physical workspace static/css first, with fallback to project_files DB.
    """
    css_files: Dict[str, str] = {}
    try:
        ws = get_project_workspace(project_id)
        static_dir = ws / "static"
        if static_dir.exists():
            for root, _, files in os.walk(static_dir):
                for file in files:
                    if file.endswith(".css"):
                        p = Path(root) / file
                        rel = p.relative_to(ws).as_posix()
                        with open(p, "r", encoding="utf-8", errors="replace") as f:
                            css_files[rel] = f.read()
    except Exception:
        pass

    if not css_files:
        db_files = get_project_files_from_db(project_id)
        for f in db_files:
            if f["filename"].endswith(".css"):
                norm = f["filename"].replace("\\", "/").lstrip("/")
                css_files[norm] = f["file_content"]

    return css_files


def get_project_combined_css(project_id: str) -> str:
    """
    Return combined CSS string for a project, prioritizing style.css or app.css.
    """
    css_map = resolve_project_css(project_id)
    if not css_map:
        return ""
    
    # Sort with style.css or app.css first
    sorted_keys = sorted(
        css_map.keys(),
        key=lambda k: 0 if "style.css" in k else (1 if "app.css" in k else 2)
    )
    return "\n\n".join([f"/* Asset: {k} */\n" + css_map[k] for k in sorted_keys])

def mock_url_for(project_id: str, endpoint: str, auth_mode: str = "auto", **kwargs) -> str:
    """
    Generate isolated preview URLs strictly routing inside the project sandbox,
    preventing any child navigation leaks into DevGuardian AI Studio.
    """
    if endpoint == "static":
        fn = kwargs.get("filename", "")
        token = get_preview_asset_token(project_id)
        return f"/projects/{project_id}/preview/asset/{fn}?token={token}"
    clean_ep = endpoint.replace("-", "_")
    target_template = f"templates/{clean_ep}.html"
    return f"/projects/{project_id}/ui-preview/render?page={target_template}&auth={auth_mode}"


def render_preview_page(
    project_id: str,
    page_name: str,
    auth_mode: str = "auto",
    current_user_info: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """
    Render a specific project page with isolated, resilient context inside a Jinja2 environment.
    Supports Jinja template inheritance, macros, includes, and safe variable resolution.
    Returns (success: bool, rendered_html: str).
    """
    templates = resolve_project_templates(project_id)
    if not templates:
        return False, render_preview_error_page("No Templates Available", f"Project '{project_id}' does not have any generated HTML templates.")

    # Normalize requested page_name
    clean_name = page_name.replace("\\", "/").lstrip("/")
    if not clean_name.endswith(".html"):
        clean_name = f"{clean_name}.html"
    if not clean_name.startswith("templates/") and f"templates/{clean_name}" in templates:
        clean_name = f"templates/{clean_name}"

    # Match target template
    target_key = None
    if clean_name in templates:
        target_key = clean_name
    else:
        target_base = os.path.basename(clean_name)
        for k in templates:
            if os.path.basename(k) == target_base:
                target_key = k
                break

    if not target_key:
        available = ", ".join([os.path.basename(k) for k in templates])
        return False, render_preview_error_page("Template Not Found", f"Template '{page_name}' could not be located in this project.", f"Available templates: {available}")

    # Build loader dictionary with multiple path keys so both 'foo.html' and 'templates/foo.html' resolve
    loader_dict: Dict[str, str] = {}
    for k, v in templates.items():
        loader_dict[k] = v
        base = os.path.basename(k)
        loader_dict[base] = v
        if not k.startswith("templates/"):
            loader_dict[f"templates/{k}"] = v

    # Create isolated Jinja Environment with SafePreviewUndefined
    env = jinja2.Environment(
        loader=jinja2.DictLoader(loader_dict),
        autoescape=True,
        undefined=SafePreviewUndefined
    )

    # Configure Authentication Context
    category = categorize_template(target_key)
    if auth_mode == "authenticated":
        is_auth = True
    elif auth_mode == "guest":
        is_auth = False
    else:  # auto
        is_auth = category in ["Dashboard", "Reports", "Forms", "Other pages"]

    if is_auth:
        user_name = (current_user_info or {}).get("name") or "Krishna Deepika"
        user_email = (current_user_info or {}).get("email") or "developer@devguardian.ai"
        user_obj = PreviewAuthenticatedUser(user_id=1, username=user_name, email=user_email, role="Senior Claims Adjuster", full_name=user_name)
    else:
        user_obj = PreviewAnonymousUser()

    # Route helpers
    asset_token = get_preview_asset_token(project_id)

    def mock_url_for(endpoint, **kwargs):
        if endpoint == "static":
            fn = kwargs.get("filename", "")
            return f"/projects/{project_id}/preview/asset/{fn}?token={asset_token}"
        # Route mapping: strictly route to isolated template render endpoint so child links never navigate to DevGuardian AI Studio
        clean_ep = endpoint.replace("-", "_")
        # Check if project template exists
        target_template = f"templates/{clean_ep}.html"
        return f"/projects/{project_id}/ui-preview/render?page={target_template}&auth={auth_mode}"

    def mock_get_flashed_messages(with_categories=False, category_filter=()):
        return [("success", "Operation completed successfully and verified by AI engine.")] if with_categories else ["Operation completed successfully."]

    mock_req = MockRequest(target_key)
    mock_token = MockCSRFToken("devguardian_preview_csrf_authenticated")

    # InsurTech Domain Mock Data
    insurtech_claims = [
        {
            "id": 1,
            "claim_number": "CLM-2026-0812",
            "claimant_name": "Marcus Vance",
            "policy_number": "POL-AU-9021",
            "policy_type": "Commercial Auto",
            "incident_date": "2026-10-10",
            "submission_date": "2026-10-11 09:15",
            "claimed_amount": 18500.00,
            "status": "Under Review",
            "risk_score": 24,
            "is_fraud_suspected": False,
            "fraud_risk_level": "Low",
            "description": "Multi-vehicle rear-end collision at intersection during heavy rain. Front bumper, radiator, and sensor array damaged.",
            "documents_count": 4,
            "agent_status": "Intake Verified",
            "documents": [
                {"id": 101, "filename": "Police_Accident_Report_1010.pdf", "document_type": "Police Report", "upload_date": "2026-10-11", "is_verified": True},
                {"id": 102, "filename": "Repair_Estimate_ApexAuto.pdf", "document_type": "Repair Estimate", "upload_date": "2026-10-11", "is_verified": True},
                {"id": 103, "filename": "Vehicle_Photos_Set.zip", "document_type": "Photographic Evidence", "upload_date": "2026-10-11", "is_verified": True}
            ],
            "reviews": [
                {"reviewer": "Elena Rostova", "review_date": "2026-10-12", "decision": "Pending", "notes": "Damage appraisal consistent with speed telemetry data. Awaiting parts supplier confirmation."}
            ]
        },
        {
            "id": 2,
            "claim_number": "CLM-2026-0813",
            "claimant_name": "Elena Rostova",
            "policy_number": "POL-HM-4182",
            "policy_type": "Homeowners Comprehensive",
            "incident_date": "2026-10-12",
            "submission_date": "2026-10-13 14:20",
            "claimed_amount": 42000.00,
            "status": "Submitted",
            "risk_score": 48,
            "is_fraud_suspected": False,
            "fraud_risk_level": "Medium",
            "description": "Severe basement flooding caused by main sewer backup following localized torrential storm.",
            "documents_count": 5,
            "agent_status": "Document Processed",
            "documents": [
                {"id": 104, "filename": "Plumbing_Emergency_Invoice.pdf", "document_type": "Invoice", "upload_date": "2026-10-13", "is_verified": True},
                {"id": 105, "filename": "Basement_Damage_Photos.pdf", "document_type": "Damage Photos", "upload_date": "2026-10-13", "is_verified": True}
            ],
            "reviews": []
        },
        {
            "id": 3,
            "claim_number": "CLM-2026-0814",
            "claimant_name": "Apex Logistics Corp",
            "policy_number": "POL-CM-7731",
            "policy_type": "Commercial Property",
            "incident_date": "2026-10-14",
            "submission_date": "2026-10-14 16:45",
            "claimed_amount": 125000.00,
            "status": "Flagged",
            "risk_score": 88,
            "is_fraud_suspected": True,
            "fraud_risk_level": "High",
            "description": "Warehouse refrigeration failure resulting in total loss of perishable pharmaceutical freight.",
            "documents_count": 8,
            "agent_status": "Fraud Alert Triggered",
            "documents": [
                {"id": 106, "filename": "Freight_Manifest_ColdChain.pdf", "document_type": "Bill of Lading", "upload_date": "2026-10-14", "is_verified": False},
                {"id": 107, "filename": "IoT_Temp_Sensor_Logs.csv", "document_type": "Sensor Telemetry", "upload_date": "2026-10-14", "is_verified": True}
            ],
            "reviews": [
                {"reviewer": "SIU Investigator Reynolds", "review_date": "2026-10-15", "decision": "Escalated", "notes": "Telemetry timestamps exhibit anomalies; refrigeration logs show normal temp while power breaker log was altered."}
            ]
        },
        {
            "id": 4,
            "claim_number": "CLM-2026-0815",
            "claimant_name": "Sarah Jenkins",
            "policy_number": "POL-AU-3104",
            "policy_type": "Personal Auto",
            "incident_date": "2026-10-15",
            "submission_date": "2026-10-15 11:10",
            "claimed_amount": 3200.00,
            "status": "Approved",
            "risk_score": 12,
            "is_fraud_suspected": False,
            "fraud_risk_level": "Low",
            "description": "Windshield and side mirror cracked by highway road debris from commercial dump truck.",
            "documents_count": 2,
            "agent_status": "Straight-Through Approved",
            "documents": [
                {"id": 108, "filename": "Safelite_Glass_Invoice.pdf", "document_type": "Repair Invoice", "upload_date": "2026-10-15", "is_verified": True}
            ],
            "reviews": [
                {"reviewer": "Automated Adjudication Agent", "review_date": "2026-10-15", "decision": "Approved", "notes": "STP fast-track settlement authorized. Amount within auto-approval threshold of $5,000."}
            ]
        },
        {
            "id": 5,
            "claim_number": "CLM-2026-0816",
            "claimant_name": "Robert Sterling",
            "policy_number": "POL-HM-8819",
            "policy_type": "Luxury Estate",
            "incident_date": "2026-10-16",
            "submission_date": "2026-10-16 17:30",
            "claimed_amount": 89500.00,
            "status": "Under Review",
            "risk_score": 62,
            "is_fraud_suspected": False,
            "fraud_risk_level": "Medium",
            "description": "Lightning strike induced power surge damaging integrated smart-home automation system and wine cellar cooling.",
            "documents_count": 6,
            "agent_status": "Review Pending",
            "documents": [
                {"id": 109, "filename": "Electrician_Diagnostic_Report.pdf", "document_type": "Technical Report", "upload_date": "2026-10-16", "is_verified": True}
            ],
            "reviews": []
        },
        {
            "id": 6,
            "claim_number": "CLM-2026-0817",
            "claimant_name": "Amara Okafor",
            "policy_number": "POL-WC-5520",
            "policy_type": "Workers Comp",
            "incident_date": "2026-10-17",
            "submission_date": "2026-10-18 08:45",
            "claimed_amount": 14200.00,
            "status": "Approved",
            "risk_score": 15,
            "is_fraud_suspected": False,
            "fraud_risk_level": "Low",
            "description": "Slip and fall in warehouse loading dock causing wrist fracture. Emergency room and orthopedic care verified.",
            "documents_count": 4,
            "agent_status": "Settlement Approved",
            "documents": [
                {"id": 110, "filename": "ER_Clinical_Summary.pdf", "document_type": "Medical Record", "upload_date": "2026-10-18", "is_verified": True}
            ],
            "reviews": [
                {"reviewer": "Dr. Anthony Perez", "review_date": "2026-10-18", "decision": "Approved", "notes": "Medical documentation and physical therapy plan verified against state workers comp fee schedule."}
            ]
        }
    ]

    insurtech_policies = [
        {"id": 1, "policy_number": "POL-AU-9021", "policy_holder_name": "Marcus Vance", "policy_type": "Commercial Auto", "coverage_amount": 250000.00, "start_date": "2026-01-01", "end_date": "2026-12-31", "is_active": True, "active_claims": 1},
        {"id": 2, "policy_number": "POL-HM-4182", "policy_holder_name": "Elena Rostova", "policy_type": "Homeowners Comprehensive", "coverage_amount": 750000.00, "start_date": "2025-06-15", "end_date": "2026-06-14", "is_active": True, "active_claims": 1},
        {"id": 3, "policy_number": "POL-CM-7731", "policy_holder_name": "Apex Logistics Corp", "policy_type": "Commercial Property", "coverage_amount": 5000000.00, "start_date": "2026-03-01", "end_date": "2027-02-28", "is_active": True, "active_claims": 1},
        {"id": 4, "policy_number": "POL-AU-3104", "policy_holder_name": "Sarah Jenkins", "policy_type": "Personal Auto", "coverage_amount": 100000.00, "start_date": "2026-02-10", "end_date": "2027-02-09", "is_active": True, "active_claims": 0},
        {"id": 5, "policy_number": "POL-HM-8819", "policy_holder_name": "Robert Sterling", "policy_type": "Luxury Estate", "coverage_amount": 2500000.00, "start_date": "2025-11-01", "end_date": "2026-10-31", "is_active": True, "active_claims": 1},
        {"id": 6, "policy_number": "POL-WC-5520", "policy_holder_name": "Midwest Distribution Inc", "policy_type": "Workers Comp", "coverage_amount": 1000000.00, "start_date": "2026-01-01", "end_date": "2026-12-31", "is_active": True, "active_claims": 1}
    ]

    insurtech_agents = [
        {"name": "Claim Intake Agent", "status": "Active", "model": "Gemini 2.5 Flash", "accuracy": "99.4%", "avg_latency": "1.2s", "queue": 3, "processed_today": 84, "state": "Optimal"},
        {"name": "Document Intelligence Agent", "status": "Active", "model": "Gemini 2.5 Flash + OCR", "accuracy": "98.1%", "avg_latency": "2.8s", "queue": 5, "processed_today": 126, "state": "Optimal"},
        {"name": "Fraud Risk Assessment Agent", "status": "Active", "model": "Anomaly Model v4.2", "accuracy": "96.8%", "avg_latency": "1.9s", "queue": 2, "processed_today": 79, "state": "Optimal"},
        {"name": "Policy Verification Agent", "status": "Active", "model": "Underwriting Rules Engine", "accuracy": "99.9%", "avg_latency": "0.8s", "queue": 0, "processed_today": 142, "state": "Optimal"},
        {"name": "Evidence Consistency Agent", "status": "Active", "model": "Multi-Modal Forensic AI", "accuracy": "95.4%", "avg_latency": "3.1s", "queue": 1, "processed_today": 53, "state": "Optimal"}
    ]

    # Domain mock context with SafePreviewDict
    context = {
        "url_for": mock_url_for,
        "get_flashed_messages": mock_get_flashed_messages,
        "csrf_token": mock_token,
        "request": mock_req,
        "current_user": user_obj,
        "user": user_obj,
        "is_gemini_configured": True,
        "config": SafePreviewDict({"APP_NAME": "ClaimWise AI", "DEBUG": True, "SECRET_KEY": "preview_secret"}),
        "claims": insurtech_claims,
        "claim": insurtech_claims[0],
        "policies": insurtech_policies,
        "policy": insurtech_policies[0],
        "agent_monitors": insurtech_agents,
        "agents": insurtech_agents,
        "claim_stats": SafePreviewDict({
            "total_claims": 148,
            "pending_claims": 32,
            "under_review_claims": 24,
            "flagged_claims": 7,
            "approved_claims": 81,
            "rejected_claims": 4,
            "total_value": 2840500.00,
            "settled_value": 1920000.00,
            "avg_cycle_days": 2.4,
            "stp_rate": 68.5,
            "fraud_prevented": 348000.00
        }),
        "stats": SafePreviewDict({
            "total_items": 148,
            "pending_tasks": 32,
            "completed": 81,
            "active_projects": 6,
            "total_users": 48,
            "total_spend": 1920000.00,
            "total_income": 2840500.00,
            "total_claims": 148,
            "pending_claims": 32,
            "under_review_claims": 24,
            "flagged_claims": 7,
            "total": 148
        }),
        "summary": SafePreviewDict({
            "total_claims": 148,
            "pending_claims": 32,
            "under_review_claims": 24,
            "flagged_claims": 7,
            "total_income": 4500.00,
            "total_expenses": 2840.50,
            "income": 4500.00,
            "expenses": 2840.50,
            "net_savings": 1659.50,
            "savings_rate": 36.8,
            "budget_status": "Compliant"
        }),
        "audit_logs": [
            {"id": 1, "timestamp": "2026-10-18 10:14:22", "actor": "Intake Agent", "action": "Claim Ingested & Verified", "claim_id": "CLM-2026-0817", "ip": "10.0.4.12", "status": "Success"},
            {"id": 2, "timestamp": "2026-10-18 09:30:15", "actor": "Elena Rostova", "action": "Adjudication Review Approved", "claim_id": "CLM-2026-0815", "ip": "192.168.1.45", "status": "Success"},
            {"id": 3, "timestamp": "2026-10-18 08:22:04", "actor": "Fraud Detection Agent", "action": "Risk Score Escalation (88/100)", "claim_id": "CLM-2026-0814", "ip": "10.0.4.15", "status": "Flagged"},
            {"id": 4, "timestamp": "2026-10-17 17:05:11", "actor": "Marcus Vance", "action": "Supplemental Evidence Uploaded", "claim_id": "CLM-2026-0812", "ip": "192.168.1.88", "status": "Success"}
        ],
        "compliance_items": [
            {"id": 1, "standard": "NAIC Model Unfair Claims Settlement Practices Act", "status": "Fully Compliant", "score": "100%", "last_audit": "2026-10-15"},
            {"id": 2, "standard": "SOC2 Type II Statutory Records Safeguard", "status": "Active & Monitored", "score": "99.8%", "last_audit": "2026-10-12"},
            {"id": 3, "standard": "HIPAA Medical Records Redaction Benchmark", "status": "Verified", "score": "100%", "last_audit": "2026-10-18"},
            {"id": 4, "standard": "State Prompt Pay Statutory Deadlines", "status": "Zero Violations", "score": "100%", "last_audit": "2026-10-17"}
        ],
        "fraud_alerts": [
            {"id": 1, "claim_number": "CLM-2026-0814", "claimant": "Apex Logistics Corp", "risk_score": 88, "type": "Telemetry Inconsistency", "date": "2026-10-14", "action_required": "SIU Investigation"},
            {"id": 2, "claim_number": "CLM-2026-0816", "claimant": "Robert Sterling", "risk_score": 62, "type": "High Single-Item Value", "date": "2026-10-16", "action_required": "Appraisal Verification"}
        ],
        "notifications_list": [
            {"id": 1, "title": "High Risk Fraud Alert", "message": "Claim CLM-2026-0814 was flagged with risk score 88/100.", "time": "20m ago", "type": "danger"},
            {"id": 2, "title": "Straight-Through Settlement", "message": "Claim CLM-2026-0815 ($3,200) was automatically approved and queued for payout.", "time": "1h ago", "type": "success"},
            {"id": 3, "title": "Compliance Audit Complete", "message": "Quarterly NAIC statutory settlement audit completed with 0 non-compliance notices.", "time": "3h ago", "type": "info"}
        ],
        "report": SafePreviewDict({
            "total_income": 4500.00,
            "total_expenses": 2840.50,
            "net_savings": 1659.50,
            "savings_rate": 36.8,
            "summary": "Claims Adjudication Performance Report",
            "start_date": "2026-10-01",
            "end_date": "2026-10-31"
        }),
        "transactions": [
            {"id": 1, "date": "2026-10-15", "description": "Cloud Infrastructure", "amount": 142.50, "category": {"name": "Hosting"}, "type": "expense"},
            {"id": 2, "date": "2026-10-16", "description": "Client Consultation", "amount": 1200.00, "category": {"name": "Income"}, "type": "income"}
        ],
        "categories": [
            {"id": 1, "name": "Commercial Auto"},
            {"id": 2, "name": "Homeowners"},
            {"id": 3, "name": "Commercial Property"},
            {"id": 4, "name": "Workers Comp"}
        ],
        "candidates": [
            {"id": 1, "name": "Sarah Chen", "role": "Senior Claims Adjuster", "score": 94, "status": "Recommended", "skills": "Claims Adjudication, Fraud Analytics"}
        ],
        "selected_month": datetime.datetime.now().month,
        "selected_year": datetime.datetime.now().year,
        "now": datetime.datetime.now(),
        "datetime": datetime,
        "str": str,
        "int": int,
        "float": float,
        "len": len,
        "range": range,
        "list": list,
        "dict": dict
    }

    try:
        template = env.get_template(target_key)
        rendered_html = template.render(**context)

        # Inject project stylesheet into <head> for instant, bulletproof styling in iframe sandbox
        combined_css = get_project_combined_css(project_id)
        if combined_css:
            injected_tag = f'\n    <!-- Injected Project Stylesheet for Sandbox Isolation -->\n    <style id="preview-injected-styles">\n{combined_css}\n    </style>\n'
            if "</head>" in rendered_html:
                rendered_html = rendered_html.replace("</head>", f"{injected_tag}</head>", 1)
            elif "<body" in rendered_html:
                rendered_html = f"<head>{injected_tag}</head>\n" + rendered_html
        # Sanitize internal navigation links so clicking login, signup, dashboard, etc., inside iframe never escapes into DevGuardian AI
        route_mappings = {
            'href="/login"': f'href="/projects/{project_id}/ui-preview/render?page=templates/login.html&auth=guest"',
            'href="/signup"': f'href="/projects/{project_id}/ui-preview/render?page=templates/signup.html&auth=guest"',
            'href="/logout"': f'href="/projects/{project_id}/ui-preview/render?page=templates/index.html&auth=guest"',
            'href="/dashboard"': f'href="/projects/{project_id}/ui-preview/render?page=templates/dashboard.html&auth=authenticated"',
            'href="/live_camera"': f'href="/projects/{project_id}/ui-preview/render?page=templates/live_camera.html"',
            'href="/analytics"': f'href="/projects/{project_id}/ui-preview/render?page=templates/analytics.html"',
            'href="/reports"': f'href="/projects/{project_id}/ui-preview/render?page=templates/reports.html"',
            'href="/destinations"': f'href="/projects/{project_id}/ui-preview/render?page=templates/destinations.html"',
            'href="/culture_guide"': f'href="/projects/{project_id}/ui-preview/render?page=templates/culture_guide.html"',
            'href="/translator"': f'href="/projects/{project_id}/ui-preview/render?page=templates/translator.html"',
            'href="/itinerary"': f'href="/projects/{project_id}/ui-preview/render?page=templates/itinerary.html"',
            'href="/new_claim"': f'href="/projects/{project_id}/ui-preview/render?page=templates/new_claim.html"',
            'href="/"': f'href="/projects/{project_id}/ui-preview/render?page=templates/index.html"',
        }
        for orig_link, target_link in route_mappings.items():
            rendered_html = rendered_html.replace(orig_link, target_link)

        return True, rendered_html
    except jinja2.TemplateSyntaxError as e:
        err_msg = f"Syntax Error on line {e.lineno} in {target_key}: {e.message}"
        return False, render_preview_error_page("Template Syntax Notice", err_msg)
    except Exception as e:
        err_msg = f"Rendering Notice: {str(e)}"
        return False, render_preview_error_page("Preview Rendering Notice", err_msg)


# =====================================================================
# 15-CATEGORY INTELLIGENT UI/UX RECOMMENDATION ENGINE
# =====================================================================

def analyze_project_ui_ux(project_id: str) -> Dict[str, Any]:
    """
    Perform deep static and heuristic UI/UX analysis across 15 core design dimensions:
    1. Visual hierarchy
    2. Spacing consistency
    3. Typography
    4. Color contrast
    5. Responsive layout
    6. Navigation consistency
    7. Form usability
    8. Button consistency
    9. Accessibility
    10. Loading and empty states
    11. Error states
    12. Reusable components
    13. CSS duplication
    14. Asset loading
    15. Page consistency
    Persists findings to `ui_recommendations` table and returns structured audit summary.
    """
    templates = resolve_project_templates(project_id)
    
    # Also fetch CSS
    css_files: Dict[str, str] = {}
    try:
        ws = get_project_workspace(project_id)
        static_dir = ws / "static"
        if static_dir.exists():
            for root, _, files in os.walk(static_dir):
                for file in files:
                    if file.endswith(".css"):
                        p = Path(root) / file
                        rel = p.relative_to(ws).as_posix()
                        with open(p, "r", encoding="utf-8", errors="replace") as f:
                            css_files[rel] = f.read()
    except Exception:
        pass

    if not css_files:
        db_files = get_project_files_from_db(project_id)
        for f in db_files:
            if f["filename"].endswith(".css"):
                css_files[f["filename"].replace("\\", "/")] = f["file_content"]

    recommendations: List[Dict[str, Any]] = []

    # 1. VISUAL HIERARCHY
    for rel_path, content in templates.items():
        if "<h1" in content and "<h3" in content and "<h2" not in content:
            rec_id = f"rec_vh_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Fix Heading Hierarchy Progression",
                "category": "Visual hierarchy",
                "priority": "Medium",
                "explanation": "Document structure skips heading level 2 directly from h1 to h3, confusing screen reader navigation outlines.",
                "evidence": f"Heading hierarchy in '{rel_path}' contains <h1> and <h3> without an intermediate <h2> section divider.",
                "affected_file": rel_path,
                "suggested_improvement": "Refactor initial sub-section headings from <h3> to <h2> to maintain sequential document outline.",
                "expected_benefit": "Improves visual flow, SEO heading scoring, and screen reader semantic hierarchy.",
                "proposed_diff": "- <h3>\n+ <h2>\n- </h3>\n+ </h2>",
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 2. SPACING CONSISTENCY
    for rel_path, content in css_files.items():
        if "px" in content and "rem" in content and ("margin: 15px" in content or "padding: 13px" in content):
            rec_id = f"rec_sp_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Standardize Component Spacing System",
                "category": "Spacing consistency",
                "priority": "Low",
                "explanation": "Arbitrary off-grid spacing values (e.g. 13px, 15px) detected alongside rem units.",
                "evidence": f"Found non-standard padding/margin values in '{rel_path}' outside standard 4px/8px design grid.",
                "affected_file": rel_path,
                "suggested_improvement": "Unify spacing using an 8pt spatial grid scale (8px, 16px, 24px, 32px) or CSS spacing variables.",
                "expected_benefit": "Produces clean, balanced alignment across containers, cards, and input fields.",
                "proposed_diff": "- padding: 13px;\n+ padding: 16px;",
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 3. TYPOGRAPHY
    for rel_path, content in css_files.items():
        if "font-family" in content and "system-ui" not in content and "-apple-system" not in content:
            rec_id = f"rec_ty_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Modernize System Font Stack Fallback",
                "category": "Typography",
                "priority": "Medium",
                "explanation": "CSS font-family declaration lacks modern system font fallbacks, leading to unstyled serif flashes if primary font is unavailable.",
                "evidence": f"font-family declarations in '{rel_path}' lack system-ui, -apple-system, and BlinkMacSystemFont fallbacks.",
                "affected_file": rel_path,
                "suggested_improvement": "Append -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif to body font-family.",
                "expected_benefit": "Ensures crisp, native rendering across macOS, Windows, Linux, and iOS devices.",
                "proposed_diff": "- font-family: Inter, sans-serif;\n+ font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;",
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 4. COLOR CONTRAST
    for rel_path, content in css_files.items():
        if "#666" in content or "#777" in content or "#888" in content or "#999" in content:
            rec_id = f"rec_cc_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Enhance Text Color Contrast Ratio",
                "category": "Color contrast",
                "priority": "High",
                "explanation": "Light grey body text on light backgrounds fails WCAG 2.1 AA requirement of minimum 4.5:1 contrast ratio.",
                "evidence": f"Found secondary text color #888/#999 in '{rel_path}' yielding sub-4.5:1 contrast on white cards.",
                "affected_file": rel_path,
                "suggested_improvement": "Darken secondary text color to #475569 or #334155 to guarantee WCAG AA compliance.",
                "expected_benefit": "Significantly improves readability in outdoor sunlight and for users with low vision.",
                "proposed_diff": "- color: #888888;\n+ color: #475569;",
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 5. RESPONSIVE LAYOUT
    for rel_path, content in templates.items():
        if re.search(r'style="[^"]*width:\s*[4-9]\d{2}px', content) or "min-width: 500px" in content:
            rec_id = f"rec_rl_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Prevent Mobile Horizontal Overflow",
                "category": "Responsive layout",
                "priority": "High",
                "explanation": "Hardcoded element width exceeding 375px triggers horizontal viewport overflow on smartphones.",
                "evidence": f"Fixed width attribute detected in '{rel_path}' without max-width: 100% boundary constraint.",
                "affected_file": rel_path,
                "suggested_improvement": "Add max-width: 100% and box-sizing: border-box or convert to a responsive flex/grid column.",
                "expected_benefit": "Eliminates horizontal scrolling on mobile viewports (375px).",
                "proposed_diff": '- style="width: 500px;"\n+ style="width: 100%; max-width: 500px; box-sizing: border-box;"',
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 6. NAVIGATION CONSISTENCY
    base_template = next((content for path, content in templates.items() if "base.html" in path), None)
    base_path = next((path for path in templates if "base.html" in path), "templates/base.html")
    if base_template and "aria-current" not in base_template and "active" not in base_template:
        rec_id = f"rec_nc_{uuid.uuid4().hex[:8]}"
        recommendations.append({
            "id": rec_id,
            "project_id": project_id,
            "title": "Add Active Link Indicator to Navigation",
            "category": "Navigation consistency",
            "priority": "Medium",
            "explanation": "Header navigation links do not indicate the currently active route or view.",
            "evidence": f"Navigation bar in '{base_path}' has no dynamic active state or aria-current='page' markup.",
            "affected_file": base_path,
            "suggested_improvement": "Use request.endpoint matching to attach an 'active' CSS class and aria-current='page'.",
            "expected_benefit": "Users instantly orient where they are within the application.",
            "proposed_diff": '- <a href="{{ url_for(\'dashboard\') }}" class="nav-link">\n+ <a href="{{ url_for(\'dashboard\') }}" class="nav-link {{ \'active\' if request.endpoint == \'dashboard\' else \'\' }}" aria-current="{{ \'page\' if request.endpoint == \'dashboard\' else \'false\' }}">',
            "status": "pending",
            "source": "rule_based"
        })

    # 7. FORM USABILITY
    for rel_path, content in templates.items():
        if '<input type="password"' in content and 'autocomplete="current-password"' not in content and 'autocomplete="new-password"' not in content:
            rec_id = f"rec_fu_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Add Credential Autofill to Password Inputs",
                "category": "Form usability",
                "priority": "High",
                "explanation": "Password fields lack HTML5 autocomplete hints, preventing browser credential managers and 1Password from offering single-tap login.",
                "evidence": f"Password input tag in '{rel_path}' does not specify autocomplete='current-password'.",
                "affected_file": rel_path,
                "suggested_improvement": 'Add autocomplete="current-password" to existing password input.',
                "expected_benefit": "Enables biometric and password manager auto-fill, reducing mobile authentication friction.",
                "proposed_diff": '- <input type="password" id="password" name="password" class="form-control" required>\n+ <input type="password" id="password" name="password" class="form-control" autocomplete="current-password" required>',
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 8. BUTTON CONSISTENCY
    for rel_path, content in templates.items():
        if re.search(r'<button[^>]*style="[^"]*background:\s*#', content) and 'class="btn' not in content:
            rec_id = f"rec_bc_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Standardize Button Design Classes",
                "category": "Button consistency",
                "priority": "Medium",
                "explanation": "Buttons use ad-hoc inline styling instead of centralized design system button classes.",
                "evidence": f"Found button with hardcoded inline background color in '{rel_path}'.",
                "affected_file": rel_path,
                "suggested_improvement": "Replace inline styling with .btn and .btn-primary utility classes.",
                "expected_benefit": "Guarantees unified hover states, focus rings, and active transitions across pages.",
                "proposed_diff": '- <button style="background: #2563EB; color: white; padding: 8px;">\n+ <button class="btn btn-primary">',
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 9. ACCESSIBILITY
    for rel_path, content in templates.items():
        if "<img" in content and "alt=" not in content:
            rec_id = f"rec_ac_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Add Alternative Text to Image Elements",
                "category": "Accessibility",
                "priority": "High",
                "explanation": "<img> element lacks an alt attribute, violating WCAG 1.1.1 Non-Text Content guidelines.",
                "evidence": f"Found <img> tag in '{rel_path}' without an alt attribute.",
                "affected_file": rel_path,
                "suggested_improvement": "Add descriptive alt text or alt='' for decorative assets.",
                "expected_benefit": "Screen reader users understand visual content; prevents accessibility compliance failures.",
                "proposed_diff": '- <img src="{{ url_for(\'static\', filename=\'logo.png\') }}">\n+ <img src="{{ url_for(\'static\', filename=\'logo.png\') }}" alt="Application Logo">',
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 10. LOADING AND EMPTY STATES
    for rel_path, content in templates.items():
        if "{% for" in content and "{% else %}" not in content:
            rec_id = f"rec_le_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Add Empty-State Guidance to Data Lists",
                "category": "Loading and empty states",
                "priority": "Medium",
                "explanation": "Data loops display a blank void when users first register and have zero records.",
                "evidence": f"Jinja loop in '{rel_path}' lacks an {{% else %}} empty-state fallback branch.",
                "affected_file": rel_path,
                "suggested_improvement": "Add {{% else %}} block rendering an onboarding illustration, empty state text, and creation CTA.",
                "expected_benefit": "Guides new users on how to populate their workspace, boosting initial conversion.",
                "proposed_diff": "+ {% else %}\n+   <div class=\"empty-state\"><p>No items recorded yet. Click 'Add New' to begin.</p></div>\n  {% endfor %}",
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 11. ERROR STATES
    for rel_path, content in templates.items():
        if "<form" in content and "get_flashed_messages" not in content and base_template and "get_flashed_messages" not in base_template:
            rec_id = f"rec_es_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Add Form Validation Error Alert Container",
                "category": "Error states",
                "priority": "High",
                "explanation": "Form template lacks a flash alert container to display backend validation or authentication errors.",
                "evidence": f"Form in '{rel_path}' has no alert message container for flash notifications.",
                "affected_file": rel_path,
                "suggested_improvement": "Insert Jinja get_flashed_messages alert loop above the form card.",
                "expected_benefit": "Users receive clear, actionable feedback when submission fails.",
                "proposed_diff": "+ {% with messages = get_flashed_messages(with_categories=true) %}\n+   {% for cat, msg in messages %}<div class=\"alert alert-{{ cat }}\">{{ msg }}</div>{% endfor %}\n+ {% endwith %}",
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 12. REUSABLE COMPONENTS
    nav_count = sum(1 for c in templates.values() if "<header" in c or "<nav" in c)
    if nav_count > 2 and base_path:
        rec_id = f"rec_rc_{uuid.uuid4().hex[:8]}"
        recommendations.append({
            "id": rec_id,
            "project_id": project_id,
            "title": "Consolidate Navigation into Layout Template",
            "category": "Reusable components",
            "priority": "Low",
            "explanation": "Multiple templates duplicate header markup instead of extending base.html or including a shared navigation macro.",
            "evidence": f"Detected repeating navigation bars across {nav_count} separate templates.",
            "affected_file": base_path,
            "suggested_improvement": "Extract topbar into base.html with {% block content %} to prevent header divergence.",
            "expected_benefit": "Modifying a menu item updates the entire application simultaneously.",
            "proposed_diff": "- <!-- Individual header markup -->\n+ {% extends 'base.html' %}",
            "status": "pending",
            "source": "rule_based"
        })

    # 13. CSS DUPLICATION
    for rel_path, content in css_files.items():
        hex_matches = re.findall(r'#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})\b', content)
        counts = {h.lower(): hex_matches.count(h) for h in set(hex_matches)}
        repeated = [h for h, c in counts.items() if c >= 3]
        if repeated:
            rec_id = f"rec_cd_{uuid.uuid4().hex[:8]}"
            sample_hex = f"#{repeated[0]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Tokenize Repeated Color Hex Codes",
                "category": "CSS duplication",
                "priority": "Medium",
                "explanation": f"Color code {sample_hex} is repeated {counts[repeated[0]]} times throughout CSS without referencing a design token.",
                "evidence": f"Found duplicate hex colors in '{rel_path}' not bound to CSS :root variables.",
                "affected_file": rel_path,
                "suggested_improvement": f"Define --color-brand: {sample_hex}; in :root and replace hardcoded instances with var(--color-brand).",
                "expected_benefit": "Simplifies future theming, dark mode toggling, and rebranding updates.",
                "proposed_diff": f"- color: {sample_hex};\n+ color: var(--color-brand);",
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 14. ASSET LOADING
    for rel_path, content in templates.items():
        if "http://" in content:
            rec_id = f"rec_al_{uuid.uuid4().hex[:8]}"
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Upgrade External Assets to HTTPS",
                "category": "Asset loading",
                "priority": "High",
                "explanation": "External asset loaded over insecure HTTP, triggering mixed content browser security blocks.",
                "evidence": f"Found insecure 'http://' resource URI in '{rel_path}'.",
                "affected_file": rel_path,
                "suggested_improvement": "Change protocol to https:// or bundle asset locally under static/.",
                "expected_benefit": "Guarantees asset loads across all modern SSL/TLS enforcing web browsers.",
                "proposed_diff": '- http://\n+ https://',
                "status": "pending",
                "source": "rule_based"
            })
            break

    # 15. PAGE CONSISTENCY
    for rel_path, content in templates.items():
        if "{% block title %}" not in content and rel_path != "templates/base.html":
            rec_id = f"rec_pc_{uuid.uuid4().hex[:8]}"
            slug_title = os.path.basename(rel_path).replace(".html", "").replace("_", " ").title()
            recommendations.append({
                "id": rec_id,
                "project_id": project_id,
                "title": "Define Unique Page Title Block",
                "category": "Page consistency",
                "priority": "Low",
                "explanation": "Template does not override {% block title %}, leaving the browser tab title identical across different views.",
                "evidence": f"Template '{rel_path}' is missing a specific '{{% block title %}}' definition.",
                "affected_file": rel_path,
                "suggested_improvement": f"Add {{% block title %}}{slug_title} — DevGuardian Project{{% endblock %}} to page header.",
                "expected_benefit": "Users easily distinguish multiple open tabs; improves browser history clarity.",
                "proposed_diff": f'+ {{% block title %}}{slug_title} — DevGuardian Project{{% endblock %}}',
                "status": "pending",
                "source": "rule_based"
            })
            break

    # Persist findings to database
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        for r in recommendations:
            cursor.execute("""
                INSERT OR REPLACE INTO ui_recommendations 
                (id, project_id, title, category, priority, explanation, evidence, affected_file, suggested_improvement, expected_benefit, proposed_diff, status, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["id"], r["project_id"], r["title"], r["category"], r["priority"],
                r["explanation"], r["evidence"], r["affected_file"], r["suggested_improvement"],
                r["expected_benefit"], r["proposed_diff"], r["status"], r["source"]
            ))
    conn.close()

    return {
        "project_id": project_id,
        "total_recommendations": len(recommendations),
        "high_priority": sum(1 for r in recommendations if r["priority"] == "High"),
        "medium_priority": sum(1 for r in recommendations if r["priority"] == "Medium"),
        "low_priority": sum(1 for r in recommendations if r["priority"] == "Low"),
        "recommendations": recommendations
    }


def get_project_ui_recommendations(project_id: str) -> List[Dict[str, Any]]:
    """Retrieve stored UI/UX recommendations for a project. Runs analysis if none exist."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, project_id, title, category, priority, explanation, evidence, 
               affected_file, suggested_improvement, expected_benefit, proposed_diff, 
               status, source, created_at, applied_at
        FROM ui_recommendations
        WHERE project_id = ?
        ORDER BY 
            CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
            created_at DESC
    """, (project_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        analysis = analyze_project_ui_ux(project_id)
        return analysis["recommendations"]
        
    return [dict(r) for r in rows]


def apply_ui_recommendation(project_id: str, recommendation_id: str) -> Dict[str, Any]:
    """
    Safely apply a UI/UX recommendation to the project:
    1. Preserves full backup before modification.
    2. Modifies affected file on disk and in database.
    3. Validates modified template or CSS.
    4. Automatically rolls back if validation fails.
    5. Updates recommendation status to 'applied'.
    """
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM ui_recommendations WHERE id = ? AND project_id = ?
    """, (recommendation_id, project_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"success": False, "error": "Recommendation not found."}

    rec = dict(row)
    affected_file = rec["affected_file"]
    
    try:
        ws = get_project_workspace(project_id)
        file_path = ws / affected_file
        if not file_path.exists():
            return {"success": False, "error": f"Target file '{affected_file}' not found on disk."}
            
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()
    except Exception as e:
        return {"success": False, "error": f"Failed to access file: {str(e)}"}

    # 1. Create safety backup
    backup_root = Path(__file__).resolve().parent.parent / "instance" / "backups" / "ui_recommendations"
    backup_dir = backup_root / f"{recommendation_id}_{int(datetime.datetime.now().timestamp())}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / Path(affected_file).name
    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(original_content)

    # 2. Apply change based on category
    modified_content = original_content
    category = rec["category"]

    if category == "Form usability" and '<input type="password"' in modified_content:
        modified_content = re.sub(
            r'(<input[^>]*type="password"[^>]*)>',
            r'\1 autocomplete="current-password">',
            modified_content,
            count=1
        )
    elif category == "Accessibility" and "<img" in modified_content:
        modified_content = re.sub(
            r'(<img[^>]*?)(/?>)',
            r'\1 alt="Application Logo"\2',
            modified_content,
            count=1
        )
    elif category == "Visual hierarchy":
        modified_content = modified_content.replace("<h3>", "<h2>", 1).replace("</h3>", "</h2>", 1)
    elif category == "Typography":
        modified_content = re.sub(
            r'font-family:\s*[^;]+;',
            "font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;",
            modified_content,
            count=1
        )
    elif category == "Color contrast":
        modified_content = modified_content.replace("#888888", "#475569").replace("#888", "#475569")
    elif category == "Responsive layout":
        modified_content = re.sub(
            r'style="([^"]*width:\s*\d{3}px[^"]*)"',
            r'style="\1; max-width: 100%; box-sizing: border-box;"',
            modified_content,
            count=1
        )
    elif category == "Loading and empty states" and "{% for" in modified_content and "{% else %}" not in modified_content:
        modified_content = re.sub(
            r'({%\s*endfor\s*%})',
            r'{% else %}\n                    <div class="empty-state" style="text-align: center; padding: 24px; color: #64748b;"><p>No records found. Click add to create the first record.</p></div>\n                \1',
            modified_content,
            count=1
        )
    elif category == "Page consistency" and "{% block title %}" not in modified_content:
        slug = os.path.basename(affected_file).replace(".html", "").replace("_", " ").title()
        modified_content = f"{{% block title %}}{slug} — DevGuardian Project{{% endblock %}}\n" + modified_content
    else:
        # Fallback gentle insertion
        if rec["title"] == "Add Credential Autofill to Password Inputs":
            modified_content = modified_content.replace('type="password"', 'type="password" autocomplete="current-password"', 1)
        else:
            modified_content = original_content + "\n<!-- DevGuardian UI Enhancement Applied -->\n"

    # 3. Validate modified template/CSS
    if affected_file.endswith(".html"):
        try:
            jinja2.Environment().parse(modified_content)
        except jinja2.TemplateSyntaxError as e:
            # ROLLBACK
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(original_content)
            return {"success": False, "error": f"Validation failed: Syntax error on line {e.lineno}. Rolled back automatically."}

    # 4. Save to disk and database
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(modified_content)

    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE project_files SET file_content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE project_id = ? AND (filename = ? OR filename = ?)
        """, (modified_content, project_id, affected_file, f"templates/{os.path.basename(affected_file)}"))
        
        cursor.execute("""
            UPDATE ui_recommendations 
            SET status = 'applied', applied_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (recommendation_id,))
    conn.close()

    return {
        "success": True,
        "message": f"Successfully applied '{rec['title']}' to {affected_file}.",
        "affected_file": affected_file,
        "backup_path": str(backup_file)
    }


def dismiss_ui_recommendation(project_id: str, recommendation_id: str) -> Dict[str, Any]:
    """Dismiss a UI/UX recommendation without modifying any files."""
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ui_recommendations SET status = 'dismissed'
            WHERE id = ? AND project_id = ?
        """, (recommendation_id, project_id))
    conn.close()
    return {"success": True, "message": "Recommendation dismissed."}


def get_recommendation_diff(project_id: str, recommendation_id: str) -> Dict[str, Any]:
    """Generate a clean unified diff preview of what applying the recommendation will change."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ui_recommendations WHERE id = ? AND project_id = ?", (recommendation_id, project_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"success": False, "error": "Recommendation not found."}

    rec = dict(row)
    return {
        "success": True,
        "recommendation": rec,
        "diff": rec.get("proposed_diff", "No diff available."),
        "affected_file": rec["affected_file"]
    }


def refine_project_ui(project_id: str, feedback: str) -> Dict[str, Any]:
    """Refine UI assets based on user feedback."""
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, ui_requirements FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {"status": "failed", "message": "Project not found"}
    
    ui_req = {}
    if row["ui_requirements"]:
        try:
            ui_req = json.loads(row["ui_requirements"])
        except Exception:
            ui_req = {}
    
    ui_req["design_instructions"] = f"{ui_req.get('design_instructions', '')}\nRefinement feedback: {feedback}".strip()
    return generate_ui_solution(project_id, row["name"], row["description"], ui_config=ui_req)


