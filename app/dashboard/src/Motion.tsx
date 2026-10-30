import React from "react";

/* ------------------------------------------------------------------
 * Motion.tsx — scroll-driven background + reveal system (no dependencies)
 *
 *  • <BgScene/>        fixed SVG background: glowing blobs, dot grid, rings, a
 *                      network graph, a wave that "draws itself" and floating
 *                      shapes. Each layer moves at its own speed (parallax) and
 *                      the colours drift with scroll progress (scrub).
 *  • useScrollMotion() staggered reveal of panels/cards as they enter the screen
 *                      + sticky-header state.
 *
 *  Everything honours prefers-reduced-motion and uses the theme variables
 *  (--accent, --bg) so it follows light / dark / OLED / custom colours.
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
      {EDGES.map(([a, b], i) => (
        <line key={i} className="bg-edge" x1={NODES[a][0]} y1={NODES[a][1]} x2={NODES[b][0]} y2={NODES[b][1]} />
      ))}
      {NODES.map(([nx, ny], i) => (
        <circle key={i} className="bg-node" cx={nx} cy={ny} r={i % 3 === 0 ? 7 : 4.5} style={{ animationDelay: `${(i * 0.45).toFixed(2)}s` }} />
      ))}
    </g>
  );
}

const lang = () => (document.documentElement.lang === "en" ? "en" : "fa");

export function BgScene() {
  const root = React.useRef<HTMLDivElement>(null);
  const bar = React.useRef<HTMLDivElement>(null);
  const top = React.useRef<HTMLButtonElement>(null);
  const [lg, setLg] = React.useState(lang());

  React.useEffect(() => {
    const mo = new MutationObserver(() => setLg(lang()));
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
    return () => mo.disconnect();
  }, []);

  React.useEffect(() => {
    const el = root.current!;
    const still = matchMedia("(prefers-reduced-motion:reduce)").matches;
    const layers = [...el.querySelectorAll<SVGGElement>("[data-depth]")];
    const spinners = [...el.querySelectorAll<SVGGElement>("[data-spin]")];
    const wave = el.querySelector<SVGPathElement>(".bg-wave");
    if (still) { // static scene: wave fully drawn, nothing moves
      wave?.style.setProperty("stroke-dashoffset", "0");
      return;
    }
    let cur = 0, target = 0, raf = 0;
    const clamp = (v: number) => Math.min(1, Math.max(0, v));
    const read = () => {
      const max = document.documentElement.scrollHeight - innerHeight;
      target = max > 0 ? clamp(scrollY / max) : 0;
      top.current?.toggleAttribute("data-show", scrollY > 520);
    };
    const paint = (p: number) => {
      layers.forEach(g => { g.style.transform = `translate(0px,${(-p * +(g.dataset.depth || 0) * 1100).toFixed(1)}px)`; });
      spinners.forEach(g => { g.style.transform = `rotate(${(p * +(g.dataset.spin || 0)).toFixed(2)}deg)`; });
      if (wave) wave.style.strokeDashoffset = String((1 - clamp(p * 1.25)).toFixed(4));
      el.style.setProperty("--hue", `${(p * 70).toFixed(1)}deg`);
      if (bar.current) bar.current.style.transform = `scaleX(${p.toFixed(4)})`;
    };
    const tick = () => {
      raf = 0;
      const d = target - cur;
      cur = Math.abs(d) < 0.0005 ? target : cur + d * 0.12; // smoothed "scrub"
      paint(cur);
      if (cur !== target) raf = requestAnimationFrame(tick);
    };
    const kick = () => { read(); if (!raf) raf = requestAnimationFrame(tick); };
    paint(0); kick();
    addEventListener("scroll", kick, { passive: true });
    addEventListener("resize", kick);
    const ro = new ResizeObserver(kick); ro.observe(document.body); // tab switch / data loaded → page height changed
    return () => { removeEventListener("scroll", kick); removeEventListener("resize", kick); ro.disconnect(); if (raf) cancelAnimationFrame(raf); };
  }, []);

  return (
    <>
      <div className="scroll-progress" ref={bar} aria-hidden="true" />
      <div className="bg-scene" ref={root} aria-hidden="true">
        <svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" focusable="false">
          <defs>
            <radialGradient id="bgA"><stop offset="0" style={{ stopColor: "var(--accent,#3b82f6)", stopOpacity: 0.55 }} /><stop offset="1" style={{ stopColor: "var(--accent,#3b82f6)", stopOpacity: 0 }} /></radialGradient>
            <radialGradient id="bgB"><stop offset="0" style={{ stopColor: "#22d3ee", stopOpacity: 0.5 }} /><stop offset="1" style={{ stopColor: "#22d3ee", stopOpacity: 0 }} /></radialGradient>
            <radialGradient id="bgC"><stop offset="0" style={{ stopColor: "#a78bfa", stopOpacity: 0.5 }} /><stop offset="1" style={{ stopColor: "#a78bfa", stopOpacity: 0 }} /></radialGradient>
            <pattern id="bgDots" width="36" height="36" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.6" className="bg-dot" /></pattern>
            <linearGradient id="bgFade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff" /><stop offset="0.5" stopColor="#fff" stopOpacity="0.35" /><stop offset="1" stopColor="#fff" /></linearGradient>
            <mask id="bgMask"><rect width="1440" height="2400" fill="url(#bgFade)" /></mask>
          </defs>

          {/* 1 · soft glowing blobs — colour drifts with scroll */}
          <g className="bg-blobs" data-depth="0.12">
            <circle className="bg-float f1" cx="220" cy="230" r="430" fill="url(#bgA)" />
            <circle className="bg-float f2" cx="1250" cy="520" r="400" fill="url(#bgB)" />
            <circle className="bg-float f3" cx="420" cy="1150" r="470" fill="url(#bgC)" />
            <circle className="bg-float f1" cx="1220" cy="1650" r="420" fill="url(#bgA)" />
            <circle className="bg-float f2" cx="300" cy="2000" r="380" fill="url(#bgB)" />
          </g>

          {/* 2 · dot grid */}
          <g data-depth="0.22"><rect width="1440" height="2400" fill="url(#bgDots)" mask="url(#bgMask)" /></g>

          {/* 3 · rings that rotate as you scroll */}
          <g data-depth="0.4">
            <g data-spin="70"><g className="bg-ring"><circle cx="1130" cy="330" r="110" /><circle cx="1130" cy="330" r="190" strokeDasharray="6 12" /><circle cx="1130" cy="330" r="280" strokeDasharray="2 14" /></g></g>
            <g data-spin="-55"><g className="bg-ring"><circle cx="230" cy="1010" r="90" /><circle cx="230" cy="1010" r="170" strokeDasharray="8 10" /><circle cx="230" cy="1010" r="250" strokeDasharray="2 12" /></g></g>
            <g data-spin="40"><g className="bg-ring"><circle cx="1190" cy="1560" r="100" /><circle cx="1190" cy="1560" r="200" strokeDasharray="6 12" /></g></g>
          </g>

          {/* 4 · network graph */}
          <g data-depth="0.55">
            <Net x={640} y={130} k={0.9} />
            <Net x={40} y={1250} k={0.8} />
            <Net x={820} y={1750} k={0.85} />
          </g>

          {/* 5 · wave that draws itself while you scroll */}
          <g data-depth="0.75">
            <path className="bg-wave" pathLength={1}
              d="M-40 160 C 260 60, 420 330, 720 240 S 1180 80, 1500 300 S 1260 620, 900 680 S 240 760, 120 980 S 520 1260, 880 1220 S 1420 1300, 1330 1560 S 760 1760, 420 1850 S -40 2050, 200 2300" />
          </g>

          {/* 6 · floating shapes (fastest layer) */}
          <g data-depth="0.95">
            <g className="bg-float f1"><polygon className="bg-shape" points={hex(900, 120, 46)} /></g>
            <g className="bg-float f2"><polygon className="bg-shape fill" points={hex(150, 640, 30)} /></g>
            <g className="bg-float f3"><polygon className="bg-shape" points={tri(1290, 760, 40)} /></g>
            <g className="bg-float f2"><polygon className="bg-shape" points={hex(660, 980, 38)} /></g>
            <g className="bg-float f1"><polygon className="bg-shape fill" points={tri(980, 1200, 34)} /></g>
            <g className="bg-float f3"><polygon className="bg-shape" points={hex(1340, 1330, 52)} /></g>
            <g className="bg-float f2"><polygon className="bg-shape" points={tri(110, 1530, 44)} /></g>
            <g className="bg-float f1"><polygon className="bg-shape fill" points={hex(560, 1700, 32)} /></g>
            <g className="bg-float f3"><polygon className="bg-shape" points={hex(1010, 2000, 42)} /></g>
            {[[520, 560], [1040, 700], [760, 1420], [200, 1830], [1250, 1960]].map(([x, y], i) => (
              <path key={i} className="bg-plus" d={`M${x - 12} ${y}H${x + 12}M${x} ${y - 12}V${y + 12}`} />
            ))}
          </g>
        </svg>
      </div>
      <button ref={top} className="to-top" aria-label={lg === "en" ? "Back to top" : "بازگشت به بالا"}
        onClick={() => scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion:reduce)").matches ? "auto" : "smooth" })}>↑</button>
    </>
  );
}

/** Staggered scroll reveal + sticky header state. `dep` re-runs it (e.g. after login). */
export function useScrollMotion(dep: unknown) {
  React.useEffect(() => {
    const SEL = ".panel,.stat,.create-form,.login,.guide .chakra-accordion__item";
    const still = matchMedia("(prefers-reduced-motion:reduce)").matches;
    const io = new IntersectionObserver(entries => {
      const vis = entries.filter(x => x.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top || a.boundingClientRect.left - b.boundingClientRect.left);
      vis.forEach((x, i) => {
        const t = x.target as HTMLElement;
        t.style.setProperty("--rv-d", `${Math.min(i, 6) * 80}ms`); // stagger items that appear together
        t.setAttribute("data-rv", "in");
        t.addEventListener("transitionend", function done(e) {
          if (e.propertyName !== "transform") return;
          t.removeEventListener("transitionend", done);
          t.setAttribute("data-rv", "done"); // drop the delay so hover/other transitions are not slowed
        });
        io.unobserve(t);
      });
    }, { threshold: 0.06, rootMargin: "0px 0px -32px 0px" });
    const scan = () => document.querySelectorAll(SEL + ":not([data-rv])").forEach(el => {
      if (still) { el.setAttribute("data-rv", "in"); return; }
      el.setAttribute("data-rv", ""); io.observe(el);
    });
    scan();
    const mo = new MutationObserver(scan);
    mo.observe(document.body, { childList: true, subtree: true });
    const onScroll = () => document.querySelector(".hdr")?.toggleAttribute("data-stuck", scrollY > 8);
    onScroll();
    addEventListener("scroll", onScroll, { passive: true });
    return () => { io.disconnect(); mo.disconnect(); removeEventListener("scroll", onScroll); };
  }, [dep]);
}
