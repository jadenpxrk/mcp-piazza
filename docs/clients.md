# Client setup

piazza-mcp works with every MCP client that supports local stdio servers.
The server command is `uvx` with the argument `mcp-piazza`.
You do not need credentials in the configuration. If the server has no session, the first tool call opens a login page.

If the client shows `spawn uvx ENOENT` or "command not found", use the full path to `uvx` in `command`.
Run `which uvx` (macOS, Linux) or `where uvx` (Windows) to find it.

## Clients with an add command

```bash
claude mcp add --scope user --transport stdio piazza -- uvx mcp-piazza       # Claude Code
codex mcp add piazza -- uvx mcp-piazza                                       # Codex CLI
gemini mcp add -s user piazza uvx mcp-piazza                                 # Gemini CLI
devin mcp add -s user piazza -- uvx mcp-piazza                               # Windsurf (Devin Local)
code --add-mcp '{"name":"piazza","command":"uvx","args":["mcp-piazza"]}'     # VS Code
```

## Clients with an `mcpServers` file

Add this entry to the file in the table:

```json
{
  "mcpServers": {
    "piazza": {
      "command": "uvx",
      "args": ["mcp-piazza"],
      "env": {}
    }
  }
}
```

| Client | File | Notes |
|---|---|---|
| Claude Desktop | macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`. Windows: `%APPDATA%\Claude\claude_desktop_config.json`. | Use the full path to `uvx`. Restart the app after the change. You can also install `piazza-mcp.mcpb` from the [latest release](https://github.com/jadenpxrk/piazza-mcp/releases/latest). |
| Cursor | `~/.cursor/mcp.json`, or `.cursor/mcp.json` in a project | |
| Windsurf | `~/.config/devin/mcp_config.json` (Devin Local), or `~/.codeium/windsurf/mcp_config.json` (Cascade) | |
| Cline | MCP Servers > Configure > Configure MCP Servers | To skip approval prompts, add tool names to `autoApprove`. |
| Gemini CLI | `~/.gemini/settings.json`, or `.gemini/settings.json` in a project | Gemini CLI removes sensitive variables from the server environment. Put all options in `env`. |
| JetBrains AI Assistant | Settings > Tools > AI Assistant > Model Context Protocol (MCP) > Add | |
| LM Studio | Program tab > Install > Edit mcp.json | Use a model that supports tool calls. |

## Clients with other formats

VS Code (`.vscode/mcp.json`, or "MCP: Open User Configuration") uses the key `servers`:

```json
{ "servers": { "piazza": { "type": "stdio", "command": "uvx", "args": ["mcp-piazza"] } } }
```

Zed (`~/.config/zed/settings.json`) uses the key `context_servers`:

```json
{ "context_servers": { "piazza": { "command": "uvx", "args": ["mcp-piazza"], "env": {} } } }
```

Codex CLI (`~/.codex/config.toml`). The first `uvx` run downloads the package, so increase the start timeout:

```toml
[mcp_servers.piazza]
command = "uvx"
args = ["mcp-piazza"]
startup_timeout_sec = 60
```

opencode (`~/.config/opencode/opencode.json`, or `opencode.json` in a project):

```json
{ "mcp": { "piazza": { "type": "local", "command": ["uvx", "mcp-piazza"], "enabled": true, "environment": {} } } }
```

Goose (`~/.config/goose/config.yaml`), or run `goose configure` and add a command-line extension:

```yaml
extensions:
  piazza:
    name: piazza
    type: stdio
    cmd: uvx
    args: [mcp-piazza]
    enabled: true
    timeout: 300
```

Continue (`.continue/mcpServers/piazza.yaml` in the workspace). The tools work only in agent mode:

```yaml
name: Piazza
version: 0.0.1
schema: v1
mcpServers:
  - name: piazza
    type: stdio
    command: uvx
    args: [mcp-piazza]
```

## Options

Put options in the `env` block of the server entry, for example `"env": {"PIAZZA_KEEP_UNREAD": "true"}`.
In Claude Code, use `--env`: `claude mcp add --env PIAZZA_KEEP_UNREAD=true --transport stdio piazza -- uvx mcp-piazza`.
Some clients do not pass your shell variables to the server, so always use the `env` block.
See [configuration.md](configuration.md) for all options.

## HTTP-only clients

Start the server with the streamable HTTP transport, then connect the client to `http://127.0.0.1:8000/mcp`:

```bash
uvx mcp-piazza serve --transport http --port 8000
```

The HTTP server has no authentication. Keep the default host `127.0.0.1`, so that only your computer can connect.
