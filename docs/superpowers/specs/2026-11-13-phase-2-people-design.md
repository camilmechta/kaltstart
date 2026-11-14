# Phase 2: from founders to people, design

Date: 2026-11-13
Status: awaiting review
Parent specs: `2026-11-11-kaltstart-design.md` (sections 2, 6, 7.2, 7.4) and
`2026-11-12-phase-2-contact-measurement-design.md`, which this document amends.

## 1. Why

Four measurements on 80 Swiss companies gave two clear results (decisions D36
to D42):

- Finding a usable address works: 70 % of companies on the last 40, and no
  address reported by the scraper was found wrong.
- Finding the name of a founder does not: 35 % on the last 40, with 5 wrong
  lists out of 19, and no single cause left to fix.

The scraper reads a team card well: a name in one block, a job title next to
it. What it does badly is decide whether that person is a founder, because
every site says it differently. This design removes that question. The
scraper reads the people a company presents with their job title, keeps those
who lead the company, lead a function or recruit, and the product picks the
right one for each student.

It also follows a product observation by the project owner: for an internship
in product at a company of a hundred people, the head of product is a better
person to write to than the founder.

## 2. What changes for the student

Three levels, from automatic to manual. Only the first is built in this
phase; the two others are recorded here so that the phases that build them
agree with it.

1. **The scraper proposes a person**, read on the company's own site, with the
   page it was read on.
2. **Otherwise the student completes it**: the app shows the link to the
   company's team page, a button that opens a search the student runs in
   their own browser, and two fields, name and job title. The scraper visits
   nothing for this. A name entered by a student is used for that student's
   mail only and never joins the shared list.
3. **In every case the address comes from the company's site**, where the
   scraper is reliable. An address is never guessed. If the site publishes the
   person's own address it is proposed; otherwise the mail goes to the
   careers or general address and opens with the person's first name.

## 3. Scope

In scope:

- Reading people with their job title, in place of founders.
- Job-title categories and levels.
- The rule that chooses the person and the address proposed to a student.
- Measuring it, with two new criteria.

Out of scope, in the phases that already hold them:

- The "who are you writing to?" screen, its two buttons and the student's own
  entry: Phase 4.
- Mail wording that depends on the recipient's job: Phase 3.
- The nightly run, the database table, removal on request: the second plan of
  Phase 2, after the verdict.
- Accepting a company's second domain when its own legal notice presents it
  as its own (seen 4 times in 80 companies): a separate change, after this
  one, so that one measurement tests one change.
- The Swiss commercial register as a second source: later, if the measurement
  shows small Swiss companies are the weak point.
- Everything about addresses, which is accepted as it is.

## 4. What the scraper reads

### 4.1 A person

On home, legal-notice, team and about pages. A person is a name and the job
title written next to it, in one of the layouts already in use (D37, D40):

- a card: one block holding nothing but the name, next to a short block
  holding the title, or next to one of that block's wrappers, at most two
  levels up;
- a line: "Name, title" or "Name - title";
- a label: "Geschäftsführer: Name, Name".

Running prose is never read. What marks a block as worth reading is no longer
a founder word but a recognised job title (4.2).

Because any job title now triggers the reading, four more things are told
apart from a team card (decision D51):

- a job opening: the name always comes before the title, never after it; a
  title with "(m/w/d)" or a workload in per cent, or inside a block named
  after jobs, careers or vacancies, is an opening;
- a sentence: a title block with a lower-case word other than a small
  connector ("Built for every Head of Sales") is not a title;
- another section: a card whose nearest section heading announces advisors,
  a board, investors, job openings, customers, speakers or press is skipped;
- a label or a place: words such as "Full Time", "Apply Now" or a city are
  never a person's name.

For each person the scraper keeps: the name, the title exactly as the site
writes it, its categories, its level, and the page it was read on. Nothing
else: no picture, no biography, no link to a profile.

### 4.2 Job titles kept

A title is kept when it belongs to one of seven categories. A person may
belong to several ("Co-Founder & Head of Product" is leadership and product).

| Category | Titles, in English, German and French |
|---|---|
| `leadership` | Founder, Co-Founder, CEO, Chief Executive Officer, Managing Director, President, COO, CFO, CTO and their spelled-out forms; Gründer(in), Mitgründer(in), Geschäftsführer(in), Geschäftsleitung; Fondateur, Fondatrice, Cofondateur, Cofondatrice, Directeur général, Directrice générale |
| `product` | a head or manager title (below) with Product, Produkt, Produit; CPO, Chief Product Officer |
| `growth` | the same with Growth, Marketing; CMO, Chief Marketing Officer |
| `data` | the same with Data, Analytics; Chief Data Officer |
| `operations` | the same with Operations, Betrieb, Opérations |
| `sales` | the same with Sales, Business Development, Partnerships, Vertrieb, Ventes; CRO, CCO, Chief Revenue Officer, Chief Commercial Officer |
| `recruiting` | the same with People, HR, Human Resources, Talent, Recruiting, Personal, Ressources humaines; CHRO, Chief People Officer |

Two levels:

- `head`: Head of, Director, VP, Vice President, Chief, Lead, Leiter(in),
  Bereichsleiter(in), Directeur, Directrice, Responsable. Every `leadership`
  title is at this level.
- `manager`: Manager, as in "Product Manager". Kept because it is often the
  person in charge at a small company, and ranked after a `head` of the same
  category. A recruiter ("Recruiter", "Recruitment Manager") is at this level.

A head word and a function word must stand side by side ("Head of Product",
"Product Lead", "Marketingleiter"), with one qualifier at most in between
("Head of Global Sales"). A title that names an individual contributor's job
(engineer, scientist, designer, developer, analyst, specialist) carries no
function category, whatever else it says: "Lead Data Scientist" is not a head
of data. "Produktion" is manufacturing, not product. A president is not kept
when the title names a board.

### 4.3 People not kept

- Anyone without a head or manager title: developers, designers, analysts,
  interns, working students, assistants.
- Heads of purely technical functions (Head of Engineering): no role a
  student can ask for matches them. A CTO is kept, as leadership.
- Board members, advisors and investors, unless their title also carries a
  kept category at this company ("Co-Founder & Advisor").
- Anyone whose title is tied to another organisation, and anyone in a
  customer testimonial (D37, D40, unchanged).
- "Former CEO", "Ex-CEO", "Assistant to the CEO": a title someone no longer
  holds, or that belongs to someone else, is not theirs. A past job named
  after the present one does not cancel it: "Founder, ex-McKinsey" is a
  founder.

## 5. Who is proposed

The student's target role maps to a category: product to `product`, growth to
`growth`, data to `data`, ops to `operations`, BD to `sales`.

| Order | Condition | Person proposed |
|---|---|---|
| 1 | Someone is in the category of the student's target role | That person; a `head` before a `manager`; then page order |
| 2 | Otherwise, small company | A `leadership` person; a founder before another leader |
| 3 | Otherwise, medium or large company | A `recruiting` person; a `head` before a `manager` |
| 4 | Otherwise | Nobody: neutral greeting |

The student always sees the whole list with its source pages and can choose
another person.

The address, in order: the published address of the person proposed (its
local part carries their last name, or is exactly their first name: D35);
else the careers address; else the general address. When the site publishes
nothing but the address of another person kept, that person is proposed with
their address, so that the company does not disappear from the list. With no
address at all, the company is hidden from the student list as today.

Confidence: high for the person's own published address; medium for a careers
address, or a general address with a person proposed; low for a general
address alone. This replaces the table of the parent spec, section 7.2, where
"founder" becomes "person proposed".

## 6. Protections

- One mail per person and per student, in addition to one mail per company
  and per student.
- Three non-abandoned mails per company over 30 days, unchanged. It also
  protects people: nobody receives more than three applications a month from
  the app.

## 7. Personal data

Rules of caution, not legal advice. If the project becomes a real product,
this section must be reviewed by someone qualified, for Swiss law and for the
GDPR in Germany and Austria.

- One source: the company's own site, on a page it publishes.
- The minimum: name, title, categories, level, source page, date read.
- Freshness: a person who is no longer on the site at the next reading is
  removed.
- Removal on request: a person or a company can ask not to be listed. An
  exclusion list keeps the scraper from adding them again.
- Nothing public: this data is never in the repository and never visible
  without an account. Students see it one company at a time.
- A name entered by a student stays with that student's mail.

In this phase, as in the measurements so far, names exist only in files under
`local/` on the owner's machine.

## 8. Success criteria

The criterion "name of a founder for 40 % of companies" is replaced. It
measured one number where two different things matter, and the scraper is no
longer what stands between a student and a mail: when it finds nobody, the
student completes it. The replacement was fixed before any measurement of the
new code.

| Criterion | Definition | Threshold |
|---|---|---|
| Accuracy | Among companies for which the scraper reports people: the share where every person reported is a real person of this company, with the right title, in a kept category | 90 %, blocking |
| Coverage | Among all companies: the share where the scraper reports at least one person and the whole list is right | 40 %, a goal |

Accuracy blocks: below 90 %, the people read by the scraper are not shown to
students, and only levels 2 and 3 of section 2 are offered. Coverage is a
measure of comfort: at 35 % the product still works.

On the last 40 companies, with the founder-only code, accuracy was 14 of 19
(74 %) and coverage 14 of 40 (35 %).

The 90 % figure is a choice, not a demonstrated value: one wrong list in ten
is judged recoverable because the student sees the name and its source page
before sending.

## 9. Measurement

The protocol of the contact measurement, with these changes:

1. **Tuning** on the 80 companies already seen. These figures do not count
   for the verdict: the rules will have been written while looking at them.
2. **Verdict** on 40 companies never seen, drawn in two samples of 20 (seeds
   2030 and 2031, excluding the four earlier sample files), with the code
   frozen between the two. Twenty companies were shown to be too few to
   conclude (D42).
3. Verification by an assistant on all 40 with a browser that renders
   JavaScript, then by the owner on 5 companies of each sample.

The verification column `founder_check` becomes `people_check`, with the same
four values: `confirmed` (every person reported is right), `wrong` (at least
one is not), `missed` (nobody reported, but the site names a person in a kept
category), `none_exists`.

A result within one company (coverage) or one list (accuracy) of its
threshold is inconclusive, and 20 more companies are drawn.

The usable-contact criterion stays at 65 % and is measured again on the same
40 companies, to check that nothing regressed.

## 10. Consequences for the parent spec

To be changed when this design is implemented, with the former rules kept in
`DECISIONS.md`:

- Section 2: the criterion "name of a founder, 40 %" becomes the two criteria
  of section 8.
- Section 6.1: `contacts` holds a person's name, title, categories and level
  in place of "founder's name and role".
- Section 7.2: founder names, address types, the contact table and the
  confidence table follow sections 4 and 5.
- Section 7.4: the rule of one mail per person is added.
- Section 6.5: the personal-data rules of section 7 are added.

## 11. Decisions

To be added to `DECISIONS.md`:

| Decision | Reason | Options set aside |
|---|---|---|
| The scraper reads people with their job title instead of founders | Reading a team card works; deciding who is a founder does not, and has no single cause left to fix. For many companies a function head is the better person to write to | Keep adding founder rules; drop names altogether |
| Only leaders, heads and managers of five functions, and recruiters are kept | They decide on a hire, and it keeps personal data to people with an outward-facing role | Keep everyone on the team page |
| The person proposed follows the student's target role first, then the company's size | It answers the case where the head of a function is the right contact, and changes little at a company of ten | Size first, as before |
| When the scraper finds nobody, the student completes the name, helped by a link to the team page and a search the student runs | Costs almost nothing, stores no scraped personal data, and makes the scraper's coverage a comfort instead of a gate | External paid data; address finders, which guess addresses |
| A name entered by a student is used for that student's mail only | No shared list built from unverified input | Share it with other students |
| Two criteria replace the founder threshold: accuracy at 90 %, blocking, and coverage at 40 %, a goal | A wrong name in a mail is worse than a missing one; one figure hid the difference | Coverage alone; no threshold |
| The verdict is taken on 40 new companies with frozen code | Twenty companies gave 45 % and then 25 % for the same code | Decide on 20 |
| One mail per person and per student | Protects the person, as the company cap protects the company | Company cap only |
