"""Stub Piazza data and fixtures. Tests run offline and never contact Piazza.

The data shapes follow the field names that other Piazza clients read from real responses
(hfaran/piazza-api data dictionary, d4l3k/piazza-api Go types).
"""

import copy
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client
from piazza_api.exceptions import RequestError

from piazza_mcp.client import PiazzaClient
from piazza_mcp.config import Settings
from piazza_mcp.server import build_server

STATUS = {
    "id": "me",
    "name": "Me Student",
    "networks": [
        {
            "id": "abc123",
            "name": "Data Structures",
            "course_number": "CSE 12",
            "term": "Fall 2026",
            "status": "active",
            "prof_hash": {"prof1": 1, "ta1": 1},
            "profs": [
                {"id": "prof1", "name": "Dr. P", "role": "professor", "email": "p@school.edu"},
                {"id": "ta1", "name": "Tia", "role": "ta", "email": "tia@school.edu"},
            ],
            "folders": ["hw1", "exam", "logistics"],
            "school": "State U",
            "department": "CSE",
            "start_date": "2026-09-20",
            "user_count": 300,
            "course_description": "<p>Lists, trees &amp; graphs.</p>",
            "syllabus": '<p>Read <a href="/syllabus.pdf">the syllabus</a>.</p>',
            "office_hours": {"Dr. P": "Mon 2-3pm", "Tia": "Wed 4-5pm"},
            "general_information": [{"title": "Grading", "content": "<p>50% exams</p>"}],
            "config": {"resource_sections": [{"name": "general", "title": "General Resources"}, {"name": "hw"}]},
        },
        {
            "id": "def456",
            "name": "Microeconomics",
            "course_number": "ECON 1",
            "term": "Fall 2026",
            "status": "active",
            "prof_hash": {},
        },
        {
            "id": "old789",
            "name": "Data Structures",
            "course_number": "CSE 12",
            "term": "Fall 2025",
            "status": "inactive",
            "prof_hash": {},
        },
    ],
}

FEED = [
    {
        "nr": 9,
        "subject": "Welcome",
        "content_snipet": "Read the syllabus",
        "type": "note",
        "folders": ["logistics"],
        "tags": ["instructor-note", "pin", "logistics"],
        "bucket_name": "Pinned",
        "updated": "2026-09-01T00:00:00Z",
    },
    {
        "nr": 7,
        "subject": "HW1 &amp; tests",
        "content_snipet": "Why does <b>test 3</b> fail?",
        "type": "question",
        "folders": ["hw1"],
        "tags": ["hw1", "student", "unanswered"],
        "is_new": True,
        "updated": "2026-10-10T00:00:00Z",
    },
    {
        "nr": 5,
        "subject": "Exam room",
        "content_snipet": "Room 101",
        "type": "note",
        "folders": ["exam"],
        "tags": ["exam", "instructor-note"],
        "my_favorite": True,
        "num_favorites": 4,
        "gd": 2,
        "tag_endorse_prof": 1,
        "updated": "2026-10-05T00:00:00Z",
    },
    {
        "nr": 3,
        "subject": "Old post",
        "content_snipet": "old",
        "type": "question",
        "folders": ["hw1"],
        "tags": ["student"],
        "no_answer_followup": 1,
        "updated": "2026-08-01T00:00:00Z",
    },
]

POST = {
    "id": "cid7",
    "nr": 7,
    "type": "question",
    "created": "2026-10-09T00:00:00Z",
    "folders": ["hw1"],
    "status": "active",
    "config": {"editor": "rte"},
    "history": [
        {
            "subject": "HW1 &amp; tests",
            "content": '<p>Why does <code>vector&lt;int&gt;</code> fail?</p><p><a href="/redirect/x">log</a></p>',
            "uid": "s1",
            "anon": "no",
            "created": "2026-10-09T01:00:00Z",
        },
        {
            "subject": "HW1",
            "content": "<p>Why does it fail?</p>",
            "uid": "s1",
            "anon": "no",
            "created": "2026-10-09T00:00:00Z",
        },
    ],
    "children": [
        {
            "type": "i_answer",
            "tag_good": [{"id": "s3", "name": "Ann", "role": "student"}],
            "history": [
                {
                    "content": "<p>Use <b>size_t</b>.</p>",
                    "uid": "prof1",
                    "anon": "no",
                    "created": "2026-10-10T00:00:00Z",
                }
            ],
        },
        {
            "type": "followup",
            "subject": "Still fails<br/>on Mac",
            "uid": "s2",
            "anon": "stud",
            "no_answer": 1,
            "created": "2026-10-10T02:00:00Z",
            "children": [
                {
                    "type": "feedback",
                    "subject": "Same here",
                    "uid": "s1",
                    "anon": "no",
                    "created": "2026-10-10T03:00:00Z",
                },
                {
                    "type": "feedback",
                    "subject": "Ask <b>Tia</b>",
                    "uid": "ta1",
                    "anon": "no",
                    "created": "2026-10-10T04:00:00Z",
                },
                {
                    "type": "feedback",
                    "subject": "Fixed it",
                    "uid": "me",
                    "anon": "no",
                    "created": "2026-10-10T05:00:00Z",
                },
            ],
        },
    ],
}

POLL = {
    "id": "cid11",
    "nr": 11,
    "type": "poll",
    "history": [{"subject": "Pick a time", "content": "", "uid": "prof1"}],
    "data": {"embed_links": [], "options": ["Mon", "Tue"], "votes": [3, 5]},
}

USERS = [{"id": "s1", "name": "Sam", "role": "student"}, {"id": "s3", "name": "Ann", "role": "student"}]


class FakeNetwork:
    """Stands in for piazza_api.network.Network. Records calls so tests can check request counts."""

    def __init__(self, calls: list[tuple[Any, ...]], feed: list[dict[str, Any]]) -> None:
        self.calls = calls
        self.feed = feed

    def get_feed(self, limit: int, offset: int) -> dict[str, Any]:
        self.calls.append(("get_feed", limit, offset))
        return {"feed": copy.deepcopy(self.feed[offset : offset + limit]), "more": offset + limit < len(self.feed)}

    def rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Stands in for PiazzaRPC.request."""
        if method == "content.mark_unread":
            self.calls.append(("mark_unread", params["cid"]))
            return {"result": "OK"}
        assert method == "network.filter_feed", method
        return self.filter_feed(params)

    def filter_feed(self, params: dict[str, Any]) -> dict[str, Any]:
        """Stands in for the network.filter_feed RPC."""
        self.calls.append(("filter_feed", *sorted(k for k in params if k not in ("nid", "sort", "filter_folder"))))
        tests = {
            "unread": lambda i: i.get("is_new"),
            "unanswered": lambda i: "unanswered" in i["tags"],
            "instructors": lambda i: {"instructor-note", "instructor-poll"} & set(i["tags"]),
            "folder": lambda i: params.get("filter_folder") in i["folders"],
        }
        keep = next((t for k, t in tests.items() if k in params), lambda i: False)
        return {"result": {"feed": copy.deepcopy([i for i in self.feed if keep(i)])}}

    def search_feed(self, q: str) -> list[dict[str, Any]]:
        self.calls.append(("search_feed", q))
        return [i for i in self.feed if q.lower() in i["subject"].lower()]

    def get_post(self, nr: int) -> dict[str, Any]:
        self.calls.append(("get_post", nr))
        posts = {7: POST, 11: POLL}
        if nr not in posts:
            raise RequestError(
                f"Could not get post {nr}.\n"
                'Response: {"result": null, "error": "The post you are looking for cannot be found"}'
            )
        return copy.deepcopy(posts[nr])

    def get_users(self, uids: list[str]) -> list[dict[str, Any]]:
        self.calls.append(("get_users", tuple(uids)))
        return [u for u in USERS if u["id"] in uids]

    def get_statistics(self) -> dict[str, Any]:
        return {"total_posts": len(self.feed)}


def make_client(tmp_path: Path, feed: list[dict[str, Any]] | None = None, **settings: Any) -> PiazzaClient:
    client = PiazzaClient(Settings(cookie_file=tmp_path / "cookies.json", **settings))
    client._logged_in = True
    client.calls = []  # type: ignore[attr-defined]
    data = FEED if feed is None else feed
    client.piazza.get_user_status = lambda: copy.deepcopy(STATUS)  # type: ignore[method-assign]
    client.piazza.network = lambda nid: FakeNetwork(client.calls, data)  # type: ignore[method-assign,attr-defined]
    client.rpc.request = lambda method, params, nid: FakeNetwork(client.calls, data).rpc(method, params)  # type: ignore[method-assign,attr-defined]
    return client


@pytest.fixture
def client(tmp_path: Path) -> PiazzaClient:
    return make_client(tmp_path)


@pytest.fixture
async def mcp(client: PiazzaClient) -> AsyncIterator[Client]:
    async with Client(build_server(client)) as c:
        yield c
