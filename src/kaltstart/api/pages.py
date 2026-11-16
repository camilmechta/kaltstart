"""The pages behind sign-in: companies, company, mails, profile."""

from fastapi import FastAPI, Request


def register(app: FastAPI) -> None:
    page, signed_in = app.state.page, app.state.signed_in

    @app.get("/companies")
    async def companies(request: Request):
        if (gate := signed_in(request)):
            return gate
        return page(request, "companies.html")

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
