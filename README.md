# ✅ My Tasks

A feature-rich, privacy-first desktop task manager built with Python and Tkinter. My Tasks offers encrypted local storage, multi-user accounts, workspaces, cloud sync, a local REST API, and a polished dark/light UI — all without a server or subscription.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## ✨ Features

### Task Management
- Create, edit, and delete tasks with name, description, category, priority, and due date
- Mark tasks done with a single click on the checkbox column
- **Subtasks** — one level of nested tasks with independent priority and due dates
- **Recurring tasks** — Daily, Weekly, or Monthly recurrence with automatic next-occurrence spawning
- **File attachments** — attach images and documents (PNG, JPG, ODF, TXT, CSV) to any task
- Full **undo / redo** (up to 50 steps) via the Command pattern

### Views & Filtering
- Filter by All / Active / Completed / Overdue
- Sort by Due Date, Priority, A–Z, or Creation Date (ascending or descending)
- **Live search** with 200 ms debounce
- **Category sidebar** — colour-coded pill buttons for instant category filtering
- **Mini calendar** — click any day to filter tasks to that date; hover for task tooltips
- **Gantt Timeline** — scrollable GitHub-style bar chart with priority colours and subtask progress
- **Advanced Analytics** — KPI tiles, completion trends, category donuts, priority breakdown, heatmap, and more

### Users & Workspaces
- Multi-user login with username or email
- Passwords hashed with PBKDF2-HMAC-SHA256 (260 000 iterations)
- **Encrypted storage** — tasks encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256); key derived from password, never written to disk
- **Auto-login sessions** — optional session tokens with configurable duration (1–30 days); session key wraps the encryption key
- **Workspaces** — each user can maintain multiple independent task lists, each stored in its own encrypted file

### Import & Export
| Format | Import | Export |
|--------|--------|--------|
| CSV    | ✅     | ✅     |
| TXT    | ✅     | ✅     |
| PDF    | ✅ (`pdfplumber`) | ✅ (`reportlab`) |

### Cloud Sync
Sync your encrypted task file to any of three providers:

| Provider     | Auth          | Extra install |
|--------------|---------------|---------------|
| GitHub Gist  | Personal token | none (stdlib) |
| Google Drive | OAuth2 PKCE   | `google-auth-oauthlib google-api-python-client` |
| Dropbox      | OAuth2 PKCE   | `dropbox` |

### Local REST API
An optional HTTP server (default port 5000) exposes your tasks over a local REST API, protected by an auto-generated API key. Useful for integrations, automation, and scripting.

```
GET    /api/tasks          List all tasks (filter/category/priority query params)
GET    /api/tasks/<id>     Get a single task
POST   /api/tasks          Create a task
PUT    /api/tasks/<id>     Full update
PATCH  /api/tasks/<id>     Partial update
DELETE /api/tasks/<id>     Delete a task
PATCH  /api/tasks/<id>/done  Toggle done
GET    /api/stats          Dashboard statistics
GET    /api/categories     List categories
GET    /health             Health check (no auth required)
```

Enable it in **Settings → Local REST API** and restart the app.

### Reminders
Background reminder service checks tasks on a configurable interval and fires OS-level notifications via `plyer` (with a built-in in-app toast fallback). Configurable per-threshold: overdue, due today, due tomorrow, due within 3 days.

### System Tray
Minimise to tray on close (requires `pystray` + `Pillow`). The tray icon shows active/overdue counts and provides quick access to add tasks or quit.

---

## 📸 UI Highlights

- **Dark and light themes** — toggle with `Ctrl+T` or in Settings; all colours defined as named theme constants
- **Activity heatmap** — GitHub-style contribution grid showing task due-date density over the past ~3 months
- **Dashboard stats panel** — live totals, overdue count, completion progress bar
- Smooth hover effects, tooltip system, and animated in-app toasts
- Optional **ttkbootstrap** integration for rounded widgets and a more native appearance

---

## 🚀 Getting Started

### Requirements

- Python 3.10 or higher
- No mandatory third-party packages — the app runs with stdlib only

### Installation

```bash
git clone https://github.com/your-username/my-tasks.git
cd my-tasks
```

### Optional dependencies

Install any combination depending on the features you want:

```bash
# Modern UI theme
pip install ttkbootstrap

# Encrypted storage (strongly recommended)
pip install cryptography

# OS notifications
pip install plyer

# System tray icon
pip install pystray Pillow

# PDF export
pip install reportlab

# PDF import
pip install pdfplumber

# Google Drive sync
pip install google-auth-oauthlib google-api-python-client

# Dropbox sync
pip install dropbox

# All optional dependencies at once
pip install ttkbootstrap cryptography plyer pystray Pillow reportlab pdfplumber
```

### Run

```bash
python main.py
```

On first launch you will be asked to create an account. Your tasks are saved to the `data/` directory.

---

## 📁 Project Structure

```
my-tasks/
├── main.py                 # Entry point
├── core/
│   ├── tasks.py            # Task and TaskManager models
│   ├── storage.py          # Encrypted save/load, config persistence
│   ├── logic.py            # Pure business logic (filter, sort, days_info)
│   ├── auth.py             # User registration, login, sessions, key derivation
│   ├── commands.py         # Command pattern for undo/redo
│   ├── workspaces.py       # Workspace CRUD and file routing
│   └── categories.py       # Category palette and colour helpers
├── gui/
│   ├── app.py              # Main application window (TodoApp)
│   ├── login.py            # Login / register dialog
│   ├── theme.py            # ttkbootstrap integration helpers
│   └── ttkbs_compat.py     # Frame.__init__ capture before ttkbootstrap patches
├── api/
│   └── server.py           # Local REST API (HTTPServer, no Flask required)
├── services/
│   ├── export.py           # CSV / TXT / PDF export
│   ├── importer.py         # CSV / TXT / PDF import
│   ├── share.py            # File sharing helpers (email, WhatsApp, Telegram…)
│   ├── cloud_sync.py       # GitHub Gist / Google Drive / Dropbox providers
│   └── reminders.py        # Background reminder service + in-app toast
├── test_todo.py            # Unit test suite (unittest, no tkinter required)
└── data/                   # Runtime data (created automatically)
    ├── tasks_<user>.enc    # Encrypted task files
    ├── config_<user>.json  # Per-user UI preferences
    ├── workspaces_<user>.json
    ├── users.json
    ├── session.json
    └── api_key.txt
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New task |
| `Ctrl+E` | Edit selected task |
| `Delete` | Delete selected task |
| `Ctrl+D` | Mark selected task done |
| `Double-click` | Edit task |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Redo |
| `Ctrl+F` | Focus search |
| `Escape` | Clear search / filters |
| `Ctrl+Home` / `Ctrl+End` | Select first / last task |
| `Ctrl+T` | Toggle dark / light mode |
| `Ctrl+,` | Open Settings |
| `?` | Show shortcuts help |

---

## 🧪 Running Tests

The test suite covers task creation, filtering, sorting, storage round-trips, and edge cases. It requires no GUI and no optional dependencies.

```bash
python -m pytest test_todo.py -v
# or
python test_todo.py
```

---

## 🔒 Security Notes

- Passwords are never stored in plaintext. PBKDF2-HMAC-SHA256 with 260 000 iterations and a random per-user salt is used.
- The task encryption key is derived from the password using a separate salt (`enc_salt`) and is held only in memory during the session.
- Auto-login session tokens wrap the encryption key using a second Fernet layer keyed from the session token itself — the raw key is never written to disk unprotected.
- The local REST API key is a random 48-character hex string stored in `data/api_key.txt`.
- Cloud sync uploads the already-encrypted task file; your password is never sent to any cloud provider.

---

## 🛣️ Roadmap

- [ ] Mobile companion app
- [ ] CalDAV / iCal integration
- [ ] Task sharing between users
- [ ] Natural language task input
- [ ] Plugin / extension system

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change. Make sure to run the test suite before submitting.

---

## 📄 License

[MIT](LICENSE)
