# piazza-mcp

<!-- mcp-name: io.github.jadenpxrk/piazza-mcp -->

[![CI](https://github.com/jadenpxrk/piazza-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/jadenpxrk/piazza-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mcp-piazza)](https://pypi.org/project/mcp-piazza/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-piazza)](https://pypi.org/project/mcp-piazza/)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/jadenpxrk/piazza-mcp/badge)](https://scorecard.dev/viewer/?uri=github.com/jadenpxrk/piazza-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

A read-only [Model Context Protocol](https://modelcontextprotocol.io) server for [Piazza](https://piazza.com).
It works with every MCP client: Claude Code, Claude Desktop, Cursor, VS Code, Windsurf, Zed, Cline, Codex, Gemini CLI, Goose, opencode, JetBrains, LM Studio, Continue, and others.

Ask your assistant about your courses:

- "What did I miss on Piazza this week?"
- "Are there unresolved questions about HW3 in CSE 12?"
- "Did anyone already ask about the midterm room?"
- "When are the TA office hours?"
- "What did the instructor change in @142?"

The server only reads data. It cannot post, edit, endorse, or delete.

## Quick start

1. Install [uv](https://docs.astral.sh/uv/).
2. Log in one time. The command opens a login page in your browser:

   ```bash
   uvx mcp-piazza login
   ```

   You can also skip this step. If the server has no session, the first tool call opens the same page and shows its link.

3. Add the server to your client. The server command is `uvx` with the argument `mcp-piazza`. For example:

   ```bash
   claude mcp add --scope user --transport stdio piazza -- uvx mcp-piazza   # Claude Code
   codex mcp add piazza -- uvx mcp-piazza                                   # Codex CLI
   ```

   See [docs/clients.md](docs/clients.md) for Claude Desktop, Cursor, VS Code, Windsurf, Zed, Gemini CLI, and other clients.

4. Ask: "List my Piazza courses."

## Tools, prompts and resources

| Tool | Purpose |
|---|---|
| `list_courses` | List your courses with ID, course number, term, role, active status, and folders. |
| `get_course_info` | Get the course page: description, syllabus, office hours, general information, and staff with emails. |
| `get_unread_counts` | Count unread posts in each active course. |
| `recent_activity` | List posts with new activity since a time (`24h`, `7d`, `2026-10-01`), in all active courses or one course. |
| `list_posts` | List post summaries. Filters: `all`, `unread`, `following`, `unresolved`, `unanswered`, `mine`, `starred`. Optional `folder` and paging. |
| `search_posts` | Search posts by keywords in one course or in all active courses. |
| `get_post` | Read one full thread: question, instructor answer, student answer, followups, replies, and poll data. |
| `get_posts` | Read up to 20 full threads in one call. |
| `get_post_history` | Show every version of a post, with a diff between versions. |
| `list_instructor_notes` | List notes and polls written by instructors. |
| `get_attachment` | Open an image or file from a post. The model can see images. |
| `get_course_stats` | Get the data from the course Statistics page. |

Every tool accepts a course ID, a course number such as `CSE 12` or `cse12`, or part of the course name.

| Prompt | Purpose |
|---|---|
| `catch_up` | Read all posts since a time and summarize them, with actions for you. |
| `before_asking` | Find out if a question was already asked and answered. |
| `exam_prep` | Read all posts about an exam or topic and collect the facts. |

Many clients show prompts as slash commands.

| Skill | Purpose |
|---|---|
| `piazza-catch-up` | The `catch_up` steps, for agents that use skills. |
| `piazza-exam-prep` | The `exam_prep` steps. |
| `piazza-before-asking` | The `before_asking` steps. |

Skills work in Claude Code, Cursor, Codex, opencode, and other agents. They need the server. To install them:

```bash
npx skills add jadenpxrk/piazza-mcp
```

| Resource | Content |
|---|---|
| `piazza://courses` | Your courses |
| `piazza://courses/{course_id}/posts/{number}` | One full thread |

See [docs/tools.md](docs/tools.md) for parameters and output fields, and [docs/workflows.md](docs/workflows.md) for examples.

## Authentication

Piazza has no public API.
This server uses [piazza-api](https://github.com/hfaran/piazza-api), which logs in as the Piazza website does.

| Method | How | Use it when |
|---|---|---|
| Login page | `mcp-piazza login`, or the link from the first tool call | Most people. The page offers the three methods below. |
| Browser session | `mcp-piazza login --browser` | You are logged in to piazza.com in Chrome, Arc, Brave, Edge, Firefox, Safari, Chromium, Vivaldi, or Opera. This works with school SSO. |
| Password | `mcp-piazza login --password` | You want to type your email and password in the terminal. |
| Session cookie | `mcp-piazza login --cookie` | You want to paste the `session_id` cookie from the browser developer tools. |
| Environment variables | `PIAZZA_EMAIL`, `PIAZZA_PASSWORD` | You want automatic login when the session expires. |

All methods save only the session cookies to `~/.config/piazza-mcp/cookies.json` with file mode `600`. They do not save your password.
When the session expires, the next tool call opens the login page again. `mcp-piazza logout` deletes the session.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PIAZZA_EMAIL` | none | Account email for automatic login. |
| `PIAZZA_PASSWORD` | none | Account password for automatic login. |
| `PIAZZA_COOKIE_FILE` | `~/.config/piazza-mcp/cookies.json` | Path of the saved session. |
| `PIAZZA_ANONYMIZE_STUDENTS` | `false` | Replace student names with pseudonyms. |
| `PIAZZA_FENCE_CONTENT` | `true` | Mark post text as untrusted data. |
| `PIAZZA_KEEP_UNREAD` | `false` | Mark unread posts unread again after the server reads them. |
| `PIAZZA_MIN_INTERVAL` | `0.5` | Minimum seconds between Piazza requests. |
| `PIAZZA_CACHE_TTL` | `60` | Seconds to keep feeds and posts in memory. `0` turns off the cache. |

See [docs/configuration.md](docs/configuration.md) for examples and the command line.

## Privacy and safety

- **Read-only.** The server has no tools that change Piazza data. The only write is the optional `PIAZZA_KEEP_UNREAD` restore.
- **Prompt-injection fencing.** Other course members write the post text. The server puts that text between `<<<UNTRUSTED PIAZZA TEXT ...>>>` markers, and the server instructions tell the model to treat it as data.
- **Student pseudonyms.** When `PIAZZA_ANONYMIZE_STUDENTS=true`, other students show as `Student 3f2a1c`. Staff keep their names. Your own posts show as `you`.
- **Local only.** The server runs on your computer. It sends your cookies only to `piazza.com`.

See [docs/privacy.md](docs/privacy.md) for the full model and its limits.

## Development

```bash
uv sync
uv run pytest               # offline tests, no Piazza account needed
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
```

See [AGENTS.md](AGENTS.md) for the project layout and rules.

## Limitations

- Piazza can change its internal API at any time. If tools fail after a Piazza update, see [docs/troubleshooting.md](docs/troubleshooting.md).
- When the server reads a full post, Piazza marks the post as read and counts a view, as the website does. Set `PIAZZA_KEEP_UNREAD=true` to mark unread posts unread again.
- The course page files and links (the Resources tab) are not available. `get_course_info` shows the names of the resource sections only.
- Piazza does not document the poll format. `get_post` returns the poll data as Piazza sends it.
- Some instructors hide the Statistics page. For those courses, `get_course_stats` returns an error.

## License

[MIT](LICENSE). This project is not affiliated with Piazza.
