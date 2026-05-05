"""
main.py — Entry point for My Tasks.
Run:  python main.py

Uses ttkbootstrap for a modern OS-native look when installed:
    py -m pip install ttkbootstrap
Falls back to plain tkinter if not available.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("data", exist_ok=True)

import tkinter as tk
import tkinter.ttk as ttk

# ── IMPORTANT: capture original Frame.__init__ BEFORE ttkbootstrap patches it ─
import gui.ttkbs_compat as _compat   # sets _compat.ORIG_FRAME_INIT

# ── Try ttkbootstrap ──────────────────────────────────────────────────────────
try:
    import ttkbootstrap as _ttkbs
    TTKBOOTSTRAP = True
except ImportError:
    TTKBOOTSTRAP = False

from core.storage import load_config
from core.auth import (verify_session, get_encryption_key,
                       _load_users, _find_by_login)
from gui.login import LoginWindow, _load_remembered
from gui.app import TodoApp

# Pre-compute icon path once at module level
_ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets", "icon.ico")


def _set_icon(window):
    try:
        window.iconbitmap(_ICON_PATH)
    except Exception:
        pass


def _detect_theme() -> bool:
    remembered = _load_remembered()
    identifier = remembered.get("identifier", "")
    if identifier:
        users = _load_users()
        key   = _find_by_login(identifier, users)
        if key:
            display = users[key].get("display_name", key)
            cfg = load_config(display)
            return cfg.get("dark_mode", True)
    cfg = load_config()
    return cfg.get("dark_mode", True)


def _make_root(dark: bool) -> tk.Tk:
    """
    Create root window. Use plain tk.Tk + ttkbootstrap.Style so ttkbootstrap
    applies its theme without needing ttkbootstrap.Window.
    """
    root = tk.Tk()
    if TTKBOOTSTRAP:
        bs_theme = "darkly" if dark else "flatly"
        try:
            _ttkbs.Style(theme=bs_theme)
            print(f"[UI] ttkbootstrap active — theme: {bs_theme}")
        except Exception as e:
            print(f"[UI] ttkbootstrap style failed: {e}")
    else:
        print("[UI] ttkbootstrap not installed — using classic tkinter")
        print("[UI] For a modern look:  py -m pip install ttkbootstrap")
    return root


if __name__ == "__main__":
    dark = _detect_theme()
    root = _make_root(dark)
    root.withdraw()

    session = verify_session()
    if session:
        username = session["display_name"]
        enc_key  = session.get("enc_key")
        root.deiconify()
        _set_icon(root)
        app = TodoApp(root, username=username, enc_key=enc_key,
                      _session_info=session)
        root.mainloop()
    else:
        # Reuse the already-computed `dark` — no need to call _detect_theme() again
        lw = LoginWindow(root, dark_mode=dark)
        _set_icon(lw.top)
        username, enc_key = lw.run()

        if not username:
            root.destroy()
        else:
            root.deiconify()
            _set_icon(root)
            app = TodoApp(root, username=username, enc_key=enc_key,
                          _session_info=None)
            root.mainloop()
