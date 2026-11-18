-- Read-only check, to run in the Supabase SQL editor after pasting a
-- migration (decision D88): every column must be true. A false names the
-- migration to paste again. It changes nothing.
select
  to_regclass('public.profiles') is not null                                   as m0004_profiles,
  to_regclass('public.mails') is not null                                      as m0004_mails,
  to_regprocedure('public.reserve_mail(uuid,text,text,jsonb)') is not null     as m0004_reserve,
  exists (select 1 from information_schema.columns where table_schema = 'public'
          and table_name = 'profiles' and column_name = 'degree_level')        as m0004_degree,
  exists (select 1 from information_schema.columns where table_schema = 'public'
          and table_name = 'profiles' and column_name = 'attach_cv')           as m0004_cv,
  exists (select 1 from information_schema.columns where table_schema = 'public'
          and table_name = 'mails' and column_name = 'variant')                as m0004_variant,
  exists (select 1 from information_schema.columns where table_schema = 'public'
          and table_name = 'profiles' and column_name = 'university')          as m0005_university,
  to_regclass('public.invitation_codes') is not null                           as m0006_codes,
  to_regprocedure('public.save_profile_and_showcases(uuid,jsonb,jsonb)') is not null as m0007_save,
  exists (select 1 from information_schema.columns where table_schema = 'public'
          and table_name = 'mails' and column_name = 'redacted_at')            as m0007_redacted,
  coalesce(pg_get_functiondef(to_regprocedure('public.reserve_mail(uuid,text,text,jsonb)'))
           not like '%copied_at is not null%', false)                          as m0008_slots;
