"""The keep-awake workflow (D108): Render's free instance sleeps after 15
minutes without a visit, so GitHub opens a light page every 10 minutes."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
PATH = ROOT / ".github" / "workflows" / "keep-awake.yml"


def workflow():
    return yaml.safe_load(PATH.read_text())


def test_it_runs_every_ten_minutes_and_by_hand():
    triggers = workflow()[True]           # YAML reads the key "on" as True
    assert triggers["schedule"] == [{"cron": "*/10 * * * *"}]
    assert "workflow_dispatch" in triggers
    assert "push" not in triggers


def test_it_opens_only_the_light_about_page_of_the_site():
    text = PATH.read_text()
    urls = re.findall(r"https?://\S+", text)
    assert urls == ["https://kaltstart.onrender.com/about"]


def test_it_reads_only_and_needs_no_secret():
    text = PATH.read_text()
    assert workflow()["permissions"] == {"contents": "read"}
    assert "secrets." not in text and "checkout" not in text


def test_a_run_is_short_and_prints_nothing_of_the_page():
    job = next(iter(workflow()["jobs"].values()))
    assert job["timeout-minutes"] <= 5
    command = job["steps"][0]["run"]
    assert "--output /dev/null" in command and "--max-time" in command
