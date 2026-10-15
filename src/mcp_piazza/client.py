"""Authenticated access to Piazza through the unofficial piazza-api client."""

import json
import logging
import os
import re
import threading
import time
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

from fastmcp.exceptions import ToolError
from piazza_api import Piazza
from piazza_api.exceptions import AuthenticationError, RequestError
from piazza_api.network import Network
from piazza_api.rpc import PiazzaRPC

from .config import Settings

log = logging.getLogger("mcp_piazza")
T = TypeVar("T")

LOGIN_CMD = "mcp-piazza login"
FULL_FEED = 999_999  # Piazza returns the whole feed for a large limit, in one request
RETRY_DELAY = 1.0


def piazza_reason(e: Exception) -> str:
    """Piazza's own error message, without the raw response that piazza-api adds."""
    text = str(e)
    try:
        reason = json.loads(text.partition("Response: ")[2]).get("error")
    except (ValueError, AttributeError):
        reason = None
    return str(reason or text.splitlines()[0] if text else type(e).__name__)


class PiazzaClient:
    """One Piazza session for the process. Every Network shares the RPC session, so a new login updates all of them."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.rpc = PiazzaRPC()
        self.piazza = Piazza(self.rpc)
        self._lock = threading.Lock()
        self._throttle_lock = threading.Lock()
        self._last_request = 0.0
        self._logged_in = False
        self._status: dict[str, Any] | None = None
        self._cache: dict[Hashable, tuple[float, Any]] = {}
        self._users: dict[str, dict[str, Any]] = {}
        self.restore_threads: list[threading.Thread] = []  # background "mark unread" runs
        self.login_page: Callable[[], str] | None = None  # starts the local login page and returns its URL

    # Authentication

    def save_cookies(self) -> None:
        path = self.settings.cookie_file
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.rpc.get_cookies(), f)
        os.chmod(path, 0o600)

    def password_login(self, email: str, password: str) -> None:
        self.rpc.session.cookies.clear()  # an old cookie with the same name causes a CookieConflictError
        try:
            self.rpc.user_login(email=email, password=password)
        except AuthenticationError as e:
            log.warning("password login failed: %s", e)
            reason = str(e).splitlines()[-1].strip().rstrip(".")  # Piazza's own message, without the HTML page
            if len(reason) > 120 or "<" in reason:
                reason = "Piazza rejected the email or password"
            raise ToolError(f"Login failed: {reason}. Check the email and password, then try again.") from e
        self.save_cookies()
        self._logged_in = True
        log.info("logged in; session saved to %s", self.settings.cookie_file)

    def cookie_login(self, cookies: dict[str, str]) -> str:
        """Use piazza.com cookies from a browser (this works for SSO accounts). Returns the account name."""
        cookies = {k: v.strip() for k, v in cookies.items() if v and v.strip()}
        if not cookies.get("session_id"):
            raise ToolError("The session_id cookie is empty.")
        self.rpc.session.cookies.clear()
        self.rpc.set_cookies(cookies)
        try:
            status = self.piazza.get_user_status()
        except (RequestError, ValueError) as e:
            self.rpc.session.cookies.clear()
            log.warning("session cookie rejected: %s", e)
            raise ToolError(
                "Piazza did not accept the session cookie. It is possibly expired. "
                "Log in at piazza.com again, then try again."
            ) from e
        self.save_cookies()
        self._logged_in = True
        return str(status.get("name") or status.get("email") or "unknown")

    def _login(self, use_saved: bool) -> None:
        s = self.settings
        if use_saved and s.cookie_file.exists():
            try:
                cookies = json.loads(s.cookie_file.read_text())
            except (OSError, ValueError) as e:
                raise ToolError(f"Cannot read {s.cookie_file}: {e}. Run: {LOGIN_CMD}") from e
            self.rpc.set_cookies(cookies)
            self._logged_in = True
        elif s.email and s.password:
            self.password_login(s.email, s.password)
        else:
            raise ToolError(self.login_help("No Piazza session."))

    def login_help(self, problem: str) -> str:
        if self.login_page:
            return f"{problem} Open this link to log in, then try again: {self.login_page()}"
        return f"{problem} Run this command in a terminal, then try again: {LOGIN_CMD}"

    # Request control

    def _throttle(self) -> None:
        """Keep at least min_interval seconds between requests. Piazza blocks clients that send too fast."""
        with self._throttle_lock:
            wait = self._last_request + self.settings.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    def call(self, fn: Callable[[], T]) -> T:
        """Run one Piazza request. If it fails and the session expired, log in again and retry once.

        An expired session looks like any other error, so a failure first checks the session.
        """
        with self._lock:
            if not self._logged_in:
                self._login(use_saved=True)
        try:
            self._throttle()
            return fn()
        except (RequestError, ValueError) as e:  # ValueError: the reply was not JSON
            first_error = e
        if self._session_ok():
            raise ToolError(f"Piazza request failed: {piazza_reason(first_error)}") from first_error
        log.warning("Piazza request failed (%s); logging in again", first_error)
        try:
            with self._lock:
                self._login(use_saved=False)
        except ToolError as e:
            raise ToolError(
                self.login_help(f"Piazza request failed: {piazza_reason(first_error)}. The session probably expired.")
            ) from e
        time.sleep(RETRY_DELAY)
        try:
            self._throttle()
            return fn()
        except (RequestError, ValueError) as e:
            raise ToolError(f"Piazza request failed: {piazza_reason(e)}") from e

    def _session_ok(self) -> bool:
        try:
            self._throttle()
            self.piazza.get_user_status()
        except (RequestError, ValueError):
            return False
        return True

    def cached(self, key: Hashable, fn: Callable[[], T]) -> T:
        ttl = self.settings.cache_ttl
        now = time.monotonic()
        hit = self._cache.get(key)
        if ttl and hit and hit[0] > now:
            value: T = hit[1]
            return value
        value = self.call(fn)
        if ttl:
            self._cache[key] = (now + ttl, value)
        return value

    # Courses

    def status(self, refresh: bool = False) -> dict[str, Any]:
        if self._status is None or refresh:
            self._status = self.call(self.piazza.get_user_status)
            if refresh:
                self._cache.clear()
        return self._status

    @property
    def my_uid(self) -> str | None:
        return self.status().get("id")

    def courses(self, refresh: bool = False, active_only: bool = False) -> list[dict[str, Any]]:
        courses = list(self.status(refresh).get("networks", []))
        if active_only:
            courses = [c for c in courses if c.get("status", "active") == "active"]
        return courses

    def resolve(self, course: str) -> dict[str, Any]:
        """Find a course by ID, course number ('CSE 12', 'cse12'), or part of its name."""
        q = course.strip().lower()
        courses = self.courses()
        for c in courses:
            if c.get("id", "").lower() == q:
                return c

        def squash(s: str | None) -> str:
            return re.sub(r"\s+", "", (s or "").lower())

        matches = [
            c
            for c in courses
            if (q and squash(q) in squash(c.get("course_number"))) or (q and q in (c.get("name") or "").lower())
        ]
        if len(matches) > 1:
            active = [c for c in matches if c.get("status", "active") == "active"]
            matches = active if len(active) == 1 else matches
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ToolError(f"No course matches {course!r}. Call list_courses to see the available courses.")
        options = "; ".join(f"{c['id']} = {c.get('course_number')} {c.get('name')} ({c.get('term')})" for c in matches)
        raise ToolError(f"{course!r} matches more than one course. Use one of these IDs: {options}")

    # Network requests. Each lambda builds the Network inside the retry, so the retry uses the new session.

    def _net(self, nid: str) -> Network:
        return self.piazza.network(nid)

    def feed(self, nid: str, limit: int, offset: int = 0) -> dict[str, Any]:
        """One feed page, newest activity first. The result has "feed" (items) and "more" (bool)."""
        return self.cached(("feed", nid, limit, offset), lambda: self._net(nid).get_feed(limit=limit, offset=offset))

    def full_feed(self, nid: str) -> list[dict[str, Any]]:
        return list(self.feed(nid, FULL_FEED).get("feed", []))

    def filtered_feed(self, nid: str, kind: str, folder: str | None = None) -> list[dict[str, Any]]:
        """A server-side feed filter, with the names the Piazza website uses: unread, following, unanswered,
        instructors, my_posts, or folder. piazza-api is not used here because its "unread" filter sends "updated".
        """
        params: dict[str, Any] = {"folder": 1, "filter_folder": folder} if kind == "folder" else {kind: 1}
        return list(self.cached(("filter", nid, kind, folder), lambda: self._filter_feed(nid, params)).get("feed", []))

    def _filter_feed(self, nid: str, params: dict[str, Any]) -> dict[str, Any]:
        res = self.rpc.request("network.filter_feed", {"sort": "updated", **params}, nid=nid)
        result: dict[str, Any] = self.rpc._handle_error(res, f"Piazza feed filter {params} failed")
        return result

    def search(self, nid: str, query: str) -> list[dict[str, Any]]:
        res = self.cached(("search", nid, query), lambda: self._net(nid).search_feed(query))
        return list(res if isinstance(res, list) else res.get("feed", []))

    def posts(self, nid: str, numbers: list[int]) -> list[dict[str, Any] | ToolError]:
        """Read full posts. Piazza marks a post as read when it sends it.

        With keep_unread, posts that were unread before are marked unread again in a background thread,
        so the result does not wait for those requests. A post that cannot be read gives a ToolError in its place.
        """
        was_unread: set[int] = set()
        if self.settings.keep_unread and not all(self._fresh(("post", nid, n)) for n in numbers):
            feed = self.call(lambda: self._filter_feed(nid, {"unread": 1})).get("feed", [])
            was_unread = {i.get("nr") for i in feed}
        out: list[dict[str, Any] | ToolError] = []
        restore: list[tuple[int, str]] = []
        for n in numbers:
            fetched = not self._fresh(("post", nid, n))
            try:
                post = self.cached(("post", nid, n), lambda: self._net(nid).get_post(n))  # noqa: B023 - runs now
            except ToolError as e:
                out.append(e)
                continue
            out.append(post)
            if fetched and n in was_unread and post.get("id"):
                restore.append((n, post["id"]))
        if restore:
            # Not a daemon thread: Python waits for it at exit, so a client that closes right after a read
            # does not leave these posts marked read.
            thread = threading.Thread(target=self._mark_unread, args=(nid, restore))
            thread.start()
            self.restore_threads = [t for t in self.restore_threads if t.is_alive()] + [thread]
        return out

    def _mark_unread(self, nid: str, posts: list[tuple[int, str]]) -> None:
        # Not inside call(): its retry could read nothing new, and a relogin here must not race the main thread.
        for number, cid in posts:
            try:
                self._throttle()
                res = self.rpc.request("content.mark_unread", {"cid": cid}, nid=nid)
                self.rpc._handle_error(res, "content.mark_unread failed")
            except (RequestError, ValueError, OSError) as e:
                log.warning("could not mark @%s unread again: %s", number, e)

    def _fresh(self, key: Hashable) -> bool:
        hit = self._cache.get(key)
        return bool(self.settings.cache_ttl and hit and hit[0] > time.monotonic())

    def users(self, nid: str, uids: list[str]) -> dict[str, dict[str, Any]]:
        """Return users by ID, from memory where possible. Names are optional, so a failure returns what is known."""
        missing = [u for u in uids if u not in self._users]
        if missing:
            try:
                for u in self.call(lambda: self._net(nid).get_users(missing)):
                    self._users[u["id"]] = u
            except ToolError as e:
                log.warning("could not load user names: %s", e)
        return {u: self._users[u] for u in uids if u in self._users}

    def stats(self, nid: str) -> dict[str, Any]:
        return self.cached(("stats", nid), lambda: self._net(nid).get_statistics())

    def download(self, url: str, max_bytes: int) -> tuple[bytes, str]:
        """Download a file with the session cookies. Returns the bytes and the content type."""

        def run() -> tuple[bytes, str]:
            with self.rpc.session.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                data = b""
                for chunk in r.iter_content(64 * 1024):
                    data += chunk
                    if len(data) > max_bytes:
                        raise ToolError(f"The file is larger than {max_bytes // 1_000_000} MB.")
                return data, r.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()

        with self._lock:
            if not self._logged_in:
                self._login(use_saved=True)
        self._throttle()
        try:
            return run()
        except OSError as e:  # requests errors are OSError subclasses
            raise ToolError(f"Download failed: {e}") from e
