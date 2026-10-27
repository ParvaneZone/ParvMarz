"""Customer-facing subscription page (what a user sees when the sub link is opened in a browser).

Pure functions, no web-framework imports: easy to test. Everything that comes from outside
(usernames, remarks from panels, URLs) is HTML-escaped. Only inline CSS/JS, no external assets, so
it works on blocked/filtered networks.
"""
import base64
import html
import math
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
        '<div class="cfg-addr ltr">' + e(p.get("server", "")) + ":" + e(p.get("port", "")) + "</div></div>"
        '<button class="btn sm" data-copy="' + e(p.get("raw", "")) + '">کپی</button></li>'
    )


def render_subscription_page(*, nonce: str, brand: str, username: str, state: str, used: int, limit: int | None,
                             expire: int, created: int, now: int, online_at: int | None, service: str,
                             reset: str, on_hold_days: int | None, links: list[dict], sub_url: str,
                             qr_svg: str = "") -> str:
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

    def ts_cell(title, ts, empty="—"):
        val = f'<span class="date" data-ts="{int(ts)}">—</span>' if ts else empty
        return f'<div class="kv"><span class="k">{title}</span><span class="v">{val}</span></div>'

    imports = {}
    for group, name, href in import_links(sub_url, username):
        imports.setdefault(group, []).append(f'<a class="btn app" href="{e(href)}" rel="noopener">{e(name)}</a>')
    imports_html = "".join(
        f'<div class="grp"><span class="grp-t">{e(g)}</span><div class="grp-b">{"".join(items)}</div></div>'
        for g, items in imports.items())

    if links:
        cfgs = "".join(_link_card(p) for p in links)
        cfg_block = f'<ul class="cfgs">{cfgs}</ul>'
    else:
        cfg_block = '<p class="muted">در حال حاضر کانفیگی برای نمایش وجود ندارد.</p>'

    time_bar = ""
    if time_pct is not None:
        time_bar = (f'<div class="bar"><i class="{"bad" if time_pct >= 90 else "warn" if time_pct >= 70 else "ok"}" '
                    f'style="width:{time_pct:.1f}%"></i></div>')

    qr_block = f'<div class="qr" aria-label="QR">{qr_svg}</div>' if qr_svg else ""

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
</style></head><body>
<div class="wrap">
 <div class="top"><div class="brand">{e(brand)}</div><button class="btn sm" id="theme" type="button" aria-label="تم">🌓 تم</button></div>
 {alerts_html}
 <section class="card">
  <div class="hero">
   <div class="ring"><svg viewBox="0 0 120 120" aria-hidden="true"><circle class="tr" cx="60" cy="60" r="52"/><circle class="pg {ring_tone}" cx="60" cy="60" r="52" stroke-dasharray="{ring_c:.2f}" stroke-dashoffset="{ring_off:.2f}"/></svg>
    <div class="mid"><b>{fa(f"{pct:.0f}") + "٪" if limit else "∞"}</b><span>{"مصرف‌شده" if limit else "حجم نامحدود"}</span></div></div>
   <div class="hero-info"><div class="uname">{e(username)}</div><span class="badge {tone}">{e(label)}</span>
    {time_bar}
    <div class="grid">
     <div class="stat"><span class="k">مصرف‌شده</span><span class="v">{fmt_bytes(used)}</span></div>
     <div class="stat"><span class="k">حجم کل</span><span class="v">{fmt_bytes(limit)}</span></div>
     <div class="stat"><span class="k">باقی‌مانده</span><span class="v">{fmt_bytes(remaining)}</span></div>
     <div class="stat"><span class="k">{days_sub}</span><span class="v">{days_txt}</span></div>
    </div></div>
  </div>
 </section>
 <section class="card"><h2>مشخصات اشتراک</h2>
  <div class="kv"><span class="k">نام کاربری</span><span class="v ltr">{e(username)}</span></div>
  <div class="kv"><span class="k">وضعیت</span><span class="v">{e(label)}</span></div>
  {f'<div class="kv"><span class="k">سرویس</span><span class="v">{e(service)}</span></div>' if service else ""}
  {ts_cell("تاریخ شروع", created)}
  {ts_cell("تاریخ پایان", expire, "نامحدود")}
  {ts_cell("آخرین اتصال", online_at, "هنوز متصل نشده")}
  <div class="kv"><span class="k">بازنشانی حجم</span><span class="v">{e(RESET.get(reset, reset))}</span></div>
  <div class="kv"><span class="k">تعداد کانفیگ‌ها</span><span class="v">{fa(len(links))}</span></div>
 </section>
 <section class="card"><h2>لینک اشتراک</h2>
  <div class="two"><div>
   <div class="sublink"><code id="sub">{e(sub_url)}</code><button class="btn pri" data-copy="{e(sub_url)}" type="button">کپی لینک</button></div>
   <p class="muted" style="margin:10px 0 0;font-size:13px">این لینک شخصی شماست؛ آن را با کسی به اشتراک نگذارید.</p>
   {imports_html}
  </div>{qr_block}</div>
 </section>
 <section class="card"><h2>کانفیگ‌ها</h2>{cfg_block}</section>
 <section class="card"><h2>راهنمای اتصال</h2>
  <ol class="steps"><li>یکی از برنامه‌ها را نصب کنید: <b>v2rayNG</b> (اندروید)، <b>Streisand</b> یا <b>Shadowrocket</b> (آیفون)، <b>Hiddify</b> (همه سیستم‌ها).</li>
  <li>روی دکمه‌ی همان برنامه در بالا بزنید، یا لینک اشتراک را کپی و در برنامه از بخش «افزودن اشتراک» وارد کنید.</li>
  <li>اشتراک را بروزرسانی کنید و یک کانفیگ را انتخاب و وصل شوید.</li></ol>
 </section>
 <div class="foot">{e(brand)}</div>
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
