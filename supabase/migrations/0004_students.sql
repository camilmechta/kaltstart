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
  abandoned_at timestamptz
);
create index mails_company_idx on mails (company_id, created_at desc);
create index mails_student_idx on mails (student_id, created_at desc);

alter table app_settings enable row level security;
alter table profiles enable row level security;
alter table showcases enable row level security;
alter table mails enable row level security;

-- Keeping a mail: the four rules of spec 7.1 checked and the row inserted in
-- one transaction, one company at a time, so that two students clicking on
-- the last slot cannot both get it. kaltstart.api.rules holds the same rules.
create function reserve_mail(p_student_id uuid, p_company_id text,
                             p_person_key text, p_row jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_taken int;
  v_oldest timestamptz;
  v_id uuid;
begin
  perform pg_advisory_xact_lock(hashtext(p_company_id));

  select count(*), min(created_at) into v_taken, v_oldest from mails
    where company_id = p_company_id and status <> 'abandoned'
      and created_at > now() - interval '30 days';
  if v_taken >= 3 then
    return jsonb_build_object('ok', false, 'reason', 'company_full',
                              'frees_on', (v_oldest + interval '30 days')::date);
  end if;
  if (select count(*) from mails where student_id = p_student_id
        and status in ('generated', 'copied')
        and created_at > now() - interval '7 days') >= 5 then
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
                     company_line, used_company_line, subject, body)
  values (p_student_id, p_company_id, p_row->>'round_id', p_row->>'address',
          p_row->>'address_type', p_row->>'person_name', p_person_key,
          p_row->>'person_choice', p_row->>'person_source_url', p_row->>'style',
          p_row->>'language', p_row->>'company_line',
          coalesce((p_row->>'used_company_line')::boolean, false),
          p_row->>'subject', p_row->>'body')
  returning id into v_id;
  return jsonb_build_object('ok', true, 'id', v_id);
end;
$$;

-- Nobody signs up without the invitation code, even calling Supabase directly.
create function check_invitation_code()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if coalesce(new.raw_user_meta_data->>'invitation_code', '') <>
     coalesce((select value from app_settings where key = 'invitation_code'), '') then
    raise exception 'Sign-up refused.';
  end if;
  return new;
end;
$$;
create trigger check_invitation_code before insert on auth.users
  for each row execute function check_invitation_code();

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
revoke all on function exclude_company(p_company_id text) from public, anon, authenticated;
revoke all on function exclude_person(p_company_id text, p_person_name text) from public, anon, authenticated;
