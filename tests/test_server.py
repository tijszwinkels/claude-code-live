"""Tests for the FastAPI server."""

import json
import pytest
from fastapi.testclient import TestClient

from claude_code_live.server import app, set_session_path


class TestServerEndpoints:
    """Tests for server endpoints."""

    def test_index_returns_html(self, temp_jsonl_file):
        """Test that index returns HTML page."""
        set_session_path(temp_jsonl_file)
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Claude Code Live" in response.text

    def test_index_includes_css(self, temp_jsonl_file):
        """Test that index includes CSS."""
        set_session_path(temp_jsonl_file)
        client = TestClient(app)

        response = client.get("/")
        assert ":root" in response.text
        assert "--bg-color" in response.text

    def test_index_includes_sse_script(self, temp_jsonl_file):
        """Test that index includes SSE client script."""
        set_session_path(temp_jsonl_file)
        client = TestClient(app)

        response = client.get("/")
        assert "EventSource" in response.text
        assert "/events" in response.text

    def test_health_check(self, temp_jsonl_file):
        """Test health check endpoint."""
        set_session_path(temp_jsonl_file)
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "session" in data
        assert "clients" in data


# Note: SSE endpoint streaming tests are skipped because TestClient
# doesn't handle SSE event generators well. The endpoint is tested
# manually and through integration tests.
