-- Review before applying. The API contract sends all data requests through FastAPI.
-- These tables should not be accessible directly with a publishable key.
-- The backend's postgres connection bypasses RLS and enforces ownership in routes.
-- Does not remove any existing policies: check policies before deployment.
alter table public.users enable row level security;
alter table public.gyms enable row level security;
alter table public.equipment enable row level security;
alter table public.gym_reviews enable row level security;
alter table public.plans enable row level security;
alter table public.exercises enable row level security;
alter table public.workout_logs enable row level security;
alter table public.calorie_logs enable row level security;
alter table public.saved_plans enable row level security;
alter table public.moderation_reports enable row level security;
