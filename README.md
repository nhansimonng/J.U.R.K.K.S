# Pump Check — J.U.R.K.K.S

FastAPI backend for the CMPE 131 project. Frontend requests follow the team's
Pump Check API Contract v0.1. `/docs` shows the implemented request/response shapes.

## Run the backend

From the repository root:

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Create `.env` from `.env.example` **only if you do not already have `.env`**.
Fill in SUPABASE_URL, SUPABASE_ANON_KEY (a publishable key also works), and
DATABASE_URL. Keep the existing tables in Supabase; do not rerun schema.sql on
an initialized project. Use a database connection with SSL enabled.

```sh
python -m uvicorn app.main:app --app-dir backend --reload
```

Open http://127.0.0.1:8000/docs. Log in, then authorize with the access token.
See [authentication setup](backend/AUTH_SETUP.md) for details.

## Implemented features

| Feature | Routes | External setup |
| --- | --- | --- |
| Authentication | register, login, logout, current user | Supabase Auth and DB |
| Workout logs | create, personal history with date range, delete | Existing DB |
| Workout plans | create, personal list, detail, full edit, delete | Existing DB |
| Community | public browse/filter, bookmark/unbookmark, saved plans | Existing DB |
| Gym search | name/address, location radius, equipment filter | Local records work now; Google optional |
| Gym details | ratings, equipment, busy-hour mentions | Existing DB |
| Reviews | create, paginated list, report for moderation | Existing DB |
| Equipment | list, add/update availability and condition | Existing DB |
| Recommendations | visible plans matching goal and/or muscle group | Existing DB |
| Compatibility | equipment status and matching exercise alternatives | Existing DB |
| Food search | USDA lookup, cached fallback on rate limit | USDA key |
| Calorie logs | server-calculated calories, daily totals, own-entry deletion | USDA key for uncached food IDs |
| Review photos | validate JPEG/PNG, upload, attach to own review | Supabase Storage bucket/policies |

All data routes require a verified user token. Only public plans or the caller's
own plans appear in recommendations/alternatives. Workout and calorie logs are
private to their owner. Any signed-in user may contribute equipment reports,
as specified in the contract. Moderation reports are saved as pending; an admin
moderation screen is not included in this API contract.

## Remaining service setup (not applied automatically)

1. **USDA:** obtain a FoodData Central API key, put it in `USDA_API_KEY` in `.env`,
   then restart the backend. No fabricated foods are supplied when the key is
   missing. Cached data is bounded to 1,000 entries for 24 hours and is lost on
   restart. On a rate limit, the same query's cached results are returned with
   `cached_only: true`; if none exist, the list is empty.
2. **Google:** enable Places API (New) in a Google Cloud project and configure
   billing/restrictions as required by Google. Put the key in `GOOGLE_MAPS_API_KEY`
   and restart. Search then retrieves matching gyms and saves/updates them for
   reviews and equipment. Without the key, search covers existing local gyms.
   No Google requests or paid-service setup were performed during development.
   Before public release, implement the required Google Maps attribution and
   review Google's storage/caching terms for the team's chosen deployment.
3. **Photos:** review and run `backend/setup/storage.sql` once in Supabase's SQL
   editor. It creates a public `review-photos` bucket and authenticated upload
   policies restricted to the user's folder. The script is not run by startup.
   If the bucket already exists, check that it is public with the stated file
   limit and MIME types. Review photos are public, not private uploads.
4. **Database access:** inspect existing RLS policies before release. The
   contract routes data through the backend; publishable keys should not allow
   direct reading/writing of private tables. `backend/setup/backend_only_rls.sql`
   enables RLS for these tables without adding direct-access policies. Review it
   before applying; it does not remove any existing permissive policies.
5. **Frontend:** use `frontend/api.js`; set `CORS_ORIGINS` for Mert's actual local
   frontend origin. The helper is not a completed website. See the handoff below.

References: [USDA API](https://fdc.nal.usda.gov/api-guide/),
[Google Places](https://developers.google.com/maps/documentation/places/web-service/text-search),
[Supabase Storage policies](https://supabase.com/docs/guides/storage/security/access-control).

## Frontend handoff

```js
import { createApi } from './api.js';
const api = createApi({
  baseUrl: 'http://127.0.0.1:8000',
  onUnauthorized: () => { window.location.href = '/login.html'; }
});
await api.login({ email, password });
const { plans } = await api.myPlans();
```

The helper stores access tokens in sessionStorage, sends bearer headers, clears
expired tokens on 401, supports multipart uploads, and handles empty 204 replies.
Render user text with textContent, not raw innerHTML. Display API errors and keep
form values so the user can correct them. Registration may return
`confirmation_required` instead of a session; show the message and request login
after the user confirms their email. There is no automatic refresh-token flow.

Use the backend host's URL when the frontend runs on a different computer:
`127.0.0.1` always points to the current computer. Deployment is a separate step.

Photo flow: compress to at most 500 KB in the browser, call `uploadPhoto(file)`,
then pass its `photo_path` to `addReview`. Only .jpg and .png are accepted. The
server checks the actual file format, image dimensions, and size, and removes
metadata. Uploads that are never attached to a review remain in Storage and can
be cleaned up from the dashboard.

Food search reports calories per 100 g. Calorie logging fetches the food detail
and ignores client-supplied food names/calorie amounts when computing totals.
Grams and ounces always have defined conversions. Cups and servings require a
food-specific gram weight from USDA; otherwise use g or oz. They are never
assumed to be equal to 100 g. Saved calories are rounded to two decimal places.

Equipment names are lowercase and whitespace-normalized. Names must match
between exercises and equipment (use consistent labels such as `barbell`);
synonym inference is not included. Broken equipment is unavailable. Missing or
unconfirmed equipment produces an unconfirmed result. Alternatives come from
visible saved plans, so an empty database has no recommendations or alternatives.

Plan edits replace exercises and generate new exercise IDs. The current schema
has no exercise-order column; clients must not rely on submission order.
The complete request example is in `backend/WORKOUT_PLANS.md`.

## Tests and verification status

```sh
python -m pytest -q
node --test frontend/api.test.mjs
```

Current local result: **93 Python tests + 7 JavaScript tests passed**.
They cover auth, ownership/privacy, logs, plans, recommendations, equipment,
review aggregation, photos, calorie conversions, provider error handling, and
frontend token/HTTP behavior. Provider calls are simulated; local DB tests use
SQLite with a test-only JSON substitute for PostgreSQL arrays.

Earlier live checks confirmed auth, workout-log CRUD, and workout-plan creation
and listing. New review/community/calorie/photo flows have not been live-tested
against Supabase or external providers. The user chose local-only verification.

An optional PostgreSQL test mode exists for a separately approved run:
`python -m pytest backend/tests/test_remaining_backend.py --postgres -q`.
It uses the configured database connection, temporary tables, and an outer
rollback. Do not run it against a shared database without team authorization.
No shared schema, storage configuration, or production data was changed by
these tests. The existing dependency stack emits a Starlette TestClient
httpx deprecation warning; tests still pass.
