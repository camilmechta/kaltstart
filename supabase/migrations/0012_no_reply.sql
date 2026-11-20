-- Migration 0012: a sent mail can be marked "No reply" (design 2026-11-20,
-- Did they reply?). The check on mails.status gains 'no_reply' and the
-- column no_reply_at holds its date. No data changes.
-- The owner pastes this in the Supabase SQL editor before the push that
-- ships the reminder, then runs supabase/check_migrations.sql.

alter table mails drop constraint if exists mails_status_check;
alter table mails add constraint mails_status_check check (status in
  ('generated', 'copied', 'sent', 'no_reply', 'human_reply', 'positive_reply', 'abandoned'));
alter table mails add column if not exists no_reply_at timestamptz;
