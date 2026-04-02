"""
storage.py — Encrypted task persistence for My Tasks.

Task files are encrypted with Fernet (AES-128-CBC + HMAC-SHA256).
The encryption key is derived from the user's password at login and
kept in memory for the session — it is never written to disk.

Config files stay as plain JSON (they contain only UI preferences,
no sensitive data).

File format (tasks):
    Encrypted  → binary Fernet token written to  tasks_<user>.enc
    Plain JSON → tasks_<user>.json  (legacy / no-auth mode)

Migration: on first encrypted save, the legacy .json file is removed.
"""

import json
import re
import os
from datetime import datetime
from core.tasks import Task

CONFIG_FILE = "data/config.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name.strip().lower()) or "user"


def tasks_file(username=None, encrypted=False) -> str:
    if username:
        ext = ".enc" if encrypted else ".json"
        return f"data/tasks_{_safe(username)}{ext}"
    return "data/tasks.json"


def config_file(username=None) -> str:
    return f"data/config_{_safe(username)}.json" if username else CONFIG_FILE


# ── Encryption helpers ────────────────────────────────────────────────────────

def _fernet(enc_key: bytes):
    """Return a Fernet instance from a 44-byte URL-safe base64 key."""
    try:
        from cryptography.fernet import Fernet
        return Fernet(enc_key)
    except ImportError:
        raise RuntimeError(
            "The 'cryptography' package is required for encrypted storage.\n"
            "Install it with:  pip install cryptography"
        )


def _encrypt(data: bytes, enc_key: bytes) -> bytes:
    return _fernet(enc_key).encrypt(data)


def _decrypt(token: bytes, enc_key: bytes) -> bytes:
    from cryptography.fernet import InvalidToken
    try:
        return _fernet(enc_key).decrypt(token)
    except InvalidToken:
        raise ValueError(
            "Could not decrypt task file — wrong password or corrupted file."
        )


# ── Save / load tasks ─────────────────────────────────────────────────────────

def save_tasks(manager, username=None, enc_key: bytes | None = None):
    """
    Serialize tasks to JSON and, if enc_key is provided, encrypt the result.
    Writes to  data/tasks_<user>.enc  (encrypted) or  .json  (plain).
    """
    data = []
    for task in manager.tasks:
        data.append({
            "name":         task.name,
            "description":  task.description,
            "due_date":     task.due_date.strftime("%Y-%m-%d") if task.due_date else None,
            "priority":     task.priority,
            "category":     getattr(task, "category", "General"),
            "done":         task.done,
            "created_at":   getattr(task, "created_at",   None),
            "completed_at": getattr(task, "completed_at", None),
        })

    raw = json.dumps(data, indent=4).encode("utf-8")

    if enc_key and username:
        path = tasks_file(username, encrypted=True)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(_encrypt(raw, enc_key))
        # Remove legacy plain file if it exists
        plain = tasks_file(username, encrypted=False)
        if os.path.exists(plain):
            os.remove(plain)
    else:
        path = tasks_file(username, encrypted=False)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw.decode("utf-8"))


def load_tasks(manager, username=None, enc_key: bytes | None = None):
    """
    Load tasks. Tries encrypted file first, then plain JSON fallback.
    """
    enc_path   = tasks_file(username, encrypted=True)  if username else None
    plain_path = tasks_file(username, encrypted=False)

    # ── 1. Encrypted file ─────────────────────────────
    if enc_key and enc_path and os.path.exists(enc_path):
        with open(enc_path, "rb") as f:
            token = f.read()
        raw = _decrypt(token, enc_key)
        _populate(manager, json.loads(raw.decode("utf-8")))
        return

    # ── 2. Legacy plain JSON (migration) ──────────────
    # Check for anonymous tasks.json migration
    if username and not os.path.exists(plain_path) and os.path.exists("data/tasks.json"):
        import shutil
        shutil.copy("data/tasks.json", plain_path)

    if os.path.exists(plain_path):
        try:
            with open(plain_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _populate(manager, data)
        except (json.JSONDecodeError, KeyError):
            pass
        return

    # Nothing to load — fresh user


def _populate(manager, data: list):
    """Parse a list of task dicts into manager.tasks."""
    for td in data:
        due = td.get("due_date")
        if due:
            try:
                due = datetime.strptime(due, "%Y-%m-%d").date()
            except ValueError:
                due = None
        task = Task(
            td["name"],
            td.get("description", ""),
            due,
            td.get("priority", "Medium"),
        )
        task.done         = td.get("done", False)
        task.category     = td.get("category", "General")
        task.recurrence   = td.get("recurrence", None)
        task.created_at   = td.get("created_at",   datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        task.completed_at = td.get("completed_at", None)
        task.update_status()
        manager.tasks.append(task)


# ── Save / load config (always plain JSON) ────────────────────────────────────

def save_config(config, username=None):
    path = config_file(username)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def load_config(username=None) -> dict:
    path = config_file(username)
    # Migrate legacy config
    if username and not os.path.exists(path) and os.path.exists(CONFIG_FILE):
        import shutil
        shutil.copy(CONFIG_FILE, path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, bool):
            return {"dark_mode": cfg, "sort_type": "due_date", "filter_type": "All"}
        return cfg
    except (FileNotFoundError, json.JSONDecodeError):
        return {"dark_mode": False, "sort_type": "due_date", "filter_type": "All"}