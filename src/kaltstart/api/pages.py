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
