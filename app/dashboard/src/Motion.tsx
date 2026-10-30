import React from "react";

/* ------------------------------------------------------------------
 * Motion.tsx — scroll-driven background + reveal system (no dependencies)
 *
 * Performance design (this replaced a version that repainted the whole SVG on every scroll frame):
 *  • every parallax layer is its OWN <svg>; scrolling only changes `transform` on that element
 *    (compositor-only, nothing is re-rasterised);
 *  • no CSS filters, no backdrop-filter, no infinite SVG-child animations; the idle "float" is a
 *    compositor animation on a wrapper div;
 *  • colour drift = cross-fade of two pre-rendered blob layers (opacity only);
 *  • per-page look: the route (#/users, #/panels …) picks one of 5 palettes/offsets and the scene
 *    transitions to it, so the background changes when you move between pages;
 *  • honours prefers-reduced-motion and pauses when the tab is hidden.
 * ------------------------------------------------------------------ */

const hex = (cx: number, cy: number, r: number) =>
  Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 3) * i + Math.PI / 6;
    return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
  }).join(" ");
const tri = (cx: number, cy: number, r: number) =>
  [0, 1, 2].map(i => {
    const a = ((Math.PI * 2) / 3) * i - Math.PI / 2;
    return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
  }).join(" ");

const NODES: [number, number][] = [[120, 120], [300, 40], [460, 190], [260, 330], [560, 400], [90, 460], [380, 560], [700, 220]];
const EDGES: [number, number][] = [[0, 1], [1, 2], [0, 3], [2, 3], [3, 4], [2, 4], [3, 5], [5, 6], [4, 6], [2, 7], [7, 4]];

function Net({ x, y, k = 1 }: { x: number; y: number; k?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${k})`}>
      {EDGES.map(([a, b], i) => <line key={i} className="bg-edge" x1={NODES[a][0]} y1={NODES[a][1]} x2={NODES[b][0]} y2={NODES[b][1]} />)}
      {NODES.map(([nx, ny], i) => <circle key={i} className="bg-node" cx={nx} cy={ny} r={i % 3 === 0 ? 7 : 4.5} />)}
    </g>
  );
}

const Layer = ({ depth, cls = "", children, id }: { depth: number; cls?: string; children: React.ReactNode; id?: string }) => (
  <svg className={`bg-layer ${cls}`} data-depth={depth} data-id={id} style={{ "--d": depth } as React.CSSProperties}
    viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" focusable="false">{children}</svg>
);

const ORDER = ["dashboard", "users", "panels", "inbounds", "services", "templates", "admins", "usage", "actions", "live", "geo", "diagnostics", "system", "account", "guide"];
const variantOf = () => { const i = ORDER.indexOf(location.hash.replace("#/", "").replace("#", "")); return i < 0 ? 0 : i % 5; };
const lang = () => (document.documentElement.lang === "en" ? "en" : "fa");

export function BgScene() {
  const root = React.useRef<HTMLDivElement>(null);
  const bar = React.useRef<HTMLDivElement>(null);
  const top = React.useRef<HTMLButtonElement>(null);
  const [lg, setLg] = React.useState(lang());
  const [v, setV] = React.useState(variantOf());

  React.useEffect(() => {
    const mo = new MutationObserver(() => setLg(lang()));
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
    const onHash = () => setV(variantOf());
    const onVis = () => root.current?.toggleAttribute("data-paused", document.hidden);
    addEventListener("hashchange", onHash);
    document.addEventListener("visibilitychange", onVis);
    return () => { mo.disconnect(); removeEventListener("hashchange", onHash); document.removeEventListener("visibilitychange", onVis); };
  }, []);

  React.useEffect(() => {
    const el = root.current!;
    const still = matchMedia("(prefers-reduced-motion:reduce)").matches;
    const layers = [...el.querySelectorAll<SVGSVGElement>("svg[data-depth]")].map(s => ({ s, d: +(s.dataset.depth || 0) * 1100 }));
    const spinners = [...el.querySelectorAll<SVGGElement>("[data-spin]")].map(g => ({ g, k: +(g.dataset.spin || 0) }));
    const wave = el.querySelector<SVGPathElement>(".bg-wave");
    const blobA = el.querySelector<SVGSVGElement>("[data-id=blobA]");
    const blobB = el.querySelector<SVGSVGElement>("[data-id=blobB]");
    if (still) { wave?.style.setProperty("stroke-dashoffset", "0"); return; }
    let cur = 0, target = 0, raf = 0, max = 0, last = "";
    const clamp = (x: number) => Math.min(1, Math.max(0, x));
    const measure = () => { max = document.documentElement.scrollHeight - innerHeight; };
    const read = () => {
      target = max > 0 ? clamp(scrollY / max) : 0;
      top.current?.toggleAttribute("data-show", scrollY > 520);
    };
    const paint = (p: number) => {
      const key = p.toFixed(3);
      if (key === last) return;
      last = key;
      for (const l of layers) l.s.style.transform = `translate3d(0,${(-p * l.d).toFixed(1)}px,0)`;
      for (const x of spinners) x.g.style.transform = `rotate(${(p * x.k).toFixed(1)}deg)`;
      if (wave) wave.style.strokeDashoffset = (1 - clamp(p * 1.25)).toFixed(3);
      if (blobA) blobA.style.opacity = (1 - 0.7 * p).toFixed(3);
      if (blobB) blobB.style.opacity = (0.3 + 0.7 * p).toFixed(3);
      if (bar.current) bar.current.style.transform = `scaleX(${p.toFixed(4)})`;
    };
    const tick = () => {
      raf = 0;
      const d = target - cur;
      cur = Math.abs(d) < 0.001 ? target : cur + d * 0.16;
      paint(cur);
      if (cur !== target) raf = requestAnimationFrame(tick);
    };
    const kick = () => { read(); if (!raf) raf = requestAnimationFrame(tick); };
    let rt = 0;
    const remeasure = () => { clearTimeout(rt); rt = window.setTimeout(() => { measure(); kick(); }, 150); };
    measure(); paint(0); kick();
    addEventListener("scroll", kick, { passive: true });
    addEventListener("resize", remeasure);
    const ro = new ResizeObserver(remeasure); ro.observe(document.body); // page height changed (tab switch / data loaded)
    return () => { removeEventListener("scroll", kick); removeEventListener("resize", remeasure); ro.disconnect(); clearTimeout(rt); if (raf) cancelAnimationFrame(raf); };
  }, []);

  const blobs = (a: string, b: string, c: string) => (
    <>
      <circle cx="220" cy="230" r="430" fill={a} /><circle cx="1250" cy="520" r="400" fill={b} />
      <circle cx="420" cy="1150" r="470" fill={c} /><circle cx="1220" cy="1650" r="420" fill={a} /><circle cx="300" cy="2000" r="380" fill={b} />
    </>
  );

  return (
    <>
      <div className="scroll-progress" ref={bar} aria-hidden="true" />
      <div className="bg-scene" ref={root} data-v={v} aria-hidden="true">
        <svg width="0" height="0" style={{ position: "absolute" }} focusable="false">
          <defs>
            {[["A1", "--c1"], ["A2", "--c2"], ["A3", "--c3"], ["B1", "--c2"], ["B2", "--c3"], ["B3", "--c1"]].map(([id, c]) => (
              <radialGradient key={id} id={`g${id}`}>
                <stop offset="0" style={{ stopColor: `var(${c})`, stopOpacity: 0.5 }} /><stop offset="1" style={{ stopColor: `var(${c})`, stopOpacity: 0 }} />
              </radialGradient>
            ))}
            <pattern id="bgDots" width="36" height="36" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.6" className="bg-dot" /></pattern>
            <linearGradient id="bgFade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff" /><stop offset="0.5" stopColor="#fff" stopOpacity="0.35" /><stop offset="1" stopColor="#fff" /></linearGradient>
            <mask id="bgMask"><rect width="1440" height="2400" fill="url(#bgFade)" /></mask>
          </defs>
        </svg>

        <Layer depth={0.12} id="blobA" cls="blobs">{blobs("url(#gA1)", "url(#gA2)", "url(#gA3)")}</Layer>
        <Layer depth={0.12} id="blobB" cls="blobs b">{blobs("url(#gB1)", "url(#gB2)", "url(#gB3)")}</Layer>
        <Layer depth={0.22}><rect width="1440" height="2400" fill="url(#bgDots)" mask="url(#bgMask)" /></Layer>

        <Layer depth={0.4} cls="hv">
          <g data-spin="70"><g className="bg-ring"><circle cx="1130" cy="330" r="110" /><circle cx="1130" cy="330" r="190" strokeDasharray="6 12" /><circle cx="1130" cy="330" r="280" strokeDasharray="2 14" /></g></g>
          <g data-spin="-55"><g className="bg-ring"><circle cx="230" cy="1010" r="90" /><circle cx="230" cy="1010" r="170" strokeDasharray="8 10" /><circle cx="230" cy="1010" r="250" strokeDasharray="2 12" /></g></g>
          <g data-spin="40"><g className="bg-ring"><circle cx="1190" cy="1560" r="100" /><circle cx="1190" cy="1560" r="200" strokeDasharray="6 12" /></g></g>
        </Layer>

        <Layer depth={0.55} cls="hv"><Net x={640} y={130} k={0.9} /><Net x={40} y={1250} k={0.8} /><Net x={820} y={1750} k={0.85} /></Layer>

        <Layer depth={0.75}>
          <path className="bg-wave" pathLength={1}
            d="M-40 160 C 260 60, 420 330, 720 240 S 1180 80, 1500 300 S 1260 620, 900 680 S 240 760, 120 980 S 520 1260, 880 1220 S 1420 1300, 1330 1560 S 760 1760, 420 1850 S -40 2050, 200 2300" />
        </Layer>

        <div className="bg-drift">
          <Layer depth={0.95} cls="hv">
            <polygon className="bg-shape" points={hex(900, 120, 46)} /><polygon className="bg-shape fill" points={hex(150, 640, 30)} />
            <polygon className="bg-shape" points={tri(1290, 760, 40)} /><polygon className="bg-shape" points={hex(660, 980, 38)} />
            <polygon className="bg-shape fill" points={tri(980, 1200, 34)} /><polygon className="bg-shape" points={hex(1340, 1330, 52)} />
            <polygon className="bg-shape" points={tri(110, 1530, 44)} /><polygon className="bg-shape fill" points={hex(560, 1700, 32)} />
            <polygon className="bg-shape" points={hex(1010, 2000, 42)} />
            {[[520, 560], [1040, 700], [760, 1420], [200, 1830], [1250, 1960]].map(([x, y], i) => (
              <path key={i} className="bg-plus" d={`M${x - 12} ${y}H${x + 12}M${x} ${y - 12}V${y + 12}`} />
            ))}
          </Layer>
        </div>
      </div>
      <button ref={top} className="to-top" aria-label={lg === "en" ? "Back to top" : "بازگشت به بالا"}
        onClick={() => scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion:reduce)").matches ? "auto" : "smooth" })}>↑</button>
    </>
  );
}

/** Light staggered reveal + sticky header state. `dep` re-runs it (e.g. after login). */
export function useScrollMotion(dep: unknown) {
  React.useEffect(() => {
    const SEL = ".panel,.stat,.create-form,.login,.guide .chakra-accordion__item";
    const still = matchMedia("(prefers-reduced-motion:reduce)").matches;
    const timers = new Set<number>();
    const io = new IntersectionObserver(entries => {
      const vis = entries.filter(x => x.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top || a.boundingClientRect.left - b.boundingClientRect.left);
      vis.forEach((x, i) => {
        const t = x.target as HTMLElement, d = Math.min(i, 5) * 60;
        t.style.setProperty("--rv-d", `${d}ms`);
        t.setAttribute("data-rv", "in");
        io.unobserve(t);
        const id = window.setTimeout(() => { timers.delete(id); t.setAttribute("data-rv", "done"); }, 700 + d);
        timers.add(id);
      });
    }, { threshold: 0.04, rootMargin: "0px 0px -24px 0px" });
    const scan = () => document.querySelectorAll(SEL + ":not([data-rv])").forEach(el => {
      if (still) { el.setAttribute("data-rv", "done"); return; }
      el.setAttribute("data-rv", ""); io.observe(el);
    });
    scan();
    let q = 0;
    const mo = new MutationObserver(() => { if (!q) q = window.setTimeout(() => { q = 0; scan(); }, 120); }); // batch bursts of DOM changes
    mo.observe(document.body, { childList: true, subtree: true });
    let stuck = false;
    const onScroll = () => { const s = scrollY > 8; if (s !== stuck) { stuck = s; document.querySelector(".hdr")?.toggleAttribute("data-stuck", s); } };
    onScroll();
    addEventListener("scroll", onScroll, { passive: true });
    return () => { io.disconnect(); mo.disconnect(); clearTimeout(q); timers.forEach(clearTimeout); removeEventListener("scroll", onScroll); };
  }, [dep]);
}
