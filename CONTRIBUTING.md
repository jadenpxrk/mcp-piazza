# Contributing

Bug reports, feature requests, and pull requests are welcome.

## Set up

```bash
git clone https://github.com/jadenpxrk/piazza-mcp
cd piazza-mcp
uv sync
uv run pytest
```

To use your local copy in a client, set the server command to `uv` and the arguments to `run --directory /path/to/piazza-mcp mcp-piazza`.

## Rules

[AGENTS.md](AGENTS.md) has the code layout, the commands, and the rules for this repository. Read it before you change code.
The most important rule: the server is read-only. Do not add tools or requests that change Piazza data.

## Pull requests

1. Make one pull request for each change.
2. Add a test for each change in behavior. Tests must not contact Piazza.
3. Make sure that CI passes.
4. Add an entry to `CHANGELOG.md` if users can see the change.

## Security problems

Do not open a public issue. See [SECURITY.md](SECURITY.md).
