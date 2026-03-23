"""
share.py — Share an exported file via various channels
=======================================================
All functions are fire-and-forget (open a URL or process).
No external dependencies beyond stdlib.
"""
import os
import sys
import subprocess
import webbrowser
import urllib.parse


# ── Open file / folder ────────────────────────────────────────────────────────

def open_file(path: str) -> None:
    """Open the file with the OS default app."""
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def reveal_in_folder(path: str) -> None:
    """Open the containing folder, highlighting the file where supported."""
    folder = os.path.dirname(os.path.abspath(path))
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.abspath(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", folder])


# ── Clipboard ─────────────────────────────────────────────────────────────────

def copy_path_to_clipboard(path: str, root) -> None:
    """Copy the file path string to the clipboard."""
    root.clipboard_clear()
    root.clipboard_append(os.path.abspath(path))
    root.update()


def copy_content_to_clipboard(path: str, root) -> bool:
    """Read the file and copy its text content to clipboard. Returns True on success."""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        root.clipboard_clear()
        root.clipboard_append(content)
        root.update()
        return True
    except Exception:
        return False


# ── Email ─────────────────────────────────────────────────────────────────────

def send_email(path: str, subject: str = "My Tasks export") -> None:
    """
    Open the default email client via a mailto: link.
    The file path is included in the body as a note (mailto: can't attach files).
    For a proper attachment, the user opens their mail client manually.
    """
    body = (
        f"Hi,\n\n"
        f"Please find my exported task list attached.\n\n"
        f"File: {os.path.basename(path)}\n"
        f"Location: {os.path.abspath(path)}\n\n"
        f"(Attach the file manually from the location above.)"
    )
    params = urllib.parse.urlencode({
        "subject": subject,
        "body":    body,
    }, quote_via=urllib.parse.quote)
    webbrowser.open(f"mailto:?{params}")


def send_email_outlook(path: str, subject: str = "My Tasks export") -> bool:
    """
    On Windows, try to open Outlook with the file pre-attached using COM.
    Falls back gracefully if Outlook is not installed.
    Returns True if Outlook was opened successfully.
    """
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # type: ignore
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail    = outlook.CreateItem(0)
        mail.Subject     = subject
        mail.Body        = "Please find my exported task list attached."
        mail.Attachments.Add(os.path.abspath(path))
        mail.Display(True)
        return True
    except Exception:
        return False


# ── WhatsApp ──────────────────────────────────────────────────────────────────

def share_whatsapp(text: str) -> None:
    """Open WhatsApp Web share URL with the text pre-filled (text only)."""
    encoded = urllib.parse.quote(text[:4000])   # WA has a ~4000 char URL limit
    webbrowser.open(f"https://wa.me/?text={encoded}")


# ── Telegram ──────────────────────────────────────────────────────────────────

def share_telegram(text: str) -> None:
    """Open Telegram share URL with text pre-filled."""
    encoded = urllib.parse.quote(text[:4096])
    webbrowser.open(f"https://t.me/share/url?url=&text={encoded}")


# ── Generic communicator URLs ─────────────────────────────────────────────────

COMMUNICATORS = [
    ("WhatsApp",  "💬", share_whatsapp),
    ("Telegram",  "✈️",  share_telegram),
]


# ── Text summary builder ──────────────────────────────────────────────────────

def tasks_to_share_text(tasks: list, max_tasks: int = 30) -> str:
    """
    Build a concise plain-text summary suitable for messaging apps.
    Emoji-based, no special formatting.
    """
    from datetime import date as dt_date
    today = dt_date.today()

    lines = [f"📋 My Tasks ({len(tasks)} total)\n"]
    shown = tasks[:max_tasks]

    for t in shown:
        done_mark = "✅" if t.done else "🔲"
        pri_icon  = {"High": "🔥", "Medium": "⚡", "Low": "🌿"}.get(t.priority, "")
        due_str   = ""
        if t.due_date and not t.done:
            delta = (t.due_date - today).days
            if delta < 0:
                due_str = f" ⚠️ overdue"
            elif delta == 0:
                due_str = f" 📅 today"
            elif delta <= 7:
                due_str = f" 📅 in {delta}d"
        lines.append(f"{done_mark} {pri_icon} {t.name}{due_str}")

    if len(tasks) > max_tasks:
        lines.append(f"\n… and {len(tasks) - max_tasks} more tasks.")

    return "\n".join(lines)