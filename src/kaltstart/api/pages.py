"""The pages behind sign-in: companies, company, mails, profile."""

from fastapi import FastAPI, Request


def register(app: FastAPI) -> None:
    page, signed_in = app.state.page, app.state.signed_in

    @app.get("/companies")
    async def companies(request: Request):
        if (gate := signed_in(request)):
            return gate
        return page(request, "companies.html")
