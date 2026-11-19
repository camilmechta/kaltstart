# Technical Roles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the target roles Software & AI (`software_ai`) and R&D & Hardware (`rd_hardware`) to the profile, the mails, the scraper and the person suggestion.

**Architecture:** The mail generator owns the list of roles (`mailgen/models.ROLES`); the app, the scraper mappings and the database check follow it. The scraper gains two categories, `engineering` and `rnd`, read from job titles like the five existing functions. A SQL migration widens the check on `profiles.target_role`.

**Tech Stack:** Python 3.12, FastAPI + Jinja2, pytest, PostgreSQL (Supabase), local PostgreSQL for `tests/sql`.

**Spec:** `docs/superpowers/specs/2026-11-19-technical-roles-design.md`

## Global Constraints

- Role keys exactly `software_ai` and `rd_hardware`, appended after the five existing roles (order matters: `tests/mailgen/test_matrix.py` uses `ROLES.index`).
- Labels: EN "Software & AI", "R&D & Hardware"; DE "Software & KI", "Forschung & Entwicklung".
- Words inside a sentence: EN "software and AI", "R&D and hardware"; DE same as the German labels.
- Card hints: "Building products, machine learning, infrastructure"; "Prototypes, electronics, mechanics, lab work".
- Mails stay within 210 words and subjects within 60 characters (existing matrix and subject tests run over every role).
- Individual engineers, developers and scientists are never kept.
- Every file in English; tests use invented people on `example.ch/.de/.com` only.
- Test first: each test is seen failing before the code.
- Commits `type: description`, author `Camil Mechta <351572234+camilmechta@users.noreply.github.com>`, no Co-Authored-By line, no mention of Claude.
- Nothing is pushed until the owner has pasted migration `0009` and run `supabase/check_migrations.sql` (all true), and has approved the push.
- Run the full suite as `.venv/bin/pytest -q > local/last-test.log 2>&1; tail -1 local/last-test.log` before every commit; commit only with no `failed`.

## Review Focus

1. "Head of Business Development" and "Leiter Geschäftsentwicklung": must stay `sales` only, never `rnd` (Task 2 test).
2. A business title with a technical qualifier, "Head of Software Sales", "Head of AI Partnerships": must stay `sales` only (Task 2 test).
3. "Market Research Manager" and "Head of Market Research": must not be `rnd` (Task 2 test).
4. A student with a technical role at a small company whose site lists a founder and a CTO but no technical head: the CTO is suggested, with a sentence that says why (Tasks 3 and 5 tests).
5. A profile saved online with a new role before `0009` is applied fails; the check query must show `m0009_roles` false until it is applied (Task 4 test, and the push gate above).

---

### Task 1: Mail generator roles

**Files:**
- Modify: `src/kaltstart/mailgen/models.py` (`ROLES`)
- Modify: `src/kaltstart/mailgen/phrases.py` (`_ROLE_NAMES`, `_ROLE_PARAGRAPHS`, new `role_words`)
- Modify: `src/kaltstart/mailgen/generator.py` (`_role_words`)
- Test: `tests/mailgen/test_phrases.py`, `tests/mailgen/test_generator.py`

**Interfaces:**
- Produces: `ROLES = ("product", "growth", "data", "operations", "business_development", "software_ai", "rd_hardware")`; `role_name(role, language) -> str`; `role_words(role: str, language: str) -> str` in `phrases.py`.

- [ ] **Step 1: Write the failing tests**

In `test_phrases.py`, update `test_role_names`:
```python
assert [role_name(r, "en") for r in ROLES] == [
    "Product", "Growth", "Data", "Operations", "Business development",
    "Software & AI", "R&D & Hardware"]
assert role_name("software_ai", "de") == "Software & KI"
assert role_name("rd_hardware", "de") == "Forschung & Entwicklung"
```
Add:
```python
@pytest.mark.parametrize("role,language,expected", [
    ("growth", "en", "growth"), ("product", "de", "Produkt"),
    ("software_ai", "en", "software and AI"), ("rd_hardware", "en", "R&D and hardware"),
    ("software_ai", "de", "Software & KI"), ("rd_hardware", "de", "Forschung & Entwicklung")])
def test_role_words(role, language, expected):
    assert role_words(role, language) == expected

def test_technical_paragraphs():
    assert role_paragraph("software_ai", "en", False) == (
        "After a round, the team must ship faster. I would like to help build "
        "and ship the next features.")
    assert role_paragraph("rd_hardware", "en", False) == (
        "New funding turns prototypes into products. I would like to help design, "
        "build and test the next iterations.")
```
In `test_generator.py`, add a test that generates a Round-style English mail and a German mail for `software_ai` with the existing helpers (`tests/mailgen/helpers.py`) and asserts the body contains "software and AI" (EN) and "im Bereich Software & KI" (DE), and never "software & ai".

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/pytest -q tests/mailgen/test_phrases.py tests/mailgen/test_generator.py`
Expected: FAIL (`role_words` not defined, list of roles shorter).

- [ ] **Step 3: Implement**

Append the two keys to `ROLES`. Add names to `_ROLE_NAMES["en"]` and `["de"]`. Add the four paragraphs to `_ROLE_PARAGRAPHS`, EN as in the test, DE exactly:
- `software_ai`: "Nach einer Runde muss das Team schneller liefern. Ich würde gerne helfen, die nächsten Features zu bauen und auszuliefern."
- `rd_hardware`: "Neues Kapital macht aus Prototypen Produkte. Ich würde gerne helfen, die nächsten Iterationen zu entwerfen, zu bauen und zu testen."

Add `role_words(role, language)`: a small dict of the four sentence words above; for any other role, `role_name(...).lower()` in English and `role_name(...)` in German (today's behaviour). Make `generator._role_words` return `role_words(role, language)`.

- [ ] **Step 4: Run the mailgen tests**

Run: `.venv/bin/pytest -q tests/mailgen`
Expected: all pass, including `test_matrix.py` and `test_subject_never_exceeds_60_characters` over the seven roles, and `test_golden.py` unchanged. If a matrix case exceeds 210 words, shorten the new paragraph (meaning kept) and say so in the commit message.

- [ ] **Step 5: Commit**

`git commit -m "feat: Software & AI and R&D & Hardware roles in the mail generator"`

---

### Task 2: Scraper reads technical heads

**Files:**
- Modify: `src/kaltstart/contacts/titles.py` (`CATEGORIES`, `ROLE_TO_CATEGORY`, `_CHIEFS`, `_FUNCTIONS`, `_COMPOUND_HEADS`, head matching)
- Modify: module docstring of `titles.py` (five functions → seven)
- Test: `tests/contacts/test_titles.py`

**Interfaces:**
- Produces: `CATEGORIES = ("leadership", "product", "growth", "data", "operations", "sales", "engineering", "rnd", "recruiting")`; `ROLE_TO_CATEGORY` gains `"software": "engineering", "rnd": "rnd"` (selection keys used by Task 3 and Task 5).

- [ ] **Step 1: Write the failing tests**

Extend the `classify_title` parametrize list:
```python
("Head of Engineering", ("engineering",), "head"),
("VP Engineering", ("engineering",), "head"),
("Director of Software", ("engineering",), "head"),
("Head of AI", ("engineering",), "head"),
("Head of AI/ML", ("engineering",), "head"),
("Machine Learning Lead", ("engineering",), "head"),
("Chief AI Officer", ("engineering",), "head"),
("Engineering Manager", ("engineering",), "manager"),
("Leiter Softwareentwicklung", ("engineering",), "head"),
("Head of R&D", ("rnd",), "head"),
("Head of Research", ("rnd",), "head"),
("Head of Hardware", ("rnd",), "head"),
("Director Electronics", ("rnd",), "head"),
("Chief Scientific Officer", ("rnd",), "head"),
("Leiter Forschung & Entwicklung", ("rnd",), "head"),
("Entwicklungsleiterin", ("rnd",), "head"),
("R&D Manager", ("rnd",), "manager"),
("Hardware Manager", ("rnd",), "manager"),
("Head of Data Engineering", ("data", "engineering"), "head"),
("CTO", ("leadership",), "head"),
```
Add a test of titles that are never technical:
```python
@pytest.mark.parametrize("text,categories", [
    ("Head of Business Development", ("sales",)),
    ("Leiter Geschäftsentwicklung", None),
    ("Head of Software Sales", ("sales",)),
    ("Head of AI Partnerships", ("sales",)),
    ("Head of Market Research", None),
    ("Market Research Manager", None),
])
def test_business_titles_stay_business(text, categories):
    title = classify_title(text)
    assert (title.categories if title else None) == categories
```
Add a test that individual titles are still dropped: "Software Engineer", "Hardware Engineer", "Research Scientist", "ML Engineer", "Senior Software Developer" → `None`. Update the existing `CATEGORIES` / `ROLE_TO_CATEGORY` assertion in this file to the new values.

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/pytest -q tests/contacts/test_titles.py`
Expected: FAIL on the new technical titles.

- [ ] **Step 3: Implement**

- `_FUNCTIONS["engineering"] = r"engineering|software|softwareentwicklung|ai|machine learning|ml"`; `_FUNCTIONS["rnd"] = r"r&d|f&e|research|hardware|electronics|mechanical|forschung(?: & entwicklung| und entwicklung)?|entwicklung"`. No plain "development", "technology" or "platform" (spec section 5; "technology" and "platform" are dropped because they appear in business titles).
- `_CHIEFS["engineering"] = _words("chief ai officer")`; `_CHIEFS["rnd"] = _words("chief scientific officer")`. CSO short form is not read.
- `_COMPOUND_HEADS["rnd"] = r"entwicklungs"` (for "Entwicklungsleiterin"). "Entwicklung" is matched as a whole word only, so "Softwareentwicklung" reads as engineering and "Geschäftsentwicklung" as nothing technical.
- Technical categories must not fire when their word only qualifies a business function. For `engineering` and `rnd`, reject a head or manager match when the function word is followed by a business function word (`sales|business development|partnerships?|marketing|growth|vertrieb`), and reject `research` when preceded by "market". Implement this as a lookahead/lookbehind in the patterns built for these two categories only, so the five existing categories behave exactly as before.
- `TITLE_WORD` picks up the new words through `_ANY_FUNCTION`; check `tests/contacts/test_people.py` and `test_names.py` still pass (a short word like "ai" must not turn a name into a title; add a people test with an invented person "Ai Beispiel, Head of Product" if `test_people.py` shows a risk).

- [ ] **Step 4: Run the contacts tests**

Run: `.venv/bin/pytest -q tests/contacts`
Expected: all pass, the existing title cases unchanged.

- [ ] **Step 5: Commit**

`git commit -m "feat: the contact scraper keeps engineering and R&D heads"`

---

### Task 3: CTO first for technical roles

**Files:**
- Modify: `src/kaltstart/contacts/selection.py` (`choose_person`)
- Test: `tests/contacts/test_selection.py`

**Interfaces:**
- Consumes: `ROLE_TO_CATEGORY` keys `"software"` and `"rnd"` (Task 2).
- Produces: `TECHNICAL_ROLES = frozenset({"software", "rnd"})` in `selection.py`; `choose_person(people, target_role, size_category)` signature unchanged.

- [ ] **Step 1: Write the failing tests**

With the file's `person(...)` helper and invented names:
```python
HEAD_ENG = person("Tim Muster", "Head of Engineering", ("engineering",))
HEAD_RND = person("Eva Probe", "Head of R&D", ("rnd",))

def test_a_technical_role_finds_its_head():
    assert choose_person([FOUNDER, CTO, HEAD_ENG], "software", "small") == HEAD_ENG
    assert choose_person([FOUNDER, CTO, HEAD_RND], "rnd", "medium") == HEAD_RND

def test_a_technical_role_falls_back_to_the_cto_at_a_small_company():
    assert choose_person([FOUNDER, CTO], "software", "small") == CTO
    assert choose_person([FOUNDER, CTO], "rnd", "small") == CTO

def test_business_roles_still_prefer_the_founder():
    assert choose_person([CTO, FOUNDER], "growth", "small") == FOUNDER

def test_a_technical_role_at_a_larger_company_goes_to_recruiting():
    assert choose_person([CTO, HR], "software", "large") == HR
```

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/pytest -q tests/contacts/test_selection.py`
Expected: FAIL on the CTO fallback (founder returned).

- [ ] **Step 3: Implement**

In step 2 of `choose_person`, when `target_role in TECHNICAL_ROLES`, sort leaders with a CTO title first (match "cto" or "chief technology officer" as whole words), then founders, then the rest; otherwise keep today's order. Update the docstring.

- [ ] **Step 4: Run the contacts tests**

Run: `.venv/bin/pytest -q tests/contacts`
Expected: all pass.

- [ ] **Step 5: Commit**

`git commit -m "feat: technical roles fall back to the CTO at a small company"`

---

### Task 4: Migration 0009

**Files:**
- Create: `supabase/migrations/0009_technical_roles.sql`
- Modify: `supabase/check_migrations.sql` (new column `m0009_roles`)
- Test: `tests/api/test_migration_0009.py`, `tests/test_migration_check.py`, `tests/sql/test_profile_save.py`

**Interfaces:**
- Produces: the check `profiles_target_role_check` accepting the seven keys of `ROLES`.

- [ ] **Step 1: Write the failing tests**

- `tests/api/test_migration_0009.py`: reads the file and asserts it drops and re-adds `profiles_target_role_check` with exactly the seven keys, and contains no `delete`, `update` or `drop table`. Also assert the seven keys equal `mailgen.models.ROLES`.
- `tests/test_migration_check.py`: add `"m0009_roles"` to the list of names.
- `tests/sql/test_profile_save.py`: `@pytest.mark.parametrize("role", ["software_ai", "rd_hardware"])` saving `PROFILE | {"target_role": role}` succeeds and reads back; saving `"engineering"` raises `psycopg.errors.CheckViolation`.

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/pytest -q tests/api/test_migration_0009.py tests/test_migration_check.py tests/sql`
Expected: FAIL (file missing, column missing, check violation on the new roles). If the local PostgreSQL for `tests/sql` is not installed, run `pip install -e ".[dev,sql]"` first; the `sql` workflow runs them on GitHub too.

- [ ] **Step 3: Implement**

```sql
alter table profiles drop constraint if exists profiles_target_role_check;
alter table profiles add constraint profiles_target_role_check check (target_role in
  ('product', 'growth', 'data', 'operations', 'business_development',
   'software_ai', 'rd_hardware'));
```
With a header comment saying what it does and that the owner pastes it before the push. Check column: `coalesce(pg_get_constraintdef((select oid from pg_constraint where conname = 'profiles_target_role_check')) like '%rd_hardware%', false) as m0009_roles`.

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/pytest -q tests/api/test_migration_0009.py tests/test_migration_check.py tests/sql`
Expected: PASS, and `tests/sql/test_migration_check.py` (all columns true) passes.

- [ ] **Step 5: Commit**

`git commit -m "feat: migration 0009 accepts the two technical roles"`

---

### Task 5: Web app profile and suggestion

**Files:**
- Modify: `src/kaltstart/api/forms.py` (`ROLE_LABELS`, error message "choose one of the seven roles")
- Modify: `src/kaltstart/api/compose.py` (`ROLE_TO_SELECTION`, `_ROLE_LABELS`, `_ROLE_CATEGORY`, `why`)
- Modify: `src/kaltstart/api/templates/profile.html` (`role_hints`, `role_icon`)
- Modify: `src/kaltstart/api/seed.py` (`_PEOPLE`)
- Test: `tests/api/test_profile.py`, `tests/api/test_compose.py`, `tests/api/test_seed.py`

**Interfaces:**
- Consumes: `ROLES` (Task 1), selection keys `"software"` / `"rnd"` (Tasks 2, 3).

- [ ] **Step 1: Write the failing tests**

- `test_profile.py`: the profile page shows seven role cards in the order of `ROLES`, with the labels and hints of the Global Constraints; posting the profile form (CSRF token read from the page, as the other tests do) with `target_role=software_ai` saves it and the page shows it checked.
- `test_compose.py`: with a small company whose people are a founder and a CTO, a profile with `target_role="rd_hardware"` gets the CTO from `suggested(...)`, and `why(...)` returns "At a small company, the CTO reads applications for technical roles."; with a "Head of Engineering" person (`categories=("engineering",)`) and `target_role="software_ai"`, `why` returns "Their title, Head of Engineering, matches your target role: Software & AI."
- `test_seed.py`: the seed people include at least one `engineering` and one `rnd` head.

- [ ] **Step 2: Run them and see them fail**

Run: `.venv/bin/pytest -q tests/api/test_profile.py tests/api/test_compose.py tests/api/test_seed.py`
Expected: FAIL.

- [ ] **Step 3: Implement**

- `ROLE_LABELS` and `_ROLE_LABELS`: add `"software_ai": "Software & AI"`, `"rd_hardware": "R&D & Hardware"` (keep one source if simple: `compose._ROLE_LABELS` may import `forms.ROLE_LABELS`).
- `ROLE_TO_SELECTION`: `"software_ai": "software"`, `"rd_hardware": "rnd"`. `_ROLE_CATEGORY`: `"software_ai": "engineering"`, `"rd_hardware": "rnd"`.
- `why`: after the matching-title case and the recruiting case, when the role is technical and the person's title reads as CTO, return the CTO sentence above.
- `profile.html`: hints as in Global Constraints; icons (Lucide, ISC):
  - `software_ai`: `<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>`
  - `rd_hardware`: `<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2M15 20v2M2 15h2M2 9h2M20 15h2M20 9h2M9 2v2M9 20v2"/>`
  - give `business_development` its own `elif` branch so the `else` is no longer it.
- `seed.py`: add two invented people, e.g. ("Tim Muster", "Head of Engineering", ("engineering",), "head") and ("Eva Probe", "Head of R&D", ("rnd",), "head").

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest -q > local/last-test.log 2>&1; tail -1 local/last-test.log`
Expected: no `failed`.

- [ ] **Step 5: Check the page in the local app**

Restart `.venv/bin/python -m kaltstart.api --dev --port 8000` (code `dev`), sign up, open the profile: seven cards, icons visible at phone width; choose Software & AI, save, open a company and see the suggestion and its reason. Screenshot for the owner.

- [ ] **Step 6: Commit**

`git commit -m "feat: Software & AI and R&D & Hardware in the profile and the suggestion"`

---

### Task 6: Documents and release

**Files:**
- Modify: `CLAUDE.md` (people kept: seven functions: product, growth, data, operations, sales, engineering, R&D, and recruiters)
- Modify: `DECISIONS.md` (D93: two technical roles; why; rejected: one Engineering role, three roles; CTO first for technical roles; heads appear as sites are re-read every 30 days)
- Modify: `CHANGELOG.md` (one line under Added, citing D93)

- [ ] **Step 1: Write the three updates and run the full suite**

Run: `.venv/bin/pytest -q > local/last-test.log 2>&1; tail -1 local/last-test.log`
Expected: no `failed`.

- [ ] **Step 2: Commit**

`git commit -m "docs: technical roles in CLAUDE.md, D93 and the changelog"`

- [ ] **Step 3: Owner applies the migration**

Ask the owner to paste `supabase/migrations/0009_technical_roles.sql` in the Supabase SQL editor, then run `supabase/check_migrations.sql`: every column true, `m0009_roles` included.

- [ ] **Step 4: Push with the owner's approval**

Before asking: `git log origin/main..main` reviewed, `git diff origin/main | grep -nEi "gmail|eyJ|sb_secret"` empty. After the push, all checks green (`tests` with `pytest` and `pinned`, `sql`, `security`), then the owner saves a profile with a technical role on the live site.
