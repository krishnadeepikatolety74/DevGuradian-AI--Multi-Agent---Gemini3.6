"""
DevGuardian AI — Project Launch Authentication & Session Verification Suite
Validates:
1. Valid session allows launching a project and continues with startup.
2. Expired session returns 401 with login_url preserving next=/projects/<id>/workspace.
3. Logged out user receives 401 with login_url on project-launch API / SSE.
4. Login with next param redirects back to the project workspace.
5. Unauthorized access (user A attempting to launch user B's project) receives 403 Forbidden.
6. Session cookie configuration uses 'devguardian_session' (avoids 127.0.0.1 port collisions).
7. Subprocess environment receives isolated SESSION_COOKIE_NAME for generated projects.
"""
import pytest
from unittest.mock import patch
from app import app
from db import init_db, get_standalone_db
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client

@pytest.fixture
def test_users_and_projects():
    """Create two test users and their respective projects."""
    init_db()
    conn = get_standalone_db()
    with conn:
        cursor = conn.cursor()

        # User A
        cursor.execute("SELECT id FROM users WHERE email = 'usera@devguardian.ai'")
        row_a = cursor.fetchone()
        pwd_hash = generate_password_hash("password123")
        if not row_a:
            cursor.execute("""
                INSERT INTO users (full_name, email, password_hash, role)
                VALUES ('User A', 'usera@devguardian.ai', ?, 'Developer')
            """, (pwd_hash,))
            user_a_id = cursor.lastrowid
        else:
            user_a_id = row_a["id"]
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pwd_hash, user_a_id))

        # User B
        cursor.execute("SELECT id FROM users WHERE email = 'userb@devguardian.ai'")
        row_b = cursor.fetchone()
        if not row_b:
            cursor.execute("""
                INSERT INTO users (full_name, email, password_hash, role)
                VALUES ('User B', 'userb@devguardian.ai', ?, 'Developer')
            """, (pwd_hash,))
            user_b_id = cursor.lastrowid
        else:
            user_b_id = row_b["id"]
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pwd_hash, user_b_id))

        # Project for User A
        cursor.execute("SELECT id FROM projects WHERE id = 'proj_usera_secret'")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO projects (id, user_id, name, description, status)
                VALUES ('proj_usera_secret', ?, 'User A Project', 'Private Project', 'created')
            """, (user_a_id,))
        else:
            cursor.execute("UPDATE projects SET user_id = ? WHERE id = 'proj_usera_secret'", (user_a_id,))

        # Project for User B
        cursor.execute("SELECT id FROM projects WHERE id = 'proj_userb_secret'")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO projects (id, user_id, name, description, status)
                VALUES ('proj_userb_secret', ?, 'User B Project', 'Private Project', 'created')
            """, (user_b_id,))
        else:
            cursor.execute("UPDATE projects SET user_id = ? WHERE id = 'proj_userb_secret'", (user_b_id,))

    conn.close()

    yield {
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "project_a_id": "proj_usera_secret",
        "project_b_id": "proj_userb_secret"
    }

def test_session_cookie_configuration():
    """Verify session cookie name is isolated to 'devguardian_session'."""
    assert app.config["SESSION_COOKIE_NAME"] == "devguardian_session"
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

def test_launch_while_logged_in_with_valid_session(client, test_users_and_projects):
    """Scenario 1: Launch while logged in with a valid session."""
    data = test_users_and_projects
    user_a_id = data["user_a_id"]
    proj_a_id = data["project_a_id"]

    # Establish session
    with client.session_transaction() as sess:
        sess["user_id"] = user_a_id
        sess["user_name"] = "User A"
        sess["user_email"] = "usera@devguardian.ai"

    # Mock execution_service.start_project_app
    with patch("services.execution_service.start_project_app") as mock_start:
        mock_start.return_value = {
            "success": True,
            "status": "Running",
            "local_url": "http://127.0.0.1:5050",
            "port": 5050,
            "pid": 99999,
            "stage": "ready",
            "message": "Application started successfully"
        }

        # Send launch request
        res = client.post(
            f"/projects/{proj_a_id}/run-project",
            headers={"Accept": "application/json"}
        )

        assert res.status_code == 200
        json_data = res.get_json()
        assert json_data["success"] is True
        assert json_data["status"] == "running"
        assert json_data["local_url"] == "http://127.0.0.1:5050"
        assert json_data["port"] == 5050
        mock_start.assert_called_once_with(proj_a_id)

def test_launch_after_session_expires(client, test_users_and_projects):
    """Scenario 2: Launch after session expires returns 401 with structured JSON and login_url."""
    data = test_users_and_projects
    proj_a_id = data["project_a_id"]

    # Ensure no active session
    with client.session_transaction() as sess:
        sess.clear()

    res = client.post(
        f"/projects/{proj_a_id}/run-project",
        headers={"Accept": "application/json"}
    )

    assert res.status_code == 401
    json_data = res.get_json()
    assert json_data["success"] is False
    assert json_data["status"] == "failed"
    assert "error" in json_data
    assert json_data["error"]["code"] == "UNAUTHORIZED"
    assert "session has expired or you are not signed in" in json_data["error"]["message"].lower()
    # login_url must preserve next parameter pointing to the workspace
    assert "login_url" in json_data
    assert f"/projects/{proj_a_id}/workspace" in json_data["login_url"]

def test_stream_launch_after_session_expires(client, test_users_and_projects):
    """Scenario 2b: SSE Stream launch after session expires returns 401 with login_url."""
    data = test_users_and_projects
    proj_a_id = data["project_a_id"]

    with client.session_transaction() as sess:
        sess.clear()

    res = client.get(
        f"/projects/{proj_a_id}/run-project-stream",
        headers={"Accept": "text/event-stream"}
    )

    assert res.status_code == 401
    json_data = res.get_json()
    assert json_data["error"]["code"] == "UNAUTHORIZED"
    assert f"/projects/{proj_a_id}/workspace" in json_data["login_url"]

def test_launch_after_logout(client, test_users_and_projects):
    """Scenario 3: Launch after logging out."""
    data = test_users_and_projects
    user_a_id = data["user_a_id"]
    proj_a_id = data["project_a_id"]

    # First log in
    with client.session_transaction() as sess:
        sess["user_id"] = user_a_id

    # Now call logout route
    logout_res = client.get("/logout", follow_redirects=False)
    assert logout_res.status_code == 302

    # Attempt launch after logging out
    res = client.post(
        f"/projects/{proj_a_id}/run-project",
        headers={"Accept": "application/json"}
    )
    assert res.status_code == 401
    json_data = res.get_json()
    assert json_data["error"]["code"] == "UNAUTHORIZED"
    assert f"/projects/{proj_a_id}/workspace" in json_data["login_url"]

def test_login_preserves_next_and_redirects_to_workspace(client, test_users_and_projects):
    """Scenario 4: Logging in again preserves 'next' parameter and redirects to project workspace."""
    data = test_users_and_projects
    proj_a_id = data["project_a_id"]

    res = client.post(
        f"/login?next=/projects/{proj_a_id}/workspace",
        data={
            "email": "usera@devguardian.ai",
            "password": "password123",
            "next": f"/projects/{proj_a_id}/workspace"
        },
        follow_redirects=False
    )

    assert res.status_code == 302
    assert res.location == f"/projects/{proj_a_id}/workspace"

def test_attempt_to_launch_project_without_authorization(client, test_users_and_projects):
    """Scenario 5: Attempt to launch a project owned by another user returns HTTP 403 Forbidden."""
    data = test_users_and_projects
    user_b_id = data["user_b_id"]
    proj_a_id = data["project_a_id"] # Owned by User A!

    # User B logs in
    with client.session_transaction() as sess:
        sess["user_id"] = user_b_id
        sess["user_name"] = "User B"
        sess["user_email"] = "userb@devguardian.ai"

    # User B attempts to launch User A's private project via POST
    res = client.post(
        f"/projects/{proj_a_id}/run-project",
        headers={"Accept": "application/json"}
    )

    assert res.status_code == 403
    json_data = res.get_json()
    assert json_data["success"] is False
    assert json_data["error"]["code"] == "FORBIDDEN"
    assert "not authorized" in json_data["error"]["message"].lower()

    # User B attempts to launch User A's private project via SSE Stream
    stream_res = client.get(
        f"/projects/{proj_a_id}/run-project-stream",
        headers={"Accept": "text/event-stream"}
    )
    assert stream_res.status_code == 403
    stream_json = stream_res.get_json()
    assert stream_json["error"]["code"] == "FORBIDDEN"

    # User B attempts to query status
    status_res = client.get(
        f"/projects/{proj_a_id}/status-json",
        headers={"Accept": "application/json"}
    )
    assert status_res.status_code == 403
    status_json = status_res.get_json()
    assert status_json["error"]["code"] == "FORBIDDEN"

def test_subprocess_cookie_name_isolation(test_users_and_projects):
    """Scenario 6: Subprocess environment receives a project-specific SESSION_COOKIE_NAME."""
    from services.execution_service import start_project_app
    from pathlib import Path

    proj_id = test_users_and_projects["project_a_id"]
    proj_dir = Path("generated_projects") / proj_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    app_py = proj_dir / "app.py"
    app_py.write_text("# dummy app\n", encoding="utf-8")

    try:
        with patch("services.project_service.get_project_by_id") as mock_get:
            mock_get.return_value = {
                "id": proj_id,
                "name": "User A Project",
                "entry_point": "app.py"
            }
            with patch("subprocess.Popen") as mock_popen, \
                 patch("services.port_manager.PortManager.allocate_port", return_value=5999), \
                 patch("services.execution_service.is_server_reachable", return_value=True):
                mock_proc = mock_popen.return_value
                mock_proc.pid = 12345
                mock_proc.poll.return_value = None
                start_project_app(proj_id)
                assert mock_popen.called
                popen_kwargs = mock_popen.call_args[1]
                env = popen_kwargs["env"]
                # Subprocess MUST have its own SESSION_COOKIE_NAME set
                assert "SESSION_COOKIE_NAME" in env
                assert env["SESSION_COOKIE_NAME"] != "devguardian_session"
                assert proj_id[:16] in env["SESSION_COOKIE_NAME"]
    finally:
        if app_py.exists():
            app_py.unlink()
        if proj_dir.exists():
            try:
                proj_dir.rmdir()
            except Exception:
                pass
