-- Migration 0008: every kept mail holds its company and round slot, even
-- abandoned (decision D92, finding F5 of the first security scan).
--
-- The address of a mail shows once it is kept (D77), so a student could read
-- it, abandon the mail without pressing "Copy text" and free the slot for a
-- mail that may have been sent. reserve_mail is the one of migration 0004
-- without the two "abandoned and never copied" exceptions; nothing else
-- changes. Paste it whole in the Supabase SQL editor, then run
-- supabase/check_migrations.sql: every column must be true.

create or replace function reserve_mail(p_student_id uuid, p_company_id text,
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
      and created_at > now() - make_interval(days => v_cap_days);
  if v_taken >= (v_limits->>'company_cap')::int then
    return jsonb_build_object('ok', false, 'reason', 'company_full',
                              'frees_on', (v_oldest + make_interval(days => v_cap_days))::date);
  end if;
  if v_round_cap is not null and (select count(*) from mails
        where company_id = p_company_id and round_id = p_row->>'round_id') >= v_round_cap then
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

-- Kept by "create or replace"; repeated so the file reads on its own.
revoke all on function reserve_mail(uuid, text, text, jsonb) from public, anon, authenticated;
