"""
main.py — Entry point for My Tasks.
Run:  python main.py
"""

import os
import sys
import tkinter as tk

# Ensure the project root is on sys.path so all packages resolve correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure the data/ directory exists before anything tries to read/write it
os.makedirs("data", exist_ok=True)

from core.storage import load_config
from core.auth import get_display_name
from gui.login import LoginWindow, _load_remembered
from gui.app import TodoApp


def _detect_theme() -> bool:
    """
    Return the dark_mode bool to use for the login window.
    Priority: remembered user's config → anonymous config → default True (dark).
    """
    remembered = _load_remembered()
    identifier = remembered.get("identifier", "")
    if identifier:
        # Try to resolve identifier to a username key for the config file
        from core.auth import _load_users, _find_by_login
        users = _load_users()
        key   = _find_by_login(identifier, users)
        if key:
            display = users[key].get("display_name", key)
            cfg = load_config(display)
            return cfg.get("dark_mode", True)
    # Fall back to anonymous config
    cfg = load_config()
    return cfg.get("dark_mode", True)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    dark = _detect_theme()

    lw               = LoginWindow(root, dark_mode=dark)
    username, enc_key = lw.run()

    if not username:
        root.destroy()
    else:
        root.deiconify()
        app = TodoApp(root, username=username, enc_key=enc_key)
        root.mainloop()