import pytest

from kaltstart.contacts.measurement import (
    CHECK_VALUES, RESULT_COLUMNS, check_problems, read_results, summarise,
    verdict, write_results)
from kaltstart.contacts.models import (
    CompanyResult, FoundEmail, FoundPerson, ProposedContact)


def result(i, with_email=True, with_founder=True, size="small", failure=None):
    emails = (FoundEmail(f"anna{i}@example{i}.ch", "personal",
                         f"https://example{i}.ch/team"),) if with_email else ()
    category = ("leadership", "product", "recruiting")[i % 3]
    founders = (FoundPerson(f"Anna Muster{i}", "Founder", (category,), "head",
                            f"https://example{i}.ch/team"),) if with_founder else ()
    contact = ProposedContact(emails[0].address, founders[0].name if founders else None,
                              "high") if emails else None
    return CompanyResult(f"c{i}", f"Example Robotics {i}", f"https://example{i}.ch",
                         size, (f"https://example{i}.ch/",), emails, founders, contact,
                         None if with_email else (failure or "no_address"))


def test_constants():
    assert RESULT_COLUMNS == (
        "company_id", "name", "website", "size_category", "pages_fetched", "emails",
        "people", "contact_address", "contact_person", "confidence", "failure",
        "email_check", "people_check", "notes")
    assert CHECK_VALUES == ("confirmed", "wrong", "missed", "none_exists")


def test_write_then_read_round_trip(tmp_path):
    path = tmp_path / "sub" / "results.csv"
    write_results([result(1), result(2, with_email=False, with_founder=False)], path)
    rows = read_results(path)
    assert tuple(rows[0].keys()) == RESULT_COLUMNS
    assert rows[0]["emails"] == "anna1@example1.ch|personal|https://example1.ch/team"
    assert rows[0]["people"] == "Anna Muster1|Founder|product|head|https://example1.ch/team"
    assert rows[0]["pages_fetched"] == "1"
    assert (rows[0]["contact_address"], rows[0]["contact_person"], rows[0]["confidence"]) == (
        "anna1@example1.ch", "Anna Muster1", "high")
    assert rows[0]["failure"] == ""
    assert rows[1]["failure"] == "no_address"
    assert (rows[1]["emails"], rows[1]["contact_address"]) == ("", "")
    for row in rows:
        assert (row["email_check"], row["people_check"], row["notes"]) == ("", "", "")


@pytest.mark.parametrize("threshold,counts", [
    (0.7, {12: "fail", 13: "inconclusive", 14: "inconclusive", 15: "inconclusive", 16: "pass"}),
    (0.4, {6: "fail", 7: "inconclusive", 8: "inconclusive", 9: "inconclusive", 10: "pass"}),
])
def test_verdict(threshold, counts):
    for count, expected in counts.items():
        assert verdict(count, 20, threshold) == expected


def verified_rows(tmp_path):
    """20 rows: 16 addresses reported (15 confirmed, 1 wrong), 2 missed, 2 none;
    9 founders reported (8 confirmed, 1 wrong), 3 missed, 8 none."""
    results = []
    for i in range(20):
        size = ("small", "medium", "large")[i % 3]
        failure = ("no_address", "little_text", "unreachable", "contact_form_only")[i % 4]
        results.append(result(i, with_email=i < 16, with_founder=i < 9, size=size,
                              failure=failure))
    path = tmp_path / "results.csv"
    write_results(results, path)
    rows = read_results(path)
    for i, row in enumerate(rows):
        row["email_check"] = ("confirmed" if i < 15 else "wrong" if i == 15
                              else "missed" if i < 18 else "none_exists")
        row["people_check"] = ("confirmed" if i < 8 else "wrong" if i == 8
                                else "missed" if i < 12 else "none_exists")
    return rows


def test_summarise_rates_and_mistakes(tmp_path):
    text = summarise(verified_rows(tmp_path))
    assert text.startswith("# Phase 2 measurement\n")
    for line in (
        "Companies: 20",
        "Usable contact: reported 16/20 (80%), confirmed 15/20 (75%)",
        "People, accuracy: 8/9 lists right (89%)",
        "People, coverage: 8/20 (40%)",
        "wrong address: 1", "missed address: 2",
        "wrong people list: 1", "missed people: 3",
        "leadership: 3", "product: 3", "recruiting: 3", "growth: 0", "data: 0",
        "operations: 0", "sales: 0",
        "robots_forbidden: 0", "unreachable: 1", "little_text: 1",
        "other_domain_only: 0", "contact_form_only: 1", "no_address: 1",
        "Usable contact (threshold 65%): pass",
        "People accuracy (threshold 90%, blocking): inconclusive",
        "People coverage (threshold 40%, goal): inconclusive",
    ):
        assert line in text, line
    # Confidence by size category: 16 contacts proposed, all "high" here.
    assert "| small | 6 | 0 | 0 | 1 |" in text
    assert "| medium | 5 | 0 | 0 | 2 |" in text
    assert "| large | 5 | 0 | 0 | 1 |" in text


def test_summarise_contains_no_personal_data(tmp_path):
    rows = verified_rows(tmp_path)
    text = summarise(rows)
    for row in rows:
        assert row["name"] not in text
        assert row["website"] not in text
    assert "Anna" not in text and "Muster" not in text
    assert "@" not in text


def test_thresholds():
    from kaltstart.contacts.measurement import (
        ACCURACY_THRESHOLD, CONTACT_THRESHOLD, COVERAGE_THRESHOLD)
    assert (CONTACT_THRESHOLD, ACCURACY_THRESHOLD, COVERAGE_THRESHOLD) == (0.65, 0.9, 0.4)


def test_check_problems(tmp_path):
    rows = verified_rows(tmp_path)
    assert check_problems(rows) == []
    rows[0]["email_check"] = ""
    rows[1]["people_check"] = "maybe"
    rows[2]["email_check"] = "missed"          # but an address was reported
    rows[19]["email_check"] = "confirmed"      # but nothing was reported
    problems = check_problems(rows)
    assert [p.split(":")[0] for p in problems] == ["c0", "c1", "c2", "c19"]


def test_summarise_with_no_people_reported(tmp_path):
    rows = verified_rows(tmp_path)
    for row in rows:
        row["people"] = ""
        row["people_check"] = "none_exists"
    text = summarise(rows)
    assert "People, accuracy: 0/0 lists right" in text
    assert "People accuracy (threshold 90%, blocking): fail" in text
    assert "People, coverage: 0/20 (0%)" in text


def test_check_problems_rejects_old_results_files():
    old = [{"company_id": "c1", "emails": "", "founders": "", "email_check": "none_exists",
            "founder_check": "none_exists"}]
    problems = check_problems(old)
    assert len(problems) == 1
    assert "people" in problems[0]
