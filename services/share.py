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
    """Open WhatsApp Web with text pre-filled — user picks the chat to send to."""
    encoded = urllib.parse.quote(text[:4000])
    webbrowser.open(f"https://web.whatsapp.com/send?text={encoded}")


# ── Telegram ──────────────────────────────────────────────────────────────────

def share_telegram(text: str) -> None:
    """Open Telegram share URL with text pre-filled."""
    encoded = urllib.parse.quote(text[:4096])
    webbrowser.open(f"https://t.me/share/url?url=&text={encoded}")


# ── Signal ────────────────────────────────────────────────────────────────────

def share_signal(text: str, root=None) -> None:
    """
    Signal has no web share URL — copy the text to clipboard and open Signal.
    The user pastes into any Signal conversation.
    """
    if root:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    # Try to launch Signal desktop app
    if sys.platform == "win32":
        _try_launch_app([
            r"%LOCALAPPDATA%\Programs\signal-desktop\Signal.exe",
            r"C:\Program Files\Signal\Signal.exe",
        ])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Signal"])
    else:
        subprocess.Popen(["signal-desktop"])


# ── Messenger ─────────────────────────────────────────────────────────────────

def share_messenger(text: str, root=None) -> None:
    """
    Open Messenger web in browser. Text is copied to clipboard so the
    user can paste it into any conversation.
    """
    if root:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    webbrowser.open("https://www.messenger.com")


# ── Instagram ─────────────────────────────────────────────────────────────────

def share_instagram(text: str, root=None) -> None:
    """
    Instagram has no web share API — copy text to clipboard and open Instagram.
    User pastes into a DM.
    """
    if root:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    webbrowser.open("https://www.instagram.com/direct/inbox/")


# ── Discord ───────────────────────────────────────────────────────────────────

def share_discord(text: str, root=None) -> None:
    """
    Discord has no public share URL — copy text to clipboard and open Discord.
    User pastes into any channel or DM.
    """
    if root:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    # Try to launch Discord desktop app first
    launched = False
    if sys.platform == "win32":
        launched = _try_launch_app([
            r"%LOCALAPPDATA%\Discord\Update.exe",
        ])
    elif sys.platform == "darwin":
        try:
            subprocess.Popen(["open", "-a", "Discord"])
            launched = True
        except Exception:
            pass
    if not launched:
        webbrowser.open("https://discord.com/app")


# ── Launch helper ─────────────────────────────────────────────────────────────

def _try_launch_app(paths: list) -> bool:
    """Try to launch an app from a list of candidate paths. Returns True on success."""
    for raw_path in paths:
        path = os.path.expandvars(raw_path)
        if os.path.exists(path):
            try:
                subprocess.Popen([path])
                return True
            except Exception:
                continue
    return False


# ── Communicators registry ────────────────────────────────────────────────────
# Each entry: (label, emoji, fn, needs_root, note)
# needs_root=True  → fn(text, root)  — copies to clipboard then opens app
# needs_root=False → fn(text)        — opens a URL directly

COMMUNICATORS = [
    ("WhatsApp",  "💬", share_whatsapp,  False, "Opens WhatsApp Web"),
    ("Telegram",  "✈️",  share_telegram,  False, "Opens Telegram Web"),
    ("Signal",    "🔒", share_signal,    True,  "Copies text → opens Signal"),
    ("Messenger", "💙", share_messenger, True,  "Copies text → opens Messenger"),
    ("Instagram", "📸", share_instagram, True,  "Copies text → opens Instagram DMs"),
    ("Discord",   "🎮", share_discord,   True,  "Copies text → opens Discord"),
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