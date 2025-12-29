"""Tests for the SessionTailer class."""

import json
import tempfile
from pathlib import Path

import pytest

from claude_code_live.tailer import SessionTailer, find_most_recent_session


class TestSessionTailer:
    """Tests for SessionTailer."""

    def test_read_all_returns_messages(self, temp_jsonl_file):
        """Test that read_all returns all messages from file."""
        tailer = SessionTailer(temp_jsonl_file)
        messages = tailer.read_all()

        assert len(messages) == 2
        assert messages[0]["type"] == "user"
        assert messages[1]["type"] == "assistant"

    def test_read_all_filters_non_messages(self):
        """Test that read_all filters out non-message entries."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            entries = [
                {"type": "system", "data": "ignored"},
                {"type": "user", "timestamp": "2024-12-30T10:00:00Z", "message": {"content": "Hello"}},
                {"type": "summary", "summary": "ignored"},
                {"type": "assistant", "timestamp": "2024-12-30T10:00:01Z", "message": {"content": [{"type": "text", "text": "Hi"}]}},
            ]
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
            f.flush()
            path = Path(f.name)

        try:
            tailer = SessionTailer(path)
            messages = tailer.read_all()

            assert len(messages) == 2
            assert messages[0]["type"] == "user"
            assert messages[1]["type"] == "assistant"
        finally:
            path.unlink()

    def test_read_new_lines_incremental(self):
        """Test that read_new_lines reads incrementally."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"type": "user", "timestamp": "1", "message": {"content": "First"}}) + "\n")
            f.flush()
            path = Path(f.name)

        try:
            tailer = SessionTailer(path)

            # First read
            messages = tailer.read_new_lines()
            assert len(messages) == 1
            assert messages[0]["message"]["content"] == "First"

            # Append more data
            with open(path, "a") as f:
                f.write(json.dumps({"type": "assistant", "timestamp": "2", "message": {"content": [{"type": "text", "text": "Second"}]}}) + "\n")

            # Second read should only get new message
            messages = tailer.read_new_lines()
            assert len(messages) == 1
            assert messages[0]["type"] == "assistant"

            # Third read should be empty
            messages = tailer.read_new_lines()
            assert len(messages) == 0
        finally:
            path.unlink()

    def test_handles_incomplete_lines(self):
        """Test that incomplete lines are buffered correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"type": "user", "timestamp": "1", "message": {"content": "Complete"}}) + "\n")
            f.write('{"type": "assistant", "timestamp": "2", "message": {"content": [{"type": "text", "text": "Incomple')  # No newline
            f.flush()
            path = Path(f.name)

        try:
            tailer = SessionTailer(path)
            messages = tailer.read_new_lines()

            # Should only get the complete message
            assert len(messages) == 1
            assert messages[0]["message"]["content"] == "Complete"

            # Complete the line
            with open(path, "a") as f:
                f.write('te"}]}}\n')

            # Now should get the second message
            messages = tailer.read_new_lines()
            assert len(messages) == 1
            assert messages[0]["type"] == "assistant"
        finally:
            path.unlink()

    def test_handles_malformed_json(self):
        """Test that malformed JSON lines are skipped."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"type": "user", "timestamp": "1", "message": {"content": "Valid"}}) + "\n")
            f.write("this is not json\n")
            f.write(json.dumps({"type": "assistant", "timestamp": "2", "message": {"content": [{"type": "text", "text": "Also valid"}]}}) + "\n")
            f.flush()
            path = Path(f.name)

        try:
            tailer = SessionTailer(path)
            messages = tailer.read_new_lines()

            # Should get both valid messages, skip the invalid one
            assert len(messages) == 2
        finally:
            path.unlink()

    def test_handles_missing_file(self):
        """Test that missing file returns empty list."""
        tailer = SessionTailer(Path("/nonexistent/file.jsonl"))
        messages = tailer.read_new_lines()
        assert messages == []


class TestFindMostRecentSession:
    """Tests for find_most_recent_session."""

    def test_returns_none_for_nonexistent_dir(self):
        """Test that nonexistent directory returns None."""
        result = find_most_recent_session(Path("/nonexistent/path"))
        assert result is None

    def test_returns_none_for_empty_dir(self):
        """Test that empty directory returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_most_recent_session(Path(tmpdir))
            assert result is None

    def test_finds_most_recent(self):
        """Test that most recently modified file is returned."""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create older file
            older = tmppath / "older.jsonl"
            older.write_text('{"type": "user"}\n')

            time.sleep(0.01)  # Ensure different mtime

            # Create newer file
            newer = tmppath / "newer.jsonl"
            newer.write_text('{"type": "user"}\n')

            result = find_most_recent_session(tmppath)
            assert result == newer

    def test_excludes_agent_files(self):
        """Test that agent-* files are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create agent file (should be excluded)
            agent = tmppath / "agent-123.jsonl"
            agent.write_text('{"type": "user"}\n')

            # Create regular file
            regular = tmppath / "session.jsonl"
            regular.write_text('{"type": "user"}\n')

            result = find_most_recent_session(tmppath)
            assert result == regular
