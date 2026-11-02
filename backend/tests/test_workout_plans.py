from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, create_engine, event, select
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import workout_plans
from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models.exercise import Exercise
from app.models.plan import Plan
from app.models.saved_plan import SavedPlan
from app.models.user import User

ALICE = "aaaaaaaa-1111-4111-8111-111111111111"
BOB = "bbbbbbbb-2222-4222-8222-222222222222"
EXERCISE = {"name": "Bench Press", "muscle_group": "chest", "sets": 4, "reps": 8,
            "required_equipment": ["barbell", "bench"]}
BODY = {"name": "Push Day", "fitness_goal": "muscle_gain", "exercises": [EXERCISE]}


@compiles(PostgresUUID, "sqlite")
def sqlite_uuid(type_, compiler, **kwargs):
    return "CHAR(32)"


@pytest.fixture
def setup(monkeypatch):
    # SQLite has no PostgreSQL arrays. Use JSON only in this isolated test engine.
    column = Exercise.__table__.c.required_equipment
    monkeypatch.setattr(column, "type", column.type.with_variant(JSON(), "sqlite"))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
    for model in (User, Plan, Exercise, SavedPlan):
        model.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([User(id=UUID(ALICE), username="alice"), User(id=UUID(BOB), username="bob")])
        db.commit()
    def database():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: {"id": ALICE}
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def create(client, **changes):
    response = client.post("/api/workout-plans", json={**BODY, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_list_read_and_update(setup):
    client, _ = setup
    assert client.get("/api/users/me/workout-plans").json() == {"plans": []}
    plan = create(client)
    assert plan["user_id"] == ALICE and plan["is_public"] is False
    assert plan["exercises"][0]["required_equipment"] == ["barbell", "bench"]
    assert client.get("/api/users/me/workout-plans").json() == {"plans": [plan]}
    assert client.get(f"/api/workout-plans/{plan['id']}").json() == plan
    body = {**BODY, "name": "Updated", "exercises": [{**EXERCISE, "reps": 12}]}
    result = client.put(f"/api/workout-plans/{plan['id']}", json=body)
    assert result.status_code == 200
    assert result.json()["exercises"][0]["reps"] == 12
    assert result.json()["name"] == "Updated"
    assert result.json()["exercises"][0]["id"] != plan["exercises"][0]["id"]
    assert client.get(f"/api/workout-plans/{plan['id']}").json() == result.json()


@pytest.mark.parametrize("public", [False, True])
def test_ownership_and_public_read_access(setup, public):
    client, _ = setup
    plan = create(client, is_public=public)
    app.dependency_overrides[get_current_user] = lambda: {"id": BOB}
    path = f"/api/workout-plans/{plan['id']}"
    assert client.get("/api/users/me/workout-plans").json() == {"plans": []}
    assert client.get(path).status_code == (200 if public else 403)
    assert client.put(path, json=BODY).status_code == 403
    assert client.delete(path).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: {"id": ALICE}
    assert client.get(path).json() == plan


def test_delete_cascades_exercises_and_bookmarks(setup):
    client, engine = setup
    plan = create(client, is_public=True)
    with Session(engine) as db:
        db.add(SavedPlan(user_id=UUID(BOB), plan_id=UUID(plan["id"])))
        db.commit()
    response = client.delete(f"/api/workout-plans/{plan['id']}")
    assert response.status_code == 204 and response.content == b""
    with Session(engine) as db:
        assert db.scalars(select(Exercise)).all() == []
        assert db.scalars(select(SavedPlan)).all() == []
    assert client.get(f"/api/workout-plans/{plan['id']}").status_code == 404


@pytest.mark.parametrize("change", [
    {"name": "  "}, {"exercises": []}, {"user_id": BOB}, {"is_public": "false"},
    {"exercises": [{**EXERCISE, "sets": 0}]},
    {"exercises": [{**EXERCISE, "reps": 1.5}]},
    {"exercises": [{**EXERCISE, "sets": True}]},
    {"exercises": [{**EXERCISE, "name": "  "}]},
    {"exercises": [{**EXERCISE, "required_equipment": [" "]}]},
])
def test_invalid_create_and_update_preserve_data(setup, change):
    client, _ = setup
    plan = create(client)
    bad = {**BODY, **change}
    assert client.post("/api/workout-plans", json=bad).status_code == 400
    assert client.put(f"/api/workout-plans/{plan['id']}", json=bad).status_code == 400
    assert client.get("/api/users/me/workout-plans").json() == {"plans": [plan]}


def test_failed_write_rolls_back_plan_and_exercises(setup, monkeypatch):
    client, engine = setup
    plan = create(client)
    original = workout_plans.add_exercises
    def fail_after_insert(*args):
        original(*args)
        raise RuntimeError("simulated database failure")
    monkeypatch.setattr(workout_plans, "add_exercises", fail_after_insert)
    assert client.post("/api/workout-plans", json=BODY).status_code == 500
    assert client.put(f"/api/workout-plans/{plan['id']}",
                      json={**BODY, "name": "Must roll back"}).status_code == 500
    assert client.get("/api/users/me/workout-plans").json() == {"plans": [plan]}


def test_missing_and_invalid_ids(setup):
    client, _ = setup
    for id_, expected in ((BOB, 404), ("not-a-uuid", 400)):
        path = f"/api/workout-plans/{id_}"
        assert client.get(path).status_code == expected
        assert client.put(path, json=BODY).status_code == expected
        assert client.delete(path).status_code == expected


def test_all_routes_require_authentication(setup):
    client, _ = setup
    del app.dependency_overrides[get_current_user]
    assert client.post("/api/workout-plans", json=BODY).status_code == 401
    assert client.get("/api/users/me/workout-plans").status_code == 401
    assert client.get(f"/api/workout-plans/{BOB}").status_code == 401
    assert client.put(f"/api/workout-plans/{BOB}", json=BODY).status_code == 401
    assert client.delete(f"/api/workout-plans/{BOB}").status_code == 401
