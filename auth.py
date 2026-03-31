"""Simple session-based authentication."""
import os
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

# Simple in-memory sessions (for production use Redis/DB)
_sessions = {}

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "digiturk2024")

# Runtime password override (allows changing password without restart)
_password_override = None


def get_password():
    """Return current effective password."""
    return _password_override or ADMIN_PASSWORD


def get_current_user() -> str:
    """Return the admin username."""
    return ADMIN_USERNAME


def change_password(current: str, new: str) -> tuple:
    """Change admin password at runtime. Returns (success, error)."""
    global _password_override
    if current != get_password():
        return False, "Mevcut şifre yanlış"
    if len(new) < 6:
        return False, "Yeni şifre en az 6 karakter olmalı"
    _password_override = new
    return True, None


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"username": username, "created_at": datetime.now(timezone.utc)}
    return token


def verify_session(request: Request) -> dict:
    token = request.cookies.get("session_token")
    if not token or token not in _sessions:
        return None
    session = _sessions[token]
    # 24 hour expiry
    if datetime.now(timezone.utc) - session["created_at"] > timedelta(hours=24):
        del _sessions[token]
        return None
    return session


def require_auth(request: Request):
    if not verify_session(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})


def logout(token: str):
    _sessions.pop(token, None)
