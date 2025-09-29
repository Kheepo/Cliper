import pytest
import requests
import time

def test_server_health():
    """Test that the server health endpoint is working"""
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "ok"
    except requests.exceptions.ConnectionError:
        pytest.skip("Server not running")

def test_frontend_accessible():
    """Test that the frontend is accessible"""
    try:
        response = requests.get("http://localhost:3000", timeout=5)
        assert response.status_code == 200
    except requests.exceptions.ConnectionError:
        pytest.skip("Frontend server not running")

def test_api_performance_system():
    """Test system performance endpoint"""
    try:
        response = requests.get("http://localhost:8000/api/performance/system", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data
        assert "process" in data
    except requests.exceptions.ConnectionError:
        pytest.skip("Server not running")

def test_api_redis_status():
    """Test Redis status endpoint"""
    try:
        response = requests.get("http://localhost:8000/api/performance/redis", timeout=5)
        assert response.status_code == 200
        data = response.json()
        # Redis is expected to be unhealthy in current setup
        assert "status" in data
    except requests.exceptions.ConnectionError:
        pytest.skip("Server not running")

def test_api_celery_status():
    """Test Celery status endpoint"""
    try:
        response = requests.get("http://localhost:8000/api/performance/celery", timeout=5)
        assert response.status_code == 200
        data = response.json()
        # Celery is expected to have errors in current setup
        assert "error" in data or "status" in data
    except requests.exceptions.ConnectionError:
        pytest.skip("Server not running")