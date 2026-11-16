"""Invented inputs for the mail generator tests."""

from datetime import date

from kaltstart.mailgen.models import Company, Contact, Example, Round, Student


def student(**changes) -> Student:
    values = dict(
        id="s1", first_name="Lea", last_name="Beispiel", programme="Business Innovation",
        languages=("en", "de"), role="growth", request="internship",
        start_date=date(2027, 4, 1), duration_months=3, workload_percent=None,
        link="https://example.com/lea",
        examples=(Example("I grew a student newsletter from 0 to 4000 readers in one year.",
                          "Ich habe einen Studierenden-Newsletter in einem Jahr auf 4000 Leser gebracht."),),
        chosen_example=0)
    values.update(changes)
    return Student(**values)


def company(**changes) -> Company:
    values = dict(id="c1", name="Example Robotics", country="Germany", city="Berlin", region=None)
    values.update(changes)
    return Company(**values)


def round_(**changes) -> Round:
    values = dict(stage="Series A", amount_eur=8_000_000, amount_native=None, currency=None,
                  investors=("Example Ventures", "Other Capital"), size_category="medium")
    values.update(changes)
    return Round(**values)


def contact(**changes) -> Contact:
    values = dict(address="anna@example.de", address_type="personal", person_name="Anna Muster")
    values.update(changes)
    return Contact(**values)
