"""MCP tool registration. Every tool is read-only."""

from typing import Any

from fastmcp import FastMCP

from ..client import PiazzaClient
from ..formatting import Formatter

READ_ONLY: dict[str, Any] = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}

# Claude Code shortens long tool results unless the tool declares a larger limit. Other clients ignore this key.
FULL_CONTENT: dict[str, Any] = {"anthropic/maxResultSizeChars": 500_000}

MAX_LIMIT = 200


def clamp(limit: int, high: int = MAX_LIMIT) -> int:
    return max(1, min(limit, high))


def formatter(
    client: PiazzaClient, course: dict[str, Any], users: dict[str, dict[str, Any]] | None = None
) -> Formatter:
    known = {p["id"]: p for p in course.get("profs") or [] if p.get("id")}  # staff names come with the course
    return Formatter(
        settings=client.settings,
        nid=course["id"],
        staff=course.get("prof_hash") or {},
        my_uid=client.my_uid,
        users=known | (users or {}),
    )


def register_all(mcp: FastMCP, client: PiazzaClient) -> None:
    from . import activity, courses, files, posts

    courses.register(mcp, client)
    posts.register(mcp, client)
    activity.register(mcp, client)
    files.register(mcp, client)
