import React from "react";
import { Box, Heading, Text, SimpleGrid, Button, HStack, VStack, Input, Badge, Progress, Image, Slider, SliderTrack, SliderFilledTrack, SliderThumb, FormControl, FormLabel, Alert, AlertIcon, Code, Wrap } from "@chakra-ui/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import QRCode from "qrcode";
import type { Ctx } from "./Manage";
import type { Prefs, Mode } from "./theme";
import { DEFAULT_PREFS, hexToHsl, hslToHex, isHex } from "./theme";

const GB = 1024 ** 3;
const gb = (v: number | null | undefined) => (v == null ? "∞" : (v / GB).toFixed(2) + " GB");
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e));
const J = (m: string, b?: unknown): RequestInit => ({ method: m, body: b === undefined ? undefined : JSON.stringify(b) });

/* ---------------- color palette (build any color) ---------------- */
const SWATCHES = ["#2563eb", "#0ea5e9", "#06b6d4", "#10b981", "#84cc16", "#f59e0b", "#f97316", "#ef4444", "#ec4899", "#a855f7", "#6366f1", "#64748b"];
const BG_SWATCHES = ["#f3f5f9", "#fdf6e3", "#eef7ee", "#fdeef4", "#0f172a", "#111827", "#1a1423", "#10211b", "#000000"];

function ColorPalette({ value, fallback, onChange, swatches, c }: { value: string | null; fallback: string; onChange: (v: string | null) => void; swatches: string[]; c: Ctx }) {
  const { t } = c; const cur = value || fallback; const [h, s, l] = hexToHsl(cur);
  const [txt, setTxt] = React.useState(cur);
  React.useEffect(() => setTxt(cur), [cur]);
  const hsl = (nh: number, ns: number, nl: number) => onChange(hslToHex(nh, ns, nl));
  const track = (bg: string) => ({ background: bg, height: "10px", borderRadius: "6px" });
  return <Box>
    <HStack spacing={3} mb={3} align="center">
      <Input type="color" w="56px" h="44px" p="2px" aria-label="color" value={cur} onChange={e => onChange(e.target.value.toLowerCase())} />
      <Input className="ltr" maxW="130px" value={txt} placeholder="#2563eb" onChange={e => { setTxt(e.target.value); const v = e.target.value.trim(); if (isHex(v)) onChange(v.toLowerCase()); }} />
      <Box w="44px" h="44px" borderRadius="12px" borderWidth="1px" style={{ background: cur }} />
      {value && <Button size="sm" variant="outline" onClick={() => onChange(null)}>{t("پیش‌فرض", "Default")}</Button>}
    </HStack>
    {([[t("رنگ (Hue)", "Hue"), h, 360, (v: number) => hsl(v, s || 60, l || 50), "linear-gradient(90deg,#f00,#ff0,#0f0,#0ff,#00f,#f0f,#f00)"],
      [t("اشباع", "Saturation"), s, 100, (v: number) => hsl(h, v, l), `linear-gradient(90deg,${hslToHex(h, 0, l)},${hslToHex(h, 100, l)})`],
      [t("روشنایی", "Lightness"), l, 100, (v: number) => hsl(h, s, v), `linear-gradient(90deg,#000,${hslToHex(h, s, 50)},#fff)`]] as [string, number, number, (v: number) => void, string][]).map(([label, v, max, set, grad]) =>
      <FormControl key={label} mb={2}><FormLabel fontSize="sm" mb={1}>{label}</FormLabel>
        <Box dir="ltr" px={2}><Slider min={0} max={max} value={v} onChange={set} aria-label={label}><SliderTrack sx={track(grad)}><SliderFilledTrack bg="transparent" /></SliderTrack><SliderThumb boxSize={5} borderWidth="2px" /></Slider></Box></FormControl>)}
    <Wrap mt={2} spacing={2}>{swatches.map(sw => <Box as="button" key={sw} type="button" aria-label={sw} onClick={() => onChange(sw)} w="30px" h="30px" borderRadius="full" borderWidth={cur.toLowerCase() === sw ? "3px" : "1px"} style={{ background: sw }} />)}</Wrap>
  </Box>;
}

export function AppearanceCard({ c, prefs, setPrefs }: { c: Ctx; prefs: Prefs; setPrefs: (p: Prefs) => void }) {
  const { t } = c; const modes: [Mode, string][] = [["light", t("روشن", "Light")], ["dark", t("تیره", "Dark")], ["oled", "OLED"]];
  return <Box className="panel" mb={4}>
    <HStack justify="space-between" mb={1} flexWrap="wrap"><Heading size="md">{t("ظاهر و رنگ‌ها", "Appearance & colors")}</Heading>
      <Button size="sm" variant="outline" onClick={() => setPrefs({ ...DEFAULT_PREFS, lang: prefs.lang })}>{t("بازگشت به رنگ‌های پیش‌فرض", "Reset colors")}</Button></HStack>
    <Text className="muted" fontSize="sm" mb={4}>{t("تغییرات فوری اعمال و برای همین حساب ذخیره می‌شود؛ با رفرش و خروج/ورود پاک نمی‌شود.", "Applied instantly and saved to your account; it survives refresh and sign-out/in.")}</Text>
    <HStack mb={4} spacing={2}>{modes.map(([m, label]) => <Button key={m} size="sm" variant={prefs.theme === m ? "solid" : "outline"} colorScheme="blue" onClick={() => setPrefs({ ...prefs, theme: m })}>{label}</Button>)}</HStack>
    <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
      <Box><Text fontWeight={700} mb={2}>{t("رنگ اصلی (دکمه‌ها و تأکیدها)", "Accent color (buttons & highlights)")}</Text>
        <ColorPalette c={c} value={prefs.accent} fallback="#3182ce" swatches={SWATCHES} onChange={v => setPrefs({ ...prefs, accent: v })} /></Box>
      <Box><Text fontWeight={700} mb={2}>{t("رنگ پس‌زمینه (بقیه رنگ‌ها خودکار هماهنگ می‌شوند)", "Background (other colors adapt automatically)")}</Text>
        <ColorPalette c={c} value={prefs.bg} fallback={prefs.theme === "light" ? "#f3f5f9" : prefs.theme === "dark" ? "#0f172a" : "#000000"} swatches={BG_SWATCHES} onChange={v => setPrefs({ ...prefs, bg: v })} /></Box>
    </SimpleGrid>
  </Box>;
}

/* ---------------- 2FA ---------------- */
function TwoFactorCard({ c, enabled, left, refresh }: { c: Ctx; enabled: boolean; left: number; refresh: () => void }) {
  const { api, t, toast } = c;
  const [pw, setPw] = React.useState(""); const [code, setCode] = React.useState("");
  const [setup, setSetup] = React.useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [qr, setQr] = React.useState(""); const [codes, setCodes] = React.useState<string[] | null>(null); const [busy, setBusy] = React.useState(false);
  React.useEffect(() => { if (setup) void QRCode.toDataURL(setup.otpauth_uri, { width: 220, margin: 1 }).then(setQr); else setQr(""); }, [setup]);
  const go = async (fn: () => Promise<void>) => { setBusy(true); try { await fn(); } catch (e) { toast({ title: msg(e), status: "error" }); } finally { setBusy(false); } };
  const start = () => go(async () => { setSetup(await api("/api/admin/2fa/setup", J("POST", { password: pw }))); setPw(""); });
  const enable = () => go(async () => { const r = await api("/api/admin/2fa/enable", J("POST", { code })); setCodes(r.recovery_codes); setSetup(null); setCode(""); refresh(); });
  const disable = () => go(async () => { await api("/api/admin/2fa/disable", J("POST", { password: pw, code })); setPw(""); setCode(""); refresh(); toast({ title: t("احراز هویت دو مرحله‌ای غیرفعال شد", "Two-factor disabled"), status: "success" }); });
  return <Box className="panel" mb={4}>
    <HStack justify="space-between" mb={2}><Heading size="md">{t("احراز هویت دو مرحله‌ای (Google Authenticator)", "Two-factor authentication (Google Authenticator)")}</Heading>
      <Badge colorScheme={enabled ? "green" : "gray"}>{enabled ? t("فعال", "On") : t("غیرفعال", "Off")}</Badge></HStack>
    <Text className="muted" fontSize="sm" mb={4}>{t("اختیاری است. با فعال‌سازی، هنگام ورود علاوه بر رمز، کد ۶ رقمی برنامه هم لازم است.", "Optional. When on, sign-in also needs the 6-digit code from your authenticator app.")}</Text>
    {codes && <Alert status="warning" borderRadius="12px" mb={4} alignItems="flex-start"><AlertIcon /><Box>
      <Text fontWeight={700} mb={2}>{t("کدهای بازیابی را همین حالا ذخیره کنید؛ دیگر نمایش داده نمی‌شوند. هر کد یک‌بار مصرف است.", "Save these recovery codes now; they are shown only once. Each works one time.")}</Text>
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={2} mb={3}>{codes.map(x => <Code key={x} p={1} textAlign="center" className="ltr">{x}</Code>)}</SimpleGrid>
      <HStack><Button size="sm" onClick={() => void navigator.clipboard.writeText(codes.join("\n"))}>{t("کپی", "Copy")}</Button><Button size="sm" colorScheme="blue" onClick={() => setCodes(null)}>{t("ذخیره کردم", "I saved them")}</Button></HStack></Box></Alert>}
    {!enabled && !setup && <HStack flexWrap="wrap" align="flex-end"><FormControl maxW="260px"><FormLabel fontSize="sm">{t("رمز فعلی", "Current password")}</FormLabel><Input type="password" value={pw} onChange={e => setPw(e.target.value)} /></FormControl>
      <Button colorScheme="blue" isLoading={busy} isDisabled={!pw} onClick={start}>{t("فعال‌سازی", "Set up")}</Button></HStack>}
    {!enabled && setup && <VStack align="stretch" spacing={3}>
      <Text fontSize="sm">{t("۱) QR را در Google Authenticator اسکن کنید (یا کلید را دستی وارد کنید).  ۲) کد ۶ رقمی را وارد کنید.", "1) Scan the QR in Google Authenticator (or enter the key manually).  2) Enter the 6-digit code.")}</Text>
      {qr && <Image src={qr} alt="2FA QR" boxSize="220px" bg="white" borderRadius="12px" p={1} />}
      <Code className="ltr" p={2} borderRadius="8px" userSelect="all">{setup.secret}</Code>
      <HStack flexWrap="wrap"><Input className="ltr" maxW="180px" inputMode="numeric" autoComplete="one-time-code" placeholder="123456" value={code} onChange={e => setCode(e.target.value)} onKeyDown={e => e.key === "Enter" && void enable()} />
        <Button colorScheme="blue" isLoading={busy} isDisabled={code.replace(/\D/g, "").length !== 6} onClick={enable}>{t("تأیید و فعال‌سازی", "Verify & enable")}</Button><Button variant="outline" onClick={() => setSetup(null)}>{t("انصراف", "Cancel")}</Button></HStack></VStack>}
    {enabled && <VStack align="stretch" spacing={3}>
      <Text fontSize="sm" className="muted">{t(`کدهای بازیابی باقی‌مانده: ${left}`, `Recovery codes left: ${left}`)}</Text>
      <HStack flexWrap="wrap" align="flex-end"><FormControl maxW="240px"><FormLabel fontSize="sm">{t("رمز فعلی", "Current password")}</FormLabel><Input type="password" value={pw} onChange={e => setPw(e.target.value)} /></FormControl>
        <FormControl maxW="200px"><FormLabel fontSize="sm">{t("کد برنامه یا کد بازیابی", "App or recovery code")}</FormLabel><Input className="ltr" value={code} onChange={e => setCode(e.target.value)} /></FormControl>
        <Button colorScheme="red" isLoading={busy} isDisabled={!pw || !code} onClick={() => confirm(t("غیرفعال شود؟", "Disable 2FA?")) && void disable()}>{t("غیرفعال‌سازی", "Disable")}</Button></HStack></VStack>}
  </Box>;
}

/* ---------------- My account tab ---------------- */
function Meter({ label, value, max, text }: { label: string; value: number; max: number | null; text: string }) {
  const pct = max ? Math.min(100, (value / max) * 100) : 0;
  return <Box><HStack justify="space-between" mb={1}><Text fontSize="sm" className="muted">{label}</Text><Text fontSize="sm" className="ltr" fontWeight={600}>{text}</Text></HStack>
    <Progress value={max ? pct : 0} size="sm" borderRadius="full" colorScheme={pct > 90 ? "red" : pct > 70 ? "orange" : "blue"} /></Box>;
}
export function AccountTab({ c, prefs, setPrefs }: { c: Ctx; prefs: Prefs; setPrefs: (p: Prefs) => void }) {
  const { api, t } = c; const qc = useQueryClient();
  const q = useQuery({ queryKey: ["account"], queryFn: () => api("/api/admin/account") });
  const d = q.data; const tr = d?.traffic; const us = d?.users;
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["account"] }); void qc.invalidateQueries({ queryKey: ["me"] }); };
  const fmtDate = (v?: string | null) => (v ? new Date(v).toLocaleDateString() : "—");
  const stat = (label: string, value: React.ReactNode) => <Box className="stat" p={3}><Text fontSize="sm" className="muted">{label}</Text><Text fontSize="lg" fontWeight={700} className="ltr">{value}</Text></Box>;
  return <Box>
    <Box className="panel" mb={4}>
      <HStack justify="space-between" mb={4} flexWrap="wrap"><Heading size="md">{t("اکانت من", "My account")}</Heading><Button size="sm" onClick={() => void q.refetch()}>{t("بروزرسانی", "Refresh")}</Button></HStack>
      {q.isLoading && <Text>{t("در حال بارگذاری…", "Loading…")}</Text>}
      {q.isError && <Text color="red.400">{msg(q.error)}</Text>}
      {d && <>
        <SimpleGrid columns={{ base: 2, md: 4 }} spacing={3} mb={5}>
          {stat(t("نام کاربری", "Username"), d.username)}
          {stat(t("نقش", "Role"), d.role === "sudo" ? t("مدیر اصلی", "Sudo") : t("ادمین", "Admin"))}
          {stat(t("وضعیت", "Status"), d.disabled ? t("غیرفعال", "Disabled") : t("فعال", "Active"))}
          {stat(t("انقضای اکانت", "Account expiry"), d.expire ? `${fmtDate(d.expire)}${d.days_left != null ? ` (${d.days_left} ${t("روز", "d")})` : ""}` : t("نامحدود", "Never"))}
        </SimpleGrid>
        <SimpleGrid columns={{ base: 2, md: 4 }} spacing={3} mb={5}>
          {stat(t("حجم کل", "Total traffic"), gb(tr.total))}
          {stat(t("مصرف‌شده", "Used"), gb(tr.used))}
          {stat(t("حجم باقی‌مانده", "Remaining"), gb(tr.remaining))}
          {stat(t("قابل تخصیص به کاربر جدید", "Left to allocate"), gb(tr.unallocated))}
        </SimpleGrid>
        <VStack align="stretch" spacing={4}>
          <Meter label={t("مصرف از حجم کل", "Usage of total")} value={tr.used} max={tr.total} text={`${gb(tr.used)} / ${gb(tr.total)}`} />
          <Meter label={t("حجم تخصیص‌یافته به کاربران", "Allocated to users")} value={tr.allocated} max={tr.total} text={`${gb(tr.allocated)} / ${gb(tr.total)}`} />
          <Meter label={t("تعداد کاربران", "Users")} value={us.count} max={us.max} text={`${us.count} / ${us.max ?? "∞"}`} />
        </VStack>
        <Wrap mt={4} spacing={2}>{Object.entries(us.by_status as Record<string, number>).map(([k, v]) => <Badge key={k} colorScheme={k === "active" ? "green" : k === "disabled" ? "gray" : "orange"}>{k}: {v}</Badge>)}
          {tr.unlimited_users > 0 && <Badge colorScheme="purple">{t("کاربر نامحدود", "unlimited users")}: {tr.unlimited_users}</Badge>}</Wrap>
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={3} mt={5}>
          {stat(t("سقف حجم هر کاربر", "Per-user traffic cap"), gb(d.limits.max_user_traffic))}
          {stat(t("سقف روز هر کاربر", "Per-user max days"), d.limits.max_user_days ?? "∞")}
          {stat(t("تاریخ ساخت اکانت", "Created"), fmtDate(d.created_at))}
        </SimpleGrid>
        <Text mt={4} fontSize="sm" className="muted">{t("سرویس‌های مجاز", "Allowed services")}: {d.services.length ? d.services.map((s: any) => s.name).join("، ") : "—"}</Text>
      </>}
    </Box>
    <AppearanceCard c={c} prefs={prefs} setPrefs={setPrefs} />
    {d && <TwoFactorCard c={c} enabled={!!d.totp_enabled} left={d.recovery_codes_left || 0} refresh={refresh} />}
  </Box>;
}
