from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models.gym import Gym
from app.models.review import GymReview
from app.models.user import User

ALICE = "aaaaaaaa-1111-4111-8111-111111111111"
GYM_A = "cccccccc-1111-4111-8111-111111111111"
GYM_B = "dddddddd-2222-4222-8222-222222222222"
MISSING = "eeeeeeee-3333-4333-8333-333333333333"


@compiles(PostgresUUID, "sqlite")
def sqlite_uuid(type_, compiler, **kwargs):
    return "CHAR(32)"


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    User.__table__.create(engine)
    Gym.__table__.create(engine)
    GymReview.__table__.create(engine)
    with Session(engine) as db:
        db.add(User(id=UUID(ALICE), username="alice"))
        db.add_all([
            Gym(id=UUID(GYM_A), name="Iron Works", address="1 Main St, San Jose"),
            Gym(id=UUID(GYM_B), name="Planet Gym", address="2 Oak Ave, Campbell"),
        ])
        db.add_all([
            GymReview(user_id=UUID(ALICE), gym_id=UUID(GYM_A), rating=5),
            GymReview(user_id=UUID(ALICE), gym_id=UUID(GYM_A), rating=4),
        ])
        db.commit()

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: {"id": ALICE}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_search_by_name_is_case_insensitive(client):
    gyms = client.get("/api/gyms?query=iron").json()["gyms"]
    assert [g["name"] for g in gyms] == ["Iron Works"]


def test_search_by_address(client):
    gyms = client.get("/api/gyms?query=campbell").json()["gyms"]
    assert [g["name"] for g in gyms] == ["Planet Gym"]


def test_ratings_and_review_counts(client):
    gyms = {g["name"]: g for g in client.get("/api/gyms?query=o").json()["gyms"]}
    assert gyms["Iron Works"]["average_rating"] == 4.5
    assert gyms["Iron Works"]["review_count"] == 2
    assert gyms["Planet Gym"]["average_rating"] is None
    assert gyms["Planet Gym"]["review_count"] == 0


def test_no_matches_returns_empty_list(client):
    assert client.get("/api/gyms?query=nothing-here").json() == {"gyms": []}


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_search_rejected(client, query):
    response = client.get("/api/gyms", params={"query": query})
    assert response.status_code == 400
    assert response.json() == {"error": "Enter a gym name or location"}


@pytest.mark.parametrize("query", ["%", "_"])
def test_wildcards_are_treated_as_plain_text(client, query):
    assert client.get("/api/gyms", params={"query": query}).json() == {"gyms": []}


def test_gym_detail(client):
    response = client.get(f"/api/gyms/{GYM_A}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Iron Works"
    assert body["average_rating"] == 4.5
    assert body["review_count"] == 2
    assert body["equipment"] == []


def test_unknown_gym_is_404(client):
    response = client.get(f"/api/gyms/{MISSING}")
    assert response.status_code == 404
    assert response.json() == {"error": "Gym not found"}


def test_invalid_gym_id_rejected(client):
    assert client.get("/api/gyms/not-a-uuid").status_code == 400


def test_routes_require_authentication(client):
    del app.dependency_overrides[get_current_user]
    assert client.get("/api/gyms?query=iron").status_code == 401
    assert client.get(f"/api/gyms/{GYM_A}").status_code == 401