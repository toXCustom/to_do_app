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

Performance notes:
  - Fernet instance is cached per key to avoid re-creation overhead
  - Encrypted data skips indent=4 (saves ~30% serialisation time)
  - _populate uses a single list.extend instead of repeated appends
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


def tasks_file(username=None, encrypted=False, workspace=None) -> str:
    if username:
        ext  = ".enc" if encrypted else ".json"
        ws   = f"_{_safe(workspace)}" if workspace and workspace != "Default" else ""
        return f"data/tasks_{_safe(username)}{ws}{ext}"
    return "data/tasks.json"


def config_file(username=None) -> str:
    return f"data/config_{_safe(username)}.json" if username else CONFIG_FILE


def workspaces_file(username=None) -> str:
    """Per-user workspace list file."""
    if username:
        return f"data/workspaces_{_safe(username)}.json"
    return "data/workspaces.json"


def attachments_dir(username=None, workspace=None) -> str:
    """Return the folder where attachments are stored for this user/workspace."""
    ws   = f"_{_safe(workspace)}" if workspace and workspace != "Default" else ""
    base = f"data/attachments/{_safe(username)}{ws}" if username else "data/attachments/default"
    os.makedirs(base, exist_ok=True)
    return base


# ── Encryption helpers ────────────────────────────────────────────────────────

# Cache Fernet instances per key — avoids re-creating on every save/load cycle
_fernet_cache = {}

def _fernet(enc_key: bytes):
    """Return a cached Fernet instance from a 44-byte URL-safe base64 key."""
    if enc_key in _fernet_cache:
        return _fernet_cache[enc_key]
    try:
        from cryptography.fernet import Fernet
        f = Fernet(enc_key)
        _fernet_cache[enc_key] = f
        return f
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

def save_tasks(manager, username=None, enc_key=None, workspace=None):
    """Serialize tasks. workspace scopes the file path."""
    data = [task.to_dict() for task in manager.tasks]
    # Skip indent for encrypted data (never human-read, saves ~30% time)
    indent = None if (enc_key and username) else 4
    raw  = json.dumps(data, indent=indent, separators=(',', ':') if indent is None else None).encode("utf-8")

    if enc_key and username:
        path = tasks_file(username, encrypted=True, workspace=workspace)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(_encrypt(raw, enc_key))
        plain = tasks_file(username, encrypted=False, workspace=workspace)
        if os.path.exists(plain):
            os.remove(plain)
    else:
        if username and os.path.exists(tasks_file(username, encrypted=True, workspace=workspace)):
            return
        path = tasks_file(username, encrypted=False, workspace=workspace)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw.decode("utf-8"))


def load_tasks(manager, username=None, enc_key=None, workspace=None):
    """Load tasks. workspace scopes the file path."""
    enc_path   = tasks_file(username, encrypted=True,  workspace=workspace) if username else None
    plain_path = tasks_file(username, encrypted=False, workspace=workspace)

    if enc_path and os.path.exists(enc_path):
        if not enc_key:
            print(f"[storage] WARNING: {enc_path} exists but no enc_key provided.")
            return
        with open(enc_path, "rb") as f:
            token = f.read()
        raw = _decrypt(token, enc_key)
        _populate(manager, json.loads(raw.decode("utf-8")))
        return

    if username and not os.path.exists(plain_path) and workspace is None:
        legacy = f"data/tasks.json"
        if os.path.exists(legacy):
            import shutil
            shutil.copy(legacy, plain_path)

    if os.path.exists(plain_path):
        try:
            with open(plain_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _populate(manager, data)
        except (json.JSONDecodeError, KeyError):
            pass


def _populate(manager, data: list):
    """Parse a list of task dicts into manager.tasks — optimised bulk load."""
    from datetime import datetime as _dt
    _now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")

    tasks = []
    for td in data:
        task = Task.from_dict(td)
        # Backfill missing created_at without calling datetime.now() per task
        if not task.created_at:
            task.created_at = _now_str
        tasks.append(task)

    manager.tasks.extend(tasks)   # single list extend vs repeated append


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