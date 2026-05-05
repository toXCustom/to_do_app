"""
core/workspaces.py — Workspace management for My Tasks
=======================================================
A workspace is a named task list owned by a user.
Each workspace maps to its own tasks file:
    data/tasks_<user>_<workspace>.enc  (or .json)

The Default workspace uses the existing file naming (no suffix).

Workspace metadata is stored in:
    data/workspaces_<user>.json
Schema:
    {
        "active": "Work",
        "workspaces": [
            {"name": "Default", "description": "Personal tasks", "color": "#E07A47"},
            {"name": "Work",    "description": "Work projects",  "color": "#4A9EE0"},
        ]
    }
"""

import json
import os
import re

_DEFAULT_COLOR = "#E07A47"


def _safe(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name.strip().lower()) or "user"


def _wfile(username: str) -> str:
    return f"data/workspaces_{_safe(username)}.json"


# ── Load / save ───────────────────────────────────────────────────────────────

def load_workspaces(username: str) -> dict:
    """
    Return workspace metadata for a user.
    Creates defaults if the file doesn't exist.
    """
    path = _wfile(username)
    try:
        with open(path) as f:
            data = json.load(f)
        # Ensure Default always exists
        names = [w["name"] for w in data.get("workspaces", [])]
        if "Default" not in names:
            data["workspaces"].insert(0, _default_ws())
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "active":     "Default",
            "workspaces": [_default_ws()],
        }


def save_workspaces(username: str, data: dict):
    os.makedirs("data", exist_ok=True)
    with open(_wfile(username), "w") as f:
        json.dump(data, f, indent=2)


def _default_ws() -> dict:
    return {"name": "Default", "description": "My personal tasks",
            "color": "#E07A47"}


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_workspaces(username: str) -> list:
    """Return list of workspace dicts [{name, description, color}]."""
    return load_workspaces(username)["workspaces"]


def active_workspace(username: str) -> str:
    """Return the name of the currently active workspace."""
    return load_workspaces(username).get("active", "Default")


def set_active_workspace(username: str, name: str):
    data = load_workspaces(username)
    names = [w["name"] for w in data["workspaces"]]
    if name not in names:
        raise ValueError(f"Workspace '{name}' does not exist.")
    data["active"] = name
    save_workspaces(username, data)


def create_workspace(username: str, name: str,
                     description: str = "", color: str = _DEFAULT_COLOR) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Workspace name cannot be empty.")
    if len(name) > 32:
        raise ValueError("Workspace name must be 32 characters or fewer.")
    data  = load_workspaces(username)
    names = [w["name"] for w in data["workspaces"]]
    if name in names:
        raise ValueError(f"Workspace '{name}' already exists.")
    ws = {"name": name, "description": description, "color": color}
    data["workspaces"].append(ws)
    save_workspaces(username, data)
    return ws


def update_workspace(username: str, old_name: str,
                     new_name: str = None, description: str = None,
                     color: str = None):
    data = load_workspaces(username)
    for ws in data["workspaces"]:
        if ws["name"] == old_name:
            if new_name and new_name != old_name:
                if old_name == "Default":
                    raise ValueError("Cannot rename the Default workspace.")
                ws["name"] = new_name.strip()
                if data["active"] == old_name:
                    data["active"] = new_name.strip()
            if description is not None:
                ws["description"] = description
            if color is not None:
                ws["color"] = color
            save_workspaces(username, data)
            return ws
    raise ValueError(f"Workspace '{old_name}' not found.")


def delete_workspace(username: str, name: str):
    if name == "Default":
        raise ValueError("Cannot delete the Default workspace.")
    data  = load_workspaces(username)
    before = len(data["workspaces"])
    data["workspaces"] = [w for w in data["workspaces"] if w["name"] != name]
    if len(data["workspaces"]) == before:
        raise ValueError(f"Workspace '{name}' not found.")
    if data.get("active") == name:
        data["active"] = "Default"
    save_workspaces(username, data)

    # Optionally delete the task file too
    from core.storage import tasks_file
    for enc in (True, False):
        path = tasks_file(username, encrypted=enc, workspace=name)
        if os.path.exists(path):
            os.remove(path)