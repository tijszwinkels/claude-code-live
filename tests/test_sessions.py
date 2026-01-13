"""Tests for session management."""

import json
import os
import time

import pytest

from claude_code_session_explorer.sessions import SessionInfo, set_backend
from claude_code_session_explorer.backends.claude_code.backend import ClaudeCodeBackend


class TestSessionInfoMtimeCheck:
    """Tests for SessionInfo mtime checking to filter spurious file watcher events."""

    @pytest.fixture(autouse=True)
    def setup_backend(self, tmp_path):
        """Set up backend for tests."""
        # Create a projects directory
        projects_dir = tmp_path / "projects"
        projects_dir.mkdir()

        # Create backend with custom projects dir
        backend = ClaudeCodeBackend(projects_dir=projects_dir)
        set_backend(backend)

        yield backend

        # Reset backend after test
        set_backend(None)

    @pytest.fixture
    def session_file(self, tmp_path):
        """Create a test session file."""
        projects_dir = tmp_path / "projects"
        session_dir = projects_dir / "-home-test-project"
        session_dir.mkdir(parents=True)
        session_file = session_dir / "test-session.jsonl"

        # Write initial message
        msg = {
            "type": "user",
            "message": {"role": "user", "content": "Hello"},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        session_file.write_text(json.dumps(msg) + "\n")

        return session_file

    def test_check_mtime_changed_returns_false_when_unchanged(self, session_file, setup_backend):
        """When file mtime hasn't changed, check_mtime_changed returns False."""
        info = SessionInfo(
            path=session_file,
            tailer=setup_backend.create_tailer(session_file),
        )

        # First call after creation - mtime already set in __post_init__
        # Calling again without file change should return False
        assert info.check_mtime_changed() is False

    def test_check_mtime_changed_returns_true_when_modified(self, session_file, setup_backend):
        """When file is modified, check_mtime_changed returns True."""
        info = SessionInfo(
            path=session_file,
            tailer=setup_backend.create_tailer(session_file),
        )

        # Ensure time passes (mtime resolution may be 1 second)
        time.sleep(0.01)

        # Modify the file
        with open(session_file, "a") as f:
            msg = {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi"}]},
                "timestamp": "2024-01-01T00:00:01Z",
            }
            f.write(json.dumps(msg) + "\n")

        # Force mtime update (some filesystems have coarse resolution)
        os.utime(session_file, None)

        # Now check should return True
        assert info.check_mtime_changed() is True

    def test_check_mtime_changed_updates_stored_mtime(self, session_file, setup_backend):
        """After detecting a change, stored mtime is updated."""
        info = SessionInfo(
            path=session_file,
            tailer=setup_backend.create_tailer(session_file),
        )

        original_mtime = info.last_mtime

        # Modify file
        time.sleep(0.01)
        with open(session_file, "a") as f:
            f.write('{"type": "user"}\n')
        os.utime(session_file, None)

        # First check detects change
        assert info.check_mtime_changed() is True

        # Mtime should be updated
        assert info.last_mtime > original_mtime

        # Second check without changes returns False
        assert info.check_mtime_changed() is False

    def test_check_mtime_changed_handles_missing_file(self, session_file, setup_backend):
        """When file is deleted, check_mtime_changed returns False."""
        info = SessionInfo(
            path=session_file,
            tailer=setup_backend.create_tailer(session_file),
        )

        # Delete file
        session_file.unlink()

        # Should return False (not crash)
        assert info.check_mtime_changed() is False
