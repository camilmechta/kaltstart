# Sending limits and mail variation: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cap kept mails per funding round and per student per week, count a copied mail even when abandoned, and make the mails one company receives differ in subject and structure.

**Architecture:** The rules stay pure functions in `kaltstart.api.rules`, mirrored by the SQL function `reserve_mail` (migration 0004, changed in place: never applied). The generator takes `variant` as the count `k` of mails already kept for the company's round and turns it into one wording per axis with a fixed rotation. The pages pass `k`, word the new refusals and show the places left.

**Tech Stack:** Python 3.12/3.13, FastAPI, Jinja2, Supabase (PostgreSQL), pytest.

**Spec:** `docs/superpowers/specs/2026-11-16-sending-limits-and-variation-design.md`

## Global Constraints

- Round cap: Small 6, Medium 9, Large 15 kept mails per company and round; a new round starts at zero.
- Speed: 10 kept mails per student in 7 rolling days, abandoned ones included.
- An abandoned mail frees a company slot (30-day rule and round cap) only if it was never copied.
- Unchanged: 3 per company in 30 days, 5 in progress, once per company, once per person.
- `k` = number of mails ever kept for this company and round, abandoned included (0 for the first).
- Any two of the first three mails to a company differ on every three-wording axis; no two of the first 15 share subject, opening, lead-in and close.
- Every mail ≤ 200 words, subject ≤ 60 characters; wording 0 of every axis is today's text, so `k = 0` reproduces the existing golden mails.
- Every file in English; no AI at runtime; test first, seen failing; commits `type: description`, no co-author line.

## Review Focus

1. Two students preview the same company, one keeps, the other keeps later: the second kept mail uses the new `k` (different wording from the first), even if it differs from what that student previewed. Test in Task 4.
2. A company raises a new round while old mails exist: the round cap counts only mails of the current `round_id`, the 30-day rule still counts all. Test in Task 1.
3. Keep, copy, abandon: the slot stays taken; keep, abandon without copying: it frees. Test in Task 1 (and the SQL mirror in Task 3).
4. The longest company name with every subject wording falls back to a shorter subject, never over 60 characters. Test in Task 2 (matrix).
5. A student at 10 kept mails in 7 days, one abandoned: still refused, and the refusal names the date it frees. Test in Task 1.

---

### Task 1: The new rules

**Files:**
- Modify: `src/kaltstart/api/rules.py`
- Modify: `src/kaltstart/api/store.py` (`MailRecord` fields filled by `Mail.record()`)
- Test: `tests/api/test_rules.py`

**Interfaces:**
- Produces:
  - `MailRecord` gains `round_id: str | None = None` and `copied: bool = False` (defaults keep existing constructors working). `Mail.record()` sets `copied = "copied" in status_dates or status in ("copied", "sent", "human_reply", "positive_reply")`.
  - `ROUND_CAP = {"small": 6, "medium": 9, "large": 15}`, `SPEED_LIMIT = 10`, `SPEED_DAYS = 7`.
  - `refusal(student_id, company_id, person_key, mails, now, *, round_id: str | None = None, size: str | None = None) -> Refusal | None` with new reasons `"round_full"` (frees_on None) and `"student_speed"` (frees_on = oldest of the 10 counted + 7 days). Order of checks: company_full, round_full, student_speed, student_pending, company_done, person_done.
  - `places_left(company_id, round_id, size, mails, now) -> int` = min(3 − counted in 30 days, cap − counted in round), never below 0.
  - `variant_for(company_id, round_id, mails) -> int` = count of every mail of that company and round (abandoned included).
  - `last_slot` is removed; callers use `places_left`.

- [ ] **Step 1: Write the failing tests** in `tests/api/test_rules.py`:
  `test_the_round_cap_depends_on_the_size` (6 small mails of one round over 6 months, 30-day rule never hit → 7th refused `round_full`; medium allows 9; large 15), `test_a_new_round_starts_the_count_again` (6 mails on `r1`, keep on `r2` allowed; 30-day rule still counts the `r1` mails of the last 30 days), `test_the_speed_limit_counts_abandoned_mails` (10 kept in 6 days, 1 abandoned → refused `student_speed`, `frees_on` = first + 7 days; at day 8 allowed), `test_a_copied_then_abandoned_mail_still_counts` (3 mails in 30 days, one `copied=True` then abandoned → `company_full`; same with `copied=False` → allowed), `test_places_left` (fresh small company → 3; after 2 in 30 days → 1; 5 in the round over 3 months → 1), `test_variant_counts_every_mail_of_the_round` (2 kept + 1 abandoned on `r1`, 1 on `r2` → `variant_for(c, "r1")` is 3).
- [ ] **Step 2: Run** `.venv/bin/pytest tests/api/test_rules.py -q` — Expected: the new tests FAIL (unknown keyword / attribute).
- [ ] **Step 3: Implement** in `rules.py` and `store.py` as in Interfaces; `_counting` excludes an abandoned mail only when `not m.copied`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: all pass except callers of `last_slot` (fixed in Task 4: until then keep a `last_slot` wrapper returning `places_left(...) == 1` and remove it in Task 4).
- [ ] **Step 5: Commit** `feat: round cap, weekly speed limit and copied mails keep their slot`

### Task 2: Variation in the generator

**Files:**
- Modify: `src/kaltstart/mailgen/choices.py`, `src/kaltstart/mailgen/generator.py`, the six templates in `src/kaltstart/mailgen/templates/`
- Test: `tests/mailgen/test_variation.py` (new), `tests/mailgen/test_matrix.py`, `tests/mailgen/test_review_fixes.py`, `tests/mailgen/test_golden.py` and `tests/mailgen/golden/`

**Interfaces:**
- Produces:
  - `axes(k: int) -> tuple[int, int, int, int, int]` in `choices.py`: (subject, opening, lead_in, close, order). With `q = k // 3`, `t = k // 9`: subject `= k % 3`, opening `= (k + q) % 3`, lead-in `= (k + 2*q + t) % 3`, close `= (k + 2*t) % 3`, order `= q % 2`.
  - `generate(..., variant: int | None = None)`: `variant` is `k ≥ 0`; `None` keeps today's hash choice for k; negative raises `ValueError`. Formal now varies too.
  - `subject(style, language, company, round, role, request, wording: int = 0) -> str`.
  - Templates take `intro_first: bool`: true is today's layout (opening and intro in one paragraph); false puts the opening alone, then the showcase, then the intro as its own paragraph.

Exact copy (wording 0 is today's; `{C}` company, `{role}`/`{Role}` role name, `{kind}`/`{Kind}` internship or part-time role, `{round}` round name). Each subject keeps a fallback chain ending as today's last candidate.

| Axis | Style | EN 1 | EN 2 | DE 1 | DE 2 |
|---|---|---|---|---|---|
| Subject | direct | `{Kind} at {C}?` | `{Role} {kind} at {C}?` | `{C}: {Kind}?` | `{Role}-{Kind} bei {C}?` |
| Subject | round | `{Role} at {C}, after your {round}` | `Joining {C} after your {round}?` | `{Role} bei {C} nach eurer {round}` | `Mitarbeit im Bereich {Role} bei {C}?` |
| Subject | formal | `{Role} {kind}: application to {C}` | `Spontaneous application: {role} {kind} at {C}` | `Initiativbewerbung: {Role}-{Kind} bei {C}` | `{Role}-{Kind} bei {C}: Bewerbung` |
| Lead-in | direct | `What I have done so far:` | `One thing I am proud of:` | `Was ich bisher gemacht habe:` | `Worauf ich stolz bin:` |
| Lead-in | round | `What I have done so far:` | `A recent example:` | `Was ich bisher gemacht habe:` | `Ein aktuelles Beispiel:` |
| Lead-in | formal | `My most relevant experience:` | `A recent example of my work:` | `Meine wichtigste Erfahrung:` | `Ein aktuelles Beispiel meiner Arbeit:` |
| Close | direct | `…, or with whatever helps most. Could that be useful to you?` | `…, or with whatever helps most. Shall we talk?` | `… Wäre das für euch interessant?` | `… Wollen wir kurz sprechen?` |
| Close | round | `Would you have 15 minutes this week or next?` | `Could we find 15 minutes for a short call?` | `Hast du/Habt ihr nächste Woche 15 Minuten?` | `Können wir 15 Minuten telefonieren?` |
| Close | formal | `I would be glad to discuss this in a short call. Thank you for your time.` | `I look forward to hearing from you. Thank you for your consideration.` | `Ich freue mich über die Gelegenheit zu einem kurzen Gespräch. Vielen Dank.` | `Ich freue mich auf Ihre Rückmeldung. Vielen Dank für Ihre Zeit.` |
| Opening | formal | `Congratulations on {deal}; it caught my attention.` | `I read with interest about {deal}.` | `Herzlichen Glückwunsch zu {deal}; das hat meine Aufmerksamkeit geweckt.` | `Mit Interesse habe ich von {deal} gelesen.` |

(`…` in Direct closes stands for today's first sentence, kept; German Round keeps today's du/ihr switch.)

- [ ] **Step 1: Write the failing tests** in `tests/mailgen/test_variation.py`: `test_axes_of_the_first_three_differ_everywhere` (for k in 0..2, the four three-wording axes all equal k), `test_the_first_fifteen_combinations_are_distinct` (len(set(axes(k)[:4] for k in range(15))) == 15), `test_three_mails_to_one_company_differ` (for each style and language, `generate` with variant 0, 1, 2: three different subjects and three different bodies, and no lead-in shared), `test_order_moves_the_intro_after_the_showcase` (variant 3: body index of the showcase text < index of "HSG"), `test_a_negative_variant_is_refused`. In `test_review_fixes.py` change the out-of-range case to `variant=-1` only. In `test_matrix.py` replace the variant list with `(0, 1, 2, 3, 4, 5)` for every style.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/mailgen -q` — Expected: new tests FAIL; golden tests still PASS (k = 0 unchanged).
- [ ] **Step 3: Implement** the copy table, `axes`, the subject wording, the formal openings and `intro_first` in the six templates.
- [ ] **Step 4: Run** `.venv/bin/pytest tests/mailgen -q` — Expected: PASS, matrix included (no mail over 200 words, no subject over 60 characters).
- [ ] **Step 5: Add golden mails for k = 1 and k = 2**: `CASES` gains a variant dimension `(0, 1, 2)` without company line for k > 0; file name `{style}_{language}_v{k}.txt`; regenerate with `python -m tests.mailgen.test_golden`; read the 12 new files. Run `.venv/bin/pytest -q` — Expected: PASS.
- [ ] **Step 6: Commit** `feat: mails to one company vary in subject, wording and order`

### Task 3: Database: `reserve_mail` and the `mails` table

**Files:**
- Modify: `supabase/migrations/0004_students.sql`, `src/kaltstart/api/supabase_store.py`, `src/kaltstart/api/store.py` (`NewMail`, `Mail`, in-memory `reserve`)
- Test: `tests/api/test_migration_0004.py`, `tests/api/test_supabase_store.py`, `tests/api/test_store.py`

**Interfaces:**
- Consumes: Task 1 rules and `MailRecord` fields.
- Produces: `mails.variant int not null default 0` and `mails.size_category text` columns; `NewMail` gains `variant: int = 0` and `size_category: str | None = None`; `Mail` gains `variant: int = 0`; `reserve_mail` applies, in this order and with the same reasons as Task 1: 30-day cap (abandoned counted when `copied_at` is not null), round cap from `p_row->>'size_category'` (6/9/15) on `round_id`, speed (10 in 7 days, any status, `frees_on` = oldest + 7 days), pending, company, person; inserts `variant` and `size_category`. `SupabaseAppStore.mail_records` reads `round_id, copied_at`.

- [ ] **Step 1: Write the failing tests**: in `test_migration_0004.py` assert the SQL text contains `'round_full'`, `'student_speed'`, `copied_at is not null`, `interval '7 days'` inside the speed check, `variant` in the insert column list, and the three caps `6`, `9`, `15` in one `case` on `size_category`; in `test_supabase_store.py` (fake client) assert `reserve` sends `variant` and `size_category` in `p_row` and `mail_records` maps `round_id` and `copied`; in `test_store.py` assert the in-memory store refuses the 7th small mail of one round (`round_full`) and stores `variant`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/api/test_migration_0004.py tests/api/test_supabase_store.py tests/api/test_store.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** the SQL, the dataclass fields and the two stores (`InMemoryAppStore.reserve` passes `round_id` and `size` to `rules.refusal`).
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: reserve_mail applies the round cap, the speed limit and stores the variant`

### Task 4: Pages

**Files:**
- Modify: `src/kaltstart/api/pages.py`, `src/kaltstart/api/store.py` (`eligible`), `src/kaltstart/api/templates/companies.html`, `company.html`
- Test: `tests/api/test_company_page.py`, `tests/api/test_companies.py`

**Interfaces:**
- Consumes: `rules.refusal(..., round_id=, size=)`, `rules.places_left`, `rules.variant_for`, `generate(variant=k)`, `NewMail(variant=, size_category=)`.
- Produces: refusal sentences — `round_full`: "This company has received all the mails Kaltstart allows for its current funding round. Others are waiting for you."; `student_speed`: "You kept 10 mails this week. You can keep a new one on {date}." The list and the company page show "{n} place(s) left" when `places_left` is 1 or 2 (ruling: at 3 it would show on every fresh company); a company whose round is full is hidden from the list unless the student wrote to it.

- [ ] **Step 1: Write the failing tests**: `test_a_company_whose_round_is_full_is_hidden` (store with 6 kept small mails on the company's round spread over 6 months → not in `/companies`), `test_the_round_full_refusal_is_said` (preview → 409 and the sentence), `test_the_speed_refusal_names_the_date`, `test_places_left_are_shown` ("1 place left" and "2 places left"), `test_the_second_kept_mail_to_a_company_uses_the_next_variant` (student A keeps, student B keeps the same company: different subjects; `store` mail of B has `variant == 1`).
- [ ] **Step 2: Run** `.venv/bin/pytest tests/api -q` — Expected: new tests FAIL.
- [ ] **Step 3: Implement**: `compose_mail` computes `k = rules.variant_for(company.id, company.round_id, records)` and passes `round_id`, `size` to `rules.refusal`; keep recomputes `k` at keep time (ruling of Review Focus 1); `NewMail` gets `variant=k, size_category=company.size_category`; `eligible` hides `round_full` like `company_full`; replace `last_slot` with `places_left`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: pages word the new limits and show the places left`

### Task 5: Records

**Files:** `DECISIONS.md` (D76), `CHANGELOG.md`, `README.md` (rules section if it lists the limits)

- [ ] **Step 1:** D76 states the limits, the copied rule, the rotation and the ruling on keep recomputing `k`, with the figures of the spec. CHANGELOG line under Added.
- [ ] **Step 2: Run** `.venv/bin/pytest -q` — Expected: PASS. Restart the dev app and check in the browser: a fresh company, a company with "1 place left", a refusal.
- [ ] **Step 3: Commit** `docs: record the sending limits and mail variation`
