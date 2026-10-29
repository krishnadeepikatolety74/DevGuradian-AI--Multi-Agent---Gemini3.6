import os
import sys
import unittest
import sqlite3
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from db import init_db, get_standalone_db
import services.oauth_service as oauth_service
import services.project_service as project_service

class OAuthAuthenticationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        init_db()

    def setUp(self):
        self.client = app.test_client()
        # Set dummy credentials for testing
        os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test-google-client-secret"
        os.environ["GITHUB_CLIENT_ID"] = "test-github-client-id"
        os.environ["GITHUB_CLIENT_SECRET"] = "test-github-client-secret"
        
        # Clean test user data
        conn = get_standalone_db()
        with conn:
            conn.execute("DELETE FROM oauth_accounts WHERE provider_email LIKE '%@test-oauth.com'")
            conn.execute("DELETE FROM users WHERE email LIKE '%@test-oauth.com'")
            conn.execute("DELETE FROM projects WHERE name LIKE 'OAuth Test Project%'")
        conn.close()

    def tearDown(self):
        conn = get_standalone_db()
        with conn:
            conn.execute("DELETE FROM oauth_accounts WHERE provider_email LIKE '%@test-oauth.com'")
            conn.execute("DELETE FROM users WHERE email LIKE '%@test-oauth.com'")
            conn.execute("DELETE FROM projects WHERE name LIKE 'OAuth Test Project%'")
        conn.close()

    # 1. Google OAuth initiation
    def test_01_google_oauth_initiation(self):
        res = self.client.get("/auth/google")
        self.assertEqual(res.status_code, 302)
        location = res.headers.get("Location", "")
        self.assertTrue(location.startswith("https://accounts.google.com/o/oauth2/v2/auth"))
        self.assertIn("client_id=test-google-client-id", location)
        self.assertIn("response_type=code", location)
        self.assertIn("scope=openid+email+profile", location)
        self.assertIn("state=", location)
        
        with self.client.session_transaction() as sess:
            self.assertIn("oauth_state", sess)
            self.assertEqual(sess.get("oauth_provider"), "google")

    # 2. Google callback success
    @patch("services.oauth_service.exchange_google_code")
    @patch("services.oauth_service.verify_google_identity")
    def test_02_google_callback_success(self, mock_verify, mock_exchange):
        mock_exchange.return_value = {"id_token": "mock_id_token", "access_token": "mock_access_token"}
        mock_verify.return_value = {
            "provider": "google",
            "provider_user_id": "google-sub-1001",
            "email": "user1@test-oauth.com",
            "email_verified": True,
            "full_name": "Google User One"
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state123"
            sess["oauth_provider"] = "google"

        res = self.client.get("/auth/callback/google?code=valid_code&state=state123")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get("Location"), "/dashboard")

        with self.client.session_transaction() as sess:
            self.assertIsNotNone(sess.get("user_id"))
            self.assertEqual(sess.get("user_email"), "user1@test-oauth.com")
            self.assertEqual(sess.get("auth_provider"), "google")

    # 3. Google callback state validation failure
    def test_03_google_callback_state_validation_failure(self):
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "correct_state"

        res = self.client.get("/auth/callback/google?code=valid_code&state=wrong_state", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Security verification failed", res.data)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    # 4. Google provider denial / cancellation
    def test_04_google_provider_denial(self):
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state123"

        res = self.client.get("/auth/callback/google?error=access_denied&state=state123", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Google authentication was cancelled", res.data)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    # 5. Google missing/unverified email
    @patch("services.oauth_service.exchange_google_code")
    @patch("services.oauth_service.verify_google_identity")
    def test_05_google_missing_email(self, mock_verify, mock_exchange):
        mock_exchange.return_value = {"id_token": "mock_id_token"}
        mock_verify.return_value = {
            "provider": "google",
            "provider_user_id": "google-sub-unverified",
            "email": "",
            "email_verified": False,
            "full_name": "Unverified User"
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state123"

        res = self.client.get("/auth/callback/google?code=valid_code&state=state123")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get("Location"), "/auth/complete-registration")

        with self.client.session_transaction() as sess:
            self.assertIn("pending_oauth_registration", sess)

    # 6. Google existing-user login (no duplicate user created)
    @patch("services.oauth_service.exchange_google_code")
    @patch("services.oauth_service.verify_google_identity")
    def test_06_google_existing_user_login(self, mock_verify, mock_exchange):
        mock_exchange.return_value = {"id_token": "mock_id_token"}
        mock_verify.return_value = {
            "provider": "google",
            "provider_user_id": "google-sub-2002",
            "email": "existing_google@test-oauth.com",
            "email_verified": True,
            "full_name": "Existing Google Dev"
        }

        # First login (registration)
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state_first"
        self.client.get("/auth/callback/google?code=code1&state=state_first")

        # Second login
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["oauth_state"] = "state_second"

        res2 = self.client.get("/auth/callback/google?code=code2&state=state_second", follow_redirects=True)
        self.assertEqual(res2.status_code, 200)
        self.assertIn(b"Welcome back", res2.data)

        # Verify only 1 user exists in DB
        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE email = 'existing_google@test-oauth.com'")
        self.assertEqual(cursor.fetchone()["cnt"], 1)
        conn.close()

    # 7. Google new-user registration
    @patch("services.oauth_service.exchange_google_code")
    @patch("services.oauth_service.verify_google_identity")
    def test_07_google_new_user_registration(self, mock_verify, mock_exchange):
        mock_exchange.return_value = {"id_token": "mock_id_token"}
        mock_verify.return_value = {
            "provider": "google",
            "provider_user_id": "google-sub-3003",
            "email": "new_google_reg@test-oauth.com",
            "email_verified": True,
            "full_name": "New Google Register"
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state_new"

        res = self.client.get("/auth/callback/google?code=code_new&state=state_new", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Account created and signed in with Google", res.data)

        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM oauth_accounts WHERE provider = 'google' AND provider_user_id = 'google-sub-3003'")
        oauth_row = cursor.fetchone()
        self.assertIsNotNone(oauth_row)
        self.assertEqual(oauth_row["provider_email"], "new_google_reg@test-oauth.com")
        conn.close()

    # 8. GitHub OAuth initiation
    def test_08_github_oauth_initiation(self):
        res = self.client.get("/auth/github")
        self.assertEqual(res.status_code, 302)
        location = res.headers.get("Location", "")
        self.assertTrue(location.startswith("https://github.com/login/oauth/authorize"))
        self.assertIn("client_id=test-github-client-id", location)
        self.assertIn("scope=read%3Auser+user%3Aemail", location)
        self.assertIn("state=", location)

        with self.client.session_transaction() as sess:
            self.assertIn("oauth_state", sess)
            self.assertEqual(sess.get("oauth_provider"), "github")

    # 9. GitHub callback success
    @patch("services.oauth_service.exchange_github_code")
    @patch("services.oauth_service.get_github_identity")
    def test_09_github_callback_success(self, mock_identity, mock_exchange):
        mock_exchange.return_value = "gh_access_token_123"
        mock_identity.return_value = {
            "provider": "github",
            "provider_user_id": "gh-id-4004",
            "email": "ghuser@test-oauth.com",
            "email_verified": True,
            "full_name": "GitHub Developer Four"
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state_gh"

        res = self.client.get("/auth/callback/github?code=code_gh&state=state_gh")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get("Location"), "/dashboard")

        with self.client.session_transaction() as sess:
            self.assertIsNotNone(sess.get("user_id"))
            self.assertEqual(sess.get("user_email"), "ghuser@test-oauth.com")
            self.assertEqual(sess.get("auth_provider"), "github")

    # 10. GitHub callback state validation failure
    def test_10_github_callback_state_validation_failure(self):
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "valid_state_gh"

        res = self.client.get("/auth/callback/github?code=code_gh&state=invalid_state_gh", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Security verification failed", res.data)

    # 11. GitHub provider denial
    def test_11_github_provider_denial(self):
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state_gh"

        res = self.client.get("/auth/callback/github?error=access_denied&state=state_gh", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"GitHub authentication was cancelled", res.data)

    # 12. GitHub private email handling
    @patch("requests.get")
    def test_12_github_private_email_handling(self, mock_get):
        # 1st call for /user (profile has email=None)
        user_resp = MagicMock()
        user_resp.ok = True
        user_resp.json.return_value = {"id": 887766, "login": "octo_private", "name": "Private Octocat", "email": None}

        # 2nd call for /user/emails (private primary verified email)
        emails_resp = MagicMock()
        emails_resp.ok = True
        emails_resp.json.return_value = [
            {"email": "unverified@test-oauth.com", "primary": False, "verified": False},
            {"email": "private_primary@test-oauth.com", "primary": True, "verified": True}
        ]

        mock_get.side_effect = [user_resp, emails_resp]

        identity = oauth_service.get_github_identity("dummy_token")
        self.assertEqual(identity["provider_user_id"], "887766")
        self.assertEqual(identity["email"], "private_primary@test-oauth.com")
        self.assertTrue(identity["email_verified"])
        self.assertEqual(identity["full_name"], "Private Octocat")

    # 13. GitHub existing-user login
    @patch("services.oauth_service.exchange_github_code")
    @patch("services.oauth_service.get_github_identity")
    def test_13_github_existing_user_login(self, mock_identity, mock_exchange):
        mock_exchange.return_value = "gh_token"
        mock_identity.return_value = {
            "provider": "github",
            "provider_user_id": "gh-id-5005",
            "email": "existing_gh@test-oauth.com",
            "email_verified": True,
            "full_name": "Existing GH User"
        }

        # First login
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state1"
        self.client.get("/auth/callback/github?code=c1&state=state1")

        # Second login
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["oauth_state"] = "state2"

        res = self.client.get("/auth/callback/github?code=c2&state=state2", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Welcome back", res.data)

        # Verify only 1 user exists
        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE email = 'existing_gh@test-oauth.com'")
        self.assertEqual(cursor.fetchone()["cnt"], 1)
        conn.close()

    # 14. GitHub new-user registration
    @patch("services.oauth_service.exchange_github_code")
    @patch("services.oauth_service.get_github_identity")
    def test_14_github_new_user_registration(self, mock_identity, mock_exchange):
        mock_exchange.return_value = "gh_token"
        mock_identity.return_value = {
            "provider": "github",
            "provider_user_id": "gh-id-6006",
            "email": "new_gh@test-oauth.com",
            "email_verified": True,
            "full_name": "New GH User"
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "state_gh_new"

        res = self.client.get("/auth/callback/github?code=c_new&state=state_gh_new", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Account created and signed in with GitHub", res.data)

        conn = get_standalone_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM oauth_accounts WHERE provider = 'github' AND provider_user_id = 'gh-id-6006'")
        self.assertIsNotNone(cursor.fetchone())
        conn.close()

    # 15. Duplicate provider identity handling (uniqueness constraint)
    def test_15_duplicate_provider_identity_handling(self):
        conn = get_standalone_db()
        with conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (full_name, email, password_hash)
                VALUES ('Dup Test', 'dup1@test-oauth.com', 'hash123')
            """)
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO oauth_accounts (user_id, provider, provider_user_id, provider_email)
                VALUES (?, 'google', 'same-provider-uid', 'dup1@test-oauth.com')
            """, (u_id,))

            with self.assertRaises(sqlite3.IntegrityError):
                cursor.execute("""
                    INSERT INTO oauth_accounts (user_id, provider, provider_user_id, provider_email)
                    VALUES (?, 'google', 'same-provider-uid', 'dup2@test-oauth.com')
                """, (u_id,))
        conn.close()

    # 16. Account-linking protection
    @patch("services.oauth_service.exchange_google_code")
    @patch("services.oauth_service.verify_google_identity")
    def test_16_account_linking_protection(self, mock_verify, mock_exchange):
        # 1. Create email/password user
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "token123"
        self.client.post("/register", data={
            "csrf_token": "token123",
            "full_name": "Password User",
            "email": "link_test@test-oauth.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.client.get("/logout")

        # 2. Try to log in with Google using same email
        mock_exchange.return_value = {"id_token": "mock_id_token"}
        mock_verify.return_value = {
            "provider": "google",
            "provider_user_id": "google-link-777",
            "email": "link_test@test-oauth.com",
            "email_verified": True,
            "full_name": "Google Link Attempt"
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "link_state"

        res = self.client.get("/auth/callback/google?code=linkcode&state=link_state")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get("Location"), "/auth/link-account")

        # Verify not automatically signed in
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))
            self.assertIn("pending_oauth_link", sess)

        # 3. Confirm linking with correct password
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "link_csrf"
        res_confirm = self.client.post("/auth/link-account/confirm", data={
            "csrf_token": "link_csrf",
            "password": "Password123!"
        }, follow_redirects=True)

        self.assertEqual(res_confirm.status_code, 200)
        self.assertIn(b"Successfully linked your Google account", res_confirm.data)

        # Verify user is now authenticated
        with self.client.session_transaction() as sess:
            self.assertIsNotNone(sess.get("user_id"))
            self.assertEqual(sess.get("auth_provider"), "google")

    # 17. Missing provider credentials
    def test_17_missing_provider_credentials(self):
        # Unset credentials
        os.environ.pop("GOOGLE_CLIENT_ID", None)
        os.environ.pop("GOOGLE_CLIENT_SECRET", None)

        res = self.client.get("/auth/google", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Google OAuth is not configured", res.data)

        os.environ.pop("GITHUB_CLIENT_ID", None)
        os.environ.pop("GITHUB_CLIENT_SECRET", None)

        res_gh = self.client.get("/auth/github", follow_redirects=True)
        self.assertEqual(res_gh.status_code, 200)
        self.assertIn(b"GitHub OAuth is not configured", res_gh.data)

    # 18. Session creation and rotation
    @patch("services.oauth_service.exchange_google_code")
    @patch("services.oauth_service.verify_google_identity")
    def test_18_session_creation(self, mock_verify, mock_exchange):
        mock_exchange.return_value = {"id_token": "mock_id_token"}
        mock_verify.return_value = {
            "provider": "google",
            "provider_user_id": "google-session-test",
            "email": "session_test@test-oauth.com",
            "email_verified": True,
            "full_name": "Session Tester"
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "sess_state"
            sess["oauth_provider"] = "google"

        self.client.get("/auth/callback/google?code=c&state=sess_state")

        with self.client.session_transaction() as sess:
            self.assertIsNotNone(sess.get("user_id"))
            self.assertIsNotNone(sess.get("csrf_token"))
            self.assertIsNone(sess.get("oauth_state"))
            self.assertIsNone(sess.get("pending_oauth_link"))

    # 19. Dashboard redirection and open redirect prevention
    @patch("services.oauth_service.exchange_google_code")
    @patch("services.oauth_service.verify_google_identity")
    def test_19_dashboard_redirection(self, mock_verify, mock_exchange):
        mock_exchange.return_value = {"id_token": "mock_id_token"}
        mock_verify.return_value = {
            "provider": "google",
            "provider_user_id": "google-redir-test",
            "email": "redir_test@test-oauth.com",
            "email_verified": True,
            "full_name": "Redirect Tester"
        }

        # Safe next URL
        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "redir_state"
            sess["oauth_next"] = "/projects"

        res = self.client.get("/auth/callback/google?code=c&state=redir_state")
        self.assertEqual(res.headers.get("Location"), "/projects")

        # Unsafe open redirect attempt
        with self.client.session_transaction() as sess:
            sess.clear()
            sess["oauth_state"] = "redir_state2"
            sess["oauth_next"] = "https://evil.com"

        res2 = self.client.get("/auth/callback/google?code=c&state=redir_state2")
        self.assertEqual(res2.headers.get("Location"), "/dashboard")

    # 20. Logout compatibility
    @patch("services.oauth_service.exchange_google_code")
    @patch("services.oauth_service.verify_google_identity")
    def test_20_logout_compatibility(self, mock_verify, mock_exchange):
        mock_exchange.return_value = {"id_token": "mock_id_token"}
        mock_verify.return_value = {
            "provider": "google",
            "provider_user_id": "google-logout-test",
            "email": "logout_test@test-oauth.com",
            "email_verified": True,
            "full_name": "Logout Tester"
        }

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "logout_state"

        self.client.get("/auth/callback/google?code=c&state=logout_state")
        
        # Verify authenticated
        with self.client.session_transaction() as sess:
            self.assertIsNotNone(sess.get("user_id"))

        # Logout
        res_logout = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(res_logout.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    # 21. Database transaction failure handling
    @patch("services.oauth_service.exchange_google_code")
    @patch("services.oauth_service.verify_google_identity")
    @patch("app.get_db")
    def test_21_database_transaction_failure_handling(self, mock_get_db, mock_verify, mock_exchange):
        mock_exchange.return_value = {"id_token": "mock_id_token"}
        mock_verify.return_value = {
            "provider": "google",
            "provider_user_id": "google-db-fail",
            "email": "db_fail@test-oauth.com",
            "email_verified": True,
            "full_name": "DB Fail Tester"
        }

        # Mock DB to raise IntegrityError on cursor execute
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.execute.side_effect = sqlite3.IntegrityError("Simulated DB integrity failure")
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value = mock_conn

        with self.client.session_transaction() as sess:
            sess["oauth_state"] = "db_fail_state"

        res = self.client.get("/auth/callback/google?code=c&state=db_fail_state", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"An account creation error occurred", res.data)

    # 22. Existing email/password login compatibility
    def test_22_existing_email_password_login_compatibility(self):
        # Register via password
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf_pwd"
        self.client.post("/register", data={
            "csrf_token": "csrf_pwd",
            "full_name": "Standard Dev",
            "email": "standard@test-oauth.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.client.get("/logout")

        # Sign in via password
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf_login"
        res = self.client.post("/login", data={
            "csrf_token": "csrf_login",
            "email": "standard@test-oauth.com",
            "password": "Password123!"
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Welcome back, Standard Dev", res.data)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_email"), "standard@test-oauth.com")

    # 23. Unauthorized project access prevention
    def test_23_unauthorized_project_access_prevention(self):
        # Create User A & User B
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf1"
        self.client.post("/register", data={
            "csrf_token": "csrf1",
            "full_name": "Owner A",
            "email": "owner_a@test-oauth.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })

        with self.client.session_transaction() as sess:
            owner_a_id = sess["user_id"]

        # Create Project owned by User A
        proj_id = project_service.create_project(
            user_id=owner_a_id,
            name="OAuth Test Project A",
            description="Project owned by User A"
        )

        self.client.get("/logout")

        # Register User B
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf2"
        self.client.post("/register", data={
            "csrf_token": "csrf2",
            "full_name": "Attacker B",
            "email": "attacker_b@test-oauth.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })

        # User B attempts to access User A's project
        res_overview = self.client.get(f"/projects/{proj_id}")
        self.assertEqual(res_overview.status_code, 404)

        res_workspace = self.client.get(f"/projects/{proj_id}/workspace")
        self.assertEqual(res_workspace.status_code, 404)

        res_code = self.client.get(f"/projects/{proj_id}/code")
        self.assertEqual(res_code.status_code, 404)

        res_tests = self.client.get(f"/projects/{proj_id}/tests")
        self.assertEqual(res_tests.status_code, 404)

if __name__ == "__main__":
    unittest.main()
