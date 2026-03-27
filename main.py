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
from gui.login import LoginWindow
from gui.app import TodoApp


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    _cfg  = load_config()
    dark  = _cfg.get("dark_mode", True)

    lw       = LoginWindow(root, dark_mode=dark)
    username = lw.run()

    if not username:
        root.destroy()
    else:
        root.deiconify()
        app = TodoApp(root, username=username)
        root.mainloop()