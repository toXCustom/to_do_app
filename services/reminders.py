"""
reminders.py — Task reminder service
=====================================
ReminderService runs a background daemon thread that checks tasks every minute
and fires OS-level notifications (via plyer if installed) or falls back to an
in-app Tkinter toast shown in the bottom-right corner.

Usage:
    svc = ReminderService(root_widget, get_tasks_fn, config)
    svc.start()
    svc.update_config(new_config)   # call when settings change
    svc.stop()
"""

import threading
import time
from datetime import date, timedelta

# ── Optional OS notification backend ─────────────────────────────────────────
try:
    from plyer import notification as _plyer_notify
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "reminders_enabled": True,
    "remind_overdue":    True,      # notify for overdue tasks
    "remind_today":      True,      # notify for tasks due today
    "remind_tomorrow":   False,     # notify for tasks due tomorrow
    "remind_3days":      False,     # notify for tasks due within 3 days
    "check_interval":    60,        # seconds between checks
}

APP_NAME  = "My Tasks"
APP_ICON  = None   # set to .ico path if you have one


class ReminderService:
    def __init__(self, root, get_tasks_fn, config: dict):
        self.root        = root
        self.get_tasks   = get_tasks_fn   # callable → list[Task]
        self.cfg         = {**DEFAULT_CONFIG, **config}
        self._stop_evt   = threading.Event()
        self._thread     = None
        self._fired: set = set()   # task ids already notified this session
        self._toast_win  = None    # current in-app toast window

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ReminderThread")
        self._thread.start()

    def stop(self):
        self._stop_evt.set()

    def update_config(self, config: dict):
        self.cfg = {**DEFAULT_CONFIG, **config}

    def reset_fired(self):
        """Call when tasks are added/edited so reminders re-evaluate."""
        self._fired.clear()

    # ── Background loop ───────────────────────────────────────────────────────

    def _loop(self):
        # Initial delay so app finishes drawing before first check
        time.sleep(5)
        while not self._stop_evt.is_set():
            if self.cfg.get("reminders_enabled", True):
                try:
                    self._check()
                except Exception:
                    pass
            self._stop_evt.wait(self.cfg.get("check_interval", 60))

    def _check(self):
        today    = date.today()
        tomorrow = today + timedelta(days=1)
        in3days  = today + timedelta(days=3)
        tasks    = self.get_tasks()

        for task in tasks:
            if task.done:
                continue
            uid = id(task)
            if uid in self._fired:
                continue

            due = task.due_date
            fire = False
            urgency = "normal"

            if due is None:
                continue
            if due < today and self.cfg.get("remind_overdue", True):
                fire    = True
                urgency = "critical"
            elif due == today and self.cfg.get("remind_today", True):
                fire    = True
                urgency = "normal"
            elif due == tomorrow and self.cfg.get("remind_tomorrow", False):
                fire    = True
                urgency = "normal"
            elif today < due <= in3days and self.cfg.get("remind_3days", False):
                fire    = True
                urgency = "low"

            if fire:
                self._fired.add(uid)
                self.root.after(0, lambda t=task, u=urgency: self._notify(t, u))

    # ── Notification dispatch ─────────────────────────────────────────────────

    def _notify(self, task, urgency: str):
        due   = task.due_date
        today = date.today()

        if due < today:
            delta = (today - due).days
            title = f"⚠️ Overdue: {task.name}"
            msg   = f"{delta} day{'s' if delta != 1 else ''} overdue  •  {task.priority} priority"
        elif due == today:
            title = f"📅 Due today: {task.name}"
            msg   = f"Due today  •  {task.priority} priority  •  {task.category}"
        else:
            delta = (due - today).days
            title = f"🔔 Upcoming: {task.name}"
            msg   = f"Due in {delta} day{'s' if delta != 1 else ''}  •  {task.priority} priority"

        sent = False
        if PLYER_AVAILABLE:
            try:
                _plyer_notify.notify(
                    title=title,
                    message=msg,
                    app_name=APP_NAME,
                    app_icon=APP_ICON or "",
                    timeout=8,
                )
                sent = True
            except Exception:
                pass

        if not sent:
            self._show_toast(title, msg, urgency)

    # ── In-app toast (plyer fallback) ─────────────────────────────────────────

    def _show_toast(self, title: str, message: str, urgency: str = "normal"):
        """Show a non-blocking, auto-dismissing toast at bottom-right."""
        if self._toast_win and self._toast_win.winfo_exists():
            try:
                self._toast_win.destroy()
            except Exception:
                pass

        toast = self._toast_win = _InAppToast(self.root, title, message, urgency)
        toast.show()


# ── In-app toast widget ───────────────────────────────────────────────────────

class _InAppToast:
    DURATION_MS = 5000
    WIDTH       = 320
    HEIGHT      = 80

    COLORS = {
        "critical": {"bg": "#7F1D1D", "border": "#EF4444", "fg": "#FEE2E2"},
        "normal":   {"bg": "#1C3557", "border": "#3B82F6", "fg": "#DBEAFE"},
        "low":      {"bg": "#1A2E1A", "border": "#4ADE80", "fg": "#DCFCE7"},
    }

    def __init__(self, root, title: str, message: str, urgency: str):
        import tkinter as tk
        self.root    = root
        self.title   = title
        self.message = message
        self.colors  = self.COLORS.get(urgency, self.COLORS["normal"])
        self._win    = None
        self._tk     = tk

    def show(self):
        tk    = self._tk
        c     = self.colors
        root  = self.root

        win = self._win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=c["border"])

        inner = tk.Frame(win, bg=c["bg"], padx=14, pady=10)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Label(inner, text=self.title,
                 bg=c["bg"], fg=c["fg"],
                 font=("TkDefaultFont", 10, "bold"),
                 wraplength=self.WIDTH - 30,
                 anchor="w", justify="left").pack(fill=tk.X)
        tk.Label(inner, text=self.message,
                 bg=c["bg"], fg=c["fg"],
                 font=("TkDefaultFont", 9),
                 wraplength=self.WIDTH - 30,
                 anchor="w", justify="left").pack(fill=tk.X)

        # Position: bottom-right of screen
        win.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x  = sw - self.WIDTH  - 18
        y  = sh - self.HEIGHT - 60
        win.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        # Click to dismiss
        for w in [win, inner] + inner.winfo_children():
            try:
                w.bind("<Button-1>", lambda e: self._dismiss())
            except Exception:
                pass

        # Auto-dismiss
        win.after(self.DURATION_MS, self._dismiss)

        # Slide-in animation (fade in via alpha)
        self._fade_in(win, 0.0)

    def _fade_in(self, win, alpha):
        try:
            alpha = min(alpha + 0.12, 1.0)
            win.attributes("-alpha", alpha)
            if alpha < 1.0:
                win.after(20, lambda: self._fade_in(win, alpha))
        except Exception:
            pass

    def _dismiss(self):
        try:
            if self._win and self._win.winfo_exists():
                self._win.destroy()
        except Exception:
            pass