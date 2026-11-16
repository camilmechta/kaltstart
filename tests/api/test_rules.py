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
