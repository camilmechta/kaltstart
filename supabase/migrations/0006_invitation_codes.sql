-- Single-use invitation codes (decision D86). Applied by hand in the Supabase
-- SQL editor, after 0005.
--
-- Each code works for one account. The owner creates codes in the SQL editor
-- and sees them once:
--   select * from create_invitation_codes(20);
-- Only a SHA-256 fingerprint of each code is stored. The shared code of
-- app_settings is no longer accepted.
--
-- Which codes were used, and when (no code is shown, only fingerprints):
--   select created_at, used_at, used_by is not null as used from invitation_codes order by created_at;
-- Cancel a code that was not used yet:
--   select cancel_invitation_code('KS-...');

create table if not exists invitation_codes (
  code_hash text primary key,
  created_at timestamptz not null default now(),
  used_at timestamptz,
  used_by uuid references auth.users(id) on delete set null
);
alter table invitation_codes enable row level security;

-- New codes, shown once: "KS-" and 12 random hexadecimal characters.
create or replace function create_invitation_codes(p_count int)
returns table (code text) language plpgsql security definer set search_path = public as $$
declare
  v_code text;
begin
  if not (p_count between 1 and 100) then
    raise exception 'Create between 1 and 100 codes at a time.';
  end if;
  for i in 1..p_count loop
    v_code := 'KS-' || upper(encode(extensions.gen_random_bytes(6), 'hex'));
    insert into invitation_codes (code_hash)
      values (encode(extensions.digest(v_code, 'sha256'), 'hex'));
    code := v_code;
    return next;
  end loop;
end;
$$;

-- Whether a code can still be used; asked by the app before signing up.
create or replace function invitation_code_ok(p_code text)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from invitation_codes
    where code_hash = encode(extensions.digest(upper(trim(coalesce(p_code, ''))), 'sha256'), 'hex')
      and used_at is null);
$$;

-- Cancel a code that was not used yet; true when one was cancelled.
create or replace function cancel_invitation_code(p_code text)
returns boolean language plpgsql security definer set search_path = public as $$
begin
  delete from invitation_codes
    where code_hash = encode(extensions.digest(upper(trim(coalesce(p_code, ''))), 'sha256'), 'hex')
      and used_at is null;
  return found;
end;
$$;

-- Nobody signs up without an unused code, even calling Supabase directly. The
-- code is used in the same transaction as the new account: two people typing
-- the same code at once cannot both get an account. After the insert, so that
-- used_by can refer to the new account.
create or replace function check_invitation_code()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  update invitation_codes set used_at = now(), used_by = new.id
    where code_hash = encode(extensions.digest(upper(trim(coalesce(
            new.raw_user_meta_data->>'invitation_code', ''))), 'sha256'), 'hex')
      and used_at is null;
  if not found then
    raise exception 'Sign-up refused.';
  end if;
  return new;
end;
$$;
drop trigger if exists check_invitation_code on auth.users;
create trigger check_invitation_code after insert on auth.users
  for each row execute function check_invitation_code();

revoke all on function create_invitation_codes(int) from public, anon, authenticated;
revoke all on function invitation_code_ok(text) from public, anon, authenticated;
revoke all on function cancel_invitation_code(text) from public, anon, authenticated;
revoke all on function check_invitation_code() from public, anon, authenticated;
