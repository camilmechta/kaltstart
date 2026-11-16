-- Fixes after the review of the contact storage (decision D63).
-- Applied by hand in the Supabase SQL editor, after 0002.

-- 1. A removed person's address forms are kept as keys too, so that their
--    address is dropped whatever type it is read as. A row with neither a
--    person key nor an address key still excludes the whole company.
alter table contact_exclusions add column address_key text;
drop index contact_exclusions_unique_idx;
create unique index contact_exclusions_unique_idx
  on contact_exclusions (company_id, coalesce(person_key, ''), coalesce(address_key, ''));

-- 2. Database write errors of each run.
alter table contact_runs add column write_errors int not null default 0;

-- 3. Names are cleaned exactly as kaltstart.contacts.exclusions.normalise_name
--    does: Unicode NFC, every kind of space collapsed to one, trimmed, lower
--    case. The list of spaces is the one Python splits on.
create function contact_normalise_name(p_name text)
returns text language sql stable set search_path = public as $$
  select lower(btrim(regexp_replace(normalize(p_name, NFC),
    '[ \t\n\u000b\f\r\u001c-\u001f\u0085   -     　]+',
    ' ', 'g')));
$$;

-- The key of a value: SHA-256 of the company id, a line break and the value
-- (kaltstart.contacts.exclusions.contact_key).
create function contact_key(p_company_id text, p_value text)
returns text language sql stable set search_path = public as $$
  select encode(sha256(convert_to(p_company_id || E'\n' || p_value, 'UTF8')), 'hex');
$$;

create or replace function contact_person_key(p_company_id text, p_person_name text)
returns text language sql stable set search_path = public as $$
  select contact_key(p_company_id, contact_normalise_name(p_person_name));
$$;

-- Removal of a person, run by the owner in the SQL editor:
--   select exclude_person('<company id>', 'First Last');
-- Copy the name from contact_people. Returns what was removed.
drop function exclude_person(text, text);
create function exclude_person(p_company_id text, p_person_name text)
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

  if v_people = 0 then
    return format('Exclusion saved, but no stored person has this name. Check the '
                  'spelling with: select name from contact_people where company_id = %L; '
                  '%s address(es) removed.', p_company_id, v_addresses);
  end if;
  return format('Removed %s person(s) and %s address(es). They will not be added again.',
                v_people, v_addresses);
end;
$$;

-- For the owner only, in the SQL editor.
revoke all on function contact_normalise_name(text) from public, anon, authenticated;
revoke all on function contact_key(text, text) from public, anon, authenticated;
revoke all on function exclude_person(p_company_id text, p_person_name text) from public, anon, authenticated;
