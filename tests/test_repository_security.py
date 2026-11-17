"""Protections of the repository itself (owner's request, 2026-11-17): alerts
on vulnerable libraries, a vulnerability check that never blocks the tests,
and GitHub actions pinned to exact commits."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_dependabot_watches_the_libraries_and_the_actions():
    config = (ROOT / ".github" / "dependabot.yml").read_text()
    assert 'package-ecosystem: "pip"' in config
    assert 'package-ecosystem: "github-actions"' in config
    assert "interval: \"weekly\"" in config


def test_the_vulnerability_check_runs_apart_from_the_tests():
    security = (WORKFLOWS / "security.yml").read_text()
    assert "pip-audit" in security and "requirements.txt" in security
    assert "schedule:" in security and "push:" in security
    assert "pip-audit" not in (WORKFLOWS / "tests.yml").read_text()
    for name in ("nightly.yml", "contacts.yml"):
        assert "pip-audit" not in (WORKFLOWS / name).read_text()


def test_every_action_is_pinned_to_a_commit():
    for path in WORKFLOWS.glob("*.yml"):
        for use in re.findall(r"uses:\s*(\S+)", path.read_text()):
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", use), (path.name, use)


def test_every_workflow_reads_only():
    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text()
        assert "permissions:\n  contents: read" in text, path.name
        assert "write" not in text.split("permissions:", 1)[1].split("\n\n", 1)[0], path.name


def test_the_image_installs_the_pinned_list():
    assert "requirements.txt" in (ROOT / "Dockerfile").read_text()
    lock = (ROOT / "requirements.txt").read_text()
    assert "fastapi==" in lock and "pytest" not in lock
