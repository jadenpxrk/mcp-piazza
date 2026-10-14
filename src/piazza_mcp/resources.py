"""MCP resources, so a client can attach the course list or a thread as context."""

from fastmcp import FastMCP

from .client import PiazzaClient
from .models import Course, Thread
from .tools.courses import course_list
from .tools.posts import read_threads


def register(mcp: FastMCP, client: PiazzaClient) -> None:
    @mcp.resource("piazza://courses", mime_type="application/json")
    def courses() -> list[Course]:
        """The user's Piazza courses."""
        return course_list(client)

    @mcp.resource("piazza://courses/{course_id}/posts/{number}", mime_type="application/json")
    def post(course_id: str, number: int) -> Thread:
        """One full Piazza thread."""
        return read_threads(client, course_id, [number])[0]
