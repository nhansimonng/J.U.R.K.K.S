"""Integration tests with real ORM operations and isolated provider doubles."""
from io import BytesIO
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import JSON, create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import config, foods, integrations, places, reviews
from app.auth import get_access_token, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import Equipment, Exercise, Gym, GymReview, Plan, User

A = "aaaaaaaa-1111-4111-8111-111111111111"
B = "bbbbbbbb-2222-4222-8222-222222222222"
G = "cccccccc-3333-4333-8333-333333333333"
PLAN = {"name": "Leg day", "fitness_goal": "strength", "is_public": True,
        "exercises": [{"name": "Squat", "muscle_group": "legs", "sets": 3, "reps": 8,
                       "required_equipment": ["barbell"]}]}
FOOD = {"fdcId": 123, "description": "Chicken", "foodNutrients": [
    {"nutrient": {"id": 1008, "unitName": "kcal"}, "amount": 165}],
    "servingSize": 50, "servingSizeUnit": "g",
    "foodPortions": [{"amount": 1, "gramWeight": 140, "measureUnit": {"name": "cup"}}]}
LOG = {"food_id": "123", "food_name": "Client name", "portion": 150,
       "portion_unit": "g", "log_date": "2026-11-02"}


@pytest.fixture
def full_setup(monkeypatch, request):
    monkeypatch.setattr(config, "GOOGLE_MAPS_API_KEY", None)
    monkeypatch.setattr(config, "USDA_API_KEY", None)
    monkeypatch.setattr(config, "SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "test-key")
    monkeypatch.setattr(foods, "cache", foods.FoodCache())
    if request.config.getoption("--postgres"):
        # Temp tables shadow public tables for this connection only. The outer
        # transaction is always rolled back; public tables are never modified.
        from app.database import engine
        connection = engine.connect()
        outer = connection.begin()
        from sqlalchemy.schema import CreateTable
        for table in Base.metadata.sorted_tables:
            sql = str(CreateTable(table).compile(dialect=engine.dialect))
            connection.exec_driver_sql(sql.replace("CREATE TABLE", "CREATE TEMPORARY TABLE", 1))
        def session():
            return Session(bind=connection, join_transaction_mode="create_savepoint")
    else:
        column = Exercise.__table__.c.required_equipment
        monkeypatch.setattr(column, "type", column.type.with_variant(JSON(), "sqlite"))
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        @event.listens_for(engine, "connect")
        def fk(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(engine)
        def session():
            return Session(engine)
    with session() as db:
        db.add_all([User(id=UUID(A), username="alice"), User(id=UUID(B), username="bob")])
        db.add(Gym(id=UUID(G), name="Campus Gym", address="San Jose", latitude=37.33, longitude=-121.88))
        db.commit()
    def database():
        with session() as db:
            yield db
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: {"id": A}
    app.dependency_overrides[get_access_token] = lambda: "test-token"
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, session
    app.dependency_overrides.clear()
    if request.config.getoption("--postgres"):
        outer.rollback()
        connection.close()
    else:
        engine.dispose()


def create_plan(client, **changes):
    result = client.post("/api/workout-plans", json={**PLAN, **changes})
    assert result.status_code == 201, result.text
    return result.json()


def test_community_filters_bookmarks_and_privacy(full_setup):
    client, session = full_setup
    plan = create_plan(client)
    create_plan(client, name="Private", is_public=False)
    app.dependency_overrides[get_current_user] = lambda: {"id": B}
    listing = client.get("/api/workout-plans?goal=strength&muscle_group=legs").json()["plans"]
    assert len(listing) == 1 and listing[0]["author_username"] == "alice"
    assert client.get("/api/workout-plans?goal=other").json() == {"plans": []}
    for _ in range(2):
        assert client.post(f"/api/workout-plans/{plan['id']}/save").status_code == 201
    assert len(client.get("/api/users/me/saved-plans").json()["plans"]) == 1
    app.dependency_overrides[get_current_user] = lambda: {"id": A}
    assert client.get("/api/users/me/saved-plans").json() == {"plans": []}
    assert client.put(f"/api/workout-plans/{plan['id']}", json={**PLAN, "is_public": False}).status_code == 200
    app.dependency_overrides[get_current_user] = lambda: {"id": B}
    assert client.get("/api/users/me/saved-plans").json() == {"plans": []}
    assert client.post(f"/api/workout-plans/{plan['id']}/save").status_code == 403
    assert client.delete(f"/api/workout-plans/{plan['id']}/save").status_code == 204


def test_recommendations_never_expose_other_private_plans(full_setup):
    client, _ = full_setup
    create_plan(client, is_public=False)
    app.dependency_overrides[get_current_user] = lambda: {"id": B}
    assert client.get("/api/recommendations?goal=strength").json() == {"plans": []}
    app.dependency_overrides[get_current_user] = lambda: {"id": A}
    assert len(client.get("/api/recommendations?muscle_group=legs").json()["plans"]) == 1
    assert client.get("/api/recommendations").status_code == 400


def test_equipment_and_compatibility(full_setup):
    client, _ = full_setup
    plan = create_plan(client)
    alternative = {"name": "Bodyweight Squat", "muscle_group": "legs", "sets": 3, "reps": 8,
                   "required_equipment": []}
    create_plan(client, name="Alternatives", exercises=[alternative])
    url = f"/api/gyms/{G}/compatibility?plan_id={plan['id']}"
    result = client.get(url).json()
    assert result["compatible"] is False
    assert result["results"][0]["status"] == "unconfirmed"
    assert result["results"][0]["alternatives"][0]["name"] == "Bodyweight Squat"
    body = {"name": " Barbell ", "availability": "available", "condition": "good"}
    saved = client.post(f"/api/gyms/{G}/equipment", json=body)
    assert saved.status_code == 201
    assert saved.json()["name"] == "barbell"
    assert client.get(url).json()["compatible"] is True
    saved2 = client.post(f"/api/gyms/{G}/equipment", json={**body, "condition": "broken"})
    assert saved2.json()["id"] == saved.json()["id"]
    assert client.get(url).json()["results"][0]["status"] == "unavailable"
    assert len(client.get(f"/api/gyms/{G}/equipment").json()["equipment"]) == 1
    assert client.post(f"/api/gyms/{G}/equipment", json={**body, "availability": "fake"}).status_code == 400
    assert client.get(f"/api/gyms/{uuid4()}/equipment").status_code == 404


def test_reviews_aggregate_pagination_and_reports(full_setup):
    client, _ = full_setup
    for rating in (4, 5):
        result = client.post(f"/api/gyms/{G}/reviews", json={"rating": rating, "busy_hour_info": "5pm-8pm"})
        assert result.status_code == 201, result.text
    assert result.json()["average_rating"] == 4.5
    listing = client.get(f"/api/gyms/{G}/reviews?limit=1").json()
    assert listing["total"] == 2 and len(listing["reviews"]) == 1
    assert listing["reviews"][0]["username"] == "alice"
    detail = client.get(f"/api/gyms/{G}").json()
    assert detail["average_rating"] == 4.5
    assert detail["busy_hours"] == [{"label": "5pm-8pm", "mentions": 2}]
    report = client.post(f"/api/reviews/{result.json()['id']}/reports", json={"reason": "Spam"})
    assert report.status_code == 201 and report.json()["status"] == "pending"
    assert client.post(f"/api/reviews/{result.json()['id']}/reports", json={"reason": " "}).status_code == 400
    for invalid in ({"rating": 6}, {"rating": True}, {"rating": 3, "review_text": "x" * 1001}):
        assert client.post(f"/api/gyms/{G}/reviews", json=invalid).status_code == 400
    assert client.get(f"/api/gyms/{G}/reviews?limit=0").status_code == 400


def test_gym_distance_equipment_filters(full_setup):
    client, _ = full_setup
    assert client.get("/api/gyms?lat=37.33").status_code == 400
    results = client.get("/api/gyms?lat=37.33&lng=-121.88&radius_km=1").json()["gyms"]
    assert results[0]["distance_km"] == 0
    assert client.get("/api/gyms?lat=0&lng=0&radius_km=1").json() == {"gyms": []}
    client.post(f"/api/gyms/{G}/equipment", json={"name": "barbell", "availability": "available", "condition": "good"})
    assert len(client.get("/api/gyms?equipment=barbell").json()["gyms"]) == 1
    assert client.get("/api/gyms?equipment=barbell,bench").json() == {"gyms": []}


def test_calories_conversion_totals_ownership(full_setup, monkeypatch):
    client, _ = full_setup
    monkeypatch.setattr(foods, "usda", lambda *args, **kwargs: FOOD)
    result = client.post("/api/calorie-logs", json=LOG)
    assert result.status_code == 201, result.text
    assert result.json()["calories"] == 247.5 and result.json()["food_name"] == "Chicken"
    entry_id = result.json()["id"]
    result = client.post("/api/calorie-logs", json={**LOG, "portion_unit": "serving", "portion": 2})
    assert result.json()["calories"] == 165 and result.json()["daily_total"] == 412.5
    result = client.post("/api/calorie-logs", json={**LOG, "portion_unit": "cup", "portion": 1})
    assert result.json()["calories"] == 231
    result = client.post("/api/calorie-logs", json={**LOG, "portion_unit": "oz", "portion": 1})
    assert result.json()["calories"] == 46.78
    assert len(client.get("/api/calorie-logs?date=2026-11-02").json()["entries"]) == 4
    app.dependency_overrides[get_current_user] = lambda: {"id": B}
    assert client.get("/api/calorie-logs?date=2026-11-02").json()["daily_total"] == 0
    assert client.delete(f"/api/calorie-logs/{entry_id}").status_code == 404
    app.dependency_overrides[get_current_user] = lambda: {"id": A}
    assert client.delete(f"/api/calorie-logs/{entry_id}").status_code == 204
    for bad in ({"portion": 0}, {"portion_unit": "bowl"}, {"calories": 0}, {"food_id": "../secrets"}):
        assert client.post("/api/calorie-logs", json={**LOG, **bad}).status_code == 400


def test_no_fake_calories_when_unit_data_missing(full_setup, monkeypatch):
    client, _ = full_setup
    monkeypatch.setattr(foods, "usda", lambda *args, **kwargs: {**FOOD, "foodPortions": []})
    result = client.post("/api/calorie-logs", json={**LOG, "portion_unit": "cup"})
    assert result.status_code == 400
    assert client.get("/api/calorie-logs?date=2026-11-02").json()["daily_total"] == 0


def test_food_search_and_rate_limit_cache(full_setup, monkeypatch):
    client, _ = full_setup
    assert client.get("/api/foods/search?query=chicken").status_code == 503
    search_food = {"fdcId": 123, "description": "Chicken", "foodNutrients": [
        {"nutrientId": 1008, "unitName": "KCAL", "value": 165}]}
    monkeypatch.setattr(foods, "usda", lambda *args, **kwargs: {"foods": [search_food]})
    response = client.get("/api/foods/search?query=chicken").json()
    assert response["foods"][0]["reference_calories"] == 165 and not response["cached_only"]
    def rate_limit(*args, **kwargs):
        raise HTTPException(429, "limit")
    monkeypatch.setattr(foods, "usda", rate_limit)
    response = client.get("/api/foods/search?query=chicken").json()
    assert response["cached_only"] and len(response["foods"]) == 1
    assert client.get("/api/foods/search?query=unknown").json() == {"foods": [], "cached_only": True}


def test_photo_validation_and_ownership(full_setup, monkeypatch):
    client, _ = full_setup
    calls = []
    monkeypatch.setattr(integrations, "request", lambda *args, **kwargs: calls.append((args, kwargs)))
    assert client.post("/api/reviews/photo", files={"file": ("x.jpg", b"not a photo", "image/jpeg")}).status_code == 400
    assert client.post("/api/reviews/photo", files={"file": ("x.png", b"x" * (500 * 1024 + 1), "image/png")}).status_code == 400
    assert client.post("/api/reviews/photo", files={"file": ("x.svg", b"<svg/>", "image/svg+xml")}).status_code == 400
    image = BytesIO()
    Image.new("RGB", (3, 3)).save(image, format="PNG")
    result = client.post("/api/reviews/photo", files={"file": ("x.png", image.getvalue(), "image/png")})
    assert result.status_code == 201
    path = result.json()["photo_path"]
    assert path.startswith(f"reviews/{A}/")
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-token"
    assert client.post(f"/api/gyms/{G}/reviews", json={"rating": 4, "photo_path": path}).status_code == 201
    app.dependency_overrides[get_current_user] = lambda: {"id": B}
    assert client.post(f"/api/gyms/{G}/reviews", json={"rating": 4, "photo_path": path}).status_code == 400


def test_google_import_is_repeatable(full_setup, monkeypatch):
    client, _ = full_setup
    monkeypatch.setattr(config, "GOOGLE_MAPS_API_KEY", "test")
    calls = []
    def google(*args, **kwargs):
        calls.append((args, kwargs))
        return {"places": [{"id": "google-id", "displayName": {"text": "New Gym"},
                             "formattedAddress": "Main Street", "location": {"latitude": 37.33, "longitude": -121.88}}]}
    monkeypatch.setattr(integrations, "json_request", google)
    for _ in range(2):
        response = client.get("/api/gyms?query=New%20Gym")
        assert response.status_code == 200
        assert len(response.json()["gyms"]) == 1
    assert calls[0][1]["headers"]["X-Goog-Api-Key"] == "test"
    assert calls[0][0][1].endswith("searchText")


def test_provider_timeout_and_rate_limit_are_sanitized(monkeypatch):
    original = httpx.Client
    def handler(request):
        return httpx.Response(429, json={"key": "secret"})
    monkeypatch.setattr(integrations.httpx, "Client", lambda **kwargs:
                        original(transport=httpx.MockTransport(handler), **kwargs))
    with pytest.raises(HTTPException) as error:
        integrations.json_request("GET", "https://provider.example", "Provider")
    assert error.value.status_code == 429 and "secret" not in error.value.detail


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/workout-plans", None), ("GET", "/api/users/me/saved-plans", None),
    ("POST", f"/api/workout-plans/{G}/save", None), ("DELETE", f"/api/workout-plans/{G}/save", None),
    ("GET", "/api/recommendations?goal=strength", None),
    ("GET", f"/api/gyms/{G}/compatibility?plan_id={G}", None),
    ("GET", f"/api/gyms/{G}/equipment", None),
    ("POST", f"/api/gyms/{G}/equipment", {"name": "bench", "availability": "available", "condition": "good"}),
    ("GET", f"/api/gyms/{G}/reviews", None), ("POST", f"/api/gyms/{G}/reviews", {"rating": 4}),
    ("POST", f"/api/reviews/{G}/reports", {"reason": "spam"}),
    ("GET", "/api/foods/search?query=chicken", None), ("POST", "/api/calorie-logs", LOG),
    ("GET", "/api/calorie-logs?date=2026-11-02", None), ("DELETE", f"/api/calorie-logs/{G}", None),
])
def test_new_routes_require_auth(full_setup, method, path, body):
    client, _ = full_setup
    del app.dependency_overrides[get_current_user]
    del app.dependency_overrides[get_access_token]
    assert client.request(method, path, json=body).status_code == 401


def test_photo_multipart_body_limit(full_setup):
    client, _ = full_setup
    response = client.post('/api/reviews/photo', content=b'x' * (600 * 1024),
                           headers={'Content-Type': 'multipart/form-data; boundary=test'})
    assert response.status_code == 400
    assert response.json() == {'error': 'Photo is too large'}


def test_broken_equipment_is_unavailable_even_if_unconfirmed(full_setup):
    client, _ = full_setup
    plan = create_plan(client)
    client.post(f'/api/gyms/{G}/equipment', json={
        'name': 'barbell', 'availability': 'unconfirmed', 'condition': 'broken'})
    response = client.get(f"/api/gyms/{G}/compatibility?plan_id={plan['id']}")
    assert response.json()['results'][0]['status'] == 'unavailable'


def test_google_text_query_can_return_name_not_containing_query(full_setup, monkeypatch):
    client, _ = full_setup
    monkeypatch.setattr(config, 'GOOGLE_MAPS_API_KEY', 'test')
    monkeypatch.setattr(integrations, 'json_request', lambda *args, **kwargs: {'places': [
        {'id': 'p123', 'displayName': {'text': 'Iron Works'}, 'formattedAddress': 'San Jose',
         'location': {'latitude': 37.33, 'longitude': -121.88}}]})
    response = client.get('/api/gyms?query=gyms%20in%20San%20Jose')
    assert response.status_code == 200
    assert response.json()['gyms'][0]['name'] == 'Iron Works'


def test_openapi_includes_contract_endpoints():
    schema = app.openapi()
    expected = {
        '/api/auth/register': ['post'], '/api/auth/login': ['post'], '/api/auth/logout': ['post'],
        '/api/users/me': ['get'], '/api/gyms': ['get'], '/api/gyms/{gym_id}': ['get'],
        '/api/gyms/{gym_id}/equipment': ['get', 'post'], '/api/gyms/{gym_id}/reviews': ['get', 'post'],
        '/api/reviews/photo': ['post'], '/api/reviews/{review_id}/reports': ['post'],
        '/api/workout-logs': ['post'], '/api/users/me/workout-logs': ['get'],
        '/api/workout-logs/{log_id}': ['delete'], '/api/workout-plans': ['get', 'post'],
        '/api/users/me/workout-plans': ['get'], '/api/workout-plans/{plan_id}': ['get', 'put', 'delete'],
        '/api/workout-plans/{plan_id}/save': ['post', 'delete'], '/api/users/me/saved-plans': ['get'],
        '/api/recommendations': ['get'], '/api/gyms/{gym_id}/compatibility': ['get'],
        '/api/foods/search': ['get'], '/api/calorie-logs': ['get', 'post'],
        '/api/calorie-logs/{entry_id}': ['delete']}
    for path, methods in expected.items():
        for method in methods:
            operation = schema['paths'][path][method]
            if path not in ('/api/auth/register', '/api/auth/login'):
                assert operation['security'] == [{'HTTPBearer': []}]
