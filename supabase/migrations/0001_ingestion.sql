create table raw_rounds (
  id text primary key,
  payload jsonb not null,
  fetched_at timestamptz not null default now()
);
create table companies (
  id text primary key,
  name text not null,
  country text not null,
  city_raw text,
  city text,
  region text,
  sectors text[] not null default '{}',
  techeu_url text not null,
  website text,
  description text,
  founded int,
  details_fetched_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table rounds (
  id text primary key,
  company_id text not null references companies(id),
  date date not null,
  stage text,
  raw_round_type text,
  amount_eur bigint,
  amount_native numeric,
  currency text,
  size_category text not null check (size_category in ('small','medium','large')),
  investors text[] not null default '{}',
  source_url text not null,
  source_domain text,
  confidence text,
  updated_at timestamptz not null default now()
);
create index rounds_date_idx on rounds (date desc);
create index rounds_company_idx on rounds (company_id);
create index companies_country_city_idx on companies (country, city);
create table sync_runs (
  id bigint generated always as identity primary key,
  command text not null,
  started_at timestamptz not null,
  finished_at timestamptz not null,
  status text not null check (status in ('success','failed')),
  rounds_upserted int not null default 0,
  rounds_removed int not null default 0,
  companies_upserted int not null default 0,
  details_fetched int not null default 0,
  requests_made int not null default 0,
  error text
);
alter table raw_rounds enable row level security;
alter table companies enable row level security;
alter table rounds enable row level security;
alter table sync_runs enable row level security;
