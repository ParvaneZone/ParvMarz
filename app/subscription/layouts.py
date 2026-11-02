"""Per-template page layouts for the subscription page.

Each layout receives the prepared fragments `c` (already HTML-escaped by page.py) and returns the markup
placed between the top bar and the footer. Colors/styling live in themes.py; here only the structure differs.
"""
from app.subscription.page import PROTO, e, fa


def _tone(p: float) -> str:
    return "bad" if p >= 90 else "warn" if p >= 70 else "ok"


def _meta(p: dict) -> str:
    proto = PROTO.get(p.get("type", ""), str(p.get("type", "")).upper())
    sec = p.get("security") or ("tls" if p.get("tls") else "none")
    parts = [proto, p.get("network") or "tcp"]
    if sec and sec != "none":
        parts.append(sec.upper())
    return " / ".join(parts)


def _addr(p: dict) -> str:
    return e(p.get("server", "")) + ":" + e(p.get("port", ""))


def _copy_btn(p: dict, text: str = "کپی") -> str:
    return '<button class="btn sm" data-copy="' + e(p.get("raw", "")) + '" type="button">' + text + "</button>"


def _cfg_table(c: dict) -> str:
    if not c["links"]:
        return c["cfgs"]
    rows = "".join(
        "<tr><td>" + e(p.get("name") or "—") + '</td><td class="ltr">' + e(_meta(p)) + '</td><td class="a">'
        + _addr(p) + "</td><td>" + _copy_btn(p) + "</td></tr>" for p in c["links"])
    return ('<div class="tbl-w"><table class="tbl"><thead><tr><th>نام</th><th>نوع</th><th>آدرس</th><th></th></tr></thead>'
            "<tbody>" + rows + "</tbody></table></div>")


def _cfg_lines(c: dict) -> str:
    if not c["links"]:
        return c["cfgs"]
    return "".join(
        '<div class="tm-cfg"><span class="n">' + e(p.get("name") or "—") + '</span><span class="a">' + e(_meta(p)) + " "
        + _addr(p) + "</span>" + _copy_btn(p, "cp") + "</div>" for p in c["links"])


def _vcols(c: dict) -> str:
    cols = []

    def col(p, txt, cap):
        cols.append(f'<div class="vcol"><div class="vt"><i class="{_tone(p)}" style="height:{p:.0f}%"></i></div>'
                    f"<b>{txt}</b><span>{cap}</span></div>")
    col(c["pct"], c["pct_txt"], "حجم")
    if c["time_pct"] is not None:
        col(c["time_pct"], fa(f'{c["time_pct"]:.0f}') + "٪", "زمان")
    return '<div class="vcols">' + "".join(cols) + "</div>"


def classic(c: dict) -> str:
    """Wide hero (ring + info + stats row), then two columns: connect | details, then configs and guide."""
    return f"""{c['alerts']}
 <section class="card cl-hero">
  {c['ring']}
  <div class="cl-info"><div class="uname">{c['u']}</div>{c['badge']}{c['time_bar']}</div>
  <div class="grid cl-stats">{c['stats']}</div>
 </section>
 <div class="cl-cols">
  <section class="card"><h2>لینک اشتراک</h2><div class="two"><div>{c['sublink']}{c['imports']}</div>{c['qr']}</div></section>
  <section class="card"><h2>مشخصات اشتراک</h2>{c['details']}</section>
 </div>
 <section class="card"><h2>کانفیگ‌ها</h2>{c['cfgs']}</section>
 <section class="card"><h2>راهنمای اتصال</h2>{c['guide']}</section>"""


def aurora(c: dict) -> str:
    """Neo-brutalist bento: sticker tiles, usage shown as tall vertical columns."""
    vcols = _vcols(c)
    return f"""{c['alerts']}
 <div class="br-grid">
  <section class="card br-id"><h2>اشتراک</h2><div class="uname">{c['u']}</div>{c['badge']}
   <div class="br-big">{c['pct_txt']}</div><div class="br-cap">{c['usage_caption']}</div></section>
  <section class="card br-cols"><h2>مصرف</h2>{vcols}</section>
  <div class="br-stats">{c['stats']}</div>
  <section class="card br-con"><h2>اتصال</h2><div class="two"><div>{c['sublink']}{c['imports']}</div>{c['qr']}</div></section>
  <section class="card br-det"><h2>مشخصات</h2>{c['details']}</section>
  <section class="card br-cfg"><h2>کانفیگ‌ها</h2>{c['cfgs']}</section>
  <section class="card br-gd"><h2>راهنما</h2>{c['guide']}</section>
 </div>"""


def midnight(c: dict) -> str:
    """One terminal window; every section is the output of a shell command, usage is an ASCII bar."""
    n = round(c["pct"] / 5) if c["has_limit"] else 0
    ascii_bar = "[" + "█" * n + "░" * (20 - n) + "] " + c["pct_txt"]
    return f"""{c['alerts']}
 <section class="card tm"><div class="tm-bar">● ● ●  root@sub:~</div>
  <div class="tm-body">
   <div class="tm-l">whoami</div><div class="tm-o"><div class="uname">{c['u']}</div>{c['badge']}</div>
   <div class="tm-l">usage --bar</div><div class="tm-o"><div class="tm-ascii {c['ring_tone']}">{ascii_bar}</div>{c['stat_rows']}</div>
   <div class="tm-l">cat details</div><div class="tm-o">{c['details']}</div>
   <div class="tm-l">show sub-link</div><div class="tm-o">{c['sublink']}{c['imports']}{c['qr']}</div>
   <div class="tm-l">ls configs/</div><div class="tm-o">{_cfg_lines(c)}</div>
   <div class="tm-l">cat HELP</div><div class="tm-o">{c['guide']}</div>
  </div></section>"""


def paper(c: dict) -> str:
    """Boarding pass: main ticket + perforated stub with QR, then slips for details, link, configs."""
    stub = c["qr"] or c["ring"]
    line = c["time_bar"] or '<div class="bar"></div>'
    return f"""{c['alerts']}
 <section class="card tk-pass">
  <div class="tk-main">
   <div class="tk-hd"><span>{c['b']}</span><span>{c['service_txt']}</span></div>
   <div class="uname">{c['u']}</div>{c['badge']}
   <div class="tk-route"><div><small>شروع</small>{c['start']}</div><div class="tk-line">{line}</div><div><small>پایان</small>{c['end']}</div></div>
   <div class="grid tk-cols">{c['stats']}</div>{c['vol_bar']}
  </div>
  <div class="tk-stub">{stub}<button class="btn sm" data-copy="{c['sub']}" type="button">کپی لینک</button></div>
 </section>
 <section class="card"><h2>لینک اشتراک</h2>{c['sublink']}{c['imports']}</section>
 <section class="card"><h2>مشخصات</h2>{c['details']}</section>
 <section class="card"><h2>کانفیگ‌ها</h2>{c['cfgs']}</section>
 <section class="card"><h2>راهنما</h2>{c['guide']}</section>"""


def sunset(c: dict) -> str:
    """Sticky gradient sidebar (profile, ring, QR, app buttons) + content column with stats, table of configs."""
    return f"""{c['alerts']}
 <div class="sb-wrap">
  <aside class="card sb-side">{c['ring']}<div class="uname">{c['u']}</div>{c['badge']}{c['time_bar']}{c['qr']}{c['imports']}</aside>
  <main class="sb-main">
   <div class="grid sb-stats">{c['stats']}</div>
   <section class="card"><h2>لینک اشتراک</h2>{c['sublink']}</section>
   <section class="card"><h2>مشخصات اشتراک</h2><div class="sb-kv">{c['details']}</div></section>
   <section class="card"><h2>کانفیگ‌ها</h2>{_cfg_table(c)}</section>
   <section class="card"><h2>راهنمای اتصال</h2>{c['guide']}</section>
  </main>
 </div>"""


LAYOUTS = {"classic": classic, "aurora": aurora, "midnight": midnight, "paper": paper, "sunset": sunset}
