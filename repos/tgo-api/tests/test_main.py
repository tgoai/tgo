"""Test main application."""

def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert data["message"] == "TGO-Tech API Service"


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_openapi_docs(client):
    """Test OpenAPI documentation is accessible."""
    response = client.get("/v1/docs")
    assert response.status_code == 200


def test_openapi_json(client):
    """Test OpenAPI JSON is accessible."""
    response = client.get("/v1/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "info" in data
