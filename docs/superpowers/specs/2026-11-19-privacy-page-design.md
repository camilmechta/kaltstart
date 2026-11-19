# Privacy page: design

Date: 2026-11-19. Status: draft for the owner's approval. Size: a small
change.

## Why

Kaltstart is about to invite students. It keeps personal data of two kinds:
the students' own (account, profile, kept mails) and that of people who
never signed up (names and titles read on company websites). Swiss law and,
for Germany and Austria, the GDPR expect a site to say who runs it, what it
keeps, why, where, for how long, and how to use one's rights. The site says
none of this today.

The project's purpose sets the tone: a non-commercial student project, a
small test, then 20 to 30 students, one figure for the owner's CV, then the
project closes. The page says so plainly.

## Goals, non-goals, anti-goals

Goals: one public page, `/privacy`, in plain English, about one screen of
reading; linked from every page and from sign-up.

Non-goals: no cookie banner (one session cookie, no tracking), no consent
checkbox, no legal notice ("Impressum"), no German or French version.

Anti-goals: anything the code does not do (the page must match the app
exactly); a promise the owner cannot keep alone.

## Decisions

- **Responsible party:** "Kaltstart", with the removal address shown
  elsewhere on the site.
- **Approach:** a page of the existing app, like `/about`. Rejected:
  folding it into `/about` (too long, mixes purpose and legal text); an
  external document (would drift from the app).
- The contact address is the `REMOVAL_CONTACT` value, as on `/about`;
  never hard-coded.

## Content

Headings and what each says (final wording left to the builder, short
sentences, no legal jargon):

1. **Who runs Kaltstart.** A non-commercial student project, in beta, by
   invitation. Contact: the removal address.
2. **If you have an account.** Kept: e-mail address, first and last name,
   university, degree and programme, languages, target role, what you are
   looking for and when, optional link, preferred countries and sectors,
   showcase sentences, and the mails you keep with their status. Purpose:
   preparing your mails and applying the fair-use limits. Deleting your
   account (on the profile page) removes your account, profile and
   showcase sentences at once; mails you kept stay counted for the
   companies, without your name or their text.
3. **If you work at a company in the list.** Kept: your name, job title and
   the page of your company's own website it was read on; the company's
   published addresses. Never from social networks or other sites. A name
   is only a suggestion a student must confirm. Removed when the company's
   last funding round is more than 12 months old, when the page no longer
   shows it, or on request to the removal address.
4. **What Kaltstart never does.** It never sends a mail (students send
   their own), never sells or shares data, shows no ads, has no visit
   statistics and no tracking; one cookie keeps you signed in, for 14 days.
5. **Where the data is.** The app runs on Render in Frankfurt (Germany);
   the database on Supabase in Paris (France). Funding rounds come from
   the Tech.eu Funding Explorer (CC BY 4.0).
6. **Your rights.** Ask for a copy, a correction or a deletion at the
   removal address; answered within 30 days.
7. **When the project ends.** All personal data is deleted; only totals
   without any name (for example a reply rate) are kept.

A "Last updated" date at the bottom.

## Links

- Footer of every page (`base.html`): "Privacy" next to "About Kaltstart".
- Sign-up page: one line under the button, "How Kaltstart uses your data:
  Privacy."

## Tests

- `/privacy` answers 200 without signing in and shows the removal contact
  of the app's configuration.
- Every page's footer links to `/privacy`; the sign-up page does too.
- The page names Render (Frankfurt) and Supabase (Paris), the 14-day
  cookie and the 12-month rule, so a later change to those values in code
  has a test to update.

## Left to the builder

The exact wording, within the content above; the styling, reusing the
`/about` layout.

## Documents

`DECISIONS.md` (next number), `CHANGELOG.md`.
