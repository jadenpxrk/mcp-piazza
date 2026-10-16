# Changelog

This file follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-15

### Added

- Read-only tools: `list_courses`, `get_course_info`, `get_unread_counts`, `get_course_stats`, `recent_activity`, `list_posts`, `search_posts`, `list_instructor_notes`, `get_post`, `get_posts`, `get_post_history`, and `get_attachment`.
- Prompts: `catch_up`, `before_asking`, and `exam_prep`.
- Agent skills: `piazza-catch-up`, `piazza-before-asking`, and `piazza-exam-prep`. Install them with `npx skills add jadenpxrk/mcp-piazza`.
- Resources: `piazza://courses` and `piazza://courses/{course_id}/posts/{number}`.
- Typed output schemas for all tools that return data.
- Course lookup by ID, course number, or part of the name, with the active term first.
- Search in one course or in all active courses.
- `list_posts` filters: `unread`, `following`, `unresolved`, `unanswered`, `mine`, `starred`, and folders.
- Post summaries with `instructor_endorsed`, `likes`, `stars`, and `starred`, so that the assistant can put important posts first.
- Optional `PIAZZA_KEEP_UNREAD`, which marks posts unread again after the server reads them.
- HTML to markdown-style text, with code blocks, tables, lists, headings, and quotes.
- Local login page. `mcp-piazza login` opens it, and a tool call without a session opens it and returns its link.
- Browser session import with `mcp-piazza login --browser` for Chrome, Arc, Brave, Edge, Firefox, Safari, Chromium, Vivaldi, and Opera.
- Terminal login with `mcp-piazza login --password` and `mcp-piazza login --cookie`, and `mcp-piazza logout`.
- Automatic login again when a session expires, if `PIAZZA_EMAIL` and `PIAZZA_PASSWORD` are set.
- Request throttle (`PIAZZA_MIN_INTERVAL`) and in-memory cache (`PIAZZA_CACHE_TTL`).
- Streamable HTTP transport with `mcp-piazza serve --transport http`.
- Untrusted-text fencing for post text, on by default.
- Optional student pseudonyms with `PIAZZA_ANONYMIZE_STUDENTS`.
- Setup guide for MCP clients.
- Claude Desktop extension manifest and MCP registry metadata.
