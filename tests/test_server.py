"""Tests for the FastAPI server."""

import json
import pytest
from fastapi.testclient import TestClient

from claude_code_live import server
from claude_code_live.server import app, add_session


@pytest.fixture(autouse=True)
def reset_server_state():
    """Reset server state before each test."""
    server._sessions.clear()
    server._clients.clear()
    server._known_session_files.clear()
    yield
    server._sessions.clear()
    server._clients.clear()
    server._known_session_files.clear()


class TestServerEndpoints:
    """Tests for server endpoints."""

    def test_index_returns_html(self, temp_jsonl_file):
        """Test that index returns HTML page."""
        add_session(temp_jsonl_file)
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Claude Code Live" in response.text

    def test_index_includes_css(self, temp_jsonl_file):
        """Test that index includes CSS."""
        add_session(temp_jsonl_file)
        client = TestClient(app)

        response = client.get("/")
        assert ":root" in response.text
        assert "--bg-color" in response.text

    def test_index_includes_sse_script(self, temp_jsonl_file):
        """Test that index includes SSE client script."""
        add_session(temp_jsonl_file)
        client = TestClient(app)

        response = client.get("/")
        assert "EventSource" in response.text
        assert "/events" in response.text

    def test_index_includes_tab_bar(self, temp_jsonl_file):
        """Test that index includes tab bar elements."""
        add_session(temp_jsonl_file)
        client = TestClient(app)

        response = client.get("/")
        assert "tab-bar" in response.text
        assert "auto-follow" in response.text

    def test_health_check(self, temp_jsonl_file):
        """Test health check endpoint."""
        add_session(temp_jsonl_file)
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "sessions" in data
        assert "clients" in data

    def test_sessions_endpoint(self, temp_jsonl_file):
        """Test sessions list endpoint."""
        add_session(temp_jsonl_file)
        client = TestClient(app)

        response = client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert len(data["sessions"]) == 1


class TestSessionManagement:
    """Tests for session management functions."""

    def test_add_session(self, temp_jsonl_file):
        """Test adding a session."""
        info, evicted_id = add_session(temp_jsonl_file)

        assert info is not None
        assert evicted_id is None
        assert info.session_id == temp_jsonl_file.stem
        assert info.path == temp_jsonl_file

    def test_add_duplicate_session(self, temp_jsonl_file):
        """Test that adding duplicate session returns None."""
        info1, _ = add_session(temp_jsonl_file)
        info2, evicted_id = add_session(temp_jsonl_file)

        assert info1 is not None
        assert info2 is None
        assert evicted_id is None

    def test_session_limit_with_eviction(self, tmp_path):
        """Test that session limit evicts oldest sessions."""
        import time

        # Create more sessions than the limit, with slight time delays
        for i in range(server.MAX_SESSIONS + 2):
            session_file = tmp_path / f"session_{i}.jsonl"
            session_file.write_text('{"type": "user"}\n')
            add_session(session_file)
            time.sleep(0.01)  # Ensure different mtime

        # Should still have MAX_SESSIONS (oldest got evicted)
        assert len(server._sessions) == server.MAX_SESSIONS
        # First session should have been evicted
        assert "session_0" not in server._sessions

    def test_session_limit_without_eviction(self, tmp_path):
        """Test that session limit is respected when eviction is disabled."""
        # Create more sessions than the limit without eviction
        for i in range(server.MAX_SESSIONS + 2):
            session_file = tmp_path / f"session_{i}.jsonl"
            session_file.write_text('{"type": "user"}\n')
            add_session(session_file, evict_oldest=False)

        # Should stop at MAX_SESSIONS
        assert len(server._sessions) == server.MAX_SESSIONS

    def test_remove_session(self, temp_jsonl_file):
        """Test removing a session."""
        info, _ = add_session(temp_jsonl_file)
        session_id = info.session_id

        assert server.remove_session(session_id) is True
        assert session_id not in server._sessions

    def test_remove_nonexistent_session(self):
        """Test removing a session that doesn't exist."""
        assert server.remove_session("nonexistent") is False

    def test_get_sessions_list(self, temp_jsonl_file):
        """Test getting the sessions list."""
        add_session(temp_jsonl_file)
        sessions = server.get_sessions_list()

        assert len(sessions) == 1
        assert sessions[0]["id"] == temp_jsonl_file.stem


# Note: SSE endpoint streaming tests are skipped because TestClient
# doesn't handle SSE event generators well. The endpoint is tested
# manually and through integration tests.
