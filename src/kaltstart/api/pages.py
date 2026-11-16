"""The pages behind sign-in: companies, company, mails, profile."""

from fastapi import FastAPI, Request


def register(app: FastAPI) -> None:
    page, signed_in = app.state.page, app.state.signed_in


    from kaltstart.api.forms import COUNTRIES, ROLE_LABELS, parse_profile
    from kaltstart.api.store import Profile
    store, auth, redirect, form_of = app.state.store, app.state.auth, app.state.redirect, app.state.form_of

    def profile_page(request, profile, showcases, errors=None, status=200):
        by_position = {s.position: s for s in showcases}
        return page(request, "profile.html", status=status, profile=profile or Profile(id=""),
                    showcase=by_position, errors=errors or {}, countries=COUNTRIES,
                    sectors=store.sectors(), roles=ROLE_LABELS,
                    saved=request.query_params.get("saved") == "1")

    @app.get("/profile")
    async def profile(request: Request):
        if (gate := signed_in(request)):
            return gate
        student = request.state.user_id
        return profile_page(request, store.profile(student), store.showcases(student))

    @app.post("/profile")
    async def save_profile(request: Request):
        if (gate := signed_in(request)):
            return gate
        form = await form_of(request)
        profile, showcases, errors = parse_profile(form, request.state.user_id)
        if errors:
            return profile_page(request, profile, showcases, errors, status=400)
        store.save_profile(profile)
        store.save_showcases(profile.id, showcases)
        return redirect(request, "/profile?saved=1")

    @app.get("/profile/delete")
    async def delete_form(request: Request):
        if (gate := signed_in(request)):
            return gate
        return page(request, "delete.html")

    @app.post("/profile/delete")
    async def delete_account(request: Request):
        if (gate := signed_in(request)):
            return gate
        await form_of(request)
        student = request.state.user_id
        store.delete_student(student)
        auth.delete_user(student)
        request.state.session.pop("access", None)
        request.state.session.pop("refresh", None)
        return redirect(request, "/signin?deleted=1")

    from fastapi.responses import Response
    from kaltstart.api import rules

    ORDER = {"generated": 0, "copied": 1, "sent": 2, "human_reply": 3, "positive_reply": 4}
    LABELS = {"generated": "Generated", "copied": "Copied", "sent": "Sent",
              "human_reply": "Got a reply", "positive_reply": "Positive reply",
              "abandoned": "Abandoned", "presumed_sent": "Presumed sent"}

    def allowed(current: str, new: str) -> bool:
        if new == "abandoned":
            return current in ("generated", "copied")
        return current in ORDER and new in ORDER and ORDER[new] > ORDER[current]

    def names_of(mails):
        return {m.company_id: (c.name if (c := store.company(m.company_id)) else "A company")
                for m in mails}

    @app.get("/mails")
    async def my_mails(request: Request):
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
    async def one_mail(request: Request, mail_id: str):
        if (gate := signed_in(request)):
            return gate
        mail = store.mail(request.state.user_id, mail_id)
        if mail is None:
            return Response("Not found", status_code=404)
        shown = rules.shown_status(mail.record(), app.state.now())
        return page(request, "mail.html", mail=mail, shown=shown, labels=LABELS,
                    company_name=names_of([mail])[mail.company_id])

    @app.post("/mails/{mail_id}/status")
    async def change_status(request: Request, mail_id: str):
        if (gate := signed_in(request)):
            return gate
        form = await form_of(request)
        mail = store.mail(request.state.user_id, mail_id)
        if mail is None:
            return Response("Not found", status_code=404)
        new = form.get("status", "")
        if allowed(mail.status, new):
            store.set_status(request.state.user_id, mail_id, new, app.state.now())
        return redirect(request, form.get("back") or f"/mails/{mail_id}")

    @app.post("/mails/{mail_id}/copied")
    async def copied(request: Request, mail_id: str):
        if (gate := signed_in(request)):
            return gate
        await form_of(request)
        mail = store.mail(request.state.user_id, mail_id)
        if mail is None:
            return Response("Not found", status_code=404)
        if mail.status == "generated":
            store.set_status(request.state.user_id, mail_id, "copied", app.state.now())
        return Response(status_code=204)

    from urllib.parse import urlencode
    from kaltstart.api.store import ListFilters
    from kaltstart.mailgen.phrases import amount, round_name
    from kaltstart.mailgen.models import Round as MailRound

    # What a size category means for a student (parent spec 6.3).
    SIZE_INFO = {
        "small": ("Small", "pre-seed or seed, or under €7M",
                  "Usually a small team: founders read applications themselves."),
        "medium": ("Medium", "Series A, or €7M to €20M",
                   "A team is forming: heads of product, growth or sales start hiring."),
        "large": ("Large", "Series B and later, or over €20M",
                  "A structured company: a recruiter or the HR team handles applications."),
    }
    SIZES = {key: label for key, (label, _r, _m) in SIZE_INFO.items()}

    def contact_kind(company_id: str) -> str:
        if store.people(company_id):
            return "Person suggested"
        if any(e.type == "careers" for e in store.emails(company_id)):
            return "Careers address"
        return "General address"

    def round_text(c) -> str:
        r = MailRound(c.stage, c.amount_eur, c.amount_native, c.currency, c.investors,
                      c.size_category)
        money = amount(r, "en")
        name = round_name(c.stage, "en")
        return f"{money} {name}" if money else name[0].upper() + name[1:]

    @app.get("/companies")
    async def companies(request: Request):
        if (gate := signed_in(request)):
            return gate
        q = request.query_params
        profile = store.profile(request.state.user_id)
        first_visit = not q
        countries = tuple(q.getlist("country")) or (
            profile.preferred_countries if first_visit and profile else ())
        sectors = tuple(q.getlist("sector")) or (
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
        items = [dict(company=c, round=round_text(c), contact=contact_kind(c.id),
                      last_slot=rules.last_slot(c.id, records, now)) for c in rows]
        base = [("q", filters.query)] + [("country", c) for c in countries] + \
               [("sector", s) for s in sectors] + [("size", s) for s in filters.sizes] + \
               [("months", str(months))] + ([("person", "1")] if filters.with_person else [])
        pages = max((total + 49) // 50, 1)
        link = lambda n: "/companies?" + urlencode(base + [("page", str(n))])
        return page(request, "companies.html", items=items, total=total, filters=filters,
                    countries=COUNTRIES, sectors=store.sectors(), sizes=SIZES, size_info=SIZE_INFO,
                    page_number=page_number, pages=pages,
                    previous=link(page_number - 1) if page_number > 1 else None,
                    next_page=link(page_number + 1) if page_number < pages else None)

    from kaltstart.api import compose
    from kaltstart.api.forms import missing_for_mail
    from kaltstart.api.store import NewMail
    from kaltstart.mailgen.choices import suggested_style
    from kaltstart.mailgen.language import choose_language
    from kaltstart.mailgen import models as mg
    from kaltstart.mailgen.generator import generate
    from kaltstart.mailgen.models import MissingData, TooLong

    REFUSALS = {
        "company_full": "This company already has 3 mails this month, to protect its founders.",
        "student_pending": "You have 5 mails waiting for a status. Mark some as sent or "
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
                "first_name": "Your first name is too long.", "last_name": "Your last name is too long.",
                "body": "This mail would be too long: shorten your sentences."}

    def refusal_text(refused) -> str:
        text = REFUSALS[refused.reason]
        if refused.frees_on:
            from kaltstart.mailgen.phrases import long_date
            text += f" A slot frees on {long_date(refused.frees_on, 'en')}."
        return text

    def defaults(company, profile, people, emails):
        """The suggested person, style and language shown before any choice."""
        person = compose.suggested(company, people, profile)
        if person is not None:
            style = "direct"
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
                    why=compose.why(person, profile, company) if person else None)

    def compose_mail(request, company, form):
        """(recipient, mail) or (None, (message, link, status))."""
        student = request.state.user_id
        profile, showcases = store.profile(student), store.showcases(student)
        choice = form.get("choice") or ""
        if choice not in compose.CHOICES:
            return None, ("Choose who you write to (step 1).", None, 400)
        missing = missing_for_mail(profile, showcases)
        if missing:
            return None, ("Complete your profile first: " + ", ".join(missing) + ".",
                          "/profile", 400)
        try:
            index = int(form.get("person")) if form.get("person") not in (None, "") else None
        except ValueError:
            index = None
        try:
            recipient = compose.choose(company, store.people(company.id), store.emails(company.id),
                                       profile, choice, person_index=index,
                                       typed_name=form.get("typed_name"))
        except compose.NoAddress:
            return None, ("This company publishes no address for this choice. Choose someone "
                          "else or write to the team.", None, 400)
        except ValueError:
            return None, ("Choose who you write to (step 1).", None, 400)
        refused = rules.refusal(student, company.id, recipient.person_key,
                                store.mail_records(), app.state.now())
        if refused:
            return None, (refusal_text(refused), "/mails" if refused.reason != "company_full"
                          else None, 409)
        style = form.get("style") if form.get("style") in ("direct", "round", "formal") else "direct"
        language = form.get("language") if form.get("language") in ("en", "de") else "en"
        try:
            showcase = int(form.get("showcase") or 1)
        except ValueError:
            showcase = 1
        inputs = compose.to_mailgen(profile, showcases, company, recipient, showcase)
        try:
            mail = generate(*inputs, style=style, language=language,
                            company_line=form.get("company_line") or None)
        except MissingData as exc:
            words = [FIELD_WORDS.get(f, f) for f in exc.fields]
            return None, ("Missing for this mail: " + ", ".join(words) + ".", "/profile", 400)
        except TooLong as exc:
            return None, (TOO_LONG.get(exc.field, "A text is too long."), None, 400)
        return recipient, mail

    @app.get("/companies/{company_id}")
    async def company_page(request: Request, company_id: str):
        if (gate := signed_in(request)):
            return gate
        company = store.company(company_id)
        if company is None:
            return Response("Not found", status_code=404)
        return company_view(request, company)

    @app.post("/companies/{company_id}/preview")
    async def preview(request: Request, company_id: str):
        if (gate := signed_in(request)):
            return gate
        form = await form_of(request)
        company = store.company(company_id)
        if company is None:
            return Response("Not found", status_code=404)
        recipient, result = compose_mail(request, company, form)
        if recipient is None:
            message, link, status = result
            return company_view(request, company, form=form, error=message, error_link=link,
                                status=status)
        return company_view(request, company, form=form, preview=result, recipient=recipient)

    @app.post("/companies/{company_id}/keep")
    async def keep_mail(request: Request, company_id: str):
        if (gate := signed_in(request)):
            return gate
        form = await form_of(request)
        company = store.company(company_id)
        if company is None:
            return Response("Not found", status_code=404)
        recipient, result = compose_mail(request, company, form)
        if recipient is None:
            message, link, status = result
            return company_view(request, company, form=form, error=message, error_link=link,
                                status=status)
        mail = result
        kept = store.reserve(request.state.user_id, NewMail(
            company_id=company.id, round_id=company.round_id, address=recipient.address,
            address_type=recipient.address_type, person_name=recipient.person_name,
            person_key=recipient.person_key, person_choice=recipient.person_choice,
            person_source_url=recipient.person_source_url, style=mail.style,
            language=mail.language, company_line=(form.get("company_line") or None),
            used_company_line=mail.used_company_line, subject=mail.subject, body=mail.body),
            app.state.now())
        if not isinstance(kept, str):
            return company_view(request, company, form=form, error=refusal_text(kept),
                                error_link="/mails", status=409)
        return redirect(request, f"/mails/{kept}?kept=1")
