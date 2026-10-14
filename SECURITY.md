# Security policy

## Report a problem

Do not open a public issue for a security problem.
Use [GitHub private vulnerability reporting](https://github.com/jadenpxrk/piazza-mcp/security/advisories/new).
Include the steps to cause the problem and the version of piazza-mcp.

## Scope

These problems are in scope:

- A change to Piazza data, other than the `PIAZZA_KEEP_UNREAD` restore of unread posts.
- Post text that gets out of the untrusted-text fence.
- Student names in the output when `PIAZZA_ANONYMIZE_STUDENTS=true`, other than names in post text.
- Credentials or cookies in logs or tool output.
- A session file that other users can read.

See [docs/privacy.md](docs/privacy.md) for the safety model and its known limits.
