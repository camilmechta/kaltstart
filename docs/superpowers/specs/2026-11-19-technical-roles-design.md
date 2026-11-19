# Technical roles: design

Date: 2026-11-19. Status: approved by the owner in conversation.
Parents: `2026-11-13-phase-2-people-design.md` (people kept, section 5
person choice), `2026-11-16-phase-3-mail-generator-design.md` (roles and
paragraphs), `2026-11-16-phase-4-web-app-design.md` (profile).

## 1. Why

The beta is open to any university (D85). Students of the EPFL already test
it: one in computer science, one in microengineering. The profile offers
five target roles, all on the business side (Product, Growth, Data,
Operations, Business development). A technical student has to pick the
closest one, and the mail then describes work they do not do ("help build
the dashboards the team needs"), while the person suggested is a business
lead. Many companies in the list are deep tech (hardware, medtech, energy),
which hire exactly these students.

Success: a computer science or microengineering student picks a role that
describes them, receives a mail whose role paragraph is true for them, and
is offered a technical lead of the company when the site lists one.

## 2. Goals, non-goals, anti-goals

Goals:
- Two new target roles: **Software & AI** and **R&D & Hardware**. They are
  for technical students in general, not for developers only.
- A mail paragraph for each, in English and German.
- The scraper keeps the heads of the two matching functions, and the app
  suggests them.

Non-goals:
- No Design, Finance or other new role.
- No new measurement on real sites; tests use invented pages only.
- No forced re-read of every site.

Anti-goals (a failure even if it works):
- Keeping individual engineers, developers or scientists. They are still
  dropped, as today (`_INDIVIDUAL` in `contacts/titles.py`).
- A business title read as technical, or the reverse: "Head of Business
  Development" must stay in sales and never become R&D.
- A mail over the existing limits (210 words, subject 60 characters).

## 3. Approaches considered

- **A. One role, "Engineering"** (software, hardware, AI, R&D). Simplest,
  but its paragraph has to stay so general that it speaks poorly to a
  microengineering or life-science student.
- **B. Two roles, Software & AI and R&D & Hardware.** Each mail speaks of
  the student's real work; the line between the two is easy to explain.
  Two paragraphs and two title families instead of one. **Chosen by the
  owner.**
- **C. Three roles, Software, Hardware, Science/Lab.** Most precise, but
  hardware and lab work often sit in the same team of a start-up, the
  scraper would rarely find a different person for each, and the student
  would hesitate between two cards.

## 4. The two roles

| Key | Card (EN) | Hint on the card | Name in German |
|---|---|---|---|
| `software_ai` | Software & AI | Building products, machine learning, infrastructure | Software & KI |
| `rd_hardware` | R&D & Hardware | Prototypes, electronics, mechanics, lab work | Forschung & Entwicklung |

The profile shows seven cards. Icons from the Lucide set already used
(ISC licence, inline): `code` for Software & AI, `cpu` for R&D & Hardware.

**Inside a sentence.** Today English sentences use the role name in lower
case ("a role in growth") and German ones put it after "im Bereich". Lower
case breaks these names ("software & ai", "r&d & hardware"). Each role gets
its own words for use inside a sentence, used instead of the lower-cased
name for every role where they are defined:

- English: "software and AI", "R&D and hardware".
- German: "Software & KI" ("im Bereich Software & KI"), "Forschung &
  Entwicklung".

**Role paragraphs** (final wording to be checked against the word limit):

- EN `software_ai`: "After a round, the team must ship faster. I would
  like to help build and ship the next features."
- EN `rd_hardware`: "New funding turns prototypes into products. I would
  like to help design, build and test the next iterations."
- DE `software_ai`: "Nach einer Runde muss das Team schneller liefern. Ich
  würde gerne helfen, die nächsten Features zu bauen und auszuliefern."
- DE `rd_hardware`: "Neues Kapital macht aus Prototypen Produkte. Ich würde
  gerne helfen, die nächsten Iterationen zu entwerfen, zu bauen und zu
  testen."

Like the other paragraphs, they speak of the student and never address the
reader, so they read right with "du" and "Sie".

## 5. People the scraper keeps

Two new categories, `engineering` and `rnd`, added to `CATEGORIES`.

| Category | Head level | Manager level |
|---|---|---|
| `engineering` | VP, Head, Director, Lead of Engineering, Software, AI, Machine Learning, ML; Chief AI Officer; German "Leiter Softwareentwicklung" | Engineering Manager, Software Manager |
| `rnd` | Head, Director, VP, Lead of R&D, Research, Hardware, Electronics, Mechanical, Forschung, Entwicklung; Chief Scientific Officer (in full words); German "Entwicklungsleiter(in)", "Leiter Forschung & Entwicklung" | R&D Manager, Hardware Manager |

Rules for the builder:
- The CTO stays in `leadership`, as today; it is not added to either new
  category.
- "Development" alone is **not** an R&D word: it would catch "Head of
  Business Development". "Entwicklung" is matched only as a whole word, so
  "Geschäftsentwicklung" does not match.
- "Head of R&D" and "Head of AI/ML" must read as one function. (The
  classifier only splits titles on `&` and `/` to drop a past job, so this
  holds today; a test pins it.)
- "Technology" and "Platform" are left out of the engineering words: they
  also appear in business titles ("Head of Technology Partnerships"), and
  the CTO already covers the technology lead. (Decided while planning.)
- "CSO" is ambiguous (chief scientific, security or strategy officer):
  only the full words "Chief Scientific Officer" count unless the builder
  finds a safe way to read the short form.
- Individual titles stay dropped: "Software Engineer", "Hardware
  Engineer", "Research Scientist", "ML Engineer".
- A title may already carry several categories. "Head of Data Engineering"
  may be both `data` and `engineering`; that is accepted. But a business
  title must not gain a technical category through a qualifier: "Head of
  Technology Partnerships" stays `sales` only, "Head of Market Research"
  stays out of `rnd`. Each of these cases gets a test.

## 6. The person suggested

`choose_person` (`contacts/selection.py`) keeps its order, with one change
for the two new roles:

1. a person in the role's category, a head before a manager;
2. otherwise, at a small company, a leader: **for the two technical roles,
   the CTO first**, then a founder, then the other leaders; for the five
   other roles, unchanged (a founder first);
3. otherwise, at a medium or large company, a recruiter;
4. otherwise nobody.

Mappings to extend: `ROLE_TO_SELECTION` (`api/compose.py`) and
`ROLE_TO_CATEGORY` (`contacts/titles.py`). The mail style rule is unchanged
(Round if the person recruits, else Direct).

## 7. Database

Migration `0009` replaces the check on `profiles.target_role` so it
accepts the seven roles. `supabase/check_migrations.sql` gets a column that
is true once `0009` is applied, and `tests/sql` cover saving a profile with
each new role. The owner pastes `0009` in the SQL editor **before** the push
that ships the new roles, then runs the check; otherwise saving a profile
with a new role fails online.

`contacts.categories` has no check on its values: no change there.

## 8. Existing data

Every site is read again 30 days after its last reading (`REREAD_DAYS`).
Technical heads therefore appear over the month after the release, without
an extra run and within the Tech.eu and site quotas. Until a site is read
again, a student with a technical role is offered the CTO at a small
company (already stored as a leader) or a recruiter at a larger one.

## 9. Documents to update

- `CLAUDE.md`: people kept by the scraper, from five functions to seven
  (adding engineering and R&D).
- `DECISIONS.md`: a new decision (next number) with this choice, why, and
  the rejected options A and C.
- `CHANGELOG.md`: one line under Added.
- The dev seed (`api/seed.py`): invented technical heads on `example.*`
  sites, so the local app shows the new suggestions.

## 10. Left to the builder

- Exact regular expressions, as long as section 5's cases and anti-goals
  are covered by tests written first.
- The final wording of the four paragraphs if a test shows a mail over the
  word or subject limit; the meaning stays.
- The order of the seven cards on the profile (proposal: the five business
  roles, then the two technical ones).
