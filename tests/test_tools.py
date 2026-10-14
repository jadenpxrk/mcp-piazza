import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from conftest import make_client
from piazza_mcp.safety import FENCE_END, FENCE_START
from piazza_mcp.server import build_server
from piazza_mcp.tools.activity import parse_since

EXPECTED_TOOLS = {
    "list_courses", "get_course_info", "get_unread_counts", "get_course_stats",
    "list_posts", "search_posts", "get_post", "get_posts", "get_post_history",
    "recent_activity", "list_instructor_notes", "get_attachment",
}  # fmt: skip


async def call(mcp: Client, name: str, **args: Any) -> Any:
    res = await mcp.call_tool(name, args)
    data = res.structured_content
    return data["result"] if set(data) == {"result"} else data


def unfence(s: str) -> str:
    if s.startswith(FENCE_START):
        return s[len(FENCE_START) + 1 : -len(FENCE_END) - 1]
    return s.removeprefix("<<<untrusted: ").removesuffix(">>>")


async def test_every_tool_is_read_only(mcp: Client) -> None:
    tools = await mcp.list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOLS
    assert all(t.annotations.read_only_hint for t in tools)


async def test_typed_tools_publish_output_schemas(mcp: Client) -> None:
    tools = {t.name: t for t in await mcp.list_tools()}
    assert "posts" in tools["list_posts"].output_schema["properties"]
    assert tools["get_attachment"].output_schema is None


async def test_list_courses(mcp: Client) -> None:
    courses = await call(mcp, "list_courses")
    assert courses[0] == {"id": "abc123", "number": "CSE 12", "name": "Data Structures", "term": "Fall 2026",
                          "role": "student", "active": True, "folders": ["hw1", "exam", "logistics"]}  # fmt: skip
    assert courses[2]["active"] is False


async def test_course_number_prefers_the_active_term(mcp: Client) -> None:
    out = await call(mcp, "list_posts", course="CSE 12", limit=1)
    assert out["course"] == "abc123"


async def test_get_course_info(mcp: Client) -> None:
    info = await call(mcp, "get_course_info", course="cse12")
    assert unfence(info["description"]) == "Lists, trees & graphs."
    assert unfence(info["syllabus"]) == "Read the syllabus (https://piazza.com/syllabus.pdf)."
    assert unfence(info["office_hours"]) == "Dr. P: Mon 2-3pm\nTia: Wed 4-5pm"
    assert unfence(info["general_information"]) == "Grading\n50% exams"
    assert info["resource_sections"] == ["General Resources", "hw"]
    assert info["staff"][1] == {"name": "Tia", "role": "ta", "email": "tia@school.edu"}
    assert info["students"] == 300 and info["active"] is True


async def test_get_unread_counts_skips_inactive(mcp: Client, client) -> None:
    out = await call(mcp, "get_unread_counts")
    assert out == {"total": 2, "courses": [
        {"course": "abc123", "number": "CSE 12", "name": "Data Structures", "unread": 1},
        {"course": "def456", "number": "ECON 1", "name": "Microeconomics", "unread": 1},
    ]}  # fmt: skip
    assert client.calls.count(("filter_feed", "unread")) == 2


async def test_list_posts_all_uses_server_paging(mcp: Client, client) -> None:
    out = await call(mcp, "list_posts", course="abc123", limit=2, offset=1)
    assert [p["number"] for p in out["posts"]] == [7, 5] and out["has_more"] is True
    assert client.calls == [("get_feed", 2, 1)]
    p = out["posts"][0]
    assert unfence(p["subject"]) == "HW1 & tests" and unfence(p["snippet"]) == "Why does test 3 fail?"
    assert p["unread"] is True and p["unanswered"] is True and p["url"].endswith("/abc123/post/7")


async def test_summary_flags_come_from_tags(mcp: Client) -> None:
    out = await call(mcp, "list_posts", course="abc123", limit=1)
    assert out["posts"][0]["pinned"] is True and out["posts"][0]["instructor_note"] is True


async def test_list_posts_filters(mcp: Client, client) -> None:
    unresolved = await call(mcp, "list_posts", course="abc123", filter="unresolved")
    assert [p["number"] for p in unresolved["posts"]] == [7, 3]
    unread_hw = await call(mcp, "list_posts", course="abc123", filter="unread", folder="HW1")
    assert [p["number"] for p in unread_hw["posts"]] == [7]
    unanswered = await call(mcp, "list_posts", course="abc123", filter="unanswered")
    assert [p["number"] for p in unanswered["posts"]] == [7]
    starred = await call(mcp, "list_posts", course="abc123", filter="starred")
    assert [p["number"] for p in starred["posts"]] == [5]
    p = starred["posts"][0]
    assert (p["starred"], p["stars"], p["likes"], p["instructor_endorsed"]) == (True, 4, 2, True)
    assert (await call(mcp, "list_posts", course="abc123", filter="mine"))["posts"] == []
    assert ("filter_feed", "unread") in client.calls and ("filter_feed", "my_posts") in client.calls
    exam = await call(mcp, "list_posts", course="abc123", folder="exam")
    assert [p["number"] for p in exam["posts"]] == [5] and exam["has_more"] is False


async def test_search_posts_one_course_and_all(mcp: Client) -> None:
    one = await call(mcp, "search_posts", query="exam", course="ECON 1")
    assert [g["course"] for g in one["courses"]] == ["def456"]
    every = await call(mcp, "search_posts", query="exam")
    assert [g["course"] for g in every["courses"]] == ["abc123", "def456"]
    assert every["courses"][0]["posts"][0]["number"] == 5


async def test_get_post_thread(mcp: Client, client) -> None:
    p = await call(mcp, "get_post", course="abc123", number=7)
    assert unfence(p["content"]) == "Why does `vector<int>` fail?\n\nlog (https://piazza.com/redirect/x)"
    assert p["author"] == "Sam (student)" and p["edits"] == 1
    ans = p["instructor_answer"]
    assert ans["author"] == "Dr. P (instructor)" and unfence(ans["content"]) == "Use size_t."
    assert ans["endorsed_by"] == ["Ann (student)"]
    fu = p["discussion"][0]
    assert fu["author"] == "Anonymous" and unfence(fu["content"]) == "Still fails\non Mac" and fu["resolved"] is False
    assert [r["author"] for r in fu["replies"]] == ["Sam (student)", "Tia (instructor)", "you"]
    assert sum(1 for c in client.calls if c[0] == "get_users") == 1


async def test_poll_data_is_passed_on(mcp: Client) -> None:
    p = await call(mcp, "get_post", course="abc123", number=11)
    assert p["type"] == "poll" and p["poll"] == {"options": ["Mon", "Tue"], "votes": [3, 5]}


async def test_get_post_missing(mcp: Client) -> None:
    res = await mcp.call_tool("get_post", {"course": "abc123", "number": 404}, raise_on_error=False)
    assert res.is_error and "cannot be found" in res.content[0].text


async def test_get_posts_batch_keeps_going_after_an_error(mcp: Client) -> None:
    out = await call(mcp, "get_posts", course="abc123", numbers=[7, 404, 7])
    assert [p["number"] for p in out["posts"]] == [7, 404]
    assert "error" in out["posts"][1]


async def test_get_posts_limits(mcp: Client) -> None:
    res = await mcp.call_tool("get_posts", {"course": "abc123", "numbers": list(range(21))}, raise_on_error=False)
    assert res.is_error and "at most 20" in res.content[0].text


async def test_get_post_history(mcp: Client) -> None:
    h = await call(mcp, "get_post_history", course="abc123", number=7)
    v1, v2 = h["versions"]
    assert v1["version"] == 1 and unfence(v1["content"]) == "Why does it fail?" and "diff" not in v1
    assert unfence(v2["subject"]) == "HW1 & tests" and "content" not in v2
    assert "-Why does it fail?\n+Why does `vector<int>` fail?" in unfence(v2["diff"])
    full = await call(mcp, "get_post_history", course="abc123", number=7, diff=False)
    assert all("content" in v for v in full["versions"])


async def test_anonymize_students_and_no_fence(tmp_path: Path) -> None:
    client = make_client(tmp_path, anonymize_students=True, fence_content=False)
    async with Client(build_server(client)) as mcp:
        p = await call(mcp, "get_post", course="abc123", number=7)
    dumped = json.dumps(p)
    assert p["author"].startswith("Student ") and "Sam (" not in dumped and "Ann (" not in dumped
    assert p["instructor_answer"]["author"] == "Dr. P (instructor)"
    assert "Tia (instructor)" in dumped
    assert p["content"].startswith("Why does")


async def test_recent_activity_skips_inactive_courses(mcp: Client) -> None:
    out = await call(mcp, "recent_activity", since="2026-10-01T00:00:00+00:00")
    assert [c["course"] for c in out["courses"]] == ["abc123", "def456"]
    assert [p["number"] for p in out["courses"][0]["posts"]] == [7, 5]
    with_old = await call(mcp, "recent_activity", since="2026-10-01T00:00:00+00:00", include_inactive=True)
    assert [c["course"] for c in with_old["courses"]] == ["abc123", "def456", "old789"]


async def test_recent_activity_pages_until_older_post(tmp_path: Path) -> None:
    feed = [{"nr": n, "subject": "s", "updated": "2026-10-10T00:00:00Z"} for n in range(150)]
    feed.append({"nr": 999, "subject": "old", "updated": "2020-01-01T00:00:00Z"})
    client = make_client(tmp_path, feed=feed)
    async with Client(build_server(client)) as mcp:
        out = await call(mcp, "recent_activity", since="2026-10-01", course="abc123", limit=200)
    assert out["courses"][0]["count"] == 150
    assert [c for c in client.calls if c[0] == "get_feed"] == [("get_feed", 100, 0), ("get_feed", 100, 100)]


async def test_list_instructor_notes(mcp: Client) -> None:
    out = await call(mcp, "list_instructor_notes", course="abc123")
    assert [p["number"] for p in out["posts"]] == [9, 5]
    assert all(p["instructor_note"] for p in out["posts"])


async def test_cache_reuses_full_feed(tmp_path: Path) -> None:
    client = make_client(tmp_path, cache_ttl=60)
    async with Client(build_server(client)) as mcp:
        await call(mcp, "list_posts", course="abc123", filter="starred")
        await call(mcp, "list_posts", course="abc123", filter="unresolved")
    assert sum(1 for c in client.calls if c[0] == "get_feed") == 1


async def test_get_attachment_rejects_other_hosts(mcp: Client) -> None:
    for url in ("https://evil.example/x.png", "http://piazza.com/x.png", "https://piazza.com.evil.example/x"):
        res = await mcp.call_tool("get_attachment", {"url": url}, raise_on_error=False)
        assert res.is_error and "only reads https links on piazza.com" in res.content[0].text


async def test_get_attachment_image_text_and_file(mcp: Client, client, monkeypatch: pytest.MonkeyPatch) -> None:
    files = {
        "https://piazza.com/redirect/s3?p=a.png": (b"\x89PNG fake", "image/png"),
        "https://cdn-uploads.piazza.com/notes.txt": (b"hello", "text/plain"),
        "https://piazza.com/doc.pdf": (b"%PDF-1.7", "application/pdf"),
    }
    monkeypatch.setattr(client, "download", lambda url, max_bytes: files[url])
    img = await mcp.call_tool("get_attachment", {"url": "/redirect/s3?p=a.png"})
    assert img.content[0].type == "image" and img.content[0].mime_type == "image/png"
    txt = await mcp.call_tool("get_attachment", {"url": "https://cdn-uploads.piazza.com/notes.txt"})
    assert unfence(txt.content[0].text) == "hello"
    pdf = await mcp.call_tool("get_attachment", {"url": "https://piazza.com/doc.pdf"})
    assert pdf.content[0].type == "resource"


async def test_unknown_course_error(mcp: Client) -> None:
    res = await mcp.call_tool("list_posts", {"course": "nope"}, raise_on_error=False)
    assert res.is_error and "No course matches" in res.content[0].text


async def test_resources(mcp: Client) -> None:
    courses = json.loads((await mcp.read_resource("piazza://courses"))[0].text)
    assert courses[1]["id"] == "def456"
    post = json.loads((await mcp.read_resource("piazza://courses/abc123/posts/7"))[0].text)
    assert post["number"] == 7


async def test_prompts(mcp: Client) -> None:
    names = {p.name for p in await mcp.list_prompts()}
    assert names == {"catch_up", "before_asking", "exam_prep"}
    msg = await mcp.get_prompt("catch_up", {"since": "3d"})
    assert "recent_activity" in msg.messages[0].content.text and "'3d'" in msg.messages[0].content.text


def test_parse_since() -> None:
    now = datetime(2026, 10, 11, 12, tzinfo=UTC)
    assert parse_since("24h", now) == datetime(2026, 10, 10, 12, tzinfo=UTC)
    assert parse_since("2w", now) == datetime(2026, 9, 27, 12, tzinfo=UTC)
    assert parse_since("2026-10-01T00:00:00Z", now) == datetime(2026, 10, 1, tzinfo=UTC)
    assert parse_since("2026-10-01", now).tzinfo is not None
    with pytest.raises(ToolError, match="since must be"):
        parse_since("last week", now)


async def test_keep_unread_marks_only_unread_posts_unread_again(tmp_path: Path) -> None:
    client = make_client(tmp_path, keep_unread=True)
    async with Client(build_server(client)) as mcp:
        out = await call(mcp, "get_posts", course="abc123", numbers=[7, 11])
    assert [p["number"] for p in out["posts"]] == [7, 11]
    assert client.restore_thread is not None and not client.restore_thread.daemon  # Python waits for it at exit
    client.restore_thread.join(5)
    assert [c for c in client.calls if c[0] == "mark_unread"] == [("mark_unread", "cid7")]


async def test_keep_unread_skips_cached_posts(tmp_path: Path) -> None:
    client = make_client(tmp_path, keep_unread=True, cache_ttl=60)
    async with Client(build_server(client)) as mcp:
        await call(mcp, "get_posts", course="abc123", numbers=[7])
        assert client.restore_thread is not None
        client.restore_thread.join(5)
        before = len(client.calls)
        await call(mcp, "get_post", course="abc123", number=7)
    assert not [c for c in client.calls[before:] if c[0] in ("filter_feed", "get_post", "mark_unread")]


async def test_default_never_marks_unread(mcp: Client, client) -> None:
    await call(mcp, "get_posts", course="abc123", numbers=[7, 11])
    assert not any(c[0] in ("mark_unread", "filter_feed") for c in client.calls)
