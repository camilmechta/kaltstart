"""The Render Blueprint (owner's choice of host, 2026-11-17): a Starter
instance in Frankfurt since D107, so the site never sleeps, deploys only when
the checks pass, and no secret in the file."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def blueprint():
    return yaml.safe_load((ROOT / "render.yaml").read_text())


def test_one_always_on_docker_web_service_in_frankfurt():
    services = blueprint()["services"]
    assert len(services) == 1
    web = services[0]
    assert (web["type"], web["runtime"], web["plan"], web["region"]) == (
        "web", "docker", "starter", "frankfurt")       # D107: never asleep
    assert web["branch"] == "main" and web["autoDeployTrigger"] == "checksPass"
    assert web["healthCheckPath"] == "/about"


def test_secrets_are_asked_in_render_never_written_here():
    env = {e["key"]: e for e in blueprint()["services"][0]["envVars"]}
    for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "REMOVAL_CONTACT"):
        assert env[key] == {"key": key, "sync": False}, key
    assert env["SESSION_SECRET"] == {"key": "SESSION_SECRET", "generateValue": True}
    assert env["PROXY_HOPS"]["value"] == "3"   # client, Cloudflare, Render (D83)
    for entry in env.values():
        assert "value" not in entry or entry["key"] == "PROXY_HOPS"
