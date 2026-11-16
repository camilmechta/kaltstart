# Mail Generator (Phase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pure function that writes a spontaneous application mail (subject and body) in three styles and two languages from a student, a company, its round and a contact.

**Architecture:** Frozen dataclasses for the inputs, small formatting helpers for every variable phrase, six Jinja2 templates (three styles × English and German) that only arrange those phrases, and one `generate` function that validates, picks a variant, renders and checks the limits. No I/O anywhere in the package.

**Tech Stack:** Python 3.12+, Jinja2, pytest.

**Spec:** `docs/superpowers/specs/2026-11-16-phase-3-mail-generator-design.md` (parent: `docs/superpowers/specs/2026-11-11-kaltstart-design.md`, section 7.3)

## Global Constraints

- No AI, no network, no database, no file written: the package reads only its own templates.
- Body at most 150 words (split on whitespace, greeting and signature included, a link is one word); subject at most 60 characters.
- English and German only. German text contains no "ß". German Direct and Round use "Du", Formal uses "Sie".
- No sentence with a gap: no `{`, `}`, `None`, double space, space before punctuation, or three line breaks in a row.
- Never "led by" / "angeführt von": the first investor is "backed by X" (one investor) or "with X and others" (several).
- A person is greeted by name only when `Contact.person_name` is set; the caller sets it only for a confirmed person.
- The student's own texts (company line, examples) are used as written: trimmed, a final full stop added if missing, at most 200 characters.
- Tests use invented people and companies only (`example.ch`, `example.de`, `example.com`).
- Test first: each test seen failing before the code. Commits `type: description`, author Camil Mechta, no co-author line.

## Review Focus

1. A student text ending in "!" or "?" must not get an extra full stop. Test in Task 2.
2. A company name with an ampersand or apostrophe (`Fuchs & Eule`, `O'Neil Labs`) appears unescaped in the body. Test in Task 4.
3. A German mail to a Swiss company whose city is unknown and region unknown falls back to English. Test in Task 1.
4. A 9.96 million round reads "10M" / "10 Mio.", never "10.0M". Test in Task 2.
5. Regenerating the same mail twice gives byte-identical output across processes (no use of Python's salted `hash`). Test in Task 3.

---

### Task 1: Inputs, language rule and Jinja2

**Files:**
- Modify: `pyproject.toml` (add `jinja2` to dependencies)
- Create: `src/kaltstart/mailgen/__init__.py`, `src/kaltstart/mailgen/models.py`, `src/kaltstart/mailgen/language.py`
- Test: `tests/mailgen/__init__.py`, `tests/mailgen/test_language.py`

**Interfaces:**
- Produces, in `models.py`, frozen dataclasses:
  - `Example(text_en: str | None, text_de: str | None)`
  - `Student(id: str, first_name: str, last_name: str, programme: str, languages: tuple[str, ...], role: str, request: str, start_date: date | None, duration_months: int | None, workload_percent: int | None, link: str | None, examples: tuple[Example, ...], chosen_example: int = 0)`
  - `Company(id: str, name: str, country: str, city: str | None, region: str | None)`
  - `Round(stage: str | None, amount_eur: int | None, amount_native: float | None, currency: str | None, investors: tuple[str, ...], size_category: str)`
  - `Contact(address: str | None, address_type: str, person_name: str | None)`
  - `Mail(subject: str, body: str, language: str, style: str, used_company_line: bool)`
  - `class MissingData(ValueError)` with attribute `fields: tuple[str, ...]`
  - Constants `ROLES = ("product", "growth", "data", "operations", "business_development")`, `REQUESTS = ("internship", "part_time")`, `STYLES = ("direct", "round", "formal")`, `LANGUAGES = ("en", "de")`.
- Produces, in `language.py`: `choose_language(student: Student, company: Company) -> str`.

- [ ] **Step 1: Write the failing tests** in `tests/mailgen/test_language.py`:
  - German speaker (`"de" in languages`) and company in `Germany` or `Austria` → `"de"`.
  - German speaker, `Switzerland`, region `"Zurich"` → `"de"`; region `"Bern"` → `"de"`; region `"Vaud"` → `"en"`.
  - German speaker, `Switzerland`, no region, city `"Basel"` → `"de"`; city `"Geneva"` → `"en"`; no region and no city → `"en"` (Review Focus 3).
  - Student without German, company in Germany → `"en"`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/mailgen -q`. Expected: FAIL, module not found.
- [ ] **Step 3: Implement** the models and `choose_language`. Canton list: Aargau, Appenzell Ausserrhoden, Appenzell Innerrhoden, Basel-Landschaft, Basel-Stadt, Bern, Glarus, Graubünden, Lucerne, Nidwalden, Obwalden, Schaffhausen, Schwyz, Solothurn, St. Gallen, Thurgau, Uri, Zug, Zurich (English spellings, as `city_aliases.csv` stores them). City list: the capitals of those cantons, plus Winterthur, Biel, Baden, Brig, Davos, Rapperswil, Wil, Olten, Thun, Kreuzlingen.
- [ ] **Step 4: Run** `pip install -e ".[dev]"` then `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: mail generator inputs and language rule`.

### Task 2: Phrases

**Files:**
- Create: `src/kaltstart/mailgen/phrases.py`
- Test: `tests/mailgen/test_phrases.py`

**Interfaces:**
- Consumes: Task 1 models.
- Produces:
  - `round_name(stage: str | None, language: str) -> str`: the spec 8.1 table; `None` and unknown stages read as `"funding round"` / `"Finanzierungsrunde"`.
  - `amount(round: Round, language: str) -> str | None`
  - `investor_phrase(round: Round, language: str) -> str | None`
  - `role_name(role: str, language: str) -> str` (short display names: `"Product"`, `"Growth"`, `"Data"`, `"Operations"`, `"Business development"`; German `"Produkt"`, `"Growth"`, `"Data"`, `"Operations"`, `"Business Development"`)
  - `role_paragraph(role: str, language: str, formal: bool) -> str` (one per role and language; the `formal` flag switches German "du" to "Sie"; at most 35 words)
  - `request_phrase(student: Student, language: str) -> str`
  - `long_date(d: date, language: str) -> str`
  - `student_text(text: str) -> str` (trim, add a final full stop unless it ends in `.`, `!` or `?`)

- [ ] **Step 1: Write the failing tests**, one per row of the spec tables:
  - `amount`: 8_000_000 EUR → `"€8M"` / `"8 Mio. €"`; native 2_500_000 CHF → `"CHF 2.5M"` / `"2,5 Mio. CHF"`; 40_000_000 USD → `"$40M"`; 3_000_000 GBP → `"£3M"`; 30_000_000 SEK → `"SEK 30M"`; 9_960_000 EUR → `"€10M"` and `"10 Mio. €"` (Review Focus 4); empty currency with native amount → euro amount; 0 or `None` → `None`.
  - `investor_phrase`: one investor → `"backed by Example Ventures"` / `"mit Example Ventures"`; three → `"with Example Ventures and others"` / `"mit Example Ventures und weiteren"`; a first name of 41 characters → `None`; none → `None`; the string `"led"` never appears.
  - `round_name`: `"Seed"` → `"Seed"`; `"Series A"` → `"Series A"`; `"Other"`, `"Crowdfunding"`, `None` → `"funding round"`; `"Debt"` → `"financing"` / `"Finanzierung"`; `"Grant"` → `"grant"` / `"Förderung"`.
  - `long_date(date(2027, 4, 1))` → `"1 April 2027"` / `"1. April 2027"`; March in German is `"März"`.
  - `request_phrase`: internship → `"an internship from 1 April 2027 for 3 months"`; part-time 40 → `"part-time work (40 %) from 1 April 2027"`; German equivalents end without "ß".
  - `student_text`: `"  I tried your app "` → `"I tried your app."`; `"Would love that!"` unchanged; `"Why not?"` unchanged (Review Focus 1).
  - `role_paragraph`: for every role and language, at most 35 words; German `formal=True` contains `"Sie"` and not `" du "` / `" dich "` / `" dein"`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/mailgen/test_phrases.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `phrases.py`. Amount: take the native amount and currency when both are set, else `amount_eur` in euros; value in millions rounded once (`round(x, 1)` under 10, `round(x)` from 10), printed without a trailing `.0`. Write the role paragraphs in the spirit of the spec, about what the student would do in that function at a company that just raised money.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: phrases for mails (round, amount, investor, role, request)`.

### Task 3: Variant choice and subject

**Files:**
- Create: `src/kaltstart/mailgen/choices.py`
- Test: `tests/mailgen/test_choices.py`

**Interfaces:**
- Produces:
  - `variant(student_id: str, company_id: str) -> int`: SHA-256 of `f"{student_id}\n{company_id}"`, first 8 hex digits as an integer, modulo 3.
  - `subject(style: str, language: str, company: str, round: str, role: str, request: str) -> str`: the spec section 9 table; `role` is the display name from `role_name`; internship / part-time wording per request; drops the round, then the role, until at most 60 characters; Direct falls back to `"Internship?"` / `"Praktikum?"` (or `"Part-time role?"` / `"Teilzeit?"`).
  - `suggested_style(contact: Contact, round: Round) -> str`: `"formal"` when `contact.person_name` is `None`, `contact.address_type` is `"careers"` or `"generic"`, and `round.size_category == "large"`; else `"direct"`.

- [ ] **Step 1: Write the failing tests**:
  - `variant("s1", "c1")` equals a pinned value computed once with `hashlib`, and is the same in a subprocess (`subprocess.run([sys.executable, "-c", ...])`) (Review Focus 5); over student ids `s0`…`s29` and company `c1`, all three values occur.
  - For every style, language and request, with a 40-character company name, a long round name and every role: `len(subject(...)) <= 60`.
  - `subject("direct", "en", "Example Robotics", "Series A", "Growth", "internship")` → `"Example Robotics internship?"`.
  - `subject("round", "de", "Example Robotics", "Seed", "Produkt", "internship")` → `"Nach eurer Seed: Produkt bei Example Robotics"`.
  - `suggested_style`: the three conditions true → `"formal"`; any one false → `"direct"`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/mailgen/test_choices.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `choices.py`.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: mail variant, subject and suggested style`.

### Task 4: Templates and `generate`

**Files:**
- Create: `src/kaltstart/mailgen/generator.py`, `src/kaltstart/mailgen/templates/{direct,round,formal}_{en,de}.j2`
- Modify: `pyproject.toml` (package data: include `templates/*.j2`)
- Test: `tests/mailgen/test_generator.py`

**Interfaces:**
- Consumes: Tasks 1 to 3.
- Produces: `generate(student: Student, company: Company, round: Round, contact: Contact, *, style: str, language: str, company_line: str | None = None, variant: int | None = None) -> Mail`.
  - Raises `MissingData` with the field names, in this order when several are missing: `first_name`, `last_name`, `programme`, `start_date`, `duration_months` (internship) or `workload_percent` (part-time), `contact_address`, `company_line_or_example`. Also raises `ValueError` for a company line or example over 200 characters, or an unknown style or language.
  - The templates receive only finished strings (greeting, opening, core, role paragraph, request, link, signature) and arrange them; Jinja2 environment with `autoescape=False`, `trim_blocks=True`, `lstrip_blocks=True`, `undefined=StrictUndefined`.
  - Openings: per style and language, three wordings for Direct and Round, one for Formal, each with four forms (amount and investor present, amount only, investor only, neither); `variant` overrides `choices.variant(...)`.
  - Core: the company line when given (`used_company_line=True`), else the chosen example in the mail's language; Formal follows the same rule (spec 7, after the builder check).
  - After rendering: collapse nothing silently; instead assert the gap rules of the Global Constraints and the 150-word limit, raising `AssertionError` with the style and language if broken (a template bug, caught by Task 5).

- [ ] **Step 1: Write the failing tests**:
  - A full English Direct mail for an invented student and company starts with `"Hi Anna!"` when `person_name="Anna Muster"`, and with `"Hi Example Robotics team!"` when `person_name=None`; Formal with a person starts `"Dear Anna Muster,"` / `"Guten Tag Anna Muster,"`.
  - `used_company_line` is `True` with a company line and `False` without; without a line the chosen example's text is in the body.
  - Each missing field raises `MissingData` naming it; a German mail for a student whose examples have only English text and no company line raises `MissingData(("company_line_or_example",))`.
  - Company name `"Fuchs & Eule"` and `"O'Neil Labs"` appear as written in the body (Review Focus 2).
  - The German Direct body contains `"du"` or `"dir"` forms and no `"Sie "` as a pronoun; German Formal the reverse; no German body contains `"ß"`.
  - The link appears after `"This is me: "` in Direct and in the signature in Round and Formal; no link, no link line.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/mailgen/test_generator.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `generator.py` and the six templates.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: mail templates and generate`.

### Task 5: The full matrix and the golden mails

**Files:**
- Test: `tests/mailgen/test_matrix.py`, `tests/mailgen/test_golden.py`, `tests/mailgen/golden/{direct,round,formal}_{en,de}.txt`

**Interfaces:**
- Consumes: `generate` from Task 4.

- [ ] **Step 1: Write the matrix test**: parametrised over style (3) × size category (3) × role (5) × language (2) × request (2) × missing data (none, no amount, no investor, neither) × company line (present, absent) × variant (0, 1, 2) for Direct and Round. Inputs at their longest: a 40-character company name, a 40-character investor, a 200-character company line and example made of short words, a link of 40 characters. For each mail: no `{`, `}`, `None`, `"  "`, `" ."`, `" ,"`, `"\n\n\n"`; body at most 150 words; subject at most 60 characters; `"led by"` and `"angeführt"` absent.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/mailgen/test_matrix.py -q`. Expected: PASS if Task 4 is right; any failure is a template to fix in this task, with the failing case kept as a regular test in `test_generator.py`.
- [ ] **Step 3: Write `test_golden.py`**: for each style and language, one fixed invented input with every optional part present, `variant=0`; the generated `subject + "\n\n" + body` equals the file in `tests/mailgen/golden/`. Generate the six files once with a short script, read each one, and commit them.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `test: mail matrix and golden mails`.

### Task 6: Documents and the owner's reading

**Files:**
- Modify: `DECISIONS.md`, `CHANGELOG.md`, `README.md` (Status table, a short "Mails" section), `CLAUDE.md` (structure line for `mailgen/`)

- [ ] **Step 1:** Add a decision row: three styles from the owner's model, optional company line, no sector sentence, never "led by", no round date, Formal uses one personal text, language rule with the Swiss canton and city lists, stable variant by SHA-256.
- [ ] **Step 2:** Show the owner the six golden mails (in French, explaining what each style is for) and apply the wording changes they ask for, regenerating the golden files and keeping the matrix green.
- [ ] **Step 3: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 4: Commit** `docs: mail generator (Phase 3)`; push only with the owner's approval.
