# AGENTS.md

This file is for AI agents and people who work on this repository.
For tool usage, see [docs/tools.md](docs/tools.md).

## Layout

```text
src/piazza_mcp/
  server.py       Command line (serve, login, logout) and build_server()
  config.py       Settings from environment variables
  client.py       PiazzaClient: login, saved session, throttle, cache, retry, course resolution, requests
  models.py       TypedDict output types; FastMCP turns them into output schemas
  formatting.py   Feed items, posts, and courses to typed, model-friendly dicts
  text.py         Piazza HTML to markdown-style text (stdlib HTMLParser)
  safety.py       Untrusted-text fences and student pseudonyms
  login.py        Browser session import and the local login page
  prompts.py      MCP prompts
  resources.py    MCP resources
  tools/          courses.py, posts.py, activity.py, files.py; register(mcp, client) adds the tools
skills/           Agent skills; each one matches a prompt in prompts.py
tests/            Offline tests; conftest.py has the stub Piazza data
```

## Commands

```bash
uv sync
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
```

CI runs all of these on Python 3.11, 3.12, and 3.13.

## Rules

- The server is read-only. Do not add tools that change Piazza data. Every tool uses `annotations=READ_ONLY`.
- The only write is `content.mark_unread` in `PiazzaClient._mark_unread`. It runs only when `PIAZZA_KEEP_UNREAD=true`, and only on posts that were unread before the server read them.
- Send all Piazza requests through `PiazzaClient.call` or `PiazzaClient.cached`. They throttle requests. When a request fails, they check the session, and they log in again and retry one time if it expired.
- Build the `Network` object inside the function that `call` runs. A new login replaces the session cookies, and the retry must use them.
- Format all text that course members write with `Formatter`. It applies fencing and pseudonyms. Do not return raw post text.
- Write logs to stderr only. Stdout carries the MCP protocol.
- Tests must not contact Piazza. Add stub data to `tests/conftest.py`.
- Raise `ToolError` with a message that tells the user what to do.
- Declare every output key in `models.py`. FastMCP drops keys that the TypedDict does not declare. Import `TypedDict` from `typing_extensions`.
- `get_attachment` must send cookies only to `https` URLs on `piazza.com`. Keep `check_url` in front of every download.
- When you change a prompt in `prompts.py`, change the matching skill in `skills/`.
- Pin GitHub Actions to a commit SHA, with the version in a comment.
- The login page binds to `127.0.0.1` only and checks the token, `Host`, and `Origin`. Keep all three checks.

## Add a tool

1. Add the function to the correct module in `tools/`, in its `register` function.
2. Use `@mcp.tool(annotations=READ_ONLY)`. Add `meta=FULL_CONTENT` if the tool returns full threads. Give it a return type from `models.py`.
3. Write the docstring for the model: what the tool returns and when to use it.
4. Add the tool name to `EXPECTED_TOOLS` in `tests/test_tools.py`, and add a test.
5. Add the tool to `README.md`, `docs/tools.md`, and the `tools` list in `manifest.json`.

## Data shapes

Piazza has no API documentation. The method and field names come from the code of the Piazza website and from real responses.
The [piazza-api data dictionary](https://github.com/hfaran/piazza-api/blob/develop/data_descriptions/Piazza_API_Post_Data_Dictionary.md) describes post fields.
Feed items mark pinned, unanswered, and instructor posts with `tags` and `bucket_name`.
Feed filter names come from the Piazza website code: `unread`, `following`, `unanswered`, `instructors`, `my_posts`, and `folder`.
Do not use the piazza-api `unread` filter. It sends `updated`, which also includes read posts with old changes.
Read fields with `.get()`, because Piazza can leave out any field.

## Release

1. Change the version in `src/piazza_mcp/__init__.py`, `manifest.json`, and both fields in `server.json`. CI checks that they agree.
2. Add an entry to `CHANGELOG.md`.
3. Push a tag such as `v0.2.0`. The publish workflow publishes to PyPI and the MCP registry, and attaches `piazza-mcp.mcpb` to a GitHub release.
