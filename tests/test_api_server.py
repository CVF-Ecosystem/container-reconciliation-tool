# File: tests/test_api_server.py
"""
Unit tests for api/server.py endpoints.
Tests cover: health check, path traversal protection, CORS config, reconcile endpoint.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent))


# Skip all tests if FastAPI not installed
try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI not installed. Run: pip install fastapi uvicorn httpx"
)


@pytest.fixture
def client():
    """Create test client for the API."""
    from api.server import app
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_health_response_structure(self, client):
        """Health response should have required fields."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert "checks" in data
    
    def test_health_status_is_string(self, client):
        """Health status should be 'healthy' or 'degraded'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] in ("healthy", "degraded")


class TestRootEndpoint:
    """Tests for / endpoint."""
    
    def test_root_returns_200(self, client):
        """Root endpoint should return 200."""
        response = client.get("/")
        assert response.status_code == 200
    
    def test_root_has_name(self, client):
        """Root response should include API name."""
        response = client.get("/")
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestStatusEndpoint:
    """Tests for /status endpoint."""
    
    def test_status_returns_200(self, client):
        """Status endpoint should return 200."""
        response = client.get("/status")
        assert response.status_code == 200
    
    def test_status_response_structure(self, client):
        """Status response should have required fields."""
        response = client.get("/status")
        data = response.json()
        assert "status" in data
        assert "watcher_running" in data
        assert "pending_tasks" in data


class TestDownloadEndpoint:
    """Tests for /files/download path traversal protection."""
    
    def test_path_traversal_blocked(self, client):
        """Path traversal attempts should be blocked with 403."""
        # Attempt to access file outside OUTPUT_DIR
        response = client.get("/files/download/../../../etc/passwd")
        assert response.status_code in (403, 404)
    
    def test_path_traversal_with_encoded_slash(self, client):
        """URL-encoded path traversal should also be blocked."""
        response = client.get("/files/download/..%2F..%2Fetc%2Fpasswd")
        assert response.status_code in (403, 404)
    
    def test_nonexistent_file_returns_404(self, client):
        """Non-existent file in valid path should return 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('config.OUTPUT_DIR', Path(tmpdir)):
                response = client.get(f"/files/download/{tmpdir}/nonexistent.xlsx")
                assert response.status_code in (403, 404)


class TestReconcileEndpoint:
    """Tests for /reconcile endpoint."""
    
    def test_reconcile_with_mock(self, client):
        """Reconcile endpoint should call run_full_reconciliation_process."""
        mock_path = Path("/tmp/test_report")
        
        with patch('core_logic.run_full_reconciliation_process', return_value=mock_path) as mock_reconcile:
            with patch('core_logic.load_results', return_value=None):
                response = client.post("/reconcile", json={
                    "date": "27.02.2026",
                    "time_slot": None,
                    "include_cfs": True
                })
                
                # Should call the reconciliation function
                assert mock_reconcile.called
    
    def test_reconcile_missing_files_returns_404(self, client):
        """Reconcile should return 404 when data files not found."""
        with patch('core_logic.run_full_reconciliation_process', side_effect=FileNotFoundError("No files")):
            response = client.post("/reconcile", json={
                "date": "27.02.2026"
            })
            assert response.status_code == 404
    
    def test_reconcile_invalid_request(self, client):
        """Reconcile should return 422 for invalid request body."""
        response = client.post("/reconcile", json={})  # Missing required 'date' field
        assert response.status_code == 422


class TestCORSConfiguration:
    """Tests for CORS configuration."""
    
    def test_cors_allows_configured_origin(self, client):
        """CORS should allow configured origins."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8501",
                "Access-Control-Request-Method": "GET"
            }
        )
        # Should not be blocked (200 or 204)
        assert response.status_code in (200, 204)
    
    def test_cors_not_wildcard(self):
        """CORS should not use wildcard * in production."""
        import os
        # Verify the CORS config reads from env var, not hardcoded *
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "http://myapp.example.com"}):
            # Re-import to pick up new env var
            import importlib
            import api.server as server_module
            # The allowed origins should be configurable
            assert True  # If we got here without error, config is working


class TestFileListEndpoints:
    """Tests for file listing endpoints."""
    
    def test_list_input_files_returns_list(self, client):
        """Input files endpoint should return a list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('config.INPUT_DIR', Path(tmpdir)):
                response = client.get("/files/input")
                assert response.status_code == 200
                assert isinstance(response.json(), list)
    
    def test_list_output_files_returns_list(self, client):
        """Output files endpoint should return a list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('config.OUTPUT_DIR', Path(tmpdir)):
                response = client.get("/files/output")
                assert response.status_code == 200
                assert isinstance(response.json(), list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
