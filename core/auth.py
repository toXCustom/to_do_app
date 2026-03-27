"""
auth.py — User authentication for My Tasks.
Stores users in users.json with PBKDF2-HMAC-SHA256 hashed passwords.
Registration requires username + email. Login accepts username OR email.
"""

import json
import re
import hashlib
import secrets

USERS_FILE = "data/users.json"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_users() -> dict:
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_users(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)


def _hash_password(password: str, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=260_000,
    )
    return key.hex(), salt


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def _find_by_login(identifier: str, users: dict):
    """
    Resolve a login identifier (username or email) to a users-dict key.
    Returns the key string or None.
    """
    ident = identifier.strip().lower()
    # Direct username match
    if ident in users:
        return ident
    # Email match — scan all records
    for key, rec in users.items():
        if rec.get("email", "").lower() == ident:
            return key
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def user_exists(username: str) -> bool:
    return username.strip().lower() in _load_users()


def email_exists(email: str) -> bool:
    email = email.strip().lower()
    return any(r.get("email", "").lower() == email for r in _load_users().values())


def register_user(username: str, email: str, password: str):
    """
    Create a new user with username + email.
    Returns (success: bool, message: str).
    """
    username = username.strip()
    email    = email.strip()

    if not username:
        return False, "Username cannot be empty."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if not email:
        return False, "Email cannot be empty."
    if not _is_valid_email(email):
        return False, "Please enter a valid email address."
    if not password:
        return False, "Password cannot be empty."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    users = _load_users()
    if username.lower() in users:
        return False, "Username already taken."
    if any(r.get("email", "").lower() == email.lower() for r in users.values()):
        return False, "An account with that email already exists."

    hash_hex, salt = _hash_password(password)
    users[username.lower()] = {
        "display_name": username,
        "email":        email.lower(),
        "hash":         hash_hex,
        "salt":         salt,
    }
    _save_users(users)
    return True, "Account created successfully."


def verify_user(identifier: str, password: str):
    """
    Verify credentials by username OR email.
    Returns (success: bool, display_name | error_message).
    """
    users = _load_users()
    key   = _find_by_login(identifier, users)
    if key is None:
        return False, "Username or email not found."

    record = users[key]
    hash_hex, _ = _hash_password(password, salt=record["salt"])
    if hash_hex != record["hash"]:
        return False, "Incorrect password."

    return True, record["display_name"]


def get_display_name(username: str) -> str:
    users = _load_users()
    key   = username.strip().lower()
    return users.get(key, {}).get("display_name", username)