-- Students, their mails and the reservation of a slot (Phase 4).
-- Applied by hand in the Supabase SQL editor, after 0003.
-- See docs/superpowers/specs/2026-11-16-phase-4-web-app-design.md.

-- Settings only the owner and the server read. The invitation code is set
-- once in the SQL editor:
--   insert into app_settings values ('invitation_code', '<code>');
create table app_settings (
  key text primary key,
  value text not null
);

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  first_name text not null default '',
  last_name text not null default '',
  programme text not null default '',
  degree_level text check (degree_level in ('bachelor', 'master')),
  attach_cv boolean not null default true,
  languages text[] not null default '{en}',
  target_role text check (target_role in
    ('product', 'growth', 'data', 'operations', 'business_development')),
  request text check (request in ('internship', 'part_time')),
  start_date date,
  duration_months int,
  workload_percent int,
  link text,
  preferred_countries text[] not null default '{}',
  preferred_sectors text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- The showcase sentences of a student (two at most, decision D71).
create table showcases (
  student_id uuid not null references auth.users(id) on delete cascade,
  position int not null check (position in (1, 2)),
  text_en text,
  text_de text,
  primary key (student_id, position)
);

-- A kept mail. Previews are never stored. When a student deletes their
-- account the row stays, anonymised, for the company cap and the Phase 5 rates.
create table mails (
  id uuid primary key default gen_random_uuid(),
  student_id uuid references auth.users(id) on delete set null,
  company_id text not null references companies(id),
  round_id text references rounds(id) on delete set null,
  address text,
  address_type text check (address_type in ('personal', 'careers', 'generic')),
  person_name text,
  person_key text,
  person_choice text not null check (person_choice in
    ('suggested', 'other_on_list', 'typed', 'team')),
  person_source_url text,
  style text not null check (style in ('direct', 'round', 'formal')),
  language text not null check (language in ('en', 'de')),
  company_line text,
  used_company_line boolean not null default false,
  subject text,
  body text,
  status text not null default 'generated' check (status in
    ('generated', 'copied', 'sent', 'human_reply', 'positive_reply', 'abandoned')),
  created_at timestamptz not null default now(),
  copied_at timestamptz,
  sent_at timestamptz,
  human_reply_at timestamptz,
  positive_reply_at timestamptz,
  abandoned_at timestamptz,
  -- How many mails were kept before for this company and round: picks the
  -- wordings, so that mails to one company differ.
  variant int not null default 0,
  -- Size category of the round, which sets the round cap.
  size_category text check (size_category in ('small', 'medium', 'large'))
);
create index mails_company_idx on mails (company_id, created_at desc);
create index mails_student_idx on mails (student_id, created_at desc);

alter table app_settings enable row level security;
alter table profiles enable row level security;
alter table showcases enable row level security;
alter table mails enable row level security;

-- Keeping a mail: the rules of kaltstart.api.rules checked and the row
-- inserted in one transaction, one company at a time, so that two students
-- clicking on the last slot cannot both get it. The limits come from the
-- server (rules.LIMITS, in p_row->'limits'): changing one needs no migration.
-- An abandoned mail frees its slot only if its text was never copied.
create function reserve_mail(p_student_id uuid, p_company_id text,
                             p_person_key text, p_row jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_limits jsonb := p_row->'limits';
  v_cap_days int := (v_limits->>'cap_days')::int;
  v_speed_days int := (v_limits->>'speed_days')::int;
  v_round_cap int := (v_limits->'round_cap'->>(p_row->>'size_category'))::int;
  v_taken int;
  v_oldest timestamptz;
  v_id uuid;
begin
  if v_limits is null then
    raise exception 'reserve_mail needs the limits of the server';
  end if;
  -- The student first, then the company, always in this order: the speed and
  -- pending limits hold even with two tabs keeping two companies at once.
  perform pg_advisory_xact_lock(hashtext(p_student_id::text));
  perform pg_advisory_xact_lock(hashtext(p_company_id));

  select count(*), min(created_at) into v_taken, v_oldest from mails
    where company_id = p_company_id
      and (status <> 'abandoned' or copied_at is not null)
      and created_at > now() - make_interval(days => v_cap_days);
  if v_taken >= (v_limits->>'company_cap')::int then
    return jsonb_build_object('ok', false, 'reason', 'company_full',
                              'frees_on', (v_oldest + make_interval(days => v_cap_days))::date);
  end if;
  if v_round_cap is not null and (select count(*) from mails
        where company_id = p_company_id and round_id = p_row->>'round_id'
          and (status <> 'abandoned' or copied_at is not null)) >= v_round_cap then
    return jsonb_build_object('ok', false, 'reason', 'round_full', 'frees_on', null);
  end if;
  select count(*), min(created_at) into v_taken, v_oldest from mails
    where student_id = p_student_id
      and created_at > now() - make_interval(days => v_speed_days);
  if v_taken >= (v_limits->>'speed')::int then
    return jsonb_build_object('ok', false, 'reason', 'student_speed',
                              'frees_on', (v_oldest + make_interval(days => v_speed_days))::date);
  end if;
  if (select count(*) from mails where student_id = p_student_id
        and status in ('generated', 'copied')
        and created_at > now() - make_interval(days => (v_limits->>'presumed_sent_days')::int))
        >= (v_limits->>'pending')::int then
    return jsonb_build_object('ok', false, 'reason', 'student_pending', 'frees_on', null);
  end if;
  if exists (select 1 from mails where student_id = p_student_id
               and company_id = p_company_id and status <> 'abandoned') then
    return jsonb_build_object('ok', false, 'reason', 'company_done', 'frees_on', null);
  end if;
  if p_person_key is not null and exists (
       select 1 from mails where student_id = p_student_id
         and person_key = p_person_key and status <> 'abandoned') then
    return jsonb_build_object('ok', false, 'reason', 'person_done', 'frees_on', null);
  end if;

  insert into mails (student_id, company_id, round_id, address, address_type, person_name,
                     person_key, person_choice, person_source_url, style, language,
                     company_line, used_company_line, subject, body, variant, size_category)
  values (p_student_id, p_company_id, p_row->>'round_id', p_row->>'address',
          p_row->>'address_type', p_row->>'person_name', p_person_key,
          p_row->>'person_choice', p_row->>'person_source_url', p_row->>'style',
          p_row->>'language', p_row->>'company_line',
          coalesce((p_row->>'used_company_line')::boolean, false),
          p_row->>'subject', p_row->>'body',
          coalesce((p_row->>'variant')::int, 0), p_row->>'size_category')
  returning id into v_id;
  return jsonb_build_object('ok', true, 'id', v_id);
end;
$$;

-- Nobody signs up without the invitation code, even calling Supabase directly,
-- and nobody at all while no code is set.
create function check_invitation_code()
returns trigger language plpgsql security definer set search_path = public as $$
declare
  v_code text := (select value from app_settings where key = 'invitation_code');
begin
  if v_code is null or v_code = ''
     or coalesce(new.raw_user_meta_data->>'invitation_code', '') <> v_code then
    raise exception 'Sign-up refused.';
  end if;
  return new;
end;
$$;
create trigger check_invitation_code before insert on auth.users
  for each row execute function check_invitation_code();

-- A student deleted from the Supabase dashboard is anonymised exactly as one
-- who deletes their account in the app: their mails stay for the company caps
-- and the Phase 5 rates, without anything that names anybody.
create function anonymise_student()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  update mails set student_id = null, subject = null, body = null, person_name = null,
                   person_source_url = null, address = null, company_line = null
    where student_id = old.id;
  delete from showcases where student_id = old.id;
  delete from profiles where id = old.id;
  return old;
end;
$$;
create trigger anonymise_student before delete on auth.users
  for each row execute function anonymise_student();

-- Removal on request now also blanks the person's name in mails already
-- generated for that company.
create or replace function exclude_company(p_company_id text)
returns void language plpgsql security definer set search_path = public as $$
begin
  insert into contact_exclusions (company_id, person_key)
    values (p_company_id, null) on conflict do nothing;
  delete from contact_emails where company_id = p_company_id;
  delete from contact_people where company_id = p_company_id;
  update mails set person_name = null, person_source_url = null
    where company_id = p_company_id;
end;
$$;

create or replace function exclude_person(p_company_id text, p_person_name text)
returns text language plpgsql security definer set search_path = public as $$
declare
  v_name text := contact_normalise_name(p_person_name);
  v_words text[] := string_to_array(v_name, ' ');
  v_first text := v_words[1];
  v_last text := v_words[array_length(v_words, 1)];
  v_people int;
  v_addresses int;
begin
  if v_name is null or v_name = '' then
    raise exception 'The name is empty.';
  end if;
  if not exists (select 1 from companies where id = p_company_id) then
    raise exception 'No company has this id: copy it from the companies table.';
  end if;

  insert into contact_exclusions (company_id, person_key)
    values (p_company_id, contact_key(p_company_id, v_name))
    on conflict do nothing;
  insert into contact_exclusions (company_id, address_key)
    select p_company_id, contact_key(p_company_id, value)
    from unnest(array['last:' || v_last, 'whole:' || v_first,
                      'whole:' || left(v_first, 1) || v_last]) as value
    on conflict do nothing;

  delete from contact_people
    where company_id = p_company_id
      and contact_person_key(company_id, name) = contact_key(p_company_id, v_name);
  get diagnostics v_people = row_count;

  -- The same address forms as kaltstart.contacts.selection.address_owner,
  -- whatever type the address was stored as.
  delete from contact_emails
    where company_id = p_company_id
      and (v_last = any (regexp_split_to_array(lower(split_part(address, '@', 1)), '[._-]'))
           or lower(split_part(address, '@', 1)) in (v_first, left(v_first, 1) || v_last));
  get diagnostics v_addresses = row_count;

  -- Mails already generated keep the key (rule 4) but lose the name.
  update mails set person_name = null, person_source_url = null
    where company_id = p_company_id and person_key = contact_key(p_company_id, v_name);

  if v_people = 0 then
    return format('Exclusion saved, but no stored person has this name. Check the '
                  'spelling with: select name from contact_people where company_id = %L; '
                  '%s address(es) removed.', p_company_id, v_addresses);
  end if;
  return format('Removed %s person(s) and %s address(es). They will not be added again.',
                v_people, v_addresses);
end;
$$;

revoke all on function reserve_mail(uuid, text, text, jsonb) from public, anon, authenticated;
revoke all on function check_invitation_code() from public, anon, authenticated;
revoke all on function anonymise_student() from public, anon, authenticated;
revoke all on function exclude_company(p_company_id text) from public, anon, authenticated;
revoke all on function exclude_person(p_company_id text, p_person_name text) from public, anon, authenticated;
