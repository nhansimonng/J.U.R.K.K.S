from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.compiler import compiles

from app import auth
from app.database import get_db
from app.main import app
from app.models.user import User

USER_ID = "11111111-1111-4111-8111-111111111111"
IDENTITY = {"id": USER_ID, "email": "student@example.com",
            "user_metadata": {"username": "krish"}}
SESSION = {"user": IDENTITY, "access_token": "test-token", "expires_at": 1793125800,
           "refresh_token": "must-not-be-returned"}
LOGIN = {"email": "student@example.com", "password": "testPass123!"}
HEADERS = {"Authorization": "Bearer test-token"}


@compiles(PostgresUUID, "sqlite")
def sqlite_uuid(type_, compiler, **kwargs):
    # SQLite otherwise applies numeric affinity to PostgreSQL's UUID name.
    return "CHAR(32)"


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    User.__table__.create(engine)
    def database():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = database
    monkeypatch.setattr(auth.config, "SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setattr(auth.config, "SUPABASE_ANON_KEY", "test-anon")
    state = {"status": 200, "data": SESSION, "requests": []}
    def handler(request):
        state["requests"].append(request)
        if state.get("timeout"):
            raise httpx.ConnectTimeout("offline", request=request)
        return httpx.Response(state["status"], json=state["data"])
    original_client = httpx.Client
    monkeypatch.setattr(auth.httpx, "Client", lambda **kwargs:
                        original_client(transport=httpx.MockTransport(handler), **kwargs))
    with TestClient(app) as client:
        yield client, state, engine
    app.dependency_overrides.clear()
    engine.dispose()


def test_register_creates_profile_and_hides_refresh_token(setup):
    client, state, engine = setup
    response = client.post("/api/auth/register", json={**LOGIN, "username": " krish "})
    assert response.status_code == 201
    assert response.json()["user"]["username"] == "krish"
    assert set(response.json()) == {"user", "access_token", "expires_at"}
    assert state["requests"][0].url.path == "/auth/v1/signup"
    with Session(engine) as db:
        assert db.get(User, UUID(USER_ID)).username == "krish"


def test_login_reuses_existing_profile(setup):
    client, state, engine = setup
    with Session(engine) as db:
        db.add(User(id=UUID(USER_ID), username="updated-name"))
        db.commit()
    for _ in range(2):
        response = client.post("/api/auth/login", json=LOGIN)
        assert response.status_code == 200
        assert response.json()["user"]["username"] == "updated-name"
    assert state["requests"][0].url.params["grant_type"] == "password"


def test_confirmation_does_not_create_profile(setup):
    client, state, engine = setup
    state["data"] = IDENTITY
    response = client.post("/api/auth/register", json={**LOGIN, "username": "krish"})
    assert response.status_code == 201
    assert response.json()["confirmation_required"] is True
    assert "access_token" not in response.json()
    with Session(engine) as db:
        assert db.get(User, UUID(USER_ID)) is None


@pytest.mark.parametrize("change", [{"password": "short"}, {"username": "   "},
                                    {"email": "invalid"}])
def test_registration_validation(setup, change):
    client, state, _ = setup
    response = client.post("/api/auth/register", json={**LOGIN, "username": "krish", **change})
    assert response.status_code == 400
    assert set(response.json()) == {"error"}
    assert state["requests"] == []


@pytest.mark.parametrize("header", [{}, {"Authorization": "Basic abc"}])
def test_protected_routes_require_bearer(setup, header):
    client, state, _ = setup
    assert client.get("/api/users/me", headers=header).status_code == 401
    assert client.post("/api/auth/logout", headers=header).status_code == 401
    assert state["requests"] == []


def test_me_verifies_token_and_ignores_client_identity(setup):
    client, state, _ = setup
    state["data"] = IDENTITY
    response = client.get("/api/users/me?user_id=someone-else", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["id"] == USER_ID
    assert "created_at" in response.json()
    assert state["requests"][0].headers["Authorization"] == "Bearer test-token"
    assert state["requests"][0].url.path == "/auth/v1/user"


def test_logout_current_session(setup):
    client, state, _ = setup
    state["status"] = 204
    response = client.post("/api/auth/logout", headers=HEADERS)
    assert response.status_code == 204
    assert response.content == b""
    assert state["requests"][0].url.params["scope"] == "local"


@pytest.mark.parametrize("path,status,code,expected", [
    ("login", 400, "invalid_credentials", 401),
    ("login", 400, "email_not_confirmed", 403),
    ("register", 422, "user_already_exists", 400),
    ("register", 422, "weak_password", 400),
    ("login", 429, "over_request_rate_limit", 429),
    ("login", 500, "unexpected_failure", 503),
])
def test_provider_errors_are_safe(setup, path, status, code, expected):
    client, state, _ = setup
    state.update(status=status, data={"error_code": code, "msg": "private provider detail"})
    response = client.post(f"/api/auth/{path}", json={**LOGIN, "username": "krish"})
    assert response.status_code == expected
    assert "private" not in response.text


def test_invalid_token_rejected(setup):
    client, state, _ = setup
    state.update(status=401, data={"error_code": "bad_jwt"})
    assert client.get("/api/users/me", headers=HEADERS).status_code == 401


def test_unavailable_provider(setup):
    client, state, _ = setup
    state["timeout"] = True
    assert client.post("/api/auth/login", json=LOGIN).status_code == 503


def test_missing_configuration(setup, monkeypatch):
    client, state, _ = setup
    monkeypatch.setattr(auth.config, "SUPABASE_URL", None)
    assert client.post("/api/auth/login", json=LOGIN).status_code == 503
    assert state["requests"] == []
