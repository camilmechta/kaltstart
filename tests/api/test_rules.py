from datetime import date, datetime, timedelta, timezone

from kaltstart.api.rules import (
    CAP_DAYS, COMPANY_CAP, PENDING_LIMIT, PRESUMED_SENT_DAYS, REMINDER_HOURS, MailRecord,
    Refusal, last_slot, needs_reminder, pending_count, refusal, shown_status)

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def mail(n, student="s1", company="c1", person=None, status="generated", days=0.0):
    return MailRecord(f"m{n}", student, company, person, status, NOW - timedelta(days=days))


def test_constants():
    assert (COMPANY_CAP, CAP_DAYS, PENDING_LIMIT, PRESUMED_SENT_DAYS, REMINDER_HOURS) == (3, 30, 5, 7, 72)


def test_nothing_refused_on_an_empty_history():
    assert refusal("s1", "c1", "k", [], NOW) is None


def test_company_full_with_the_date_a_slot_frees():
    mails = [mail(1, "a", status="sent", days=20), mail(2, "b", days=2), mail(3, "c", days=1)]
    assert refusal("s1", "c1", None, mails, NOW) == Refusal("company_full", date(2026, 11, 26))


def test_the_30_day_boundary():
    old = [mail(1, "a", days=30), mail(2, "b"), mail(3, "c")]
    assert refusal("s1", "c1", None, old, NOW) is None
    young = [mail(1, "a", days=30 - 1 / 24 / 60), mail(2, "b"), mail(3, "c")]
    assert refusal("s1", "c1", None, young, NOW).reason == "company_full"


def test_abandoned_mails_count_for_nothing():
    mails = [mail(n, f"x{n}", status="abandoned") for n in range(5)]
    assert refusal("s1", "c1", None, mails, NOW) is None


def test_anonymised_mails_still_count_for_the_company():
    mails = [mail(n, None) for n in range(3)]
    assert refusal("s1", "c1", None, mails, NOW).reason == "company_full"


def test_student_pending_limit():
    mails = [mail(n, company=f"c{n + 10}") for n in range(5)]
    assert refusal("s1", "c1", None, mails, NOW) == Refusal("student_pending", None)


def test_a_presumed_sent_mail_counts_for_the_company_not_for_pending():
    mails = [mail(n, company=f"c{n + 10}", days=8) for n in range(5)]
    assert refusal("s1", "c1", None, mails, NOW) is None
    assert pending_count("s1", mails, NOW) == 0
    cap = [mail(n, f"x{n}", days=8) for n in range(3)]
    assert refusal("s1", "c1", None, cap, NOW).reason == "company_full"


def test_one_mail_per_company_and_per_person():
    assert refusal("s1", "c1", None, [mail(1, status="sent", days=40)], NOW).reason == "company_done"
    other_company = [mail(1, company="c9", person="k", status="sent")]
    assert refusal("s1", "c1", "k", other_company, NOW).reason == "person_done"
    assert refusal("s1", "c1", "k", [mail(1, company="c9", person="k", status="abandoned")], NOW) is None


def test_rules_are_checked_in_order():
    mails = [mail(1, "a"), mail(2, "b"), mail(3, "s1")]
    assert refusal("s1", "c1", None, mails, NOW).reason == "company_full"


def test_shown_status():
    assert shown_status(mail(1, days=8), NOW) == "presumed_sent"
    assert shown_status(mail(1, status="copied", days=6), NOW) == "copied"
    assert shown_status(mail(1, status="sent", days=30), NOW) == "sent"


def test_reminder_between_72_hours_and_7_days():
    assert not needs_reminder(mail(1, days=2.9), NOW)
    assert needs_reminder(mail(1, days=3), NOW)
    assert needs_reminder(mail(1, status="copied", days=6.9), NOW)
    assert not needs_reminder(mail(1, days=7), NOW)
    assert not needs_reminder(mail(1, status="sent", days=4), NOW)


def test_last_slot():
    assert last_slot("c1", [mail(1, "a"), mail(2, "b")], NOW)
    assert not last_slot("c1", [mail(1, "a")], NOW)


# --- sending limits (spec 2026-11-16-sending-limits-and-variation) ----------

from kaltstart.api.rules import LIMITS, places_left, variant_for  # noqa: E402


def kept(n, student=None, company="c1", round_id="r1", status="sent", days=0.0, copied=False):
    return MailRecord(f"k{n}", student or f"st{n}", company, None, status,
                      NOW - timedelta(days=days), round_id=round_id, copied=copied)


def test_the_limits_are_in_one_place():
    assert LIMITS.round_cap == {"small": 6, "medium": 9, "large": 15}
    assert (LIMITS.speed, LIMITS.speed_days, LIMITS.company_cap, LIMITS.cap_days,
            LIMITS.pending) == (10, 7, 3, 30, 5)


def test_the_round_cap_depends_on_the_size():
    six = [kept(n, days=40 + 31 * n) for n in range(6)]          # never 3 in 30 days
    assert refusal("s", "c1", None, six, NOW, round_id="r1", size="small").reason == "round_full"
    assert refusal("s", "c1", None, six, NOW, round_id="r1", size="medium") is None
    nine = [kept(n, days=40 + 31 * n) for n in range(9)]
    assert refusal("s", "c1", None, nine, NOW, round_id="r1", size="medium").reason == "round_full"
    assert refusal("s", "c1", None, nine, NOW, round_id="r1", size="large") is None


def test_a_new_round_starts_the_count_again():
    six = [kept(n, days=40 + 31 * n) for n in range(6)]
    assert refusal("s", "c1", None, six, NOW, round_id="r2", size="small") is None
    recent = [kept(n, round_id="r1", days=n) for n in range(3)]
    assert refusal("s", "c1", None, recent, NOW, round_id="r2", size="small").reason == "company_full"


def test_the_speed_limit_counts_abandoned_mails():
    ten = [kept(n, student="s", company=f"c{n}", days=6 - n * 0.5,
                status="abandoned" if n == 0 else "sent") for n in range(10)]
    refused = refusal("s", "new", None, ten, NOW, round_id="r9", size="small")
    assert refused == Refusal("student_speed", (NOW - timedelta(days=6) + timedelta(days=7)).date())
    later = [replace_days(m, 8) for m in ten]
    assert refusal("s", "new", None, later, NOW, round_id="r9", size="small") is None


def replace_days(m, days):
    from dataclasses import replace
    return replace(m, created_at=NOW - timedelta(days=days))


def test_a_copied_then_abandoned_mail_still_counts():
    copied = [kept(1, status="abandoned", copied=True, days=1), kept(2, days=1), kept(3, days=1)]
    assert refusal("s", "c1", None, copied, NOW, round_id="r1", size="small").reason == "company_full"
    clean = [kept(1, status="abandoned", copied=False, days=1), kept(2, days=1), kept(3, days=1)]
    assert refusal("s", "c1", None, clean, NOW, round_id="r1", size="small") is None


def test_places_left():
    assert places_left("c1", "r1", "small", [], NOW) == 3
    assert places_left("c1", "r1", "small", [kept(1, days=1), kept(2, days=2)], NOW) == 1
    five = [kept(n, days=40 + 20 * n) for n in range(5)]
    assert places_left("c1", "r1", "small", five, NOW) == 1
    assert places_left("c1", "r1", "small", five + [kept(9, days=200)], NOW) == 0


def test_variant_counts_every_mail_of_the_round():
    mails = [kept(1), kept(2), kept(3, status="abandoned"), kept(4, round_id="r2"),
             kept(5, company="c2")]
    assert variant_for("c1", "r1", mails) == 3
    assert variant_for("c1", "r3", mails) == 0
