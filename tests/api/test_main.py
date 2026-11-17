from kaltstart.api.__main__ import main
from kaltstart.api.auth import FakeAuth
from kaltstart.api.store import InMemoryAppStore


def test_dev_mode_serves_the_seeded_app_with_fake_accounts(capsys):
    served = {}
    assert main(["--dev"], serve=lambda app, host, port: served.update(app=app, host=host, port=port)) == 0
    app = served["app"]
    assert isinstance(app.state.auth, FakeAuth) and isinstance(app.state.store, InMemoryAppStore)
    assert (served["host"], served["port"]) == ("127.0.0.1", 8000)
    out = capsys.readouterr().out
    assert "http://127.0.0.1:8000" in out and "invitation code: dev" in out


def test_without_dev_the_environment_is_required(monkeypatch, capsys):
    for name in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_ANON_KEY", "SESSION_SECRET",
                 "REMOVAL_CONTACT"):
        monkeypatch.delenv(name, raising=False)
    assert main([], serve=lambda *a: None) == 1
    assert "must be set" in capsys.readouterr().err
