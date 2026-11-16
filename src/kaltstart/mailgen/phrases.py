"""Every variable phrase of a mail, as finished text. The templates only
arrange these phrases; they never build a sentence from raw data."""

from datetime import date

from kaltstart.mailgen.models import Round, Student

MAX_INVESTOR_CHARS = 40

_NAMED_STAGES = ("Pre-Seed", "Seed", "Series A", "Series B", "Series C")
_STAGE_WORDS = {
    "Growth/Late": ("growth round", "Wachstumsrunde"),
    "Series D+": ("growth round", "Wachstumsrunde"),
    "Debt": ("financing", "Finanzierung"),
    "Grant": ("grant", "Förderung"),
}
_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}
_MONTHS = {
    "en": ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"),
    "de": ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
           "September", "Oktober", "November", "Dezember"),
}
_ROLE_NAMES = {
    "en": {"product": "Product", "growth": "Growth", "data": "Data",
           "operations": "Operations", "business_development": "Business development"},
    "de": {"product": "Produkt", "growth": "Growth", "data": "Data",
           "operations": "Operations", "business_development": "Business Development"},
}
# What the student would do in that function at a company that has just raised.
_ROLE_PARAGRAPHS = {
    ("en", "product"): "After a round, the product must keep pace. I would like to help turn "
                       "customer feedback into the next features.",
    ("en", "growth"): "New funding means ambitious targets. I would like to help test channels "
                      "fast and double down on what works.",
    ("en", "data"): "More users bring more data. I would like to help build the dashboards the "
                    "team needs to decide quickly.",
    ("en", "operations"): "Scaling puts pressure on every process. I would like to help find "
                          "bottlenecks and set up workflows that keep up.",
    ("en", "business_development"): "A new round opens doors to partners and markets. I would "
                                    "like to help research leads and prepare first conversations.",
    ("de", "product"): "Nach einer Runde muss das Produkt Schritt halten. Ich würde gerne helfen, "
                       "Kundenfeedback in die nächsten Features zu übersetzen.",
    ("de", "growth"): "Neues Kapital bedeutet ehrgeizige Ziele. Ich würde gerne helfen, Kanäle "
                      "schnell zu testen und das Wirksame auszubauen.",
    ("de", "data"): "Mehr Nutzer bringen mehr Daten. Ich würde gerne helfen, die Dashboards "
                    "aufzubauen, mit denen das Team schnell entscheidet.",
    ("de", "operations"): "Skalieren setzt jeden Prozess unter Druck. Ich würde gerne helfen, "
                          "Engpässe zu finden und Abläufe aufzusetzen, die mitwachsen.",
    ("de", "business_development"): "Eine neue Runde öffnet Türen zu Partnern und Märkten. Ich "
                                    "würde gerne helfen, Kontakte zu recherchieren und Gespräche vorzubereiten.",
}


def round_name(stage: str | None, language: str) -> str:
    """The round as a mail names it: "Series A", or a plain word when the
    stage is unknown or not a classic venture round."""
    if stage in _NAMED_STAGES:
        return stage
    en, de = _STAGE_WORDS.get(stage or "", ("funding round", "Finanzierungsrunde"))
    return en if language == "en" else de


def _millions(value: float) -> str:
    millions = value / 1_000_000
    rounded = round(millions, 1) if millions < 10 else round(millions)
    if rounded >= 10:
        rounded = round(rounded)
    return f"{rounded:g}"


def amount(round: Round, language: str) -> str | None:
    """"€8M" / "8 Mio. €"; the native amount when its currency is known."""
    if round.amount_native and round.currency:
        value, currency = round.amount_native, round.currency.upper()
    elif round.amount_eur:
        value, currency = round.amount_eur, "EUR"
    else:
        return None
    number = _millions(value)
    symbol = _SYMBOLS.get(currency)
    if language == "de":
        return f"{number.replace('.', ',')} Mio. {symbol or currency}"
    return f"{symbol}{number}M" if symbol else f"{currency} {number}M"


def investor_phrase(round: Round, language: str) -> str | None:
    """The first investor, never called the lead: the data does not say who led."""
    if not round.investors or len(round.investors[0]) > MAX_INVESTOR_CHARS:
        return None
    first = round.investors[0]
    if len(round.investors) == 1:
        return f"backed by {first}" if language == "en" else f"mit {first}"
    return (f"with {first} and others" if language == "en"
            else f"mit {first} und weiteren")


def role_name(role: str, language: str) -> str:
    return _ROLE_NAMES[language][role]


def role_paragraph(role: str, language: str, formal: bool) -> str:
    """What the student would do in that function. The paragraphs speak of
    the student and never address the reader, so they read right with "du"
    and with "Sie"; `formal` is kept for styles that may need it later."""
    return _ROLE_PARAGRAPHS[(language, role)]


def long_date(d: date, language: str) -> str:
    month = _MONTHS[language][d.month - 1]
    return f"{d.day} {month} {d.year}" if language == "en" else f"{d.day}. {month} {d.year}"


def request_phrase(student: Student, language: str) -> str:
    start = long_date(student.start_date, language)
    if student.request == "internship":
        months = student.duration_months
        if language == "en":
            return f"an internship from {start} for {months} month{'s' if months != 1 else ''}"
        return f"ein Praktikum ab {start} für {months} Monat{'e' if months != 1 else ''}"
    workload = student.workload_percent
    if language == "en":
        return f"part-time work ({workload} %) from {start}"
    return f"eine Teilzeitstelle ({workload} %) ab {start}"


def student_text(text: str) -> str:
    """The student's own words, unchanged but for spacing and a final stop."""
    text = " ".join(text.split())
    return text if text.endswith((".", "!", "?")) else text + "."
