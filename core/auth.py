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
    if len(username) > 32:
        return False, "Username must be 32 characters or fewer."
    if not re.match(r"^[a-zA-Z0-9_\-]+$", username):
        return False, "Username may only contain letters, numbers, _ and -."
    if not email:
        return False, "Email cannot be empty."
    if not _is_valid_email(email):
        return False, "Please enter a valid email address."
    if not password:
        return False, "Password cannot be empty."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    users = _load_users()
    if username.lower() in users:
        return False, "Username already taken."
    if any(r.get("email", "").lower() == email.lower() for r in users.values()):
        return False, "An account with that email already exists."

    hash_hex, salt = _hash_password(password)
    enc_salt = secrets.token_hex(16)
    users[username.lower()] = {
        "display_name": username,
        "email":        email.lower(),
        "hash":         hash_hex,
        "salt":         salt,
        "enc_salt":     enc_salt,
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


def get_user_info(username: str) -> dict:
    """Return {display_name, email} for the given username key."""
    users = _load_users()
    key   = username.strip().lower()
    rec   = users.get(key, {})
    return {
        "display_name": rec.get("display_name", username),
        "email":        rec.get("email", ""),
    }


def update_username(old_username: str, new_username: str) -> tuple:
    """Rename a user. Returns (ok, message)."""
    new_username = new_username.strip()
    if not new_username or len(new_username) < 3:
        return False, "Username must be at least 3 characters."
    users   = _load_users()
    old_key = old_username.strip().lower()
    new_key = new_username.lower()
    if old_key not in users:
        return False, "User not found."
    if new_key != old_key and new_key in users:
        return False, "Username already taken."
    rec = users.pop(old_key)
    rec["display_name"] = new_username
    users[new_key] = rec
    _save_users(users)
    return True, new_username   # return new display_name


def update_email(username: str, new_email: str) -> tuple:
    """Change email. Returns (ok, message)."""
    new_email = new_email.strip().lower()
    if not _is_valid_email(new_email):
        return False, "Please enter a valid email address."
    users = _load_users()
    key   = username.strip().lower()
    if key not in users:
        return False, "User not found."
    # Check duplicate (ignore own email)
    for k, rec in users.items():
        if k != key and rec.get("email", "").lower() == new_email:
            return False, "That email is already in use."
    users[key]["email"] = new_email
    _save_users(users)
    return True, "Email updated."


def update_password(username: str, current_pw: str, new_pw: str) -> tuple:
    """Change password after verifying current one. Returns (ok, message)."""
    if len(new_pw) < 6:
        return False, "New password must be at least 6 characters."
    ok, _ = verify_user(username, current_pw)
    if not ok:
        return False, "Current password is incorrect."
    users = _load_users()
    key   = username.strip().lower()
    hash_hex, salt = _hash_password(new_pw)
    users[key]["hash"] = hash_hex
    users[key]["salt"] = salt
    _save_users(users)
    return True, "Password updated."


# ── Encryption key derivation ─────────────────────────────────────────────────

def get_encryption_key(username: str, password: str) -> bytes | None:
    """
    Derive a 32-byte Fernet-compatible encryption key from the user's password.
    Uses a dedicated enc_salt stored alongside the password hash.
    Returns the URL-safe base64-encoded key (44 bytes), or None if user not found.
    """
    import base64 as _b64
    users = _load_users()
    key   = username.strip().lower()
    if key not in users:
        return None
    rec = users[key]

    # Create enc_salt on first call (old accounts won't have it yet)
    if "enc_salt" not in rec:
        rec["enc_salt"] = secrets.token_hex(16)
        _save_users(users)

    enc_salt = rec["enc_salt"].encode("utf-8")
    derived  = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        enc_salt,
        iterations=260_000,
        dklen=32,
    )
    # Fernet requires a URL-safe base64-encoded 32-byte key
    return _b64.urlsafe_b64encode(derived)