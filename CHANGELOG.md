# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- No e-mail confirmation at sign-up (D103): Supabase's own e-mail service
  sends 2 e-mails an hour, so confirmation is off and the sign-up page says
  the account is ready; an account left unconfirmed is told to write to
  the contact address. The setup guide now lists migrations up to `0011`.
- Show the value (D102): the landing page leads with "Internships that are
  never posted", says why it works in three points and shows an honest
  example (a general address with its PS, and the LinkedIn note); the list
  opens with "For you" (recent rounds naming someone of the student's
  field), rows say "Raised 5 days ago" and "{title} named: your field", and
  a strip shows the student's kept, sent and replied mails.

### Added

- LinkedIn as a second channel (D101): the app writes a connection note of
  at most 200 characters (counted by code on every combination) and a
  message for once the request is accepted; the kept page links to a
  LinkedIn people search and lists four steps; it counts in every limit and
  in the reply statistics like a mail; migration `0011`. Kaltstart never
  visits LinkedIn.

### Changed

- Large companies (Series B and later) name nobody: the student writes to
  the careers or general address, or names someone they know themselves;
  the list and its "name people" filter follow (D100).

### Fixed

- "Back" showed a mail as still kept after it was abandoned: the browser
  showed its saved copy. Pages are now sent with `Cache-Control: no-store`,
  static files still cache (D99).

### Added

- Honest addresses (D98): the company page says where each mail goes
  (the person's own address, or the company's careers or general address);
  a mail to a named person through a shared address greets them by first
  name and ends with a PS asking that it reach them; support, no-reply, privacy, press, billing and
  similar addresses are never used; a student can give the person's
  address they found themselves (migration `0010`). My mails says "via the
  general address" for such mails. Kaltstart still never guesses an
  address.

- "Forgot your password?": a student asks for a link by e-mail and chooses
  a new password on `/reset-password`; the link is spent only when the new
  password is sent, and every session ends afterwards. The sign-in page now
  says why it failed: wrong e-mail or password, e-mail not confirmed, too
  many sign-ins, or sign-in not working (D97).

### Changed

- The README is one page for visitors: what Kaltstart does, screenshots of
  the demo mode, the main product decisions, how it works, figures and how
  it was built with Claude Code. Operations moved to `docs/operations.md`
  and the crawler measurements to `docs/measurements/README.md`.

### Fixed

- A second click on "Sign in" showed "This form has expired" although the
  first click had signed the student in: a signed-in visitor sending the
  sign-in form again is taken to the companies, and the sign-in and
  sign-up buttons send their form once (D96).

### Added

- The header shows "7 of 10 mails kept this week · 2 waiting" on every
  signed-in page, `/about` says how many mails a student can keep, and
  every limit shown comes from `rules.LIMITS` (D95).

- A public privacy page, `/privacy`, linked from every page and from
  sign-up: what Kaltstart keeps about students and about people at
  companies, what it never does, where the data is, how to use one's
  rights, and that all personal data is deleted when the project ends
  (D94).

- Two target roles for technical students, Software & AI and R&D &
  Hardware: profile cards, mail paragraphs in English and German, and
  engineering and R&D heads read by the contact scraper; at a small
  company the CTO is suggested before a founder for these roles; migration
  `0009` (D93).

### Security

- Three ways a company website could stall the nightly contact scraper are
  closed: a run of credentials after a name, a long run of address letters
  or one address repeated many times, and a page charset no website uses
  (D90).
- Sign-in attempts are limited per computer and per e-mail from one
  computer, so a stranger can no longer lock a student out; an IPv6 client
  counts as its /64 network (D91).
- An abandoned mail keeps its company and round slot, copied or not, since
  its address showed once it was kept; migration `0008` (D92).

### Added

- After an outside review: atomic profile save, removals that also clear kept
  mails, one read of company names on My mails, and SQL tests on a local
  PostgreSQL (migration `0007`, D87).
- Single-use invitation codes, created by the owner in the SQL editor and
  stored as fingerprints; the shared code is no longer accepted (D86).
- Beta open to any university: no HSG-only wording, a Beta tag, the
  student's university in the profile and in every mail; migration `0005`;
  mails hold at most 210 words (D85).
- Names read on sites are cleaned of degrees and schools, and lines that are
  not a person's are dropped, in the scraper and when the app shows people;
  German titles get an English meaning (D84).
- `render.yaml`: the web app on Render's free plan in Frankfurt, deployed
  from `main` once the checks pass, with no secret in the file (D82).
- CV: a profile switch, on by default, adds "My CV is attached." to every
  mail and a reminder on the mail page; Kaltstart never stores a CV. Mails
  hold at most 205 words (D81).
- Profile: Bachelor or Master, then the programme; a line under each section
  says why it is asked. Mails name the degree. The preview says the hidden
  part is the e-mail address. Fixed: "I sent it" downloaded a file (D80).
- Repository protections: Dependabot updates for libraries and actions, a
  separate `security` workflow running `pip-audit`, actions pinned to exact
  commits, read-only workflows (D79).
- Security fixes after the final review of the web app: real client address
  behind the host's proxy, limits on sign-in and on wrong invitation codes,
  sign-out revokes the session, CSRF token rotation, safe links from data,
  security headers, non-blocking routes, fewer database calls on the list,
  pinned dependencies and an unprivileged container (D78).
- The preview of a mail hides the address; it shows once the mail is kept.
- Sending limits: at most 6, 9 or 15 mails per company and funding round by
  size, 10 kept mails per student a week, and a copied mail keeps its slot
  even when abandoned; every limit is set in one place (`rules.LIMITS`).
  Mails to one company vary in subject, wording and order; "N places left"
  replaces "Last slot".
- Web app motion: the generated mail unfolds and its address lights up, a
  check draws on Copy, chosen cards press, rows lift, and the landing
  example plays once; all stop under reduced motion.
- Web app, after an outside design review: an invented example of the
  product on the landing page and an honest headline, a folding size legend,
  style cards and no stepper on the company page, "Kept" status pills and
  rows on My mails, matching sign-in and sign-up pages, larger helper text.
  The default style is Round when the suggested person is a recruiter.
- Web app, second round of the owner's feedback: a profile with role cards,
  chips and a German switch; saving it leads to the company list; the
  company page says the address comes with the generated mail.
- Web app after the owner's first try: a second colour, size tags and legend,
  an About page with the data credit, numbered steps and choice cards on the
  company page, the reason a person is suggested, and a filter on companies
  that name people.
- Web app (`kaltstart.api`): sign-up with an invitation code, profile, company
  list with filters, company page with a free preview and "Keep this mail",
  My mails with statuses and reminders, account deletion; `--dev` mode with
  invented data; a `Dockerfile`. Migration `0004` for students and mails.
- Mails are built around the student's showcase sentence (up to 60 words);
  the sentence about the company is an optional bonus. A mail holds at most
  200 words.
- Mail generator (`kaltstart.mailgen`): three styles in English and German,
  an optional sentence of the student about the company, refusal naming any
  missing data, and every combination tested at its longest.
- Austria is read every night after Switzerland and Germany. Pages up to
  5 MB are read (2 MB before), so heavy home pages are no longer counted as
  unreachable.
- First measurement in Austria, on 20 companies: address found for 15 of the
  18 that publish one, no wrong address, people accuracy 9 lists of 10.
- Germany is read every night after Switzerland; `run` and `status` take
  several `--country` options.
- First measurement in Germany, on 20 companies: address found for 18 of the
  18 that publish one, people accuracy 10 lists of 13, coverage 50 %.
- Migration `0003`: removal of a person also covers their addresses
  whatever their type, name keys are computed alike in Python and SQL,
  `exclude_person` reports what it removed, and each run counts its
  database write errors.
- First full contact run on the 236 eligible Swiss companies: 161 with an
  address stored, 110 with a person suggested. The nightly run is live.
- Contact storage: tables `contact_emails`, `contact_people`,
  `contact_exclusions` and `contact_runs`, the `run` and `status` commands,
  and the `contacts` workflow that reads the due company sites every night
  (Switzerland only for now). Removal on request through two SQL functions.
- Contact scraper (`kaltstart.contacts`): polite fetcher, page choice, address
  and founder extraction, contact selection, and the `measure` and `summary`
  commands. Not run nightly and not connected to the database yet.
- `sample` command to draw companies for a measurement, and a free-text
  `args` input on the manual workflow run.
- First measurement on 20 Swiss companies: usable address confirmed for 65 %
  (inconclusive against 70 %), founder name confirmed for 5 % (fails 40 %).
- Second measurement on 20 new companies after the founder rewrite: usable
  address 65 %, founder name 30 %. Both thresholds still missed.
- Third measurement on 20 new companies: usable address 70 %, founder name
  45 %, both above their thresholds by one company (inconclusive).
- Fourth measurement with the same code, and verdict on 40 companies: usable
  address 70 % (pass), founder name 35 % (fail).
- Fifth to seventh measurements, on 60 new companies with the people
  scraper: people accuracy 24 lists of 25 (96 %, pass), people coverage 40 %
  (at the goal), usable address 52 % (fail against 65 %).
- Eighth measurement, on 20 new companies after the address fixes: usable
  address 70 % (one company above 65 %, inconclusive), people accuracy 8
  lists of 10, people coverage 40 %. No wrong address.

### Changed

- Workflows use `actions/checkout` 7.0.1 and `actions/setup-python` 7.1.0,
  still pinned to exact commits, `sql.yml` included. The `websockets` 17.4
  update is declined: the Supabase `realtime` client requires a version
  below 16.
- The `tests` workflow installs `requirements.txt` as the Docker image does
  and runs `pip check`, so a conflicting pin fails before the host builds
  it (D89).
- The contact scraper reads people with their job title instead of founders
  only, keeps leaders, function heads and managers, and recruiters, and
  proposes the person matching the student's target role. Two criteria
  replace the founder threshold: accuracy (90 %, blocking) and coverage
  (40 %, a goal).
- After a tuning run on the 80 companies already measured: titles written
  above the name, titles followed by a biography in the same block and names
  three levels above the title are read; text a page never shows, cards with
  a customer's logo and job titles in Italian or French are not. A website
  that is a profile on another organisation's site is reported as
  `not_own_site` and not read.
- A person read by the scraper is now a suggestion the student confirms on
  its source page; people accuracy (90 %) is tracked and no longer blocks.
- A caption that introduces somebody ("With ...") is not read as a name, and
  "Personal Care" in a title is no longer read as human resources.
- People under a plain "Board" or "Advisors" label, and people on a card
  that links to a customer story, are no longer kept.
- Ninth measurement, on 20 new companies: address found for 13 of the 16
  companies that publish one, no wrong address, people accuracy 6 lists of
  9 (fail), people coverage 30 %.
- The address threshold (65 % of all companies) is replaced by two criteria:
  an address found for 75 % of the companies that publish one on a site of
  their own, and no wrong address. The `summary` command reports both.
- After the verdict on 60 companies, three address fixes: the root of the
  site is read when the stored page no longer exists, a "Site Notice" link
  is read as a legal notice, and an address on a second domain that carries
  the company's name is kept.
- A network failure on `robots.txt` is reported as `unreachable`, not as
  `robots_forbidden`.
- Founder extraction rewritten from the failures of the first measurement:
  names are read only from team cards, "Name, role" lines and legal-notice
  labels, and only when the role is held at the company itself.
- After the second measurement: names one or two levels above the role are
  read, customer testimonials are skipped, Cloudflare-protected addresses are
  decoded. The usable-contact threshold is lowered from 70 % to 65 %.

## Phase 1 - 2026-11-12

First load run against the live database on 2026-11-11: 832 funding rounds
(Germany 508, Switzerland 260, Austria 64), 783 companies, 780 of them with a
website.

### Added

- Python package `kaltstart`, test setup with pytest, CI workflow, recorded
  Tech.eu API fixtures for tests.
- Ingestion: cleaning and transform functions, Tech.eu HTTP client, store
  interface with in-memory and Supabase implementations, SQL schema, pipelines
  (backfill, sync, details, reclean), command line interface.
- Nightly GitHub Actions workflow for `sync`, weekly `backfill` (Sundays) to
  pick up edits to known rounds, which the `/changes` endpoint does not
  report, and manual runs of any command including `report` and `cities`.
- `report` prints the share of companies with fetched details and with a
  website.

### Changed

- Size bounds for rounds without a known stage calibrated on real data:
  7 and 20 million euros (were 3 and 15).
- City aliases completed from the first load: spelling variants, one
  encoding glitch, and regions that Tech.eu stores in the city field.
- Design spec and Phase 1 plan translated to English; the spec file is now
  `docs/superpowers/specs/2026-11-11-kaltstart-design.md`.

### Fixed

- An address whose first letters a page writes outside its mail link is no
  longer stored as a second, truncated address.
- The nightly sync no longer crashes on a round that Tech.eu has not completed
  yet (missing date, identifier, company or page link); such rounds are
  skipped and listed in the run summary.

## Phase 0 - 2026-11-11

### Added

- Design specification, validated.
- Public documents: README, PRD, DECISIONS, CHANGELOG, CLAUDE.md.
- Implementation plan for Phase 1 (ingestion).
