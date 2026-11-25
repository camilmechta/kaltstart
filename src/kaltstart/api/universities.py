"""The universities offered in the profile (D113): the main ones of the three
countries Kaltstart covers. The value is the short name a mail uses (30
characters at most, D85); the label is the full name shown in the list."""

UNIVERSITIES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("Switzerland", (
        ("HSG", "University of St. Gallen (HSG)"),
        ("ETH Zurich", "ETH Zurich"),
        ("EPFL", "EPFL"),
        ("University of Zurich", "University of Zurich"),
        ("University of Basel", "University of Basel"),
        ("University of Bern", "University of Bern"),
        ("University of Geneva", "University of Geneva"),
        ("University of Lausanne", "University of Lausanne"),
        ("USI Lugano", "Università della Svizzera italiana (USI)"),
    )),
    ("Germany", (
        ("TUM", "Technical University of Munich (TUM)"),
        ("LMU Munich", "LMU Munich"),
        ("RWTH Aachen", "RWTH Aachen University"),
        ("KIT", "Karlsruhe Institute of Technology (KIT)"),
        ("Heidelberg University", "Heidelberg University"),
        ("HU Berlin", "Humboldt University of Berlin"),
        ("FU Berlin", "Free University of Berlin"),
        ("TU Berlin", "Technical University of Berlin"),
        ("University of Mannheim", "University of Mannheim"),
        ("WHU", "WHU – Otto Beisheim School of Management"),
        ("Frankfurt School", "Frankfurt School of Finance & Management"),
        ("University of Cologne", "University of Cologne"),
        ("Goethe University Frankfurt", "Goethe University Frankfurt"),
        ("TU Dresden", "TU Dresden"),
    )),
    ("Austria", (
        ("University of Vienna", "University of Vienna"),
        ("WU Vienna", "Vienna University of Economics and Business (WU)"),
        ("TU Wien", "TU Wien"),
        ("University of Innsbruck", "University of Innsbruck"),
        ("TU Graz", "Graz University of Technology"),
        ("JKU Linz", "Johannes Kepler University Linz"),
    )),
)

_VALUES = frozenset(value for _, unis in UNIVERSITIES for value, _ in unis)


def listed(university: str) -> bool:
    """True if this saved university is one of the list."""
    return university in _VALUES
