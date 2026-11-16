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

    SIZES = {"small": "Small (pre-seed, seed)", "medium": "Medium (Series A)",
             "large": "Large (Series B and later)"}

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
                              months=months, page=page_number)
        now = app.state.now()
        rows, total = store.companies(filters, request.state.user_id, now)
        records = store.mail_records()
        items = [dict(company=c, round=round_text(c), contact=contact_kind(c.id),
                      last_slot=rules.last_slot(c.id, records, now)) for c in rows]
        base = [("q", filters.query)] + [("country", c) for c in countries] + \
               [("sector", s) for s in sectors] + [("size", s) for s in filters.sizes] + \
               [("months", str(months))]
        pages = max((total + 49) // 50, 1)
        link = lambda n: "/companies?" + urlencode(base + [("page", str(n))])
        return page(request, "companies.html", items=items, total=total, filters=filters,
                    countries=COUNTRIES, sectors=store.sectors(), sizes=SIZES,
                    page_number=page_number, pages=pages,
                    previous=link(page_number - 1) if page_number > 1 else None,
                    next_page=link(page_number + 1) if page_number < pages else None)

    @app.get("/companies/{company_id}")
    async def company_page(request: Request, company_id: str):
        if (gate := signed_in(request)):
            return gate
        company = store.company(company_id)
        if company is None:
            return Response("Not found", status_code=404)
        return page(request, "company.html", company=company)
