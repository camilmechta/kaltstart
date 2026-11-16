"""The language of a mail: German for a German speaker writing to a
German-speaking company, English otherwise. The student can switch."""

from kaltstart.mailgen.models import Company, Student

# Swiss cantons where German is the main language, spelled as the ingestion
# stores them (English names). Bern is bilingual with a German majority.
_GERMAN_CANTONS = frozenset((
    "Aargau", "Appenzell Ausserrhoden", "Appenzell Innerrhoden", "Basel-Landschaft",
    "Basel-Stadt", "Bern", "Glarus", "Graubünden", "Lucerne", "Nidwalden", "Obwalden",
    "Schaffhausen", "Schwyz", "Solothurn", "St. Gallen", "Thurgau", "Uri", "Zug", "Zurich"))
# Main German-speaking Swiss towns, for companies whose canton is unknown.
_GERMAN_CITIES = frozenset((
    "Aarau", "Herisau", "Appenzell", "Liestal", "Basel", "Bern", "Glarus", "Chur", "Lucerne",
    "Stans", "Sarnen", "Schaffhausen", "Schwyz", "Solothurn", "St. Gallen", "Frauenfeld",
    "Altdorf", "Zug", "Zurich", "Winterthur", "Biel", "Baden", "Brig", "Davos", "Rapperswil",
    "Wil", "Olten", "Thun", "Kreuzlingen"))


def _german_speaking(company: Company) -> bool:
    if company.country in ("Germany", "Austria"):
        return True
    if company.country != "Switzerland":
        return False
    if company.region:
        return company.region in _GERMAN_CANTONS
    # Unknown canton and town: English, a smaller fault than a wrong German mail.
    return bool(company.city) and company.city in _GERMAN_CITIES


def choose_language(student: Student, company: Company) -> str:
    return "de" if "de" in student.languages and _german_speaking(company) else "en"
