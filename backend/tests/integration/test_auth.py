"""
Integration tests for authentication endpoints.
"""


def test_register_creates_account(client):
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "new@example.com",
            "password": "securepass123",
            "organization_name": "New Corp",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_register_duplicate_email_rejected(client):
    payload = {
        "email": "dup@example.com",
        "password": "securepass123",
        "organization_name": "Dup Corp",
    }
    client.post("/api/auth/register", json=payload)
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 400


def test_login_success(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "login@example.com",
            "password": "securepass123",
            "organization_name": "Login Corp",
        },
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "securepass123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "wrong@example.com",
            "password": "securepass123",
            "organization_name": "Wrong Corp",
        },
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "wrong@example.com", "password": "incorrect"},
    )
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


def test_me_with_token(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
