# Did they reply? (design, 2026-11-20)

## Why

Phase 5 measures replies on the mails marked sent (PRD: 10 % human
replies, 3 % positive). Students forget to come back and tick a reply, and
a mail without a reply has no way to say so: the rate would be wrong or
empty. The owner wants a reliable figure from 5 to 10 beta testers.

## Goals

- 14 days after a mail is marked sent, the app asks the student whether
  they got a reply.
- The student can answer "No reply yet", which is stored, so the figure
  can read "X replies out of Y mails with a known outcome".
- A reply that comes after "No reply yet" can still be recorded.

## Non-goals and anti-goals

- The app sends nothing: no e-mail, no notification (rule of the project,
  and Supabase sends 2 e-mails an hour).
- No reminder for mails only presumed sent (kept and never marked): the
  measurement counts mails marked sent.
- Never nag: one answer and the reminder for that mail is gone.

## Approaches

- **A, chosen by the owner:** a new status `no_reply` with its date
  `no_reply_at` (migration `0012`, pasted by the owner before the push).
  The reminder disappears once answered; a known zero is data.
- B: no new status, the reminder shows from day 14 to day 30 and then
  hides itself. No migration, but "no reply" cannot be told from "never
  looked". Rejected for that reason.

## Design

- Status `no_reply`, label "No reply", between `sent` and `human_reply`:
  `sent` can go to `no_reply`, `human_reply` or `positive_reply`;
  `no_reply` can go to `human_reply` or `positive_reply`. Nothing goes
  back to `no_reply`.
- Migration `0012`: the status check of `mails` gains `no_reply`, and a
  column `no_reply_at timestamptz`. `check_migrations.sql` checks both.
- A mail needs the reply reminder when its status is `sent` and it was
  marked sent at least 14 days ago (`rules.REPLY_REMINDER_DAYS = 14`).
- My mails: one notice per such mail, "Your mail to {company} was sent
  {N} days ago: did they reply?", with three buttons: "Got a reply",
  "Positive reply", "No reply yet".
- Company list: when at least one mail needs it, one line under the
  progress strip linking to My mails: "{N} mail(s) sent 2 weeks ago or
  more: did they reply?".
- On the mail row and the mail page, a `sent` mail also offers
  "No reply yet"; a `no_reply` mail offers "Got a reply" and
  "Positive reply".
- Progress strip: a `no_reply` mail counts as sent.
- `/privacy` already says the app keeps "the mails you keep with their
  status and dates": no change.

## Left to the builder

Exact CSS of the notices (reuse the "did you send it?" notice), the order
of the reminders (oldest first), and the dev data (one mail sent 15 days
ago, so the reminder shows in `--dev`).
