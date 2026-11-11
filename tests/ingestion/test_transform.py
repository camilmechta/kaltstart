import json, pathlib
from kaltstart.ingestion.transform import transform_round, transform_company_details

FIX = pathlib.Path(__file__).parents[1] / "fixtures" / "techeu"

def _round(**overrides):
    raw = json.loads((FIX / "rounds_page1.json").read_text())["data"][0]
    raw.update(overrides)
    return raw

def test_transform_round_maps_all_fields():
    raw = _round()
    company, rnd = transform_round(raw)
    assert company == {
        "id": raw["company"]["id"], "name": raw["company"]["name"],
        "country": "Switzerland", "city_raw": raw["company"]["city"],
        "city": "Lausanne", "region": None,
        "sectors": raw["company"]["sectors"],
        "techeu_url": raw["company"]["pageUrl"]}
    assert rnd["id"] == raw["id"]
    assert rnd["company_id"] == raw["company"]["id"]
    assert rnd["date"] == raw["date"]
    assert rnd["amount_eur"] == raw["amountEur"]
    assert rnd["size_category"] == "small"
    assert rnd["source_url"] == raw["pageUrl"]
    assert rnd["source_domain"] == raw["source"]["domain"]
    assert all(name == name.strip() for name in rnd["investors"])

def test_missing_amount_city_and_currency_become_none():
    raw = _round(amountEur=None, amountNative=None, currency="", fx=None)
    raw["company"] = {**raw["company"], "city": None, "sectors": None}
    company, rnd = transform_round(raw)
    assert (company["city"], company["region"], company["sectors"]) == (None, None, [])
    assert (rnd["amount_eur"], rnd["currency"]) == (None, None)

def test_missing_source_and_investors():
    company, rnd = transform_round(_round(source=None, investors=None))
    assert rnd["source_domain"] is None and rnd["investors"] == []

def test_company_details():
    raw = json.loads((FIX / "company.json").read_text())
    assert transform_company_details(raw) == {
        "website": "https://www.lightframe.tech",
        "description": raw["description"], "founded": raw["founded"]}

def test_company_details_with_bad_website_and_blank_description():
    assert transform_company_details(
        {"website": "n/a", "description": "  ", "founded": None}
    ) == {"website": None, "description": None, "founded": None}

def test_empty_string_amounts_become_none():
    company, rnd = transform_round(_round(amountEur="", amountNative="", stage=None))
    assert (rnd["amount_eur"], rnd["amount_native"]) == (None, None)
    assert rnd["size_category"] == "small"

def test_company_details_empty_founded_becomes_none():
    assert transform_company_details({"founded": ""})["founded"] is None
