# Honest addresses: design

Date: 2026-11-19. Status: approved by the owner in conversation (points 1
to 4). Size: a project of four small parts.

## Why

The owner found that a student who picks "Anna Muster, VP of Product"
expects Anna's address, and gets `support@` once the mail is kept. Counts
on the live database (2026-11-19, read-only query, counts only):

| | Count |
|---|---|
| Companies with an address | 603 |
| Personal addresses | 57 (of about 1,200) |
| Companies with a suggested person | 401 |
| ... where no person has a published address | 335 (84 %) |
| Addresses such as `support@`, `noreply@`, `privacy@` | 173, in 146 companies |
| Companies left with no usable address once those are set aside | 22 |
| Companies whose named mail went to such an address only | 12 |

So the mail to a named person almost always lands in a shared inbox, the
page does not say so, and the greeting ("Hi Anna!") pretends otherwise.

## Goals

1. **Say where the mail goes, before "Keep".** The address stays hidden
   until the mail is kept (D77), but its kind is shown.
2. **Write the mail for the inbox it reaches.** A mail for a named person
   that goes to a shared address greets the team and asks them to pass it
   on to that person.
3. **Never write to an address that is not meant for it.** Support,
   no-reply, privacy, press, billing and similar addresses are not used.
4. **Let the student give the person's address.** An optional field, for
   an address the student found themselves; used for that mail only.

Non-goals: the app never guesses an address (rule kept, owner's choice A);
LinkedIn messages (a later, separate feature); changing the crawler.

## Decisions

**1. Destination shown.** On the company page, under the suggested person:

- "Goes to Anna's own address." (a personal address of that person)
- "Goes to the address you gave." (an address the student typed, point 4)
- "Goes to Example Robotics's careers address: Anna's own address is not
  published. The mail asks them to pass it on." (careers)
- "Goes to Example Robotics's general address: Anna's own address is not
  published. The mail asks them to pass it on." (generic)

"Someone else from their website" and "A person you found yourself" get one
line: "Goes to their own address if the website publishes it, otherwise to
the company's careers or general address, asked to pass it on." "No name" says it goes to the
careers or general address. My mails says "To Anna Muster, via the
general address" for such mails.

**2. The forward line.** When a named person is confirmed and the address
is not theirs (careers or generic), the greeting is the team's and a short
paragraph follows it:

| | English | German |
|---|---|---|
| Direct, Round | Could you pass this on to Anna Muster (VP of Product)? Thank you! | Könntet ihr das bitte an Anna Muster (VP of Product) weiterleiten? Danke! |
| Formal | Could you please forward this message to Anna Muster, VP of Product? Thank you. | Könnten Sie diese Nachricht bitte an Anna Muster (VP of Product) weiterleiten? Vielen Dank. |

The title is left out when unknown (a typed name). The rest of the mail
speaks to the team, as a mail without a name does today. The mail stays
within 210 words. `mailgen.Contact` gains `person_title`.

**3. Unfit addresses.** One function, `contacts.selection.usable_address`,
says whether a local part may receive an application. Refused local parts
(exact match, lower case): support, help, helpdesk, service, services,
customerservice, customer-service, customercare, care, kundenservice,
kundendienst, noreply, no-reply, donotreply, do-not-reply, privacy,
datenschutz, dpo, gdpr, dataprotection, press, presse, media, pr, abuse,
legal, billing, invoice, invoices, rechnung, rechnungen, accounting,
buchhaltung, finance, orders, order, bestellung, shop, store, newsletter,
unsubscribe, webmaster, postmaster, hostmaster, security, compliance,
returns, retoure, feedback, bugs, status, api, dev, developers. The app's
stores leave these addresses out (company page, list, "has an address"),
so another general address is chosen when there is one; a company with
none left shows no address. The crawler still stores them: no migration,
and the list can change without a new crawl.

**4. The student's address.** Under each named choice, an optional field
"Their address, if you know it". Accepted: one address of at most 254
characters with one "@" and a dot in the domain; nothing else is checked.
When filled, the mail goes there, greets the person by name, and the
address type is `student`. Migration `0010` adds `student` to the check on
`mails.address_type`; the owner pastes it before the push. `/privacy` says
that an address a student types is kept in that mail only.

## Approaches considered

- **Chosen:** filter unfit addresses in the app, show the destination, adapt
  the mail, accept a student's address.
- Guessing addresses from names: rejected by the owner (privacy page,
  bounces from the student's mailbox, the project's own rule).
- Marking unfit addresses in the crawler: needs a migration and a new crawl
  to take effect; the app filter works at once.

## Tests

- `usable_address` refuses each listed local part and accepts `info`,
  `hello`, `contact`, `jobs`, `team`, `office`, `kontakt`.
- Stores: a company whose only address is `support@` has no address; with
  `support@` and `info@`, `info@` is chosen.
- Mail: a named person with a generic or careers address gives the team
  greeting and the forward line, in the four language and formality
  combinations, with and without a title; a personal or student address
  gives the person's greeting and no forward line; the 210-word matrix
  still holds.
- Company page: each destination sentence; the address field; an invalid
  address keeps the form with an error; a valid one gives a kept mail with
  that address and type `student`.
- Migration `0010` and the migration check column `m0010_student`.

## Changes while building

- A forwarded mail may hold 230 words instead of 210: with the longest texts
  and an eight-word title, the forward line adds up to 20 words
  (`MAX_FORWARDED_BODY_WORDS`). Shortening it would make the mail less clear.
- The address field is one field under the choices, not one per choice; it
  applies to the named choice and is ignored for "No name".
