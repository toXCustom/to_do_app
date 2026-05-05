"""
services/cloud_sync.py — Cloud Sync for My Tasks
=================================================
Supports three providers:

  Provider       Auth             Extra install
  ─────────────────────────────────────────────
  GitHub Gist    Personal Token   none (urllib)
  Google Drive   OAuth2 PKCE      pip install google-auth-oauthlib google-api-python-client
  Dropbox        OAuth2 PKCE      pip install dropbox

All providers expose the same interface:
    provider.push(local_path, username)   → sync_id (str)
    provider.pull(local_path, username)   → True / False
    provider.configured() → bool

Credentials and sync metadata are stored in  data/cloud_sync.json
(plain JSON — tokens are not sensitive enough to encrypt, and the file
 is already protected by the OS user's file permissions).
"""

import os
import sys
import json
import time
import threading
import urllib.request
import urllib.parse
import urllib.error
import base64
import hashlib
import secrets
from http.server import HTTPServer, BaseHTTPRequestHandler

_SYNC_FILE = "data/cloud_sync.json"


# ── Credential store ──────────────────────────────────────────────────────────

def _load_creds() -> dict:
    try:
        with open(_SYNC_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_creds(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(_SYNC_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── OAuth PKCE helper (used by Google Drive + Dropbox) ───────────────────────

class _PKCEFlow:
    """Opens browser, listens on localhost:PORT for the OAuth callback."""

    REDIRECT_URI = "http://localhost:9753/callback"

    def __init__(self):
        self._code:  str | None = None
        self._error: str | None = None
        self._server: HTTPServer | None = None

    def start_listener(self):
        """Start a one-shot HTTP server for the OAuth redirect."""
        flow = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if "code" in qs:
                    flow._code  = qs["code"][0]
                    msg = b"<html><body><h2>Authorised! You can close this tab.</h2></body></html>"
                else:
                    flow._error = qs.get("error", ["unknown"])[0]
                    msg = b"<html><body><h2>Authorisation failed. Please try again.</h2></body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(msg)

            def log_message(self, *_): pass

        self._server = HTTPServer(("localhost", 9753), Handler)
        t = threading.Thread(target=self._server.handle_request, daemon=True)
        t.start()

    def wait_for_code(self, timeout=120) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._code or self._error:
                break
            time.sleep(0.2)
        if self._server:
            try: self._server.server_close()
            except: pass
        if self._error:
            raise RuntimeError(f"OAuth error: {self._error}")
        if not self._code:
            raise TimeoutError("OAuth timed out — no response within 2 minutes.")
        return self._code

    @staticmethod
    def pkce_pair():
        verifier  = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        return verifier, challenge


# ── Base provider ─────────────────────────────────────────────────────────────

class CloudProvider:
    NAME = "base"

    def configured(self) -> bool:
        raise NotImplementedError

    def push(self, local_path: str, username: str = None) -> str:
        """Upload file. Returns sync ID (URL / file ID / gist ID)."""
        raise NotImplementedError

    def pull(self, local_path: str, username: str = None) -> bool:
        """Download file to local_path. Returns True on success."""
        raise NotImplementedError

    def disconnect(self):
        """Remove stored credentials."""
        creds = _load_creds()
        creds.pop(self.NAME, None)
        _save_creds(creds)


# ═══════════════════════════════════════════════════════════════════════════════
#  GITHUB GIST
# ═══════════════════════════════════════════════════════════════════════════════

class GitHubGist(CloudProvider):
    """
    Sync tasks to/from a secret GitHub Gist.
    Requires a Personal Access Token with 'gist' scope.
    Create one at: https://github.com/settings/tokens
    """
    NAME        = "github_gist"
    API_BASE    = "https://api.github.com"
    GIST_FILE   = "mytasks.json"

    def configured(self) -> bool:
        return bool(_load_creds().get(self.NAME, {}).get("token"))

    def _token(self) -> str:
        return _load_creds().get(self.NAME, {}).get("token", "")

    def _gist_id(self) -> str:
        return _load_creds().get(self.NAME, {}).get("gist_id", "")

    def set_token(self, token: str):
        creds = _load_creds()
        creds.setdefault(self.NAME, {})["token"] = token.strip()
        _save_creds(creds)

    def _request(self, method: str, path: str, body=None) -> dict:
        url = self.API_BASE + path
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={
                "Authorization": f"token {self._token()}",
                "Accept":        "application/vnd.github+json",
                "Content-Type":  "application/json",
                "User-Agent":    "MyTasks-App/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub {e.code}: {body}")

    def push(self, local_path: str, username: str = None) -> str:
        with open(local_path, "rb") as f:
            raw = f.read()
        # Try base64 if binary (encrypted)
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = base64.b64encode(raw).decode("ascii")

        gist_id = self._gist_id()
        payload = {
            "description": f"My Tasks backup — {username or 'user'}",
            "public":      False,
            "files":       {self.GIST_FILE: {"content": content}},
        }
        if gist_id:
            result = self._request("PATCH", f"/gists/{gist_id}", payload)
        else:
            result = self._request("POST", "/gists", payload)

        new_id = result["id"]
        creds  = _load_creds()
        creds.setdefault(self.NAME, {})["gist_id"] = new_id
        creds[self.NAME]["last_push"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_creds(creds)
        return result["html_url"]

    def pull(self, local_path: str, username: str = None) -> bool:
        gist_id = self._gist_id()
        if not gist_id:
            raise RuntimeError("No Gist ID stored — push first to create the Gist.")
        result  = self._request("GET", f"/gists/{gist_id}")
        content = result["files"].get(self.GIST_FILE, {}).get("content", "")
        if not content:
            return False
        # Detect base64
        try:
            raw = content.encode("utf-8")
            try:
                decoded = base64.b64decode(raw)
                # Check if it looks like Fernet (starts with 'gA')
                if content.startswith("gA"):
                    raw = decoded
            except Exception:
                pass
        except Exception:
            return False

        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(raw if isinstance(raw, bytes) else raw.encode())
        creds = _load_creds()
        creds.setdefault(self.NAME, {})["last_pull"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_creds(creds)
        return True


# ═══════════════════════════════════════════════════════════════════════════════
#  GOOGLE DRIVE
# ═══════════════════════════════════════════════════════════════════════════════

class GoogleDrive(CloudProvider):
    """
    Sync tasks to/from a file in Google Drive (app data folder).
    Requires:  pip install google-auth-oauthlib google-api-python-client

    Uses OAuth2 with PKCE. The app opens the browser; the user approves;
    tokens are stored locally.
    """
    NAME        = "google_drive"
    SCOPES      = ["https://www.googleapis.com/auth/drive.appdata"]
    FILENAME    = "mytasks_backup.json"
    # Public OAuth client for installed apps — safe to ship
    CLIENT_ID   = "YOUR_GOOGLE_CLIENT_ID"
    CLIENT_SEC  = "YOUR_GOOGLE_CLIENT_SECRET"

    def configured(self) -> bool:
        creds = _load_creds().get(self.NAME, {})
        return bool(creds.get("access_token") and creds.get("refresh_token"))

    def _creds(self) -> dict:
        return _load_creds().get(self.NAME, {})

    def _api(self):
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
        except ImportError:
            raise RuntimeError(
                "Google API not installed.\n"
                "Run:  py -m pip install google-auth-oauthlib google-api-python-client"
            )
        c = self._creds()
        cred = Credentials(
            token         = c.get("access_token"),
            refresh_token = c.get("refresh_token"),
            token_uri     = "https://oauth2.googleapis.com/token",
            client_id     = self.CLIENT_ID,
            client_secret = self.CLIENT_SEC,
        )
        return build("drive", "v3", credentials=cred)

    def authorise(self, open_browser_fn=None):
        """Start OAuth2 PKCE flow. Blocks until user completes in browser."""
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            raise RuntimeError(
                "Google auth not installed.\n"
                "Run:  py -m pip install google-auth-oauthlib google-api-python-client"
            )
        import webbrowser
        client_config = {"installed": {
            "client_id":     self.CLIENT_ID,
            "client_secret": self.CLIENT_SEC,
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }}
        flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
        cred = flow.run_local_server(port=9753, open_browser=True)
        data = _load_creds()
        data[self.NAME] = {
            "access_token":  cred.token,
            "refresh_token": cred.refresh_token,
        }
        _save_creds(data)

    def push(self, local_path: str, username: str = None) -> str:
        service = self._api()
        with open(local_path, "rb") as f:
            raw = f.read()
        from googleapiclient.http import MediaIoBaseUpload
        import io

        # Find existing file
        results = service.files().list(
            spaces="appDataFolder",
            fields="files(id, name)",
            q=f"name='{self.FILENAME}'",
        ).execute()
        files = results.get("files", [])

        media = MediaIoBaseUpload(io.BytesIO(raw), mimetype="application/octet-stream")
        if files:
            service.files().update(fileId=files[0]["id"], media_body=media).execute()
            file_id = files[0]["id"]
        else:
            meta = {"name": self.FILENAME, "parents": ["appDataFolder"]}
            res  = service.files().create(body=meta, media_body=media,
                                          fields="id").execute()
            file_id = res["id"]

        creds = _load_creds()
        creds.setdefault(self.NAME, {})["file_id"]   = file_id
        creds[self.NAME]["last_push"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_creds(creds)
        return f"https://drive.google.com/file/d/{file_id}"

    def pull(self, local_path: str, username: str = None) -> bool:
        service = self._api()
        results = service.files().list(
            spaces="appDataFolder",
            fields="files(id, name)",
            q=f"name='{self.FILENAME}'",
        ).execute()
        files = results.get("files", [])
        if not files:
            return False
        raw = service.files().get_media(fileId=files[0]["id"]).execute()
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(raw)
        creds = _load_creds()
        creds.setdefault(self.NAME, {})["last_pull"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_creds(creds)
        return True


# ═══════════════════════════════════════════════════════════════════════════════
#  DROPBOX
# ═══════════════════════════════════════════════════════════════════════════════

class Dropbox(CloudProvider):
    """
    Sync tasks to/from Dropbox.
    Requires:  pip install dropbox

    Uses OAuth2 PKCE long-lived refresh token.
    """
    NAME      = "dropbox"
    APP_KEY   = "YOUR_DROPBOX_APP_KEY"
    FILEPATH  = "/mytasks_backup.json"

    def configured(self) -> bool:
        return bool(_load_creds().get(self.NAME, {}).get("refresh_token"))

    def _dbx(self):
        try:
            import dropbox as _dbx_module
        except ImportError:
            raise RuntimeError(
                "Dropbox SDK not installed.\n"
                "Run:  py -m pip install dropbox"
            )
        c = _load_creds().get(self.NAME, {})
        return _dbx_module.Dropbox(
            oauth2_refresh_token = c.get("refresh_token"),
            app_key              = self.APP_KEY,
        )

    def authorise(self):
        """OAuth2 PKCE flow for Dropbox."""
        try:
            import dropbox as _dbx_module
            from dropbox import DropboxOAuth2FlowNoRedirect
        except ImportError:
            raise RuntimeError(
                "Dropbox SDK not installed.\n"
                "Run:  py -m pip install dropbox"
            )
        import webbrowser
        auth_flow = DropboxOAuth2FlowNoRedirect(
            self.APP_KEY,
            use_pkce         = True,
            token_access_type= "offline",
        )
        url = auth_flow.start()
        webbrowser.open(url)
        return auth_flow   # caller must call finish(code) after getting code from user

    def finish_auth(self, auth_flow, code: str):
        result = auth_flow.finish(code.strip())
        creds  = _load_creds()
        creds[self.NAME] = {"refresh_token": result.refresh_token}
        _save_creds(creds)

    def push(self, local_path: str, username: str = None) -> str:
        import dropbox as _dbx_module
        dbx = self._dbx()
        with open(local_path, "rb") as f:
            raw = f.read()
        dbx.files_upload(
            raw, self.FILEPATH,
            mode=_dbx_module.files.WriteMode.overwrite,
        )
        creds = _load_creds()
        creds.setdefault(self.NAME, {})["last_push"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_creds(creds)
        return f"dropbox://apps/{os.path.basename(self.FILEPATH)}"

    def pull(self, local_path: str, username: str = None) -> bool:
        dbx = self._dbx()
        try:
            _, res = dbx.files_download(self.FILEPATH)
        except Exception as e:
            if "not_found" in str(e).lower():
                return False
            raise
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(res.content)
        creds = _load_creds()
        creds.setdefault(self.NAME, {})["last_pull"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_creds(creds)
        return True


# ── Provider registry ─────────────────────────────────────────────────────────

PROVIDERS = {
    "GitHub Gist": GitHubGist(),
    "Google Drive": GoogleDrive(),
    "Dropbox":      Dropbox(),
}


def get_last_sync_info() -> dict:
    """Return {provider_name: {last_push, last_pull}} for all configured providers."""
    creds = _load_creds()
    result = {}
    for name, prov in PROVIDERS.items():
        key  = prov.NAME
        data = creds.get(key, {})
        if prov.configured():
            result[name] = {
                "last_push": data.get("last_push", "Never"),
                "last_pull": data.get("last_pull", "Never"),
            }
    return result