import { extendTheme } from "@chakra-ui/react";

export type Mode = "light" | "dark" | "oled";
export type Prefs = { lang: "fa" | "en"; theme: Mode; accent: string | null; bg: string | null };
export const DEFAULT_PREFS: Prefs = { lang: "fa", theme: "light", accent: null, bg: null };
const KEY = "subhub_prefs"; // survives refresh, logout and login on this browser
const HEX = /^#[0-9a-f]{6}$/i;

export function loadPrefs(): Prefs {
  try {
    const r = JSON.parse(localStorage.getItem(KEY) || "{}");
    return {
      lang: r.lang === "en" ? "en" : "fa",
      theme: r.theme === "dark" || r.theme === "oled" ? r.theme : "light",
      accent: HEX.test(r.accent || "") ? r.accent.toLowerCase() : null,
      bg: HEX.test(r.bg || "") ? r.bg.toLowerCase() : null,
    };
  } catch { return { ...DEFAULT_PREFS }; }
}
export function savePrefs(p: Prefs) { try { localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* storage blocked */ } }
export function normPrefs(r: any, base: Prefs): Prefs {
  return {
    lang: r?.lang === "en" || r?.lang === "fa" ? r.lang : base.lang,
    theme: r?.theme === "light" || r?.theme === "dark" || r?.theme === "oled" ? r.theme : base.theme,
    accent: r && "accent" in r ? (HEX.test(r.accent || "") ? r.accent.toLowerCase() : null) : base.accent,
    bg: r && "bg" in r ? (HEX.test(r.bg || "") ? r.bg.toLowerCase() : null) : base.bg,
  };
}

/* ---------------- color math ---------------- */
type RGB = [number, number, number];
export const hexToRgb = (h: string): RGB => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)) as RGB;
export const rgbToHex = (c: RGB) => "#" + c.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
export const mix = (a: string, b: string, t: number) => { const x = hexToRgb(a), y = hexToRgb(b); return rgbToHex([0, 1, 2].map(i => x[i] + (y[i] - x[i]) * t) as RGB); };
export function luminance(h: string) {
  const f = (v: number) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  const [r, g, b] = hexToRgb(h); return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
export const textOn = (h: string) => (luminance(h) > 0.4 ? "#111c2e" : "#ffffff");
export function hexToHsl(h: string): [number, number, number] {
  const [r, g, b] = hexToRgb(h).map(v => v / 255); const mx = Math.max(r, g, b), mn = Math.min(r, g, b); const l = (mx + mn) / 2; const d = mx - mn;
  if (!d) return [0, 0, Math.round(l * 100)];
  const s = d / (1 - Math.abs(2 * l - 1)); let hh = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  hh = (hh * 60 + 360) % 360; return [Math.round(hh), Math.round(s * 100), Math.round(l * 100)];
}
export function hslToHex(h: number, s: number, l: number) {
  s /= 100; l /= 100; const k = (n: number) => (n + h / 30) % 12; const a = s * Math.min(l, 1 - l);
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return rgbToHex([f(0) * 255, f(8) * 255, f(4) * 255]);
}
export const isHex = (v: string) => HEX.test(v);

/** 50..900 scale where 500 is exactly the picked color. */
export function scale(hex: string) {
  const L: [number, number][] = [[50, .92], [100, .82], [200, .66], [300, .46], [400, .24]];
  const D: [number, number][] = [[600, .14], [700, .28], [800, .42], [900, .56]];
  const out: Record<string, string> = { 500: hex };
  L.forEach(([k, t]) => { out[k] = mix(hex, "#ffffff", t); });
  D.forEach(([k, t]) => { out[k] = mix(hex, "#000000", t); });
  return out;
}

/* ---------------- apply to the page ---------------- */
const BASE = { light: { bg: "#f3f5f9", dark: false }, dark: { bg: "#0f172a", dark: true }, oled: { bg: "#000000", dark: true } };
/** Effective darkness (a custom background can flip it) — drives Chakra's color mode too. */
export const isDark = (p: Prefs) => (p.bg ? luminance(p.bg) < 0.4 : BASE[p.theme].dark);
const VARS = ["--bg", "--card", "--soft", "--border", "--input-border", "--fg", "--muted", "--accent", "--accent-hover", "--accent-active", "--accent-fg"];

export function applyPrefs(p: Prefs) {
  const b = document.body; b.dataset.theme = p.theme;
  VARS.forEach(v => b.style.removeProperty(v));
  if (p.bg) {
    const dark = luminance(p.bg) < 0.4;
    const set: Record<string, string> = dark
      ? { "--bg": p.bg, "--card": mix(p.bg, "#ffffff", .07), "--soft": mix(p.bg, "#000000", .25), "--border": mix(p.bg, "#ffffff", .2), "--input-border": mix(p.bg, "#ffffff", .42), "--fg": "#f1f5f9", "--muted": "#b4c0d3" }
      : { "--bg": p.bg, "--card": mix(p.bg, "#ffffff", .7), "--soft": mix(p.bg, "#000000", .04), "--border": mix(p.bg, "#000000", .14), "--input-border": mix(p.bg, "#000000", .42), "--fg": "#111c2e", "--muted": "#475569" };
    Object.entries(set).forEach(([k, v]) => b.style.setProperty(k, v));
  }
  if (p.accent) {
    b.style.setProperty("--accent", p.accent); b.style.setProperty("--accent-hover", mix(p.accent, "#000000", .14));
    b.style.setProperty("--accent-active", mix(p.accent, "#000000", .28)); b.style.setProperty("--accent-fg", textOn(p.accent));
  }
}

/** Chakra theme: `blue` (the color scheme used everywhere) follows the picked accent. */
export function buildTheme(p: Prefs) {
  return extendTheme({
    config: { initialColorMode: "light", useSystemColorMode: false },
    fonts: { body: "Vazirmatn, Tahoma, 'Segoe UI', system-ui, sans-serif", heading: "Vazirmatn, Tahoma, 'Segoe UI', system-ui, sans-serif" },
    styles: { global: { body: { bg: "var(--bg)", color: "var(--fg)" } } },
    ...(p.accent ? { colors: { blue: scale(p.accent) } } : {}),
    components: {
      Button: {
        baseStyle: { borderRadius: "12px", fontWeight: 600 },
        variants: p.accent ? { solid: (props: any) => props.colorScheme === "blue"
          ? { bg: "var(--accent)", color: "var(--accent-fg)", _hover: { bg: "var(--accent-hover)", _disabled: { bg: "var(--accent)" } }, _active: { bg: "var(--accent-active)" } } : {} } : {},
      },
      Input: { defaultProps: { size: "md" } },
    },
  });
}
