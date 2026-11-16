# Phase 2 measurement

Companies: 20

## Rates

- Usable contact: reported 18/20 (90%), confirmed 18/20 (90%)
- Address published by the company: 18/20 (90%)
- Address found when one is published: 18/18 (100%)
- People, accuracy: 10/13 lists right (77%)
- People, coverage: 10/20 (50%)

## Scraper mistakes found by the verification

- wrong address: 0
- missed address: 0
- wrong people list: 3
- missed people: 3

## Failure causes (companies without a usable contact)

- robots_forbidden: 0
- unreachable: 1
- little_text: 0
- other_domain_only: 1
- contact_form_only: 0
- no_address: 0
- not_own_site: 0

## Companies with a person reported, by category

- leadership: 12
- product: 5
- growth: 3
- data: 1
- operations: 0
- sales: 4
- recruiting: 2

## Proposed contacts by confidence and size category

| size | high | medium | low | none |
|---|---|---|---|---|
| small | 1 | 6 | 5 | 2 |
| medium | 0 | 3 | 1 | 0 |
| large | 0 | 0 | 2 | 0 |

## Verdict

Counted on confirmed results. Within one company (or one list, for accuracy) of a threshold, the result is inconclusive.

- Address found when one is published (threshold 75%): pass
- Wrong addresses (none allowed, blocking): pass
- People accuracy (threshold 90%, tracked): fail
- People coverage (threshold 40%, goal): pass
