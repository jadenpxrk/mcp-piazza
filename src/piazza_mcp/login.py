"""Easy login: copy the Piazza session from a browser, or log in on a local web page.

The login page runs on 127.0.0.1 only. Its URL has a random token, and it checks the Host and Origin headers,
so other web pages and other computers cannot use it. The password goes from the page to Piazza, never to the model.
"""

import html
import logging
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

from fastmcp.exceptions import ToolError

if TYPE_CHECKING:
    from .client import PiazzaClient

log = logging.getLogger("piazza_mcp")

BROWSERS = ("chrome", "arc", "brave", "edge", "firefox", "safari", "chromium", "vivaldi", "opera")


def browser_cookie_sets(browser: str | None = None) -> tuple[list[tuple[str, dict[str, str]]], list[str]]:
    """Return the piazza.com cookies of each browser that has a Piazza session, and the errors for the others."""
    import browser_cookie3  # imported here because it is slow to import

    found: list[tuple[str, dict[str, str]]] = []
    errors: list[str] = []
    for name in [browser] if browser else BROWSERS:
        try:
            jar = getattr(browser_cookie3, name)(domain_name="piazza.com")
        except Exception as e:  # browser_cookie3 raises many types: missing profile, keychain refusal, locked DB
            errors.append(f"{name}: {e}")
            continue
        cookies = {c.name: c.value for c in jar if (c.domain or "").lstrip(".").endswith("piazza.com") and c.value}
        if cookies.get("session_id"):
            found.append((name, cookies))
    return found, errors


def browser_login(client: "PiazzaClient", browser: str | None = None) -> str:
    """Use the first browser session that Piazza accepts. Returns a message for the user."""
    found, errors = browser_cookie_sets(browser)
    rejected: list[str] = []
    for name, cookies in found:
        try:
            who = client.cookie_login(cookies)
        except ToolError as e:
            rejected.append(f"{name}: {e}")
            continue
        return f"Logged in as {who} with the {name} session."
    where = browser or ", ".join(BROWSERS)
    detail = "; ".join(rejected + errors[:3])
    raise ToolError(
        f"No usable Piazza session in {where}. Log in at https://piazza.com in your browser, then try again."
        + (f" Details: {detail}" if detail else "")
    )


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Piazza login</title>
<style>
:root {{ color-scheme: light dark; --fg: #1f2328; --bg: #ffffff; --muted: #59636e; --line: #d1d9e0; --accent: #3e7aab; --on-accent: #ffffff; --error: #b42318; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fg: #e6edf3; --bg: #0d1117; --muted: #9198a1; --line: #3d444d; --accent: #6ea8d8; --on-accent: #0d1117; --error: #f97066; }} }}
* {{ box-sizing: border-box; }}
body {{ font: 16px/1.5 system-ui, sans-serif; color: var(--fg); background: var(--bg); max-width: 26rem; margin: 4rem auto; padding: 0 1rem; }}
h1 {{ font-size: 1.35rem; margin: 0 0 .25rem; }}
.sub {{ color: var(--muted); margin: 0 0 1.75rem; }}
.msg {{ margin: 0 0 1.5rem; }} .msg.error {{ color: var(--error); }}
button {{ width: 100%; padding: .65rem 1rem; font: inherit; font-weight: 600; color: var(--on-accent); background: var(--accent); border: 0; border-radius: 8px; cursor: pointer; }}
button:focus-visible, input:focus-visible, summary:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.hint {{ color: var(--muted); font-size: .875rem; margin: .5rem 0 1.75rem; }}
details {{ margin-top: .75rem; }}
summary {{ cursor: pointer; color: var(--muted); }}
details form {{ margin-top: .75rem; }}
label {{ display: block; font-size: .875rem; margin: .75rem 0 .25rem; }}
input {{ width: 100%; padding: .55rem .65rem; font: inherit; color: var(--fg); background: var(--bg); border: 1px solid var(--line); border-radius: 8px; }}
details button {{ margin-top: 1rem; }}
.foot {{ color: var(--muted); font-size: .8rem; margin-top: 2.5rem; }}
</style></head><body>
<h1>Log in to Piazza</h1>
<p class="sub">Your AI assistant uses this session to read your courses.</p>
{message}
{forms}
</body></html>"""

_FORMS = """<form method="post" action="/{token}/browser"><button>Use my browser session</button></form>
<p class="hint">Log in at piazza.com in your browser first. Chrome-based browsers ask for Keychain access on macOS.</p>
<details><summary>Use email and password</summary>
<form method="post" action="/{token}/password">
<label for="email">Email</label><input id="email" name="email" type="email" autocomplete="username" required>
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required>
<button>Log in</button></form></details>
<details><summary>Paste a session cookie (school SSO)</summary>
<form method="post" action="/{token}/cookie">
<label for="cookie">Value of the <code>session_id</code> cookie for piazza.com</label>
<input id="cookie" name="cookie" autocomplete="off" required>
<button>Save session</button></form></details>
<p class="foot">Only the session cookie is saved, in {cookie_file}. Your password is not saved.</p>"""


class LoginPage:
    """A one-time login page on 127.0.0.1. It stops after a successful login."""

    def __init__(self, client: "PiazzaClient") -> None:
        self.client = client
        self.token = secrets.token_urlsafe(16)
        self.done = threading.Event()
        self.result = ""
        self._server: ThreadingHTTPServer | None = None
        self.port = 0
        self._lock = threading.Lock()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/{self.token}"

    def start(self, open_browser: bool = True) -> str:
        """Start the page if it is not running. Return its URL."""
        with self._lock:
            if self._server is None:
                self.done.clear()
                self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
                self.port = self._server.server_port
                threading.Thread(target=self._server.serve_forever, daemon=True).start()
                log.info("login page at %s", self.url)
                if open_browser:
                    try:
                        webbrowser.open(self.url)
                    except Exception:  # no browser available, for example on a server; the URL is still shown
                        pass
            return self.url

    def _finish(self, message: str) -> None:
        self.result = message
        self.done.set()
        server, self._server = self._server, None
        if server:
            threading.Thread(target=server.shutdown, daemon=True).start()

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        page = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # stdout carries MCP; log to stderr only
                log.debug(format, *args)

            def _origin_ok(self) -> bool:
                hosts = {f"127.0.0.1:{page.port}", f"localhost:{page.port}"}
                if self.headers.get("Host") not in hosts:
                    return False
                origin = self.headers.get("Origin")
                return origin is None or origin.removeprefix("http://") in hosts

            def _send(self, status: int, body: str) -> None:
                data = body.encode()
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                # "no-referrer" makes browsers send "Origin: null" on form posts, which _origin_ok rejects
                self.send_header("Referrer-Policy", "same-origin")
                self.send_header("X-Frame-Options", "DENY")
                self.end_headers()
                self.wfile.write(data)

            def _render(self, message: str = "", forms: bool = True, status: int = 200) -> None:
                kind = "msg error" if status >= 400 else "msg"
                msg = f'<p class="{kind}">{html.escape(message)}</p>' if message else ""
                body = (
                    _FORMS.format(token=page.token, cookie_file=html.escape(str(page.client.settings.cookie_file)))
                    if forms
                    else ""
                )
                self._send(status, _PAGE.format(message=msg, forms=body))

            def do_GET(self) -> None:
                if not self._origin_ok() or self.path != f"/{page.token}":
                    self._send(404, "Not found")
                    return
                self._render()

            def do_POST(self) -> None:
                prefix = f"/{page.token}/"
                if not self._origin_ok() or not self.path.startswith(prefix):
                    self._send(404, "Not found")
                    return
                length = min(int(self.headers.get("Content-Length") or 0), 10_000)
                form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()}
                method = self.path[len(prefix) :]
                try:
                    with page.client._lock:
                        if method == "browser":
                            message = browser_login(page.client)
                        elif method == "password":
                            page.client.password_login(form.get("email", ""), form.get("password", ""))
                            message = "Logged in."
                        elif method == "cookie":
                            message = (
                                f"Logged in as {page.client.cookie_login({'session_id': form.get('cookie', '')})}."
                            )
                        else:
                            self._send(404, "Not found")
                            return
                except ToolError as e:
                    self._render(str(e), status=400)
                    return
                self._render(f"{message} You can close this tab and go back to your assistant.", forms=False)
                page._finish(message)

        return Handler
