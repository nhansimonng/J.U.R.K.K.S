# Backend deployment on Render

Use a Python Web Service with the existing Supabase project. No new database
or schema reset is needed.

## Service settings

- Repository: `nhansimonng/J.U.R.K.K.S`
- Branch: `setup/project-skeleton`
- Root directory: leave blank (repository root)
- Runtime: Python 3.12
- Build command: `pip install -r requirements.txt`
- Start command: `python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`
- Health check path: `/api/health`
- Instance: Free, for the class demo

Keep one worker for now: the food cache is in memory. Free services sleep after
15 minutes without requests; open the app before presenting the demo.

## Environment variables

Enter values privately in Render's environment settings using the team's local
`.env`. Do not commit or upload `.env` to GitHub.

| Name | Value |
| --- | --- |
| `SUPABASE_URL` | Existing project URL |
| `SUPABASE_ANON_KEY` | Existing publishable/anon key |
| `DATABASE_URL` | Existing Supabase session-pooler URL, with `sslmode=require` |
| `USDA_API_KEY` | Existing USDA key |
| `GOOGLE_MAPS_API_KEY` | Existing Google Places key; this exact variable name is required |
| `REVIEW_PHOTO_BUCKET` | `review-photos` |
| `CORS_ORIGINS` | Exact frontend origin(s), comma-separated, with no trailing slash |

If DATABASE_URL already has query parameters, append `&sslmode=require` instead
of `?sslmode=require`. Preserve URL-encoding of the database password.
No Supabase service-role key is required for the app.

## After deployment

1. Confirm `/api/health` and `/api/health/db` return HTTP 200.
2. Test login in the deployed `/docs`, then a protected route.
3. Set the frontend API helper's `baseUrl` to the deployed HTTPS backend URL.
4. Set `CORS_ORIGINS` to the real frontend origin and redeploy after changes.
5. Verify login, plans, logs, food search, reviews, and photos through the frontend.

Do not rerun `backend/schema.sql` on the existing shared database. Photo storage
and RLS are already configured. Hosting deployment and full browser integration
remain unverified until these checks are completed.

References: https://render.com/docs/deploy-fastapi and https://render.com/docs/free
