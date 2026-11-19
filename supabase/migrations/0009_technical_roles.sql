-- Migration 0009: two technical target roles, Software & AI and R&D &
-- Hardware (technical roles design, section 7). The check on
-- profiles.target_role is replaced so it accepts the seven roles of
-- mailgen.models.ROLES. No data changes.
-- The owner pastes this in the Supabase SQL editor before the push that
-- ships the new roles, then runs supabase/check_migrations.sql.

alter table profiles drop constraint if exists profiles_target_role_check;
alter table profiles add constraint profiles_target_role_check check (target_role in
  ('product', 'growth', 'data', 'operations', 'business_development',
   'software_ai', 'rd_hardware'));
