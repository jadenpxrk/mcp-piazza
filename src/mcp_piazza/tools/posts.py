from typing import Any, Literal, cast

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..client import PiazzaClient
from ..formatting import clean, collect_uids, is_unresolved
from ..models import CoursePosts, History, MultiCoursePosts, PostList, Thread, ThreadList
from . import FULL_CONTENT, READ_ONLY, clamp, formatter

MAX_BATCH = 20

Filter = Literal["all", "unread", "following", "unresolved", "unanswered", "mine", "starred"]
SERVER_FILTERS = {"unread": "unread", "following": "following", "unanswered": "unanswered", "mine": "my_posts"}


def read_threads(client: PiazzaClient, course: str, numbers: list[int]) -> list[Thread]:
    """Read several threads with one user-name lookup. A post that fails returns an error entry, not a failed call."""
    c = client.resolve(course)
    raw: list[tuple[int, dict[str, Any] | str]] = []
    uids: set[str] = set()
    for n, post in zip(numbers, client.posts(c["id"], numbers), strict=True):
        if isinstance(post, ToolError):
            raw.append((n, str(post)))
            continue
        collect_uids(post, uids)
        raw.append((n, post))
    fmt = formatter(client, c, client.users(c["id"], sorted(uids)))
    return [fmt.thread(p) if isinstance(p, dict) else cast(Thread, {"number": n, "error": p}) for n, p in raw]


def register(mcp: FastMCP, client: PiazzaClient) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def list_posts(
        course: str,
        filter: Filter = "all",
        folder: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PostList:
        """List post summaries for a course, most recent activity first.

        filter: "unread" = posts with content the user has not read. "following" = posts the user follows.
        "unresolved" = unanswered questions and posts with unresolved followups. "unanswered" = questions with
        no answer. "mine" = the user's own posts that show their name. "starred" = posts the user starred.
        folder: only posts in this folder, for example "hw1". list_courses shows the folder names.
        Summaries have a short snippet only. Call get_post or get_posts for full threads.
        """
        c = client.resolve(course)
        nid, limit, offset = c["id"], clamp(limit), max(0, offset)

        if filter == "all" and not folder:
            page = client.feed(nid, limit=limit, offset=offset)
            items = list(page.get("feed", []))
            has_more = bool(page.get("more", len(items) == limit))
        else:
            if filter in SERVER_FILTERS:
                items = client.filtered_feed(nid, SERVER_FILTERS[filter])
            elif filter == "all":
                items = client.filtered_feed(nid, "folder", folder)
            else:  # Piazza has no server filter for these, so read the full feed in one request
                keep = is_unresolved if filter == "unresolved" else lambda i: bool(i.get("my_favorite"))
                items = [i for i in client.full_feed(nid) if keep(i)]
            if folder and filter != "all":
                items = [i for i in items if folder.lower() in (f.lower() for f in i.get("folders") or [])]
            has_more = len(items) > offset + limit
            items = items[offset : offset + limit]

        fmt = formatter(client, c)
        posts = [fmt.summary(i) for i in items]
        return {"course": nid, "offset": offset, "count": len(posts), "has_more": has_more, "posts": posts}

    @mcp.tool(annotations=READ_ONLY)
    def search_posts(query: str, course: str | None = None, limit: int = 20) -> MultiCoursePosts:
        """Search posts by keywords, like the Piazza search box, in one course or in all active courses.

        Use it before the user asks a new question, to find duplicates. Returns post summaries grouped by course.
        """
        limit = clamp(limit)
        courses = [client.resolve(course)] if course else client.courses(active_only=True)
        groups: list[CoursePosts] = []
        for c in courses:
            items = client.search(c["id"], query)[:limit]
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
        return {"query": query, "courses": groups}

    @mcp.tool(annotations=READ_ONLY, meta=FULL_CONTENT)
    def get_post(course: str, number: int) -> Thread:
        """Read one full thread: the question or note, both answers, and followups with replies.

        number is the post number that Piazza shows as @123.
        """
        thread = read_threads(client, course, [number])[0]
        if "error" in thread:
            raise ToolError(thread["error"])
        return thread

    @mcp.tool(annotations=READ_ONLY, meta=FULL_CONTENT)
    def get_posts(course: str, numbers: list[int]) -> ThreadList:
        """Read up to 20 full threads from one course in one call. A post that cannot be read has an "error" field."""
        if not numbers:
            raise ToolError("numbers must contain at least one post number.")
        if len(numbers) > MAX_BATCH:
            raise ToolError(f"numbers can contain at most {MAX_BATCH} post numbers.")
        return {"posts": read_threads(client, course, list(dict.fromkeys(numbers)))}

    @mcp.tool(annotations=READ_ONLY, meta=FULL_CONTENT)
    def get_post_history(course: str, number: int, diff: bool = True) -> History:
        """Show every version of a post, oldest first, with author and time.

        With diff=true, version 1 has the full text and each later version has only a diff from the version before.
        Use it to see what an instructor changed in an announcement or a question.
        """
        c = client.resolve(course)
        post = client.posts(c["id"], [number])[0]
        if isinstance(post, ToolError):
            raise post
        users = client.users(c["id"], sorted(collect_uids({"history": post.get("history")})))
        return formatter(client, c, users).history(post, diff)
