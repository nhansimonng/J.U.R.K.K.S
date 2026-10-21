-- Users (id matches Supabase Auth)
create table users (
  id uuid primary key references auth.users(id) on delete cascade,
  username text not null,
  created_at timestamptz default now()
);

create table gyms (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text,
  latitude decimal,
  longitude decimal
);

create table equipment (
  id uuid primary key default gen_random_uuid(),
  gym_id uuid not null references gyms(id) on delete cascade,
  name text not null,
  availability text,
  condition text
);

create table gym_reviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  gym_id uuid not null references gyms(id) on delete cascade,
  rating integer not null check (rating between 1 and 5),
  review_text varchar(1000),
  photo_path text,
  busy_hour_info text,
  created_at timestamptz default now()
);

create table plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  name text not null,
  fitness_goal text,
  is_public boolean default false
);

create table exercises (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references plans(id) on delete cascade,
  name text not null,
  muscle_group text,
  sets integer check (sets > 0),
  reps integer check (reps > 0),
  required_equipment text[]
);

create table workout_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  exercise_name text not null,
  sets integer check (sets > 0),
  reps integer check (reps > 0),
  weight decimal check (weight >= 0),
  weight_unit text,
  log_date date not null default current_date
);

create table calorie_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  food_name text not null,
  portion decimal check (portion > 0),
  portion_unit text,
  calories decimal check (calories >= 0),
  log_date date not null default current_date
);

create table saved_plans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  plan_id uuid not null references plans(id) on delete cascade,
  unique (user_id, plan_id)
);

create table moderation_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  review_id uuid not null references gym_reviews(id) on delete cascade,
  reason text not null,
  status text default 'pending'
);

-- Indexes for common lookups
create index on gym_reviews (gym_id);
create index on equipment (gym_id);
create index on workout_logs (user_id, log_date);
create index on calorie_logs (user_id, log_date);
create index on exercises (plan_id);