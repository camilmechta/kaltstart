"""Migration 0003 is applied by hand in the Supabase SQL editor: no test reaches
the database. These checks keep the SQL in step with the Python keys."""

import re
import sys
from pathlib import Path

SQL = (Path(__file__).parents[2] / "supabase" / "migrations" / "0003_contact_fixes.sql").read_text()

_ESCAPES = {"t": "\t", "n": "\n", "f": "\f", "r": "\r"}


def _space_class() -> set[str]:
    """The characters of the bracket expression used to clean names in SQL."""
    match = re.search(r"regexp_replace\(normalize\(p_name, NFC\),\s*'\[(.*?)\]\+'", SQL, re.S)
    assert match, "the name cleaning regular expression was not found"
    body, chars, items = match.group(1), set(), []
    i = 0
    while i < len(body):
        if body[i] == "\\" and body[i + 1] == "u":
            items.append(chr(int(body[i + 2:i + 6], 16)))
            i += 6
        elif body[i] == "\\":
            items.append(_ESCAPES[body[i + 1]])
            i += 2
        else:
            items.append(body[i])
            i += 1
    j = 0
    while j < len(items):
        if j + 2 < len(items) and items[j + 1] == "-":
            chars |= {chr(c) for c in range(ord(items[j]), ord(items[j + 2]) + 1)}
            j += 3
        else:
            chars.add(items[j])
            j += 1
    return chars


def test_sql_name_cleaning_knows_every_space_python_splits_on():
    python_spaces = {chr(c) for c in range(sys.maxunicode + 1) if chr(c).isspace()}
    assert python_spaces <= _space_class()


def test_sql_name_cleaning_treats_no_letter_as_a_space():
    assert not any(c.isalnum() for c in _space_class())


def test_new_columns_and_index():
    assert "alter table contact_exclusions add column address_key text;" in SQL
    assert "alter table contact_runs add column write_errors int not null default 0;" in SQL
    assert "drop index contact_exclusions_unique_idx;" in SQL
    assert ("on contact_exclusions (company_id, coalesce(person_key, ''), "
            "coalesce(address_key, ''));") in SQL


def test_keys_are_built_like_the_python_ones():
    # contact_key: company id, a line break, the value (exclusions.contact_key).
    assert "encode(sha256(convert_to(p_company_id || E'\\n' || p_value, 'UTF8')), 'hex')" in SQL
    for value in ("'last:' || v_last", "'whole:' || v_first",
                  "'whole:' || left(v_first, 1) || v_last"):
        assert value in SQL, value


def test_exclude_person_reports_what_it_did_and_stays_private():
    assert "drop function exclude_person(text, text);" in SQL
    assert "returns text language plpgsql security definer set search_path = public" in SQL
    assert "get diagnostics v_people = row_count;" in SQL
    for function in ("contact_normalise_name(text)", "contact_key(text, text)",
                     "exclude_person(p_company_id text, p_person_name text)"):
        assert f"revoke all on function {function} from public, anon, authenticated;" in SQL
