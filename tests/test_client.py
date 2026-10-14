import json
import stat
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError
from piazza_api.exceptions import RequestError

from mcp_piazza.client import LOGIN_CMD, PiazzaClient
from mcp_piazza.config import Settings


def test_resolve(client: PiazzaClient) -> None:
    assert client.resolve("abc123")["id"] == "abc123"
    assert client.resolve("cse12")["id"] == "abc123"
    assert client.resolve(" CSE 12 ")["id"] == "abc123"
    assert client.resolve("micro")["id"] == "def456"
    with pytest.raises(ToolError, match="No course matches"):
        client.resolve("phys")
    with pytest.raises(ToolError, match="more than one course"):
        client.resolve("c")


def test_cookies_are_saved_private_and_reloaded(tmp_path: Path) -> None:
    c = PiazzaClient(Settings(cookie_file=tmp_path / "sub" / "cookies.json"))
    c.rpc.session.cookies.set("session_id", "abc", domain="piazza.com")
    c.save_cookies()
    assert stat.S_IMODE(c.settings.cookie_file.stat().st_mode) == 0o600

    fresh = PiazzaClient(c.settings)
    assert fresh.call(lambda: "ok") == "ok"
    assert fresh.rpc.get_cookies() == {"session_id": "abc"}


def test_no_session_and_no_password_asks_for_login(tmp_path: Path) -> None:
    c = PiazzaClient(Settings(cookie_file=tmp_path / "missing.json"))
    with pytest.raises(ToolError, match=LOGIN_CMD):
        c.call(lambda: "never")


def test_corrupt_cookie_file(tmp_path: Path) -> None:
    path = tmp_path / "cookies.json"
    path.write_text("{not json")
    with pytest.raises(ToolError, match="Cannot read"):
        PiazzaClient(Settings(cookie_file=path)).call(lambda: "never")


def test_expired_session_logs_in_again_with_password(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cookies.json"
    path.write_text(json.dumps({"session_id": "old"}))
    c = PiazzaClient(Settings(cookie_file=path, email="a@b.c", password="pw"))
    logins: list[str] = []

    def fake_login(email: str, password: str) -> None:
        logins.append(email)
        c.rpc.session.cookies.set("session_id", "new", domain="piazza.com")

    monkeypatch.setattr(c.rpc, "user_login", fake_login)
    attempts = iter([RequestError("not logged in"), "data"])

    def request() -> str:
        result = next(attempts)
        if isinstance(result, Exception):
            raise result
        return result

    assert c.call(request) == "data"
    assert logins == ["a@b.c"]
    assert json.loads(path.read_text()) == {"session_id": "new"}


def test_expired_session_without_password_explains_fix(tmp_path: Path) -> None:
    path = tmp_path / "cookies.json"
    path.write_text("{}")
    c = PiazzaClient(Settings(cookie_file=path))

    def request() -> None:
        raise RequestError("not logged in")

    with pytest.raises(ToolError, match=f"not logged in.*{LOGIN_CMD}"):
        c.call(request)


def test_throttle_spaces_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c = PiazzaClient(Settings(cookie_file=tmp_path / "c.json", min_interval=0.5))
    c._logged_in = True
    clock = [100.0]
    sleeps: list[float] = []
    monkeypatch.setattr("mcp_piazza.client.time.monotonic", lambda: clock[0])

    def fake_sleep(s: float) -> None:
        sleeps.append(round(s, 3))
        clock[0] += s

    monkeypatch.setattr("mcp_piazza.client.time.sleep", fake_sleep)
    c.call(lambda: 1)
    clock[0] += 0.2
    c.call(lambda: 2)
    assert sleeps == [0.3]


def test_cache_expires(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c = PiazzaClient(Settings(cookie_file=tmp_path / "c.json", cache_ttl=60))
    c._logged_in = True
    clock = [0.0]
    monkeypatch.setattr("mcp_piazza.client.time.monotonic", lambda: clock[0])
    calls: list[int] = []

    def fetch() -> int:
        calls.append(1)
        return len(calls)

    assert c.cached("k", fetch) == 1 and c.cached("k", fetch) == 1
    clock[0] = 61
    assert c.cached("k", fetch) == 2


def test_cookie_login_saves_the_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c = PiazzaClient(Settings(cookie_file=tmp_path / "c.json"))
    monkeypatch.setattr(c.piazza, "get_user_status", lambda: {"name": "Jae"})
    assert c.cookie_login({"session_id": " abc123 \n"}) == "Jae"
    assert json.loads(c.settings.cookie_file.read_text()) == {"session_id": "abc123"}


def test_cookie_login_rejects_a_bad_cookie(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c = PiazzaClient(Settings(cookie_file=tmp_path / "c.json"))

    def bad() -> None:
        raise RequestError("not logged in")

    monkeypatch.setattr(c.piazza, "get_user_status", bad)
    with pytest.raises(ToolError, match="did not accept"):
        c.cookie_login({"session_id": "nope"})
    assert not c.settings.cookie_file.exists()


def test_download_stops_at_size_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c = PiazzaClient(Settings(cookie_file=tmp_path / "c.json"))
    c._logged_in = True

    class FakeResponse:
        headers = {"Content-Type": "image/png; charset=binary"}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *a: object) -> None:
            pass

        def raise_for_status(self) -> None:
            pass

        def iter_content(self, size: int) -> list[bytes]:
            return [b"x" * 600_000, b"x" * 600_000]

    monkeypatch.setattr(c.rpc.session, "get", lambda *a, **k: FakeResponse())
    assert c.download("https://piazza.com/a.png", 2_000_000) == (b"x" * 1_200_000, "image/png")
    with pytest.raises(ToolError, match="larger than 1 MB"):
        c.download("https://piazza.com/a.png", 1_000_000)
