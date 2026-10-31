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


_AURORA = {"bg": "#eef0ff", "card": "rgba(255,255,255,.62)", "soft": "rgba(255,255,255,.55)", "bd": "rgba(255,255,255,.8)", "fg": "#1b1740", "mu": "#5d5a85", "ac": "#7c3aed", "ok": "#059669", "warn": "#d97706", "bad": "#e11d48", "sh": "0 10px 40px rgba(124,58,237,.15)"}
_AURORA_D = {"bg": "#0b0a1f", "card": "rgba(30,27,75,.55)", "soft": "rgba(255,255,255,.07)", "bd": "rgba(167,139,250,.28)", "fg": "#ede9fe", "mu": "#a5a1d6", "ac": "#a78bfa", "ok": "#34d399", "warn": "#fbbf24", "bad": "#fb7185", "sh": "none"}
_MIDNIGHT = {"bg": "#05070d", "card": "#0b1020", "soft": "#0f1730", "bd": "#12324a", "fg": "#e6fffb", "mu": "#7fb3b0", "ac": "#22d3ee", "ok": "#4ade80", "warn": "#facc15", "bad": "#ff4d6d", "sh": "0 0 24px rgba(34,211,238,.12)"}
_PAPER = {"bg": "#faf9f6", "card": "#ffffff", "soft": "#f3f1ea", "bd": "#e4e0d5", "fg": "#1c1b18", "mu": "#6f6b5f", "ac": "#1c1b18", "ok": "#2f7d4f", "warn": "#a8620a", "bad": "#b4231b", "sh": "none"}
_PAPER_D = {"bg": "#161513", "card": "#1d1c19", "soft": "#252420", "bd": "#34322c", "fg": "#f1eee6", "mu": "#a29d8e", "ac": "#f1eee6", "ok": "#6cc08b", "warn": "#e0a24a", "bad": "#ef7a72", "sh": "none"}
_SUNSET = {"bg": "#fff4ec", "card": "#ffffff", "soft": "#ffe9da", "bd": "#ffd5bd", "fg": "#3b1d0e", "mu": "#8a5a40", "ac": "#ea580c", "ok": "#15803d", "warn": "#b45309", "bad": "#be123c", "sh": "0 10px 30px rgba(234,88,12,.14)"}
_SUNSET_D = {"bg": "#1f0f0a", "card": "#2b1710", "soft": "#3a1f14", "bd": "#5a3020", "fg": "#ffeede", "mu": "#d2a88f", "ac": "#fb923c", "ok": "#4ade80", "warn": "#fbbf24", "bad": "#fb7185", "sh": "none"}

THEMES = {
    "classic": {"label": "کلاسیک", "css": ""},
    "aurora": {"label": "شفق (شیشه‌ای)", "css": _theme("aurora", _AURORA, _AURORA_D,
        "@{background:radial-gradient(1200px 600px at 85% -10%,color-mix(in srgb,var(--ac) 35%,transparent),transparent),radial-gradient(900px 500px at -10% 110%,color-mix(in srgb,#06b6d4 30%,transparent),transparent),var(--bg);min-height:100vh}"
        "@ .card{backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border-radius:28px}"
        "@ .stat{border-radius:18px;border:1px solid var(--bd)}@ .btn.pri{background:linear-gradient(135deg,var(--ac),#06b6d4);border:0}"
        "@ .ring circle{stroke-width:9}@ .brand{background:linear-gradient(90deg,var(--ac),#06b6d4);-webkit-background-clip:text;background-clip:text;color:transparent}")},
    "midnight": {"label": "نئون شبانه", "css": _theme("midnight", _MIDNIGHT, _MIDNIGHT,
        "@{background:radial-gradient(800px 400px at 50% -5%,rgba(34,211,238,.14),transparent),var(--bg);color-scheme:dark}"
        "@ .card{border-radius:10px;border-color:var(--bd);box-shadow:var(--sh)}@ .stat,@ .cfg,@ .sublink code{border-radius:6px;border:1px solid var(--bd)}"
        "@ .btn{border-radius:6px;border-color:var(--ac);color:var(--ac);background:transparent;text-transform:uppercase}@ .btn.pri{background:var(--ac);color:#04121a;box-shadow:0 0 16px rgba(34,211,238,.45)}"
        "@ .ring circle{stroke-width:7}@ .ring .pg{filter:drop-shadow(0 0 6px currentColor)}@ .uname,@ .stat .v,@ .ring .mid b{font-family:ui-monospace,Consolas,monospace;letter-spacing:.5px}"
        "@ .card h2{color:var(--ac);font-size:14px;letter-spacing:1px}@ .badge{border:1px solid currentColor}")},
    "paper": {"label": "مینیمال کاغذی", "css": _theme("paper", _PAPER, _PAPER_D,
        "@ .wrap{max-width:620px;padding-top:32px}@ .card{border-radius:4px;box-shadow:none;border-width:1px 0 0 0;border-radius:0;background:transparent;padding:18px 2px}"
        "@ .hero{flex-direction:column;align-items:flex-start;gap:16px}@ .ring{width:96px;height:96px}@ .ring svg{width:96px;height:96px}@ .ring circle{stroke-width:4}@ .ring .mid b{font-size:18px}@ .ring .mid span{display:none}"
        "@ .stat{background:transparent;border:0;border-bottom:1px solid var(--bd);border-radius:0;padding:8px 0}@ .grid{grid-template-columns:1fr 1fr}"
        "@ .btn{border-radius:2px;border-color:var(--fg)}@ .btn.pri{background:var(--fg);color:var(--bg)}@ .cfg{border-radius:2px;background:transparent}@ .qr{border-radius:2px}"
        "@ .brand{font-weight:600;letter-spacing:2px}@ .badge{border-radius:2px;border:1px solid currentColor;background:transparent!important}@ .bar,@ .bar i{border-radius:0;height:4px}")},
    "sunset": {"label": "غروب (دو ستونه)", "css": _theme("sunset", _SUNSET, _SUNSET_D,
        "@ .wrap{max-width:1020px;display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}@ .wrap>.top,@ .wrap>.alert,@ .wrap>.foot,@ .wrap>.card:first-of-type{grid-column:1/-1}@ .card{margin:0;border-radius:22px}"
        "@ .card:first-of-type{background:linear-gradient(135deg,#f97316,#ec4899);color:#fff;border:0}@ .card:first-of-type .k,@ .card:first-of-type .ring .mid span{color:rgba(255,255,255,.85)}"
        "@ .card:first-of-type .stat{background:rgba(255,255,255,.2)}@ .card:first-of-type .ring .tr{stroke:rgba(255,255,255,.3)}@ .card:first-of-type .ring circle.pg{stroke:#fff}@ .card:first-of-type .bar{background:rgba(255,255,255,.3)}@ .card:first-of-type .bar i{background:#fff}"
        "@ .card:first-of-type .badge{background:rgba(255,255,255,.25);color:#fff}@ .btn{border-radius:99px}@ .btn.pri{background:linear-gradient(135deg,#f97316,#ec4899);border:0}@ .chip{border-radius:99px}"
        "@media(max-width:760px){@ .wrap{grid-template-columns:1fr}}")},
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
