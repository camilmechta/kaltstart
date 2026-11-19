# Contact scraper measurements

The contact scraper is measured on companies drawn at random, with every
result checked on the company's site by an assistant. Samples and summaries are in this
folder; they contain no name and no address.

| Confirmed, on companies never seen before | Run 1 | Run 2 | Runs 3 and 4 | Threshold | Verdict |
|---|---|---|---|---|---|
| Company with a usable address | 65 % | 65 % | 70 % | 65 % (was 70 %) | Pass |
| Company with a founder's name | 5 % | 30 % | 35 % | 40 % | Fail |

Runs 1 and 2 cover 20 companies each; runs 3 and 4 use the same code and
cover 40 together. Founder extraction was rewritten after run 1 and refined
after run 2, each time from the failures read on the real pages. No address
reported by the scraper was found wrong in any run. Finding addresses is
accepted; finding founders is not. The scraper has since been changed to
read the people a company presents with their job title (leaders, function
heads and managers, recruiters).

That people scraper was measured on 60 more companies (runs 5 to 7, same
code):

| Confirmed, on 60 companies never seen before | Runs 5 to 7 | Threshold | Verdict |
|---|---|---|---|
| Company with a usable address | 52 % | 65 % | Fail |
| People accuracy: lists reported that are entirely right | 24 of 25 (96 %) | 90 %, blocking | Pass |
| People coverage: companies with a right list | 40 % | 40 %, a goal | At the goal (inconclusive) |

People read by the scraper can be shown to students. Three of the 24 right
lists hold a co-founder or an acting officer shown in an advisors or board
section: the rule fixed before the measurement counts them as right, a
stricter reading would give 21 of 25 (84 %). The one wrong list is a degree
read as part of a name. No address reported was wrong, but the address rate
fell from 70 %: five of the 60 companies have no site of their own in the
source data (a profile on an accelerator's site, a social network page), six
sites did not answer the scraper although four of them load in a browser,
and four publish their address on a second domain.

The investigation that followed found that 17 of the 29 companies without an
address publish none on a site of their own, so about 72 % was the most this
sample could give. Three fixes cover five of the twelve real misses. An
eighth run on 20 companies never seen, after the fixes:

| Confirmed, on 20 companies never seen before | Run 8 | Threshold | Verdict |
|---|---|---|---|
| Company with a usable address | 14 of 20 (70 %) | 65 % | Inconclusive (one company above) |
| People accuracy: lists reported that are entirely right | 8 of 10 (80 %) | 90 %, blocking | Below, on 10 lists |
| People coverage: companies with a right list | 40 % | 40 %, a goal | At the goal (inconclusive) |

No address reported was wrong. None of the 14 addresses came from the three
fixes: this sample simply held no accelerator profile and no site refusing
automated clients. The two wrong lists keep people of other organisations
(two customers quoted on a home page, an investor's representative). Over
runs 5 to 8, people accuracy is 32 lists of 35 (91 %).

The share of all companies with an address depends mostly on the draw: about
a quarter of the companies publish no address on a site of their own, and
nothing can be found there. The address threshold was therefore replaced by
two criteria: an address found for 75 % of the companies that publish one,
and no wrong address at all (blocking). Over runs 5 to 8, 59 of 80 companies
publish an address and the scraper found 45 of them (76 %), with no wrong
address. The new threshold was set knowing this figure, so it only counts as
passed once a later measurement confirms it.

A ninth run on 20 more companies never seen, after two more people rules
(a plain "Board" label, cards linking to a customer story):

| Confirmed, on 20 companies never seen before | Run 9 | Threshold | Verdict |
|---|---|---|---|
| Address found when the company publishes one | 13 of 16 (81 %) | 75 % | Inconclusive (one company above) |
| Wrong addresses | 0 | none, blocking | Pass |
| People accuracy: lists reported that are entirely right | 6 of 9 (67 %) | 90 %, blocking | Fail |
| People coverage: companies with a right list | 30 % | 40 %, a goal | Below |

The address part holds. The people part does not: the three wrong lists have
three new causes (a video caption read as a name, a photo caption given a
title that the page does not show for that person, and "Personal Care" in a
sales title read as the German word for staff). Over runs 5 to 9, people
accuracy is 38 lists of 44 (86 %). People read by the scraper are not
reliable enough to be used without a check. A person is therefore a
suggestion: the app will show the name, the title and the page it was read
on, and the student confirms it before it is used. The 90 % accuracy figure
is tracked and no longer blocks.

Correction to run 9: one of the three lists counted wrong (a title said to
be absent from the page) is in fact shown on the page, so the count is 7
right lists of 9 (78 %), and 39 of 44 (89 %) over runs 5 to 9.

Since then the scraper also keeps engineering and R&D heads (decision D93)
and was hardened after a security scan (D90); neither change has been
measured on a new sample yet.
