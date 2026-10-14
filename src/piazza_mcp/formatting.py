"""Turn raw Piazza feed items, posts and courses into compact, typed, model-friendly dicts."""

import difflib
import json
from dataclasses import dataclass, field
from typing import Any, cast

from .config import Settings
from .models import Answer, CourseInfo, Discussion, History, PostSummary, StaffMember, Thread, Version
from .safety import fence, fence_inline, pseudonym
from .text import to_text


def post_url(nid: str, nr: Any) -> str:
    return f"https://piazza.com/class/{nid}/post/{nr}"


def clean(d: dict[str, Any]) -> dict[str, Any]:
    """Drop empty values so the model only sees fields that carry information."""
    return {k: v for k, v in d.items() if v not in (None, [], "", {})}


def tags(item: dict[str, Any]) -> list[str]:
    return list(item.get("tags") or [])


def is_pinned(item: dict[str, Any]) -> bool:
    return bool(item.get("pin")) or "pin" in tags(item) or item.get("bucket_name") == "Pinned"


def is_unanswered(item: dict[str, Any]) -> bool:
    return bool(item.get("no_answer")) or "unanswered" in tags(item)


def is_unresolved(item: dict[str, Any]) -> bool:
    return is_unanswered(item) or bool(item.get("no_answer_followup"))


def is_instructor_note(item: dict[str, Any]) -> bool:
    return "instructor-note" in tags(item)


def _as_text(value: Any) -> str:
    """Render a course-page field of unknown shape (string, list or dict) as text."""
    if not value:
        return ""
    if isinstance(value, str):
        return to_text(value)
    if isinstance(value, list):
        return "\n\n".join(t for t in (_as_text(v) for v in value) if t)
    if isinstance(value, dict):
        if "content" in value:
            title = to_text(value.get("title") or value.get("subject") or "")
            body = to_text(value.get("content"))
            return f"{title}\n{body}" if title else body
        return "\n".join(f"{k}: {_as_text(v)}" for k, v in value.items() if v)
    return json.dumps(value)


@dataclass
class Formatter:
    settings: Settings
    nid: str
    staff: dict[str, Any] = field(default_factory=dict)  # instructor and TA user IDs for this course
    my_uid: str | None = None
    users: dict[str, dict[str, Any]] = field(default_factory=dict)

    def _block(self, text: str) -> str:
        return fence(text) if self.settings.fence_content else text

    def _inline(self, text: str) -> str:
        return fence_inline(text) if self.settings.fence_content else text

    def person(self, uid: str | None, anon: str | None = "no", name: str | None = None, role: str | None = None) -> str:
        if anon not in ("no", None):
            return "Anonymous"
        if not uid:
            return name or "unknown"
        if uid == self.my_uid:
            return "you"
        user = self.users.get(uid, {})
        is_staff = uid in self.staff or role == "instructor"
        role = "instructor" if is_staff else role or user.get("role")
        if self.settings.anonymize_students and not is_staff:
            return pseudonym(uid)
        name = name or user.get("name") or "unknown"
        return f"{name} ({role})" if role else name

    def endorsers(self, node: dict[str, Any]) -> list[str] | None:
        out = [self.person(t.get("id"), "no", t.get("name"), t.get("role")) for t in node.get("tag_good") or []]
        return out or None

    def summary(self, item: dict[str, Any]) -> PostSummary:
        return cast(
            PostSummary,
            clean(
                {
                    "number": item.get("nr"),
                    "subject": self._inline(to_text(item.get("subject"))),
                    "snippet": self._inline(to_text(item.get("content_snipet"))),
                    "type": item.get("type"),
                    "folders": item.get("folders"),
                    "updated": item.get("updated") or item.get("modified"),
                    "pinned": is_pinned(item) or None,
                    "unread": bool(item.get("is_new")) or None,
                    "instructor_note": is_instructor_note(item) or None,
                    "has_instructor_answer": bool(item.get("has_i")) or None,
                    "has_student_answer": bool(item.get("has_s")) or None,
                    "unanswered": is_unanswered(item) or None,
                    "unresolved_followups": item.get("no_answer_followup") or None,
                    "instructor_endorsed": bool(item.get("tag_endorse_prof") or item.get("tag_good_prof")) or None,
                    "likes": item.get("gd") or None,
                    "stars": item.get("num_favorites") or None,
                    "starred": bool(item.get("my_favorite")) or None,
                    "views": item.get("unique_views"),
                    "url": post_url(self.nid, item.get("nr")),
                }
            ),
        )

    def _answer(self, child: dict[str, Any]) -> Answer:
        hist = child.get("history") or [{}]
        editor = (child.get("config") or {}).get("editor")
        return cast(
            Answer,
            clean(
                {
                    "author": self.person(hist[0].get("uid"), hist[0].get("anon")),
                    "updated": hist[0].get("created"),
                    "content": self._block(to_text(hist[0].get("content"), editor)),
                    "endorsed_by": self.endorsers(child),
                    "edits": len(hist) - 1 or None,
                }
            ),
        )

    def _discussion(self, child: dict[str, Any]) -> Discussion:
        editor = (child.get("config") or {}).get("editor")
        out = {
            "author": self.person(child.get("uid"), child.get("anon")),
            "created": child.get("created"),
            "content": self._block(to_text(child.get("subject"), editor)),
            "endorsed_by": self.endorsers(child),
            "replies": [self._discussion(c) for c in child.get("children") or []] or None,
        }
        if child.get("type") == "followup":
            out["resolved"] = not child.get("no_answer")
        return cast(Discussion, clean(out))

    def _author(self, post: dict[str, Any]) -> str:
        first = (post.get("history") or [{}])[-1]
        return "you" if post.get("my_post") else self.person(first.get("uid"), first.get("anon"))

    def thread(self, post: dict[str, Any]) -> Thread:
        hist = post.get("history") or [{}]
        editor = (post.get("config") or {}).get("editor")
        children = post.get("children") or []
        i_ans = next((c for c in children if c.get("type") == "i_answer"), None)
        s_ans = next((c for c in children if c.get("type") == "s_answer"), None)
        poll = None
        if post.get("type") == "poll":  # the poll format is not documented, so pass on what Piazza sends
            poll = {k: v for k, v in (post.get("data") or {}).items() if k != "embed_links"} or None
        return cast(
            Thread,
            clean(
                {
                    "course": self.nid,
                    "number": post.get("nr"),
                    "url": post_url(self.nid, post.get("nr")),
                    "type": post.get("type"),
                    "subject": self._inline(to_text(hist[0].get("subject"))),
                    "content": self._block(to_text(hist[0].get("content"), editor)),
                    "author": self._author(post),
                    "created": post.get("created"),
                    "updated": hist[0].get("created"),
                    "edits": len(hist) - 1 or None,
                    "folders": post.get("folders"),
                    "tags": post.get("tags"),
                    "status": post.get("status"),
                    "views": post.get("unique_views"),
                    "endorsed_by": self.endorsers(post),
                    "instructor_answer": self._answer(i_ans) if i_ans else None,
                    "student_answer": self._answer(s_ans) if s_ans else None,
                    "discussion": [
                        self._discussion(c) for c in children if c.get("type") not in ("i_answer", "s_answer")
                    ]
                    or None,
                    "poll": poll,
                }
            ),
        )

    def history(self, post: dict[str, Any], diff: bool) -> History:
        """All versions of the main post, oldest first. Each later version has a diff from the version before it."""
        editor = (post.get("config") or {}).get("editor")
        versions: list[Version] = []
        previous: list[str] | None = None
        for i, h in enumerate(reversed(post.get("history") or [])):
            content = to_text(h.get("content"), editor)
            lines = content.splitlines()
            delta = ""
            if diff and previous is not None:
                delta = "\n".join(difflib.unified_diff(previous, lines, f"v{i}", f"v{i + 1}", lineterm="", n=1))
            previous = lines
            versions.append(
                cast(
                    Version,
                    clean(
                        {
                            "version": i + 1,
                            "author": "you" if post.get("my_post") else self.person(h.get("uid"), h.get("anon")),
                            "created": h.get("created"),
                            "subject": self._inline(to_text(h.get("subject"))),
                            "content": self._block(content) if not delta else None,
                            "diff": self._block(delta) if delta else None,
                        }
                    ),
                )
            )
        return cast(
            History,
            {
                "course": self.nid,
                "number": post.get("nr"),
                "url": post_url(self.nid, post.get("nr")),
                "versions": versions,
            },
        )

    def course_info(self, c: dict[str, Any]) -> CourseInfo:
        staff = [
            cast(StaffMember, clean({"name": p.get("name"), "role": p.get("role"), "email": p.get("email")}))
            for p in c.get("profs") or []
        ]
        sections = [s.get("title") or s.get("name") for s in (c.get("config") or {}).get("resource_sections") or []]
        return cast(
            CourseInfo,
            clean(
                {
                    "id": c.get("id"),
                    "number": c.get("course_number"),
                    "name": c.get("name"),
                    "term": c.get("term"),
                    "school": c.get("school"),
                    "department": c.get("department"),
                    "start_date": c.get("start_date"),
                    "end_date": c.get("end_date") if isinstance(c.get("end_date"), str) else None,
                    "active": c.get("status", "active") == "active",
                    "students": c.get("user_count"),
                    "description": self._block(_as_text(c.get("course_description"))),
                    "syllabus": self._block(_as_text(c.get("syllabus"))),
                    "office_hours": self._block(_as_text(c.get("office_hours"))),
                    "general_information": self._block(_as_text(c.get("general_information"))),
                    "folders": c.get("folders"),
                    "resource_sections": [s for s in sections if s],
                    "staff": staff,
                    "url": f"https://piazza.com/class/{c.get('id')}",
                }
            ),
        )


def collect_uids(node: dict[str, Any], acc: set[str] | None = None) -> set[str]:
    acc = set() if acc is None else acc
    for h in node.get("history") or []:
        if h.get("uid"):
            acc.add(h["uid"])
    if node.get("uid"):
        acc.add(node["uid"])
    for c in node.get("children") or []:
        collect_uids(c, acc)
    return acc
