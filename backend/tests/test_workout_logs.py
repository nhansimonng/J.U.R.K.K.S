from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models.user import User
from app.models.workout_log import WorkoutLog

ALICE = "aaaaaaaa-1111-4111-8111-111111111111"
BOB = "bbbbbbbb-2222-4222-8222-222222222222"
ENTRY = {"exercise_name": "Bench Press", "sets": 3, "reps": 10,
         "weight": 135, "weight_unit": "lb", "log_date": "2026-10-26"}


@compiles(PostgresUUID, "sqlite")
def sqlite_uuid(type_, compiler, **kwargs):
    return "CHAR(32)"


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
    User.__table__.create(engine)
    WorkoutLog.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([User(id=UUID(ALICE), username="alice"),
                    User(id=UUID(BOB), username="bob")])
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


def test_create_list_and_delete(client):
    assert client.get("/api/users/me/workout-logs").json() == {"logs": []}
    response = client.post("/api/workout-logs", json=ENTRY)
    assert response.status_code == 201
    saved = response.json()
    assert {k: v for k, v in saved.items() if k != "id"} == ENTRY
    assert client.get("/api/users/me/workout-logs").json() == {"logs": [saved]}
    response = client.delete(f"/api/workout-logs/{saved['id']}")
    assert response.status_code == 204 and response.content == b""
    assert client.get("/api/users/me/workout-logs").json() == {"logs": []}
    assert client.delete(f"/api/workout-logs/{saved['id']}").status_code == 404


def test_other_users_cannot_read_or_delete_logs(client):
    saved = client.post("/api/workout-logs", json=ENTRY).json()
    app.dependency_overrides[get_current_user] = lambda: {"id": BOB}
    assert client.get("/api/users/me/workout-logs").json() == {"logs": []}
    assert client.delete(f"/api/workout-logs/{saved['id']}").status_code == 404
    app.dependency_overrides[get_current_user] = lambda: {"id": ALICE}
    assert len(client.get("/api/users/me/workout-logs").json()["logs"]) == 1


def test_date_filters_and_newest_first(client):
    for day in ("2026-10-24", "2026-10-26", "2026-10-25"):
        assert client.post("/api/workout-logs", json={**ENTRY, "log_date": day}).status_code == 201
    logs = client.get("/api/users/me/workout-logs").json()["logs"]
    assert [log["log_date"] for log in logs] == ["2026-10-26", "2026-10-25", "2026-10-24"]
    logs = client.get("/api/users/me/workout-logs?from=2026-10-25&to=2026-10-25").json()["logs"]
    assert [log["log_date"] for log in logs] == ["2026-10-25"]
    assert client.get("/api/users/me/workout-logs?from=2026-10-26&to=2026-10-24").status_code == 400
    assert client.get("/api/users/me/workout-logs?from=bad-date").status_code == 400


@pytest.mark.parametrize("change", [
    {"sets": 0}, {"reps": -1}, {"sets": 1.5}, {"reps": True},
    {"sets": 2147483648}, {"weight": -1}, {"weight": "NaN"},
    {"weight_unit": "stone"}, {"exercise_name": "  "},
    {"log_date": "2026-02-30"}, {"user_id": BOB},
])
def test_invalid_inputs_do_not_save(client, change):
    response = client.post("/api/workout-logs", json={**ENTRY, **change})
    assert response.status_code == 400
    assert set(response.json()) == {"error"}
    assert client.get("/api/users/me/workout-logs").json() == {"logs": []}


def test_zero_weight_kg_and_trimmed_name(client):
    response = client.post("/api/workout-logs", json={**ENTRY, "weight": 0,
                           "weight_unit": "kg", "exercise_name": " Push Up "})
    assert response.status_code == 201
    assert response.json()["exercise_name"] == "Push Up"


def test_all_routes_require_authentication(client):
    del app.dependency_overrides[get_current_user]
    assert client.post("/api/workout-logs", json=ENTRY).status_code == 401
    assert client.get("/api/users/me/workout-logs").status_code == 401
    assert client.delete(f"/api/workout-logs/{ALICE}").status_code == 401
