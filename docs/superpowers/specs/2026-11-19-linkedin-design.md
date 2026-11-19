# LinkedIn messages: design

Date: 2026-11-19. Status: draft for the owner's approval. Size: a project.

## Why

Only 57 of about 1,200 addresses are a person's own (honest addresses
design). Most people the app suggests have no published address but are on
LinkedIn. The owner wants a second channel: the app writes a LinkedIn
connection note and a follow-up message; the student finds the person,
sends both and tracks the result as for a mail.

## Goals, non-goals, anti-goals

Goals:
- A channel choice on the company page: E-mail or LinkedIn.
- For LinkedIn, two texts: a connection note of at most 200 characters,
  and a message for after the connection is accepted.
- The same limits and the same statistics as mails (owner: "yes to both").

Non-goals: reading, searching or scraping LinkedIn in any way (the crawler
rule stays); sending anything; InMail; a LinkedIn sign-in.

Anti-goals:
- A note over 200 characters, ever. LinkedIn cuts or refuses it, and the
  owner warned that length is easy to underestimate. The limit is enforced
  by code and by an exhaustive test, never estimated.
- LinkedIn as a way around the "fair to founders" caps.

## Facts about LinkedIn (checked 2026-11-19, to re-check in LinkedIn)

- A connection note holds 200 characters on a free account (300 before;
  Premium keeps 300). We use 200.
- A free account may add a note to only 3 to 5 requests a month (sources
  disagree; LinkedIn publishes no figure). After that, requests go out
  without a note.
- Once connected, a message has no practical length limit.

## Decisions

**Who.** LinkedIn needs a named person: the suggested person, someone else
from the list, or a name the student types. At a large company only a typed
name (D100). "No name, write to the team" is e-mail only. The address field
("Their address, if you know it") does not apply to LinkedIn.

**The note.** Built from fixed templates, never by a model. Candidates from
the richest to the shortest; the first that fits in 200 characters is used,
counted with Python `len` on the final text. English, direct or round:

1. "Hi {first}, congrats on {company}'s {round}! I'm a {level} student at
   {university} looking for a {role} internship and would love to connect.
   {student_first}"
2. without the round ("congrats on the funding round at {company}!")
3. without the university and the level ("I'm a student looking for…")
4. "Hi {first}, congrats on {company}'s round! I'd love to connect about an
   internship. {student_first}"
5. "Hi {first}, congrats on your round! I'd love to connect about an
   internship. {student_first}"

"internship" becomes "part-time role" for part-time requests. Formal uses
"Dear {full name}," and "I would be glad to connect"; German has the same
ladder (du for direct and round, Sie for formal). The last candidate is at
most about 160 characters with the longest names allowed (40 + 40), so a
note always exists.

**The message.** Shorter than the mail, for a chat window: greeting by first
name, one line thanking them for connecting, the opening on the round, the
student's showcase sentence, the role paragraph or the student's company
line, the closing question, the name. No subject, no programme line, no CV
sentence (a CV cannot be attached to a first message), no PS. At most 190
words: measured worst case 187 with every student text at its longest;
about 100 words usually. (150 in the first draft of this design.)

**On the page.** A "Channel" choice (E-mail / LinkedIn) at the top of step
2. With LinkedIn, the preview shows the note with a live count ("143 / 200
characters") and the message. Kept, the page shows both with a Copy button
each, and a link "Find {name} on LinkedIn" that opens LinkedIn's people
search for "{name} {company}" in a new tab. Nothing is fetched by the app.

**Steps for the student,** shown on the kept page: 1. open the search and
find the person; 2. "Connect", "Add a note", paste the note (if the
monthly notes are used up, connect without it); 3. once accepted, paste
the message; 4. mark it.

**Statuses.** As for a mail. "I sent it" means the connection request was
sent; "Got a reply" means they wrote back (an accepted request alone is not
a reply); "Positive reply" as for mails. A LinkedIn item counts in every
limit (company, round, week, waiting, once per person) and in the Phase 5
rates, which can be split by channel.

**Storage.** A kept LinkedIn item is a row of `mails` with
`address_type = 'linkedin'`, `address` null, `subject` = the note and
`body` = the message. Migration `0011` adds `linkedin` to the check on
`address_type`; `reserve_mail` is unchanged. My mails says "To Anna
Muster, on LinkedIn".

**Privacy page.** One sentence: for a LinkedIn message, Kaltstart keeps the
texts and the person's name, as for a mail; it never visits LinkedIn.

## Approaches considered

- **Chosen:** a channel on the same page and the same `mails` row, so limits,
  statuses and statistics work unchanged.
- A separate table for LinkedIn items: cleaner names, but every limit and
  the SQL reservation would have to count two tables.
- A note only (no message): simpler, but the note is too short to apply,
  and notes are scarce on free accounts.

## Tests

- Note: for every style, language, role and request, with the longest
  company, person, university and programme names allowed and every round
  stage, `len(note) <= 200`; the shortest candidate exists for every input;
  the richest candidate is used when it fits.
- Message: within 190 words in the same matrix; no subject, no CV line.
- Page: the channel choice; LinkedIn refused for "team"; at a large company
  only a typed name; the kept page shows both texts, the count and the
  search link (URL-encoded name and company); My mails wording.
- Limits: a LinkedIn item takes a company slot and a weekly slot, and the
  once-per-person rule spans both channels.
- Migration `0011` and the check column `m0011_linkedin`.
