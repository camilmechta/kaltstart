# Sending limits and mail variation: design

Date: 2026-11-16. Status: draft for the owner's approval.
Parent: `2026-11-16-phase-4-web-app-design.md` (section 7, reservation rules)
and `2026-11-16-phase-3-mail-generator-design.md` (sections 7 to 9).

## 1. Why

If Kaltstart opens to many students, two things can go wrong.

1. **Volume.** The limit of 5 mails in progress only counts mails not yet
   marked as sent. A student who keeps a mail, clicks "I sent it" and starts
   again can already keep 30 mails a day. The rule of 3 mails per company in
   30 days still lets a company receive 36 mails over the 12 months it stays
   in the list, and 72 % of the companies are small ones, where the founders
   read every mail themselves.
2. **Sameness.** Students use the same templates. A company that receives
   five mails with the same subject and the same structure sees a mass
   mailing, even when each showcase sentence differs.

Figures behind the limits (owner's SQL queries, 2026-11-16): 773 eligible
companies (559 small, 114 medium, 100 large); about 68 new ones a month (21
Switzerland, 41 Germany, 5 Austria); an address for 68 % of the Swiss ones,
the only country read so far. Germany and Austria are read from the night
of 2026-11-17; the estimates are redone with their figures.

## 2. Goals, non-goals, anti-goals

- Goals: no student can send in volume; no company gets more than a modest
  number of mails per funding round; two mails to the same company never
  look like copies of each other; the student is told plainly what a limit
  means for them.
- Non-goals: limiting how many previews a student generates (free, nothing
  is sent); detecting a student who sends mails outside Kaltstart.
- Anti-goals: limits so tight that a motivated student runs out of companies
  in the first months; a variation that makes a mail read worse or breaks
  the 200-word limit; anything that looks random to the student between two
  previews of the same mail.

## 3. The limits

| Rule | Value | Counted on |
|---|---|---|
| Per company, rolling | 3 kept mails in 30 days | unchanged |
| **Per company and funding round** | **Small 6, Medium 9, Large 15** | kept mails for that company's current round |
| Per student, in progress | 5 | unchanged |
| **Per student, speed** | **10 kept mails in 7 rolling days** | every mail the student kept, abandoned ones included |
| Per student and company / person | once | unchanged |

- **The round cap** uses the size category of the round the mail was kept
  for (`mails.round_id`, already stored). When the company raises a new
  round, the count starts again from zero: new money, new hiring.
  Supported load with the figures above: about 350 mails a month, so about
  17 students writing 20 mails a month or 35 writing 10.
- **The speed limit** counts abandoned mails too, so that keeping and
  abandoning in a loop does not get around it.
- **A copied mail always counts.** Today an abandoned mail frees its
  company slot. From now on it does so only if it was never copied: once
  the text has been copied, it may have been sent. This applies to the
  30-day rule and the round cap.
- **What the student sees**:
  - on a refusal, a sentence naming the limit and when it frees, as today
    ("You kept 10 mails this week. You can keep a new one on 21 November.");
  - on the company page and in the list, the remaining places of the round
    when 3 or fewer are left ("2 places left for this round"), replacing
    "Last slot";
  - a company whose round cap is reached disappears from the list, like a
    company that is full for 30 days.
- The 5-in-progress rule stays, so a student still marks what they sent.

## 4. Invisible variation

The aim: the mails one company receives from several students differ in
subject and structure, without the student choosing anything.

**Axes of variation** (each with wordings in English and German, written by
hand, for every style):

| Axis | Wordings | Example (Direct, English) |
|---|---|---|
| Subject | 3 | "Nova Farm internship?" / "Internship at Nova Farm?" / "A growth intern for Nova Farm?" |
| Opening | 3 | existing three |
| Lead-in to the showcase sentence | 3 | "A bit about me:" / "What I have done so far:" / "One thing I am proud of:" |
| Close | 3 | "Would that work?" / "Could that be useful to you?" / "Shall we talk?" |
| Order | 2 | availability before the showcase sentence, or after it |

The style (Direct, Round, Formal) already changes the whole shape of a
mail; the variation works inside each style.

**How a wording is chosen.** Today the opening depends on a stable hash of
student and company, so two students can get the same one. Instead:

- the server counts the mails already kept for this company and round
  (`k`, 0 for the first one) and passes `k` to the generator;
- the generator turns `k` into one wording per axis so that **any two of
  the first three mails differ on every axis**, and no two of the first 15
  (the largest round cap) share the same combination of subject, opening,
  lead-in and close;
- the preview uses the `k` of the moment, so the student sees exactly the
  mail they will keep; generating again shows the same wording as long as
  nobody else kept a mail for that company in between.

`k` is stored with the mail (`mails.variant`, a small integer), so the
choice can be explained later and used in Phase 5 to compare reply rates
between wordings.

**What does not vary**: the student's showcase sentence and company line,
the facts (round, amount, dates), the greeting rule of each style, the
signature. Every combination must hold within the existing limits (200
words, subject 60 characters); the test of every combination at its
longest is extended to the new axes.

## 5. Approaches considered

1. **Count-based rotation (chosen).** Deterministic, testable, guarantees
   that the first mails to a company differ, and needs one integer stored.
2. Random wording at each preview: simple, but two students can still get
   the same mail, and the preview would change at every click.
3. Hash of student and company (today): stable for a student, but gives no
   guarantee between students, which is the point of this change.

For the limits, a single lifetime cap of 6 per company was considered
(about 14 students at 20 mails a month); the cap by size is chosen because
recruiters of large companies are used to volume and founders are not.

## 6. Where it changes

- `kaltstart.api.rules`: the round cap, the speed limit, the copied rule,
  the remaining places; `Refusal` gains the reasons `round_full` and
  `student_speed`.
- `supabase/migrations/0004_students.sql`: `reserve_mail` applies the same
  rules and stores `variant`; the `mails` table gains `variant` and a
  `copied_at` column. Migration 0004 has not been applied yet, so it is
  changed in place rather than followed by a 0005 (builder's call).
- `kaltstart.mailgen`: new wordings per axis and style, `variant` becomes
  the count `k` with the rotation above; the golden mails are regenerated
  and read again by the owner.
- Pages: refusal sentences, "N places left", the list hides companies whose
  round is full.
- DECISIONS.md and CHANGELOG.md.

## 7. Left to the builder

The exact rotation formula; the wordings themselves, within the tone of
each style (the owner reads the golden mails); the wording of the refusal
sentences.
