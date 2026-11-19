-- Migration 0011: a kept item may be a LinkedIn message (design 2026-11-19).
-- It has no address; its subject holds the connection note and its body the
-- message. The check on mails.address_type gains 'linkedin'. No data changes.
-- The owner pastes this in the Supabase SQL editor before the push that
-- ships the channel, then runs supabase/check_migrations.sql.

alter table mails drop constraint if exists mails_address_type_check;
alter table mails add constraint mails_address_type_check check (address_type in
  ('personal', 'careers', 'generic', 'student', 'linkedin'));
