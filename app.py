import os
import sys
import re
import json
import secrets
import datetime
import functools
import sqlite3
from typing import Optional, Dict, Any
from pathlib import Path
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, g, send_file, abort, jsonify, Response, stream_with_context
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import urllib.parse
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

# Initialize Database and core services
from db import init_db, get_db, close_db, get_standalone_db
import services.project_service as project_service
import services.ai_service as ai_service
import services.code_generator as code_generator
import services.testing_service as testing_service
import services.security_service as security_service
import services.review_service as review_service
import services.deployment_service as deployment_service
import services.report_service as report_service
import services.workflow_service as workflow_service
import services.oauth_service as oauth_service
import services.ide_service as ide_service
import services.execution_service as execution_service
from services.port_manager import PortManager
import services.ui_service as ui_service
import services.requirements_service as requirements_service
import services.validation_service as validation_service
import services.architecture_generator as architecture_generator
import services.documentation_service as documentation_service
import services.documentation_template_service as documentation_template_service
import services.documentation_validation_service as documentation_validation_service
import services.documentation_chat_service as documentation_chat_service
import services.documentation_project_analyzer as documentation_project_analyzer

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "devguardian-production-secret-key-92847120")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_COOKIE_NAME"] = "devguardian_session"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=7)

# Register teardown
app.teardown_appcontext(close_db)

# Ensure database tables exist on startup
with app.app_context():
    init_db()

# =====================================================================
# SECURITY & AUTHENTICATION HELPERS
# =====================================================================

def generate_csrf_token():
    """Generate or retrieve per-session CSRF token."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)
    return session["csrf_token"]

@app.context_processor
def inject_global_template_context():
    """Inject CSRF token, string conversion, and active status helpers to all templates."""
    return {
        "csrf_token": generate_csrf_token(),
        "is_api_configured": ai_service.is_api_key_configured(session.get("gemini_api_key")),
        "current_model": os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"),
        "safe_markdown": report_service.render_safe_markdown,
        "str": str,
    }

def establish_user_session(user_row, auth_provider="local", remember_me=False):
    """
    Establish authenticated session, prevent session fixation,
    and clear temporary authentication states.
    """
    session.permanent = bool(remember_me)
    # Clear temporary OAuth tokens & linking states
    session.pop("oauth_state", None)
    session.pop("oauth_provider", None)
    session.pop("oauth_next", None)
    session.pop("pending_oauth_link", None)
    session.pop("pending_oauth_registration", None)

    session["user_id"] = user_row["id"]
    session["user_name"] = user_row["full_name"]
    session["user_email"] = user_row["email"]
    session["user_role"] = user_row["role"]
    session["auth_provider"] = auth_provider
    if user_row["gemini_api_key"]:
        session["gemini_api_key"] = user_row["gemini_api_key"]

    # Rotate CSRF token on session establishment
    session["csrf_token"] = secrets.token_hex(24)

def _is_api_or_ajax_request() -> bool:
    """Determine whether current request expects a JSON or SSE response."""
    if request.is_json:
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    accept = request.headers.get("Accept", "")
    if "application/json" in accept or "text/event-stream" in accept:
        return True
    path = request.path or ""
    if path.startswith("/api/") or "/run-project" in path or "/launch-status" in path or "/status-json" in path or "/workflow" in path:
        return True
    return False

def login_required(view_func):
    """Decorator ensuring user is authenticated."""
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            if _is_api_or_ajax_request():
                next_target = request.path or "/"
                if "/projects/" in next_target:
                    m = re.search(r"(/projects/[^/]+)", next_target)
                    if m:
                        next_target = f"{m.group(1)}/workspace"
                login_url = url_for("login", next=next_target)
                return jsonify({
                    "success": False,
                    "status": "failed",
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Your session has expired or you are not signed in. Please sign in again.",
                        "login_url": login_url
                    },
                    "login_url": login_url
                }), 401
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped_view

def verify_csrf():
    """Validate CSRF token for unsafe HTTP methods."""
    if app.config.get("TESTING") and not app.config.get("WTF_CSRF_ENABLED", True):
        return None
    if request.method == "POST":
        # If user is not authenticated, let login_required handle 401 with login_url
        if not session.get("user_id") and _is_api_or_ajax_request():
            return None
        token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if not token or token != session.get("csrf_token"):
            if _is_api_or_ajax_request():
                response = jsonify({
                    "success": False,
                    "status": "failed",
                    "error": {
                        "code": "CSRF_VERIFICATION_FAILED",
                        "message": "Security error: Invalid or expired session token. Please try again."
                    }
                })
                response.status_code = 403
                return response
            flash("Security error: Invalid or expired session token. Please try again.", "error")
            abort(403)
    return None

@app.before_request
def csrf_protect():
    if request.method == "POST":
        res = verify_csrf()
        if res is not None:
            return res

def get_current_user_id():
    uid = session.get("user_id")
    if uid is None:
        return None
    try:
        return int(uid)
    except (ValueError, TypeError):
        return uid


# =====================================================================
# PUBLIC & AUTHENTICATION ROUTES
# =====================================================================

@app.route("/")
def landing():
    """Render high-polish minimalist landing page."""
    return render_template("landing.html", hide_sidebar=True, active_page="landing")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register new developer account."""
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            flash("An account with this email address already exists. Please sign in.", "error")
            return render_template("register.html")

        pwd_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (full_name, email, password_hash, role)
            VALUES (?, ?, ?, 'Developer')
        """, (full_name, email, pwd_hash))
        db.commit()
        user_id = cursor.lastrowid

        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        new_user = cursor.fetchone()
        establish_user_session(new_user, auth_provider="local")

        flash(f"Welcome to DevGuardian AI, {full_name}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate user with email and password."""
    next_url = request.args.get("next") or request.form.get("next")
    if session.get("user_id"):
        if next_url and oauth_service.is_safe_redirect_url(next_url):
            return redirect(next_url)
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember_me = bool(request.form.get("remember_me"))

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("login.html", next=next_url)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password_hash"], password):
            establish_user_session(user, auth_provider="local", remember_me=remember_me)
            flash(f"Welcome back, {user['full_name']}!", "success")
            if next_url and oauth_service.is_safe_redirect_url(next_url):
                return redirect(next_url)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password. Please verify your credentials.", "error")

    return render_template("login.html", next=next_url)

@app.route("/logout")
def logout():
    """Terminate user session."""
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("landing"))

# =====================================================================
# SOCIAL & OAUTH AUTHENTICATION ROUTES (Google & GitHub)
# =====================================================================

def resolve_oauth_identity(identity: Dict[str, Any]) -> Any:
    """
    Resolve verified OAuth identity against existing database accounts.
    Handles CASE A (new OAuth user), CASE B (existing OAuth user),
    and CASE C (existing email/password account requiring password confirmation).
    """
    provider = identity["provider"].lower()
    provider_user_id = str(identity["provider_user_id"])
    email = identity.get("email", "").strip().lower()
    full_name = identity.get("full_name", "").strip() or ("Google Developer" if provider == "google" else "GitHub Developer")
    next_url = session.pop("oauth_next", None)
    if not oauth_service.is_safe_redirect_url(next_url):
        next_url = None

    db = get_db()
    cursor = db.cursor()

    try:
        # Check for existing OAuth provider association (CASE B)
        cursor.execute("""
            SELECT * FROM oauth_accounts
            WHERE provider = ? AND provider_user_id = ?
        """, (provider, provider_user_id))
        oauth_account = cursor.fetchone()

        if oauth_account:
            cursor.execute("SELECT * FROM users WHERE id = ?", (oauth_account["user_id"],))
            user = cursor.fetchone()
            if user:
                # Update email in oauth_accounts if changed
                if email and oauth_account["provider_email"] != email:
                    cursor.execute("""
                        UPDATE oauth_accounts SET provider_email = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (email, oauth_account["id"]))
                    db.commit()

                establish_user_session(user, auth_provider=provider)
                provider_title = "Google" if provider == "google" else "GitHub"
                flash(f"Welcome back, {user['full_name']}! Signed in with {provider_title}.", "success")
                return redirect(next_url or url_for("dashboard"))

        # If no provider association exists, check if a user with this email already exists (CASE C)
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            # Prevent automatic linking - require explicit password confirmation
            session["pending_oauth_link"] = {
                "provider": provider,
                "provider_user_id": provider_user_id,
                "provider_email": email,
                "full_name": full_name,
                "target_user_id": existing_user["id"],
                "next_url": next_url,
            }
            provider_title = "Google" if provider == "google" else "GitHub"
            flash(
                f"An account with {email} already exists. Please verify your password to link your {provider_title} account.",
                "info"
            )
            return redirect(url_for("oauth_link_account"))

        # No existing user account - create new user and provider association atomically (CASE A)
        with db:
            random_pwd = secrets.token_urlsafe(32)
            pwd_hash = generate_password_hash(random_pwd)
            cursor.execute("""
                INSERT INTO users (full_name, email, password_hash, role)
                VALUES (?, ?, ?, 'Developer')
            """, (full_name, email, pwd_hash))
            new_user_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO oauth_accounts (user_id, provider, provider_user_id, provider_email)
                VALUES (?, ?, ?, ?)
            """, (new_user_id, provider, provider_user_id, email))

        cursor.execute("SELECT * FROM users WHERE id = ?", (new_user_id,))
        new_user = cursor.fetchone()
        establish_user_session(new_user, auth_provider=provider)

        provider_title = "Google" if provider == "google" else "GitHub"
        flash(f"Welcome to DevGuardian AI, {full_name}! Account created and signed in with {provider_title}.", "success")
        return redirect(next_url or url_for("dashboard"))

    except sqlite3.Error:
        flash("An account creation error occurred due to a database issue. Please try signing in again.", "error")
        return redirect(url_for("login"))


@app.route("/auth/<provider>", methods=["GET", "POST"])
def oauth_start(provider):
    """
    Initiate genuine OAuth 2.0 authorization code flow with Google or GitHub.
    Generates cryptographically random state to protect against CSRF.
    """
    provider = provider.lower()
    if provider not in ["google", "github"]:
        abort(404)

    if not oauth_service.is_provider_configured(provider):
        flash(oauth_service.get_missing_credentials_message(provider), "warning")
        return redirect(url_for("login"))

    # Generate state and store in session
    state = oauth_service.generate_oauth_state()
    session["oauth_state"] = state
    session["oauth_provider"] = provider

    next_param = request.args.get("next") or request.form.get("next")
    if oauth_service.is_safe_redirect_url(next_param):
        session["oauth_next"] = next_param

    if provider == "google":
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI") or url_for("oauth_callback", provider="google", _external=True)
        auth_url = oauth_service.get_google_authorization_url(state, redirect_uri)
    else:
        redirect_uri = os.environ.get("GITHUB_REDIRECT_URI") or url_for("oauth_callback", provider="github", _external=True)
        auth_url = oauth_service.get_github_authorization_url(state, redirect_uri)

    return redirect(auth_url)


@app.route("/auth/callback/<provider>")
@app.route("/auth/<provider>/callback")
def oauth_callback(provider):
    """
    Handle OAuth callback from Google or GitHub.
    Validates state, exchanges authorization code, verifies identity,
    and resolves the authenticated account.
    """
    provider = provider.lower()
    if provider not in ["google", "github"]:
        abort(404)

    provider_title = "Google" if provider == "google" else "GitHub"

    # 1. Handle provider-side errors and cancellation (CASE D & CASE F)
    error = request.args.get("error")
    if error:
        session.pop("oauth_state", None)
        session.pop("oauth_next", None)
        if error in ["access_denied", "user_cancelled_authorize", "user_cancelled_login"]:
            flash(f"{provider_title} authentication was cancelled.", "info")
        else:
            err_desc = request.args.get("error_description", error)
            flash(f"{provider_title} authorization error: {err_desc}", "error")
        return redirect(url_for("login"))

    # 2. Validate state token (CSRF protection)
    received_state = request.args.get("state")
    expected_state = session.pop("oauth_state", None)
    if not expected_state or not received_state or not secrets.compare_digest(expected_state, received_state):
        session.pop("oauth_next", None)
        flash("Security verification failed: invalid or expired OAuth state. Please try again.", "error")
        return redirect(url_for("login"))

    # 3. Verify code presence
    code = request.args.get("code")
    if not code:
        flash(f"No authorization code received from {provider_title}.", "error")
        return redirect(url_for("login"))

    # 4. Exchange code securely & retrieve verified identity
    redirect_uri = os.environ.get(f"{provider.upper()}_REDIRECT_URI") or url_for("oauth_callback", provider=provider, _external=True)

    try:
        if provider == "google":
            tokens = oauth_service.exchange_google_code(code, redirect_uri)
            id_token_str = tokens.get("id_token")
            if not id_token_str:
                raise ValueError("Google did not return an id_token in token exchange.")
            identity = oauth_service.verify_google_identity(id_token_str)
        else:
            access_token = oauth_service.exchange_github_code(code, redirect_uri)
            identity = oauth_service.get_github_identity(access_token)
    except Exception as e:
        flash(f"{provider_title} authentication error: {str(e)}", "error")
        return redirect(url_for("login"))

    # 5. Handle unverified or unavailable email (CASE E)
    if not identity.get("email") or not identity.get("email_verified"):
        session["pending_oauth_registration"] = identity
        flash(f"Your {provider_title} account did not provide a verified email. Please complete registration.", "warning")
        return redirect(url_for("oauth_complete_registration"))

    return resolve_oauth_identity(identity)


@app.route("/auth/link-account", methods=["GET"])
def oauth_link_account():
    """Render account linking confirmation screen."""
    pending = session.get("pending_oauth_link")
    if not pending:
        flash("No pending account linking request found.", "info")
        return redirect(url_for("login"))

    return render_template(
        "oauth_link.html",
        provider=pending["provider"],
        email=pending["provider_email"],
        full_name=pending["full_name"],
        hide_sidebar=True
    )


@app.route("/auth/link-account/confirm", methods=["POST"])
def oauth_link_confirm():
    """Verify password and link OAuth identity to existing account."""
    pending = session.get("pending_oauth_link")
    if not pending:
        flash("Account linking session expired. Please try signing in again.", "error")
        return redirect(url_for("login"))

    password = request.form.get("password", "")
    target_user_id = pending.get("target_user_id")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (target_user_id,))
    user = cursor.fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        flash("Incorrect password. Please verify your password to link your account.", "error")
        return render_template(
            "oauth_link.html",
            provider=pending["provider"],
            email=pending["provider_email"],
            full_name=pending["full_name"],
            hide_sidebar=True
        )

    try:
        with db:
            cursor.execute("""
                INSERT INTO oauth_accounts (user_id, provider, provider_user_id, provider_email)
                VALUES (?, ?, ?, ?)
            """, (user["id"], pending["provider"], pending["provider_user_id"], pending["provider_email"]))
    except sqlite3.IntegrityError:
        pass  # Already linked

    next_url = pending.get("next_url")
    establish_user_session(user, auth_provider=pending["provider"])
    provider_title = "Google" if pending["provider"] == "google" else "GitHub"
    flash(f"Successfully linked your {provider_title} account! Welcome back, {user['full_name']}.", "success")
    return redirect(next_url or url_for("dashboard"))


@app.route("/auth/link-account/cancel", methods=["POST"])
def oauth_link_cancel():
    """Cancel pending account linking flow."""
    session.pop("pending_oauth_link", None)
    session.pop("pending_oauth_registration", None)
    flash("Account linking was cancelled.", "info")
    return redirect(url_for("login"))


@app.route("/auth/complete-registration", methods=["GET", "POST"])
def oauth_complete_registration():
    """Complete registration if provider did not return verified email."""
    pending = session.get("pending_oauth_registration")
    if not pending:
        flash("No pending registration found.", "info")
        return redirect(url_for("login"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        full_name = request.form.get("full_name", "").strip() or pending.get("full_name", "Developer")

        if not email or "@" not in email:
            flash("Please enter a valid email address.", "error")
            return render_template("oauth_complete.html", provider=pending["provider"], full_name=full_name, hide_sidebar=True)

        pending["email"] = email
        pending["email_verified"] = True
        pending["full_name"] = full_name
        session.pop("pending_oauth_registration", None)
        return resolve_oauth_identity(pending)

    return render_template(
        "oauth_complete.html",
        provider=pending["provider"],
        full_name=pending.get("full_name", ""),
        hide_sidebar=True
    )

# =====================================================================
# DASHBOARD & PROJECT MANAGEMENT ROUTES
# =====================================================================

@app.route("/dashboard")
@login_required
def dashboard():
    """Render main dashboard with live stats and recent projects."""
    user_id = get_current_user_id()
    stats = project_service.get_dashboard_stats(user_id)
    projects = project_service.get_user_projects(user_id)
    return render_template("dashboard.html", active_page="dashboard", stats=stats, projects=projects)

@app.route("/projects")
@login_required
def projects_list():
    """List all projects owned by user with workspace, port, entry point, and process status."""
    user_id = get_current_user_id()
    projects = project_service.get_user_projects(user_id)
    for p in projects:
        proc = execution_service.get_project_process_status(p["id"])
        p["is_running"] = proc.get("is_running", False)
        p["process_status"] = proc.get("status", "Not Started")
        p["health_status"] = proc.get("health_status", "Not Running")
        p["process_url"] = proc.get("local_url")
        p["process_port"] = proc.get("port") or p.get("assigned_port")
        p["pid"] = proc.get("pid")
        p["entry_point"] = p.get("entry_point") or proc.get("entry_point") or "app.py"
        p["run_cmd"] = f"python {p['entry_point']}"
        p["started_at"] = proc.get("started_at")
        p["last_run"] = proc.get("started_at") or "Never"
        p["detail"] = proc.get("detail", "")
        last_logs = proc.get("logs", "")
        p["last_error"] = proc.get("last_error") or (last_logs if (p["process_status"] in ["Failed", "Health Check Failed", "Port Conflict", "Dependencies Missing", "Entry Point Missing"] or "error" in last_logs.lower()) else None)

    servers_overview = PortManager.get_system_servers_overview(user_id=user_id)
    port_conflicts = PortManager.detect_port_conflicts(user_id=user_id)
    return render_template(
        "projects.html",
        active_page="projects",
        projects=projects,
        servers_overview=servers_overview,
        port_conflicts=port_conflicts
    )

@app.route("/projects/new", methods=["GET", "POST"])
@login_required
def new_project():
    """Render project creation wizard with IDE detection cards."""
    ide_cards = ide_service.list_supported_ides()
    return render_template("new_project.html", active_page="new_project", ide_cards=ide_cards)

@app.route("/projects/create", methods=["POST"])
@login_required
def create_new_project():
    """Process project creation submission and transition to workspace."""
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    app_type = request.form.get("app_type", "Web App").strip()
    language = request.form.get("language", "Python Flask").strip()
    tech_preferences = request.form.get("tech_preferences", "").strip()

    if not name or not description:
        flash("Project name and description are required.", "error")
        return redirect(url_for("new_project"))

    # IDE Selection (Features 2 & 3)
    selected_ide = (request.form.get("selected_ide") or "vscode").strip().lower()
    ide_custom_path = request.form.get(f"custom_path_{selected_ide}") or request.form.get("ide_custom_path")

    # UI / UX Design Requirements (Three Generation Options: Option A: Generate UI, Option B: Backend Only, Option C: Both - Full-Stack Application)
    ui_gen_mode = (request.form.get("generation_mode") or request.form.get("ui_generation") or "both").strip().lower()
    if ui_gen_mode not in ("both", "generate_ui", "backend_only"):
        ui_gen_mode = "both"
    design_style = request.form.get("design_style", "Modern SaaS")
    color_palette = request.form.get("color_palette", "White and Grey")
    layout_preference = request.form.get("layout_preference", "Responsive Web Application")
    design_instructions = request.form.get("design_instructions", "").strip()
    required_pages = request.form.getlist("required_pages")
    custom_pages = request.form.get("custom_pages", "").strip()

    ui_requirements = {
        "generation_mode": ui_gen_mode,
        "generate_ui": (ui_gen_mode in ("generate_ui", "both")),
        "backend_only": (ui_gen_mode == "backend_only"),
        "full_stack": (ui_gen_mode == "both"),
        "design_style": design_style,
        "color_palette": color_palette,
        "layout_preference": layout_preference,
        "design_instructions": design_instructions,
        "required_pages": required_pages if required_pages else ["Landing Page", "Sign In", "Sign Up", "Dashboard", "Project Pages", "Reports", "Settings"],
        "custom_pages": custom_pages
    }

    user_id = get_current_user_id()
    try:
        project_id = project_service.create_project(
            user_id=user_id,
            name=name,
            description=description,
            app_type=app_type,
            language=language,
            tech_preferences=tech_preferences,
            selected_ide=selected_ide,
            ide_custom_path=ide_custom_path,
            ui_requirements=ui_requirements,
            generation_mode=ui_gen_mode
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("new_project"))

    # Save optional reference image upload
    ref_image = request.files.get("ui_reference_image")
    if ref_image and ref_image.filename:
        try:
            pdir = code_generator.get_project_dir(project_id)
            ref_path = pdir / f"design_reference_{secrets.token_hex(4)}.png"
            ref_image.save(ref_path)
        except Exception:
            pass

    flash(f"Project '{name}' initialized. Your autonomous engineering team is standing by.", "success")
    return redirect(url_for("project_workspace", project_id=project_id))

@app.route("/projects/<project_id>")
@login_required
def project_overview(project_id):
    """Render project hub view."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    return render_template("project_detail.html", active_page="projects", project=project)

@app.route("/projects/<project_id>/workspace")
@login_required
def project_workspace(project_id):
    """Render interactive multi-agent workspace and progress tracker."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    executions = project_service.get_project_agent_executions(project_id)
    
    # Calculate progress % based on completed stages
    completed_stages = sum(1 for e in executions if e["status"] == "completed")
    progress_pct = int((completed_stages / 8) * 100) if executions else 0

    # Determine current agent
    current_agent = None
    for e in executions:
        if e["status"] in ["running", "pending", "failed"]:
            current_agent = e
            break
    if not current_agent and executions:
        current_agent = executions[-1]

    # IDE and Execution details
    ide_cfg = ide_service.get_project_ide_config(project_id)
    all_ides = ide_service.list_supported_ides(
        selected_ide=ide_cfg["selected_ide"],
        custom_path_map={ide_cfg["selected_ide"]: ide_cfg["ide_custom_path"]}
    )
    selected_adapter = ide_service.get_ide_adapter(ide_cfg["selected_ide"])
    ide_info = selected_adapter.detect(custom_path=ide_cfg.get("ide_custom_path"))
    ide_info["name"] = selected_adapter.name

    process_status = execution_service.get_project_process_status(project_id)
    try:
        project_dir = str(code_generator.get_project_dir(project_id).resolve())
    except Exception:
        project_dir = ""

    from services.agent_metrics_service import AgentMetricsService
    agent_reports = AgentMetricsService.get_agent_reports_for_project(project_id)
    timeline_events = AgentMetricsService.get_timeline_events(project_id)

    return render_template(
        "project_progress.html",
        active_page="projects",
        project=project,
        executions=executions,
        current_agent=current_agent,
        progress_pct=progress_pct,
        ide_info=ide_info,
        all_ides=all_ides,
        process_status=process_status,
        project_dir=project_dir,
        agent_reports=agent_reports,
        timeline_events=timeline_events
    )

# =====================================================================
# IDE MANAGEMENT ROUTES (FEATURES 2, 3, 4)
# =====================================================================

@app.route("/projects/<project_id>/ide/select", methods=["POST"])
@login_required
def select_project_ide_action(project_id):
    """Update selected development environment for project."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    selected_ide = request.form.get("selected_ide", "vscode")
    try:
        ide_service.save_project_ide_preference(project_id, selected_ide)
        adapter = ide_service.get_ide_adapter(selected_ide)
        flash(f"Development environment updated to {adapter.name}.", "success")
    except Exception as e:
        flash(f"Error saving IDE preference: {str(e)}", "error")

    return redirect(url_for("project_workspace", project_id=project_id))

@app.route("/projects/<project_id>/ide/configure", methods=["POST"])
@login_required
def configure_ide_path_action(project_id):
    """Configure custom executable path when automatic detection fails."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    custom_path = request.form.get("ide_custom_path", "").strip()
    selected_ide = project.get("selected_ide") or "vscode"
    try:
        ide_service.save_project_ide_preference(project_id, selected_ide, custom_path=custom_path)
        flash("Custom executable path verified and updated.", "success")
    except Exception as e:
        flash(f"Failed to configure custom path: {str(e)}", "error")

    return redirect(url_for("project_workspace", project_id=project_id))

@app.route("/projects/<project_id>/ide/launch", methods=["POST"])
@login_required
def launch_ide_action(project_id):
    """Launch verified project workspace in selected development environment."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    ide_key = request.form.get("ide_key") or project.get("selected_ide") or "vscode"
    res = ide_service.launch_project_in_ide(project_id, ide_key=ide_key)

    if res["success"]:
        flash(f"Project opened in {res.get('ide_name', 'IDE')} at {res['project_dir']}.", "success")
    else:
        flash(f"Could not open in IDE: {res['message']} Absolute Path: {res['project_dir']}", "error")

    return redirect(url_for("project_workspace", project_id=project_id))

# =====================================================================
# PROJECT EXECUTION & PROCESS CONTROL ROUTES (FEATURE 5)
# =====================================================================

@app.route("/projects/<project_id>/run-project", methods=["GET", "POST"])
@login_required
def run_project_app_action(project_id):
    """Launch generated application in isolated background subprocess or return its status."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        existing_proj = project_service.get_project_by_id(project_id)
        if existing_proj and existing_proj.get("user_id") != user_id:
            if _is_api_or_ajax_request():
                return jsonify({
                    "success": False,
                    "status": "failed",
                    "project_id": project_id,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You are not authorized to run or access this project."
                    }
                }), 403
            abort(403)

        if _is_api_or_ajax_request():
            return jsonify({
                "success": False,
                "status": "failed",
                "project_id": project_id,
                "error": {
                    "code": "PROJECT_NOT_FOUND",
                    "message": "Project not found."
                }
            }), 404
        abort(404)

    if request.method == "GET":
        status = execution_service.get_project_process_status(project_id)
        status["project_name"] = project["name"]
        status["project_id"] = project["id"]
        status["ready"] = bool(status.get("is_running") and status.get("health_status") == "Healthy")
        status["state"] = status.get("status")
        if _is_api_or_ajax_request():
            return jsonify(status)
        return redirect(url_for("project_workspace", project_id=project_id))

    res = execution_service.start_project_app(project_id)
    is_success = bool(res.get("success"))

    status_to_code = {
        "Dependencies Missing": "DEPENDENCIES_MISSING",
        "Entry Point Missing": "ENTRY_POINT_MISSING",
        "Port Conflict": "PORT_CONFLICT",
        "Health Check Failed": "HEALTH_CHECK_FAILED",
        "Not Verified": "HEALTH_CHECK_TIMEOUT",
    }
    err_code = status_to_code.get(res.get("status"), "PROJECT_STARTUP_FAILED")
    err_msg = res.get("message") or res.get("last_error") or ("Application startup completed" if is_success else "The application could not be started")

    response_payload = {
        "success": is_success,
        "status": "running" if is_success else "failed",
        "project_id": project_id,
        "project_name": project["name"],
        "message": res.get("message", "Application started successfully" if is_success else err_msg),
        "local_url": res.get("local_url"),
        "port": res.get("port"),
        "pid": res.get("pid"),
        "stage": res.get("stage", "ready" if is_success else "failed"),
        "logs": res.get("logs", "")
    }
    if not is_success:
        response_payload["error"] = {
            "code": err_code,
            "message": err_msg
        }

    # Return JSON immediately if requested via AJAX, Fetch, or Accept header
    if _is_api_or_ajax_request():
        http_code = 200 if is_success else (400 if err_code in ["ENTRY_POINT_MISSING", "DEPENDENCIES_MISSING"] else 500)
        return jsonify(response_payload), http_code

    if is_success:
        flash(f"Application started successfully! Verified reachable at {res['local_url']} (PID {res.get('pid')})", "success")
    elif res.get("status") == "Dependencies Missing":
        flash(f"Dependencies Missing: {res['message']}", "error")
    elif res.get("status") == "Entry Point Missing":
        flash(f"Entry Point Missing: {res['message']}", "error")
    elif res.get("status") == "Port Conflict":
        flash(f"Port Conflict: {res['message']}", "error")
    elif res.get("status") in ["Not Verified", "Health Check Failed"]:
        flash(f"Subprocess started (PID {res.get('pid')}) on port {res.get('port')}, but HTTP health check was not confirmed within 8s.", "warning")
    else:
        flash(f"Application startup failed: {res.get('message', res.get('last_error', 'Unknown error'))}", "error")

    ref = request.referrer or ""
    if "/projects" in ref and "/workspace" not in ref:
        return redirect(url_for("projects_list"))
    return redirect(url_for("project_workspace", project_id=project_id))

@app.route("/projects/<project_id>/run-project-stream")
@login_required
def run_project_stream_action(project_id):
    """Stream authentic project startup progress via Server-Sent Events."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        existing_proj = project_service.get_project_by_id(project_id)
        if existing_proj and existing_proj.get("user_id") != user_id:
            return jsonify({
                "success": False,
                "status": "failed",
                "message": "You are not authorized to access this project.",
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You are not authorized to access this project."
                },
                "stage": "failed"
            }), 403

        return jsonify({
            "success": False,
            "status": "failed",
            "message": "Project not found.",
            "error": {
                "code": "PROJECT_NOT_FOUND",
                "message": "Project not found."
            },
            "stage": "failed"
        }), 404

    def event_generator():
        try:
            for event in execution_service.start_project_app_with_progress(project_id):
                if "project_name" not in event:
                    event["project_name"] = project["name"]
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.exception(f"Unexpected error in run_project_stream for {project_id}: {e}")
            err_payload = {
                "step": 5,
                "percent": 90,
                "stage": "failed",
                "success": False,
                "status": "failed",
                "message": f"Startup encountered an unexpected error: {str(e)}",
                "error": {
                    "code": "PROJECT_STARTUP_EXCEPTION",
                    "message": str(e)
                },
                "project_id": project_id,
                "project_name": project.get("name", "Project")
            }
            yield f"data: {json.dumps(err_payload)}\n\n"

    return Response(
        stream_with_context(event_generator()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

@app.route("/projects/<project_id>/status-json")
@app.route("/projects/<project_id>/launch-status")
@login_required
def project_status_json_action(project_id):
    """Return current process runtime status as JSON."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        existing_proj = project_service.get_project_by_id(project_id)
        if existing_proj and existing_proj.get("user_id") != user_id:
            return jsonify({
                "is_running": False,
                "ready": False,
                "status": "Forbidden",
                "state": "Forbidden",
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You are not authorized to access this project."
                }
            }), 403

        return jsonify({
            "is_running": False,
            "ready": False,
            "status": "Not Found",
            "state": "Not Found",
            "error": {
                "code": "PROJECT_NOT_FOUND",
                "message": "Project not found."
            }
        }), 404

    status = execution_service.get_project_process_status(project_id)
    status["project_name"] = project["name"]
    status["project_id"] = project["id"]
    status["ready"] = bool(status.get("is_running") and status.get("health_status") == "Healthy")
    status["state"] = status.get("status")
    return jsonify(status)

@app.route("/projects/<project_id>/stop-project", methods=["POST"])
@login_required
def stop_project_action(project_id):
    """Stop active application subprocess."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    res = execution_service.stop_project_process(project_id)
    flash(res["message"], "info")
    ref = request.referrer or ""
    if "/projects" in ref and "/workspace" not in ref:
        return redirect(url_for("projects_list"))
    return redirect(url_for("project_workspace", project_id=project_id))

@app.route("/projects/<project_id>/restart-project", methods=["POST"])
@login_required
def restart_project_action(project_id):
    """Restart active application subprocess cleanly."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    res = execution_service.restart_project_app(project_id)
    if res["success"]:
        flash(f"Application restarted successfully! Verified reachable at {res['local_url']} (PID {res.get('pid')})", "success")
    elif res.get("status") == "Dependencies Missing":
        flash(f"Restart failed: Dependencies missing - {res['message']}", "error")
    elif res.get("status") == "Entry Point Missing":
        flash(f"Restart failed: Entry-point missing - {res['message']}", "error")
    elif res.get("status") in ["Not Verified", "Health Check Failed"]:
        flash(f"Subprocess restarted (PID {res.get('pid')}) on port {res.get('port')}, but HTTP health check was not confirmed.", "warning")
    else:
        flash(f"Application restart failed: {res.get('message', res.get('last_error', 'Unknown error'))}", "error")

    ref = request.referrer or ""
    if "/projects" in ref and "/workspace" not in ref:
        return redirect(url_for("projects_list"))
    return redirect(url_for("project_workspace", project_id=project_id))

@app.route("/projects/<project_id>/open-folder", methods=["GET", "POST"])
@login_required
def open_project_folder_action(project_id):
    """
    Open project workspace folder in native system file explorer.
    Validates that the path is within the approved workspace before opening.
    Does not allow arbitrary browser-supplied filesystem traversal.
    """
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        if _is_api_or_ajax_request():
            return jsonify({"success": False, "error": "Project not found"}), 404
        abort(404)

    ws_path = project.get("workspace_path")
    ws = Path(ws_path).resolve() if ws_path else None
    
    # Path validation: Ensure path is within the project repository workspace
    workspace_root = Path(__file__).resolve().parent
    generated_dir = workspace_root / "generated_projects"
    is_safe = ws and (generated_dir in ws.parents or ws == generated_dir or workspace_root in ws.parents or ws == workspace_root)

    success = False
    msg = ""
    if ws and ws.exists() and is_safe:
        try:
            if os.name == "nt":
                os.startfile(str(ws))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(ws)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(ws)])
            success = True
            msg = f"Opened project folder: {ws.name}"
            flash(msg, "info")
        except Exception as e:
            msg = f"Could not open folder in file explorer: {str(e)}"
            flash(msg, "warning")
    else:
        msg = "Project workspace directory does not exist on disk or path is invalid."
        flash(msg, "error")

    if _is_api_or_ajax_request():
        return jsonify({"success": success, "message": msg, "path": str(ws) if ws else None})

    ref = request.referrer or ""
    if "/projects" in ref and "/workspace" not in ref:
        return redirect(url_for("projects_list"))
    return redirect(url_for("project_workspace", project_id=project_id))

@app.route("/projects/<project_id>/logs")
@login_required
def project_logs_view(project_id):
    """View process execution logs for a project."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    logs_data = execution_service.get_project_logs(project_id)
    proc_info = execution_service.get_project_process_status(project_id)

    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({
            "project_id": project_id,
            "project_name": project["name"],
            "logs": logs_data.get("logs", ""),
            "status": proc_info.get("status"),
            "health_status": proc_info.get("health_status"),
            "pid": proc_info.get("pid"),
            "port": proc_info.get("port"),
            "entry_point": proc_info.get("entry_point")
        })

    return render_template(
        "project_logs.html",
        active_page="projects",
        project=project,
        logs_data=logs_data,
        proc_info=proc_info
    )

@app.route("/api/port-status")
@login_required
def api_port_status():
    """Live JSON API for Port Status Monitoring."""
    user_id = get_current_user_id()
    overview = PortManager.get_system_servers_overview(user_id=user_id)
    return jsonify(overview)

@app.route("/api/port-conflicts")
@login_required
def api_port_conflicts():
    """Live JSON API returning categorized port conflict diagnostics."""
    user_id = get_current_user_id()
    conflicts_data = PortManager.detect_port_conflicts(user_id=user_id)
    return jsonify(conflicts_data)

@app.route("/api/port-conflicts/resolve", methods=["POST"])
@login_required
def api_resolve_port_conflicts():
    """Trigger safe automated port conflict resolution without terminating external processes."""
    user_id = get_current_user_id()
    result = PortManager.resolve_port_conflicts(user_id=user_id)
    return jsonify(result)

@app.route("/projects/<project_id>/run-project-tests", methods=["POST"])
@login_required
def run_project_tests_action(project_id):
    """Execute unit test suite in isolated subprocess."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    res = execution_service.run_project_tests_service(project_id)
    if res["success"]:
        flash(f"Unit tests executed: {res['passed_tests']}/{res['total_tests']} tests passed.", "success")
    else:
        flash(f"Unit tests failed: {res.get('failed_tests', 1)} failed.", "error")

    return redirect(url_for("project_testing_results", project_id=project_id))

# =====================================================================
# =====================================================================
# UI / UX PREVIEW & VALIDATION ROUTES (FEATURES 6, 7, 8)
# =====================================================================

@app.route("/projects/<project_id>/ui-preview")
@login_required
def project_ui_preview(project_id):
    """Render interactive UI preview, page catalog, and 15-category recommendations."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    pages = ui_service.get_available_preview_pages(project_id)
    if not pages:
        pages = [{"name": "Landing", "slug": "landing", "filename": "templates/landing.html", "category": "Other pages", "is_valid": True, "dependencies": []}]

    requested_page = request.args.get("page", pages[0]["filename"] if pages else "templates/landing.html")
    auth_mode = request.args.get("auth", "auto")
    active_tab = request.args.get("tab", "preview")
    
    validation = ui_service.validate_project_ui(project_id)
    recommendations = ui_service.get_project_ui_recommendations(project_id)

    ui_req_raw = project.get("ui_requirements") or "{}"
    try:
        ui_config = json.loads(ui_req_raw) if isinstance(ui_req_raw, str) else ui_req_raw
    except Exception:
        ui_config = {}

    ide_cfg = ide_service.get_project_ide_config(project_id)
    ide_adapter = ide_service.get_ide_adapter(ide_cfg["selected_ide"])

    runtime_status = execution_service.get_project_process_status(project_id)
    assigned_port = project.get("assigned_port") or runtime_status.get("port") or 5050
    live_url = f"http://127.0.0.1:{assigned_port}"

    from services.ui_reference_service import UIReferenceService
    references = UIReferenceService.get_project_references(project_id)
    page_clean = requested_page.replace("templates/", "").replace(".html", "")
    ref_comp = UIReferenceService.compare_preview_with_reference(project_id, page_clean, "")

    return render_template(
        "ui_preview.html",
        active_page="projects",
        project=project,
        pages=pages,
        current_page=requested_page,
        current_auth_mode=auth_mode,
        active_tab=active_tab,
        validation=validation,
        recommendations=recommendations,
        ui_config=ui_config,
        ide_name=ide_adapter.name,
        runtime_status=runtime_status,
        assigned_port=assigned_port,
        live_url=live_url,
        references=references,
        ref_comp=ref_comp
    )

@app.route("/projects/<project_id>/ui-preview/render")
@login_required
def render_raw_preview_page(project_id):
    """Serve isolated rendered HTML content for preview iframe."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    page_name = request.args.get("page", "templates/landing.html")
    auth_mode = request.args.get("auth", "auto")
    
    current_user_info = {
        "name": session.get("user_name", "Developer"),
        "email": session.get("user_email", "developer@devguardian.ai")
    }
    
    success, html_output = ui_service.render_preview_page(
        project_id, page_name, auth_mode=auth_mode, current_user_info=current_user_info
    )
    return html_output, (200 if success else 404), {"Content-Type": "text/html; charset=utf-8"}

@app.route("/projects/<project_id>/preview/asset/<path:asset_path>")
def serve_project_preview_asset(project_id, asset_path):
    """Safely serve static asset (CSS, JS, images, fonts) from project workspace for UI preview."""
    user_id = get_current_user_id()
    token = request.args.get("token")
    expected_token = ui_service.get_preview_asset_token(project_id)

    # Verify authorization: active session user, valid preview token, or verified project
    if user_id:
        project = project_service.get_project_by_id(project_id, user_id=user_id)
    elif token and token == expected_token:
        project = project_service.get_project_by_id(project_id, user_id=None)
    else:
        project = project_service.get_project_by_id(project_id, user_id=None)

    if not project:
        abort(404)
        
    clean_path = os.path.normpath(asset_path).lstrip(r"\/")
    if ".." in clean_path.split(os.sep):
        abort(403)
        
    try:
        from services.workspace_manager import get_project_workspace
        ws = get_project_workspace(project_id)
    except Exception:
        abort(404)
        
    static_dir = ws / "static"
    target_file = (static_dir / clean_path).resolve()
    
    try:
        target_file.relative_to(ws.resolve())
    except ValueError:
        abort(403)
        
    if target_file.suffix.lower() in [".py", ".pyc", ".db", ".sqlite", ".env", ".key", ".pem", ".log"] or target_file.name.startswith("."):
        abort(403)
        
    import mimetypes
    mime, _ = mimetypes.guess_type(str(target_file))
    if target_file.suffix.lower() == ".css":
        mime = "text/css"
    elif target_file.suffix.lower() == ".js":
        mime = "application/javascript"
    elif target_file.suffix.lower() == ".svg":
        mime = "image/svg+xml"
    elif not mime:
        mime = "application/octet-stream"

    content = None
    if target_file.is_file():
        try:
            with open(target_file, "rb") as f:
                content = f.read()
        except Exception:
            pass

    if content is None:
        # Fallback to project_files in DB
        db_files = code_generator.get_project_files_from_db(project_id)
        for f in db_files:
            fn_norm = f["filename"].replace("\\", "/").lstrip("/")
            if fn_norm in [f"static/{clean_path}", clean_path]:
                raw_c = f["file_content"]
                content = raw_c.encode("utf-8") if isinstance(raw_c, str) else raw_c
                break

    if content is None:
        abort(404)

    res = Response(content, mimetype=mime)
    res.headers["Access-Control-Allow-Origin"] = "*"
    res.headers["X-Content-Type-Options"] = "nosniff"
    res.headers["Cache-Control"] = "no-cache"
    return res

@app.route("/projects/<project_id>/ui-preview/recommendations/analyze", methods=["POST"])
@login_required
def run_ui_recommendations_analysis(project_id):
    """Re-run 15-category UI/UX static and heuristic audit."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    res = ui_service.analyze_project_ui_ux(project_id)
    flash(f"UI/UX audit completed: {res['total_recommendations']} actionable recommendations found ({res['high_priority']} High priority).", "success")
    return redirect(url_for("project_ui_preview", project_id=project_id, tab="recommendations"))

@app.route("/projects/<project_id>/ui-preview/recommendations/<rec_id>/apply", methods=["POST"])
@login_required
def apply_ui_recommendation_action(project_id, rec_id):
    """Apply a verified UI/UX recommendation with automatic backup and rollback."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    res = ui_service.apply_ui_recommendation(project_id, rec_id)
    if res["success"]:
        flash(res["message"], "success")
    else:
        flash(f"Could not apply recommendation: {res.get('error')}", "error")
    return redirect(url_for("project_ui_preview", project_id=project_id, tab="recommendations"))

@app.route("/projects/<project_id>/ui-preview/recommendations/<rec_id>/dismiss", methods=["POST"])
@login_required
def dismiss_ui_recommendation_action(project_id, rec_id):
    """Dismiss a UI/UX recommendation."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    ui_service.dismiss_ui_recommendation(project_id, rec_id)
    flash("Recommendation dismissed.", "info")
    return redirect(url_for("project_ui_preview", project_id=project_id, tab="recommendations"))

@app.route("/projects/<project_id>/ui-preview/recommendations/<rec_id>/diff")
@login_required
def get_recommendation_diff_action(project_id, rec_id):
    """Return proposed diff for modal review."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    return jsonify(ui_service.get_recommendation_diff(project_id, rec_id))

@app.route("/projects/<project_id>/ui-preview/refine", methods=["POST"])
@login_required
def request_ui_improvement_action(project_id):
    """Process user design refinement feedback and regenerate templates."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    notes = request.form.get("improvement_notes", "").strip()
    if notes:
        ui_req_raw = project.get("ui_requirements") or "{}"
        try:
            ui_config = json.loads(ui_req_raw) if isinstance(ui_req_raw, str) else ui_req_raw
        except Exception:
            ui_config = {}
        ui_config["design_instructions"] = f"{ui_config.get('design_instructions', '')}; Refinement: {notes}".strip("; ")
        ui_service.generate_ui_solution(project_id, project["name"], project["description"], ui_config=ui_config)
        flash("UI design refinements synthesized and applied to templates.", "success")

    return redirect(url_for("project_ui_preview", project_id=project_id))

# =====================================================================
# REQUIREMENTS TRACEABILITY & VERIFICATION (FEATURE 9)
# =====================================================================

@app.route("/projects/<project_id>/requirements")
@login_required
def project_requirements_page(project_id):
    """Render Requirements Traceability Matrix backed by execution evidence."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    requirements = requirements_service.sync_project_requirements(project_id)
    total = len(requirements)
    verified = sum(1 for r in requirements if r["status"] == "Verified")
    failed = sum(1 for r in requirements if r["status"] == "Failed")
    rate = int((verified / total) * 100) if total > 0 else 0

    return render_template(
        "requirements_traceability.html",
        active_page="projects",
        project=project,
        requirements=requirements,
        verified_count=verified,
        failed_count=failed,
        compliance_rate=rate
    )

# =====================================================================
# END-TO-END VALIDATION & AUTO-FIX (FEATURES 10 & 11)
# =====================================================================

@app.route("/projects/<project_id>/validate", methods=["GET", "POST"])
@login_required
def run_project_validation_action(project_id):
    """Run full 8-phase end-to-end validation with auto-fix loop."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    orchestrator = validation_service.ValidationOrchestrator(project_id)
    auto_fix_limit = session.get("auto_fix_limit", 3)
    val_results = orchestrator.run_all_phases(auto_fix=True, max_retries=auto_fix_limit)

    status = val_results.get("overall_status", "Passed")
    corrections = val_results.get("corrections", [])
    if status == "Verified":
        flash("End-to-End 8-phase software validation passed! All requirements verified.", "success")
    elif corrections:
        flash(f"Validation completed. Applied {len(corrections)} auto-fix corrections.", "info")
    else:
        flash(f"Validation concluded with status: {status}.", "warning" if status == "Partially Verified" else "error")

    return redirect(url_for("project_requirements_page", project_id=project_id))

@app.route("/projects/<project_id>/delete", methods=["POST"])
@login_required
def delete_project_action(project_id):
    """Delete a project with cascading SQLite cleanup."""
    user_id = get_current_user_id()
    execution_service.stop_project_process(project_id)
    deleted = project_service.delete_project(project_id, user_id=user_id)
    if deleted:
        flash("Project successfully deleted.", "info")
    else:
        flash("Project not found or unauthorized.", "error")
    return redirect(url_for("projects_list"))

# =====================================================================
# AGENT WORKFLOW EXECUTION ROUTES
# =====================================================================

@app.route("/projects/<project_id>/run", methods=["GET", "POST"])
@app.route("/projects/<project_id>/run-all-agents", methods=["POST"])
@login_required
def run_full_workflow_action(project_id):
    """Execute complete 8-agent autonomous workflow in background or synchronous fallback."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        existing_proj = project_service.get_project_by_id(project_id)
        if existing_proj and existing_proj.get("user_id") != user_id:
            if _is_api_or_ajax_request():
                return jsonify({
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You are not authorized to access this project."
                    }
                }), 403
            abort(403)
        if _is_api_or_ajax_request():
            return jsonify({"success": False, "message": "Project not found"}), 404
        abort(404)

    user_api_key = session.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    from services.workflow_tracker import start_workflow_in_background, get_workflow_status_payload

    # Check if AJAX / JSON request
    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")

    if is_ajax:
        started, msg = start_workflow_in_background(project_id, api_key=user_api_key, reset_stages=True)
        payload = get_workflow_status_payload(project_id)
        payload["message"] = msg
        return jsonify(payload)

    # Traditional form POST / synchronous fallback
    try:
        started, msg = start_workflow_in_background(project_id, api_key=user_api_key, reset_stages=True)
        flash(f"Autonomous agent team launched for '{project['name']}'!", "info")
    except Exception as e:
        flash(f"Agent execution encountered an error: {str(e)}", "error")

    return redirect(url_for("project_workspace", project_id=project_id))


@app.route("/projects/<project_id>/workflow-stream")
@login_required
def project_workflow_stream_action(project_id):
    """Stream authentic agent workflow progress via Server-Sent Events (SSE)."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        existing_proj = project_service.get_project_by_id(project_id)
        if existing_proj and existing_proj.get("user_id") != user_id:
            return jsonify({
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You are not authorized to access this project."
                }
            }), 403
        return jsonify({"success": False, "message": "Project not found"}), 404

    from services.workflow_tracker import stream_workflow_progress

    return Response(
        stream_with_context(stream_workflow_progress(project_id)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@app.route("/api/projects/<project_id>/workflow-status")
@login_required
def api_get_workflow_status(project_id):
    """Return authentic live status and agent reports for the workflow."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        existing_proj = project_service.get_project_by_id(project_id)
        if existing_proj and existing_proj.get("user_id") != user_id:
            return jsonify({
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You are not authorized to access this project."
                }
            }), 403
        return jsonify({"success": False, "message": "Project not found"}), 404

    from services.workflow_tracker import get_workflow_status_payload
    payload = get_workflow_status_payload(project_id)
    return jsonify(payload)


@app.route("/projects/<project_id>/workflow-retry", methods=["POST"])
@login_required
def project_workflow_retry_action(project_id):
    """Retry failed or blocked agent stages safely without duplicating completed work."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
            return jsonify({"success": False, "message": "Project not found"}), 404
        abort(404)

    user_api_key = session.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    from services.workflow_tracker import retry_failed_agents_in_background, get_workflow_status_payload
    started, msg = retry_failed_agents_in_background(project_id, api_key=user_api_key)

    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")
    if is_ajax:
        payload = get_workflow_status_payload(project_id)
        payload["message"] = msg
        return jsonify(payload)

    flash(msg, "info" if started else "warning")
    return redirect(url_for("project_workspace", project_id=project_id))

@app.route("/projects/<project_id>/run-next", methods=["GET", "POST"])
@login_required
def run_next_agent_action(project_id):
    """Execute the next pending agent in stage order."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    executions = project_service.get_project_agent_executions(project_id)
    next_stage = None
    for e in executions:
        if e["status"] in ["pending", "running", "failed"]:
            next_stage = e["agent_key"]
            break

    if not next_stage:
        flash("All agents have already completed execution.", "info")
        return redirect(url_for("project_workspace", project_id=project_id))

    user_api_key = session.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    try:
        updated_state = workflow_service.execute_single_stage(project_id, next_stage, api_key=user_api_key)
        if updated_state.get("error_info"):
            flash(f"Agent {next_stage} failed: {updated_state['error_info']}", "error")
        else:
            flash(f"{next_stage.capitalize()} Agent executed successfully.", "success")
    except Exception as e:
        flash(f"Execution error on {next_stage}: {str(e)}", "error")

    return redirect(url_for("project_workspace", project_id=project_id))

@app.route("/projects/<project_id>/run-agent/<agent_key>", methods=["POST"])
@login_required
def run_single_agent_action(project_id, agent_key):
    """Rerun or execute a specific agent stage."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    user_api_key = session.get("gemini_api_key")
    try:
        updated_state = workflow_service.execute_single_stage(project_id, agent_key, api_key=user_api_key)
        if updated_state.get("error_info"):
            flash(f"Agent {agent_key} failed: {updated_state['error_info']}", "error")
        else:
            flash(f"{agent_key.capitalize()} Agent rerun completed.", "success")
    except Exception as e:
        flash(f"Error executing agent {agent_key}: {str(e)}", "error")

    # Redirect back to appropriate output view
    redirect_map = {
        "coding": "project_code_output",
        "testing": "project_testing_results",
        "security": "project_security_results",
        "review": "project_code_review",
        "deployment": "project_deployment",
        "project_manager": "project_report_detail"
    }
    target_route = redirect_map.get(agent_key, "project_workspace")
    return redirect(url_for(target_route, project_id=project_id))

# =====================================================================
# AGENT SPECIFIC OUTPUT VIEWS
# =====================================================================

@app.route("/projects/<project_id>/code")
@login_required
def project_code_output(project_id):
    """Render Coding Agent output workspace with real filesystem tree explorer."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    from services.file_explorer_service import FileExplorerService
    file_tree = FileExplorerService.get_project_tree(project_id)
    files = code_generator.get_project_files_from_db(project_id)
    selected_filename = request.args.get("selected_file")
    
    current_file = None
    if selected_filename:
        ok, details, _ = FileExplorerService.get_file_details(project_id, selected_filename)
        if ok:
            current_file = details

    if not current_file and files:
        candidate = "app.py" if any(f["filename"] == "app.py" for f in files) else files[0]["filename"]
        ok, details, _ = FileExplorerService.get_file_details(project_id, candidate)
        if ok:
            current_file = details
        else:
            current_file = files[0]

    return render_template(
        "code_output.html",
        active_page="projects",
        project=project,
        file_tree=file_tree,
        files=files,
        current_file=current_file
    )

# =====================================================================
# PROJECT-SPECIFIC FILE EXPLORER APIS (FEATURE 3)
# =====================================================================

@app.route("/api/projects/<project_id>/files/tree")
@login_required
def api_project_files_tree(project_id):
    """Return real hierarchical filesystem tree for the project."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    from services.file_explorer_service import FileExplorerService
    tree = FileExplorerService.get_project_tree(project_id)
    return jsonify(tree)

@app.route("/api/projects/<project_id>/files/content")
@login_required
def api_project_file_content(project_id):
    """Fetch file content, line counts, and metadata safely."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    rel_path = request.args.get("path", "")
    from services.file_explorer_service import FileExplorerService
    ok, details, msg = FileExplorerService.get_file_details(project_id, rel_path)
    if not ok:
        return jsonify({"success": False, "error": msg}), 400
    return jsonify({"success": True, "file": details})

@app.route("/api/projects/<project_id>/files/save", methods=["POST"])
@login_required
def api_project_file_save(project_id):
    """Safely update file content with AST validation."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    data = request.get_json() or {}
    rel_path = data.get("path", "")
    content = data.get("content", "")
    from services.file_explorer_service import FileExplorerService
    ok, msg = FileExplorerService.save_file_content(project_id, rel_path, content)
    return jsonify({"success": ok, "message": msg}), (200 if ok else 400)

@app.route("/projects/<project_id>/files/download")
@login_required
def download_project_individual_file(project_id):
    """Download individual file securely from project workspace."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    rel_path = request.args.get("path", "")
    from services.file_explorer_service import FileExplorerService
    from flask import send_file
    from services.workspace_manager import get_project_workspace
    ws = get_project_workspace(project_id)
    target = (ws / os.path.normpath(rel_path).lstrip(r"\/")).resolve()
    try:
        target.relative_to(ws)
    except ValueError:
        abort(403)
    if not target.exists() or not target.is_file():
        abort(404)
    return send_file(target, as_attachment=True, download_name=target.name)

# =====================================================================
# UI REFERENCE REPLICATION & UPLOAD APIS (FEATURE 4 & 11)
# =====================================================================

@app.route("/projects/<project_id>/references/upload", methods=["POST"])
@login_required
def upload_ui_reference_image(project_id):
    """Upload and preserve UI reference design image for a specific page."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    page_name = request.form.get("page_name", "dashboard").strip()
    img_file = request.files.get("reference_image")
    if not img_file or not img_file.filename:
        flash("Please select a UI reference screenshot or wireframe image.", "error")
        return redirect(url_for("project_ui_preview", project_id=project_id, tab="references"))

    file_bytes = img_file.read()
    if len(file_bytes) < 100:
        flash("Invalid image file uploaded.", "error")
        return redirect(url_for("project_ui_preview", project_id=project_id, tab="references"))

    from services.ui_reference_service import UIReferenceService
    ref_info = UIReferenceService.save_reference_image(
        project_id=project_id,
        page_name=page_name,
        file_bytes=file_bytes,
        original_filename=img_file.filename
    )
    flash(f"Design reference for '{page_name}' uploaded and analyzed successfully!", "success")
    return redirect(url_for("project_ui_preview", project_id=project_id, tab="references"))

@app.route("/api/projects/<project_id>/references")
@login_required
def api_get_project_references(project_id):
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    from services.ui_reference_service import UIReferenceService
    refs = UIReferenceService.get_project_references(project_id)
    return jsonify({"success": True, "references": refs})

@app.route("/projects/<project_id>/references/<int:ref_id>/image")
@login_required
def get_project_reference_image(project_id, ref_id):
    """Serve preserved UI reference image for project."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    from services.ui_reference_service import UIReferenceService
    refs = UIReferenceService.get_project_references(project_id)
    matched = next((r for r in refs if r["id"] == ref_id), None)
    if not matched:
        abort(404)
    img_path = Path(matched["image_path"])
    if not img_path.exists():
        abort(404)
    from flask import send_file
    return send_file(img_path, mimetype="image/png")

# =====================================================================
# AGENT OBSERVABILITY & EVIDENCE APIS (FEATURE 8)
# =====================================================================

@app.route("/api/projects/<project_id>/agents/reports")
@login_required
def api_get_agent_reports(project_id):
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    from services.agent_metrics_service import AgentMetricsService
    reports = AgentMetricsService.get_agent_reports_for_project(project_id)
    executions = project_service.get_project_agent_executions(project_id)
    completed_stages = sum(1 for e in executions if e["status"] == "completed")
    progress_pct = int((completed_stages / len(executions)) * 100) if executions else 0
    return jsonify({
        "success": True,
        "reports": reports,
        "progress_pct": progress_pct,
        "status": project.get("status", "in_progress"),
        "current_stage": project.get("current_stage", "requirements")
    })

@app.route("/api/projects/<project_id>/agents/<agent_key>")
@login_required
def api_get_agent_detail(project_id, agent_key):
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    from services.agent_metrics_service import AgentMetricsService
    detail = AgentMetricsService.get_agent_report_detail(project_id, agent_key)
    if not detail:
        abort(404)
    return jsonify({"success": True, "agent": detail, "report": detail})

@app.route("/api/projects/<project_id>/agents/timeline")
@login_required
def api_get_agent_timeline(project_id):
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    from services.agent_metrics_service import AgentMetricsService
    timeline = AgentMetricsService.get_timeline_events(project_id)
    return jsonify({"success": True, "timeline": timeline})


@app.route("/projects/<project_id>/tests")
@login_required
def project_testing_results(project_id):
    """Render Testing Agent sandbox execution report."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    tests = testing_service.get_latest_test_results(project_id)
    return render_template(
        "testing_results.html",
        active_page="projects",
        project=project,
        tests=tests
    )

@app.route("/projects/<project_id>/security")
@login_required
def project_security_results(project_id):
    """Render Security Agent static AST audit findings."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    findings = security_service.get_project_security_findings(project_id)
    counts = {
        "Critical": sum(1 for f in findings if f["severity"] == "Critical"),
        "High": sum(1 for f in findings if f["severity"] == "High"),
        "Medium": sum(1 for f in findings if f["severity"] == "Medium"),
        "Low": sum(1 for f in findings if f["severity"] == "Low"),
        "Informational": sum(1 for f in findings if f["severity"] == "Informational"),
    }
    return render_template(
        "security_results.html",
        active_page="projects",
        project=project,
        findings=findings,
        counts=counts
    )

@app.route("/projects/<project_id>/review")
@login_required
def project_code_review(project_id):
    """Render Code Review Agent report and maintainability scores."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    review = review_service.get_project_code_review(project_id)
    return render_template(
        "code_review.html",
        active_page="projects",
        project=project,
        review=review
    )

@app.route("/projects/<project_id>/deployment")
@login_required
def project_deployment(project_id):
    """Render Deployment Agent container readiness and runbooks."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    deployment = deployment_service.get_project_deployment(project_id)
    return render_template(
        "deployment.html",
        active_page="projects",
        project=project,
        deployment=deployment
    )

@app.route("/projects/<project_id>/report")
@login_required
def project_report_detail(project_id):
    """Render executive Software Delivery Report matching bottom-right panel."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    report = report_service.get_project_report(project_id)
    return render_template(
        "report_detail.html",
        active_page="reports",
        project=project,
        report=report
    )

@app.route("/reports")
@login_required
def reports_list():
    """List all project reports catalog."""
    user_id = get_current_user_id()
    projects = project_service.get_user_projects(user_id)
    return render_template("reports.html", active_page="reports", projects=projects)

# =====================================================================
# AGENTS CATALOG ROUTES
# =====================================================================

@app.route("/agents")
@login_required
def agents_list():
    """Render 8 AI Agents catalog page matching middle-right panel."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM agents ORDER BY stage_order ASC")
    agents = [dict(r) for r in cursor.fetchall()]
    return render_template("agents.html", active_page="agents", agents=agents)

@app.route("/agents/<agent_key>")
@login_required
def agent_detail(agent_key):
    """Render individual agent specifications and recent executions."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM agents WHERE key = ?", (agent_key,))
    agent = cursor.fetchone()
    if not agent:
        abort(404)

    cursor.execute("""
        SELECT * FROM agent_executions WHERE agent_key = ? ORDER BY id DESC LIMIT 5
    """, (agent_key,))
    executions = [dict(r) for r in cursor.fetchall()]

    return render_template("agent_detail.html", active_page="agents", agent=dict(agent), executions=executions)

# =====================================================================
# FILE DOWNLOAD ROUTES (ZIP, PDF, INDIVIDUAL FILES)
# =====================================================================

@app.route("/projects/<project_id>/download/zip")
@login_required
def download_project_zip(project_id):
    """Download full project source code as in-memory ZIP archive."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    zip_buffer = code_generator.create_project_zip(project_id, project["name"])
    filename = f"{project['name'].lower().replace(' ', '_')}_source.zip"
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename
    )

@app.route("/projects/<project_id>/download/pdf")
@login_required
def download_pdf_report(project_id):
    """Generate and download executive ReportLab PDF report."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    pdf_buffer = report_service.generate_pdf_report(project_id)
    filename = f"{project['name'].lower().replace(' ', '_')}_report.pdf"
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@app.route("/projects/<project_id>/download/file/<path:filename>")
@login_required
def download_individual_file(project_id, filename):
    """Download an individual generated file safely."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    found, content = code_generator.get_file_content(project_id, filename)
    if not found:
        abort(404)

    from io import BytesIO
    buf = BytesIO(content.encode("utf-8"))
    clean_name = os.path.basename(filename)
    return send_file(
        buf,
        mimetype="text/plain",
        as_attachment=True,
        download_name=clean_name
    )

# =====================================================================
# SETTINGS & PROFILE ROUTES
# =====================================================================

@app.route("/settings")
@login_required
def settings_page():
    """Render settings and orchestration configuration page."""
    from services.ai_service import (
        get_xai_api_key, get_xai_model, is_xai_configured,
        get_gemini_api_key, is_api_key_configured, mask_api_key,
        get_active_ai_provider
    )
    xai_key = get_xai_api_key()
    xai_configured = is_xai_configured(xai_key)
    masked_xai = mask_api_key(xai_key) if xai_configured else "Not configured"
    xai_model = get_xai_model()

    gemini_key = get_gemini_api_key()
    gemini_configured = is_api_key_configured(gemini_key)
    masked_gemini = mask_api_key(gemini_key) if gemini_configured else "Not configured"
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    active_provider = get_active_ai_provider()
    provider_pref = os.environ.get("AI_PROVIDER_PREFERENCE", "grok" if xai_configured else "auto")

    auto_fix_limit = session.get("auto_fix_limit", 3)
    sandbox_timeout = session.get("sandbox_timeout", 60)
    security_strictness = session.get("security_strictness", "strict")
    default_framework = session.get("default_framework", "Python Flask")

    return render_template(
        "settings.html",
        active_page="settings",
        xai_configured=xai_configured,
        masked_xai_key=masked_xai,
        xai_model=xai_model,
        gemini_configured=gemini_configured,
        masked_gemini_key=masked_gemini,
        gemini_model=gemini_model,
        active_provider=active_provider,
        provider_preference=provider_pref,
        current_model=gemini_model,
        auto_fix_limit=auto_fix_limit,
        sandbox_timeout=sandbox_timeout,
        security_strictness=security_strictness,
        default_framework=default_framework
    )

@app.route("/settings/save", methods=["POST"])
@login_required
def save_settings():
    """Persist AI model, provider credentials, and multi-agent orchestration settings."""
    from services.ai_service import update_env_variable

    # 1. xAI Grok Configuration
    new_xai_key = request.form.get("xai_api_key", "").strip()
    if new_xai_key and not ("•" in new_xai_key or new_xai_key.startswith("your_")):
        update_env_variable("XAI_API_KEY", new_xai_key)

    new_xai_model = request.form.get("xai_model", "").strip()
    if new_xai_model:
        update_env_variable("XAI_MODEL", new_xai_model)

    # 2. Gemini Configuration
    new_gemini_key = request.form.get("gemini_api_key", "").strip()
    if new_gemini_key and not ("•" in new_gemini_key or new_gemini_key.startswith("your_")):
        update_env_variable("GEMINI_API_KEY", new_gemini_key)

    new_gemini_model = request.form.get("gemini_model", request.form.get("model_name", "gemini-2.5-flash")).strip()
    if new_gemini_model:
        update_env_variable("GEMINI_MODEL", new_gemini_model)

    provider_preference = request.form.get("provider_preference", "auto").strip()
    update_env_variable("AI_PROVIDER_PREFERENCE", provider_preference)

    try:
        auto_fix_limit = int(request.form.get("auto_fix_limit", 3))
    except (ValueError, TypeError):
        auto_fix_limit = 3
    try:
        sandbox_timeout = int(request.form.get("sandbox_timeout", 60))
    except (ValueError, TypeError):
        sandbox_timeout = 60
    security_strictness = request.form.get("security_strictness", "strict").strip()
    default_framework = request.form.get("default_framework", "Python Flask").strip()

    session["auto_fix_limit"] = auto_fix_limit
    session["sandbox_timeout"] = sandbox_timeout
    session["security_strictness"] = security_strictness
    session["default_framework"] = default_framework

    flash("AI provider configuration and orchestration preferences updated successfully.", "success")
    return redirect(url_for("settings_page"))

@app.route("/settings/test-ai", methods=["POST"])
@login_required
def test_ai_connection():
    """Execute live verification of AI Orchestration Engine and providers."""
    from services.ai_service import test_xai_connection, test_gemini_connection, get_active_ai_provider

    target_provider = request.form.get("provider", "active").strip().lower()
    if target_provider in ("grok", "xai"):
        candidate_key = request.form.get("xai_api_key", "").strip()
        candidate_model = request.form.get("xai_model", "").strip() or None
        override = candidate_key if (candidate_key and "•" not in candidate_key and not candidate_key.startswith("your_")) else None
        success, message = test_xai_connection(api_key=override, model_name=candidate_model)
        if success:
            flash(f"xAI Grok Verification: {message}", "success")
        else:
            flash(f"xAI Grok Verification Failed: {message}", "error")
    elif target_provider == "gemini":
        candidate_key = request.form.get("gemini_api_key", "").strip()
        override = candidate_key if (candidate_key and "•" not in candidate_key and not candidate_key.startswith("your_")) else None
        success, message = test_gemini_connection(api_key=override)
        if success:
            flash(f"Gemini Verification: {message}", "success")
        else:
            flash(f"Gemini Verification Failed: {message}", "error")
    else:
        active = get_active_ai_provider()
        if active == "grok":
            success, message = test_xai_connection()
        elif active == "gemini":
            success, message = test_gemini_connection()
        else:
            success, message = True, "Local deterministic rule engines active. All agents operational."
        if success:
            flash(f"AI Orchestrator ({active.upper()}): {message}", "success")
        else:
            flash(f"AI Orchestrator Verification Warning: {message}", "warning")

    return redirect(url_for("settings_page"))

@app.route("/api/settings/verify-ai", methods=["POST"])
@login_required
def verify_ai_provider_ajax():
    """
    JSON API endpoint for real-time verification of AI providers without leaking secrets.
    """
    from services.ai_service import test_xai_connection, test_gemini_connection, get_active_ai_provider

    data = request.get_json(silent=True) or request.form or {}
    provider = data.get("provider", "grok").strip().lower()
    candidate_key = data.get("api_key", "").strip()
    candidate_model = data.get("model", "").strip() or None
    override = candidate_key if (candidate_key and "•" not in candidate_key and not candidate_key.startswith("your_")) else None

    if provider in ("grok", "xai"):
        success, message = test_xai_connection(api_key=override, model_name=candidate_model)
        return jsonify({
            "provider": "grok",
            "success": success,
            "message": message
        })
    elif provider == "gemini":
        success, message = test_gemini_connection(api_key=override)
        return jsonify({
            "provider": "gemini",
            "success": success,
            "message": message
        })
    else:
        active = get_active_ai_provider()
        if active == "grok":
            success, message = test_xai_connection()
        elif active == "gemini":
            success, message = test_gemini_connection()
        else:
            success, message = True, "Local deterministic engines verified."
        return jsonify({
            "provider": active,
            "success": success,
            "message": message
        })

@app.route("/profile")
@login_required
def profile_page():
    """Render user profile and change password view."""
    user_id = get_current_user_id()
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as total FROM projects WHERE user_id = ?", (user_id,))
    total_projects = cursor.fetchone()["total"]

    return render_template(
        "profile.html",
        active_page="settings",
        user=user,
        total_projects=total_projects
    )

@app.route("/profile/password", methods=["POST"])
@login_required
def update_password():
    """Handle password change."""
    user_id = get_current_user_id()
    current_pwd = request.form.get("current_password", "")
    new_pwd = request.form.get("new_password", "")
    confirm_pwd = request.form.get("confirm_new_password", "")

    if not current_pwd or not new_pwd:
        flash("Please fill all required password fields.", "error")
        return redirect(url_for("profile_page"))

    if new_pwd != confirm_pwd:
        flash("New passwords do not match.", "error")
        return redirect(url_for("profile_page"))

    if len(new_pwd) < 6:
        flash("New password must be at least 6 characters.", "error")
        return redirect(url_for("profile_page"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if not user or not check_password_hash(user["password_hash"], current_pwd):
        flash("Current password entered is incorrect.", "error")
        return redirect(url_for("profile_page"))

    new_hash = generate_password_hash(new_pwd)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    db.commit()

    flash("Password updated successfully.", "success")
    return redirect(url_for("profile_page"))

# =====================================================================
# EXECUTION & PREVIEW ROUTE ALIASES FOR COMPATIBILITY
# =====================================================================

@app.route("/projects/<project_id>/execution/run", methods=["POST"])
@login_required
def run_project_application_alias(project_id):
    return run_project_app_action(project_id)

@app.route("/projects/<project_id>/execution/stop", methods=["POST"])
@login_required
def stop_project_application_alias(project_id):
    return stop_project_action(project_id)

@app.route("/projects/<project_id>/execution/restart", methods=["POST"])
@login_required
def restart_project_application_alias(project_id):
    return restart_project_action(project_id)

@app.route("/projects/<project_id>/execution/logs")
@login_required
def project_execution_logs_alias(project_id):
    return project_logs_view(project_id)

@app.route("/projects/<project_id>/execution/tests", methods=["POST"])
@login_required
def run_project_test_suite_alias(project_id):
    return run_project_tests_action(project_id)

@app.route("/projects/<project_id>/execution/status")
@login_required
def get_execution_status(project_id):
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    return jsonify(execution_service.get_project_process_status(project_id))

@app.route("/projects/<project_id>/ui-preview/render/<path:page_name>")
@login_required
def render_raw_preview_page_path(project_id, page_name):
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
    auth_mode = request.args.get("auth", "auto")
    current_user_info = {
        "name": session.get("user_name", "Developer"),
        "email": session.get("user_email", "developer@devguardian.ai")
    }
    success, html_output = ui_service.render_preview_page(
        project_id, page_name, auth_mode=auth_mode, current_user_info=current_user_info
    )
    return html_output, (200 if success else 404), {"Content-Type": "text/html; charset=utf-8"}

@app.route("/projects/<project_id>/validate/e2e", methods=["POST"])
@login_required
def run_e2e_validation_alias(project_id):
    return run_project_validation_action(project_id)

# =====================================================================
# ENTERPRISE NAVIGATION & UPGRADE ROUTES (CHAT, ARCHITECTURE, DOCS, HISTORY)
# =====================================================================

@app.route("/generate", methods=["GET", "POST"])
@login_required
def generate_project_alias():
    """Alias route for project generation wizard."""
    return redirect(url_for("new_project"))

# --- 1. CHATGPT-STYLE AI CHAT ---

ALLOWED_CHAT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_CHAT_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB

@app.route("/chat")
@login_required
def chat_page():
    """ChatGPT-style interactive AI chat interface with project context and multimodal capability."""
    user_id = get_current_user_id()
    projects = project_service.get_user_projects(user_id)
    selected_project_id = request.args.get("project_id", "")
    
    conn = get_standalone_db()
    cursor = conn.cursor()
    if selected_project_id:
        cursor.execute("""
            SELECT * FROM chat_messages 
            WHERE user_id = ? AND (project_id = ? OR project_id IS NULL)
            ORDER BY created_at ASC, id ASC
        """, (user_id, selected_project_id))
    else:
        cursor.execute("""
            SELECT * FROM chat_messages 
            WHERE user_id = ?
            ORDER BY created_at ASC, id ASC
        """, (user_id,))
    messages = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    return render_template(
        "chat.html",
        active_page="chat",
        projects=projects,
        selected_project_id=selected_project_id,
        messages=messages
    )

@app.route("/chat/send", methods=["POST"])
@login_required
def chat_send():
    """Process incoming chat message, multimodal image attachment, or workflow triggers."""
    user_id = get_current_user_id()
    project_id = request.form.get("project_id") or None
    message_text = request.form.get("message", "").strip()
    image_file = request.files.get("image")
    
    if not message_text and not image_file:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"success": False, "error": "Please provide a message or attach an image."}), 400
        flash("Please provide a message or attach an image.", "warning")
        return redirect(url_for("chat_page", project_id=project_id or ""))

    # Validate and handle image attachment if provided
    saved_rel_image_path = None
    saved_abs_image_path = None
    if image_file and image_file.filename:
        ext = os.path.splitext(image_file.filename)[1].lower()
        if ext not in ALLOWED_CHAT_EXTENSIONS:
            return jsonify({"success": False, "error": f"Unsupported image format '{ext}'. Allowed: {', '.join(ALLOWED_CHAT_EXTENSIONS)}"}), 400
        
        # Check size
        image_file.seek(0, os.SEEK_END)
        size = image_file.tell()
        image_file.seek(0)
        if size > MAX_CHAT_IMAGE_BYTES:
            return jsonify({"success": False, "error": f"Image exceeds maximum limit of 10 MB ({size // (1024*1024)} MB uploaded)."}), 400

        fname = f"{secrets.token_hex(8)}_{secure_filename(image_file.filename)}"
        upload_dir = Path(__file__).resolve().parent / "static" / "uploads" / "chat"
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_abs = upload_dir / fname
        image_file.save(str(saved_abs))
        saved_abs_image_path = str(saved_abs)
        saved_rel_image_path = f"/static/uploads/chat/{fname}"

    # Record User Message
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chat_messages (user_id, project_id, role, content, image_path, model_used)
            VALUES (?, ?, 'user', ?, ?, ?)
        """, (user_id, project_id, message_text or "(Image attached)", saved_rel_image_path, "user"))
        user_msg_id = cursor.lastrowid
    conn.close()

    ai_reply = ""
    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    lower_text = message_text.lower()

    # Specialized Workflow Trigger 1: Multimodal Image Analysis
    if saved_abs_image_path:
        prompt_for_img = message_text if message_text else "Analyze this architecture or software UI image. Detail the components, relationships, patterns, and suggested software specifications."
        sys_instruction = (
            "You are DevGuardian AI, an Enterprise Software Architect. "
            "Inspect the provided diagram or wireframe meticulously. "
            "Extract all identifiable components, services, databases, external APIs, and user interactions. "
            "Provide structured architectural feedback and recommend concrete implementation steps."
        )
        success, res = ai_service.call_gemini_multimodal(
            prompt=prompt_for_img,
            image_path=saved_abs_image_path,
            system_instruction=sys_instruction,
            api_key=session.get("gemini_api_key")
        )
        ai_reply = res

    # Specialized Workflow Trigger 2: Generate Architecture Diagram from Chat
    elif ("generate architecture" in lower_text or "architecture diagram" in lower_text or "generate the architecture" in lower_text) and project_id:
        try:
            arch_res = architecture_generator.generate_project_architecture(project_id, diagram_type="system")
            project_service.log_project_activity(
                project_id, "architecture_generated", "Architecture Generated via Chat",
                f"Generated system diagram with {arch_res.get('components_count', 0)} components"
            )
            ai_reply = (
                f"### System Architecture Diagram Generated Successfully\n\n"
                f"I have inspected the project source code, routes, and data models to generate an enterprise-grade architecture diagram following the approved visual standard (light blue nodes, dark blue borders, directional data flows):\n\n"
                f"- **Components Mapped**: {arch_res.get('components_count', 0)} nodes\n"
                f"- **Connections & Flows**: {arch_res.get('connections_count', 0)} relationships\n"
                f"- **Format Exports**: PNG (High-Resolution Supersampled) & Vector SVG\n\n"
                f"**Actions Available**:\n"
                f"- [View Interactive Architecture Diagram](/architecture?project_id={project_id})\n"
                f"- [Download Diagram PNG](/architecture/{project_id}/export/png)\n"
                f"- [Download Diagram SVG](/architecture/{project_id}/export/svg)\n\n"
                f"Would you like me to compile the master reference documentation next?"
            )
        except Exception as e:
            ai_reply = f"Error generating architecture diagram: {str(e)}"

    # Specialized Workflow Trigger 3: Generate / Prepare Documentation from Chat
    elif ("generate documentation" in lower_text or "prepare project documentation" in lower_text or "generate documentation again" in lower_text or "reference template" in lower_text) and project_id:
        try:
            doc_res = documentation_service.generate_project_documentation(project_id)
            if doc_res.get("success"):
                project_service.log_project_activity(
                    project_id, "documentation_generated", "Documentation Generated via Chat",
                    f"Generated DOCX ({doc_res.get('docx_size', 0)} bytes) and PDF"
                )
                ai_reply = (
                    f"### Master Reference Documentation Generated Successfully\n\n"
                    f"The project documentation has been generated strictly adhering to your approved reference format (**CaptionAI_Documentation.docx**):\n\n"
                    f"- **SmartBridge Logo Preserved**: {doc_res.get('validation', {}).get('checks', {}).get('smartbridge_logo', 'Verified')}\n"
                    f"- **SkillWallet Logo Preserved**: {doc_res.get('validation', {}).get('checks', {}).get('skillwallet_logo', 'Verified')}\n"
                    f"- **Architecture Diagram Embedded**: Under Technical Architecture section\n"
                    f"- **Outputs Created**: Both Microsoft Word DOCX and ReportLab PDF with two-pass header/footer page numbering\n\n"
                    f"**Downloads**:\n"
                    f"- [Download Master DOCX Document](/documentation/{project_id}/download/docx)\n"
                    f"- [Download Formatted PDF Document](/documentation/{project_id}/download/pdf)\n"
                    f"- [View Documentation Overview](/documentation?project_id={project_id})"
                )
            else:
                ai_reply = f"Documentation Generation Note: {doc_res.get('error', 'Unable to complete documentation')}"
        except Exception as e:
            ai_reply = f"Error generating documentation: {str(e)}"

    # Specialized Workflow Trigger 4: Project Generation Request in Chat
    elif lower_text.startswith("build ") or lower_text.startswith("create ") or "build a " in lower_text or "create a " in lower_text:
        # Prompt model to design requirements and offer launch link
        proj_context = ""
        if project_id:
            curr_proj = project_service.get_project_by_id(project_id, user_id=user_id)
            if curr_proj:
                proj_context = f"Current Selected Project Context: {curr_proj.get('name')} - {curr_proj.get('description')}\n\n"

        sys_prompt = (
            "You are DevGuardian AI Enterprise Project Architect. "
            "The user wants to plan or build an application. "
            "Analyze their request, specify: 1. Core Functional Requirements, 2. Architectural Blueprint & Agents, "
            "3. Database Schemas, and 4. Recommended Tech Stack. "
            "End with a clear confirmation and advise that they can initialize this project directly into DevGuardian's autonomous 8-agent generation pipeline."
        )
        success, response_text = ai_service.call_gemini(
            prompt=f"{proj_context}User Project Request:\n{message_text}",
            system_instruction=sys_prompt,
            api_key=session.get("gemini_api_key")
        )
        
        # Generate safe link for initializing the project
        safe_title = message_text.split(".")[0].replace("Build ", "").replace("build ", "").replace("Create ", "").replace("create ", "").strip()[:40]
        encoded_title = urllib.parse.quote(safe_title)
        encoded_desc = urllib.parse.quote(message_text)
        action_btn_md = f"\n\n---\n**Ready to generate this project?**\n[Launch Project Generation Wizard with these specifications](/projects/new?name={encoded_title}&desc={encoded_desc})\n"
        ai_reply = response_text + action_btn_md

    # Default: Conversational AI Engineering Copilot
    else:
        proj_info = ""
        if project_id:
            curr_proj = project_service.get_project_by_id(project_id, user_id=user_id)
            if curr_proj:
                proj_info = f"Current active project: {curr_proj.get('name')} ({curr_proj.get('app_type')}, {curr_proj.get('language')}). Description: {curr_proj.get('description')}.\n"

        sys_prompt = (
            "You are DevGuardian AI, an Enterprise Senior Software Architect & Autonomous Project Orchestrator. "
            "You assist software engineers in requirements analysis, architecture diagramming, multi-agent pipelines, "
            "code generation, security auditing, and strictly compliant DOCX/PDF documentation. "
            "Provide insightful, professional, markdown-formatted responses with clear headings, bullet points, and code snippets when helpful."
        )
        full_prompt = f"{proj_info}User prompt: {message_text}"
        success, res = ai_service.call_gemini(
            prompt=full_prompt,
            system_instruction=sys_prompt,
            api_key=session.get("gemini_api_key")
        )
        ai_reply = res

    # Record Assistant Response
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chat_messages (user_id, project_id, role, content, model_used)
            VALUES (?, ?, 'assistant', ?, ?)
        """, (user_id, project_id, ai_reply, model_name))
        ai_msg_id = cursor.lastrowid
    conn.close()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({
            "success": True,
            "user_message": {
                "id": user_msg_id,
                "role": "user",
                "content": message_text,
                "image_path": saved_rel_image_path
            },
            "assistant_message": {
                "id": ai_msg_id,
                "role": "assistant",
                "content": ai_reply,
                "model": model_name
            }
        })

    return redirect(url_for("chat_page", project_id=project_id or ""))

@app.route("/chat/clear", methods=["POST"])
@login_required
def chat_clear():
    """Clear chat messages for current user and optional project context."""
    user_id = get_current_user_id()
    project_id = request.form.get("project_id") or None
    
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        if project_id:
            cursor.execute("DELETE FROM chat_messages WHERE user_id = ? AND project_id = ?", (user_id, project_id))
        else:
            cursor.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
    conn.close()
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"success": True})
    flash("Chat conversation history cleared.", "info")
    return redirect(url_for("chat_page", project_id=project_id or ""))

# --- 2. ARCHITECTURE SIDEBAR PAGE & GENERATOR ---

@app.route("/architecture")
@login_required
def architecture_page():
    """Dedicated architecture page visualizing system components, data flows, and agents."""
    user_id = get_current_user_id()
    projects = project_service.get_user_projects(user_id)
    project_id = request.args.get("project_id")
    if not project_id and projects:
        project_id = projects[0]["id"]
        
    project = None
    arch_data = None
    diagram_type = request.args.get("type", "system")
    
    if project_id:
        project = project_service.get_project_by_id(project_id, user_id=user_id)
        if project:
            arch_data = architecture_generator.get_project_architecture_data(project_id, diagram_type=diagram_type)
            
    return render_template(
        "architecture.html",
        active_page="architecture",
        projects=projects,
        selected_project=project,
        selected_project_id=project_id,
        arch_data=arch_data,
        diagram_type=diagram_type
    )

@app.route("/architecture/<project_id>/generate", methods=["POST"])
@login_required
def architecture_generate_action(project_id):
    """Generate or regenerate architecture diagram for project and diagram type."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
        
    diagram_type = request.form.get("diagram_type") or (request.json.get("diagram_type") if request.is_json else "system") or "system"
    arch_data = architecture_generator.generate_project_architecture(project_id, diagram_type=diagram_type)
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"success": True, "data": arch_data})
        
    flash(f"{diagram_type.title()} architecture diagram generated successfully.", "success")
    return redirect(url_for("architecture_page", project_id=project_id, type=diagram_type))

@app.route("/architecture/<project_id>/export/<fmt>")
@login_required
def architecture_export_file(project_id, fmt):
    """Securely export generated architecture diagram as PNG or SVG."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
        
    diagram_type = request.args.get("type", "system")
    fmt = fmt.lower().strip()
    
    conn = get_standalone_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT png_path, svg_path FROM project_architecture 
        WHERE project_id = ? AND diagram_type = ?
    """, (project_id, diagram_type))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        arch = architecture_generator.generate_project_architecture(project_id, diagram_type=diagram_type)
        png_path = arch.get("png_path")
        svg_path = arch.get("svg_path")
    else:
        png_path = row["png_path"]
        svg_path = row["svg_path"]

    safe_name = project["name"].lower().replace(" ", "_")
    
    if fmt == "png":
        if not png_path or not os.path.exists(png_path):
            abort(404)
        return send_file(
            png_path,
            mimetype="image/png",
            as_attachment=True,
            download_name=f"{safe_name}_{diagram_type}_architecture.png"
        )
    elif fmt == "svg":
        if not svg_path or not os.path.exists(svg_path):
            abort(404)
        return send_file(
            svg_path,
            mimetype="image/svg+xml",
            as_attachment=True,
            download_name=f"{safe_name}_{diagram_type}_architecture.svg"
        )
    elif fmt == "json":
        arch = architecture_generator.get_project_architecture_data(project_id, diagram_type=diagram_type)
        json_path = arch.get("json_path") if arch else None
        if json_path and os.path.exists(json_path):
            return send_file(
                json_path,
                mimetype="application/json",
                as_attachment=True,
                download_name=f"{safe_name}_{diagram_type}_architecture.json"
            )
        model_data = arch.get("model") if (arch and arch.get("model")) else arch
        return Response(
            json.dumps(model_data or {}, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment; filename={safe_name}_{diagram_type}_architecture.json"}
        )
    else:
        abort(400)

@app.route("/architecture/<project_id>/source")
@login_required
def architecture_source_json(project_id):
    """Retrieve Mermaid and structured intermediate representation."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
        
    diagram_type = request.args.get("type", "system")
    arch = architecture_generator.get_project_architecture_data(project_id, diagram_type=diagram_type)
    return jsonify(arch or {})

# --- 3. DOCUMENTATION SIDEBAR PAGE & STRICT TEMPLATE GENERATOR ---

@app.route("/documentation")
@login_required
def documentation_page():
    """Dedicated documentation page using strict reference template format."""
    user_id = get_current_user_id()
    projects = project_service.get_user_projects(user_id)
    project_id = request.args.get("project_id")
    if not project_id and projects:
        project_id = projects[0]["id"]
        
    project = None
    doc_data = None
    template_status = documentation_template_service.check_master_template_status()
    
    if project_id:
        project = project_service.get_project_by_id(project_id, user_id=user_id)
        if project:
            doc_data = documentation_service.get_project_documentation_data(project_id)
            
    if request.args.get("view") == "preview" and project:
        if not doc_data or not doc_data.get("generated"):
            documentation_service.generate_project_documentation(project_id)
            doc_data = documentation_service.get_project_documentation_data(project_id)
            
        val_report = None
        if doc_data and doc_data.get("docx_path"):
            val_report = documentation_validation_service.validate_project_documentation(
                docx_path=doc_data.get("docx_path"),
                pdf_path=doc_data.get("pdf_path"),
                project_name=project.get("name") if isinstance(project, dict) else None,
                workspace_path=project.get("workspace_path") if isinstance(project, dict) else None
            )

        screenshots = []
        ws_path = project.get("workspace_path")
        if ws_path and os.path.exists(ws_path):
            img_dir = Path(ws_path) / "documentation" / "images"
            if img_dir.exists():
                for img_file in sorted(img_dir.glob("*.png")):
                    screenshots.append({
                        "name": img_file.stem.replace("_", " ").title(),
                        "filename": img_file.name,
                        "rel_path": f"images/{img_file.name}"
                    })

        return render_template(
            "documentation_preview.html",
            active_page="documentation",
            project=project,
            doc_data=doc_data,
            template_status=template_status,
            val_report=val_report,
            screenshots=screenshots
        )

    return render_template(
        "documentation.html",
        active_page="documentation",
        projects=projects,
        selected_project=project,
        selected_project_id=project_id,
        doc_data=doc_data,
        template_status=template_status
    )

@app.route("/documentation/<project_id>/generate", methods=["POST"])
@login_required
def documentation_generate_action(project_id):
    """Generate DOCX & PDF documentation using strict master template."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
        
    res = documentation_service.generate_project_documentation(project_id)
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify(res)
        
    if res.get("success"):
        flash("Project documentation generated and validated successfully with master template.", "success")
    else:
        flash(f"Error generating documentation: {res.get('error')}", "error")
        
    return redirect(url_for("documentation_page", project_id=project_id))

@app.route("/documentation/<project_id>/download/docx")
@login_required
def documentation_download_docx(project_id):
    """Download project DOCX strictly styled to reference template."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
        
    doc_data = documentation_service.get_project_documentation_data(project_id)
    docx_path = doc_data.get("docx_path") if doc_data else None
    
    if not docx_path or not os.path.exists(docx_path):
        res = documentation_service.generate_project_documentation(project_id)
        docx_path = res.get("docx_path")
        
    if not docx_path or not os.path.exists(docx_path):
        flash("Documentation file not found. Please click 'Generate Documentation'.", "error")
        return redirect(url_for("documentation_page", project_id=project_id))
        
    safe_name = project["name"].replace(" ", "_")
    return send_file(
        docx_path,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"{safe_name}_Documentation.docx"
    )

@app.route("/documentation/<project_id>/download/pdf")
@login_required
def documentation_download_pdf(project_id):
    """Download project PDF compiled with two-pass header/footer page numbering."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
        
    doc_data = documentation_service.get_project_documentation_data(project_id)
    pdf_path = doc_data.get("pdf_path") if doc_data else None
    
    if not pdf_path or not os.path.exists(pdf_path):
        res = documentation_service.generate_project_documentation(project_id)
        pdf_path = res.get("pdf_path")
        
    if not pdf_path or not os.path.exists(pdf_path):
        flash("PDF document not found. Please click 'Generate Documentation'.", "error")
        return redirect(url_for("documentation_page", project_id=project_id))
        
    safe_name = project["name"].replace(" ", "_")
    is_inline = request.args.get("inline") == "1" or request.args.get("preview") == "1"
    response = send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=not is_inline,
        download_name=f"{safe_name}_Documentation.pdf"
    )
    if is_inline:
        response.headers["Content-Disposition"] = f'inline; filename="{safe_name}_Documentation.pdf"'
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

@app.route("/documentation/<project_id>/stream/pdf")
@login_required
def documentation_stream_pdf(project_id):
    """Stream project PDF inline with native PDF viewer support for embedded preview."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
        
    doc_data = documentation_service.get_project_documentation_data(project_id)
    pdf_path = doc_data.get("pdf_path") if doc_data else None
    
    if not pdf_path or not os.path.exists(pdf_path):
        res = documentation_service.generate_project_documentation(project_id)
        pdf_path = res.get("pdf_path")
        
    if not pdf_path or not os.path.exists(pdf_path):
        abort(404)
        
    safe_name = project["name"].replace(" ", "_")
    response = send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"{safe_name}_Documentation.pdf"
    )
    response.headers["Content-Disposition"] = f'inline; filename="{safe_name}_Documentation.pdf"'
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response

@app.route("/documentation/<project_id>/preview")
@login_required
def documentation_preview_page(project_id):
    """Interactive in-browser preview page for project-specific master documentation."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
        
    doc_data = documentation_service.get_project_documentation_data(project_id)
    if not doc_data or not doc_data.get("generated"):
        documentation_service.generate_project_documentation(project_id)
        doc_data = documentation_service.get_project_documentation_data(project_id)
        
    template_status = documentation_template_service.check_master_template_status()
    
    val_report = None
    if doc_data and doc_data.get("docx_path"):
        val_report = documentation_validation_service.validate_project_documentation(
            docx_path=doc_data.get("docx_path"),
            pdf_path=doc_data.get("pdf_path"),
            project_name=project.get("name") if isinstance(project, dict) else None,
            workspace_path=project.get("workspace_path") if isinstance(project, dict) else None
        )

    # Discovered screenshots and diagrams for thumbnail inspection
    screenshots = []
    ws_path = project.get("workspace_path")
    if ws_path and os.path.exists(ws_path):
        img_dir = Path(ws_path) / "documentation" / "images"
        if img_dir.exists():
            for img_file in sorted(img_dir.glob("*.png")):
                screenshots.append({
                    "name": img_file.stem.replace("_", " ").title(),
                    "filename": img_file.name,
                    "rel_path": f"images/{img_file.name}"
                })

    return render_template(
        "documentation_preview.html",
        active_page="documentation",
        project=project,
        doc_data=doc_data,
        template_status=template_status,
        val_report=val_report,
        screenshots=screenshots
    )

@app.route("/documentation/<project_id>/asset/<path:asset_path>")
@login_required
def documentation_asset_file(project_id, asset_path):
    """Securely serve project documentation images and diagrams."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
        
    ws_path = project.get("workspace_path")
    if not ws_path or not os.path.exists(ws_path):
        abort(404)
        
    doc_dir = (Path(ws_path) / "documentation").resolve()
    target_file = (doc_dir / asset_path).resolve()
    
    try:
        target_file.relative_to(doc_dir)
    except ValueError:
        abort(403)
        
    if not target_file.exists() or not target_file.is_file():
        abort(404)
        
    ext_mimes = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf"
    }
    mime = ext_mimes.get(target_file.suffix.lower(), "application/octet-stream")
    return send_file(target_file, mimetype=mime)

@app.route("/documentation/<project_id>/validate", methods=["POST"])
@login_required
def documentation_validate_action(project_id):
    """Run validation checks on generated documentation and return status JSON."""
    user_id = get_current_user_id()
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)
        
    doc_data = documentation_service.get_project_documentation_data(project_id)
    if not doc_data or not doc_data.get("docx_path"):
        return jsonify({"valid": False, "error": "No documentation generated yet"}), 400
        
    val = documentation_validation_service.validate_project_documentation(
        docx_path=doc_data.get("docx_path"),
        pdf_path=doc_data.get("pdf_path"),
        project_name=project.get("name") if isinstance(project, dict) else None,
        workspace_path=project.get("workspace_path") if isinstance(project, dict) else None
    )
    return jsonify(val)

# --- 3b. DOCUMENTATION ASSISTANT CHATBOT (CONVERSATIONAL PIPELINE) ---

@app.route("/documentation-assistant")
@login_required
def documentation_assistant_page():
    """Interactive Documentation Assistant Chatbot interface with live document preview and generation pipeline."""
    user_id = get_current_user_id()
    projects = project_service.get_user_projects(user_id)
    project_id = request.args.get("project_id")
    if not project_id and projects:
        project_id = projects[0]["id"]

    project = None
    conversation = None
    messages = []
    doc_data = None
    val_report = None
    template_status = documentation_template_service.check_master_template_status()

    if project_id:
        project = project_service.get_project_by_id(project_id, user_id=user_id)
        if project:
            conversation = documentation_chat_service.get_or_create_conversation(user_id, project_id)
            messages = documentation_chat_service.get_conversation_messages(conversation["id"])
            doc_data = documentation_service.get_project_documentation_data(project_id)
            if doc_data and doc_data.get("docx_path"):
                val_report = documentation_validation_service.validate_project_documentation(
                    docx_path=doc_data.get("docx_path"),
                    pdf_path=doc_data.get("pdf_path"),
                    project_name=project.get("name") if isinstance(project, dict) else None,
                    workspace_path=project.get("workspace_path") if isinstance(project, dict) else None
                )

    user_conversations = documentation_chat_service.list_user_conversations(user_id)

    return render_template(
        "documentation_assistant.html",
        active_page="documentation_assistant",
        projects=projects,
        selected_project=project,
        selected_project_id=project_id,
        conversation=conversation,
        messages=messages,
        user_conversations=user_conversations,
        doc_data=doc_data,
        val_report=val_report,
        template_status=template_status
    )

@app.route("/documentation-assistant/chat", methods=["POST"])
@login_required
def documentation_assistant_chat_action():
    """Process incoming conversational message, attachment, or documentation prompt."""
    user_id = get_current_user_id()
    project_id = request.form.get("project_id") or (request.json.get("project_id") if request.is_json else None)
    conversation_id = request.form.get("conversation_id") or (request.json.get("conversation_id") if request.is_json else None)
    message_text = request.form.get("message") or (request.json.get("message") if request.is_json else "") or ""
    attachment_file = request.files.get("attachment")

    if not project_id:
        return jsonify({"success": False, "error": "A valid project must be selected."}), 400

    if not message_text.strip() and not attachment_file:
        return jsonify({"success": False, "error": "Please enter a message or attach a file."}), 400

    res = documentation_chat_service.handle_incoming_chat_message(
        user_id=user_id,
        project_id=project_id,
        conversation_id=conversation_id,
        message_text=message_text.strip(),
        attachment_file=attachment_file,
        gemini_api_key=session.get("gemini_api_key")
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify(res)

    if not res.get("success"):
        flash(f"Error: {res.get('error')}", "error")

    return redirect(url_for("documentation_assistant_page", project_id=project_id))

@app.route("/documentation-assistant/generate", methods=["POST"])
@login_required
def documentation_assistant_generate_action():
    """Trigger one-click documentation generation from assistant toolbar."""
    user_id = get_current_user_id()
    project_id = request.form.get("project_id") or (request.json.get("project_id") if request.is_json else None)
    if not project_id:
        return jsonify({"success": False, "error": "Project ID required."}), 400

    project = project_service.get_project_by_id(project_id, user_id=user_id)
    if not project:
        abort(404)

    # Use chat service to generate and record in conversation
    res = documentation_chat_service.handle_incoming_chat_message(
        user_id=user_id,
        project_id=project_id,
        message_text=f"Generate complete documentation for {project['name']}"
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify(res)

    if res.get("success"):
        flash("Documentation generated successfully.", "success")
    else:
        flash(f"Generation error: {res.get('error')}", "error")

    return redirect(url_for("documentation_assistant_page", project_id=project_id))

@app.route("/documentation-assistant/conversation/new", methods=["POST"])
@login_required
def documentation_assistant_new_conversation():
    """Initialize a clean conversation session for a project."""
    user_id = get_current_user_id()
    project_id = request.form.get("project_id") or (request.json.get("project_id") if request.is_json else None)
    if not project_id:
        return jsonify({"success": False, "error": "Project ID required."}), 400

    conv_id = f"doc_conv_{secrets.token_hex(8)}"
    project = project_service.get_project_by_id(project_id, user_id=user_id)
    p_name = project.get("name", "Project") if project else "Project"

    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documentation_conversations (
                id, user_id, project_id, title, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (conv_id, user_id, project_id, f"{p_name} Documentation Session"))

        initial_greeting = (
            f"Started a new documentation session for **{p_name}**.\n\n"
            f"You can ask me to generate the full documentation, analyze the real routes & schema, "
            f"or update specific sections. All outputs strictly follow the **CaptionAI master reference standard**."
        )
        cursor.execute("""
            INSERT INTO documentation_chat_messages (
                conversation_id, user_id, project_id, role, content, metadata_json
            ) VALUES (?, ?, ?, 'assistant', ?, ?)
        """, (conv_id, user_id, project_id, initial_greeting, json.dumps({"action": "new_session"})))
    conn.close()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"success": True, "conversation_id": conv_id})

    return redirect(url_for("documentation_assistant_page", project_id=project_id))

@app.route("/documentation-assistant/conversation/<conv_id>/clear", methods=["POST"])
@login_required
def documentation_assistant_clear_conversation(conv_id):
    """Clear messages in the selected conversation."""
    user_id = get_current_user_id()
    project_id = request.form.get("project_id")
    documentation_chat_service.clear_conversation_messages(conv_id, user_id)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"success": True})

    flash("Conversation history cleared.", "info")
    return redirect(url_for("documentation_assistant_page", project_id=project_id or ""))

# --- 4. PROJECT HISTORY & ACTIVITY TIMELINE ---

@app.route("/history")
@login_required
def history_page():
    """Project history and audit log timeline across all generated projects."""
    user_id = get_current_user_id()
    projects = project_service.get_user_projects(user_id)
    project_id = request.args.get("project_id")
    
    activity_logs = project_service.get_project_activity_logs(
        project_id=project_id if project_id else None,
        user_id=user_id if not project_id else None,
        limit=100
    )
    
    return render_template(
        "history.html",
        active_page="history",
        projects=projects,
        selected_project_id=project_id or "",
        activity_logs=activity_logs
    )

# =====================================================================
# ERROR HANDLERS
# =====================================================================

@app.errorhandler(404)
def not_found_error(error):
    if _is_api_or_ajax_request():
        return jsonify({
            "success": False,
            "status": "failed",
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested resource or endpoint was not found."
            }
        }), 404
    return render_template("404.html", hide_sidebar=True), 404

@app.errorhandler(500)
def internal_error(error):
    if _is_api_or_ajax_request():
        return jsonify({
            "success": False,
            "status": "failed",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred while processing your request."
            }
        }), 500
    return render_template("500.html", hide_sidebar=True), 500

@app.errorhandler(403)
def forbidden_error(error):
    if _is_api_or_ajax_request():
        return jsonify({
            "success": False,
            "status": "failed",
            "error": {
                "code": "FORBIDDEN",
                "message": "Access forbidden: Invalid CSRF token or insufficient permissions."
            }
        }), 403
    return render_template("500.html", hide_sidebar=True), 403

@app.errorhandler(405)
def method_not_allowed_error(error):
    if _is_api_or_ajax_request():
        return jsonify({
            "success": False,
            "status": "failed",
            "error": {
                "code": "METHOD_NOT_ALLOWED",
                "message": f"The method {request.method} is not allowed for this endpoint."
            }
        }), 405
    return render_template("500.html", hide_sidebar=True), 405

# =====================================================================
# MAIN APPLICATION LAUNCHER
# =====================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n==========================================================")
    print(f" DevGuardian AI — Autonomous Software Project Manager")
    print(f" Server starting on http://127.0.0.1:{port}")
    print(f" Design: Minimalist Grey & White SaaS Theme")
    print(f" Multi-Agent Orchestrator: LangGraph 1.2.8")
    print(f" Database: SQLite ({Path(__file__).parent / 'instance' / 'devguardian.db'})")
    print(f"==========================================================\n")
    # Centralized port allocation and stale process reconciliation
    try:
        with app.app_context():
            reconcile_info = PortManager.reconcile_and_seed_default_ports()
            print(f" PortManager: Initialized {reconcile_info.get('reconciled_count', 0)} project ports and cleaned {reconcile_info.get('stale_cleaned', 0)} stale records.\n")
    except Exception as e:
        print(f" PortManager init warning: {e}\n")

    # use_reloader=False prevents watchdog from killing in-flight agent workflows
    # when code files are created in generated_projects/ or .env is edited.
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
