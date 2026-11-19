# Show the value: design

Date: 2026-11-19. Status: approved by the owner in conversation ("do all").
Size: a small project in four parts.

## Why

The owner finds that a student landing on the site does not grasp the
value, and that once signed in the product does not show it either. The
landing says what Kaltstart does, not why it works (startups that just
raised hire soon but rarely post the job), does not say the time saved, and
its example shows a personal address while 84 % of named mails go through a
shared one. Signed in, the list reads like a database: nothing says "this
one is for you, and now is the moment", and nothing shows progress.

## Decisions

**A. Landing.** Headline "Internships that are never posted." Lead: "Startups
that just raised money hire in the next months, but most never post the job.
Kaltstart finds them every night, tells you who to write to, and drafts your
application in two minutes. You send it yourself." Three benefits: hidden
roles (they raised, they will hire, few students know), the right person
(who reads applications there, read on the company's own site), two minutes
instead of two hours (rounds, contacts and a first draft are ready). The
figures keep the live company count and add "new rounds every night". The
example becomes honest: a general address greeted by name with the PS, and
the LinkedIn note beside it.

**B. "For you".** At the top of the list, on page 1 without a search, for a
student whose profile is complete: up to three companies. Candidates: the
newest 50 within the student's preferred countries and sectors, rounds of
the last 3 months, not written to yet. Score: a head or manager of the
student's field named on the site (not at a large company, D100) +2, a round
in the last 30 days +1. Kept: score 2 or more, so someone of the field is
always named; ordered by score, then newest round. The block says "Recent
rounds", not "fresh" (a kept round may be up to 3 months old). Each card: name, "raised €8M,
3 weeks ago", and "Anna Muster, Head of Growth: your field" or the round.

**C. Row hooks.** In the list, a round of the last 30 days shows "Raised N
days ago" / "Raised N weeks ago" instead of the month; a company naming
someone of the student's field shows "{title} named: your field" instead of
"N people named". Large companies show no names, as before.

**D. Progress.** Once a student has kept a mail, the "Get started" box gives
way to a strip: "Your applications: 4 kept · 2 sent · 1 reply", linking to
My mails. Sent counts sent, replied and presumed sent (D75); replies count
human and positive replies.

**Data.** One store method, `field_people(company_ids, category)`, returns the
first person of that category per company (a head before a manager), read
once per page.

## Tests

- Hooks: the age wording at 0, 1, 6, 7, 29 and 30 days; the field line for
  the student's category; none at a large company.
- For you: shown with a complete profile, hidden without; scores and order;
  never a company already written to; at most three.
- Progress: counts per status; replaces "Get started".
- Landing: the headline, the benefits, the live count, the honest example
  (no personal address shown, a PS), the LinkedIn note.
