"""Reading and checking the profile form. Errors name the field, in the
words the page uses."""

from datetime import date

from kaltstart.api.store import Profile, Showcase
from kaltstart.mailgen.models import (
    MAX_EXAMPLE_CHARS, MAX_EXAMPLE_WORDS, MAX_NAME_CHARS, MAX_PROGRAMME_CHARS, MAX_UNIVERSITY_CHARS, REQUESTS, ROLES)

COUNTRIES = ("Switzerland", "Germany", "Austria")
ROLE_LABELS = {"product": "Product", "growth": "Growth", "data": "Data",
               "operations": "Operations", "business_development": "Business development"}


def _text(form, name: str) -> str:
    return " ".join((form.get(name) or "").split())


def _int(form, name: str) -> int | None:
    try:
        value = int(form.get(name) or "")
    except ValueError:
        return None
    return value if value > 0 else None


def _showcase_error(text: str, label: str) -> str | None:
    if len(text) > MAX_EXAMPLE_CHARS or len(text.split()) > MAX_EXAMPLE_WORDS:
        return f"{label}: at most {MAX_EXAMPLE_WORDS} words and {MAX_EXAMPLE_CHARS} characters."
    return None


def parse_profile(form, student_id: str) -> tuple[Profile, list[Showcase], dict[str, str]]:
    errors: dict[str, str] = {}
    first, last, programme = _text(form, "first_name"), _text(form, "last_name"), _text(form, "programme")
    for name, value, label in (("first_name", first, "First name"), ("last_name", last, "Last name")):
        if not value:
            errors[name] = f"{label} is required."
        elif len(value) > MAX_NAME_CHARS:
            errors[name] = f"{label}: at most {MAX_NAME_CHARS} characters."
    level = form.get("degree_level") or ""
    if level not in ("bachelor", "master"):
        errors["degree_level"] = "Choose Bachelor or Master."
    university = _text(form, "university")
    if not university:
        errors["university"] = "University is required."
    elif len(university) > MAX_UNIVERSITY_CHARS:
        errors["university"] = f"University: at most {MAX_UNIVERSITY_CHARS} characters."
    if not programme:
        errors["programme"] = "Degree programme is required."
    elif len(programme) > MAX_PROGRAMME_CHARS:
        errors["programme"] = f"Degree programme: at most {MAX_PROGRAMME_CHARS} characters."

    german = form.get("lang_de") == "on"
    languages = ("en", "de") if german else ("en",)
    role = form.get("target_role") or ""
    if role not in ROLES:
        errors["target_role"] = "Target role: choose one of the five roles."
    request = form.get("request") or ""
    if request not in REQUESTS:
        errors["request"] = "Choose internship or part-time."
    try:
        start = date.fromisoformat(form.get("start_date") or "")
    except ValueError:
        start = None
        errors["start_date"] = "Start date is required."
    months, workload = _int(form, "duration_months"), _int(form, "workload_percent")
    if request == "internship" and not months:
        errors["duration_months"] = "Duration in months is required for an internship."
    if request == "part_time" and not (workload and workload <= 100):
        errors["workload_percent"] = "Workload in per cent is required for part-time work."
    link = (form.get("link") or "").strip() or None
    if link and (not link.startswith(("https://", "http://")) or " " in link):
        errors["link"] = "Link: a full address starting with https://."

    showcases: list[Showcase] = []
    for position in (1, 2):
        en, de = _text(form, f"showcase{position}_en"), _text(form, f"showcase{position}_de")
        label = f"Showcase sentence {position}"
        if position == 1 and not en:
            errors["showcase1_en"] = "Showcase sentence 1 is required, in English."
        for field, text, which in ((f"showcase{position}_en", en, label),
                                   (f"showcase{position}_de", de, f"{label}, German version")):
            if text and (problem := _showcase_error(text, which)):
                errors[field] = problem
        if german and en and not de:
            errors[f"showcase{position}_de"] = (f"{label}: add the German version, since you "
                                                "write in German.")
        if en or de:
            showcases.append(Showcase(position, en or None, (de or None) if german else None))

    profile = Profile(
        id=student_id, first_name=first, last_name=last, programme=programme,
        degree_level=level if level in ("bachelor", "master") else None, university=university,
        attach_cv=form.get("attach_cv") == "on",
        languages=languages, target_role=role if role in ROLES else None,
        request=request if request in REQUESTS else None, start_date=start,
        duration_months=months if request == "internship" else None,
        workload_percent=workload if request == "part_time" else None, link=link,
        preferred_countries=tuple(c for c in form.getlist("pref_country") if c in COUNTRIES),
        preferred_sectors=tuple(form.getlist("pref_sector")))
    return profile, showcases, errors


def missing_for_mail(profile: Profile | None, showcases: list[Showcase]) -> list[str]:
    """What the profile still lacks before a first mail, in the page's words."""
    if profile is None:
        return ["your profile"]
    missing = [label for value, label in (
        (profile.first_name, "first name"), (profile.last_name, "last name"),
        (profile.university, "university"), (profile.degree_level, "Bachelor or Master"),
        (profile.programme, "degree programme"), (profile.target_role, "target role"),
        (profile.request, "internship or part-time"), (profile.start_date, "start date"))
        if not value]
    if profile.request == "internship" and not profile.duration_months:
        missing.append("duration")
    if profile.request == "part_time" and not profile.workload_percent:
        missing.append("workload")
    if not any(s.position == 1 and s.text_en for s in showcases):
        missing.append("showcase sentence 1")
    return missing
