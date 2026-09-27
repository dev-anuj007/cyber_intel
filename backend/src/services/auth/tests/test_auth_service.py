"""Comprehensive Pytest Test Suite for Auth Service, Repositories, and API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.auth.api import get_auth_service, router
from src.services.auth.auth_service import AuthService
from src.services.auth.dependencies import create_auth_service
from src.services.auth.internals.repositories.reader import UserReader
from src.services.auth.internals.repositories.writer import UserWriter
from src.services.database.database_service import DatabaseService


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_auth_comp.db")
    db_service = DatabaseService(db_path=db_path)
    db_service.init_database()
    return db_path


@pytest.fixture
def auth_service(test_db):
    return create_auth_service(db_path=test_db, jwt_secret="testsecretkey12345678901234567890")


def test_auth_service_full_workflow(auth_service, test_db):
    # 1. Signup user
    user = auth_service.signup(
        email="alice@example.com", password="SecurePassword123!", full_name="Alice Smith", role="admin"
    )
    assert user is not None
    assert user["email"] == "alice@example.com"
    assert user["full_name"] == "Alice Smith"
    assert user["role"] == "admin"

    # 2. Duplicate signup should raise exception
    with pytest.raises(Exception):
        auth_service.signup(email="alice@example.com", password="AnotherPassword123!")

    # 3. Signin success
    signin_res = auth_service.signin(email="alice@example.com", password="SecurePassword123!")
    assert "token" in signin_res
    assert signin_res["user"]["email"] == "alice@example.com"

    # 4. Signin invalid password
    with pytest.raises(Exception):
        auth_service.signin(email="alice@example.com", password="WrongPassword")

    # 5. Signin non-existent user
    with pytest.raises(Exception):
        auth_service.signin(email="nonexistent@example.com", password="Password123!")

    # 6. Verify token
    token = signin_res["token"]
    payload = auth_service.verify_token(token)
    assert payload is not None
    assert payload["email"] == "alice@example.com"

    # Invalid token
    assert auth_service.verify_token("invalid.jwt.token") is None

    # 7. Get user by ID and email
    user_id = user["id"]
    u_by_id = auth_service.get_user_by_id(user_id)
    assert u_by_id is not None
    assert u_by_id["email"] == "alice@example.com"

    u_by_email = auth_service.get_user_by_email("alice@example.com")
    assert u_by_email is not None

    # 8. Create API Key
    api_key = auth_service.create_api_key(user_id)
    assert api_key is not None
    assert api_key.startswith("sk-")

    # 9. Verify API Key
    u_by_key = auth_service.verify_api_key(api_key)
    assert u_by_key is not None
    assert u_by_key["email"] == "alice@example.com"

    # Verify invalid key
    assert auth_service.verify_api_key("sk-invalidkey") is None

    # 10. List API keys
    keys = auth_service.list_api_keys(user_id)
    assert len(keys) >= 1

    # 11. Revoke API Key
    auth_service.revoke_api_key(user_id, api_key)
    assert auth_service.verify_api_key(api_key) is None


def test_auth_repositories(test_db):
    reader = UserReader()
    writer = UserWriter()
    db_svc = DatabaseService(db_path=test_db)

    with db_svc.get_connection() as conn:
        # Create user
        uid = writer.create_user(
            conn, email="bob@example.com", password_hash="hash123", full_name="Bob Jones", role="member"
        )
        assert uid is not None

        # Read by email
        u = reader.get_user_by_email(conn, "bob@example.com")
        assert u is not None
        assert u["full_name"] == "Bob Jones"

        # Update last login
        writer.update_last_login(conn, uid)

        # Update API key
        writer.update_api_key(conn, uid, "sk-test-bob-key")
        u_key = reader.get_user_by_api_key(conn, "sk-test-bob-key")
        assert u_key is not None
        assert u_key["id"] == uid

        # Delete API key
        writer.delete_api_key(conn, uid, "sk-test-bob-key")
        assert reader.get_user_by_api_key(conn, "sk-test-bob-key") is None


def test_auth_api_endpoints(auth_service):
    api_app = FastAPI()
    api_app.include_router(router)
    api_app.dependency_overrides[get_auth_service] = lambda: auth_service
    client = TestClient(api_app)

    # Health
    r = client.get("/api/auth/health")
    if r.status_code == 404:
        r = client.get("/api/auth/me")
    assert r.status_code in [200, 401, 404]

    # Signup
    r = client.post(
        "/api/auth/signup", json={"email": "api_user@test.com", "password": "Password123!", "full_name": "API User"}
    )
    assert r.status_code == 200
    token = r.json().get("token")

    # Signin
    r = client.post("/api/auth/signin", json={"email": "api_user@test.com", "password": "Password123!"})
    assert r.status_code == 200
    token = r.json()["token"]

    # Me (authenticated)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "api_user@test.com"

    # API key creation
    r = client.post("/api/auth/api-key", headers=headers)
    assert r.status_code == 200
    api_key = r.json()["api_key"]

    # List API keys
    r = client.get("/api/auth/api-key/list", headers=headers)
    assert r.status_code == 200

    # Revoke API key
    r = client.post("/api/auth/api-key/revoke", headers=headers, json={"api_key": api_key})
    assert r.status_code == 200

    api_app.dependency_overrides.clear()
