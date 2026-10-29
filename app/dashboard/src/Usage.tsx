import React from "react";
import { Box, Heading, Text, HStack, Button, Select, Input, Table, Thead, Tbody, Tr, Th, Td, SimpleGrid } from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import type { Ctx } from "./Manage";

type Row = { t: string; admin: number | null; panel: number | null; service: number | null; bytes: number };
type Data = { bucket: "day" | "hour"; total: number; rows: Row[]; admins: Record<string, string>; panels: Record<string, string>; services: Record<string, string> };
type Dim = "service" | "admin" | "panel";
const MAPS: Record<Dim, "services" | "admins" | "panels"> = { service: "services", admin: "admins", panel: "panels" };
const COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ec4899", "#8b5cf6", "#14b8a6", "#ef4444", "#84cc16", "#06b6d4", "#f97316", "#a855f7", "#64748b"];
const DAY = 86400000, HOUR = 3600000;
const key = (v: number | null) => (v == null ? "?" : String(v));

const fmt = (n: number) => {
  const u = ["B", "KB", "MB", "GB", "TB", "PB"]; let i = 0, v = Math.max(0, n);
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${i === 0 ? v : v.toFixed(2)} ${u[i]}`;
};
const pct = (a: number, b: number) => (b > 0 ? `${((a / b) * 100).toFixed(1)}%` : "0%");

/** Window in the viewer's local time; the server buckets with the same offset. */
function windowFor(range: string, from: string, to: string) {
  const off = -new Date().getTimezoneOffset(); // minutes east of UTC
  const localNow = Date.now() + off * 60000;
  let startLocal: number, endLocal: number, bucket: "day" | "hour";
  if (range === "24h") { bucket = "hour"; endLocal = Math.floor(localNow / HOUR) * HOUR + HOUR; startLocal = endLocal - 24 * HOUR; }
  else {
    bucket = "day";
    let a: number, b: number;
    if (range === "custom") { a = Date.parse(from + "T00:00:00Z"); b = Date.parse(to + "T00:00:00Z"); }
    else { b = Math.floor(localNow / DAY) * DAY; a = b - (Number(range.replace("d", "")) - 1) * DAY; }
    if (!isFinite(a) || !isFinite(b) || b < a || (b - a) / DAY > 399) return null;
    startLocal = a; endLocal = b + DAY;
  }
  const step = bucket === "hour" ? HOUR : DAY, labels: string[] = [];
  for (let x = startLocal; x < endLocal; x += step) { const s = new Date(x).toISOString(); labels.push(bucket === "hour" ? s.slice(0, 13) + ":00" : s.slice(0, 10)); }
  return { off, bucket, labels, start: new Date(startLocal - off * 60000).toISOString(), end: new Date(endLocal - off * 60000).toISOString() };
}

function Donut({ items }: { items: { label: string; bytes: number; color: string }[] }) {
  const total = items.reduce((s, i) => s + i.bytes, 0); const R = 70, C = 2 * Math.PI * R; let acc = 0;
  return <svg viewBox="0 0 200 200" style={{ width: "100%", maxWidth: 260, margin: "0 auto", display: "block", direction: "ltr" }}>
    <circle cx="100" cy="100" r={R} fill="none" stroke="var(--border)" strokeWidth="28" />
    {total > 0 && items.filter(i => i.bytes > 0).map(i => { const len = (i.bytes / total) * C; const el = <circle key={i.label} cx="100" cy="100" r={R} fill="none" stroke={i.color} strokeWidth="28" strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-acc} transform="rotate(-90 100 100)"><title>{i.label}: {fmt(i.bytes)}</title></circle>; acc += len; return el; })}
    <text x="100" y="104" textAnchor="middle" fontSize="15" fontWeight="700" fill="var(--fg)">{fmt(total)}</text>
  </svg>;
}

function Line({ labels, values, bucket }: { labels: string[]; values: number[]; bucket: "day" | "hour" }) {
  const [hi, setHi] = React.useState<number | null>(null);
  const W = 640, H = 260, L = 64, R = 12, T = 14, B = 34, max = Math.max(...values, 0);
  const step = (() => { if (max <= 0) return 1; const raw = max / 4, p = 1024 ** Math.max(0, Math.floor(Math.log(raw) / Math.log(1024))); const m = raw / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : m <= 10 ? 10 : m <= 20 ? 20 : m <= 50 ? 50 : 100) * p; })();
  const top = max <= 0 ? 1 : Math.ceil(max / step) * step; const ticks: number[] = []; for (let v = 0; v <= top + 1e-9; v += step) ticks.push(v);
  const x = (i: number) => L + (labels.length < 2 ? (W - L - R) / 2 : (i / (labels.length - 1)) * (W - L - R)); const y = (v: number) => T + (1 - v / top) * (H - T - B);
  const path = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const every = Math.max(1, Math.ceil(labels.length / 6)); const short = (s: string) => (bucket === "hour" ? s.slice(11) : s.slice(5));
  const pick = (e: React.PointerEvent<SVGSVGElement>) => { const r = e.currentTarget.getBoundingClientRect(); const px = ((e.clientX - r.left) / r.width) * W; setHi(Math.max(0, Math.min(labels.length - 1, Math.round(((px - L) / (W - L - R)) * (labels.length - 1))))); };
  return <Box style={{ direction: "ltr" }}>
    <Text fontSize="sm" className="muted" minH="22px">{hi != null ? `${labels[hi].replace("T", " ")} — ${fmt(values[hi])}` : ""}</Text>
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", touchAction: "pan-y" }} onPointerMove={pick} onPointerDown={pick} onPointerLeave={() => setHi(null)}>
      {ticks.map(v => <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--border)" /><text x={L - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--muted)">{fmt(v)}</text></g>)}
      {labels.map((l, i) => (i % every === 0 || i === labels.length - 1) && <text key={l} x={x(i)} y={H - 10} textAnchor={i === 0 ? "start" : i === labels.length - 1 ? "end" : "middle"} fontSize="11" fill="var(--muted)">{short(l)}</text>)}
      <path d={path} fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinejoin="round" />
      {hi != null && <><line x1={x(hi)} x2={x(hi)} y1={T} y2={H - B} stroke="var(--muted)" strokeDasharray="3 3" /><circle cx={x(hi)} cy={y(values[hi])} r="4" fill="#3b82f6" /></>}
    </svg></Box>;
}

function Breakdown({ title, items, total, onPick, c }: { title: string; items: { id: string; label: string; bytes: number }[]; total: number; onPick?: (id: string) => void; c: Pick<Ctx, "t"> }) {
  const colored = items.map((i, n) => ({ ...i, color: COLORS[n % COLORS.length] }));
  return <Box className="panel" p={4}>
    <Heading size="sm" mb={3}>{title}</Heading>
    <Donut items={colored} />
    <Box className="tscroll" mt={3}><Table size="sm" sx={{ minWidth: 0 }}><Tbody>{colored.map(i => <Tr key={i.id} cursor={onPick ? "pointer" : undefined} onClick={() => onPick?.(i.id)}>
      <Td><HStack spacing={2}><Box w="10px" h="10px" borderRadius="full" flex="none" bg={i.color} /><Text>{i.label}</Text></HStack></Td>
      <Td className="ltr" isNumeric>{fmt(i.bytes)}</Td><Td className="ltr" isNumeric>{pct(i.bytes, total)}</Td></Tr>)}
      {colored.length === 0 && <Tr><Td className="muted">{c.t("بدون مصرف", "No usage")}</Td></Tr>}</Tbody></Table></Box>
  </Box>;
}

export function UsageTab(c: Ctx) {
  const { api, t } = c;
  const [dim, setDim] = React.useState<Dim>("service"); const [range, setRange] = React.useState("30d");
  const today = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const [from, setFrom] = React.useState(today); const [to, setTo] = React.useState(today); const [sel, setSel] = React.useState(""); const [tick, setTick] = React.useState(0);
  const win = React.useMemo(() => windowFor(range, from, to), [range, from, to, tick]); // eslint-disable-line react-hooks/exhaustive-deps
  const q = useQuery<Data>({ queryKey: ["usage", win?.start, win?.end, win?.bucket, win?.off], enabled: !!win, queryFn: () => api(`/api/usage?start=${encodeURIComponent(win!.start)}&end=${encodeURIComponent(win!.end)}&bucket=${win!.bucket}&tz_offset=${win!.off}`) });
  const d = q.data;
  const others: Dim[] = (["service", "admin", "panel"] as Dim[]).filter(x => x !== dim);
  const dimTitle: Record<Dim, string> = { service: t("سرویس‌ها", "Services"), admin: t("ادمین‌ها", "Admins"), panel: t("نودها (پنل‌ها)", "Nodes") };
  const dimOne: Record<Dim, string> = { service: t("سرویس", "Service"), admin: t("ادمین", "Admin"), panel: t("نود", "Node") };
  const name = (dm: Dim, k: string) => (k === "?" ? t("نامشخص (قبل از ردیابی)", "Unknown (before tracking)") : d?.[MAPS[dm]][k] ?? `[deleted-${k}]`);
  const sumBy = (rows: Row[], dm: Dim) => { const m = new Map<string, number>(); rows.forEach(r => m.set(key(r[dm]), (m.get(key(r[dm])) || 0) + r.bytes)); return m; };
  const items = (rows: Row[], dm: Dim, all = false) => { const m = sumBy(rows, dm); if (all && d) Object.keys(d[MAPS[dm]]).forEach(k => { if (!m.has(k)) m.set(k, 0); }); return [...m].map(([id, bytes]) => ({ id, label: name(dm, id), bytes })).sort((a, b) => b.bytes - a.bytes || a.label.localeCompare(b.label)); };
  const rows = d?.rows || []; const total = rows.reduce((s, r) => s + r.bytes, 0);
  const scoped = sel === "" ? rows : rows.filter(r => key(r[dim]) === sel); const scopedTotal = scoped.reduce((s, r) => s + r.bytes, 0);
  const entities = items(rows, dim, true);
  const series = React.useMemo(() => { const m = new Map<string, number>(); scoped.forEach(r => m.set(r.t, (m.get(r.t) || 0) + r.bytes)); return (win?.labels || []).map(l => m.get(l) || 0); }, [scoped, win]); // eslint-disable-line react-hooks/exhaustive-deps
  const routes = (() => { const m = new Map<string, { r: Row; bytes: number }>(); scoped.forEach(r => { const k = `${key(r[dim])}|${key(r[others[0]])}|${key(r[others[1]])}`; const e = m.get(k); if (e) e.bytes += r.bytes; else m.set(k, { r, bytes: r.bytes }); }); return [...m.values()].sort((a, b) => b.bytes - a.bytes); })();
  const ranges: [string, string][] = [["24h", t("۲۴ ساعت", "24h")], ["7d", t("۷ روز", "7d")], ["30d", t("۳۰ روز", "30d")], ["90d", t("۹۰ روز", "90d")], ["custom", t("بازه دلخواه", "Custom")]];
  return <Box>
    <HStack mb={4} flexWrap="wrap" spacing={2}>{(["service", "admin", "panel"] as Dim[]).map(x => <Button key={x} colorScheme={dim === x ? "blue" : "gray"} variant={dim === x ? "solid" : "outline"} onClick={() => { setDim(x); setSel(""); }}>{dimTitle[x]}</Button>)}</HStack>
    <Box className="panel" mb={4}>
      <Heading size="md" mb={3}>{t("مصرف", "Usage")} — {dimTitle[dim]}</Heading>
      <HStack flexWrap="wrap" spacing={2} mb={3}>{ranges.map(([id, l]) => <Button key={id} size="sm" colorScheme={range === id ? "blue" : "gray"} variant={range === id ? "solid" : "outline"} onClick={() => setRange(id)}>{l}</Button>)}
        <Button size="sm" variant="outline" onClick={() => { setTick(x => x + 1); void q.refetch(); }}>{t("بروزرسانی", "Refresh")}</Button></HStack>
      {range === "custom" && <HStack mb={3} spacing={2} flexWrap="wrap"><Input type="date" maxW="180px" className="ltr" value={from} max={to} onChange={e => setFrom(e.target.value)} /><Input type="date" maxW="180px" className="ltr" value={to} min={from} max={today} onChange={e => setTo(e.target.value)} /></HStack>}
      {!win && <Text color="red.400" fontSize="sm">{t("بازه نامعتبر است (حداکثر ۴۰۰ روز).", "Invalid range (max 400 days).")}</Text>}
      {q.isError && <Text color="red.400" fontSize="sm">{String((q.error as Error)?.message)}</Text>}
      <Text className="muted" fontSize="sm">{t("جمع بازه", "Range total")}: <b className="ltr" style={{ display: "inline-block" }}>{fmt(total)}</b> · {win && `${win.labels[0].slice(0, 10)} → ${win.labels[win.labels.length - 1].slice(0, 10)}`}</Text>
      <Text className="muted" fontSize="xs" mt={1}>{t("مصرف از لحظه فعال‌شدن ردیابی نود ثبت می‌شود؛ ردیف‌های قدیمی بدون نود در «نامشخص» می‌آیند.", "Per-node tracking starts from this update; older rows without a node appear as “Unknown”.")}</Text>
    </Box>
    {d && <>
      <Breakdown c={c} title={t(`توزیع مصرف بین ${dimTitle[dim]}`, `Usage by ${dimTitle[dim]}`)} items={entities} total={total} onPick={setSel} />
      <Box className="panel" my={4}>
        <Select mb={3} value={sel} onChange={e => setSel(e.target.value)}><option value="">{t("همه", "All")} — {dimTitle[dim]}</option>{entities.map(e => <option key={e.id} value={e.id}>{e.label} — {fmt(e.bytes)}</option>)}</Select>
        <Heading size="sm" mb={1}>{t("مصرف در طول زمان", "Usage over time")}</Heading>
        <Text className="muted" fontSize="sm" mb={2}>{dimOne[dim]}: <b>{sel === "" ? t("همه", "All") : name(dim, sel)}</b> · {t("جمع", "Total")}: <span className="ltr" style={{ display: "inline-block" }}>{fmt(scopedTotal)}</span></Text>
        <Line labels={win?.labels || []} values={series} bucket={d.bucket} />
      </Box>
      <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4} mb={4}>{others.map(o => <Breakdown key={o} c={c} title={t(`${dimOne[dim]} ← ${dimTitle[o]}`, `${dimOne[dim]} → ${dimTitle[o]}`)} items={items(scoped, o)} total={scopedTotal} />)}</SimpleGrid>
      <Box className="panel"><Heading size="sm" mb={3}>{t("مسیرهای مصرف", "Traffic routes")} ({routes.length})</Heading>
        <Box className="tscroll"><Table size="sm"><Thead><Tr><Th>{dimOne[dim]}</Th><Th>{dimOne[others[0]]}</Th><Th>{dimOne[others[1]]}</Th><Th isNumeric>{t("مصرف", "Usage")}</Th><Th isNumeric>%</Th></Tr></Thead>
          <Tbody>{routes.slice(0, 300).map(({ r, bytes }) => <Tr key={`${key(r[dim])}|${key(r[others[0]])}|${key(r[others[1]])}`}><Td>{name(dim, key(r[dim]))}</Td><Td>{name(others[0], key(r[others[0]]))}</Td><Td>{name(others[1], key(r[others[1]]))}</Td><Td className="ltr" isNumeric>{fmt(bytes)}</Td><Td className="ltr" isNumeric>{pct(bytes, scopedTotal)}</Td></Tr>)}
            {routes.length === 0 && <Tr><Td colSpan={5} className="muted">{t("بدون مصرف", "No usage")}</Td></Tr>}</Tbody></Table></Box></Box>
    </>}
    {q.isLoading && <Text className="muted">{t("در حال بارگذاری…", "Loading…")}</Text>}
  </Box>;
}
