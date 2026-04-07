"""
main.py — Entry point for My Tasks.
Run:  python main.py
"""

import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("data", exist_ok=True)

from core.storage import load_config
from core.auth import (verify_session, get_encryption_key,
                       _load_users, _find_by_login)
from gui.login import LoginWindow, _load_remembered
from gui.app import TodoApp


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


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    # ── App icon path ─────────────────────────────────
    _icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")

    def _set_icon(window):
        try:
            window.iconbitmap(_icon_path)
        except Exception:
            pass

    # ── Try session auto-login first ──────────────────
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
        # ── Normal login ──────────────────────────────
        dark = _detect_theme()
        lw = LoginWindow(root, dark_mode=dark)
        _set_icon(lw.top)          # icon on the login window itself
        username, enc_key = lw.run()

        if not username:
            root.destroy()
        else:
            root.deiconify()
            _set_icon(root)        # icon on the main window in taskbar
            app = TodoApp(root, username=username, enc_key=enc_key,
                          _session_info=None)
            root.mainloop()