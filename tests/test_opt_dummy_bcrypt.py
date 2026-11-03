from app.core import security


def test_burn_password_time_runs_a_bcrypt_check(monkeypatch):
    calls = []
    monkeypatch.setattr(security, "verify_password", lambda p, h: calls.append(h) or False)
    security.burn_password_time("x")
    assert len(calls) == 1 and calls[0].startswith("$2")
