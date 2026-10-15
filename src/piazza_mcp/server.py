"""Server entry point and the mcp-piazza command line."""

import argparse
import getpass
import logging
import os
import signal
import sys
import time

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from . import __version__, prompts, resources
from .client import PiazzaClient
from .config import Settings
from .login import BROWSERS, LoginPage, browser_login
from .safety import INSTRUCTIONS
from .tools import register_all

RESTORE_WAIT = 30  # seconds to wait for "mark unread" requests on SIGTERM

SERVER_INSTRUCTIONS = (
    "Read-only access to the user's Piazza courses. "
    "Tools accept a course ID, a course number such as 'CSE 12', or part of the course name. "
    "Use recent_activity, list_posts or search_posts to find posts. "
    "Then use get_post or get_posts to read full threads. " + INSTRUCTIONS
)


def build_server(client: PiazzaClient) -> FastMCP:
    mcp = FastMCP("piazza", instructions=SERVER_INSTRUCTIONS, version=__version__)
    page = LoginPage(client)
    client.login_page = page.start  # a missing session opens the login page instead of failing with a command
    register_all(mcp, client)
    resources.register(mcp, client)
    prompts.register(mcp)
    return mcp


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mcp-piazza", description="Read-only MCP server for Piazza.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="Run the MCP server. This is the default.")
    serve.add_argument("--transport", choices=["stdio", "http"], default="stdio", help="Default: stdio.")
    serve.add_argument("--host", default="127.0.0.1", help="HTTP host. Default: 127.0.0.1.")
    serve.add_argument("--port", type=int, default=8000, help="HTTP port. Default: 8000.")
    login = sub.add_parser("login", help="Log in to Piazza and save the session. Opens a login page by default.")
    how = login.add_mutually_exclusive_group()
    how.add_argument(
        "--browser",
        nargs="?",
        const="any",
        choices=["any", *BROWSERS],
        help="Copy the session from a browser where you are logged in to piazza.com. Default: try all browsers.",
    )
    how.add_argument("--password", action="store_true", help="Enter your email and password in the terminal.")
    how.add_argument("--cookie", action="store_true", help="Paste the session_id cookie from your browser.")
    sub.add_parser("logout", help="Delete the saved session.")
    args = parser.parse_args(argv)

    logging.basicConfig(stream=sys.stderr, level=logging.INFO)  # stdout carries the MCP protocol
    try:
        settings = Settings.from_env()
    except ValueError as e:
        parser.error(str(e))
    client = PiazzaClient(settings)

    if args.command == "login":
        try:
            if args.browser:
                print(browser_login(client, None if args.browser == "any" else args.browser))
            elif args.cookie:
                print(f"Logged in as {client.cookie_login({'session_id': getpass.getpass('session_id cookie: ')})}.")
            elif args.password:
                email = settings.email or input("Piazza email: ")
                client.password_login(email, getpass.getpass("Piazza password: "))
            else:
                page = LoginPage(client)
                print(f"Opening the login page: {page.start()}")
                print("Waiting for you to log in. Press Ctrl+C to stop.")
                page.done.wait()
                print(page.result)
        except ToolError as e:
            sys.exit(str(e))
        except KeyboardInterrupt:
            sys.exit(1)
        print(f"Saved the session to {settings.cookie_file}")
        return
    if args.command == "logout":
        settings.cookie_file.unlink(missing_ok=True)
        print(f"Deleted {settings.cookie_file}")
        return

    def on_sigterm(*_: object) -> None:
        # Let background "mark unread" requests finish. Then exit at once: a normal exit waits for the stdin thread.
        deadline = time.monotonic() + RESTORE_WAIT
        for thread in client.restore_threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        os._exit(0)

    signal.signal(signal.SIGTERM, on_sigterm)
    if getattr(args, "transport", "stdio") == "http":
        if args.host not in ("127.0.0.1", "localhost", "::1"):
            logging.warning(
                "The HTTP server has no authentication. Anyone who can reach %s can read your Piazza.", args.host
            )
        build_server(client).run(transport="http", host=args.host, port=args.port)
    else:
        build_server(client).run()


if __name__ == "__main__":
    main()
