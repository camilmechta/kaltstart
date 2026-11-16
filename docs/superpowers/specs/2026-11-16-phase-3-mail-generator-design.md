# Phase 3: the mail generator

Date: 2026-11-16. Status: written after a conversation with the project
owner; points marked "builder's call" were decided by the author of this
document, not by the owner.

Parent: `2026-11-11-kaltstart-design.md`, sections 6.2 (student data) and
7.3 (mail generation). This document replaces the open parts of 7.3 and
keeps every rule of 7.3 it does not change.

## 1. Intent

The generator writes the spontaneous application a student sends to a
company that has just raised money. It is a pure function: it receives the
student's profile, the company, its round, the contact and a few choices, and
returns a subject and a body. It calls nothing: no network, no database, no
AI (a hard rule of the project). The server of Phase 4 calls it when a
student clicks "Generate".

What makes a mail work, from the model the owner provided (a cold mail to a
startup founder that got an answer): a true personal hook, precise dates,
the student's own experience with the company's product turned into an
offer, an easy question as a close, a link that shows who the student is,
and brevity. The model is used for its structure, never for its text.

The part of that model that matters most, the student's own words about
this company, cannot be generated without AI. The student may therefore
write it (section 4). Phase 5 compares reply rates with and without it.

## 2. Goals, non-goals, anti-goals

Goals:

- Three styles, Direct, Round and Formal, each in English and German.
- A mail that reads as written for this company, from facts that are true.
- The same inputs always give the same mail; two students writing to the
  same company get different openings.

Non-goals (Phase 4): the screen where the student generates and copies a
mail, the reservation rules (3 mails per company in 30 days and the others),
storing the mail, the student's sign-up and profile screens.

Anti-goals, which would make this a failure even if every test passes:

- A sentence with a gap, a placeholder, a doubled space or "None" in it.
- A false fact: a wrong amount, an investor who did not lead, a person
  greeted by a name the student did not confirm.
- A mail that reads as a mass mail, or one over 150 words.
- A mail sent to a person the student has not confirmed (D60): the
  generator only greets by name when the contact passed to it carries a
  confirmed name.

## 3. Constraints

From the parent spec and `CLAUDE.md`: no AI at runtime; Jinja2 for the
templates; body at most 150 words, subject at most 60 characters; English
and German only; every opening has a version without an amount and one
without an investor; refusal with a message naming the missing data when a
required field is absent; templates and code in English; no real person or
company in tests or fixtures (invented ones on example domains).

## 4. Inputs

```
generate(student, company, round, contact, *, style, language, company_line=None) -> Mail
```

| Input | Fields used | Source |
|---|---|---|
| `student` | first name, last name, degree programme, languages, target role (product, growth, data, ops, bd), request type (internship or part-time), start date, duration in months (internship) or workload in per cent (part-time), link (optional, new), up to two examples, each in English and German, with the chosen one | Phase 4 profile (`profiles`, `experiences`) |
| `company` | id, name, country, city, region, sectors | `companies` |
| `round` | stage, amount in euros, native amount and currency, investors in the order Tech.eu gives them, size category | `rounds` |
| `contact` | address and its type; a person name, or none | `contact_emails`, `contact_people`. The caller passes a name only when the student confirmed it |
| `style` | `direct`, `round` or `formal` | chosen by the student |
| `language` | `en` or `de` | rule of section 6, the student can switch |
| `company_line` | the student's own sentence about this company, at most 200 characters, in the mail's language | typed when generating (new) |

The student also has an id; the generator receives it with the profile for
the variant choice of section 8.1.

Types (builder's call): frozen dataclasses `Student`, `Example`, `Company`,
`Round`, `Contact` in `kaltstart.mailgen.models`. Spellings: role `product`,
`growth`, `data`, `operations`, `business_development`; request `internship`,
`part_time`; style `direct`, `round`, `formal`; language `en`, `de`; size
category and stage as stored by the ingestion. The round date is not used:
every round in the app is from the last 12 months, so the mails say
"recent" implicitly and a month adds words without adding persuasion.

Two additions to the parent data model, both stored in Phase 4: the
optional `link` on the profile (an `https://` address), and the
`company_line` with each generated mail, so that Phase 5 can compare reply
rates with and without it.

## 5. Output

```
Mail(subject, body, language, style, used_company_line: bool)
```

or the exception `MissingData` listing the names of the missing fields, in
English, for the server to translate. Required: student first name, last
name, degree programme, start date, duration or workload (by request type),
contact address, and at least one of `company_line` or an example in the
mail's language.

## 6. Language

German when the student speaks German and the company is in Germany, in
Austria, or in a German-speaking part of Switzerland; English otherwise. The
student can switch. The package exposes this rule as
`choose_language(student, company)`; `generate` receives the language
already chosen.

German-speaking Switzerland is decided on `region` when known (full English
canton names, as the ingestion stores them: the German-speaking cantons and
Bern), else on `city` (the main German-speaking cities, including Biel,
Fribourg's German-speaking towns and Brig), else English (builder's call:
most Swiss rows have no region, and a wrong English mail is a smaller fault
than a wrong German one).

German text is written without the letter "ß", so that the same templates
read correctly in Switzerland (builder's call).

## 7. The three styles

Each style is one Jinja2 template per language, six in all, under
`src/kaltstart/mailgen/templates/`. Shared pieces (round wording, amount,
role paragraphs, request, signature) are Python helpers or Jinja2 macros
used by all styles.

| | Direct | Round | Formal |
|---|---|---|---|
| Model | the owner's example | the round and what it means for the team | larger companies, HR and careers addresses |
| German address | "Du" | "Du" | "Sie" |
| Greeting with a confirmed person | "Hi Anna!" / "Hallo Anna!" | "Hi Anna," / "Hallo Anna," | "Dear Anna Muster," / "Guten Tag Anna Muster," |
| Greeting without one | "Hi {company} team!" / "Hallo {company}-Team!" | same, with a comma | "Dear {company} team," / "Guten Tag," |
| Opening | short congratulation on the round | the round and the growth it implies for the target function | the round, stated soberly |
| Core | company line, else example | company line, else example; then the role paragraph | company line, else example; then the role paragraph |
| Close | an easy question ("Would that work?") | a request for a 15-minute call | a request for a conversation, with thanks |
| Link | "This is me: {link}" | in the signature | in the signature |

Sketch of the Direct style in English, with every optional part present:

```
Subject: {Company} internship?

Hi Anna!

Congrats on the €8M Series A! I'm studying {programme} at HSG and have an
internship window from 1 April for 3 months.

{company line, or the chosen example}

I'd love to help with {role}, or with whatever helps most. Would that work?

This is me: {link}

Best,
{first name} {last name}
```

Signature in every style: first and last name, degree programme at HSG,
and the availability in one line (parent rule).

Default style (builder's call, for the Phase 4 screen):
`suggested_style(contact, round)` returns `formal` when the contact has no
confirmed person, its address is of type careers or generic, and the size
category is large; `direct` otherwise. The student can always change it.

## 8. Variable parts

### 8.1 Round wording

| Stage | English | German |
|---|---|---|
| Pre-Seed, Seed, Series A to D+, Growth/Late | "Series A" and so on | same |
| Other, unknown, Crowdfunding | "funding round" | "Finanzierungsrunde" |
| Debt | "financing" | "Finanzierung" |
| Grant | "grant" | "Förderung" |

Amount: the native amount and currency when known, else euros; rounded to
one decimal under 10 million and to a whole number above; English "€8M",
"CHF 2.5M", "$40M"; German "8 Mio. €", "2,5 Mio. CHF". No amount, no
amount phrase.

Investor: the first one in the list, printed as stored. The mails never say
"led by": the data does not mark the lead, and naming a wrong lead is a
false fact. One investor: "backed by {investor}" / "mit {investor}"; several:
"with {investor} and others" / "mit {investor} und weiteren". An investor
name over 40 characters is treated as no investor (builder's call).

Amount details (builder's call): a zero or missing amount is no amount; an
empty currency falls back to euros; symbols for EUR, USD and GBP, the code
before the number for any other currency ("CHF 2.5M", "SEK 30M"); the value
is rounded once, so 9.96 million reads "10M".

Each style has, per language, an opening for each combination of amount
present or absent and investor present or absent. The parent rule of three
wordings per size category applies to the Direct and Round styles: the
wording is chosen by a stable hash of the student id and the company id, so
regenerating gives the same text and two students differ. `generate` takes
an optional `variant` (0, 1, 2) that overrides the hash, for tests. Formal
has one wording per combination.

### 8.2 Role paragraph

One per target role (product, growth, data, operations, business
development) and per language, at most 35 words, shared by the Round and
Formal styles. Direct names the role in one phrase only.

### 8.3 Request

Internship: "an internship from {date} for {n} months". Part-time:
"part-time work ({workload} %) from {date}". Dates written in full ("1
April 2027", "1. April 2027").

### 8.4 Sector sentence

The parent spec's sentence about the sector is dropped from all three
styles: the model has none, and a generic sector sentence is what makes a
mail read as a mass mail. Builder's call, to be confirmed by the owner.

### 8.5 Company line and examples

The company line and the examples are the student's own text and are never
changed, except that surrounding whitespace is removed and a final full
stop is added when missing. Each is at most 200 characters (checked by the
generator too, as a refusal, so that the 150-word limit always holds).

## 9. Subject

| Style | English | German |
|---|---|---|
| Direct | "{Company} internship?" | "Praktikum bei {Company}?" |
| Round | "After your {round}: {role} at {Company}" | "Nach eurer {round}: {role} bei {Company}" |
| Formal | "Application: {role} internship at {Company}" | "Bewerbung: {role}-Praktikum bei {Company}" |

"Internship" becomes "part-time role" / "Teilzeit" for part-time requests.
`{role}` is the short display name ("Product", "Growth", "Data",
"Operations", "Business development"). When a subject would exceed 60
characters, the round is dropped, then the role; Direct falls back to
"Internship?" / "Praktikum?". The shortest form of each style is under 60
characters for any company name, so the generator never cuts a subject
(builder's call).

## 10. Tests

All in `tests/mailgen/`, invented people and companies only:

- Word count: words of the body split on whitespace, greeting and
  signature included; a link counts as one word.
- For each style: every combination of size category (3) × target role (5)
  × language (2) × request type (2) × missing data (none, no amount, no
  investor, neither: 4) × company line (present or absent: 2), 480 cases
  per style. For each: no `{`, `}`, "None", double space or empty line pair;
  body at most 150 words with the longest allowed company line or example
  (200 characters of short words), a 40-character investor and a link;
  subject at most 60 characters with a 40-character company name; the
  greeting names a person only when the contact carries one.
- Determinism: the same inputs give the same mail; two student ids give
  different openings for at least one company in a small set.
- Each refusal names its field.
- Language rule, round wording and amount formatting, one test per row of
  their tables.
- German templates contain no "ß"; German Direct and Round use "Du" forms,
  Formal uses "Sie" forms (a list of forbidden words per style).
- A golden file per style and language, in `tests/mailgen/golden/`: one
  full mail, written by the builder, then read by the owner before the
  phase is closed, to catch any unintended change of text.

Jinja2 is added to the dependencies of `pyproject.toml`. `DECISIONS.md` and
`CHANGELOG.md` are updated as for every phase.

## 11. Open points for the owner

- The sector sentence is dropped (section 8.4).
- The mails never say "led by" (section 8.1).
- The owner reviews the six golden mails before the phase is closed.

## 12. Left to the builder

The exact wording of every sentence (in the spirit of section 7 and the
model, never copying it), helper names, the hash function, the list of
German-speaking cantons and cities, and how the templates share their
pieces.
