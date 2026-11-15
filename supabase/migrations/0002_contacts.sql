-- Contacts read on company sites (Phase 2, second plan).
-- Applied by hand in the Supabase SQL editor.

-- Reading state of each company.
alter table companies
  add column contacts_checked_at timestamptz,
  add column contacts_outcome text check (contacts_outcome in (
    'ok', 'robots_forbidden', 'unreachable', 'little_text', 'other_domain_only',
    'contact_form_only', 'no_address', 'not_own_site')),
  add column contacts_attempts int not null default 0,
  add column contacts_next_at timestamptz;
create index companies_contacts_next_idx on companies (country, contacts_next_at);

-- One row per address found on a company's own site.
create table contact_emails (
  company_id text not null references companies(id) on delete cascade,
  address text not null,
  type text not null check (type in ('personal', 'careers', 'generic')),
  source_url text not null,
  read_at timestamptz not null,
  primary key (company_id, address)
);

-- One row per person suggested for a company. A suggestion: the student
-- confirms it on the source page before it is used.
create table contact_people (
  company_id text not null references companies(id) on delete cascade,
  name text not null,
  title text not null,
  categories text[] not null default '{}',
  level text not null check (level in ('head', 'manager')),
  source_url text not null,
  read_at timestamptz not null,
  primary key (company_id, name)
);

-- Who asked not to be listed. A null person_key excludes the whole company.
-- A person is kept as a key, never as a name.
create table contact_exclusions (
  id bigint generated always as identity primary key,
  company_id text not null references companies(id),
  person_key text,
  created_at timestamptz not null default now()
);
create unique index contact_exclusions_unique_idx
  on contact_exclusions (company_id, coalesce(person_key, ''));

-- One row per run of the contact scraper. Numbers only.
create table contact_runs (
  id bigint generated always as identity primary key,
  started_at timestamptz not null,
  finished_at timestamptz not null,
  status text not null check (status in ('success', 'failed')),
  country text not null,
  companies_visited int not null default 0,
  with_address int not null default 0,
  with_people int not null default 0,
  outcomes jsonb not null default '{}',
  error text
);

-- Only the service key reads or writes these tables.
alter table contact_emails enable row level security;
alter table contact_people enable row level security;
alter table contact_exclusions enable row level security;
alter table contact_runs enable row level security;

-- The key of a person: SHA-256 of the company id, a line break and the
-- name, trimmed, inner whitespace collapsed, lower case. The scraper computes
-- the same value (kaltstart.contacts.exclusions.person_key).
create function contact_person_key(p_company_id text, p_person_name text)
returns text language sql immutable as $$
  select encode(sha256(convert_to(
    p_company_id || E'\n' || lower(regexp_replace(btrim(p_person_name), '\s+', ' ', 'g')),
    'UTF8')), 'hex');
$$;

-- Removal on request, run by the owner in the SQL editor:
--   select exclude_company('<company id>');
create function exclude_company(p_company_id text)
returns void language plpgsql security definer set search_path = public as $$
begin
  insert into contact_exclusions (company_id, person_key)
    values (p_company_id, null) on conflict do nothing;
  delete from contact_emails where company_id = p_company_id;
  delete from contact_people where company_id = p_company_id;
end;
$$;

--   select exclude_person('<company id>', 'First Last');
-- Removes the person and their personal addresses: those that carry the last
-- name, are exactly the first name, or the first initial and the last name
-- (the rule of kaltstart.contacts.selection.address_owner).
create function exclude_person(p_company_id text, p_person_name text)
returns void language plpgsql security definer set search_path = public as $$
declare
  v_key text := contact_person_key(p_company_id, p_person_name);
  v_words text[] := regexp_split_to_array(lower(btrim(p_person_name)), '\s+');
  v_first text := v_words[1];
  v_last text := v_words[array_length(v_words, 1)];
begin
  insert into contact_exclusions (company_id, person_key)
    values (p_company_id, v_key) on conflict do nothing;
  delete from contact_people
    where company_id = p_company_id
      and contact_person_key(company_id, name) = v_key;
  delete from contact_emails
    where company_id = p_company_id
      and type = 'personal'
      and (v_last = any (regexp_split_to_array(split_part(address, '@', 1), '[._-]'))
           or split_part(address, '@', 1) = v_first
           or split_part(address, '@', 1) = left(v_first, 1) || v_last);
end;
$$;

-- Supabase lets its API roles call the functions of the public schema by
-- default. These three are for the owner only, in the SQL editor.
revoke all on function contact_person_key(text, text) from public, anon, authenticated;
revoke all on function exclude_company(p_company_id text) from public, anon, authenticated;
revoke all on function exclude_person(p_company_id text, p_person_name text) from public, anon, authenticated;
