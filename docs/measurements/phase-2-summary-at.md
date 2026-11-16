# Phase 2 measurement

Companies: 20

## Rates

- Usable contact: reported 15/20 (75%), confirmed 15/20 (75%)
- Address published by the company: 18/20 (90%)
- Address found when one is published: 15/18 (83%)
- People, accuracy: 9/10 lists right (90%)
- People, coverage: 9/20 (45%)

## Scraper mistakes found by the verification

- wrong address: 0
- missed address: 3
- wrong people list: 1
- missed people: 5

## Failure causes (companies without a usable contact)

- robots_forbidden: 0
- unreachable: 3
- little_text: 0
- other_domain_only: 0
- contact_form_only: 1
- no_address: 0
- not_own_site: 1

## Companies with a person reported, by category

- leadership: 9
- product: 1
- growth: 0
- data: 0
- operations: 0
- sales: 1
- recruiting: 1

## Proposed contacts by confidence and size category

| size | high | medium | low | none |
|---|---|---|---|---|
| small | 1 | 10 | 3 | 4 |
| medium | 0 | 0 | 1 | 0 |
| large | 0 | 0 | 0 | 1 |

## Verdict

Counted on confirmed results. Within one company (or one list, for accuracy) of a threshold, the result is inconclusive.

- Address found when one is published (threshold 75%): pass
- Wrong addresses (none allowed, blocking): pass
- People accuracy (threshold 90%, tracked): inconclusive
- People coverage (threshold 40%, goal): inconclusive
