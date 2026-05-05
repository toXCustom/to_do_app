"""
gui/theme.py — ttkbootstrap integration helpers
================================================
Provides:
  TTKBOOTSTRAP        bool — True if ttkbootstrap is installed
  make_root(dark)     → tk.Tk or ttkbootstrap.Window
  styled_btn(...)     → tk.Button or ttk.Button with bootstyle
  styled_entry(...)   → tk.Entry or ttk.Entry
  styled_combo(...)   → tk.OptionMenu or ttk.Combobox

All helpers degrade gracefully when ttkbootstrap is not installed.

Install with:
    py -m pip install ttkbootstrap
"""

import tkinter as tk
import tkinter.ttk as ttk

# ── Detect ttkbootstrap ───────────────────────────────────────────────────────

try:
    import ttkbootstrap as _bs
    TTKBOOTSTRAP = True
except ImportError:
    TTKBOOTSTRAP = False

# ── Theme name mapping ────────────────────────────────────────────────────────
#   Our dark mode  → ttkbootstrap "darkly"
#   Our light mode → ttkbootstrap "flatly"
_BS_THEMES = {True: "darkly", False: "flatly"}


def make_root(dark: bool = True) -> tk.Tk:
    """
    Create the application root window.
    Uses ttkbootstrap.Window if available, otherwise plain tk.Tk.
    """
    if TTKBOOTSTRAP:
        root = _bs.Window(themename=_BS_THEMES[dark])
    else:
        root = tk.Tk()
    return root


def switch_theme(dark: bool):
    """Switch ttkbootstrap theme at runtime (called from apply_theme)."""
    if not TTKBOOTSTRAP:
        return
    try:
        style = _bs.Style()
        style.theme_use(_BS_THEMES[dark])
    except Exception:
        pass


# ── Widget helpers ────────────────────────────────────────────────────────────

def styled_btn(parent, text: str, command=None, primary: bool = False,
               danger: bool = False, **kw) -> tk.Widget:
    """
    Return a styled button.

    With ttkbootstrap:
      primary=True  → bootstyle="warning" (accent orange)
      danger=True   → bootstyle="danger"
      default       → bootstyle="secondary"

    Without ttkbootstrap: plain tk.Button using caller's bg/fg kw.
    """
    if TTKBOOTSTRAP:
        if primary:
            bs = "warning"
        elif danger:
            bs = "danger"
        else:
            bs = "secondary"
        # Remove plain-tk-only kwargs that ttk doesn't accept
        for k in ("bg", "fg", "activebackground", "activeforeground",
                  "relief", "bd", "highlightthickness"):
            kw.pop(k, None)
        return ttk.Button(parent, text=text, command=command,
                          bootstyle=bs, **kw)
    else:
        return tk.Button(parent, text=text, command=command, **kw)


def styled_entry(parent, textvariable=None, show: str = "",
                 width: int = 30, **kw) -> tk.Widget:
    """
    Return a styled Entry widget.
    ttkbootstrap ttk.Entry renders with rounded corners.
    """
    if TTKBOOTSTRAP:
        for k in ("bg", "fg", "insertbackground",
                  "highlightthickness", "highlightbackground",
                  "highlightcolor", "relief", "bd"):
            kw.pop(k, None)
        return ttk.Entry(parent, textvariable=textvariable,
                         show=show, width=width, **kw)
    else:
        return tk.Entry(parent, textvariable=textvariable,
                        show=show, width=width, **kw)


def styled_combo(parent, variable, values: list,
                 width: int = 16, **kw) -> tk.Widget:
    """
    Return a Combobox (ttkbootstrap) or OptionMenu (plain tk).
    """
    if TTKBOOTSTRAP:
        for k in ("bg", "fg", "activebackground", "relief", "bd"):
            kw.pop(k, None)
        cb = ttk.Combobox(parent, textvariable=variable,
                          values=values, state="readonly",
                          width=width, **kw)
        if values:
            cb.set(variable.get() or values[0])
        return cb
    else:
        return tk.OptionMenu(parent, variable, *values, **kw)


def styled_label(parent, text: str = "", textvariable=None,
                 font=None, **kw) -> tk.Label:
    """Plain tk.Label — same regardless of ttkbootstrap (labels don't need styling)."""
    kwargs = dict(text=text, font=font, **kw)
    if textvariable is not None:
        kwargs["textvariable"] = textvariable
    return tk.Label(parent, **kwargs)


def status_badge(parent, text: str, color: str, bg: str) -> tk.Label:
    """
    A coloured pill-shaped status label.
    With ttkbootstrap draws a rounded Label; without, a padded Label.
    """
    return tk.Label(parent, text=text, fg=color, bg=bg,
                    font=("TkDefaultFont", 8, "bold"),
                    padx=6, pady=2)