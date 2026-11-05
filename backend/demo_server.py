"""Run the whole site locally with NO Supabase, USDA or Google keys. For demos and QA.

    python backend/demo_server.py          (from the repository root)
    then open http://127.0.0.1:8000/

This is the real FastAPI app and the real route code. Only the outside services are
replaced, and everything lives in memory (it resets on every start):
  * database          -> a throwaway SQLite database
  * Supabase Auth     -> an in-memory login (any password of 8+ characters works for new users)
  * USDA FoodData     -> a few built-in foods
  * Photo storage     -> accepted and discarded
It listens on 127.0.0.1 only. NEVER deploy this: the login is fake and not secure.

Demo account:  demo@pumpcheck.demo / demo-pass-123
"""
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import JSON, create_engine, event
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import auth, config, foods, integrations, reviews
from app.database import Base, get_db
from app.main import app
from app.models import Exercise, Gym

DEMO_EMAIL, DEMO_PASSWORD = "demo@pumpcheck.demo", "demo-pass-123"


@compiles(PostgresUUID, "sqlite")
def _sqlite_uuid(type_, compiler, **kwargs):
    return "CHAR(32)"  # same SQLite shim the team's tests use


# ---------- database: throwaway SQLite ----------
column = Exercise.__table__.c.required_equipment
column.type = column.type.with_variant(JSON(), "sqlite")  # PostgreSQL arrays -> JSON
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def _foreign_keys(dbapi_connection, record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


Base.metadata.create_all(engine)


def _database():
    with Session(engine) as db:
        yield db


app.dependency_overrides[get_db] = _database

# ---------- fake Supabase Auth ----------
config.SUPABASE_URL, config.SUPABASE_ANON_KEY = "http://demo.invalid", "demo-key"
USERS = {}    # email -> {id, password, username}
TOKENS = {}   # access token -> email


def _identity(email):
    user = USERS[email]
    return {"id": user["id"], "email": email, "user_metadata": {"username": user["username"]}}


def fake_auth_request(method, path, *, token=None, payload=None, params=None):
    if path == "signup":
        email = payload["email"].lower()
        if email in USERS:
            raise HTTPException(400, "Email already in use")
        USERS[email] = {"id": str(uuid.uuid4()), "password": payload["password"],
                        "username": payload["data"]["username"]}
        path = "token"
        payload = {"email": email, "password": payload["password"]}
    if path == "token":
        email = payload["email"].lower()
        if email not in USERS or USERS[email]["password"] != payload["password"]:
            raise HTTPException(401, "Invalid email or password")
        access = "demo-" + uuid.uuid4().hex
        TOKENS[access] = email
        return {"user": _identity(email), "access_token": access, "expires_in": 3600}
    if path in ("user", "logout"):
        email = TOKENS.get(token)
        if email is None:
            raise HTTPException(401, "Invalid or expired access token")
        if path == "logout":
            TOKENS.pop(token, None)
            return {}
        return _identity(email)
    raise HTTPException(400, "Unsupported in demo")


auth.auth_request = fake_auth_request

# ---------- fake USDA (calories per 100 g) ----------
FOODS = {
    "170567": ("Chicken breast, cooked", 165), "168875": ("White rice, cooked", 130),
    "170903": ("Egg, whole, cooked", 155), "173944": ("Banana, raw", 89),
    "171705": ("Oatmeal, cooked", 71), "174032": ("Greek yogurt, plain", 59),
    "170188": ("Almonds, raw", 579), "169967": ("Broccoli, cooked", 35),
}


def _food(fdc_id):
    name, kcal = FOODS[fdc_id]
    return {"fdcId": int(fdc_id), "description": name, "servingSize": 100, "servingSizeUnit": "g",
            "foodNutrients": [{"nutrient": {"id": 1008, "unitName": "kcal"}, "amount": kcal}],
            "foodPortions": [{"amount": 1, "gramWeight": 140, "measureUnit": {"name": "cup"}}]}


def fake_usda(path, **params):
    if path == "foods/search":
        text = params["query"].lower()
        return {"foods": [_food(i) for i, (n, _) in FOODS.items() if text in n.lower()]}
    fdc_id = path.split("/")[-1]
    if fdc_id not in FOODS:
        raise HTTPException(404, "Food not found")
    return _food(fdc_id)


foods.usda = fake_usda
config.GOOGLE_MAPS_API_KEY = None  # gym search uses the seeded gyms only
integrations.request = lambda *args, **kwargs: None  # photo storage: accept and discard
reviews.integrations.request = integrations.request


# ---------- sample data, created through the real API ----------
def seed():
    gyms = [("Test Gym Downtown San Jose", "100 Test St, San Jose, CA", 37.3382, -121.8863),
            ("Test Gym Willow Glen", "200 Test Ave, San Jose, CA", 37.3092, -121.8984),
            ("Test Gym Santana Row", "300 Test Blvd, San Jose, CA", 37.3209, -121.9484),
            ("Test Gym Berryessa", "400 Test Way, San Jose, CA", 37.3688, -121.8680),
            ("Test Gym Campbell", "500 Test Rd, Campbell, CA", 37.2872, -121.9500)]
    with Session(engine) as db:
        db.add_all(Gym(name=n, address=a, latitude=la, longitude=lo) for n, a, la, lo in gyms)
        db.commit()

    with TestClient(app) as client:
        def signup(email, username):
            res = client.post("/api/auth/register", json={"email": email, "password": "demo-pass-123", "username": username})
            assert res.status_code == 201 and "access_token" in res.json(), (email, res.status_code, res.text)
            return {"Authorization": "Bearer " + res.json()["access_token"]}

        me = signup(DEMO_EMAIL, "Mert Hamsioglu")
        krish, kristik, umar = signup("krish@pumpcheck.demo", "krish"), signup("kristik@pumpcheck.demo", "kristik"), signup("umar@pumpcheck.demo", "umar")
        by_name = {g["name"]: g["id"] for g in client.get("/api/gyms?query=Test", headers=me).json()["gyms"]}
        berryessa, downtown = by_name["Test Gym Berryessa"], by_name["Test Gym Downtown San Jose"]

        for gym_id, items in {berryessa: [("squat rack", "available", "good"), ("barbell", "available", "good"),
                                          ("bench", "available", "fair"), ("dumbbell", "available", "good"),
                                          ("leg press", "unconfirmed", "worn")],
                              downtown: [("barbell", "available", "good"), ("bench", "available", "good"),
                                         ("leg press", "available", "good"), ("dumbbell", "available", "good")]}.items():
            for name, availability, condition in items:
                client.post(f"/api/gyms/{gym_id}/equipment", headers=krish,
                            json={"name": name, "availability": availability, "condition": condition})

        for headers, rating, text, busy in [
                (krish, 5, "Plenty of squat racks. Gets packed after 5pm.", "5pm-8pm"),
                (kristik, 4, "Clean and quiet in the mornings.", None),
                (umar, 4, "Leg press is a little worn but works.", "6pm-8pm")]:
            client.post(f"/api/gyms/{berryessa}/reviews", headers=headers,
                        json={"rating": rating, "review_text": text, "busy_hour_info": busy})

        def exercise(name, muscle, sets, reps, equipment):
            return {"name": name, "muscle_group": muscle, "sets": sets, "reps": reps, "required_equipment": equipment}

        client.post("/api/workout-plans", headers=krish, json={
            "name": "Leg Day Basics", "fitness_goal": "strength", "is_public": True, "exercises": [
                exercise("Back Squat", "legs", 5, 5, ["squat rack", "barbell"]),
                exercise("Leg Press", "legs", 3, 12, ["leg press"]),
                exercise("Goblet Squat", "legs", 3, 10, ["dumbbell"])]})
        client.post("/api/workout-plans", headers=kristik, json={
            "name": "Push Day", "fitness_goal": "muscle_gain", "is_public": True, "exercises": [
                exercise("Bench Press", "chest", 4, 8, ["barbell", "bench"]),
                exercise("Dumbbell Shoulder Press", "shoulders", 3, 10, ["dumbbell", "bench"])]})
        client.post("/api/workout-plans", headers=me, json={
            "name": "My Leg Day", "fitness_goal": "muscle_gain", "is_public": False, "exercises": [
                exercise("Back Squat", "legs", 4, 8, ["squat rack", "barbell"]),
                exercise("Leg Press", "legs", 3, 12, ["leg press"])]})
        client.post("/api/workout-logs", headers=me, json={
            "exercise_name": "Bench Press", "sets": 3, "reps": 10, "weight": 135, "weight_unit": "lb",
            "log_date": time.strftime("%Y-%m-%d")})


if __name__ == "__main__":
    seed()
    print(f"\nDemo ready: http://127.0.0.1:8000/   (log in: {DEMO_EMAIL} / {DEMO_PASSWORD})\n")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
