import pytest
from kaltstart.contacts.titles import CATEGORIES, ROLE_TO_CATEGORY, Title, classify_title


@pytest.mark.parametrize("text,categories,level", [
    ("Co-Founder & CEO", ("leadership",), "head"),
    ("Founder - CEO/CTO", ("leadership",), "head"),
    ("Chief Executive Officer", ("leadership",), "head"),
    ("Managing Director", ("leadership",), "head"),
    ("President & CEO", ("leadership",), "head"),
    ("CTO", ("leadership",), "head"),
    ("Chief Financial Officer", ("leadership",), "head"),
    ("Geschäftsführerin", ("leadership",), "head"),
    ("Mitgründer und CTO", ("leadership",), "head"),
    ("Directrice générale", ("leadership",), "head"),
    ("Cofondateur", ("leadership",), "head"),
    ("Head of Product", ("product",), "head"),
    ("VP Product", ("product",), "head"),
    ("Chief Product Officer", ("product",), "head"),
    ("Product Lead", ("product",), "head"),
    ("Product Manager", ("product",), "manager"),
    ("Senior Product Manager", ("product",), "manager"),
    ("Leiter Produktmanagement", ("product",), "head"),
    ("VP Marketing", ("growth",), "head"),
    ("CMO", ("growth",), "head"),
    ("Head of Growth", ("growth",), "head"),
    ("Marketing Manager", ("growth",), "manager"),
    ("Head of Data & Analytics", ("data",), "head"),
    ("Chief Data Officer", ("data",), "head"),
    ("Head of Operations", ("operations",), "head"),
    ("Responsable des opérations", ("operations",), "head"),
    ("Operations Manager", ("operations",), "manager"),
    ("Head of Business Development", ("sales",), "head"),
    ("Leiterin Vertrieb", ("sales",), "head"),
    ("Chief Revenue Officer", ("sales",), "head"),
    ("Sales Director", ("sales",), "head"),
    ("Chief People Officer", ("recruiting",), "head"),
    ("Head of People & Culture", ("recruiting",), "head"),
    ("Talent Acquisition Lead", ("recruiting",), "head"),
    ("HR Manager", ("recruiting",), "manager"),
    ("Responsable ressources humaines", ("recruiting",), "head"),
    # Several categories (Review Focus 1); the level is the highest one.
    ("Co-Founder & Head of Product", ("leadership", "product"), "head"),
    ("Product Marketing Manager", ("product", "growth"), "manager"),
    ("Board Member & Co-Founder", ("leadership",), "head"),
    ("Co-Founder, Advisor & ETH Professor", ("leadership",), "head"),
])

def test_titles_kept(text, categories, level):
    assert classify_title(text) == Title(categories, level)


@pytest.mark.parametrize("text", [
    # Review Focus 2: looks like a kept title, is not.
    "Account Manager", "Project Manager", "Office Manager", "Product Owner",
    "Customer Success Manager", "Head of Engineering", "Engineering Manager",
    "Founder Associate", "Head of CEO Office", "Founders Associate",
    # No head or manager title.
    "Software Engineer", "Product Designer", "Data Scientist", "Sales Representative",
    "Marketing Intern", "Working Student Marketing", "Werkstudent Vertrieb",
    # Not the company's own leaders.
    "Board Member", "Advisor", "Investor", "Chairman of the Board",
    # Not held, or held for someone else.
    "Former CEO", "Ex-CEO", "Assistant to the CEO", "Personal Assistant to the Founder & CEO",
    # Not a title at all.
    "", "Anna Muster", "Our team", "About us",
])

def test_titles_not_kept(text):
    assert classify_title(text) is None


def test_constants():
    assert CATEGORIES == ("leadership", "product", "growth", "data", "operations",
                          "sales", "recruiting")
    assert ROLE_TO_CATEGORY == {"product": "product", "growth": "growth", "data": "data",
                                "ops": "operations", "bd": "sales"}


# Found by the review before the first run on real sites.
@pytest.mark.parametrize("text,categories,level", [
    # German compounds and the usual legal-notice label.
    ("Marketingleiter", ("growth",), "head"),
    ("Personalleiterin", ("recruiting",), "head"),
    ("Betriebsleiter", ("operations",), "head"),
    ("Vertriebsleiter", ("sales",), "head"),
    ("Geschäftsführung", ("leadership",), "head"),
    ("Geschäftsführender Gesellschafter", ("leadership",), "head"),
    # Recruiters are the people to write to at a larger company.
    ("Head of Recruitment", ("recruiting",), "head"),
    ("Recruitment Manager", ("recruiting",), "manager"),
    ("Recruiter", ("recruiting",), "manager"),
    ("Responsable RH", ("recruiting",), "head"),
    ("Partnership Manager", ("sales",), "manager"),
    # A past job mentioned after the present one does not cancel it.
    ("Founder, ex-McKinsey", ("leadership",), "head"),
    ("Founder (ex Google)", ("leadership",), "head"),
    ("Co-founder and former CEO", ("leadership",), "head"),
    ("Head of Sales, formerly Otherco", ("sales",), "head"),
    # A qualifier does not hide the function.
    ("VP Sales EMEA", ("sales",), "head"),
    ("Head of Marketing & Communications", ("growth",), "head"),
    ("Head of Global Sales", ("sales",), "head"),
    ("Director of Product Management", ("product",), "head"),
    # A leader who also does an individual contributor's job stays a leader.
    ("Co-Founder & Lead Engineer", ("leadership",), "head"),
])
def test_more_titles_kept(text, categories, level):
    assert classify_title(text) == Title(categories, level)


@pytest.mark.parametrize("text", [
    # "Lead" or "Head" next to a function word does not make an individual contributor a head.
    "Lead Data Scientist", "Lead Product Designer", "Senior Lead Data Engineer",
    "Lead Sales Engineer", "Lead Software Engineer, Data Platform", "Lead UX Designer Product",
    "Marketing Lead Generation Specialist", "Data Analyst", "People Operations Specialist",
    # Manufacturing is not product.
    "Produktionsleiter", "Leiter Produktion", "Produktionsmanager",
    # The board is not the management.
    "President of the Board", "Board President", "Präsident des Verwaltungsrats",
    "Verwaltungsratspräsident", "Member of the Advisory Board",
    # Project and team leads are not heads of a function.
    "Projektleiter Marketing", "Teamleiter Vertrieb",
    # Not the function it looks like.
    "Head of Data Protection", "Data Protection Lead", "Datenschutzbeauftragter",
    "Head of Personal Training",
    # Not held any more, or not a job.
    "CEO (until 2023)", "Founder in Residence", "Formerly Head of Product",
])
def test_more_titles_not_kept(text):
    assert classify_title(text) is None
