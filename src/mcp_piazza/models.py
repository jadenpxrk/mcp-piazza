"""Typed tool outputs. MCP clients receive these as output schemas.

FastMCP drops keys that a TypedDict does not declare, so every key that a tool returns must be declared here.
Optional keys use total=False because the server leaves out empty values.
"""

from typing import Any, NotRequired

from typing_extensions import TypedDict  # pydantic needs typing_extensions.TypedDict on Python < 3.12


class Course(TypedDict, total=False):
    id: str
    number: str
    name: str
    term: str
    role: str
    active: bool
    folders: list[str]


class PostSummary(TypedDict, total=False):
    number: int
    subject: str
    snippet: str
    type: str
    folders: list[str]
    updated: str
    pinned: bool
    unread: bool
    instructor_note: bool
    has_instructor_answer: bool
    has_student_answer: bool
    unanswered: bool
    unresolved_followups: int
    instructor_endorsed: bool
    likes: int
    stars: int
    starred: bool
    views: int
    url: str


class PostList(TypedDict):
    course: str
    count: int
    posts: list[PostSummary]
    offset: NotRequired[int]
    has_more: NotRequired[bool]
    query: NotRequired[str]


class CoursePosts(TypedDict, total=False):
    course: str
    number: str
    name: str
    count: int
    posts: list[PostSummary]


class MultiCoursePosts(TypedDict, total=False):
    since: str
    query: str
    courses: list[CoursePosts]


class Answer(TypedDict, total=False):
    author: str
    updated: str
    content: str
    endorsed_by: list[str]
    edits: int


class Discussion(TypedDict, total=False):
    author: str
    created: str
    content: str
    endorsed_by: list[str]
    resolved: bool
    replies: list["Discussion"]


class Thread(TypedDict, total=False):
    course: str
    number: int
    url: str
    type: str
    subject: str
    content: str
    author: str
    created: str
    updated: str
    edits: int
    folders: list[str]
    tags: list[str]
    status: str
    views: int
    endorsed_by: list[str]
    instructor_answer: Answer
    student_answer: Answer
    discussion: list[Discussion]
    poll: dict[str, Any]
    error: str


class ThreadList(TypedDict):
    posts: list[Thread]


class Version(TypedDict, total=False):
    version: int
    author: str
    created: str
    subject: str
    content: str
    diff: str


class History(TypedDict, total=False):
    course: str
    number: int
    url: str
    versions: list[Version]


class StaffMember(TypedDict, total=False):
    name: str
    role: str
    email: str


class CourseInfo(TypedDict, total=False):
    id: str
    number: str
    name: str
    term: str
    school: str
    department: str
    start_date: str
    end_date: str
    active: bool
    students: int
    description: str
    syllabus: str
    office_hours: str
    general_information: str
    folders: list[str]
    resource_sections: list[str]
    staff: list[StaffMember]
    url: str


class UnreadCount(TypedDict, total=False):
    course: str
    number: str
    name: str
    unread: int


class UnreadCounts(TypedDict):
    total: int
    courses: list[UnreadCount]
