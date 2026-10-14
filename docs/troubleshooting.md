# Troubleshooting

## "No Piazza session. Open this link to log in"

The server has no saved session and no password.
The server opens a login page in your browser. If no page opens, open the link from the error.
Log in on the page, then ask your assistant again. You do not need to restart the client.

## "The session probably expired"

A request failed and the server could not log in again.
Open the link from the error and log in again, or set `PIAZZA_EMAIL` and `PIAZZA_PASSWORD` to log in automatically.

If you get this error again directly after you log in, the cause is not the session.
Read the Piazza message in the error.
For example, the post number or course ID can be incorrect.

## "Login failed"

- Make sure that the email and password are correct. Log in at piazza.com to test them.
- Piazza can block logins after many attempts. Wait some minutes and try again.

## SSO accounts

Some schools use single sign-on (SSO), and the Piazza account has no password.
Log in to piazza.com in your browser, then click "Use my browser session" on the login page, or run `piazza-mcp login --browser`.

If that does not work, paste the cookie:

1. Open the developer tools. In Chrome and Edge, open Application > Cookies. In Firefox and Safari, open Storage > Cookies.
2. Select `https://piazza.com` and copy the value of `session_id`.
3. On the login page, open "Paste a session cookie" and paste the value. Or run `piazza-mcp login --cookie`.

The server checks the session with Piazza before it saves it.
If you get "Piazza did not accept the session cookie", copy a new value after you log in at piazza.com again.

## "No usable Piazza session" with `--browser`

- Log in at https://piazza.com in the browser, then try again.
- On macOS, click "Allow" when Keychain asks about "Chrome Safe Storage" (or the storage of your browser).
- For Safari, give your terminal app Full Disk Access in System Settings > Privacy & Security.
- Use `--browser NAME` to read one browser, for example `--browser firefox`. The error shows the problem for each browser.

## "No course matches"

Run `list_courses` to see the courses for your account.
If you joined a course recently, use `list_courses` with `refresh=true`.

## "matches more than one course"

The value matches more than one course, for example the same course in two terms.
Use the course ID from the error message.

## `get_course_stats` fails

The instructor can hide the Statistics page from students.
Piazza then refuses the request.

## The server does not start in my MCP client

1. Run `uvx piazza-mcp --version` in a terminal. Make sure that it shows a version.
2. If the client shows `spawn uvx ENOENT` or "command not found", use the full path to `uvx` in the configuration. Run `which uvx` to find it.
3. If the client stops the server during start, increase its start timeout. The first `uvx` run downloads the package. In Codex CLI, set `startup_timeout_sec = 60`.
4. Read the logs of your MCP client. The server writes errors to stderr.

See [clients.md](clients.md) for the setup of each client.

## Responses are slow

The server waits `PIAZZA_MIN_INTERVAL` seconds (default `0.5`) between requests, so that Piazza does not block your account.
Tools that read many posts, such as `get_posts`, take more time.
Do not set the value to `0` for normal use.

## Many requests fail

Piazza can refuse requests for some time when an account sends too many.
Stop for some minutes. Then set `PIAZZA_MIN_INTERVAL` to `1` or more.

## A tool shows old data

The server keeps results for `PIAZZA_CACHE_TTL` seconds (default `60`).
Wait for that time, or call `list_courses` with `refresh=true` to clear the cache.

## `get_attachment` fails

- The tool reads only `https` links on `piazza.com`. Use the URL from an `[image: ...]` marker or a post link.
- The maximum size is 10 MB, and 5 MB for images.
- If the client does not show a PDF, the client does not support embedded files.
