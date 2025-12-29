"""FastAPI server with SSE endpoint for live transcript updates."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from .rendering import CSS, render_message, get_template
from .tailer import SessionTailer, find_most_recent_session

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage server lifecycle - start/stop file watcher."""
    global _watch_task

    # Startup
    if _session_path is None:
        # Try to find the most recent session
        path = find_most_recent_session()
        if path:
            set_session_path(path)
        else:
            logger.warning("No session file configured or found")

    if _session_path is not None:
        _watch_task = asyncio.create_task(watch_loop())

    yield

    # Shutdown
    if _watch_task:
        _watch_task.cancel()
        try:
            await _watch_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Claude Code Live", lifespan=lifespan)

# Global state
_session_path: Path | None = None
_tailer: SessionTailer | None = None
_clients: set[asyncio.Queue] = set()
_watch_task: asyncio.Task | None = None


def set_session_path(path: Path) -> None:
    """Set the session file to watch."""
    global _session_path, _tailer
    _session_path = path
    _tailer = SessionTailer(path)
    logger.info(f"Watching session: {path}")


def get_session_display_path() -> str:
    """Get a displayable version of the session path."""
    if _session_path is None:
        return "No session"
    # Show just the last two path components (project/session.jsonl)
    parts = _session_path.parts
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return str(_session_path.name)


async def broadcast_message(html: str) -> None:
    """Send a message to all connected clients."""
    event = {"type": "html", "content": html}
    dead_clients = []

    for queue in _clients:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            dead_clients.append(queue)

    for queue in dead_clients:
        _clients.discard(queue)


async def process_new_messages() -> None:
    """Read new messages from file and broadcast to clients."""
    if _tailer is None:
        return

    new_entries = _tailer.read_new_lines()
    for entry in new_entries:
        html = render_message(entry)
        if html:
            await broadcast_message(html)


async def watch_loop() -> None:
    """Background task that watches the file for changes."""
    if _session_path is None:
        return

    logger.info(f"Starting watch loop for {_session_path}")

    try:
        import watchfiles

        async for changes in watchfiles.awatch(_session_path):
            for change_type, changed_path in changes:
                if change_type == watchfiles.Change.modified:
                    await process_new_messages()
    except asyncio.CancelledError:
        logger.info("Watch loop cancelled")
        raise
    except Exception as e:
        logger.error(f"Watch loop error: {e}")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the main live transcript page."""
    template = get_template("live.html")
    html = template.render(css=CSS)
    return HTMLResponse(content=html)


async def event_generator(request: Request) -> AsyncGenerator[dict, None]:
    """Generate SSE events for a client."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _clients.add(queue)

    try:
        # Send init event
        yield {
            "event": "init",
            "data": json.dumps({
                "session_id": _session_path.stem if _session_path else "none",
                "session_path": get_session_display_path(),
            }),
        }

        # Send existing messages (catchup)
        if _tailer:
            existing = _tailer.read_all()
            for entry in existing:
                html = render_message(entry)
                if html:
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "html", "content": html}),
                    }

        # Stream new messages
        ping_interval = 30  # seconds

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                # Wait for new message with timeout for ping
                event = await asyncio.wait_for(queue.get(), timeout=ping_interval)
                yield {
                    "event": "message",
                    "data": json.dumps(event),
                }
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                yield {"event": "ping", "data": "{}"}

    finally:
        _clients.discard(queue)


@app.get("/events")
async def events(request: Request) -> EventSourceResponse:
    """SSE endpoint for live transcript updates."""
    return EventSourceResponse(event_generator(request))


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "session": str(_session_path) if _session_path else None,
        "clients": len(_clients),
    }
