"""
login.py — Login / Register window for My Tasks.
Call LoginWindow(root).run() → returns display_name string or None if cancelled.
"""

import tkinter as tk
from core.auth import verify_user, register_user

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
}


class LoginWindow:
    W, H = 380, 500

    def __init__(self, root: tk.Tk, dark_mode: bool = True):
        self.root      = root
        self.dark_mode = dark_mode
        self.result    = None
        self._mode     = "login"

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

        self._show_pw = False
        self._eye_btn = tk.Button(self.form_frame, text="Show",
                                  font=("TkDefaultFont", 8),
                                  bg=t["bg"], fg=t["muted_fg"],
                                  relief=tk.FLAT, cursor="hand2", bd=0,
                                  command=self._toggle_show_pw)
        self._eye_btn.pack(anchor="e", pady=(2, 10))

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

        self.top.bind("<Return>", lambda e: self._do_login())
        self._login_entry.focus_set()

    def _build_register_form(self, t):
        self._clear_form()

        # Taller window for registration
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.top.geometry(f"{self.W}x540+{(sw-self.W)//2}+{(sh-540)//2}")

        tk.Label(self.form_frame, text="Create account",
                 font=("TkDefaultFont", 13, "bold"),
                 bg=t["bg"], fg=t["fg"]).pack(anchor="w", pady=(0, 14))

        # Username
        tk.Label(self.form_frame, text="Username",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
        self.username_var = tk.StringVar()
        self._username_entry = self._entry(self.form_frame, self.username_var, t)
        self._username_entry.pack(fill=tk.X, pady=(3, 10))

        # Email
        tk.Label(self.form_frame, text="Email address",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
        self.email_var = tk.StringVar()
        self._entry(self.form_frame, self.email_var, t).pack(fill=tk.X, pady=(3, 10))

        # Password
        tk.Label(self.form_frame, text="Password",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
        self.password_var = tk.StringVar()
        self._entry(self.form_frame, self.password_var, t, show="●").pack(
            fill=tk.X, pady=(3, 10))

        # Confirm
        tk.Label(self.form_frame, text="Confirm password",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
        self.confirm_var = tk.StringVar()
        self._entry(self.form_frame, self.confirm_var, t, show="●").pack(
            fill=tk.X, pady=(3, 8))

        self.msg_var = tk.StringVar()
        tk.Label(self.form_frame, textvariable=self.msg_var,
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["error"],
                 wraplength=300, justify="left").pack(anchor="w", pady=(0, 8))

        self._accent_btn(self.form_frame, "Create account", self._do_register, t).pack(
            fill=tk.X, ipady=6, pady=(0, 12))

        tk.Button(self.form_frame, text="← Back to sign in",
                  font=("TkDefaultFont", 9, "underline"),
                  bg=t["bg"], fg=t["accent"],
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self._switch_to_login).pack()

        self.top.bind("<Return>", lambda e: self._do_register())
        self._username_entry.focus_set()

    # ── Helpers ───────────────────────────────────────────────────────────────

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
            self.result = val
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
            self.result = display
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
        # Restore original height
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
        self.root.wait_window(self.top)
        return self.result