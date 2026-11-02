"""USDA food search and server-calculated calorie logs."""
from collections import OrderedDict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config, integrations
from app.api_schemas import FoodResults, CalorieCreated, CalorieDay
from app.auth import get_current_user, get_profile
from app.database import get_db
from app.models import CalorieLog

router = APIRouter(tags=["Food and Calories"])
BASE_URL = "https://api.nal.usda.gov/fdc/v1"


class FoodCache:
    """One-day, bounded in-memory cache for this student app's single server."""
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            entry = self.entries.get(key)
            if entry and monotonic() - entry[0] < 86400:
                return entry[1]
            self.entries.pop(key, None)
            return None

    def put(self, key, value):
        with self.lock:
            self.entries[key] = (monotonic(), value)
            self.entries.move_to_end(key)
            while len(self.entries) > 1000:
                self.entries.popitem(last=False)


cache = FoodCache()


def usda(path, **params):
    if not config.USDA_API_KEY:
        raise HTTPException(503, "Food search needs a USDA API key")
    return integrations.json_request("GET", f"{BASE_URL}/{path}", "USDA",
                                     params={**params, "api_key": config.USDA_API_KEY})


def energy(data):
    # USDA nutrients are per 100 g. Prefer standard Energy (1008), then Atwater.
    found = {}
    for item in data.get("foodNutrients", []):
        nutrient = item.get("nutrient", item)
        nutrient_id = nutrient.get("id", item.get("nutrientId"))
        unit = nutrient.get("unitName", item.get("unitName", ""))
        value = item.get("amount", item.get("value"))
        if str(unit).lower() == "kcal" and value is not None:
            try:
                value = Decimal(str(value))
                if value.is_finite() and value >= 0:
                    found[int(nutrient_id)] = value
            except (ValueError, TypeError, ArithmeticError):
                continue
    for nutrient_id in (1008, 2048, 2047):
        if nutrient_id in found:
            return found[nutrient_id]
    return None


def food_summary(data):
    kcal = energy(data)
    if kcal is None or not data.get("fdcId") or not data.get("description"):
        return None
    return {"food_id": str(data["fdcId"]), "name": data["description"],
            "reference_portion": 100, "reference_unit": "g", "reference_calories": float(kcal)}


@router.get("/api/foods/search", response_model=FoodResults)
def search_foods(query: str = Query(..., min_length=1, max_length=200),
                 identity: dict = Depends(get_current_user)):
    query = query.strip()
    if not query:
        raise HTTPException(400, "Enter a food name")
    key = ("search", query.lower())
    try:
        data = usda("foods/search", query=query, pageSize=20)
    except HTTPException as error:
        cached = cache.get(key)
        if cached is not None and error.status_code in (429, 502, 503):
            return {"foods": cached, "cached_only": True}
        if error.status_code == 429:
            return {"foods": [], "cached_only": True}
        raise
    foods = [item for food in data.get("foods", []) if (item := food_summary(food)) is not None]
    cache.put(key, foods)
    return {"foods": foods, "cached_only": False}


def food_details(food_id):
    cached = cache.get(("detail", food_id))
    if cached is not None:
        return cached
    try:
        food = usda(f"food/{food_id}")
    except HTTPException as error:
        if error.status_code == 429:
            raise HTTPException(503, "USDA temporarily unavailable; try again later") from None
        raise
    if energy(food) is None:
        raise HTTPException(400, "Calorie information is unavailable for this food")
    cache.put(("detail", food_id), food)
    return food


def grams_per_unit(food, unit):
    if unit == "g":
        return Decimal(1)
    if unit == "oz":
        return Decimal("28.349523125")
    if unit == "serving" and str(food.get("servingSizeUnit", "")).lower() in ("g", "gr", "gram"):
        value = Decimal(str(food.get("servingSize", 0)))
        if value.is_finite() and value > 0:
            return value
    for portion in food.get("foodPortions", []):
        label = str((portion.get("measureUnit") or {}).get("name", "")).strip().lower()
        modifier = str(portion.get("modifier", "")).strip().lower()
        # Only exact measures: never assume a cup is 100 g or a serving is one cup.
        if label not in (unit, unit + "s") and modifier not in (unit, unit + "s"):
            continue
        amount, grams = Decimal(str(portion.get("amount", 0))), Decimal(str(portion.get("gramWeight", 0)))
        if amount.is_finite() and grams.is_finite() and amount > 0 and grams > 0:
            return grams / amount
    raise HTTPException(400, "No conversion for this portion unit; use g or oz")


class CalorieRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    food_id: str = Field(pattern=r"^[0-9]{1,12}$")
    food_name: str = Field(min_length=1, max_length=500)
    portion: Decimal = Field(gt=0, le=100000, allow_inf_nan=False)
    portion_unit: Literal["g", "oz", "cup", "serving"]
    log_date: date


def entry_item(entry):
    return {"id": entry.id, "food_name": entry.food_name, "portion": float(entry.portion or 0),
            "portion_unit": entry.portion_unit, "calories": float(entry.calories or 0)}


def daily_total(db, user_id, day):
    total = db.scalar(select(func.coalesce(func.sum(CalorieLog.calories), 0)).where(
        CalorieLog.user_id == user_id, CalorieLog.log_date == day))
    return float(total)


@router.post("/api/calorie-logs", status_code=201, response_model=CalorieCreated)
def log_calories(body: CalorieRequest, identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    food = food_details(body.food_id)
    calories = (energy(food) * body.portion * grams_per_unit(food, body.portion_unit) / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    profile = get_profile(identity, db)
    entry = CalorieLog(user_id=profile.id, food_name=food["description"], portion=body.portion,
                       portion_unit=body.portion_unit, calories=calories, log_date=body.log_date)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {**entry_item(entry), "log_date": entry.log_date,
            "daily_total": daily_total(db, profile.id, body.log_date)}


@router.get("/api/calorie-logs", response_model=CalorieDay)
def list_calories(day: date = Query(..., alias="date"), identity: dict = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    user_id = UUID(identity["id"])
    entries = db.scalars(select(CalorieLog).where(CalorieLog.user_id == user_id,
                                                CalorieLog.log_date == day).order_by(CalorieLog.id)).all()
    return {"date": day, "entries": [entry_item(e) for e in entries],
            "daily_total": daily_total(db, user_id, day)}


@router.delete("/api/calorie-logs/{entry_id}", status_code=204)
def delete_calories(entry_id: UUID, identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = db.scalar(select(CalorieLog).where(CalorieLog.id == entry_id,
                                             CalorieLog.user_id == UUID(identity["id"])))
    if entry is None:
        raise HTTPException(404, "Calorie entry not found")
    db.delete(entry)
    db.commit()
    return Response(status_code=204)
