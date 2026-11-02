"""Subscription-page templates. 'classic' is the built-in look; the others are CSS-only overrides (no external assets)."""
import re
from app.db.models import Admin, Setting

DEFAULT = "classic"
KEYS = ("bg", "card", "soft", "bd", "fg", "mu", "ac", "ok", "warn", "bad", "sh")


def _v(d: dict) -> str:
    return ";".join(f"--{k}:{d[k]}" for k in KEYS if k in d)


def _theme(tid: str, light: dict, dark: dict, extra: str) -> str:
    b = f"body.t-{tid}"
    return (f"{b}{{{_v(light)}}}"
            f"@media(prefers-color-scheme:dark){{html:not([data-theme=light]) {b}{{{_v(dark)}}}}}"
            f"html[data-theme=dark] {b}{{{_v(dark)}}}" + re.sub(r"@(?!media)", b, extra))


_BRUT = {"bg": "#fff7d6", "card": "#ffffff", "soft": "#ffe45e", "bd": "#111111", "fg": "#111111", "mu": "#444444", "ac": "#ff3d81", "ok": "#0a8f3c", "warn": "#c26a00", "bad": "#d10029", "sh": "6px 6px 0 #111"}
_BRUT_D = {"bg": "#141414", "card": "#1f1f1f", "soft": "#2a2a2a", "bd": "#f5f5f5", "fg": "#f5f5f5", "mu": "#bbbbbb", "ac": "#ff6fa5", "ok": "#4ade80", "warn": "#fbbf24", "bad": "#ff6b6b", "sh": "6px 6px 0 #f5f5f5"}
_TERM = {"bg": "#020a05", "card": "#04140b", "soft": "#072114", "bd": "#0f5a32", "fg": "#b6ffd0", "mu": "#55b57c", "ac": "#39ff88", "ok": "#39ff88", "warn": "#ffd24a", "bad": "#ff5a5a", "sh": "none"}
_TICKET = {"bg": "#e8e3d6", "card": "#fffdf7", "soft": "#f4f0e4", "bd": "#c9c2ae", "fg": "#1c1b18", "mu": "#6f6b5f", "ac": "#1c1b18", "ok": "#2f7d4f", "warn": "#a8620a", "bad": "#b4231b", "sh": "none"}
_TICKET_D = {"bg": "#121110", "card": "#1d1c19", "soft": "#252420", "bd": "#45423a", "fg": "#f1eee6", "mu": "#a29d8e", "ac": "#f1eee6", "ok": "#6cc08b", "warn": "#e0a24a", "bad": "#ef7a72", "sh": "none"}
_SUNSET = {"bg": "#fff4ec", "card": "#ffffff", "soft": "#ffe9da", "bd": "#ffd5bd", "fg": "#3b1d0e", "mu": "#8a5a40", "ac": "#ea580c", "ok": "#15803d", "warn": "#b45309", "bad": "#be123c", "sh": "0 10px 30px rgba(234,88,12,.14)"}
_SUNSET_D = {"bg": "#1f0f0a", "card": "#2b1710", "soft": "#3a1f14", "bd": "#5a3020", "fg": "#ffeede", "mu": "#d2a88f", "ac": "#fb923c", "ok": "#4ade80", "warn": "#fbbf24", "bad": "#fb7185", "sh": "none"}

THEMES = {
    "classic": {"label": "کلاسیک", "css": ""},
    # Neo-brutalist: thick black outlines, hard offset shadows, flat pop colors, tilted tags.
    # Layout: 2-column board; usage shown as tall vertical meter columns; links + details side by side.
    "aurora": {"label": "نئوبروتال", "css": _theme("aurora", _BRUT, _BRUT_D,
        "@{background-color:var(--bg);background-image:radial-gradient(color-mix(in srgb,var(--fg) 22%,transparent) 1.2px,transparent 1.2px);background-size:18px 18px}"
        "@ .wrap{max-width:980px;display:grid;grid-template-columns:1fr 1fr;gap:0 22px;align-items:start}"
        "@ .wrap>.top,@ .wrap>.alert{grid-column:1/-1}@ .wrap>.foot{grid-column:1/-1;order:9}"
        "@ .card:nth-of-type(1){grid-column:1/-1;order:1}@ .card:nth-of-type(3){order:2}@ .card:nth-of-type(2){order:3}"
        "@ .card:nth-of-type(4){grid-column:1/-1;order:4}@ .card:nth-of-type(5){grid-column:1/-1;order:5}"
        "@ .ring{display:none}@ .hero{flex-wrap:nowrap}@ .vcol{display:flex;gap:14px;height:200px;flex:none}"
        "@ .vc{position:relative;width:74px;height:100%;border:3px solid var(--bd);background:var(--card);box-shadow:4px 4px 0 var(--bd)}"
        "@ .vc i{position:absolute;inset-inline:0;bottom:0;height:var(--p);border-top:3px solid var(--bd)}"
        "@ .vc em{position:absolute;top:0;inset-inline:0;text-align:center;font-style:normal;font-size:11px;font-weight:800;line-height:1.4;background:var(--card);color:var(--fg);border-bottom:3px solid var(--bd);z-index:1}"
        "@ .brand{display:inline-block;background:var(--fg);color:var(--bg);padding:2px 12px;transform:rotate(1.5deg)}"
        "@ .card{margin-top:34px;border:3px solid var(--bd);border-radius:0;box-shadow:var(--sh)}"
        "@ .card h2{display:inline-block;background:var(--ac);color:#fff;border:3px solid var(--bd);padding:2px 12px;margin:-36px 0 16px;transform:rotate(-1.5deg)}"
        "@ .stat{border:3px solid var(--bd);border-radius:0;box-shadow:3px 3px 0 var(--bd);color:#111}@ .stat:nth-child(odd){background:#a0e7ff}@ .stat:nth-child(even){background:#ffe45e}@ .stat .k{color:#333}"
        "@ .btn{border:3px solid var(--bd);border-radius:0;box-shadow:3px 3px 0 var(--bd);font-weight:800}@ .btn:active{transform:translate(3px,3px);box-shadow:none}@ .btn.pri{background:var(--ac);color:#fff}@ .btn.app{background:#a0e7ff;color:#111}"
        "@ .cfg,@ .sublink code{border:3px solid var(--bd);border-radius:0}@ .qr,@ .chip,@ .badge,@ .alert,@ .toast{border-radius:0}"
        "@ .cfgs{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}"
        "@ .badge{border:2px solid var(--bd);color:#111!important;background:#b8f2c9!important}@ .badge.bad{background:#ffb3b3!important}@ .badge.warn{background:#ffe45e!important}@ .badge.mute{background:#ddd!important}"
        "@ .alert{border:3px solid var(--bd);background:#ffe45e;color:#111}@ .alert.bad{background:#ffb3b3}"
        "@ .bar{height:14px;border:3px solid var(--bd);border-radius:0;background:var(--card)}@ .bar i{border-radius:0}@ .kv{border-bottom:2px solid var(--bd)}"
        "@media(max-width:760px){@ .wrap{display:block}@ .hero{flex-wrap:wrap}@ .vcol{height:150px;margin:0 auto}}")},
    # Terminal: console windows, monospace, green-on-black, square corners.
    # Layout: status header with horizontal segmented meters, then link + configs full width, details/guide as split panes.
    "midnight": {"label": "ترمینال", "css": _theme("midnight", _TERM, _TERM,
        "@{background:repeating-linear-gradient(0deg,rgba(57,255,136,.035) 0 1px,transparent 1px 3px),var(--bg);color-scheme:dark;font-family:ui-monospace,Consolas,Menlo,Vazirmatn,monospace}"
        "@ .wrap{max-width:940px;display:grid;grid-template-columns:1fr 1fr;gap:0 16px;align-items:start}"
        "@ .wrap>.top,@ .wrap>.alert{grid-column:1/-1}@ .wrap>.foot{grid-column:1/-1;order:9}"
        "@ .card:nth-of-type(1){grid-column:1/-1;order:1}@ .card:nth-of-type(3){grid-column:1/-1;order:2}@ .card:nth-of-type(4){grid-column:1/-1;order:3}"
        "@ .card:nth-of-type(2){order:4}@ .card:nth-of-type(5){order:5}"
        "@ .ring{display:none}@ .hero{flex-wrap:nowrap;gap:22px}@ .vcol{display:flex;flex-direction:column;gap:10px;width:300px;flex:none;order:2}"
        "@ .vc{position:relative;height:24px;border:1px solid var(--bd)}"
        "@ .vc i{position:absolute;top:0;bottom:0;inset-inline-start:0;width:var(--p);background-color:transparent}"
        "@ .vc i.ok{background-image:repeating-linear-gradient(90deg,var(--ok) 0 9px,transparent 9px 11px)}"
        "@ .vc i.warn{background-image:repeating-linear-gradient(90deg,var(--warn) 0 9px,transparent 9px 11px)}"
        "@ .vc i.bad{background-image:repeating-linear-gradient(90deg,var(--bad) 0 9px,transparent 9px 11px)}"
        "@ .vc em{position:relative;z-index:1;font-style:normal;font-size:11px;padding:0 8px;line-height:22px;color:var(--fg);text-shadow:0 0 3px var(--bg),0 0 3px var(--bg),0 0 3px var(--bg)}"
        "@ .brand{direction:ltr;font-family:ui-monospace,Consolas,monospace}@ .brand::before{content:'root@sub:~# ';color:var(--ac)}"
        "@ .card{border-radius:0;border:1px solid var(--bd);padding:0 18px 18px;overflow:hidden;box-shadow:0 0 0 1px rgba(57,255,136,.08)}"
        "@ .card::before{content:'● ● ●  bash';display:block;direction:ltr;text-align:left;margin:0 -18px 16px;padding:6px 14px;background:var(--soft);border-bottom:1px solid var(--bd);color:var(--ac);font-size:11px;letter-spacing:3px}"
        "@ .card h2{color:var(--ac);font-size:14px}@ .card h2::before{content:'$ ';direction:ltr}"
        "@ .uname,@ .stat .v,@ .ring .mid b{font-family:ui-monospace,Consolas,monospace}@ .uname::before{content:'> ';color:var(--ac)}"
        "@ .stat,@ .cfg,@ .sublink code,@ .qr,@ .chip,@ .badge,@ .alert,@ .bar,@ .bar i,@ .toast{border-radius:0}@ .stat{background:transparent;border:1px dashed var(--bd)}@ .badge{border:1px solid currentColor}"
        "@ .btn{border-radius:0;background:transparent;color:var(--ac);border-color:var(--ac)}@ .btn.pri{background:var(--ac);color:#021208}"
        "@media(max-width:760px){@ .wrap{display:block}@ .hero{flex-wrap:wrap}@ .vcol{width:100%}}")},
    # Ticket / boarding pass: wide pass with a left stub (ring + thin punch meters) torn off by a dashed
    # perforation; main body holds details + link; configs as tear-off tiles; steps as a footer row; barcode.
    "paper": {"label": "بلیط", "css": _theme("paper", _TICKET, _TICKET_D,
        "@ .wrap{max-width:920px;padding-top:28px;display:grid;grid-template-columns:270px 1fr;gap:0;align-items:stretch}"
        "@ .wrap>.top,@ .wrap>.alert,@ .wrap>.foot{grid-column:1/-1}@ .top{justify-content:center;gap:16px}@ .alert{border-radius:0}"
        "@ .card{position:relative;margin:0;border:0;border-radius:0;box-shadow:none;padding:20px 22px;border-bottom:2px dashed var(--bd)}"
        "@ .card:nth-of-type(1){grid-row:span 2;border-top:6px double var(--fg);border-inline-end:3px dashed var(--bd);border-radius:10px 0 0 0;text-align:center}"
        "@ .card:nth-of-type(2){border-top:6px double var(--fg);border-radius:0 10px 0 0}"
        "@ .card:nth-of-type(4){grid-column:1/-1;border-top:0}@ .card:nth-of-type(5){grid-column:1/-1;border-bottom:0;border-radius:0 0 10px 10px}"
        "@ .card:nth-of-type(1)::before,@ .card:nth-of-type(1)::after{content:'';position:absolute;inset-inline-end:-13px;width:24px;height:24px;border-radius:50%;background:var(--bg);z-index:1}"
        "@ .card:nth-of-type(1)::before{top:-12px}@ .card:nth-of-type(1)::after{bottom:-12px}"
        "@ .card h2{text-align:center;font-size:13px;letter-spacing:3px;border-bottom:1px solid var(--fg);padding-bottom:6px}"
        "@ .hero{flex-direction:column;gap:14px}@ .hero-info{min-width:0;width:100%}@ .uname{text-align:center;font-family:ui-monospace,Consolas,monospace}@ .ring{margin:0 auto}@ .ring,@ .ring svg{width:120px;height:120px}@ .ring circle{stroke-width:5;stroke-linecap:butt}"
        "@ .vcol{display:flex;flex-direction:column;gap:6px;width:100%}@ .vc{position:relative;height:16px;border:1px solid var(--fg)}"
        "@ .vc i{position:absolute;top:0;bottom:0;inset-inline-start:0;width:var(--p);background-image:repeating-linear-gradient(135deg,rgba(0,0,0,.28) 0 2px,transparent 2px 5px)}"
        "@ .vc em{position:relative;z-index:1;font-style:normal;font-size:10px;line-height:14px;padding:0 6px;color:var(--fg);text-shadow:0 0 3px var(--card),0 0 3px var(--card)}"
        "@ .grid{grid-template-columns:1fr 1fr}@ .stat{background:transparent;border:1px dashed var(--bd);border-radius:0;text-align:center}@ .stat .v,@ .kv .v{font-family:ui-monospace,Consolas,monospace}"
        "@ .btn,@ .cfg,@ .qr,@ .chip,@ .badge,@ .bar,@ .bar i,@ .sublink code{border-radius:0}@ .btn{border:1.5px solid var(--fg)}@ .btn.pri{background:var(--fg);color:var(--bg)}"
        "@ .cfgs{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}@ .cfg{background:transparent;border:1px dashed var(--fg)}"
        "@ ol.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}"
        "@ .brand{font-weight:600;letter-spacing:3px}@ .badge{border:1px solid currentColor;background:transparent!important}"
        "@ .foot::before{content:'';display:block;height:34px;margin-bottom:8px;background:repeating-linear-gradient(90deg,var(--fg) 0 2px,transparent 2px 4px,var(--fg) 4px 5px,transparent 5px 9px,var(--fg) 9px 12px,transparent 12px 14px)}"
        "@media(max-width:760px){@ .wrap{display:block}@ .card:nth-of-type(1){border-inline-end:0;border-radius:10px 10px 0 0}@ .card:nth-of-type(1)::before,@ .card:nth-of-type(1)::after{display:none}@ .card:nth-of-type(2){border-top:0;border-radius:0}}")},
    # Bento: rounded gradient banner (ring + glowing pill meters) on top, then an asymmetric 12-column tile grid.
    "sunset": {"label": "بنتو گرادیانت", "css": _theme("sunset", _SUNSET, _SUNSET_D,
        "@ .wrap{max-width:1040px;display:grid;grid-template-columns:repeat(12,1fr);gap:16px;align-items:stretch}"
        "@ .wrap>.top,@ .wrap>.alert,@ .wrap>.foot{grid-column:1/-1}@ .top{margin-bottom:0}@ .alert{margin-bottom:0}"
        "@ .card{margin:0;border-radius:28px;grid-column:span 6}"
        "@ .card:nth-of-type(2){grid-column:span 5}@ .card:nth-of-type(3){grid-column:span 7}@ .card:nth-of-type(4){grid-column:span 7}@ .card:nth-of-type(5){grid-column:span 5;background:var(--soft)}"
        "@ .card h2::before{content:'';display:inline-block;width:10px;height:10px;border-radius:50%;margin-inline-end:8px;background:linear-gradient(135deg,#f97316,#ec4899)}"
        "@ .card:nth-of-type(1){grid-column:1/-1;padding:28px 30px;background:linear-gradient(120deg,#f97316,#ec4899);color:#fff;border:0}"
        "@ .hero{flex-wrap:nowrap;gap:28px}@ .hero-info{min-width:0}@ .uname{font-size:24px}"
        "@ .card:nth-of-type(1) .k,@ .card:nth-of-type(1) .ring .mid span{color:rgba(255,255,255,.85)}"
        "@ .card:nth-of-type(1) .stat{background:rgba(255,255,255,.2)}@ .card:nth-of-type(1) .ring .tr{stroke:rgba(255,255,255,.3)}@ .card:nth-of-type(1) .ring circle.pg{stroke:#fff}@ .card:nth-of-type(1) .bar{background:rgba(255,255,255,.3)}@ .card:nth-of-type(1) .bar i{background:#fff}"
        "@ .card:nth-of-type(1) .badge{background:rgba(255,255,255,.25);color:#fff}"
        "@ .vcol{display:flex;gap:40px;height:120px;flex:none;margin-bottom:26px}"
        "@ .vc{position:relative;width:28px;height:100%;border-radius:99px;background:rgba(255,255,255,.28)}"
        "@ .vc i{position:absolute;inset-inline:0;bottom:0;height:var(--p);min-height:6px;border-radius:99px;background:#fff!important;box-shadow:0 0 14px rgba(255,255,255,.6)}"
        "@ .vc em{position:absolute;top:100%;left:50%;transform:translateX(-50%);margin-top:4px;width:64px;text-align:center;font-style:normal;font-size:10.5px;line-height:1.2;color:#fff}"
        "@ .btn{border-radius:99px}@ .btn.pri{background:linear-gradient(135deg,#f97316,#ec4899);border:0}@ .chip{border-radius:99px}"
        "@media(max-width:860px){@ .wrap{display:block}@ .card{margin-bottom:16px}@ .hero{flex-wrap:wrap}@ .vcol{margin:0 auto 26px}}")},
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
