-- Migration 0010: a kept mail may go to an address the student gave for the
-- person (honest addresses, 2026-11-19, point 4). The check on
-- mails.address_type gains 'student'. No data changes.
-- The owner pastes this in the Supabase SQL editor before the push that
-- ships the field, then runs supabase/check_migrations.sql.

alter table mails drop constraint if exists mails_address_type_check;
alter table mails add constraint mails_address_type_check check (address_type in
  ('personal', 'careers', 'generic', 'student'));
