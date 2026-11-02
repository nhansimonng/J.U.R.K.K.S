# Workout plans

Uses the existing `plans`, `exercises`, and `saved_plans` tables from schema.sql.
No schema changes or seed data are needed. Start the backend using AUTH_SETUP.md.
All routes require `Authorization: Bearer <access_token>`.

| Method | Path | Success |
| --- | --- | --- |
| POST | /api/workout-plans | 201: created plan with exercise IDs |
| GET | /api/users/me/workout-plans | 200: {"plans": [...]} |
| GET | /api/workout-plans/{plan_id} | 200: plan with exercises |
| PUT | /api/workout-plans/{plan_id} | 200: replaced plan with exercises |
| DELETE | /api/workout-plans/{plan_id} | 204: empty body |

Example POST or PUT body:

```json
{
  "name": "Push Day",
  "fitness_goal": "muscle_gain",
  "is_public": false,
  "exercises": [
    {
      "name": "Bench Press",
      "muscle_group": "chest",
      "sets": 4,
      "reps": 8,
      "required_equipment": ["barbell", "bench"]
    }
  ]
}
```

Plans default to private. Only their owner can edit or delete them; signed-in
users can read another user's public plan by ID. The personal list includes
only the caller's plans. The caller cannot submit a user_id to choose an owner.

PUT replaces the entire plan, including its exercises, in one transaction.
It assigns new exercise IDs; frontend code should use the returned IDs.
The current database schema does not store exercise order. GET uses ID order,
so the frontend must not rely on the submitted order being retained.
Deleting a plan uses the existing cascading foreign keys to remove its
exercises and any bookmarks. Missing plans return 404; forbidden access returns
403; invalid input returns 400. Errors use {"error":"message"}.

Validation requires a nonblank plan name, at least one exercise, nonblank
exercise names, and positive integer sets/reps. Text fields are limited to 200
characters, plans to 100 exercises, and equipment lists to 50 names.
Fitness goal and muscle group are optional; equipment defaults to an empty list.

Public community browsing and bookmark endpoints are implemented in community.py; see README.md.
Automated tests cover CRUD, ownership, public visibility, validation, cascading
deletion and rollback. SQLite substitutes JSON for PostgreSQL arrays only in
tests; live PostgreSQL verification is still needed for the real array storage
and row locks. Run `python -m pytest` from the repository root.

Manual check in /docs: log in and authorize, create a plan, list your plans,
read the plan by ID, replace it with PUT, and delete it. Verify that blank names
and zero sets return 400. No live data is created by the automated tests.
