# Authentication setup

Implemented: registration, login, logout, and the current user's profile.
Supabase stores passwords. The backend calls Supabase Auth over HTTPS and stores
only the user's ID and username in the existing `public.users` table.

## Run locally

From the repository root:

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Fill in `.env` with your team's Supabase URL, anon key, and database connection
URL. Do not commit it or paste secrets into chat. An existing `backend/.env`
takes precedence over the root `.env`; environment variables take precedence
over both. No service-role key is needed for authentication.

The database must already contain the tables in `backend/schema.sql`. Do not
rerun that entire file on an existing database. Use the project's SSL-enabled
database connection settings. Confirm that `public.users` exists and references
`auth.users`. Profiles are created on the first successful registration with a
session, login, or authenticated `/me` call. Existing profiles are preserved.

```sh
python -m uvicorn app.main:app --app-dir backend --reload
```

Open http://127.0.0.1:8000/docs. Register with an email you control, then log in.
Copy `access_token` into **Authorize** and try `/api/users/me`, then logout.

## Frontend contract

| Method | Route | Result |
| --- | --- | --- |
| POST | `/api/auth/register` | 201: user, access_token, expires_at; or email confirmation message |
| POST | `/api/auth/login` | 200: user, access_token, expires_at |
| POST | `/api/auth/logout` | 204: no response body |
| GET | `/api/users/me` | 200: id, email, username, created_at |

Register takes `email`, `password` (at least 8 characters), and `username`
(1–50 characters). Login takes `email` and `password`. Protected calls use
`Authorization: Bearer <access_token>`. Errors use `{"error":"message"}`.

**Small extension to the draft contract:** when email confirmation is enabled,
registration returns `{"confirmation_required":true,"message":"Check your email
to confirm your account, then log in."}` with status 201, without a token.
The frontend should display the message and direct the user to login after
confirmation. Configure Supabase's Site URL to your frontend login page.
Supabase can deliberately return the same response for an existing account;
the API preserves this behavior instead of revealing account existence.

Logout ends the current Supabase session; the frontend must delete its token.
Already-issued access tokens can remain valid until their expiry. This version
does not implement refresh tokens, password reset, social login, or a week-long
session guarantee. After expiry, log in again. `expires_at` uses Supabase's expiry.

Other backend routes can use `Depends(get_current_user)` from `app.auth` to
verify the bearer token, and use its `id` for ownership checks. Never accept a
client-provided user ID as proof of ownership.

## Verification

```sh
python -m pytest
```

Tests simulate Supabase responses and use a temporary SQLite profile table.
They do not change the live project. Live checks still required: register,
confirm email if enabled, login, verify the profile in `public.users`, call
`/me`, try a bad token, and logout. Supabase project settings and database
permissions must be checked during that integration test.

References: [Supabase Auth API](https://github.com/supabase/auth/blob/master/openapi.yaml),
[signup behavior](https://supabase.com/docs/reference/python/auth-signup),
[logout behavior](https://supabase.com/docs/reference/python/auth-signout).
