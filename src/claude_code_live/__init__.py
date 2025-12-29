"""Claude Code Live - Live-updating transcript viewer for Claude Code sessions."""

import logging
import webbrowser
from pathlib import Path

import click
import uvicorn

from .tailer import find_most_recent_session

__version__ = "0.1.0"

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--session", "-s",
    type=click.Path(exists=True, path_type=Path),
    help="Session file to watch (defaults to most recent)",
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
def main(
    session: Path | None,
    port: int,
    host: str,
    no_open: bool,
    debug: bool,
) -> None:
    """Start a live-updating transcript viewer for Claude Code sessions.

    Watches a Claude Code session file and serves a live-updating HTML view
    that automatically shows new messages as they appear.

    If no session is specified, watches the most recently modified session
    file in ~/.claude/projects/.
    """
    # Configure logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Find session to watch
    if session is None:
        session = find_most_recent_session()
        if session is None:
            click.echo("No session files found in ~/.claude/projects/", err=True)
            click.echo("Specify a session file with --session", err=True)
            raise SystemExit(1)

    click.echo(f"Watching: {session}")

    # Configure server with the session path
    from . import server
    server.set_session_path(session)

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
