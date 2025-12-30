"""Claude Code Live - Live-updating transcript viewer for Claude Code sessions."""

import logging
import webbrowser
from pathlib import Path

import click
import uvicorn

from .tailer import find_most_recent_session, find_recent_sessions

__version__ = "0.1.0"

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--session", "-s",
    type=click.Path(exists=True, path_type=Path),
    help="Watch a specific session file (in addition to auto-discovered sessions)",
)
@click.option(
    "--port", "-p",
    type=int,
    default=8765,
    help="Port to run the server on (default: 8765)",
)
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Host to bind to (default: 127.0.0.1)",
)
@click.option(
    "--no-open",
    is_flag=True,
    help="Don't open browser automatically",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
@click.option(
    "--max-sessions",
    type=int,
    default=10,
    help="Maximum number of sessions to track (default: 10)",
)
def main(
    session: Path | None,
    port: int,
    host: str,
    no_open: bool,
    debug: bool,
    max_sessions: int,
) -> None:
    """Start a live-updating transcript viewer for Claude Code sessions.

    Watches Claude Code session files and serves a live-updating HTML view
    with tabs for each session. New messages appear automatically.

    By default, discovers and watches the most recent sessions in
    ~/.claude/projects/. Use --session to add a specific session file.
    """
    # Configure logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Configure server
    from . import server
    server.MAX_SESSIONS = max_sessions

    # If a specific session is provided, add it first
    if session is not None:
        click.echo(f"Watching: {session}")
        server.add_session(session)

    # Check if any sessions were found
    recent = find_recent_sessions(limit=max_sessions)
    if not recent and session is None:
        click.echo("No session files found in ~/.claude/projects/", err=True)
        click.echo("Specify a session file with --session", err=True)
        raise SystemExit(1)

    count = len(recent)
    if session:
        count += 1
    click.echo(f"Found {count} session(s) to watch")

    # Open browser
    url = f"http://{host}:{port}"
    if not no_open:
        click.echo(f"Opening {url} in browser...")
        webbrowser.open(url)
    else:
        click.echo(f"Server running at {url}")

    # Run server
    uvicorn.run(
        server.app,
        host=host,
        port=port,
        log_level="debug" if debug else "warning",
    )


if __name__ == "__main__":
    main()
