import os
import secrets
from urllib.parse import urlencode, urlparse, urljoin
from typing import Dict, Any, Optional, Tuple, List
import requests

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API = "https://api.github.com/user"
GITHUB_EMAILS_API = "https://api.github.com/user/emails"

def is_safe_redirect_url(target: Optional[str]) -> bool:
    """Validate that redirect target is relative and not an open redirect vulnerability."""
    if not target:
        return False
    # Target must start with a single slash and not double slash (//evil.com) or backslash
    if not target.startswith("/") or target.startswith("//") or target.startswith("/\\"):
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc

def generate_oauth_state() -> str:
    """Generate cryptographically secure random state for OAuth CSRF protection."""
    return secrets.token_urlsafe(32)

def is_provider_configured(provider: str) -> bool:
    """Check if required OAuth credentials exist in environment for provider."""
    provider = provider.lower()
    if provider == "google":
        return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))
    elif provider == "github":
        return bool(os.environ.get("GITHUB_CLIENT_ID") and os.environ.get("GITHUB_CLIENT_SECRET"))
    return False

def get_missing_credentials_message(provider: str) -> str:
    """Return friendly message explaining required credentials for provider."""
    provider = provider.lower()
    if provider == "google":
        return "Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in environment variables."
    elif provider == "github":
        return "GitHub OAuth is not configured. Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in environment variables."
    return f"OAuth provider '{provider}' is not supported."

# =====================================================================
# GOOGLE OAUTH FLOW HELPERS
# =====================================================================

def get_google_authorization_url(state: str, redirect_uri: str) -> str:
    """Build Google OAuth 2.0 authorization URL with required OpenID Connect scopes."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

def exchange_google_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    """Securely exchange authorization code for Google tokens."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(GOOGLE_TOKEN_URL, data=payload, headers=headers, timeout=10)
    
    if not response.ok:
        try:
            err_data = response.json()
            err_msg = err_data.get("error_description") or err_data.get("error") or response.text
        except Exception:
            err_msg = response.text
        raise ValueError(f"Google token exchange failed ({response.status_code}): {err_msg}")
        
    return response.json()

def verify_google_identity(id_token_str: str) -> Dict[str, Any]:
    """Verify Google OpenID Connect ID token and return verified claims."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    
    request = google_requests.Request()
    id_info = id_token.verify_oauth2_token(id_token_str, request, client_id)
    
    # Verify issuer
    if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
        raise ValueError("Invalid ID token issuer.")
        
    # Extract identity
    provider_user_id = id_info.get("sub")
    if not provider_user_id:
        raise ValueError("Google ID token missing subject identifier ('sub').")
        
    email = id_info.get("email", "").strip().lower()
    email_verified = bool(id_info.get("email_verified", False))
    full_name = id_info.get("name") or (email.split("@")[0].replace(".", " ").title() if email else "Google Developer")
    
    return {
        "provider": "google",
        "provider_user_id": str(provider_user_id),
        "email": email,
        "email_verified": email_verified,
        "full_name": full_name,
    }

# =====================================================================
# GITHUB OAUTH FLOW HELPERS
# =====================================================================

def get_github_authorization_url(state: str, redirect_uri: str) -> str:
    """Build GitHub OAuth authorization URL requesting least-privilege scopes."""
    client_id = os.environ.get("GITHUB_CLIENT_ID", "")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email",
        "state": state,
    }
    return f"{GITHUB_AUTH_URL}?{urlencode(params)}"

def exchange_github_code(code: str, redirect_uri: str) -> str:
    """Securely exchange authorization code for GitHub access token."""
    client_id = os.environ.get("GITHUB_CLIENT_ID", "")
    client_secret = os.environ.get("GITHUB_CLIENT_SECRET", "")
    
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Accept": "application/json"}
    response = requests.post(GITHUB_TOKEN_URL, json=payload, headers=headers, timeout=10)
    
    if not response.ok:
        raise ValueError(f"GitHub token exchange HTTP error {response.status_code}")
        
    data = response.json()
    if "error" in data:
        err_desc = data.get("error_description", data["error"])
        raise ValueError(f"GitHub token exchange error: {err_desc}")
        
    access_token = data.get("access_token")
    if not access_token:
        raise ValueError("No access token returned by GitHub.")
        
    return access_token

def get_github_identity(access_token: str) -> Dict[str, Any]:
    """Fetch GitHub user profile and verified primary email."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "DevGuardian-AI-OAuth"
    }
    
    # 1. Fetch user profile
    user_res = requests.get(GITHUB_USER_API, headers=headers, timeout=10)
    if not user_res.ok:
        raise ValueError(f"Failed to fetch GitHub profile ({user_res.status_code})")
        
    user_data = user_res.json()
    github_user_id = user_data.get("id")
    if not github_user_id:
        raise ValueError("GitHub profile did not contain a user id.")
        
    login = user_data.get("login", "github_user")
    full_name = user_data.get("name") or login
    
    # 2. Fetch email addresses (handles private emails)
    email = user_data.get("email")
    email_verified = False
    
    # Always query authenticated email endpoint to find verified status and primary email
    emails_res = requests.get(GITHUB_EMAILS_API, headers=headers, timeout=10)
    if emails_res.ok:
        emails_list = emails_res.json()
        if isinstance(emails_list, list):
            # Prefer primary and verified email
            for entry in emails_list:
                if entry.get("primary") and entry.get("verified"):
                    email = entry.get("email")
                    email_verified = True
                    break
            # Fallback to any verified email
            if not email_verified:
                for entry in emails_list:
                    if entry.get("verified"):
                        email = entry.get("email")
                        email_verified = True
                        break
                        
    if email:
        email = email.strip().lower()
        
    return {
        "provider": "github",
        "provider_user_id": str(github_user_id),
        "email": email or "",
        "email_verified": email_verified,
        "full_name": full_name,
    }
