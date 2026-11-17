-- Fixes after an outside review (decision D87). Applied by hand in the
-- Supabase SQL editor, after 0006. Earlier migrations are not changed: they
-- are already applied.

-- 1. The profile and its showcase sentences in one transaction ------------------
-- Before, the server deleted the showcase rows, then inserted the new ones: a
-- failure in between lost the previous sentences. A function runs in one
-- transaction: any error leaves the profile and the sentences as they were.
-- Sentences absent from p_showcases are removed on purpose.
create or replace function save_profile_and_showcases(p_student_id uuid, p_profile jsonb,
                                                      p_showcases jsonb)
returns void language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, first_name, last_name, programme, university, degree_level,
                        attach_cv, languages, target_role, request, start_date,
                        duration_months, workload_percent, link, preferred_countries,
                        preferred_sectors, updated_at)
  values (p_student_id,
          coalesce(p_profile->>'first_name', ''), coalesce(p_profile->>'last_name', ''),
          coalesce(p_profile->>'programme', ''), coalesce(p_profile->>'university', ''),
          p_profile->>'degree_level', coalesce((p_profile->>'attach_cv')::boolean, true),
          coalesce(array(select jsonb_array_elements_text(p_profile->'languages')), '{en}'),
          p_profile->>'target_role', p_profile->>'request',
          (p_profile->>'start_date')::date, (p_profile->>'duration_months')::int,
          (p_profile->>'workload_percent')::int, p_profile->>'link',
          coalesce(array(select jsonb_array_elements_text(p_profile->'preferred_countries')), '{}'),
          coalesce(array(select jsonb_array_elements_text(p_profile->'preferred_sectors')), '{}'),
          now())
  on conflict (id) do update set
    first_name = excluded.first_name, last_name = excluded.last_name,
    programme = excluded.programme, university = excluded.university,
    degree_level = excluded.degree_level, attach_cv = excluded.attach_cv,
    languages = excluded.languages, target_role = excluded.target_role,
    request = excluded.request, start_date = excluded.start_date,
    duration_months = excluded.duration_months, workload_percent = excluded.workload_percent,
    link = excluded.link, preferred_countries = excluded.preferred_countries,
    preferred_sectors = excluded.preferred_sectors, updated_at = excluded.updated_at;

  delete from showcases
    where student_id = p_student_id
      and position not in (select (s->>'position')::int
                           from jsonb_array_elements(coalesce(p_showcases, '[]')) as s);
  insert into showcases (student_id, position, text_en, text_de)
    select p_student_id, (s->>'position')::int, s->>'text_en', s->>'text_de'
    from jsonb_array_elements(coalesce(p_showcases, '[]')) as s
  on conflict (student_id, position) do update set
    text_en = excluded.text_en, text_de = excluded.text_de;
end;
$$;

-- 2. A removal on request also clears the kept mails ---------------------------
-- Policy: a kept mail of a removed person, or of a removed company, keeps only
-- what the tracking and the caps need: its id, student, company, round, size
-- category, status and dates, person key (a fingerprint, for "once per
-- person"), person choice, address type, style, language, variant and
-- whether a company line was used. Its address, subject, text, person's name,
-- source page and company line are cleared, and redacted_at says when.
-- Kaltstart cannot reach a copy the student already pasted elsewhere.
alter table mails add column if not exists redacted_at timestamptz;

create or replace function redact_mails(p_company_id text, p_person_key text)
returns int language plpgsql security definer set search_path = public as $$
declare
  v_count int;
begin
  update mails set address = null, subject = null, body = null, person_name = null,
                   person_source_url = null, company_line = null,
                   redacted_at = coalesce(redacted_at, now())
    where company_id = p_company_id
      and (p_person_key is null or person_key = p_person_key)
      and (redacted_at is null or address is not null or body is not null);
  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

create or replace function exclude_company(p_company_id text)
returns void language plpgsql security definer set search_path = public as $$
begin
  insert into contact_exclusions (company_id, person_key)
    values (p_company_id, null) on conflict do nothing;
  delete from contact_emails where company_id = p_company_id;
  delete from contact_people where company_id = p_company_id;
  perform redact_mails(p_company_id, null);
end;
$$;

-- The same removal as in 0004, plus the kept mails of that person. The mails
-- are found by the person key the app stored (SHA-256 of the company and the
-- cleaned name), never by a shared address, so another person's mail stays.
create or replace function exclude_person(p_company_id text, p_person_name text)
returns text language plpgsql security definer set search_path = public as $$
declare
  v_name text := contact_normalise_name(p_person_name);
  v_words text[] := string_to_array(v_name, ' ');
  v_first text := v_words[1];
  v_last text := v_words[array_length(v_words, 1)];
  v_people int;
  v_addresses int;
  v_mails int;
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

  delete from contact_emails
    where company_id = p_company_id
      and (v_last = any (regexp_split_to_array(lower(split_part(address, '@', 1)), '[._-]'))
           or lower(split_part(address, '@', 1)) in (v_first, left(v_first, 1) || v_last));
  get diagnostics v_addresses = row_count;

  v_mails := redact_mails(p_company_id, contact_key(p_company_id, v_name));

  if v_people = 0 then
    return format('Exclusion saved, but no stored person has this name. Check the '
                  'spelling with: select name from contact_people where company_id = %L; '
                  '%s address(es) removed, %s kept mail(s) cleared.',
                  p_company_id, v_addresses, v_mails);
  end if;
  return format('Removed %s person(s) and %s address(es), cleared %s kept mail(s). '
                'They will not be added again.', v_people, v_addresses, v_mails);
end;
$$;

-- Only the owner (SQL editor) and the server may run these.
revoke all on function save_profile_and_showcases(uuid, jsonb, jsonb) from public, anon, authenticated;
revoke all on function redact_mails(text, text) from public, anon, authenticated, service_role;
revoke all on function exclude_company(text) from public, anon, authenticated, service_role;
revoke all on function exclude_person(text, text) from public, anon, authenticated, service_role;
grant execute on function save_profile_and_showcases(uuid, jsonb, jsonb) to service_role;
