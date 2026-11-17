-- The student's university, as they write it (decision D85): Kaltstart is a
-- beta open to students of any university, by invitation. Applied by hand in
-- the Supabase SQL editor, after 0004. Existing profiles get an empty value
-- and are asked for it before their next mail.
alter table profiles add column if not exists university text not null default '';
