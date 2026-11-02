"""Public plans, bookmarks, recommendations, and equipment compatibility."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_profile
from app.database import get_db
from app.models import Equipment, Exercise, Gym, Plan, SavedPlan, User
from app.workout_plans import find_plan, plan_response, PlanListResponse
from app.api_schemas import PublicPlans, Bookmark, CompatibilityResponse

router = APIRouter(tags=["Community and Recommendations"])


def normalize(value):
    return " ".join((value or "").lower().split())


def serialize_plans(db, plans, authors=False):
    if not plans:
        return []
    exercises = db.scalars(select(Exercise).where(Exercise.plan_id.in_([p.id for p in plans]))
                          .order_by(Exercise.id)).all()
    users = dict(db.execute(select(User.id, User.username).where(
        User.id.in_([p.user_id for p in plans]))).all()) if authors else {}
    grouped = {}
    for exercise in exercises:
        grouped.setdefault(exercise.plan_id, []).append(exercise)
    results = []
    for plan in plans:
        item = plan_response(plan, grouped.get(plan.id, [])).model_dump()
        if authors:
            item["author_username"] = users.get(plan.user_id)
        results.append(item)
    return results


def filter_plans(query, goal, muscle_group):
    if goal and goal.strip():
        query = query.where(func.lower(Plan.fitness_goal) == goal.strip().lower())
    if muscle_group and muscle_group.strip():
        query = query.where(select(Exercise.id).where(
            Exercise.plan_id == Plan.id,
            func.lower(Exercise.muscle_group) == muscle_group.strip().lower()).exists())
    return query


@router.get("/api/workout-plans", response_model=PublicPlans)
def public_plans(goal: str | None = Query(None, max_length=200),
                 muscle_group: str | None = Query(None, max_length=200),
                 limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                 identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    query = filter_plans(select(Plan).where(Plan.is_public.is_(True)), goal, muscle_group)
    plans = db.scalars(query.order_by(Plan.name, Plan.id).limit(limit).offset(offset)).all()
    return {"plans": serialize_plans(db, plans, authors=True)}


@router.post("/api/workout-plans/{plan_id}/save", status_code=201, response_model=Bookmark)
def save_plan(plan_id: UUID, identity: dict = Depends(get_current_user),
              db: Session = Depends(get_db)):
    profile = get_profile(identity, db)
    # Serialize saves to this plan, including simultaneous requests by one user.
    plan = find_plan(db, plan_id, identity["id"], lock=True)
    if not plan.is_public:
        raise HTTPException(403, "Only public plans can be saved")
    saved = db.scalar(select(SavedPlan).where(SavedPlan.plan_id == plan.id,
                                            SavedPlan.user_id == profile.id))
    if saved is None:
        saved = SavedPlan(plan_id=plan.id, user_id=profile.id)
        db.add(saved)
        db.commit()
        db.refresh(saved)
    return {"id": saved.id, "plan_id": plan.id}


@router.delete("/api/workout-plans/{plan_id}/save", status_code=204)
def unsave_plan(plan_id: UUID, identity: dict = Depends(get_current_user),
                db: Session = Depends(get_db)):
    # Can remove a bookmark even after its plan becomes private.
    db.execute(delete(SavedPlan).where(SavedPlan.plan_id == plan_id,
                                      SavedPlan.user_id == UUID(identity["id"])))
    db.commit()
    return Response(status_code=204)


@router.get("/api/users/me/saved-plans", response_model=PlanListResponse)
def saved_plans(identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    plans = db.scalars(select(Plan).join(SavedPlan, SavedPlan.plan_id == Plan.id).where(
        SavedPlan.user_id == UUID(identity["id"]), Plan.is_public.is_(True))
        .order_by(Plan.name, Plan.id)).all()
    return {"plans": serialize_plans(db, plans)}


@router.get("/api/recommendations", response_model=PlanListResponse)
def recommendations(goal: str | None = Query(None, max_length=200),
                    muscle_group: str | None = Query(None, max_length=200),
                    identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (goal and goal.strip()) and not (muscle_group and muscle_group.strip()):
        raise HTTPException(400, "Provide a goal or a muscle group")
    query = select(Plan).where(or_(Plan.is_public.is_(True), Plan.user_id == UUID(identity["id"])))
    plans = db.scalars(filter_plans(query, goal, muscle_group).order_by(Plan.name, Plan.id).limit(20)).all()
    return {"plans": serialize_plans(db, plans)}


def equipment_status(required, equipment):
    unavailable, unknown = [], []
    for name in sorted({normalize(n) for n in (required or [])}):
        item = equipment.get(name)
        if item is not None and (item.condition == "broken" or item.availability == "unavailable"):
            unavailable.append(name)
        elif item is None or item.availability != "available":
            unknown.append(name)
    return ("unavailable" if unavailable else "unconfirmed" if unknown else "compatible",
            unavailable + unknown)


@router.get("/api/gyms/{gym_id}/compatibility", response_model=CompatibilityResponse)
def compatibility(gym_id: UUID, plan_id: UUID, identity: dict = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    if db.get(Gym, gym_id) is None:
        raise HTTPException(404, "Gym not found")
    plan = find_plan(db, plan_id, identity["id"])
    equipment = {normalize(e.name): e for e in db.scalars(select(Equipment).where(Equipment.gym_id == gym_id))}
    exercises = db.scalars(select(Exercise).where(Exercise.plan_id == plan.id).order_by(Exercise.id)).all()
    candidates = db.scalars(select(Exercise).join(Plan, Plan.id == Exercise.plan_id).where(
        or_(Plan.is_public.is_(True), Plan.user_id == UUID(identity["id"])))
        .order_by(Exercise.name, Exercise.id)).all()
    results = []
    for exercise in exercises:
        status, missing = equipment_status(exercise.required_equipment, equipment)
        alternatives, seen = [], set()
        if status != "compatible" and exercise.muscle_group:
            for candidate in candidates:
                name = normalize(candidate.name)
                if (name == normalize(exercise.name) or name in seen or
                    normalize(candidate.muscle_group) != normalize(exercise.muscle_group)):
                    continue
                if equipment_status(candidate.required_equipment, equipment)[0] == "compatible":
                    alternatives.append({"name": candidate.name, "muscle_group": candidate.muscle_group,
                                         "required_equipment": candidate.required_equipment or []})
                    seen.add(name)
                if len(alternatives) == 3:
                    break
        results.append({"exercise_id": exercise.id, "exercise_name": exercise.name,
                        "status": status, "missing_equipment": missing, "alternatives": alternatives})
    return {"gym_id": gym_id, "plan_id": plan_id,
            "compatible": bool(results) and all(r["status"] == "compatible" for r in results), "results": results}
