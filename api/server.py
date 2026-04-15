"""
api/server.py — Local REST API for My Tasks
============================================
Runs on  http://localhost:5000  by default.

Endpoints
---------
GET    /api/tasks                 List all tasks (supports ?filter=active|done|overdue)
GET    /api/tasks/<id>            Get a single task
POST   /api/tasks                 Create a task
PUT    /api/tasks/<id>            Update a task (full replace)
PATCH  /api/tasks/<id>            Partial update (only provided fields)
DELETE /api/tasks/<id>            Delete a task
PATCH  /api/tasks/<id>/done       Toggle done / mark done
GET    /api/stats                 Dashboard statistics
GET    /api/categories            List categories
GET    /health                    Health check

Authentication
--------------
Every request must include the header:
    X-API-Key: <key>

The key is generated on first start and saved to  data/api_key.txt
It is also printed to the console on startup.

All responses are JSON.
"""

import sys
import os

# Allow running from any working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import threading
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import secrets

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
API_KEY_FILE = "data/api_key.txt"

# ── API key management ────────────────────────────────────────────────────────

def load_or_create_api_key() -> str:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE) as f:
            key = f.read().strip()
        if key:
            return key
    key = secrets.token_hex(24)
    with open(API_KEY_FILE, "w") as f:
        f.write(key)
    return key

API_KEY = load_or_create_api_key()

# ── Task helpers ──────────────────────────────────────────────────────────────

def _task_id(task) -> str:
    """Use task name + created_at as a stable ID."""
    import hashlib
    raw = f"{task.name}:{task.created_at}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _task_to_dict(task) -> dict:
    return {
        "id":           _task_id(task),
        "name":         task.name,
        "description":  task.description,
        "done":         task.done,
        "due_date":     task.due_date.isoformat() if task.due_date else None,
        "priority":     task.priority,
        "category":     getattr(task, "category",    "General"),
        "recurrence":   getattr(task, "recurrence",  None),
        "attachments":  [os.path.basename(p) for p in getattr(task, "attachments", [])],
        "is_overdue":   getattr(task, "is_overdue",  False),
        "created_at":   task.created_at,
        "completed_at": getattr(task, "completed_at", None),
    }


def _find_by_id(manager, task_id: str):
    for t in manager.tasks:
        if _task_id(t) == task_id:
            return t
    return None


# ── HTTP handler ──────────────────────────────────────────────────────────────

class TaskAPIHandler(BaseHTTPRequestHandler):

    # Injected by TaskAPIServer
    manager   = None
    save_fn   = None   # callable(manager) → persists tasks
    username  = None
    enc_key   = None

    def log_message(self, fmt, *args):
        print(f"[API] {self.address_string()} {fmt % args}")

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _check_auth(self) -> bool:
        return self.headers.get("X-API-Key") == API_KEY

    def _send(self, code: int, data, headers: dict = None):
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _ok(self, data):         self._send(200, data)
    def _created(self, data):    self._send(201, data)
    def _bad(self, msg):         self._send(400, {"error": msg})
    def _unauth(self):           self._send(401, {"error": "Invalid or missing X-API-Key"})
    def _not_found(self, msg):   self._send(404, {"error": msg})
    def _error(self, msg):       self._send(500, {"error": msg})

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    # ── Router ────────────────────────────────────────────────────────────────

    def _route(self, method: str):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")
        qs     = parse_qs(parsed.query)

        # Health (no auth)
        if path == "/health":
            return self._ok({"status": "ok", "tasks": len(self.manager.tasks)})

        # All other endpoints require auth
        if not self._check_auth():
            return self._unauth()

        # GET /api/tasks
        if method == "GET" and path == "/api/tasks":
            return self._list_tasks(qs)

        # POST /api/tasks
        if method == "POST" and path == "/api/tasks":
            return self._create_task()

        # GET /api/stats
        if method == "GET" and path == "/api/stats":
            return self._stats()

        # GET /api/categories
        if method == "GET" and path == "/api/categories":
            cats = list({getattr(t, "category", "General") for t in self.manager.tasks})
            return self._ok(sorted(cats))

        # /api/tasks/<id>[/done]
        parts = path.split("/")
        if len(parts) >= 4 and parts[1] == "api" and parts[2] == "tasks":
            task_id = parts[3]
            sub     = parts[4] if len(parts) > 4 else None

            if method == "GET" and sub is None:
                return self._get_task(task_id)
            if method == "PUT" and sub is None:
                return self._update_task(task_id, partial=False)
            if method == "PATCH" and sub is None:
                return self._update_task(task_id, partial=True)
            if method == "DELETE" and sub is None:
                return self._delete_task(task_id)
            if method == "PATCH" and sub == "done":
                return self._toggle_done(task_id)

        self._send(404, {"error": f"No route for {method} {path}"})

    def do_GET(self):    self._route("GET")
    def do_POST(self):   self._route("POST")
    def do_PUT(self):    self._route("PUT")
    def do_PATCH(self):  self._route("PATCH")
    def do_DELETE(self): self._route("DELETE")

    def do_OPTIONS(self):
        # CORS preflight
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-API-Key")
        self.end_headers()

    # ── Endpoint implementations ──────────────────────────────────────────────

    def _list_tasks(self, qs: dict):
        filt  = qs.get("filter",   ["all"])[0].lower()
        cat   = qs.get("category", [None])[0]
        prio  = qs.get("priority", [None])[0]
        today = datetime.date.today()

        tasks = list(self.manager.tasks)
        if filt == "active":
            tasks = [t for t in tasks if not t.done]
        elif filt == "done":
            tasks = [t for t in tasks if t.done]
        elif filt == "overdue":
            tasks = [t for t in tasks
                     if not t.done and t.due_date and t.due_date < today]
        elif filt == "today":
            tasks = [t for t in tasks
                     if not t.done and t.due_date and t.due_date == today]

        if cat:
            tasks = [t for t in tasks if getattr(t, "category", "General").lower() == cat.lower()]
        if prio:
            tasks = [t for t in tasks if t.priority.lower() == prio.lower()]

        self._ok({
            "count": len(tasks),
            "tasks": [_task_to_dict(t) for t in tasks],
        })

    def _get_task(self, task_id: str):
        task = _find_by_id(self.manager, task_id)
        if not task:
            return self._not_found(f"Task '{task_id}' not found")
        self._ok(_task_to_dict(task))

    def _create_task(self):
        data = self._body()
        name = data.get("name", "").strip()
        if not name:
            return self._bad("'name' is required")

        due_str  = data.get("due_date")
        due_date = None
        if due_str:
            try:
                due_date = datetime.date.fromisoformat(due_str)
            except ValueError:
                return self._bad(f"Invalid due_date format: '{due_str}' — use YYYY-MM-DD")

        from core.tasks import Task
        task = Task(
            name,
            data.get("description", ""),
            due_date,
            data.get("priority", "Medium"),
        )
        task.category   = data.get("category",  "General")
        task.recurrence = data.get("recurrence", None)
        self.manager.tasks.append(task)
        self._persist()
        self._created(_task_to_dict(task))

    def _update_task(self, task_id: str, partial: bool):
        task = _find_by_id(self.manager, task_id)
        if not task:
            return self._not_found(f"Task '{task_id}' not found")

        data = self._body()
        if not partial and not data:
            return self._bad("Request body is empty")

        if "name" in data:
            v = data["name"].strip()
            if not v:
                return self._bad("'name' cannot be empty")
            task.name = v
        if "description" in data:
            task.description = data["description"]
        if "priority" in data:
            if data["priority"] not in ("High", "Medium", "Low"):
                return self._bad("'priority' must be High, Medium or Low")
            task.priority = data["priority"]
        if "category" in data:
            task.category = data["category"]
        if "recurrence" in data:
            if data["recurrence"] not in (None, "Daily", "Weekly", "Monthly"):
                return self._bad("'recurrence' must be null, Daily, Weekly or Monthly")
            task.recurrence = data["recurrence"]
        if "done" in data:
            task.done = bool(data["done"])
            if task.done and not task.completed_at:
                task.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "due_date" in data:
            if data["due_date"] is None:
                task.due_date = None
            else:
                try:
                    task.due_date = datetime.date.fromisoformat(data["due_date"])
                except ValueError:
                    return self._bad(f"Invalid due_date: use YYYY-MM-DD")
        task.update_status()
        self._persist()
        self._ok(_task_to_dict(task))

    def _delete_task(self, task_id: str):
        task = _find_by_id(self.manager, task_id)
        if not task:
            return self._not_found(f"Task '{task_id}' not found")
        self.manager.tasks.remove(task)
        self._persist()
        self._ok({"deleted": task_id, "name": task.name})

    def _toggle_done(self, task_id: str):
        task = _find_by_id(self.manager, task_id)
        if not task:
            return self._not_found(f"Task '{task_id}' not found")
        task.done = not task.done
        if task.done:
            task.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            task.completed_at = None
        task.update_status()
        self._persist()
        self._ok(_task_to_dict(task))

    def _stats(self):
        today    = datetime.date.today()
        tasks    = self.manager.tasks
        total    = len(tasks)
        done     = sum(1 for t in tasks if t.done)
        active   = total - done
        overdue  = sum(1 for t in tasks if not t.done and t.due_date and t.due_date < today)
        due_today = sum(1 for t in tasks if not t.done and t.due_date and t.due_date == today)
        week_end = today + datetime.timedelta(days=7)
        this_week = sum(1 for t in tasks if not t.done and t.due_date
                        and today <= t.due_date <= week_end)
        by_category = {}
        for t in tasks:
            cat = getattr(t, "category", "General")
            by_category[cat] = by_category.get(cat, 0) + 1
        by_priority = {"High": 0, "Medium": 0, "Low": 0}
        for t in tasks:
            by_priority[t.priority] = by_priority.get(t.priority, 0) + 1

        self._ok({
            "total":       total,
            "done":        done,
            "active":      active,
            "overdue":     overdue,
            "due_today":   due_today,
            "due_this_week": this_week,
            "completion_pct": round(done / total * 100, 1) if total else 0,
            "by_category": by_category,
            "by_priority": by_priority,
        })

    def _persist(self):
        if self.save_fn:
            try:
                self.save_fn(self.manager, self.username, self.enc_key)
            except Exception as e:
                print(f"[API] Save error: {e}")


# ── Server class ──────────────────────────────────────────────────────────────

class TaskAPIServer:
    """
    Wraps HTTPServer in a daemon thread so it doesn't block the GUI.

    Usage:
        server = TaskAPIServer(manager, save_fn, username, enc_key)
        server.start()   # non-blocking
        server.stop()
    """

    def __init__(self, manager, save_fn=None, username=None, enc_key=None,
                 host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host    = host
        self.port    = port
        self._thread = None
        self._httpd  = None

        # Inject dependencies into the handler class via a subclass
        class Handler(TaskAPIHandler):
            pass
        Handler.manager  = manager
        Handler.save_fn  = save_fn
        Handler.username = username
        Handler.enc_key  = enc_key

        self._httpd = HTTPServer((host, port), Handler)

    def start(self):
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            daemon=True,
            name="TaskAPIServer",
        )
        self._thread.start()
        print(f"[API] Server running at http://{self.host}:{self.port}")
        print(f"[API] API key: {API_KEY}")
        print(f"[API] Key file: {os.path.abspath(API_KEY_FILE)}")

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
        print("[API] Server stopped.")

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"

    @property
    def api_key(self):
        return API_KEY


# ── Standalone mode ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run the API server standalone (without the GUI).
    Loads tasks for the given username from disk.

    Usage:
        python api/server.py [username] [port]
    """
    username = sys.argv[1] if len(sys.argv) > 1 else None
    port     = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT

    from core.tasks   import TaskManager
    from core.storage import load_tasks, save_tasks

    manager = TaskManager()
    load_tasks(manager, username)
    print(f"[API] Loaded {len(manager.tasks)} tasks for user '{username or 'anonymous'}'")

    server = TaskAPIServer(
        manager   = manager,
        save_fn   = save_tasks,
        username  = username,
        enc_key   = None,   # plain JSON only in standalone mode
        port      = port,
    )
    server.start()

    print("[API] Press Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()