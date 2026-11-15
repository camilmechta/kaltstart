# Phase 2 measurement

Companies: 20

## Rates

- Usable contact: reported 13/20 (65%), confirmed 13/20 (65%)
- Address published by the company: 16/20 (80%)
- Address found when one is published: 13/16 (81%)
- People, accuracy: 7/9 lists right (78%)
- People, coverage: 7/20 (35%)

## Scraper mistakes found by the verification

- wrong address: 0
- missed address: 3
- wrong people list: 2
- missed people: 5

## Failure causes (companies without a usable contact)

- robots_forbidden: 0
- unreachable: 1
- little_text: 0
- other_domain_only: 0
- contact_form_only: 2
- no_address: 2
- not_own_site: 2

## Companies with a person reported, by category

- leadership: 8
- product: 3
- growth: 0
- data: 0
- operations: 1
- sales: 2
- recruiting: 1

## Proposed contacts by confidence and size category

| size | high | medium | low | none |
|---|---|---|---|---|
| small | 0 | 6 | 5 | 6 |
| medium | 0 | 0 | 2 | 0 |
| large | 0 | 0 | 0 | 1 |

## Verdict

Counted on confirmed results. Within one company (or one list, for accuracy) of a threshold, the result is inconclusive.

- Address found when one is published (threshold 75%): inconclusive
- Wrong addresses (none allowed, blocking): pass
- People accuracy (threshold 90%, tracked): fail
- People coverage (threshold 40%, goal): inconclusive
