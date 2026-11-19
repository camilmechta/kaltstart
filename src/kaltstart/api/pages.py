"""The pages behind sign-in: companies, company, mails, profile."""

import logging

from fastapi import Depends, FastAPI, Request
from starlette.datastructures import FormData

from kaltstart.api.session import safe_next

log = logging.getLogger("kaltstart.api")


def register(app: FastAPI) -> None:
    from kaltstart.api.app import error_page
    page, signed_in = app.state.page, app.state.signed_in

    from kaltstart.api.forms import COUNTRIES, ROLE_LABELS, missing_for_mail, parse_profile
    from kaltstart.api.store import Profile
    store, auth, redirect = app.state.store, app.state.auth, app.state.redirect
    posted_form = app.state.posted_form

    def profile_page(request, profile, showcases, errors=None, status=200):
        by_position = {s.position: s for s in showcases}
        return page(request, "profile.html", status=status, profile=profile or Profile(id=""),
                    showcase=by_position, errors=errors or {}, countries=COUNTRIES,
                    sectors=store.sectors(), roles=ROLE_LABELS,
                    saved=request.query_params.get("saved") == "1")

    @app.get("/profile")
    def profile(request: Request):
        if (gate := signed_in(request)):
            return gate
        student = request.state.user_id
        return profile_page(request, store.profile(student), store.showcases(student))

    @app.post("/profile")
    def save_profile(request: Request, form: FormData = Depends(posted_form)):
        if (gate := signed_in(request)):
            return gate
        profile, showcases, errors = parse_profile(form, request.state.user_id)
        if errors:
            return profile_page(request, profile, showcases, errors, status=400)
        try:
            store.save_profile(profile, showcases)
        except Exception as exc:
            log.error("profile save failed: %s", type(exc).__name__)
            return profile_page(request, profile, showcases,
                                {"_save": "Your profile could not be saved. Nothing was changed. "
                                          "Try again in a moment."}, status=503)
        return redirect(request, "/companies?saved=1")

    @app.get("/profile/delete")
    def delete_form(request: Request):
        if (gate := signed_in(request)):
            return gate
        return page(request, "delete.html")

    @app.post("/profile/delete")
    def delete_account(request: Request, form: FormData = Depends(posted_form)):
        if (gate := signed_in(request)):
            return gate
        student = request.state.user_id
        store.delete_student(student)
        auth.delete_user(student)
        request.state.session.pop("access", None)
        request.state.session.pop("refresh", None)
        return redirect(request, "/signin?deleted=1")

    from fastapi.responses import Response
    from kaltstart.api import rules

    ORDER = {"generated": 0, "copied": 1, "sent": 2, "human_reply": 3, "positive_reply": 4}
    LABELS = {"generated": "Kept", "copied": "Copied", "sent": "Sent",
              "human_reply": "Got a reply", "positive_reply": "Positive reply",
              "abandoned": "Abandoned", "presumed_sent": "Presumed sent"}

    def allowed(current: str, new: str) -> bool:
        if new == "abandoned":
            return current in ("generated", "copied")
        return current in ORDER and new in ORDER and ORDER[new] > ORDER[current]

    def names_of(mails):
        """One read for all the companies of these mails (D87)."""
        found = store.company_names([m.company_id for m in mails])
        return {m.company_id: found.get(m.company_id, "A company no longer listed")
                for m in mails}

    @app.get("/mails")
    def my_mails(request: Request):
        if (gate := signed_in(request)):
            return gate
        now = app.state.now()
        mails = store.mails(request.state.user_id)
        rows = [(m, rules.shown_status(m.record(), now)) for m in mails]
        reminders = [(m, (now - m.created_at).days) for m in mails
                     if rules.needs_reminder(m.record(), now)]
        return page(request, "mails.html", rows=rows, reminders=reminders, labels=LABELS,
                    companies=names_of(mails))

    @app.get("/mails/{mail_id}")
    def one_mail(request: Request, mail_id: str):
        if (gate := signed_in(request)):
            return gate
        mail = store.mail(request.state.user_id, mail_id)
        if mail is None:
            return error_page(404)
        shown = rules.shown_status(mail.record(), app.state.now())
        return page(request, "mail.html", mail=mail, shown=shown, labels=LABELS,
                    kept=request.query_params.get("kept") == "1",
                    company_name=names_of([mail])[mail.company_id],
                    attach_cv=bool((p := store.profile(request.state.user_id)) and p.attach_cv))

    @app.post("/mails/{mail_id}/status")
    def change_status(request: Request, mail_id: str, form: FormData = Depends(posted_form)):
        if (gate := signed_in(request)):
            return gate
        mail = store.mail(request.state.user_id, mail_id)
        if mail is None:
            return error_page(404)
        new = form.get("status", "")
        if allowed(mail.status, new):
            store.set_status(request.state.user_id, mail_id, new, app.state.now())
        back = form.get("back") or f"/mails/{mail_id}"
        return redirect(request, back if safe_next(back) == back else "/mails")

    @app.post("/mails/{mail_id}/copied")
    def copied(request: Request, mail_id: str, form: FormData = Depends(posted_form)):
        if (gate := signed_in(request)):
            return gate
        mail = store.mail(request.state.user_id, mail_id)
        if mail is None:
            return error_page(404)
        if mail.status == "generated" and not mail.redacted:
            store.set_status(request.state.user_id, mail_id, "copied", app.state.now())
        return Response(status_code=204)

    from urllib.parse import urlencode
    from kaltstart.api.store import ListFilters
    from kaltstart.mailgen.phrases import amount, round_name
    from kaltstart.mailgen.models import Round as MailRound

    # What a size category means for a student (parent spec 6.3).
    # (label, who reads applications, which rounds, one sentence for the
    # company page, why a student would aim at this size)
    SIZE_INFO = {
        "small": ("Small", "Founders", "Pre-seed or seed, under €7M",
                  "A small team: the founders read applications themselves.",
                  "Your mail goes straight to a founder: quick answers, real responsibility "
                  "from day one, but fewer formal internships."),
        "medium": ("Medium", "Team leads", "Series A, €7M to €20M",
                   "A team is forming: the heads of product, growth or sales hire.",
                   "Fresh money and new teams: plenty of projects, and you learn from the "
                   "head of your field."),
        "large": ("Large", "Recruiters", "Series B and later, over €20M",
                  "A structured company: a recruiter or the HR team reads applications.",
                  "An internship programme, mentoring and a known name on your CV, but "
                  "more candidates."),
    }
    SIZES = {key: info[0] for key, info in SIZE_INFO.items()}

    def contact_kind(summary: tuple[int, bool]) -> str:
        count, careers = summary
        if count:
            return f"{count} {'person' if count == 1 else 'people'} named"
        return "Careers address" if careers else "General address"

    def round_text(c) -> str:
        r = MailRound(c.stage, c.amount_eur, c.amount_native, c.currency, c.investors,
                      c.size_category)
        money = amount(r, "en")
        name = round_name(c.stage, "en")
        return f"{money} {name}" if money else name[0].upper() + name[1:]

    @app.get("/companies")
    def companies(request: Request):
        if (gate := signed_in(request)):
            return gate
        q = request.query_params
        profile = store.profile(request.state.user_id)
        # "saved" only says the profile was just saved: the preferences still apply.
        first_visit = not (set(q.keys()) - {"saved"})
        # "All countries" and "All sectors" arrive as empty values: no filter.
        countries = tuple(c for c in q.getlist("country") if c) or (
            profile.preferred_countries if first_visit and profile else ())
        sectors = tuple(c for c in q.getlist("sector") if c) or (
            profile.preferred_sectors if first_visit and profile else ())
        try:
            months = int(q.get("months", "12"))
        except ValueError:
            months = 12
        months = months if months in (3, 6, 12) else 12
        try:
            page_number = max(int(q.get("page", "1")), 1)
        except ValueError:
            page_number = 1
        filters = ListFilters(query=q.get("q", ""), countries=countries, sectors=sectors,
                              sizes=tuple(s for s in q.getlist("size") if s in SIZES),
                              months=months, page=page_number,
                              with_person=q.get("person") == "1")
        now = app.state.now()
        rows, total = store.companies(filters, request.state.user_id, now)
        records = store.mail_records()
        summary = store.contact_summary([c.id for c in rows])
        items = [dict(company=c, round=round_text(c), contact=contact_kind(summary[c.id]),
                      named=summary[c.id][0] > 0,
                      places_left=rules.places_left(c.id, c.round_id, c.size_category,
                                                    records, now)) for c in rows]
        student = request.state.user_id
        get_started = None
        if not any(m.student_id == student for m in records):
            get_started = {"profile_done": not missing_for_mail(profile, store.showcases(student))}
        base = [("q", filters.query)] + [("country", c) for c in countries] + \
               [("sector", s) for s in sectors] + [("size", s) for s in filters.sizes] + \
               [("months", str(months))] + ([("person", "1")] if filters.with_person else [])
        pages = max((total + 49) // 50, 1)
        link = lambda n: "/companies?" + urlencode(base + [("page", str(n))])
        return page(request, "companies.html", items=items, total=total, filters=filters,
                    countries=COUNTRIES, sectors=store.sectors(), sizes=SIZES, size_info=SIZE_INFO,
                    page_number=page_number, pages=pages,
                    previous=link(page_number - 1) if page_number > 1 else None,
                    next_page=link(page_number + 1) if page_number < pages else None,
                    get_started=get_started, saved=q.get("saved") == "1")

    from kaltstart.api import compose
    from kaltstart.api.forms import missing_for_mail
    from kaltstart.api.store import NewMail
    from kaltstart.mailgen.choices import suggested_style
    from kaltstart.mailgen.language import choose_language
    from kaltstart.mailgen import models as mg
    from kaltstart.mailgen.generator import generate
    from kaltstart.mailgen.models import MissingData, TooLong

    REFUSALS = {
        "company_full": f"This company already has {rules.LIMITS.company_cap} mails this month, "
                        "to protect its founders.",
        "round_full": "This company has received all the mails Kaltstart allows for its current "
                      "funding round. Others are waiting for you.",
        "student_speed": f"You kept {rules.LIMITS.speed} mails this week. You can keep a new one "
                         "on {date}.",
        "student_pending": f"You have {rules.LIMITS.pending} mails waiting for a status. Mark some as sent or "
                           "abandoned in My mails, then come back.",
        "company_done": "You already wrote to this company.",
        "person_done": "You already wrote to this person.",
    }
    FIELD_WORDS = {"first_name": "first name", "last_name": "last name",
                   "programme": "degree programme", "start_date": "start date",
                   "duration_months": "duration", "workload_percent": "workload",
                   "contact_address": "an address for this company",
                   "example": "a showcase sentence in the language of this mail"}
    TOO_LONG = {"company_line": "Your sentence about the company: 35 words at most.",
                "example": "Your showcase sentence is too long for a mail: 60 words at most.",
                "programme": "Your degree programme is too long: 70 characters at most.",
                "university": "Your university is too long: 30 characters at most.",
                "first_name": "Your first name is too long.", "last_name": "Your last name is too long.",
                "body": "This mail would be too long: shorten your sentences."}

    def refusal_text(refused) -> str:
        from kaltstart.mailgen.phrases import long_date
        text = REFUSALS[refused.reason]
        if "{date}" in text:
            return text.format(date=long_date(refused.frees_on, "en"))
        if refused.frees_on:
            text += f" A slot frees on {long_date(refused.frees_on, 'en')}."
        return text

    def defaults(company, profile, people, emails):
        """The suggested person, style and language shown before any choice."""
        person = compose.suggested(company, people, profile)
        if person is not None:
            # Direct suits founders and team leads; a recruiter gets the rounder style.
            style = "round" if "recruiting" in person.categories else "direct"
        else:
            shared = next((e for e in emails if e.type == "careers"), None) or \
                next((e for e in emails if e.type == "generic"), None)
            style = suggested_style(
                mg.Contact(shared.address if shared else None,
                           shared.type if shared else "generic", None),
                mg.Round(company.stage, company.amount_eur, company.amount_native,
                         company.currency, company.investors, company.size_category))
        language = "en"
        if profile:
            reader = mg.Student(profile.id, "", "", "", profile.languages, "growth",
                                "internship", None, None, None, None, ())
            language = choose_language(reader, mg.Company(company.id, company.name,
                                                          company.country, company.city, None))
        return person, style, language

    def suggested_destination(company, people, emails, profile, person):
        """Where the mail to the suggested person goes, or None."""
        if person is None:
            return None
        try:
            r = compose.choose(company, people, emails, profile, "suggested")
        except ValueError:
            return None
        return compose.where_it_goes(company.name, person.name, r.address_type)

    def company_view(request, company, *, form=None, preview=None, recipient=None, error=None,
                     error_link=None, status=200):
        student = request.state.user_id
        profile = store.profile(student)
        people, emails = store.people(company.id), store.emails(company.id)
        person, style, language = defaults(company, profile, people, emails)
        form = form or {}
        return page(request, "company.html", status=status, company=company,
                    round=round_text(company), suggested=person, people=people,
                    emails=emails, profile=profile, showcases=store.showcases(student),
                    style=form.get("style") or style, language=form.get("language") or language,
                    form=form, preview=preview, recipient=recipient, error=error,
                    error_link=error_link, size_info=SIZE_INFO[company.size_category],
                    why=compose.why(person, profile, company) if person else None,
                    goes_to=suggested_destination(company, people, emails, profile, person),
                    profile_missing=missing_for_mail(profile, store.showcases(student)),
                    places_left=rules.places_left(company.id, company.round_id,
                                                  company.size_category, store.mail_records(),
                                                  app.state.now()))

    def compose_mail(request, company, form):
        """(recipient, mail, k) or (None, (message, link, status), None); k is the
        number of mails kept before for this company and round (the variant)."""
        student = request.state.user_id
        profile, showcases = store.profile(student), store.showcases(student)
        missing = missing_for_mail(profile, showcases)
        if missing:
            return None, ("Complete your profile first: " + ", ".join(missing) + ".",
                          "/profile", 400)
        choice = form.get("choice") or ""
        if choice not in compose.CHOICES:
            return None, ("Choose who you write to (step 1).", None, 400)
        try:
            index = int(form.get("person")) if form.get("person") not in (None, "") else None
        except ValueError:
            index = None
        try:
            recipient = compose.choose(company, store.people(company.id), store.emails(company.id),
                                       profile, choice, person_index=index,
                                       typed_name=form.get("typed_name"),
                                       their_address=form.get("their_address"))
        except compose.BadAddress:
            return None, ("This address does not look right: check it, or leave the field "
                          "empty.", None, 400)
        except compose.NoAddress:
            return None, ("This company publishes no address for this choice. Choose someone "
                          "else or write to the team.", None, 400)
        except ValueError:
            return None, ("Choose who you write to (step 1).", None, 400)
        records = store.mail_records()
        refused = rules.refusal(student, company.id, recipient.person_key, records,
                                app.state.now(), round_id=company.round_id,
                                size=company.size_category)
        if refused:
            # A full company or round: the way out is another company, not My mails.
            return None, (refusal_text(refused), None if refused.reason in
                          ("company_full", "round_full") else "/mails", 409)
        style = form.get("style") if form.get("style") in ("direct", "round", "formal") else "direct"
        language = form.get("language") if form.get("language") in ("en", "de") else "en"
        try:
            showcase = int(form.get("showcase") or 1)
        except ValueError:
            showcase = 1
        inputs = compose.to_mailgen(profile, showcases, company, recipient, showcase)
        try:
            k = rules.variant_for(company.id, company.round_id, records)
            mail = generate(*inputs, style=style, language=language,
                            company_line=form.get("company_line") or None, variant=k)
        except MissingData as exc:
            words = [FIELD_WORDS.get(f, f) for f in exc.fields]
            return None, ("Missing for this mail: " + ", ".join(words) + ".", "/profile", 400)
        except TooLong as exc:
            return None, (TOO_LONG.get(exc.field, "A text is too long."), None, 400)
        return recipient, (mail, k)

    @app.get("/companies/{company_id}")
    def company_page(request: Request, company_id: str):
        if (gate := signed_in(request)):
            return gate
        company = store.company(company_id)
        if company is None:
            return error_page(404)
        return company_view(request, company)

    @app.post("/companies/{company_id}/preview")
    def preview(request: Request, company_id: str, form: FormData = Depends(posted_form)):
        if (gate := signed_in(request)):
            return gate
        company = store.company(company_id)
        if company is None:
            return error_page(404)
        recipient, result = compose_mail(request, company, form)
        if recipient is None:
            message, link, status = result
            return company_view(request, company, form=form, error=message, error_link=link,
                                status=status)
        return company_view(request, company, form=form, preview=result[0], recipient=recipient)

    @app.post("/companies/{company_id}/keep")
    def keep_mail(request: Request, company_id: str, form: FormData = Depends(posted_form)):
        if (gate := signed_in(request)):
            return gate
        company = store.company(company_id)
        if company is None:
            return error_page(404)
        recipient, result = compose_mail(request, company, form)
        if recipient is None:
            message, link, status = result
            return company_view(request, company, form=form, error=message, error_link=link,
                                status=status)
        mail, k = result
        kept = store.reserve(request.state.user_id, NewMail(
            company_id=company.id, round_id=company.round_id, address=recipient.address,
            address_type=recipient.address_type, person_name=recipient.person_name,
            person_key=recipient.person_key, person_choice=recipient.person_choice,
            person_source_url=recipient.person_source_url, style=mail.style,
            language=mail.language, company_line=(form.get("company_line") or None),
            used_company_line=mail.used_company_line, subject=mail.subject, body=mail.body,
            variant=k, size_category=company.size_category),
            app.state.now())
        if not isinstance(kept, str):
            return company_view(request, company, form=form, error=refusal_text(kept),
                                error_link="/mails", status=409)
        return redirect(request, f"/mails/{kept}?kept=1")
