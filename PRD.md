# Kaltstart: product requirements

## 1. Problem

Students looking for an internship or a part-time job at a young tech company
usually apply to posted openings. Companies that just raised money are often
about to hire, but they rarely post a job yet, and a generic spontaneous
application sent to a random address gets no answer. Finding the right
companies, the right address, and a reason to write takes hours.

Kaltstart finds tech startups and scale-ups in Switzerland, Germany and Austria
that raised funding in the last 12 months, finds who to write to, and prepares
a spontaneous application that opens on the funding round. The student reviews
and sends the mail from their own mailbox. The app never sends anything.

The product does not list job openings. Its difference is a well targeted
spontaneous application, sent when the company has just received money to hire.

## 2. Users

Students of the University of St. Gallen (HSG), invited by the project owner.
Sign-up needs a single invitation code shared for the whole test. The email
domain is not checked.

## 3. User journey

1. The student signs up with the invitation code and fills in a profile: name,
   programme, languages, target role, type of request (internship or part-time),
   availability, preferred sectors and locations, and up to two concrete
   examples of past work.
2. The student browses companies that raised funding recently, with filters.
3. The student opens a company page, sees the round and the contact proposed
   with its source and confidence level.
4. The student generates a mail. Generating reserves a slot for that company.
5. The student copies the address, subject and text, and sends the mail from
   their own mailbox.
6. The student marks the mail as sent, answered or abandoned. The app shows a
   reminder after 72 hours without a status.

## 4. Scope

In scope:

- Funding rounds for Switzerland, Germany and Austria, from the Tech.eu Funding
  Explorer API.
- Contact addresses and founder names found on public company web pages.
- Mail generation in English and German, from rules and templates.
- Booking rules: at most 3 non-abandoned mails per company over 30 days, at most
  5 mails per student in generated or copied status, one mail per student and
  company.
- Follow-up tracking and response rate reporting.

Out of scope:

- Sending mails automatically.
- Reading students' mailboxes.
- Storing CVs or attachments.
- Scraping LinkedIn.
- Guessing email addresses from a name.
- Calling an AI API at runtime.
- Other European countries (they may be added later).
- Requests other than internship or part-time (first job, simple call).
- Job openings.

## 5. Success metrics

The project is first a product builder portfolio. It becomes a real product only
if the final test reaches thresholds fixed in advance.

| Metric | Threshold | Measured in |
|---|---|---|
| Companies with a usable contact found by the scraper | 70 % | Phase 2 |
| Companies with a founder name found | 40 % | Phase 2 |
| Human response rate | 10 % of sent mails | Phase 5 |
| Positive response rate | 3 % of sent mails | Phase 5 |

Definitions:

- Usable contact: at least one email address published on the company website,
  of any type.
- Human response: any reply written by a person, including a refusal.
  Automatic acknowledgements do not count.
- Positive response: an offer of a call or an interview.
- Sent mail: a mail the student marked as sent. Mails presumed sent (no status
  update after 7 days) are excluded from the rates.

The test targets 20 students and about 10 mails each, around 200 mails. The
thresholds correspond to 20 human responses, 6 of them positive.

If a Phase 2 threshold is missed, work stops and a plan B is chosen before
going further: manual entry of missing contacts for the test, reading pages
with a real browser, or using the contact form.

## 6. Constraints

- The whole product is written in Python, with no AI at runtime: rules, text
  extraction and templates.
- Funding data comes from the Tech.eu Funding Explorer API, licence CC BY 4.0,
  with the credit "Tech.eu Funding Explorer" shown in the app and the README.
- Tech.eu quotas: 120 requests per minute, 600 per hour, 2000 per day.
- Scraping respects robots.txt, uses a limited rate and reads public pages only.
- Personal data is kept to a minimum, and every contact keeps its source.

## 7. Phases

| Phase | Content | Done when |
|---|---|---|
| 0. Scoping | Spec, PRD, repository, CLAUDE.md, structure | The spec is validated |
| 1. Ingestion | Tech.eu to Supabase for the three countries, cleaning, incremental update | Rounds are in the database and clean; a second run adds only what is new |
| 2. Contacts | Scraper tested on 20 Swiss sites | Rates are measured and compared with the 70 % and 40 % thresholds |
| 3. Mails | Generator and templates in English and German | All test cases pass, for each style |
| 4. Front end | FastAPI server, invitation sign-up, filters, list, company page, tracking | A student goes from sign-up to a copied mail without help |
| 5. Test | 20 HSG students, about 200 mails | Report comparing the rates with the 10 % and 3 % thresholds |

Each phase has its own implementation plan and ends with a code review.
