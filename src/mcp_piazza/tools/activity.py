import re
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..client import PiazzaClient
from ..formatting import clean, is_pinned
from ..models import CoursePosts, MultiCoursePosts, PostList
from . import READ_ONLY, clamp, formatter

PAGE = 100
MAX_PAGES = 10
_UNITS = {"h": "hours", "d": "days", "w": "weeks"}


def parse_since(since: str, now: datetime) -> datetime:
    """Accept a relative age such as 24h, 7d or 2w, or an ISO date or datetime.

    A value without a time zone uses local time.
    """
    m = re.fullmatch(r"(\d+)\s*([hdw])", since.strip().lower())
    if m:
        return now - timedelta(**{_UNITS[m[2]]: int(m[1])})
    try:
        dt = datetime.fromisoformat(since.strip())
    except ValueError as e:
        raise ToolError("since must be a value like 24h, 7d or 2w, or an ISO date like 2026-10-01.") from e
    return dt if dt.tzinfo else dt.astimezone()


def _updated(item: dict[str, Any]) -> datetime | None:
    raw = item.get("updated") or item.get("modified")
    try:
        return datetime.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def recent_items(client: PiazzaClient, nid: str, cutoff: datetime, limit: int) -> list[dict[str, Any]]:
    """Read the feed page by page, newest first, until a post that is not pinned is older than the cutoff."""
    out: list[dict[str, Any]] = []
    for page_no in range(MAX_PAGES):
        page = client.feed(nid, limit=PAGE, offset=page_no * PAGE)
        items = page.get("feed", [])
        reached_older = False
        for item in items:
            ts = _updated(item)
            if ts and ts >= cutoff:
                out.append(item)
            elif ts and not is_pinned(item):
                reached_older = True
        if reached_older or not page.get("more", len(items) == PAGE) or len(out) >= limit:
            break
    return out[:limit]


def register(mcp: FastMCP, client: PiazzaClient) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def recent_activity(
        since: str = "7d", course: str | None = None, limit: int = 50, include_inactive: bool = False
    ) -> MultiCoursePosts:
        """List posts with new activity since a time, in all active courses or in one course.

        since: a relative age such as 24h, 7d or 2w, or an ISO date such as 2026-10-01. The default is 7d.
        Use this tool for questions such as "what did I miss this week". Courses without activity are left out.
        """
        cutoff = parse_since(since, datetime.now(UTC))
        limit = clamp(limit)
        courses = [client.resolve(course)] if course else client.courses(active_only=not include_inactive)
        groups: list[CoursePosts] = []
        for c in courses:
            items = recent_items(client, c["id"], cutoff, limit)
            if items:
                fmt = formatter(client, c)
                group = {
                    "course": c["id"],
                    "number": c.get("course_number"),
                    "name": c.get("name"),
                    "count": len(items),
                    "posts": [fmt.summary(i) for i in items],
                }
                groups.append(cast(CoursePosts, clean(group)))
        return {"since": cutoff.isoformat(), "courses": groups}

    @mcp.tool(annotations=READ_ONLY)
    def list_instructor_notes(course: str, limit: int = 20) -> PostList:
        """List notes and polls written by instructors, such as announcements and logistics, most recent first."""
        c = client.resolve(course)
        items = client.filtered_feed(c["id"], "instructors")
        has_more = len(items) > clamp(limit)
        items = items[: clamp(limit)]
        fmt = formatter(client, c)
        return {"course": c["id"], "count": len(items), "has_more": has_more, "posts": [fmt.summary(i) for i in items]}
