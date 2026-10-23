# Test T010: Kiem tra /healthz, /readyz va /openapi.json trong moi truong offline khong can API key
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_healthz_endpoint():
    """T010: /healthz phai tra ve 200 OK va status 'ok'"""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["environment"] == "offline"
    assert "version" in data

def test_readyz_endpoint():
    """T010: /readyz phai tra ve 200 OK, database_connected=True va status 'ready'"""
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database_connected"] is True
    assert data["offline_mode"] is True

def test_openapi_json_endpoint():
    """T010: /openapi.json phai hop le va chua thong tin cac endpoints"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/healthz" in schema["paths"]
    assert "/readyz" in schema["paths"]
    assert "/v1/briefs" in schema["paths"]
    assert "/v1/workspaces" in schema["paths"]
