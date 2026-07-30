-- ============================================================
-- WeAwareNews — Supabase SQL Schema
-- ============================================================
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================


-- ── Extensions ───────────────────────────────────────────────
create extension if not exists "uuid-ossp";


-- ── Roles lookup table ────────────────────────────────────────
create table if not exists public.roles (
  name    text primary key,
  display text        not null,
  level   integer     not null default 0
);

comment on table public.roles is
  'Lookup table of application roles ordered by privilege level.';


-- ── User profiles ─────────────────────────────────────────────
-- Mirrors auth.users but holds app-specific data.
-- A row is created automatically by a trigger on sign-up.
create table if not exists public.profiles (
  id            uuid        primary key references auth.users (id) on delete cascade,
  email         text        not null,
  full_name     text,
  avatar_url    text,
  role          text        not null default 'reader' references public.roles (name),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

comment on table public.profiles is
  'One row per authenticated user; extends auth.users.';


-- ── Auto-create profile on new user sign-up ──────────────────
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name, role)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', split_part(new.email, '@', 1)),
    coalesce(new.raw_user_meta_data ->> 'role', 'reader')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();


-- ── Auto-update updated_at timestamp ─────────────────────────
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_profiles_updated_at on public.profiles;
create trigger set_profiles_updated_at
  before update on public.profiles
  for each row execute procedure public.set_updated_at();


-- ── Row-Level Security ────────────────────────────────────────
alter table public.profiles enable row level security;
alter table public.roles    enable row level security;

-- Anyone can read roles
drop policy if exists "Roles are public" on public.roles;
create policy "Roles are public"
  on public.roles for select using (true);

-- Users can read their own profile
drop policy if exists "Users can view own profile" on public.profiles;
create policy "Users can view own profile"
  on public.profiles for select
  using (auth.uid() = id);

-- Users can update their own profile (but NOT change role)
drop policy if exists "Users can update own profile" on public.profiles;
create policy "Users can update own profile"
  on public.profiles for update
  using (auth.uid() = id)
  with check (
    auth.uid() = id
    and role = (select role from public.profiles where id = auth.uid())
  );

-- Service role can do everything (used by Python scripts)
drop policy if exists "Service role full access to profiles" on public.profiles;
create policy "Service role full access to profiles"
  on public.profiles for all
  using (auth.role() = 'service_role');


-- ── Indexes ───────────────────────────────────────────────────
create index if not exists profiles_email_idx on public.profiles (email);
create index if not exists profiles_role_idx  on public.profiles (role);



-- ── Done ──────────────────────────────────────────────────────
-- After running this, go back to auth/setup_auth.py and run:
--   python setup_auth.py
-- to seed the roles table with default values.
