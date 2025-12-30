"""File tailer for watching Claude Code session files."""

import json
import logging
import urllib.parse
from pathlib import Path
from typing import AsyncGenerator, Callable

import watchfiles

logger = logging.getLogger(__name__)


def get_session_name(session_path: Path) -> str:
    """Extract a human-readable name from a session path.

    Session paths look like:
    ~/.claude/projects/-Users-tijs-projects-claude-code-live/abc123.jsonl

    The folder name uses dashes for path separators, but project names can
    also contain dashes. We use heuristics to find common directory markers
    and extract the project name after them.
    """
    # Get the parent folder name (the project identifier)
    folder = session_path.parent.name

    # URL decode any percent-encoded chars first
    folder = urllib.parse.unquote(folder)

    # Look for common directory markers and take everything after
    # Order matters - check more specific patterns first
    markers = ["-projects-", "-repos-", "-src-", "-code-", "-github-", "-tmp-", "-os-"]
    for marker in markers:
        if marker in folder:
            # Take everything after the marker
            project_name = folder.split(marker, 1)[1]
            return project_name if project_name else folder

    # Fallback: try to extract after username pattern (-Users-xxx- or -home-xxx-)
    import re
    match = re.match(r"^-(?:Users|home)-[^-]+-(.+)$", folder)
    if match:
        return match.group(1)

    # Last resort: return the folder name as-is (strip leading dash)
    return folder.lstrip("-") or folder


def get_session_id(session_path: Path) -> str:
    """Get the session ID (filename without extension)."""
    return session_path.stem


class SessionTailer:
    """Tail a JSONL session file, yielding new complete lines."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.position = 0  # Byte position in file
        self.buffer = ""  # Incomplete line buffer
        self.message_index = 0  # Count of messages yielded
        self._first_timestamp: str | None = None  # Cached first message timestamp

    def get_first_timestamp(self) -> str | None:
        """Get the timestamp of the first message in the session."""
        if self._first_timestamp is not None:
            return self._first_timestamp

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get("type") in ("user", "assistant"):
                            self._first_timestamp = obj.get("timestamp", "")
                            return self._first_timestamp
                    except json.JSONDecodeError:
                        continue
        except (FileNotFoundError, IOError):
            pass
        return None

    def read_new_lines(self) -> list[dict]:
        """Read and parse new complete lines from the file.

        Returns a list of parsed JSON objects for each complete new line.
        Handles incomplete lines by buffering them for the next read.
        """
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                f.seek(self.position)
                content = f.read()
                self.position = f.tell()
        except FileNotFoundError:
            logger.warning(f"File not found: {self.path}")
            return []
        except IOError as e:
            logger.error(f"Error reading file: {e}")
            return []

        if not content:
            return []

        self.buffer += content
        lines = self.buffer.split("\n")
        # Keep the last (potentially incomplete) line in buffer
        self.buffer = lines[-1]

        results = []
        for line in lines[:-1]:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                # Only process user and assistant messages
                entry_type = obj.get("type")
                if entry_type in ("user", "assistant"):
                    results.append(obj)
                    self.message_index += 1
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON line: {e}")
                continue

        return results

    def read_all(self) -> list[dict]:
        """Read all messages from the file from the beginning.

        Does NOT modify the current position - reads a fresh copy.
        Returns list of all parsed message objects.
        """
        # Create a fresh tailer to read from start without affecting our position
        fresh_tailer = SessionTailer(self.path)
        return fresh_tailer.read_new_lines()


async def watch_file(path: Path, callback: Callable[[], None]) -> AsyncGenerator[None, None]:
    """Watch a file for modifications and call callback on each change.

    Args:
        path: Path to the file to watch
        callback: Async function to call when file changes

    Yields:
        Nothing, runs indefinitely until cancelled
    """
    logger.info(f"Starting file watch on {path}")
    try:
        async for changes in watchfiles.awatch(path):
            for change_type, changed_path in changes:
                if change_type == watchfiles.Change.modified:
                    logger.debug(f"File modified: {changed_path}")
                    await callback()
    except Exception as e:
        logger.error(f"Error watching file: {e}")
        raise


def find_recent_sessions(
    projects_dir: Path | None = None, limit: int = 10
) -> list[Path]:
    """Find the most recently modified session files.

    Args:
        projects_dir: Base directory to search (defaults to ~/.claude/projects)
        limit: Maximum number of sessions to return

    Returns:
        List of paths to recent .jsonl files, sorted by modification time (newest first)
    """
    if projects_dir is None:
        projects_dir = Path.home() / ".claude" / "projects"

    if not projects_dir.exists():
        logger.warning(f"Projects directory not found: {projects_dir}")
        return []

    # Find all .jsonl files, excluding agent files
    sessions = []
    for f in projects_dir.glob("**/*.jsonl"):
        if f.name.startswith("agent-"):
            continue
        try:
            mtime = f.stat().st_mtime
            sessions.append((f, mtime))
        except OSError:
            continue

    if not sessions:
        logger.warning("No session files found")
        return []

    # Return the most recently modified
    sessions.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in sessions[:limit]]


def find_most_recent_session(projects_dir: Path | None = None) -> Path | None:
    """Find the most recently modified session file.

    Args:
        projects_dir: Base directory to search (defaults to ~/.claude/projects)

    Returns:
        Path to most recent .jsonl file, or None if not found
    """
    sessions = find_recent_sessions(projects_dir, limit=1)
    return sessions[0] if sessions else None
