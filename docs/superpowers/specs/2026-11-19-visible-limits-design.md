# Visible sending limits: design

Date: 2026-11-19. Status: approved by the owner in conversation. Size: a
small change.

## Why

A student may keep 10 mails in 7 rolling days, abandoned ones included
(D75, D76), have 5 in progress at a time, and write to a company once. The
site shows only the second rule ("2 of 5 mails in progress"); the weekly
limit, the real ceiling, appears only when a student is blocked. Even the
owner could not tell how many mails a student may send.

## Decisions

- The header badge becomes "7 of 10 mails kept this week · 2 waiting",
  shown on every signed-in page, linking to My mails. "Kept", not "sent":
  the app never sends; a mail counts when the student presses "Keep this
  mail".
- `/about`, in "Fair to founders": "You can keep up to 10 mails a week,
  5 waiting at a time, and write to each company once."
- My mails keeps its explanation, with the weekly rule added.
- Every number comes from `rules.LIMITS`; none is written in a template.
- One function counts the week, `rules.week_count(student_id, mails, now)`,
  used by the header and by the refusal rule, so they cannot disagree.

Rejected: a "Your limits" box on My mails only (still hidden at the start);
showing the limits on the landing page (not signed in, no counts).

## Tests

- `week_count` counts kept mails of the last 7 days, abandoned included,
  and not older ones or other students'.
- The header shows "0 of 10 mails kept this week · 0 waiting" for a new
  student, and the counts after keeping mails.
- `/about` shows the student line; no template contains the literal "of 5"
  or "of 10".
- The weekly refusal still triggers at 10.
