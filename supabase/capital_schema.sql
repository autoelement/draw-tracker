-- ═══════════════════════════════════════════════════════════════════
--  X CAP · Capital dashboard schema
--  Run once in the Supabase SQL editor (project jczzctpbrbaavzetidov).
--  Every table is per-user and locked down with RLS, so the published
--  page carries no financial data — it is an empty shell until login.
-- ═══════════════════════════════════════════════════════════════════

-- ── assets ────────────────────────────────────────────────────────
create table if not exists capital_assets (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name_ka    text not null,
  name_en    text,
  amount     numeric not null,                    -- in `currency`, not USD
  currency   text not null default 'USD' check (currency in ('USD','GEL','BTC')),
  valuation  text not null default 'est' check (valuation in ('mkt','est','nom')),
  color      text not null default '--accent',
  note       text,
  sort       int  not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ── liabilities ───────────────────────────────────────────────────
create table if not exists capital_debts (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name_ka    text not null,
  name_en    text,
  amount     numeric not null,
  currency   text not null default 'USD' check (currency in ('USD','GEL','BTC')),
  note       text,
  sort       int  not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ── historical snapshots ──────────────────────────────────────────
-- Stored in USD as recorded on the day. Never recomputed from live
-- rates: a past net worth is a historical fact, not a live figure.
create table if not exists capital_snapshots (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
  date       date not null,
  net_usd    numeric not null,
  gross_usd  numeric,                             -- incl. excluded assets, optional
  gel_rate   numeric,                             -- rate in force that day, if known
  note       text,
  created_at timestamptz not null default now(),
  unique (user_id, date)
);

-- ── investment portfolio (own valuation date) ─────────────────────
create table if not exists capital_portfolio (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name_ka    text not null,
  name_en    text,
  amount     numeric not null,
  currency   text not null default 'USD' check (currency in ('USD','GEL','BTC')),
  color      text not null default '--accent',
  maps_to    uuid references capital_assets(id) on delete set null,
  as_of      date not null default current_date,
  sort       int  not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ── last known FX / crypto rates (cache + offline fallback) ───────
create table if not exists capital_rates (
  user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
  code       text not null,                       -- 'GEL' (per USD) | 'BTC' (USD each)
  rate       numeric not null,
  source     text,
  fetched_at timestamptz not null default now(),
  primary key (user_id, code)
);

-- ── row level security: a user only ever sees their own rows ──────
do $$
declare t text;
begin
  foreach t in array array['capital_assets','capital_debts','capital_snapshots',
                           'capital_portfolio','capital_rates']
  loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists own_rows on %I', t);
    execute format($f$create policy own_rows on %I
                      for all to authenticated
                      using (auth.uid() = user_id)
                      with check (auth.uid() = user_id)$f$, t);
  end loop;
end $$;

-- ── keep updated_at honest ────────────────────────────────────────
create or replace function touch_updated_at() returns trigger
language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

do $$
declare t text;
begin
  foreach t in array array['capital_assets','capital_debts','capital_portfolio']
  loop
    execute format('drop trigger if exists set_updated_at on %I', t);
    execute format('create trigger set_updated_at before update on %I
                    for each row execute function touch_updated_at()', t);
  end loop;
end $$;

create index if not exists capital_snapshots_user_date
  on capital_snapshots (user_id, date);
