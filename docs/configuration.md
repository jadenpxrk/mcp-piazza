# Configuration

The server reads all settings from environment variables.
If a value is not valid, the server stops and shows the variable name.

| Variable | Default | Values |
|---|---|---|
| `PIAZZA_EMAIL` | none | Your Piazza account email. |
| `PIAZZA_PASSWORD` | none | Your Piazza account password. |
| `PIAZZA_COOKIE_FILE` | `~/.config/piazza-mcp/cookies.json` | A file path. |
| `PIAZZA_ANONYMIZE_STUDENTS` | `false` | `true`, `false`, `1`, `0`, `yes`, `no`, `on`, `off`. |
| `PIAZZA_FENCE_CONTENT` | `true` | The same values as `PIAZZA_ANONYMIZE_STUDENTS`. |
| `PIAZZA_KEEP_UNREAD` | `false` | The same values as `PIAZZA_ANONYMIZE_STUDENTS`. See [Keep posts unread](#keep-posts-unread). |
| `PIAZZA_MIN_INTERVAL` | `0.5` | Seconds between Piazza requests, from `0` to `10`. |
| `PIAZZA_CACHE_TTL` | `60` | Seconds to keep feeds and posts in memory, from `0` to `3600`. `0` turns off the cache. |

## Keep posts unread

Piazza marks a post as read when the server reads the full post, as the website does.
Thus, if the assistant reads 40 posts for you, Piazza shows the 40 posts as read.

Set `PIAZZA_KEEP_UNREAD=true` to prevent this.
Before the server reads posts, it gets the list of your unread posts.
After it reads a post from that list, it marks the post unread again.
The server sends these requests in the background, so the result does not wait for them.
This setting adds one request for each `get_post` or `get_posts` call, and one request for each unread post.
Posts in the cache need no requests.
When the client stops the server, the server sends the remaining requests before it stops.
Only a forced stop, such as a crash or `kill -9`, can leave some posts read.

This is the only change that the server can make to Piazza data. The server never changes posts that you already read.
Piazza still counts one view for each post that the server reads.

## Request rate and cache

Piazza can block an account that sends many requests quickly.
The server waits `PIAZZA_MIN_INTERVAL` seconds between requests, and it waits 1 second before a retry.
For example, `get_posts` with 20 posts takes about 10 seconds with the default value.

The server keeps feeds, search results, and posts in memory for `PIAZZA_CACHE_TTL` seconds.
Thus, a second question about the same course in one conversation does not send the same requests again.
`list_courses` with `refresh=true` clears the cache.

## Automatic login with a password

With these variables, the server logs in again by itself when the session expires.
The password is in plain text in the configuration file, so keep the file private.

```json
{
  "mcpServers": {
    "piazza": {
      "command": "uvx",
      "args": ["mcp-piazza"],
      "env": {
        "PIAZZA_EMAIL": "you@school.edu",
        "PIAZZA_PASSWORD": "your-password"
      }
    }
  }
}
```

## More than one Piazza account

Give each account its own session file:

```bash
PIAZZA_COOKIE_FILE=~/.config/piazza-mcp/ta.json uvx mcp-piazza login
claude mcp add --env PIAZZA_COOKIE_FILE=$HOME/.config/piazza-mcp/ta.json --transport stdio piazza-ta -- uvx mcp-piazza
```

## Command line

```text
mcp-piazza                                   Run the MCP server on stdio.
mcp-piazza serve                             Run the MCP server on stdio.
mcp-piazza serve --transport http            Run the MCP server on http://127.0.0.1:8000/mcp.
mcp-piazza serve --transport http --port N   Use port N.
mcp-piazza login                             Open the login page in your browser and wait for the login.
mcp-piazza login --browser                   Copy the Piazza session from any browser where you are logged in.
mcp-piazza login --browser chrome            Copy the session from one browser: chrome, arc, brave, edge, firefox, safari, chromium, vivaldi, opera.
mcp-piazza login --password                  Enter your email and password in the terminal. Uses PIAZZA_EMAIL if it is set.
mcp-piazza login --cookie                    Paste the session_id cookie from your browser.
mcp-piazza logout                            Delete the saved session.
mcp-piazza --version                         Show the version.
```

The HTTP transport has no authentication.
If you set `--host` to an address other than `127.0.0.1`, `localhost`, or `::1`, other computers can read your Piazza data, and the server shows a warning.
