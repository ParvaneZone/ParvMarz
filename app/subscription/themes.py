"""Subscription-page templates. Colors/styling live here; the markup of each template is in layouts.py.

Every template has its own layout: classic = hero + two columns, aurora = neo-brutalist bento with vertical usage
columns, midnight = single terminal window, paper = boarding pass, sunset = sidebar dashboard. CSS only, no external assets.
"""
import re
from app.db.models import Admin, Setting

DEFAULT = "classic"
KEYS = ("bg", "card", "soft", "bd", "fg", "mu", "ac", "ok", "warn", "bad", "sh")


def _v(d: dict) -> str:
    return ";".join(f"--{k}:{d[k]}" for k in KEYS if k in d)


def _x(tid: str, extra: str) -> str:
    return re.sub(r"@(?!media)", f"body.t-{tid}", extra)


def _theme(tid: str, light: dict, dark: dict, extra: str) -> str:
    b = f"body.t-{tid}"
    return (f"{b}{{{_v(light)}}}"
            f"@media(prefers-color-scheme:dark){{html:not([data-theme=light]) {b}{{{_v(dark)}}}}}"
            f"html[data-theme=dark] {b}{{{_v(dark)}}}" + _x(tid, extra))


_BRUT = {"bg": "#fff7d6", "card": "#ffffff", "soft": "#ffe45e", "bd": "#111111", "fg": "#111111", "mu": "#444444", "ac": "#ff3d81", "ok": "#0a8f3c", "warn": "#c26a00", "bad": "#d10029", "sh": "6px 6px 0 #111"}
_BRUT_D = {"bg": "#141414", "card": "#1f1f1f", "soft": "#2a2a2a", "bd": "#f5f5f5", "fg": "#f5f5f5", "mu": "#bbbbbb", "ac": "#ff6fa5", "ok": "#4ade80", "warn": "#fbbf24", "bad": "#ff6b6b", "sh": "6px 6px 0 #f5f5f5"}
_TERM = {"bg": "#020a05", "card": "#04140b", "soft": "#072114", "bd": "#0f5a32", "fg": "#b6ffd0", "mu": "#55b57c", "ac": "#39ff88", "ok": "#39ff88", "warn": "#ffd24a", "bad": "#ff5a5a", "sh": "none"}
_TICKET = {"bg": "#e8e3d6", "card": "#fffdf7", "soft": "#f4f0e4", "bd": "#c9c2ae", "fg": "#1c1b18", "mu": "#6f6b5f", "ac": "#1c1b18", "ok": "#2f7d4f", "warn": "#a8620a", "bad": "#b4231b", "sh": "none"}
_TICKET_D = {"bg": "#121110", "card": "#1d1c19", "soft": "#252420", "bd": "#45423a", "fg": "#f1eee6", "mu": "#a29d8e", "ac": "#f1eee6", "ok": "#6cc08b", "warn": "#e0a24a", "bad": "#ef7a72", "sh": "none"}
_SUNSET = {"bg": "#fff4ec", "card": "#ffffff", "soft": "#ffe9da", "bd": "#ffd5bd", "fg": "#3b1d0e", "mu": "#8a5a40", "ac": "#ea580c", "ok": "#15803d", "warn": "#b45309", "bad": "#be123c", "sh": "0 10px 30px rgba(234,88,12,.14)"}
_SUNSET_D = {"bg": "#1f0f0a", "card": "#2b1710", "soft": "#3a1f14", "bd": "#5a3020", "fg": "#ffeede", "mu": "#d2a88f", "ac": "#fb923c", "ok": "#4ade80", "warn": "#fbbf24", "bad": "#fb7185", "sh": "none"}

THEMES = {
    # Hero banner (ring + info + stats row), then two columns: connect | details.
    "classic": {"label": "کلاسیک", "css": _x("classic",
        "@ .wrap{max-width:920px}"
        "@ .cl-hero{display:grid;grid-template-columns:auto 1fr;gap:18px 24px;align-items:center}"
        "@ .cl-hero .cl-stats{grid-column:1/-1;margin-top:0}"
        "@ .cl-cols{display:grid;grid-template-columns:1.2fr 1fr;gap:16px;align-items:start}"
        "@ .cl-cols .card{margin-bottom:0}@ .cl-cols+.card{margin-top:16px}"
        "@media(max-width:720px){@ .cl-hero{grid-template-columns:1fr;justify-items:center;text-align:center}@ .cl-info{width:100%}@ .cl-hero .uname{text-align:center}"
        "@ .cl-cols{grid-template-columns:1fr}@ .cl-cols .card{margin-bottom:16px}@ .cl-cols+.card{margin-top:0}}")},
    # Neo-brutalist bento: thick outlines, hard shadows, sticker tiles, usage as tall vertical columns.
    "aurora": {"label": "نئوبروتال", "css": _theme("aurora", _BRUT, _BRUT_D,
        "@{background-color:var(--bg);background-image:radial-gradient(color-mix(in srgb,var(--fg) 22%,transparent) 1.2px,transparent 1.2px);background-size:18px 18px}"
        "@ .wrap{max-width:980px}@ .brand{display:inline-block;background:var(--fg);color:var(--bg);padding:2px 12px;transform:rotate(1.5deg)}"
        "@ .br-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:46px 20px;margin-top:40px}"
        "@ .br-id,@ .br-cols{grid-column:span 3}@ .br-stats{grid-column:1/-1;display:grid;grid-template-columns:repeat(4,1fr);gap:16px}"
        "@ .br-con{grid-column:span 4}@ .br-det{grid-column:span 2}@ .br-cfg,@ .br-gd{grid-column:1/-1}"
        "@ .card{margin:0;border:3px solid var(--bd);border-radius:0;box-shadow:var(--sh)}"
        "@ .card h2{display:inline-block;background:var(--ac);color:#fff;border:3px solid var(--bd);padding:2px 12px;margin:-36px 0 16px;transform:rotate(-1.5deg)}"
        "@ .br-big{font-size:68px;font-weight:900;line-height:1.1;margin-top:10px}@ .br-cap{color:var(--mu)}"
        "@ .vcols{display:flex;gap:28px;justify-content:center;align-items:flex-end}@ .vcol{display:flex;flex-direction:column;align-items:center;gap:4px}"
        "@ .vt{width:58px;height:170px;border:3px solid var(--bd);background:var(--card);display:flex;align-items:flex-end}@ .vt i{display:block;width:100%}"
        "@ .vt i.ok{background:#4ade80}@ .vt i.warn{background:#ffe45e}@ .vt i.bad{background:#ff6b6b}@ .vcol b{font-size:20px}@ .vcol span{font-size:12px;color:var(--mu)}"
        "@ .stat{border:3px solid var(--bd);border-radius:0;box-shadow:3px 3px 0 var(--bd);color:#111}@ .stat:nth-child(odd){background:#a0e7ff}@ .stat:nth-child(even){background:#ffe45e}@ .stat .k{color:#333}"
        "@ .btn{border:3px solid var(--bd);border-radius:0;box-shadow:3px 3px 0 var(--bd);font-weight:800}@ .btn:active{transform:translate(3px,3px);box-shadow:none}@ .btn.pri{background:var(--ac);color:#fff}@ .btn.app{background:#a0e7ff;color:#111}"
        "@ .cfgs{grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}"
        "@ .cfg,@ .sublink code{border:3px solid var(--bd);border-radius:0}@ .qr,@ .chip,@ .badge,@ .alert,@ .toast{border-radius:0}"
        "@ .badge{border:2px solid var(--bd);color:#111!important;background:#b8f2c9!important}@ .badge.bad{background:#ffb3b3!important}@ .badge.warn{background:#ffe45e!important}@ .badge.mute{background:#ddd!important}"
        "@ .alert{border:3px solid var(--bd);background:#ffe45e;color:#111}@ .alert.bad{background:#ffb3b3}"
        "@ .bar{height:14px;border:3px solid var(--bd);border-radius:0;background:var(--card)}@ .bar i{border-radius:0}@ .kv{border-bottom:2px solid var(--bd)}"
        "@media(max-width:760px){@ .br-grid>*{grid-column:1/-1}@ .br-stats{grid-template-columns:1fr 1fr}@ .br-big{font-size:52px}}")},
    # Terminal: one console window, each section is a command's output, usage is an ASCII bar.
    "midnight": {"label": "ترمینال", "css": _theme("midnight", _TERM, _TERM,
        "@{background:repeating-linear-gradient(0deg,rgba(57,255,136,.035) 0 1px,transparent 1px 3px),var(--bg);color-scheme:dark;font-family:ui-monospace,Consolas,Menlo,Vazirmatn,monospace}"
        "@ .wrap{max-width:820px}@ .brand{direction:ltr}@ .brand::before{content:'root@sub:~# ';color:var(--ac)}"
        "@ .tm{padding:0;border-radius:0;overflow:hidden;box-shadow:0 0 0 1px rgba(57,255,136,.08)}"
        "@ .tm-bar{direction:ltr;text-align:left;padding:7px 14px;background:var(--soft);border-bottom:1px solid var(--bd);color:var(--ac);font-size:12px;letter-spacing:2px}"
        "@ .tm-body{padding:6px 18px 22px}"
        "@ .tm-l{direction:ltr;text-align:left;color:var(--ac);margin:18px 0 6px;font-size:13px}@ .tm-l::before{content:'$ '}"
        "@ .tm-o{padding-inline-start:14px;border-inline-start:1px solid var(--bd)}"
        "@ .tm-ascii{direction:ltr;text-align:left;font-size:15px;letter-spacing:1px;color:var(--ok);word-break:break-all}@ .tm-ascii.warn{color:var(--warn)}@ .tm-ascii.bad{color:var(--bad)}"
        "@ .tm-cfg{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;padding:6px 0;border-bottom:1px dashed var(--bd)}"
        "@ .tm-cfg .n{font-weight:700}@ .tm-cfg .a{direction:ltr;color:var(--mu);font-size:12px;word-break:break-all}"
        "@ .uname::before{content:'> ';color:var(--ac)}@ .uname,@ .stat .v,@ .kv .v{font-family:ui-monospace,Consolas,monospace}"
        "@ .qr,@ .chip,@ .badge,@ .alert,@ .toast,@ .sublink code{border-radius:0}@ .badge{border:1px solid currentColor}"
        "@ .btn{border-radius:0;background:transparent;color:var(--ac);border-color:var(--ac)}@ .btn.pri{background:var(--ac);color:#021208}@ .qr{margin-top:12px;display:inline-block}")},
    # Boarding pass: main ticket + perforated stub, narrow slips below, barcode footer.
    "paper": {"label": "بلیط", "css": _theme("paper", _TICKET, _TICKET_D,
        "@ .wrap{max-width:780px;padding-top:28px}@ .top{justify-content:center;gap:16px}@ .brand{font-weight:600;letter-spacing:3px}"
        "@ .card{border-radius:6px;box-shadow:0 2px 0 rgba(0,0,0,.06)}"
        "@ .card h2{font-size:13px;letter-spacing:3px;border-bottom:1px solid var(--fg);padding-bottom:6px}"
        "@ .tk-pass{display:grid;grid-template-columns:1fr 210px;padding:0;position:relative;border-top:6px double var(--fg)}"
        "@ .tk-main{padding:20px 22px;min-width:0}"
        "@ .tk-hd{display:flex;justify-content:space-between;gap:10px;font-size:12px;letter-spacing:2px;color:var(--mu);border-bottom:1px dashed var(--bd);padding-bottom:6px;margin-bottom:10px}"
        "@ .tk-route{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;margin:14px 0}@ .tk-route small{display:block;font-size:11px;color:var(--mu);letter-spacing:1px}@ .tk-line .bar{margin:0}"
        "@ .tk-stub{border-inline-start:2px dashed var(--bd);padding:20px 16px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;position:relative}"
        "@ .tk-stub::before,@ .tk-stub::after{content:'';position:absolute;inset-inline-start:-11px;width:20px;height:20px;border-radius:50%;background:var(--bg)}@ .tk-stub::before{top:-11px}@ .tk-stub::after{bottom:-11px}"
        "@ .tk-stub .qr svg{width:130px;height:130px}"
        "@ .tk-cols{grid-template-columns:repeat(4,1fr)}@ .tk-cols+.bar{margin-top:14px}"
        "@ .stat{background:transparent;border:1px dashed var(--bd);border-radius:0;text-align:center}@ .stat .v,@ .kv .v,@ .uname{font-family:ui-monospace,Consolas,monospace}"
        "@ .btn,@ .qr,@ .chip,@ .badge,@ .bar,@ .bar i,@ .sublink code{border-radius:0}@ .btn{border:1.5px solid var(--fg)}@ .btn.pri{background:var(--fg);color:var(--bg)}@ .cfg{background:transparent;border-radius:0}"
        "@ .badge{border:1px solid currentColor;background:transparent!important}"
        "@ .foot::before{content:'';display:block;height:34px;margin-bottom:8px;background:repeating-linear-gradient(90deg,var(--fg) 0 2px,transparent 2px 4px,var(--fg) 4px 5px,transparent 5px 9px,var(--fg) 9px 12px,transparent 12px 14px)}"
        "@media(max-width:620px){@ .tk-pass{grid-template-columns:1fr}@ .tk-stub{border-inline-start:0;border-top:2px dashed var(--bd)}"
        "@ .tk-stub::before,@ .tk-stub::after{inset-inline-start:auto;top:-11px;bottom:auto}@ .tk-stub::before{right:-11px}@ .tk-stub::after{left:-11px}@ .tk-cols{grid-template-columns:1fr 1fr}@ .tk-route{grid-template-columns:1fr}}")},
    # Sidebar dashboard: sticky gradient profile column (ring, QR, apps) + content column with stats and a configs table.
    "sunset": {"label": "داشبورد سایدبار", "css": _theme("sunset", _SUNSET, _SUNSET_D,
        "@ .wrap{max-width:1100px}"
        "@ .sb-wrap{display:grid;grid-template-columns:310px 1fr;gap:18px;align-items:start}"
        "@ .sb-side{position:sticky;top:16px;margin:0;padding:26px 20px;border:0;border-radius:24px;background:linear-gradient(160deg,#f97316,#ec4899);color:#fff;text-align:center;display:flex;flex-direction:column;align-items:center;gap:12px}"
        "@ .sb-side .uname{text-align:center;font-size:20px}@ .sb-side .ring .mid span,@ .sb-side .grp-t{color:rgba(255,255,255,.85)}"
        "@ .sb-side .ring .tr{stroke:rgba(255,255,255,.3)}@ .sb-side .ring circle.pg{stroke:#fff}@ .sb-side .bar{background:rgba(255,255,255,.3);width:100%}@ .sb-side .bar i{background:#fff}"
        "@ .sb-side .badge{background:rgba(255,255,255,.25);color:#fff}@ .sb-side .btn.app{background:rgba(255,255,255,.18);color:#fff;border-color:rgba(255,255,255,.4)}@ .sb-side .grp-b{justify-content:center}"
        "@ .sb-main{min-width:0}@ .sb-main .card{border-radius:22px}@ .sb-main .card h2{border-inline-start:5px solid var(--ac);padding-inline-start:10px}@ .sb-stats{margin:0 0 16px}"
        "@ .sb-kv{display:grid;grid-template-columns:1fr 1fr;gap:0 28px}"
        "@ .tbl-w{overflow-x:auto}@ .tbl{width:100%;border-collapse:collapse;font-size:13.5px}@ .tbl th{text-align:right;color:var(--mu);font-weight:600;padding:8px 10px;border-bottom:2px solid var(--bd)}"
        "@ .tbl td{padding:9px 10px;border-bottom:1px dashed var(--bd);vertical-align:middle}@ .tbl .a{direction:ltr;text-align:left;font:12px ui-monospace,Consolas,monospace;color:var(--mu);word-break:break-all}"
        "@ .btn{border-radius:99px}@ .btn.pri{background:linear-gradient(135deg,#f97316,#ec4899);border:0}@ .chip{border-radius:99px}"
        "@media(max-width:860px){@ .sb-wrap{grid-template-columns:1fr}@ .sb-side{position:static}@ .sb-kv{grid-template-columns:1fr}}")},
}


def theme_css(tid: str) -> str:
    return THEMES.get(tid, THEMES[DEFAULT])["css"]


def perm_key(tid: str) -> str:
    return f"sub.tpl.{tid}"


def allowed_templates(admin) -> list[str]:
    from app.core.permissions import has_perm
    return [t for t in THEMES if t == DEFAULT or (admin is not None and has_perm(admin, perm_key(t)))]


def resolve_template(db, admin_id) -> str:
    """Template chosen by the user's owner; falls back to classic if not chosen or the permission was removed."""
    if admin_id is None:
        return DEFAULT
    a = db.get(Admin, int(admin_id)); s = db.get(Setting, f"subtpl:{int(admin_id)}")
    tid = s.value.get("id") if s and isinstance(s.value, dict) else DEFAULT
    return tid if tid in allowed_templates(a) else DEFAULT
