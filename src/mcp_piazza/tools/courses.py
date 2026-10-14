from typing import Any, cast

from fastmcp import FastMCP

from ..client import PiazzaClient
from ..formatting import clean
from ..models import Course, CourseInfo, UnreadCount, UnreadCounts
from . import READ_ONLY, formatter


def course_list(client: PiazzaClient, refresh: bool = False) -> list[Course]:
    me = client.my_uid
    return [
        cast(
            Course,
            clean(
                {
                    "id": c.get("id"),
                    "number": c.get("course_number"),
                    "name": c.get("name"),
                    "term": c.get("term"),
                    "role": "instructor" if me in (c.get("prof_hash") or {}) else "student",
                    "active": c.get("status", "active") == "active",
                    "folders": c.get("folders"),
                }
            ),
        )
        for c in client.courses(refresh)
    ]


def register(mcp: FastMCP, client: PiazzaClient) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def list_courses(refresh: bool = False) -> list[Course]:
        """List the user's Piazza courses with ID, course number, term, role, active status, and post folders.

        Other tools accept the ID, the course number, or part of the name. Set refresh=true to reload from Piazza.
        """
        return course_list(client, refresh)

    @mcp.tool(annotations=READ_ONLY)
    def get_course_info(course: str) -> CourseInfo:
        """Get the course page: description, syllabus, office hours, general information, dates, and the staff
        list with names, roles and emails. Use it to find who teaches the course or when office hours are."""
        c = client.resolve(course)
        return formatter(client, c).course_info(c)

    @mcp.tool(annotations=READ_ONLY)
    def get_unread_counts(include_inactive: bool = False) -> UnreadCounts:
        """Count the posts with unread content in each course. Sends one request per course.

        By default only active courses are counted. Courses with no unread posts are left out.
        """
        rows: list[UnreadCount] = []
        for c in client.courses(active_only=not include_inactive):
            n = len(client.filtered_feed(c["id"], "unread"))
            if n:
                rows.append(
                    cast(
                        UnreadCount,
                        clean(
                            {"course": c["id"], "number": c.get("course_number"), "name": c.get("name"), "unread": n}
                        ),
                    )
                )
        return {"total": sum(r["unread"] for r in rows), "courses": rows}

    @mcp.tool(annotations=READ_ONLY)
    def get_course_stats(course: str) -> dict[str, Any]:
        """Get the data from the course Statistics page. Some instructors hide this page from students."""
        return client.stats(client.resolve(course)["id"])
