from app.subscription.page import render_subscription_page, fmt_bytes


def _render(**kw):
    base = dict(nonce="n", brand="B", username="ali", state="active", used=1024 ** 3, limit=2 * 1024 ** 3,
                expire=2_000_000_000, created=1_700_000_000, now=1_900_000_000, online_at=None, service="gold",
                reset="no_reset", on_hold_days=None, links=[], sub_url="https://x.io/sub/T", qr_svg="")
    base.update(kw)
    return render_subscription_page(**base)


def test_page_escapes_untrusted_values():
    link = {"type": "vless", "name": "<script>alert(1)</script>", "server": "a.io", "port": 443, "raw": 'vless://x"><img>'}
    html = _render(links=[link])
    assert "<script>alert(1)" not in html and "<img>" not in html


def test_page_states_and_unlimited():
    assert "منقضی شده" in _render(state="expired", links=[])
    assert "∞" in _render(limit=None)
    assert fmt_bytes(None) == "نامحدود"
