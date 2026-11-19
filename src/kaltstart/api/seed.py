"""Invented companies, people and rounds for `python -m kaltstart.api --dev`.

Everything here is made up: names, people, addresses on example domains.
Nothing comes from the database, so the app can be tried without any key."""

import random
from datetime import datetime, timedelta

from kaltstart.api.store import (
    CompanyRow, EmailRow, InMemoryAppStore, NewMail, PersonRow)

_COUNTRIES = (("Switzerland", "ch", ("Zurich", "Basel", "Lausanne", "Zug", "Bern")),
              ("Germany", "de", ("Berlin", "Munich", "Hamburg", "Cologne")),
              ("Austria", "at", ("Vienna", "Graz", "Linz")))
_SECTORS = ("Robotics", "Fintech", "Healthtech", "Cleantech", "Edtech", "Cybersecurity",
            "Agritech", "Mobility")
_STAGES = (("Pre-Seed", 800_000, "small"), ("Seed", 2_500_000, "small"),
           ("Series A", 9_000_000, "medium"), ("Series B", 30_000_000, "large"),
           ("Other", 5_000_000, "small"), ("Grant", 600_000, "small"))
_WORDS = ("Alpine", "Nova", "Lumen", "Vector", "Helio", "Brix", "Quanta", "Orbit", "Tidal",
          "Fable", "Kite", "Pixel", "Ember", "Atlas", "Zephyr", "Cobalt", "Juniper", "Meridian")
_KINDS = ("Labs", "Health", "Energy", "Robotics", "Pay", "Learn", "Secure", "Farm", "Motion")
_PEOPLE = (("Anna Muster", "Co-Founder & CEO", ("leadership",), "head"),
           ("Jonas Beispiel", "Head of Growth", ("growth",), "head"),
           ("Clara Vorlage", "Product Manager", ("product",), "manager"),
           ("Noah Entwurf", "Talent Acquisition Manager", ("recruiting",), "manager"),
           ("Lea Probe", "Head of Data", ("data",), "head"),
           ("Mia Muster", "VP Sales", ("sales",), "head"),
           ("Tim Muster", "Head of Engineering", ("engineering",), "head"),
           ("Eva Probe", "Head of R&D", ("rnd",), "head"))


def seeded_store(now: datetime, count: int = 36) -> InMemoryAppStore:
    rng = random.Random(2026)
    store = InMemoryAppStore(invitation="dev")
    for n in range(count):
        country, tld, cities = _COUNTRIES[n % 3]
        stage, amount, size = rng.choice(_STAGES)
        name = f"{_WORDS[n % len(_WORDS)]} {_KINDS[(n * 7 + n // len(_WORDS)) % len(_KINDS)]}"
        host = f"{name.lower().replace(' ', '')}.example.{tld}"
        row = CompanyRow(
            id=f"dev{n:02d}", name=name, country=country, city=rng.choice(cities),
            sector=rng.choice(_SECTORS), size_category=size, round_id=f"round{n:02d}",
            round_date=(now - timedelta(days=rng.randint(3, 340))).date(), stage=stage,
            amount_eur=amount if rng.random() > 0.15 else None, amount_native=None,
            currency=None, investors=tuple(rng.sample(("Example Ventures", "Sample Capital",
                                                      "Demo Partners", "Test Fund"), rng.randint(0, 3))),
            description=f"{name} builds {rng.choice(_SECTORS).lower()} products for European customers.",
            website=f"https://{host}", source_url="https://example.com/rounds")
        emails = [EmailRow(f"info@{host}", "generic", f"https://{host}/imprint")]
        if rng.random() > 0.5:
            emails.append(EmailRow(f"jobs@{host}", "careers", f"https://{host}/careers"))
        people = [PersonRow(name_, title, categories, level, f"https://{host}/team",
                            (now - timedelta(days=rng.randint(1, 25))).date())
                  for name_, title, categories, level in rng.sample(_PEOPLE, rng.randint(0, 3))]
        store.add_company(row, emails=emails, people=people)

    full = CompanyRow(id="full", name="Glacier Systems", country="Switzerland", city="Zurich",
                      sector="Robotics", size_category="medium", round_id="round-full",
                      round_date=(now - timedelta(days=12)).date(), stage="Series A",
                      amount_eur=12_000_000, amount_native=None, currency=None,
                      investors=("Example Ventures",), description="Glacier Systems builds robots.",
                      website="https://glacier.example.ch", source_url="https://example.com/rounds")
    store.add_company(full, emails=[EmailRow("info@glacier.example.ch", "generic",
                                             "https://glacier.example.ch/contact")], people=[])
    for student in ("seed-a", "seed-b", "seed-c"):
        store.reserve(student, NewMail(
            company_id="full", round_id="round-full", address="info@glacier.example.ch",
            address_type="generic", person_name=None, person_key=None, person_choice="team",
            person_source_url=None, style="direct", language="en", company_line=None,
            used_company_line=False, subject="Glacier Systems internship?", body="Hi team!"),
            now - timedelta(days=2))
    return store
