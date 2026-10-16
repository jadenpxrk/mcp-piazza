import json
import sys
import types
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from fastmcp.exceptions import ToolError

from mcp_piazza.client import PiazzaClient
from mcp_piazza.config import Settings
from mcp_piazza.login import LoginPage, browser_login


class Cookie:
    def __init__(self, name: str, value: str, domain: str = ".piazza.com") -> None:
        self.name, self.value, self.domain = name, value, domain


@pytest.fixture
def fake_browsers(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace browser_cookie3 with stub browsers. Each value is a cookie list or an exception."""
    browsers: dict[str, Any] = {}
    module = types.ModuleType("browser_cookie3")

    def make(name: str) -> Any:
        def load(domain_name: str = "") -> list[Cookie]:
            value = browsers.get(name, FileNotFoundError("no profile"))
            if isinstance(value, Exception):
                raise value
            return value

        return load

    for name in ("chrome", "arc", "brave", "edge", "firefox", "safari", "chromium", "vivaldi", "opera"):
        setattr(module, name, make(name))
    monkeypatch.setitem(sys.modules, "browser_cookie3", module)
    return browsers


def make_client(tmp_path: Path, accepted: set[str]) -> PiazzaClient:
    c = PiazzaClient(Settings(cookie_file=tmp_path / "cookies.json"))

    def status() -> dict[str, str]:
        if c.rpc.get_cookies().get("session_id") not in accepted:
            raise ValueError("not logged in")
        return {"name": "Jae"}

    c.piazza.get_user_status = status  # type: ignore[method-assign]
    return c


def test_browser_login_uses_the_first_valid_session(tmp_path: Path, fake_browsers: dict[str, Any]) -> None:
    fake_browsers["chrome"] = PermissionError("keychain refused")
    fake_browsers["arc"] = [Cookie("session_id", "expired")]
    fake_browsers["firefox"] = [
        Cookie("session_id", "good"),
        Cookie("other", "x"),
        Cookie("session_id", "no", "evil.com"),
        Cookie("tracker", "no", ".notpiazza.com"),
    ]
    c = make_client(tmp_path, accepted={"good"})
    assert browser_login(c) == "Logged in as Jae with the firefox session."
    assert json.loads(c.settings.cookie_file.read_text()) == {"session_id": "good", "other": "x"}


def test_browser_login_without_a_session_explains(tmp_path: Path, fake_browsers: dict[str, Any]) -> None:
    fake_browsers["safari"] = [Cookie("other", "x")]
    with pytest.raises(ToolError, match="Log in at https://piazza.com in your browser"):
        browser_login(make_client(tmp_path, accepted=set()), "safari")


def request(url: str, data: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> tuple[int, str]:
    body = "&".join(f"{k}={v}" for k, v in (data or {}).items()).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_login_page_cookie_flow(tmp_path: Path) -> None:
    c = make_client(tmp_path, accepted={"good"})
    page = LoginPage(c)
    url = page.start(open_browser=False)
    status, body = request(url)
    assert status == 200 and "Use my browser session" in body and "Use email and password" in body

    status, body = request(url + "/cookie", {"cookie": "bad"})
    assert status == 400 and "did not accept" in body and not page.done.is_set()

    status, body = request(url + "/cookie", {"cookie": "good"})
    assert status == 200 and "Logged in as Jae" in body
    assert page.done.wait(2) and c.settings.cookie_file.exists()


def test_login_page_rejects_wrong_token_host_and_origin(tmp_path: Path) -> None:
    page = LoginPage(make_client(tmp_path, accepted={"good"}))
    url = page.start(open_browser=False)
    base = url.rsplit("/", 1)[0]
    assert request(base + "/wrong-token")[0] == 404
    assert request(url, headers={"Host": "evil.example"})[0] == 404
    assert request(url + "/cookie", {"cookie": "good"}, {"Origin": "https://evil.example"})[0] == 404
    assert not page.done.is_set()
    page._finish("test cleanup")


def test_missing_session_points_to_the_login_page(tmp_path: Path) -> None:
    c = PiazzaClient(Settings(cookie_file=tmp_path / "missing.json"))
    c.login_page = lambda: "http://127.0.0.1:1234/token"
    with pytest.raises(ToolError, match="Open this link to log in, then try again: http://127.0.0.1:1234/token"):
        c.call(lambda: "never")
