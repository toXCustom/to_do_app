"""
login.py — Login / Register window for My Tasks.
Call LoginWindow(root).run() → returns display_name string or None if cancelled.
"""

import json
import os
import tkinter as tk
from core.auth import (verify_user, register_user, get_encryption_key,
                       _find_by_login, _load_users,
                       create_session, revoke_session)

_REMEMBER_FILE = "data/remember.json"

_DARK = {
    "bg":        "#13151A",
    "fg":        "#EDE9E3",
    "muted_fg":  "#8A8E99",
    "accent":    "#E07A47",
    "acc_hover": "#C86832",
    "acc_fg":    "#FFFFFF",
    "surface":   "#1C1F26",
    "surface2":  "#22262F",
    "border":    "#2E3340",
    "entry_bg":  "#22262F",
    "error":     "#F87171",
    "success":   "#4ADE80",
    "check_bg":  "#22262F",
}
_LIGHT = {
    "bg":        "#FAF7F2",
    "fg":        "#1C1917",
    "muted_fg":  "#78716C",
    "accent":    "#C2622D",
    "acc_hover": "#A85226",
    "acc_fg":    "#FFFFFF",
    "surface":   "#F2EDE6",
    "surface2":  "#FFFFFF",
    "border":    "#E0D9CF",
    "entry_bg":  "#FFFFFF",
    "error":     "#DC2626",
    "success":   "#16A34A",
    "check_bg":  "#F2EDE6",
}


# ── Remember-me helpers ───────────────────────────────────────────────────────

def _load_remembered() -> dict:
    """Return {identifier, remember} or empty dict."""
    try:
        with open(_REMEMBER_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_remembered(identifier: str):
    os.makedirs(os.path.dirname(_REMEMBER_FILE), exist_ok=True)
    with open(_REMEMBER_FILE, "w") as f:
        json.dump({"identifier": identifier}, f)


def _clear_remembered():
    try:
        os.remove(_REMEMBER_FILE)
    except FileNotFoundError:
        pass


# ── Login window ──────────────────────────────────────────────────────────────

class LoginWindow:
    W, H = 380, 520

    def __init__(self, root: tk.Tk, dark_mode: bool = True):
        self.root      = root
        self.dark_mode = dark_mode
        self.result    = None
        self._mode     = "login"
        self._remembered = _load_remembered()

        self.top = tk.Toplevel(root)
        self.top.title("My Tasks — Sign in")
        self.top.resizable(False, False)
        self.top.protocol("WM_DELETE_WINDOW", self._on_close)

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        self.top.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")

        self._build()
        self.top.grab_set()
        self.top.focus_force()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        t = _DARK if self.dark_mode else _LIGHT
        self.top.configure(bg=t["bg"])

        # Header
        header = tk.Frame(self.top, bg=t["surface"], height=110)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="✅", font=("TkDefaultFont", 32),
                 bg=t["surface"], fg=t["accent"]).pack(pady=(18, 2))
        tk.Label(header, text="My Tasks", font=("TkDefaultFont", 16, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack()

        # Form area
        self.form_frame = tk.Frame(self.top, bg=t["bg"])
        self.form_frame.pack(fill=tk.BOTH, expand=True, padx=36, pady=12)

        self._build_login_form(t)

        # Theme toggle
        bar = tk.Frame(self.top, bg=t["bg"])
        bar.pack(fill=tk.X, padx=12, pady=(0, 8))
        tk.Button(bar,
                  text="☀  Light" if self.dark_mode else "🌙  Dark",
                  font=("TkDefaultFont", 8),
                  bg=t["bg"], fg=t["muted_fg"],
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self._toggle_theme).pack(side=tk.RIGHT)

    def _build_login_form(self, t):
        self._clear_form()

        tk.Label(self.form_frame, text="Sign in",
                 font=("TkDefaultFont", 13, "bold"),
                 bg=t["bg"], fg=t["fg"]).pack(anchor="w", pady=(0, 14))

        # Username or Email
        tk.Label(self.form_frame, text="Username or Email",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
        self.login_var = tk.StringVar()
        self._login_entry = self._entry(self.form_frame, self.login_var, t)
        self._login_entry.pack(fill=tk.X, pady=(3, 10))

        # Password
        tk.Label(self.form_frame, text="Password",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
        self.password_var = tk.StringVar()
        self._pw_entry = self._entry(self.form_frame, self.password_var, t, show="●")
        self._pw_entry.pack(fill=tk.X, pady=(3, 0))

        # Show / hide password
        self._show_pw = False
        self._eye_btn = tk.Button(self.form_frame, text="Show",
                                  font=("TkDefaultFont", 8),
                                  bg=t["bg"], fg=t["muted_fg"],
                                  relief=tk.FLAT, cursor="hand2", bd=0,
                                  command=self._toggle_show_pw)
        self._eye_btn.pack(anchor="e", pady=(2, 6))

        # ── Remember me ───────────────────────────────
        remember_row = tk.Frame(self.form_frame, bg=t["bg"])
        remember_row.pack(anchor="w", pady=(0, 8))

        self._remember_var = tk.BooleanVar(value=bool(self._remembered))
        cb = tk.Checkbutton(
            remember_row,
            variable=self._remember_var,
            text="Remember me",
            font=("TkDefaultFont", 9),
            bg=t["bg"], fg=t["muted_fg"],
            selectcolor=t["check_bg"],
            activebackground=t["bg"],
            activeforeground=t["fg"],
            cursor="hand2",
            relief=tk.FLAT, bd=0,
        )
        cb.pack(side=tk.LEFT)

        # Session duration dropdown
        self._session_days = 7
        _dur_options = {"1 day": 1, "3 days": 3, "7 days": 7, "14 days": 14, "30 days": 30}
        _dur_var = tk.StringVar(value="7 days")
        def _on_dur_change(*_):
            self._session_days = _dur_options.get(_dur_var.get(), 7)
        _dur_var.trace_add("write", _on_dur_change)
        dur_menu = tk.OptionMenu(remember_row, _dur_var, *_dur_options.keys())
        dur_menu.configure(
            bg=t["bg"], fg=t["muted_fg"],
            activebackground=t["border"],
            highlightthickness=0,
            relief=tk.FLAT, bd=0,
            font=("TkDefaultFont", 8),
        )
        dur_menu.pack(side=tk.LEFT, padx=(4, 0))

        # ── Error message ─────────────────────────────
        self.msg_var = tk.StringVar()
        tk.Label(self.form_frame, textvariable=self.msg_var,
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["error"],
                 wraplength=300, justify="left").pack(anchor="w", pady=(0, 8))

        self._accent_btn(self.form_frame, "Sign in", self._do_login, t).pack(
            fill=tk.X, ipady=6, pady=(0, 14))

        # Separator
        sep = tk.Frame(self.form_frame, bg=t["bg"])
        sep.pack(fill=tk.X, pady=(0, 10))
        tk.Frame(sep, bg=t["border"], height=1).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=6)
        tk.Label(sep, text="or", bg=t["bg"], fg=t["muted_fg"],
                 font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
        tk.Frame(sep, bg=t["border"], height=1).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0), pady=6)

        tk.Button(self.form_frame, text="Create a new account",
                  font=("TkDefaultFont", 9, "underline"),
                  bg=t["bg"], fg=t["accent"],
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self._switch_to_register).pack()

        # Pre-fill remembered identifier
        if self._remembered.get("identifier"):
            self.login_var.set(self._remembered["identifier"])
            self._pw_entry.focus_set()
        else:
            self._login_entry.focus_set()

        self.top.bind("<Return>", lambda e: self._do_login())

    def _build_register_form(self, t):
        self._clear_form()

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.top.geometry(f"{self.W}x640+{(sw-self.W)//2}+{(sh-640)//2}")

        tk.Label(self.form_frame, text="Create account",
                 font=("TkDefaultFont", 13, "bold"),
                 bg=t["bg"], fg=t["fg"]).pack(anchor="w", pady=(0, 10))

        # ── Username ──────────────────────────────────
        tk.Label(self.form_frame, text="Username",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
        self.username_var = tk.StringVar()
        self._username_entry = self._entry(self.form_frame, self.username_var, t)
        self._username_entry.pack(fill=tk.X, pady=(3, 2))
        uname_hint = tk.Label(self.form_frame, text="",
                              font=("TkDefaultFont", 8),
                              bg=t["bg"], fg=t["muted_fg"],
                              anchor="w", justify="left")
        uname_hint.pack(fill=tk.X, pady=(0, 6))

        def _check_username(*_):
            v = self.username_var.get()
            import re as _re
            if not v:
                uname_hint.config(text="", fg=t["muted_fg"])
            elif len(v) < 3:
                uname_hint.config(text="✗  At least 3 characters", fg="#F87171")
            elif not _re.match(r"^[a-zA-Z0-9_\-]+$", v):
                uname_hint.config(text="✗  Letters, numbers, _ and - only", fg="#F87171")
            elif len(v) > 32:
                uname_hint.config(text="✗  Maximum 32 characters", fg="#F87171")
            else:
                uname_hint.config(text="✓  Looks good", fg="#4ADE80")

        self.username_var.trace_add("write", _check_username)

        # ── Email ─────────────────────────────────────
        tk.Label(self.form_frame, text="Email address",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
        self.email_var = tk.StringVar()
        self._entry(self.form_frame, self.email_var, t).pack(fill=tk.X, pady=(3, 2))
        email_hint = tk.Label(self.form_frame, text="",
                              font=("TkDefaultFont", 8),
                              bg=t["bg"], fg=t["muted_fg"])
        email_hint.pack(anchor="w", pady=(0, 6))

        def _check_email(*_):
            import re as _re
            v = self.email_var.get().strip()
            if not v:
                email_hint.config(text="")
            elif _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
                email_hint.config(text="✓  Valid email", fg="#4ADE80")
            else:
                email_hint.config(text="✗  Enter a valid email address", fg="#F87171")

        self.email_var.trace_add("write", _check_email)

        # ── Password ──────────────────────────────────
        tk.Label(self.form_frame, text="Password",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
        self.password_var = tk.StringVar()
        self._entry(self.form_frame, self.password_var, t, show="●").pack(
            fill=tk.X, pady=(3, 4))

        # Strength bar (5 segments)
        bar_frame = tk.Frame(self.form_frame, bg=t["bg"])
        bar_frame.pack(fill=tk.X, pady=(0, 2))
        _segs = []
        for _ in range(5):
            s = tk.Frame(bar_frame, height=4, bg=t["border"])
            s.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
            _segs.append(s)
        strength_lbl = tk.Label(self.form_frame, text="",
                                font=("TkDefaultFont", 8),
                                bg=t["bg"], fg=t["muted_fg"])
        strength_lbl.pack(anchor="w", pady=(0, 6))

        def _pw_strength(pw: str) -> int:
            """Return score 0-5."""
            import re as _re
            score = 0
            if len(pw) >= 8:  score += 1
            if len(pw) >= 12: score += 1
            if _re.search(r"[A-Z]", pw): score += 1
            if _re.search(r"[0-9]", pw): score += 1
            if _re.search(r"[^a-zA-Z0-9]", pw): score += 1
            return score

        _STRENGTH_COLORS = ["#F87171", "#FB923C", "#FACC15", "#86EFAC", "#4ADE80"]
        _STRENGTH_LABELS = ["Very weak", "Weak", "Fair", "Strong", "Very strong"]

        def _check_password(*_):
            pw    = self.password_var.get()
            score = _pw_strength(pw) if pw else 0
            for i, seg in enumerate(_segs):
                if pw and i < score:
                    seg.config(bg=_STRENGTH_COLORS[min(score - 1, 4)])
                else:
                    seg.config(bg=t["border"])
            if pw:
                strength_lbl.config(
                    text=_STRENGTH_LABELS[min(score - 1, 4)] if score > 0 else "Too short",
                    fg=_STRENGTH_COLORS[min(score - 1, 4)] if score > 0 else "#F87171"
                )
            else:
                strength_lbl.config(text="")
            _check_confirm()

        self.password_var.trace_add("write", _check_password)

        # ── Confirm password ──────────────────────────
        tk.Label(self.form_frame, text="Confirm password",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
        self.confirm_var = tk.StringVar()
        self._entry(self.form_frame, self.confirm_var, t, show="●").pack(
            fill=tk.X, pady=(3, 2))
        confirm_hint = tk.Label(self.form_frame, text="",
                                font=("TkDefaultFont", 8),
                                bg=t["bg"], fg=t["muted_fg"])
        confirm_hint.pack(anchor="w", pady=(0, 6))

        def _check_confirm(*_):
            pw = self.password_var.get()
            cf = self.confirm_var.get()
            if not cf:
                confirm_hint.config(text="")
            elif pw == cf:
                confirm_hint.config(text="✓  Passwords match", fg="#4ADE80")
            else:
                confirm_hint.config(text="✗  Passwords do not match", fg="#F87171")

        self.confirm_var.trace_add("write", _check_confirm)

        # ── Error / submit ────────────────────────────
        self.msg_var = tk.StringVar()
        tk.Label(self.form_frame, textvariable=self.msg_var,
                 font=("TkDefaultFont", 9), bg=t["bg"], fg="#F87171",
                 wraplength=300, justify="left").pack(anchor="w", pady=(0, 6))

        self._accent_btn(self.form_frame, "Create account", self._do_register, t).pack(
            fill=tk.X, ipady=6, pady=(0, 10))

        tk.Button(self.form_frame, text="← Back to sign in",
                  font=("TkDefaultFont", 9, "underline"),
                  bg=t["bg"], fg=t["accent"],
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self._switch_to_login).pack()

        self.top.bind("<Return>", lambda e: self._do_register())
        self._username_entry.focus_set()

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _entry(self, parent, var, t, show=""):
        return tk.Entry(parent, textvariable=var, show=show,
                        bg=t["entry_bg"], fg=t["fg"],
                        insertbackground=t["fg"],
                        relief=tk.FLAT, font=("TkDefaultFont", 11),
                        highlightthickness=1,
                        highlightbackground=t["border"],
                        highlightcolor=t["accent"])

    def _accent_btn(self, parent, text, cmd, t):
        btn = tk.Button(parent, text=text, command=cmd,
                        bg=t["accent"], fg=t["acc_fg"],
                        activebackground=t["acc_hover"],
                        activeforeground=t["acc_fg"],
                        relief=tk.FLAT, cursor="hand2",
                        font=("TkDefaultFont", 10, "bold"))
        btn.bind("<Enter>", lambda e: btn.configure(bg=t["acc_hover"]))
        btn.bind("<Leave>", lambda e: btn.configure(bg=t["accent"]))
        return btn

    def _clear_form(self):
        for w in self.form_frame.winfo_children():
            w.destroy()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_login(self):
        identifier = self.login_var.get().strip()
        password   = self.password_var.get()
        if not identifier or not password:
            self.msg_var.set("Please fill in all fields.")
            return
        ok, val = verify_user(identifier, password)
        if ok:
            users   = _load_users()
            ukey    = _find_by_login(identifier, users)
            enc_key = get_encryption_key(ukey, password) if ukey else None

            if self._remember_var.get():
                _save_remembered(identifier)
                days = getattr(self, "_session_days", 7)
                create_session(ukey, days=days, enc_key=enc_key)
            else:
                _clear_remembered()
                revoke_session()

            self.result = (val, enc_key)
            self.top.grab_release()
            self.top.destroy()
        else:
            self.msg_var.set(val)

    def _do_register(self):
        username = self.username_var.get().strip()
        email    = self.email_var.get().strip()
        password = self.password_var.get()
        confirm  = self.confirm_var.get()
        if not username or not email or not password or not confirm:
            self.msg_var.set("Please fill in all fields.")
            return
        if password != confirm:
            self.msg_var.set("Passwords do not match.")
            return
        ok, msg = register_user(username, email, password)
        if ok:
            _, display = verify_user(username, password)
            enc_key    = get_encryption_key(username.lower(), password)
            self.result = (display, enc_key)
            self.top.grab_release()
            self.top.destroy()
        else:
            self.msg_var.set(msg)

    def _toggle_show_pw(self):
        self._show_pw = not self._show_pw
        self._pw_entry.configure(show="" if self._show_pw else "●")
        self._eye_btn.configure(text="Hide" if self._show_pw else "Show")

    def _switch_to_register(self):
        self._mode = "register"
        self._build_register_form(_DARK if self.dark_mode else _LIGHT)

    def _switch_to_login(self):
        self._mode = "login"
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.top.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")
        self._build_login_form(_DARK if self.dark_mode else _LIGHT)

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        for w in self.top.winfo_children():
            w.destroy()
        self._build()
        if self._mode == "register":
            self._switch_to_register()

    def _on_close(self):
        self.result = None
        self.top.grab_release()
        self.top.destroy()

    def run(self):
        """Returns (display_name, enc_key) or (None, None)."""
        self.root.wait_window(self.top)
        if self.result:
            return self.result
        return (None, None)