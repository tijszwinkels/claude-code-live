"""Search functionality for session transcripts.

This module provides functions to search through Claude Code and OpenCode sessions
for specific phrases and return matching sessions with context around matches.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .backends.claude_code.discovery import (
    DEFAULT_PROJECTS_DIR,
    get_last_message_timestamp,
    is_subagent_session,
    is_warmup_session,
    has_messages,
)
from .export import parse_session_entries, get_entry_role, get_entry_timestamp, format_message_as_markdown


@dataclass
class SearchResult:
    """A search result with session metadata and matching content."""

    session_path: Path
    created_at: datetime | None
    updated_at: datetime | None
    last_msg_at: datetime | None
    match_count: int
    context_entries: list[dict]  # Entries to display (with context)
    match_indices: set[int]  # Indices of actual matching messages


def get_session_timestamps(session_path: Path) -> tuple[datetime | None, datetime | None, datetime | None]:
    """Get created_at, updated_at, and last_msg_at timestamps for a session."""
    created_at = None
    updated_at = None
    last_msg_at = None

    try:
        stat = session_path.stat()
        created_at = datetime.fromtimestamp(stat.st_ctime)
        updated_at = datetime.fromtimestamp(stat.st_mtime)
    except OSError:
        pass

    msg_ts = get_last_message_timestamp(session_path)
    if msg_ts:
        last_msg_at = datetime.fromtimestamp(msg_ts)

    return created_at, updated_at, last_msg_at


def search_entries_for_phrase(
    entries: list[dict],
    search_phrase: str,
    case_insensitive: bool = True,
    hide_tools: bool = True,
) -> tuple[list[int], int]:
    """Search entries for a phrase and return matching indices.

    Args:
        entries: List of parsed session entries
        search_phrase: The phrase to search for
        case_insensitive: Whether to ignore case
        hide_tools: Whether to skip tool-related messages

    Returns:
        Tuple of (list of matching entry indices, total match count)
    """
    flags = re.IGNORECASE if case_insensitive else 0
    pattern = re.compile(re.escape(search_phrase), flags)
    matching_indices = []
    total_matches = 0

    for i, entry in enumerate(entries):
        # Skip tool results if hide_tools
        if hide_tools:
            role = get_entry_role(entry, "claude_code")
            if role == "user":
                message_data = entry.get("message", {})
                content = message_data.get("content", [])
                if isinstance(content, list) and content:
                    if isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                        continue

        # Search in the entry content
        entry_str = json.dumps(entry, ensure_ascii=False)
        matches = pattern.findall(entry_str)
        if matches:
            matching_indices.append(i)
            total_matches += len(matches)

    return matching_indices, total_matches


def get_context_window(
    entries: list[dict],
    match_indices: list[int],
    context_before: int = 5,
    context_after: int = 5,
    hide_tools: bool = True,
) -> tuple[list[dict], set[int]]:
    """Get entries with context around matches, merging overlapping windows.

    Args:
        entries: All session entries
        match_indices: Indices of matching entries
        context_before: Number of messages to show before each match
        context_after: Number of messages to show after each match
        hide_tools: Whether to filter out tool messages when counting context

    Returns:
        Tuple of (list of entries to display, set of match indices in result)
    """
    if not match_indices:
        return [], set()

    # Build list of displayable entries (filtering tools if needed)
    if hide_tools:
        displayable = []
        original_to_display = {}  # Map original index to display index
        for i, entry in enumerate(entries):
            role = get_entry_role(entry, "claude_code")
            is_tool_result = False
            if role == "user":
                message_data = entry.get("message", {})
                content = message_data.get("content", [])
                if isinstance(content, list) and content:
                    if isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                        is_tool_result = True

            # Skip tool_use blocks in assistant messages too
            if role == "assistant":
                message_data = entry.get("message", {})
                content = message_data.get("content", [])
                if isinstance(content, list):
                    has_non_tool = any(
                        isinstance(b, dict) and b.get("type") in ("text", "thinking")
                        for b in content
                    )
                    if not has_non_tool:
                        # Only tool_use, skip
                        continue

            if not is_tool_result:
                original_to_display[i] = len(displayable)
                displayable.append((i, entry))
    else:
        displayable = [(i, entry) for i, entry in enumerate(entries)]
        original_to_display = {i: i for i in range(len(entries))}

    # Convert match indices to display indices
    display_match_indices = []
    for orig_idx in match_indices:
        if orig_idx in original_to_display:
            display_match_indices.append(original_to_display[orig_idx])

    if not display_match_indices:
        return [], set()

    # Calculate ranges to include (in display indices)
    ranges_to_include = set()
    for display_idx in display_match_indices:
        start = max(0, display_idx - context_before)
        end = min(len(displayable), display_idx + context_after + 1)
        for i in range(start, end):
            ranges_to_include.add(i)

    # Get sorted unique indices
    sorted_indices = sorted(ranges_to_include)

    # Build result
    result_entries = []
    result_match_indices = set()
    for result_idx, display_idx in enumerate(sorted_indices):
        orig_idx, entry = displayable[display_idx]
        result_entries.append(entry)
        if display_idx in display_match_indices:
            result_match_indices.add(result_idx)

    return result_entries, result_match_indices


def search_session(
    session_path: Path,
    search_phrase: str,
    case_insensitive: bool = True,
    hide_tools: bool = True,
    context_before: int = 5,
    context_after: int = 5,
) -> SearchResult | None:
    """Search a session for matches and return result with context.

    Args:
        session_path: Path to session file
        search_phrase: Phrase to search for
        case_insensitive: Whether to ignore case
        hide_tools: Whether to hide tool messages
        context_before: Messages to show before match
        context_after: Messages to show after match

    Returns:
        SearchResult if matches found, None otherwise
    """
    try:
        entries, backend = parse_session_entries(session_path)
    except Exception:
        return None

    match_indices, total_matches = search_entries_for_phrase(
        entries, search_phrase, case_insensitive, hide_tools
    )

    if not match_indices:
        return None

    context_entries, result_match_indices = get_context_window(
        entries, match_indices, context_before, context_after, hide_tools
    )

    created_at, updated_at, last_msg_at = get_session_timestamps(session_path)

    return SearchResult(
        session_path=session_path,
        created_at=created_at,
        updated_at=updated_at,
        last_msg_at=last_msg_at,
        match_count=total_matches,
        context_entries=context_entries,
        match_indices=result_match_indices,
    )


def find_matching_sessions(
    search_phrase: str,
    projects_dir: Path | None = None,
    limit: int = 10,
    include_subagents: bool = False,
    case_insensitive: bool = True,
    hide_tools: bool = True,
    context_before: int = 5,
    context_after: int = 5,
) -> tuple[list[SearchResult], int]:
    """Find sessions containing the search phrase.

    Returns:
        Tuple of (list of SearchResult sorted by last_msg_at descending, total count)
    """
    if projects_dir is None:
        projects_dir = DEFAULT_PROJECTS_DIR

    if not projects_dir.exists():
        return [], 0

    # Find all session files
    candidates = []
    for f in projects_dir.glob("**/*.jsonl"):
        if not include_subagents and is_subagent_session(f):
            continue
        try:
            if f.stat().st_size == 0:
                continue
            if not has_messages(f) or is_warmup_session(f):
                continue
            candidates.append(f)
        except OSError:
            continue

    # Search each session
    results: list[SearchResult] = []
    for session_path in candidates:
        result = search_session(
            session_path,
            search_phrase,
            case_insensitive,
            hide_tools,
            context_before,
            context_after,
        )
        if result:
            results.append(result)

    # Sort by last_msg_at descending
    results.sort(key=lambda r: r.last_msg_at or datetime.min, reverse=True)

    total_count = len(results)
    return results[:limit], total_count


def format_datetime(dt: datetime | None) -> str:
    """Format datetime for output."""
    if dt is None:
        return "unknown"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_search_result(result: SearchResult, hide_tools: bool = True) -> str:
    """Format a search result with metadata and context."""
    lines = []

    # Session header
    lines.append(f"## {result.session_path}")
    lines.append("")
    lines.append(f"created_at: {format_datetime(result.created_at)}")
    lines.append(f"updated_at: {format_datetime(result.updated_at)}")
    lines.append(f"last_msg_at: {format_datetime(result.last_msg_at)}")
    lines.append(f"matches: {result.match_count}")
    lines.append("")

    # Format context entries
    for i, entry in enumerate(result.context_entries):
        is_match = i in result.match_indices
        prefix = ">>> " if is_match else ""

        md = format_message_as_markdown(entry, "claude_code", hide_tools=hide_tools)
        if md:
            if is_match:
                lines.append(f"{prefix}**[MATCH]**")
            lines.append(md)
            lines.append("")

    return "\n".join(lines)


def search_sessions(
    search_phrase: str,
    limit: int = 10,
    include_subagents: bool = False,
    case_insensitive: bool = True,
    hide_tools: bool = True,
    context_before: int = 5,
    context_after: int = 5,
) -> str:
    """Search sessions and return formatted results.

    Args:
        search_phrase: The phrase to search for
        limit: Maximum number of results (default 10)
        include_subagents: Include subagent sessions
        case_insensitive: Ignore case (default True)
        hide_tools: Hide tool calls (default True)
        context_before: Messages before match (default 5)
        context_after: Messages after match (default 5)

    Returns:
        Formatted string with matching sessions and context
    """
    results, total_count = find_matching_sessions(
        search_phrase,
        limit=limit,
        include_subagents=include_subagents,
        case_insensitive=case_insensitive,
        hide_tools=hide_tools,
        context_before=context_before,
        context_after=context_after,
    )

    if not results:
        return f"No sessions found matching '{search_phrase}'\n"

    output_parts = []

    for result in results:
        output_parts.append(format_search_result(result, hide_tools=hide_tools))
        output_parts.append("\n" + "=" * 80 + "\n\n")

    # Pagination hint
    if total_count > limit:
        remaining = total_count - limit
        output_parts.append(f"**Note:** {remaining} more session(s) match this search. ")
        output_parts.append(f"Use `--limit {total_count}` to see all results.\n")
    else:
        output_parts.append(f"**Total:** {total_count} session(s) found.\n")

    return "".join(output_parts)
