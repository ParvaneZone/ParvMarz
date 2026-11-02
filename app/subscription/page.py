"""Customer-facing subscription page (what a user sees when the sub link is opened in a browser).

Pure functions, no web-framework imports: easy to test. Everything that comes from outside
(usernames, remarks from panels, URLs) is HTML-escaped. Only inline CSS/JS, no external assets, so
it works on blocked/filtered networks.

Each template has its own *layout* (different markup and section order); colours/styling live in themes.py.
"""
import base64
import html
import math
from types import SimpleNamespace
from urllib.parse import quote

STATUS = {
    "active": ("فعال", "ok"),
    "expired": ("منقضی شده", "bad"),
    "limited": ("حجم تمام شده", "bad"),
    "disabled": ("غیرفعال", "mute"),
    "on_hold": ("در انتظار اولین اتصال", "warn"),
}
RESET = {"no_reset": "بدون ریست", "day": "روزانه", "week": "هفتگی", "month": "ماهانه", "year": "سالانه"}
PROTO = {"vless": "VLESS", "vmess": "VMess", "trojan": "Trojan", "ss": "Shadowsocks", "hysteria2": "Hysteria2"}
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
NO_CFG = '<p class="muted">در حال حاضر کانفیگی برای نمایش وجود ندارد.</p>'
STEPS = (
    '<ol class="steps"><li>یکی از برنامه‌ها را نصب کنید: <b>v2rayNG</b> (اندروید)، <b>Streisand</b> یا <b>Shadowrocket</b> (آیفون)، <b>Hiddify</b> (همه سیستم‌ها).</li>'
    '<li>روی دکمه‌ی همان برنامه در بالا بزنید، یا لینک اشتراک را کپی و در برنامه از بخش «افزودن اشتراک» وارد کنید.</li>'
    '<li>اشتراک را بروزرسانی کنید و یک کانفیگ را انتخاب و وصل شوید.</li></ol>')


def fa(value) -> str:
    return str(value).translate(_FA)


def fmt_bytes(value: int | None) -> str:
    if value is None:
        return "نامحدود"
    if value <= 0:
        return '<bdi dir="ltr">' + fa("0 B") + "</bdi>"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = min(int(math.log(value, 1024)), len(units) - 1)
    text = f"{value / 1024 ** i:.2f}" if i >= 1 else f"{value:.0f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return '<bdi dir="ltr">' + fa(f"{text} {units[i]}") + "</bdi>"


def e(value) -> str:
    return html.escape(str(value), quote=True)


def import_links(sub_url: str, name: str) -> list[tuple[str, str, str]]:
    """(group, label, deep link). Deep links open the app with the subscription pre-filled."""
    u = quote(sub_url, safe="")
    n = quote(name, safe="")
    b64 = base64.b64encode(sub_url.encode()).decode()
    return [
        ("اندروید", "v2rayNG", f"v2rayng://install-sub?url={u}&name={n}"),
        ("اندروید", "Hiddify", f"hiddify://import/{sub_url}#{n}"),
        ("آیفون / مک", "Streisand", f"streisand://import/{sub_url}"),
        ("آیفون / مک", "Shadowrocket", f"sub://{b64}#{n}"),
        ("همه سیستم‌ها", "sing-box", f"sing-box://import-remote-profile?url={u}#{n}"),
        ("ویندوز / مک", "Clash", f"clash://install-config?url={u}&name={n}"),
    ]


# ---------------------------------------------------------------- small shared pieces
def _proto_text(p: dict) -> str:
    proto = PROTO.get(p.get("type", ""), str(p.get("type", "")).upper())
    sec = p.get("security") or ("tls" if p.get("tls") else "none")
    parts = [proto, p.get("network") or "tcp"]
    if sec and sec != "none":
        parts.append(str(sec).upper())
    return " · ".join(str(x) for x in parts)


def _addr(p: dict) -> str:
    return e(p.get("server", "")) + ":" + e(p.get("port", ""))


def _link_card(p: dict) -> str:
    proto = PROTO.get(p.get("type", ""), str(p.get("type", "")).upper())
    sec = p.get("security") or ("tls" if p.get("tls") else "none")
    chips = [f'<span class="chip proto">{e(proto)}</span>', f'<span class="chip">{e(p.get("network") or "tcp")}</span>']
    if sec and sec != "none":
        chips.append(f'<span class="chip sec">{e(sec.upper())}</span>')
    if p.get("flow"):
        chips.append(f'<span class="chip">{e(p["flow"])}</span>')
    return (
        '<li class="cfg"><div class="cfg-main"><div class="cfg-name">' + e(p.get("name") or "—") + "</div>"
        '<div class="chips">' + "".join(chips) + "</div>"
        '<div class="cfg-addr ltr">' + _addr(p) + "</div></div>"
        '<button class="btn sm" data-copy="' + e(p.get("raw", "")) + '">کپی</button></li>'
    )


def _cfg_row(p: dict, i: int) -> str:
    """Terminal-style row."""
    return (
        '<li class="tm-row"><span class="tm-i">' + f"{i:02d}" + '</span><span class="tm-n">' + e(p.get("name") or "—") + "</span>"
        '<span class="tm-p">' + e(_proto_text(p)) + '</span><span class="tm-a ltr">' + _addr(p) + "</span>"
        '<button class="btn sm" data-copy="' + e(p.get("raw", "")) + '" type="button">copy</button></li>'
    )


def _cfg_leg(p: dict, i: int) -> str:
    """Ticket-itinerary line."""
    return (
        '<li class="tk-leg"><span class="tk-no">№ ' + f"{i:02d}" + '</span><div><b>' + e(p.get("name") or "—") + "</b>"
        '<small>' + e(_proto_text(p)) + '</small></div><span class="tk-addr">' + _addr(p) + "</span>"
        '<button class="btn sm" data-copy="' + e(p.get("raw", "")) + '" type="button">کپی</button></li>'
    )


def _cfgs(c, render, cls: str, empty: str = NO_CFG) -> str:
    if not c.links:
        return empty
    return f'<ul class="{cls}">' + "".join(render(p, i) for i, p in enumerate(c.links, 1)) + "</ul>"


def _date(ts, empty="—") -> str:
    return f'<span class="date" data-ts="{int(ts)}">—</span>' if ts else empty


def _kv(title: str, val: str, cls: str = "") -> str:
    return f'<div class="kv"><span class="k">{title}</span><span class="v{cls}">{val}</span></div>'


def _top(c) -> str:
    return (f'<div class="top"><div class="brand">{e(c.brand)}</div>'
            '<button class="btn sm" id="theme" type="button" aria-label="تم">🌓 تم</button></div>')


def _ring(c) -> str:
    return (
        '<div class="ring"><svg viewBox="0 0 120 120" aria-hidden="true"><circle class="tr" cx="60" cy="60" r="52"/>'
        f'<circle class="pg {c.ring_tone}" cx="60" cy="60" r="52" stroke-dasharray="{c.ring_c:.2f}" stroke-dashoffset="{c.ring_off:.2f}"/></svg>'
        f'<div class="mid"><b>{c.pct_txt}</b><span>{c.pct_sub}</span></div></div>')


def _stats(c, days: bool = True) -> str:
    out = (f'<div class="stat"><span class="k">مصرف‌شده</span><span class="v">{fmt_bytes(c.used)}</span></div>'
           f'<div class="stat"><span class="k">حجم کل</span><span class="v">{fmt_bytes(c.limit)}</span></div>'
           f'<div class="stat"><span class="k">باقی‌مانده</span><span class="v">{fmt_bytes(c.remaining)}</span></div>')
    if days:
        out += f'<div class="stat"><span class="k">{c.days_sub}</span><span class="v">{c.days_txt}</span></div>'
    return out


def _details(c) -> str:
    rows = [_kv("نام کاربری", e(c.username), " ltr"), _kv("وضعیت", e(c.label))]
    if c.service:
        rows.append(_kv("سرویس", e(c.service)))
    rows += [_kv("تاریخ شروع", _date(c.created)), _kv("تاریخ پایان", _date(c.expire, "نامحدود")),
             _kv("آخرین اتصال", _date(c.online_at, "هنوز متصل نشده")),
             _kv("بازنشانی حجم", e(RESET.get(c.reset, c.reset))), _kv("تعداد کانفیگ‌ها", fa(len(c.links)))]
    return "".join(rows)


def _sub_box(c) -> str:
    return (f'<div class="sublink"><code id="sub">{e(c.sub_url)}</code>'
            f'<button class="btn pri" data-copy="{e(c.sub_url)}" type="button">کپی لینک</button></div>'
            '<p class="muted" style="margin:10px 0 0;font-size:13px">این لینک شخصی شماست؛ آن را با کسی به اشتراک نگذارید.</p>')


def _link_section(c, title: str = "لینک اشتراک", sid: str = "") -> str:
    ident = f' id="{sid}"' if sid else ""
    return (f'<section class="card"{ident}><h2>{title}</h2>'
            f'<div class="two"><div>{_sub_box(c)}{c.imports_html}</div>{c.qr_block}</div></section>')


def _ascii_bar(pct: float, width: int = 28) -> str:
    n = round(width * max(0.0, min(100.0, pct)) / 100)
    return "█" * n + "░" * (width - n)


# ---------------------------------------------------------------- layouts (one per template)
def _layout_classic(c) -> str:
    hero = (f'<section class="card"><div class="hero">{_ring(c)}<div class="hero-info"><div class="uname">{e(c.username)}</div>'
            f'<span class="badge {c.tone}">{e(c.label)}</span>{c.time_bar}<div class="grid">{_stats(c)}</div></div></div></section>')
    return (_top(c) + c.alerts_html + hero
            + f'<section class="card"><h2>مشخصات اشتراک</h2>{_details(c)}</section>'
            + _link_section(c)
            + f'<section class="card"><h2>کانفیگ‌ها</h2>{_cfgs(c, lambda p, i: _link_card(p), "cfgs")}</section>'
            + f'<section class="card"><h2>راهنمای اتصال</h2>{STEPS}</section>'
            + f'<div class="foot">{e(c.brand)}</div>')


def _layout_sidebar(c) -> str:
    """Dashboard: sticky profile sidebar + nav, content column starts with stat tiles, then link, configs."""
    facts = (_kv("سرویس", e(c.service)) if c.service else "") + _kv("آخرین اتصال", _date(c.online_at, "هنوز متصل نشده"))
    side = (f'<aside class="sb-side"><div class="sb-profile">{_ring(c)}<div class="uname">{e(c.username)}</div>'
            f'<span class="badge {c.tone}">{e(c.label)}</span>{c.time_bar}<div class="sb-facts">{facts}</div></div>'
            '<nav class="sb-nav"><a href="#sb-link">🔗 لینک اشتراک</a><a href="#sb-cfg">⚙️ کانفیگ‌ها</a>'
            '<a href="#sb-info">📋 مشخصات</a><a href="#sb-guide">📖 راهنما</a></nav></aside>')
    main = (f'<main class="sb-main"><div class="sb-stats">{_stats(c)}</div>'
            + _link_section(c, sid="sb-link")
            + f'<section class="card" id="sb-cfg"><h2>کانفیگ‌ها</h2>{_cfgs(c, lambda p, i: _link_card(p), "cfgs")}</section>'
            + f'<section class="card" id="sb-info"><h2>مشخصات اشتراک</h2>{_details(c)}</section>'
            + f'<section class="card" id="sb-guide"><h2>راهنمای اتصال</h2>{STEPS}</section></main>')
    return _top(c) + c.alerts_html + f'<div class="sb-grid">{side}{main}</div><div class="foot">{e(c.brand)}</div>'


def _layout_bento(c) -> str:
    """Poster/bento grid: big name sticker, usage as vertical columns, tiles of different sizes."""
    if c.limit:
        heights = (100.0, max(c.pct, 2.0 if c.used else 0.0), 100.0 - c.pct)
        kinds = ("tot", c.ring_tone, "rem")
    else:
        heights = (100.0, 4.0 if c.used else 0.0, 100.0)
        kinds = ("inf", "ok", "inf")
    labels = (("حجم کل", c.limit), ("مصرف‌شده", c.used), ("باقی‌مانده", c.remaining))
    cols = "".join(
        f'<div class="col"><b class="col-v">{fmt_bytes(v)}</b><div class="col-bar"><i class="{k}" style="height:{h:.1f}%"></i></div>'
        f'<span class="col-k">{t}</span></div>' for (t, v), h, k in zip(labels, heights, kinds))
    tag = f'<span class="bn-tag">{e(c.service)}</span>' if c.service else ""
    head = f'<header class="bn-head"><div class="bn-name">{e(c.username)}</div><span class="badge {c.tone}">{e(c.label)}</span>{tag}</header>'
    tiles = (
        f'<section class="bn-tile bn-usage"><h2>مصرف</h2><div class="cols">{cols}</div></section>'
        f'<section class="bn-tile bn-ringt"><h2>سهم مصرف</h2>{_ring(c)}</section>'
        f'<section class="bn-tile bn-days"><h2>زمان</h2><div class="bn-big">{c.days_txt}</div><span class="k">{c.days_sub}</span>{c.time_bar}</section>'
        f'<section class="bn-tile bn-link"><h2>لینک اشتراک</h2><div class="two"><div>{_sub_box(c)}</div>{c.qr_block}</div></section>'
        f'<section class="bn-tile bn-apps"><h2>اتصال سریع</h2>{c.imports_html}</section>'
        f'<section class="bn-tile bn-info"><h2>مشخصات</h2>{_details(c)}</section>'
        f'<section class="bn-tile bn-cfg"><h2>کانفیگ‌ها</h2>{_cfgs(c, lambda p, i: _link_card(p), "cfgs")}</section>'
        f'<section class="bn-tile bn-guide"><h2>راهنما</h2>{STEPS}</section>')
    return _top(c) + c.alerts_html + head + f'<div class="bn-grid">{tiles}</div><div class="foot">{e(c.brand)}</div>'


def _layout_terminal(c) -> str:
    """Console windows: key=value status + ASCII meters, config listing first, details last."""
    def line(k: str, v: str) -> str:
        return f'<div class="tm-l"><span class="tm-k">{k}</span><span class="tm-eq">=</span><span class="tm-v">{v}</span></div>'

    def meter(name: str, pct: float, tone: str, txt: str) -> str:
        return (f'<div class="tm-meter" role="img" aria-label="{name} {txt}">{name:<6}[<span class="tm-fill {tone}">'
                f'{_ascii_bar(pct)}</span>] {txt}</div>')

    meters = meter("usage", c.pct if c.limit else 0, c.ring_tone, c.pct_txt)
    if c.time_pct is not None:
        t_tone = "bad" if c.time_pct >= 90 else "warn" if c.time_pct >= 70 else "ok"
        meters += meter("time", c.time_pct, t_tone, fa(f"{c.time_pct:.0f}") + "٪")
    status = ('<section class="card tm-win"><h2>cat status</h2>' + line("user", e(c.username))
              + line("state", f'<span class="badge {c.tone}">{e(c.label)}</span>') + line("used", fmt_bytes(c.used))
              + line("total", fmt_bytes(c.limit)) + line("left", fmt_bytes(c.remaining)) + line("ttl", c.days_txt)
              + meters + '</section>')
    cfgs = _cfgs(c, _cfg_row, "tm-list", '<p class="muted"># no configs</p>')
    return (_top(c) + c.alerts_html + status
            + f'<section class="card"><h2>ls configs/</h2>{cfgs}</section>'
            + _link_section(c, "echo $SUB_URL")
            + f'<section class="card"><h2>stat subscription</h2>{_details(c)}</section>'
            + f'<section class="card"><h2>man connect</h2>{STEPS}</section>'
            + f'<div class="foot">{e(c.brand)}</div>')


def _layout_ticket(c) -> str:
    """Boarding pass: landscape ticket (main + QR stub), usage as a ruler, configs as itinerary legs."""
    fields = [("وضعیت", f'<span class="badge {c.tone}">{e(c.label)}</span>'), ("سرویس", e(c.service) if c.service else "—"),
              ("بازنشانی", e(RESET.get(c.reset, c.reset))), ("آخرین اتصال", _date(c.online_at, "هنوز متصل نشده")),
              ("کانفیگ‌ها", fa(len(c.links)))]
    fields_html = "".join(f'<div class="tk-f"><span class="k">{k}</span><span class="v">{v}</span></div>' for k, v in fields)
    fill = c.pct if c.limit else 0
    ruler = (f'<div class="tk-usage"><div class="tk-usage-t"><span>مصرف</span><b>{c.pct_txt}</b></div>'
             f'<div class="tk-ruler"><i class="{c.ring_tone}" style="width:{fill:.1f}%"></i></div>'
             f'<div class="tk-scale"><span>{fa(0)}</span><span>{fmt_bytes(c.used)}</span><span>{fmt_bytes(c.limit)}</span></div>{c.time_bar}</div>')
    main = (f'<div class="tk-main"><div class="tk-eyebrow"><span>{e(c.brand)}</span><span>SUBSCRIPTION PASS</span></div>'
            f'<div class="tk-holder">{e(c.username)}</div>'
            f'<div class="tk-route"><div class="tk-pt"><small>شروع</small><b>{_date(c.created)}</b></div><div class="tk-mid"></div>'
            f'<div class="tk-pt"><small>پایان</small><b>{_date(c.expire, "نامحدود")}</b></div></div>'
            f'<div class="tk-fields">{fields_html}</div>{ruler}</div>')
    stub = (f'<div class="tk-stub"><div class="tk-days"><b>{c.days_txt}</b><small>{c.days_sub}</small></div>{c.qr_block}'
            f'<button class="btn pri" data-copy="{e(c.sub_url)}" type="button">کپی لینک</button><div class="tk-code" aria-hidden="true"></div></div>')
    return (_top(c) + c.alerts_html + f'<article class="tk-pass">{main}{stub}</article>'
            + f'<section class="card"><h2>مسیر اتصال · کانفیگ‌ها</h2>{_cfgs(c, _cfg_leg, "tk-legs")}</section>'
            + _link_section(c)
            + f'<section class="card"><h2>راهنمای اتصال</h2>{STEPS}</section>'
            + f'<div class="foot">{e(c.brand)}</div>')


LAYOUTS = {
    "classic": _layout_classic,
    "sunset": _layout_sidebar,
    "aurora": _layout_bento,
    "midnight": _layout_terminal,
    "paper": _layout_ticket,
}


def render_subscription_page(*, nonce: str, brand: str, username: str, state: str, used: int, limit: int | None,
                             expire: int, created: int, now: int, online_at: int | None, service: str,
                             reset: str, on_hold_days: int | None, links: list[dict], sub_url: str,
                             qr_svg: str = "", template: str = "classic") -> str:
    from app.subscription.themes import THEMES, theme_css
    tpl = template if template in THEMES else "classic"
    label, tone = STATUS.get(state, (state, "mute"))
    pct = 0 if not limit else min(100.0, used * 100.0 / limit)
    remaining = None if limit is None else max(0, limit - used)
    days_left = None if not expire else (expire - now) / 86400
    total_days = None if not expire or not created or expire <= created else (expire - created) / 86400
    time_pct = None if days_left is None or not total_days else max(0.0, min(100.0, (1 - days_left / total_days) * 100))
    ring_c = 2 * math.pi * 52
    ring_off = ring_c * (1 - pct / 100.0)
    ring_tone = "bad" if pct >= 90 else "warn" if pct >= 70 else "ok"

    alerts = []
    if state == "expired":
        alerts.append(("bad", "زمان اشتراک شما تمام شده است. برای تمدید با پشتیبانی تماس بگیرید."))
    elif state == "limited":
        alerts.append(("bad", "حجم اشتراک شما تمام شده است. برای افزایش حجم یا تمدید با پشتیبانی تماس بگیرید."))
    elif state == "disabled":
        alerts.append(("warn", "اشتراک شما غیرفعال است."))
    elif state == "on_hold":
        d = f" ({fa(on_hold_days)} روز)" if on_hold_days else ""
        alerts.append(("warn", f"اشتراک شما پس از اولین اتصال شروع می‌شود{d}."))
    else:
        if days_left is not None and days_left <= 3:
            alerts.append(("warn", f"فقط {fa(max(0, math.ceil(days_left)))} روز تا پایان اشتراک باقی مانده است."))
        if limit and pct >= 90:
            alerts.append(("warn", "کمتر از ۱۰٪ حجم شما باقی مانده است."))
    alerts_html = "".join(f'<div class="alert {t}">{e(m)}</div>' for t, m in alerts)

    if days_left is None:
        days_txt, days_sub = "نامحدود", "بدون تاریخ انقضا"
    elif days_left <= 0:
        days_txt, days_sub = "۰ روز", "منقضی شده"
    else:
        days_txt, days_sub = f"{fa(math.ceil(days_left))} روز", "تا پایان اشتراک"

    imports = {}
    for group, name, href in import_links(sub_url, username):
        imports.setdefault(group, []).append(f'<a class="btn app" href="{e(href)}" rel="noopener">{e(name)}</a>')
    imports_html = "".join(
        f'<div class="grp"><span class="grp-t">{e(g)}</span><div class="grp-b">{"".join(items)}</div></div>'
        for g, items in imports.items())

    time_bar = ""
    if time_pct is not None:
        time_bar = (f'<div class="bar"><i class="{"bad" if time_pct >= 90 else "warn" if time_pct >= 70 else "ok"}" '
                    f'style="width:{time_pct:.1f}%"></i></div>')

    qr_block = f'<div class="qr" aria-label="QR">{qr_svg}</div>' if qr_svg else ""
    pct_txt = (fa(f"{pct:.0f}") + "٪") if limit else "∞"
    pct_sub = "مصرف‌شده" if limit else "حجم نامحدود"

    c = SimpleNamespace(
        brand=brand, username=username, label=label, tone=tone, alerts_html=alerts_html, pct=pct, pct_txt=pct_txt,
        pct_sub=pct_sub, limit=limit, used=used, remaining=remaining, days_txt=days_txt, days_sub=days_sub,
        time_pct=time_pct, time_bar=time_bar, ring_c=ring_c, ring_off=ring_off, ring_tone=ring_tone, service=service,
        reset=reset, created=created, expire=expire, online_at=online_at, links=links, sub_url=sub_url,
        qr_block=qr_block, imports_html=imports_html)
    inner = LAYOUTS.get(tpl, _layout_classic)(c)

    return f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow,noarchive"><meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="light dark">
<title>{e(username)} · {e(brand)}</title>
<style>
:root{{--bg:#f4f6fb;--card:#fff;--soft:#eef2f9;--bd:#dde4f0;--fg:#0f1b2d;--mu:#5b6b82;--ac:#2563eb;--ok:#16a34a;--warn:#d97706;--bad:#dc2626;--sh:0 8px 30px rgba(15,27,45,.07)}}
@media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#0b1220;--card:#121c2f;--soft:#0e1626;--bd:#23324d;--fg:#eaf0fb;--mu:#9fb0c9;--ac:#5b8def;--ok:#34d399;--warn:#fbbf24;--bad:#f87171;--sh:none}}}}
:root[data-theme=dark]{{--bg:#0b1220;--card:#121c2f;--soft:#0e1626;--bd:#23324d;--fg:#eaf0fb;--mu:#9fb0c9;--ac:#5b8def;--ok:#34d399;--warn:#fbbf24;--bad:#f87171;--sh:none}}
*{{box-sizing:border-box}}html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.8 Vazirmatn,Tahoma,"Segoe UI",system-ui,sans-serif}}
.wrap{{max-width:860px;margin:0 auto;padding:20px 16px 40px}}
.top{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}}
.brand{{font-weight:800;font-size:18px;letter-spacing:.2px}}
.card{{background:var(--card);border:1px solid var(--bd);border-radius:20px;padding:20px;box-shadow:var(--sh);margin-bottom:16px}}
.card h2{{margin:0 0 14px;font-size:16px}}
.hero{{display:flex;gap:22px;align-items:center;flex-wrap:wrap}}
.ring{{position:relative;width:150px;height:150px;flex:none}}
.ring svg{{width:150px;height:150px;transform:rotate(-90deg)}}
.ring circle{{fill:none;stroke-width:11;stroke-linecap:round}}
.ring .tr{{stroke:var(--soft)}}.ring .pg.ok{{stroke:var(--ok)}}.ring .pg.warn{{stroke:var(--warn)}}.ring .pg.bad{{stroke:var(--bad)}}
.ring .mid{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.3}}
.ring .mid b{{font-size:26px}}.ring .mid span{{font-size:12px;color:var(--mu)}}
.hero-info{{flex:1;min-width:220px}}
.uname{{font-size:22px;font-weight:800;word-break:break-all;direction:ltr;text-align:right}}
.badge{{display:inline-block;padding:2px 12px;border-radius:99px;font-size:13px;font-weight:700;margin-top:4px}}
.badge.ok{{background:color-mix(in srgb,var(--ok) 15%,transparent);color:var(--ok)}}.badge.bad{{background:color-mix(in srgb,var(--bad) 15%,transparent);color:var(--bad)}}
.badge.warn{{background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--warn)}}.badge.mute{{background:var(--soft);color:var(--mu)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:16px}}
.stat{{background:var(--soft);border-radius:14px;padding:12px 14px}}.stat .k{{display:block;font-size:12px;color:var(--mu)}}.stat .v{{font-size:17px;font-weight:700}}
.bar{{height:8px;background:var(--soft);border-radius:99px;overflow:hidden;margin-top:12px}}.bar i{{display:block;height:100%;border-radius:99px}}
.bar i.ok{{background:var(--ok)}}.bar i.warn{{background:var(--warn)}}.bar i.bad{{background:var(--bad)}}
.alert{{padding:11px 14px;border-radius:14px;margin-bottom:12px;font-weight:600;font-size:14px}}
.alert.bad{{background:color-mix(in srgb,var(--bad) 13%,transparent);color:var(--bad)}}.alert.warn{{background:color-mix(in srgb,var(--warn) 15%,transparent);color:var(--warn)}}
.kv{{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px dashed var(--bd)}}.kv:last-child{{border:0}}
.k{{color:var(--mu)}}.v{{font-weight:600;text-align:left}}
.ltr{{direction:ltr;text-align:left;word-break:break-all}}
.muted{{color:var(--mu)}}
.btn{{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:42px;padding:0 16px;border:1px solid var(--bd);border-radius:12px;background:var(--card);color:var(--fg);font:inherit;font-weight:700;cursor:pointer;text-decoration:none}}
.btn.pri{{background:var(--ac);border-color:var(--ac);color:#fff}}.btn.sm{{min-height:36px;padding:0 12px;font-size:13px}}.btn:active{{transform:scale(.98)}}
.btn:focus-visible,a:focus-visible{{outline:2px solid var(--ac);outline-offset:2px}}
.sublink{{display:flex;gap:8px;align-items:stretch;flex-wrap:wrap}}
.sublink code{{flex:1;min-width:200px;direction:ltr;text-align:left;background:var(--soft);border:1px solid var(--bd);border-radius:12px;padding:9px 12px;font:12.5px/1.6 ui-monospace,Consolas,monospace;word-break:break-all;user-select:all}}
.two{{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}}.two>div:first-child{{flex:1;min-width:240px}}
.qr{{background:#fff;padding:10px;border-radius:14px;border:1px solid var(--bd);line-height:0}}.qr svg{{width:168px;height:168px}}
.grp{{margin-top:14px}}.grp-t{{display:block;font-size:12px;color:var(--mu);margin-bottom:6px}}.grp-b{{display:flex;flex-wrap:wrap;gap:8px}}
.cfgs{{list-style:none;margin:0;padding:0;display:grid;gap:10px}}
.cfg{{display:flex;align-items:center;justify-content:space-between;gap:12px;background:var(--soft);border:1px solid var(--bd);border-radius:14px;padding:12px 14px}}
.cfg-main{{min-width:0}}.cfg-name{{font-weight:700;word-break:break-word}}.cfg-addr{{font:12px ui-monospace,Consolas,monospace;color:var(--mu);margin-top:2px}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}}.chip{{font-size:11.5px;padding:0 9px;border-radius:99px;background:var(--card);border:1px solid var(--bd);color:var(--mu);direction:ltr}}
.chip.proto{{color:var(--ac);border-color:color-mix(in srgb,var(--ac) 40%,var(--bd))}}.chip.sec{{color:var(--ok)}}
ol.steps{{margin:0;padding:0 20px 0 0;color:var(--mu)}}ol.steps li{{margin-bottom:4px}}ol.steps b{{color:var(--fg)}}
.foot{{text-align:center;color:var(--mu);font-size:12px;margin-top:22px}}
.toast{{position:fixed;inset-inline:0;bottom:22px;margin:auto;width:max-content;max-width:90vw;background:var(--fg);color:var(--bg);padding:9px 18px;border-radius:99px;font-weight:700;opacity:0;transform:translateY(10px);transition:.25s;pointer-events:none}}.toast.on{{opacity:1;transform:none}}
@media(max-width:520px){{.ring{{margin:0 auto}}.uname{{font-size:19px}}.cfg{{flex-wrap:wrap}}.cfg .btn{{width:100%}}}}
@media(prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
{theme_css(tpl)}</style></head><body class="t-{tpl}">
<div class="wrap">
{inner}
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script nonce="{e(nonce)}">
(function(){{
var $=function(s,r){{return(r||document).querySelectorAll(s)}},T=$('#toast')[0],tm;
function toast(m){{T.textContent=m;T.className='toast on';clearTimeout(tm);tm=setTimeout(function(){{T.className='toast'}},1600)}}
function copy(t){{
 if(navigator.clipboard&&window.isSecureContext)return navigator.clipboard.writeText(t);
 return new Promise(function(ok,no){{var a=document.createElement('textarea');a.value=t;a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();try{{document.execCommand('copy')?ok():no()}}catch(x){{no(x)}}document.body.removeChild(a)}});
}}
Array.prototype.forEach.call($('[data-copy]'),function(b){{b.addEventListener('click',function(){{copy(b.getAttribute('data-copy')).then(function(){{toast('کپی شد ✓')}},function(){{toast('کپی نشد؛ دستی کپی کنید')}})}})}});
var fmt=null,gfmt=null;
try{{fmt=new Intl.DateTimeFormat('fa-IR-u-ca-persian',{{year:'numeric',month:'long',day:'numeric',hour:'2-digit',minute:'2-digit'}});gfmt=new Intl.DateTimeFormat('en-GB',{{year:'numeric',month:'short',day:'2-digit'}})}}catch(x){{}}
Array.prototype.forEach.call($('.date'),function(s){{var d=new Date(parseInt(s.getAttribute('data-ts'),10)*1000);s.textContent=fmt?fmt.format(d):d.toISOString().slice(0,16).replace('T',' ');if(gfmt){{s.title=gfmt.format(d)}}}});
var root=document.documentElement;try{{var s=localStorage.getItem('theme');if(s)root.setAttribute('data-theme',s)}}catch(x){{}}
$('#theme')[0].addEventListener('click',function(){{var dark=root.getAttribute('data-theme')?root.getAttribute('data-theme')==='dark':matchMedia('(prefers-color-scheme:dark)').matches;var n=dark?'light':'dark';root.setAttribute('data-theme',n);try{{localStorage.setItem('theme',n)}}catch(x){{}}}});
}})();
</script></body></html>"""
