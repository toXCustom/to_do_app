import json
import re
import os
from datetime import datetime
from core.tasks import Task

CONFIG_FILE = "data/config.json"

# ── Per-user file paths ───────────────────────────────────────────────────────

def _safe(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name.strip().lower()) or "user"

def tasks_file(username=None):
    return f"data/tasks_{_safe(username)}.json" if username else "data/tasks.json"

def config_file(username=None):
    return f"data/config_{_safe(username)}.json" if username else CONFIG_FILE

# ── Save / load tasks ─────────────────────────────────────────────────────────

def save_tasks(manager, username=None):
    data = []
    for task in manager.tasks:
        data.append({
            "name":         task.name,
            "description":  task.description,
            "due_date":     task.due_date.strftime("%Y-%m-%d") if task.due_date else None,
            "priority":     task.priority,
            "category":     getattr(task, "category", "General"),
            "done":         task.done,
            "created_at":   getattr(task, "created_at", None),
            "completed_at": getattr(task, "completed_at", None),
        })
    with open(tasks_file(username), "w") as f:
        json.dump(data, f, indent=4)

def load_tasks(manager, username=None):
    path = tasks_file(username)
    if username and not os.path.exists(path) and os.path.exists("data/tasks.json"):
        import shutil
        shutil.copy("data/tasks.json", path)
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return
    for td in data:
        due = td.get("due_date")
        if due:
            try:
                due = datetime.strptime(due, "%Y-%m-%d").date()
            except ValueError:
                due = None
        task = Task(td["name"], td.get("description",""), due, td.get("priority","Medium"))
        task.done         = td.get("done", False)
        task.category     = td.get("category", "General")
        task.created_at   = td.get("created_at",   datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        task.completed_at = td.get("completed_at", None)
        task.update_status()
        manager.tasks.append(task)

# ── Save / load config ────────────────────────────────────────────────────────

def save_config(config, username=None):
    with open(config_file(username), "w") as f:
        json.dump(config, f, indent=4)

def load_config(username=None):
    path = config_file(username)
    if username and not os.path.exists(path) and os.path.exists("data/" + CONFIG_FILE):
        import shutil
        shutil.copy("data/" + CONFIG_FILE, path)
    try:
        with open(path, "r") as f:
            cfg = json.load(f)
        if isinstance(cfg, bool):
            return {"dark_mode": cfg, "sort_type": "due_date", "filter_type": "All"}
        return cfg
    except (FileNotFoundError, json.JSONDecodeError):
        return {"dark_mode": False, "sort_type": "due_date", "filter_type": "All"}