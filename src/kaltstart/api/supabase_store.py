"""The AppStore on Supabase (service key, server side only).

The company list is read in full and filtered in Python by `store.eligible`,
the same function the in-memory store uses: a few hundred companies, so a
few requests per page, and one place for the rules of spec 7.2."""

import os
import uuid
from datetime import date, datetime, timedelta
from typing import Callable, Sequence

from supabase import Client, create_client

from kaltstart.api.rules import LIMITS, MailRecord, Refusal
from kaltstart.contacts.names import clean_name
from kaltstart.api.store import (
    RECENT_ROUND_DAYS, STATUSES, CompanyRow, EmailRow, ListFilters, Mail, NewMail, PersonRow,
    Profile, Showcase, eligible, shown_people)

PAGE_SIZE = 1000
_PROFILE_FIELDS = ("first_name", "last_name", "programme", "degree_level", "attach_cv", "university", "languages",
                   "target_role", "request",
                   "start_date", "duration_months", "workload_percent", "link",
                   "preferred_countries", "preferred_sectors")
_MAIL_COLUMNS = ("id,student_id,company_id,round_id,address,address_type,person_name,person_key,"
                 "person_choice,person_source_url,style,language,company_line,used_company_line,"
                 "subject,body,status,created_at,copied_at,sent_at,human_reply_at,"
                 "positive_reply_at,abandoned_at,variant,size_category")


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, TypeError):
        return False
    return True


_COPIED = ("copied", "sent", "human_reply", "positive_reply")


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _d(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


class SupabaseAppStore:
    def __init__(self, client: Client,
                 now: Callable[[], datetime] = lambda: datetime.now().astimezone()) -> None:
        self._client, self._now = client, now

    @classmethod
    def from_env(cls) -> "SupabaseAppStore":
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        return cls(create_client(url, key))

    def _read_all(self, table: str, columns: str, order: tuple[str, ...],
                  narrow: Callable = lambda query: query) -> list[dict]:
        out: list[dict] = []
        while True:
            query = narrow(self._client.table(table).select(columns))
            for column in order:
                query = query.order(column)
            page = query.range(len(out), len(out) + PAGE_SIZE - 1).execute().data
            out.extend(page)
            if len(page) < PAGE_SIZE:
                return out

    # --- settings and students -----------------------------------------------
    def invitation_ok(self, code: str) -> bool:
        """Whether an unused single-use code matches (D86); nothing is used yet:
        the database uses the code when the account is created."""
        code = (code or "").strip()
        if not code:
            return False
        return self._client.rpc("invitation_code_ok", {"p_code": code}).execute().data is True

    def profile(self, student_id: str) -> Profile | None:
        rows = self._client.table("profiles").select("*").eq("id", student_id).execute().data
        if not rows:
            return None
        row = rows[0]
        return Profile(id=row["id"], first_name=row["first_name"], last_name=row["last_name"],
                       programme=row["programme"], degree_level=row.get("degree_level"),
                       university=row.get("university") or "",
                       attach_cv=row.get("attach_cv", True) is not False,
                       languages=tuple(row["languages"] or ()),
                       target_role=row["target_role"], request=row["request"],
                       start_date=_d(row["start_date"]), duration_months=row["duration_months"],
                       workload_percent=row["workload_percent"], link=row["link"],
                       preferred_countries=tuple(row["preferred_countries"] or ()),
                       preferred_sectors=tuple(row["preferred_sectors"] or ()))

    def save_profile(self, profile: Profile) -> None:
        row = {"id": profile.id, "updated_at": datetime.now().astimezone().isoformat()}
        for name in _PROFILE_FIELDS:
            value = getattr(profile, name)
            row[name] = (list(value) if isinstance(value, tuple)
                         else value.isoformat() if isinstance(value, date) else value)
        self._client.table("profiles").upsert(row).execute()

    def showcases(self, student_id: str) -> list[Showcase]:
        rows = (self._client.table("showcases").select("position,text_en,text_de")
                .eq("student_id", student_id).order("position").execute().data)
        return [Showcase(r["position"], r["text_en"], r["text_de"]) for r in rows]

    def save_showcases(self, student_id: str, showcases: list[Showcase]) -> None:
        self._client.table("showcases").delete().eq("student_id", student_id).execute()
        if showcases:
            self._client.table("showcases").insert(
                [{"student_id": student_id, "position": s.position, "text_en": s.text_en,
                  "text_de": s.text_de} for s in showcases]).execute()

    # --- companies -------------------------------------------------------------
    def _company_rows(self, now: datetime, company_id: str | None = None) -> list[CompanyRow]:
        since = (now - timedelta(days=RECENT_ROUND_DAYS)).date().isoformat()
        one = (lambda q: q.eq("company_id", company_id)) if company_id else (lambda q: q)
        rounds = self._read_all(
            "rounds", "id,company_id,date,stage,amount_eur,amount_native,currency,size_category,"
            "investors,source_url", ("id",), lambda q: one(q.gte("date", since)))
        latest: dict[str, dict] = {}
        for r in rounds:
            if r["company_id"] not in latest or r["date"] > latest[r["company_id"]]["date"]:
                latest[r["company_id"]] = r
        only = (lambda q: q.eq("id", company_id)) if company_id else (lambda q: q)
        companies = self._read_all("companies",
                                   "id,name,country,city,sectors,website,description", ("id",),
                                   only)
        rows = []
        for c in companies:
            r = latest.get(c["id"])
            if r is None:
                continue
            rows.append(CompanyRow(
                id=c["id"], name=c["name"], country=c["country"], city=c["city"],
                sector=(c["sectors"] or [None])[0], size_category=r["size_category"],
                round_id=r["id"], round_date=_d(r["date"]), stage=r["stage"],
                amount_eur=r["amount_eur"], amount_native=r["amount_native"],
                currency=r["currency"], investors=tuple(r["investors"] or ()),
                description=c["description"], website=c["website"],
                source_url=r["source_url"]))
        return rows

    def _with_address(self) -> set[str]:
        return {r["company_id"] for r in self._read_all(
            "contact_emails", "company_id", ("company_id", "address"))}

    def _excluded(self) -> set[str]:
        return {r["company_id"] for r in self._read_all(
            "contact_exclusions", "company_id,person_key,address_key", ("id",))
            if r["person_key"] is None and r["address_key"] is None}

    def companies(self, filters: ListFilters, student_id: str,
                  now: datetime) -> tuple[list[CompanyRow], int]:
        with_person = ({r["company_id"] for r in self._read_all(
            "contact_people", "company_id", ("company_id", "name"))}
            if filters.with_person else set())
        return eligible(self._company_rows(now), self._with_address(), self._excluded(),
                        self.mail_records(), filters, student_id, now, with_person)

    def sectors(self) -> list[str]:
        rows = self._read_all("companies", "id,sectors", ("id",))
        return sorted({(r["sectors"] or [None])[0] for r in rows} - {None})

    def company(self, company_id: str) -> CompanyRow | None:
        now = self._now()
        rows = self._company_rows(now, company_id)
        if not rows or company_id in self._excluded():
            return None
        if not self.emails(company_id):
            return None
        return rows[0]

    def people(self, company_id: str) -> list[PersonRow]:
        rows = (self._client.table("contact_people")
                .select("name,title,categories,level,source_url,read_at")
                .eq("company_id", company_id).order("name").execute().data)
        return shown_people([PersonRow(r["name"], r["title"], tuple(r["categories"] or ()),
                                       r["level"], r["source_url"], _d(r["read_at"]))
                             for r in rows])

    def emails(self, company_id: str) -> list[EmailRow]:
        rows = (self._client.table("contact_emails").select("address,type,source_url")
                .eq("company_id", company_id).order("address").execute().data)
        return [EmailRow(r["address"], r["type"], r["source_url"]) for r in rows]

    def contact_summary(self, company_ids: Sequence[str]) -> dict[str, tuple[int, bool]]:
        ids = list(company_ids)
        if not ids:
            return {}
        people = (self._client.table("contact_people").select("company_id,name")
                  .in_("company_id", ids).execute().data)
        people = [r for r in people if clean_name(r.get("name"))]
        careers = (self._client.table("contact_emails").select("company_id")
                   .in_("company_id", ids).eq("type", "careers").execute().data)
        counts = {c: 0 for c in ids}
        for row in people:
            counts[row["company_id"]] += 1
        with_careers = {row["company_id"] for row in careers}
        return {c: (counts[c], c in with_careers) for c in ids}

    # --- mails -----------------------------------------------------------------
    def mail_records(self) -> list[MailRecord]:
        rows = self._read_all("mails", "id,student_id,company_id,person_key,status,created_at,"
                                       "round_id,copied_at", ("id",))
        return [MailRecord(r["id"], r["student_id"], r["company_id"], r["person_key"],
                           r["status"], _dt(r["created_at"]), round_id=r.get("round_id"),
                           copied=bool(r.get("copied_at")) or r["status"] in _COPIED)
                for r in rows]

    def reserve(self, student_id: str, mail: NewMail, now: datetime) -> Refusal | str:
        row = {k: v for k, v in mail.__dict__.items() if k not in ("company_id", "person_key")}
        row["limits"] = LIMITS.as_json()          # one place for every limit (rules.LIMITS)
        result = self._client.rpc("reserve_mail", {
            "p_student_id": student_id, "p_company_id": mail.company_id,
            "p_person_key": mail.person_key, "p_row": row}).execute().data
        if result.get("ok"):
            return str(result["id"])
        return Refusal(result["reason"], _d(result.get("frees_on")))

    def _mail(self, row: dict) -> Mail:
        dates = {s: _dt(row.get(f"{s}_at")) for s in STATUSES if row.get(f"{s}_at")}
        return Mail(id=row["id"], student_id=row["student_id"], company_id=row["company_id"],
                    round_id=row["round_id"], address=row["address"],
                    address_type=row["address_type"], person_name=row["person_name"],
                    person_key=row["person_key"], person_choice=row["person_choice"],
                    person_source_url=row["person_source_url"], style=row["style"],
                    language=row["language"], company_line=row["company_line"],
                    used_company_line=row["used_company_line"], subject=row["subject"],
                    body=row["body"], status=row["status"], created_at=_dt(row["created_at"]),
                    status_dates=dates, variant=row.get("variant") or 0,
                    size_category=row.get("size_category"))

    def mails(self, student_id: str) -> list[Mail]:
        rows = (self._client.table("mails").select(_MAIL_COLUMNS).eq("student_id", student_id)
                .order("created_at", desc=True).execute().data)
        return [self._mail(r) for r in rows]

    def mail(self, student_id: str, mail_id: str) -> Mail | None:
        if not _is_uuid(mail_id):
            return None                 # PostgREST would fail on it: not found
        rows = (self._client.table("mails").select(_MAIL_COLUMNS).eq("id", mail_id)
                .eq("student_id", student_id).execute().data)
        return self._mail(rows[0]) if rows else None

    def set_status(self, student_id: str, mail_id: str, status: str, now: datetime) -> bool:
        if status not in STATUSES:
            return False
        rows = (self._client.table("mails")
                .update({"status": status, f"{status}_at": now.isoformat()})
                .eq("id", mail_id).eq("student_id", student_id).execute().data)
        return bool(rows)

    def delete_student(self, student_id: str) -> None:
        self._client.table("mails").update({
            "student_id": None, "subject": None, "body": None, "person_name": None,
            "person_source_url": None, "address": None, "company_line": None,
        }).eq("student_id", student_id).execute()
        self._client.table("showcases").delete().eq("student_id", student_id).execute()
        self._client.table("profiles").delete().eq("id", student_id).execute()
