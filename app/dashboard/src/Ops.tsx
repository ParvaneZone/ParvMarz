import React from "react";
import { Box, Heading, Text, HStack, Button, Table, Thead, Tbody, Tr, Th, Td, Badge, SimpleGrid } from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import type { Ctx } from "./Manage";

const fmt = (n: number | null | undefined) => { if (n == null) return "∞"; const u = ["B", "KB", "MB", "GB", "TB", "PB"]; let i = 0, x = n; while (x >= 1024 && i < 5) { x /= 1024; i++; } return x.toFixed(i ? 2 : 0) + " " + u[i]; };
const when = (s: string | null) => (s ? new Date(s).toLocaleString() : "—");
const PAGE = 50;

/* ---------- Recent actions (audit log) ---------- */
export function ActionsTab({ api, t }: Ctx) {
  const [page, setPage] = React.useState(0);
  const q = useQuery({ queryKey: ["actions", page], queryFn: () => api(`/api/system/audit?limit=${PAGE}&offset=${page * PAGE}`), refetchInterval: 15000 });
  const admins = useQuery({ queryKey: ["admins"], queryFn: () => api("/api/admins") });
  const who = (id: number | null) => (id == null ? "—" : (admins.data || []).find((a: any) => a.id === id)?.username ?? `[deleted-${id}]`);
  const items: any[] = q.data?.items || [];
  return <Box className="panel">
    <HStack justify="space-between" mb={4} flexWrap="wrap"><Heading size="md">{t("اقدامات اخیر", "Recent actions")}</Heading><Button size="sm" variant="outline" onClick={() => void q.refetch()}>{t("بروزرسانی", "Refresh")}</Button></HStack>
    <Box className="tscroll"><Table size="sm"><Thead><Tr><Th>{t("زمان", "Time")}</Th><Th>{t("ادمین", "Admin")}</Th><Th>{t("اقدام", "Action")}</Th><Th>{t("مورد", "Object")}</Th><Th>{t("جزئیات", "Details")}</Th></Tr></Thead>
      <Tbody>{items.map(x => <Tr key={x.id}><Td className="ltr">{when(x.created_at)}</Td><Td>{who(x.actor_admin_id)}</Td><Td className="ltr">{x.action}</Td><Td className="ltr">{x.object_type}:{x.object_id}</Td><Td className="ltr" fontSize="xs">{JSON.stringify(x.details || {})}</Td></Tr>)}
        {!q.isLoading && items.length === 0 && <Tr><Td colSpan={5} className="muted">{t("موردی نیست", "Nothing here")}</Td></Tr>}</Tbody></Table></Box>
    <HStack mt={3} justify="center"><Button size="sm" isDisabled={page === 0} onClick={() => setPage(page - 1)}>{t("قبلی", "Prev")}</Button><Text className="muted" fontSize="sm">{page + 1}</Text><Button size="sm" isDisabled={items.length < PAGE} onClick={() => setPage(page + 1)}>{t("بعدی", "Next")}</Button></HStack>
  </Box>;
}

/* ---------- Live connections (online users) ---------- */
export function LiveTab({ api, t }: Ctx) {
  const q = useQuery({ queryKey: ["online"], queryFn: () => api("/api/system/online"), refetchInterval: 10000 });
  const d = q.data; const items: any[] = d?.items || [];
  return <Box className="panel">
    <HStack justify="space-between" mb={1} flexWrap="wrap"><Heading size="md">{t("اتصالات زنده", "Live connections")} ({d?.count ?? 0})</Heading><Button size="sm" variant="outline" onClick={() => void q.refetch()}>{t("بروزرسانی", "Refresh")}</Button></HStack>
    <Text className="muted" fontSize="sm" mb={3}>{t("کاربرانی که در ۳ دقیقه اخیر مصرف داشته‌اند (هر ۱۰ ثانیه بروز می‌شود).", "Users with traffic in the last 3 minutes (refreshes every 10s).")}</Text>
    <Box className="tscroll"><Table size="sm"><Thead><Tr><Th>{t("کاربر", "User")}</Th><Th>{t("ادمین", "Admin")}</Th><Th>{t("سرویس", "Service")}</Th><Th>{t("مصرف", "Usage")}</Th><Th>{t("آخرین فعالیت", "Last seen")}</Th></Tr></Thead>
      <Tbody>{items.map(u => <Tr key={u.username}><Td className="ltr">{u.username}</Td><Td>{u.admin}</Td><Td>{u.service}</Td><Td className="ltr">{fmt(u.used_traffic)} / {fmt(u.data_limit)}</Td><Td className="ltr">{when(u.online_at)}</Td></Tr>)}
        {!q.isLoading && items.length === 0 && <Tr><Td colSpan={5} className="muted">{t("الان کسی آنلاین نیست", "Nobody online right now")}</Td></Tr>}</Tbody></Table></Box>
  </Box>;
}

/* ---------- Diagnostics ---------- */
export function DiagnosticsTab({ api, t }: Ctx) {
  const q = useQuery({ queryKey: ["diagnostics"], queryFn: () => api("/api/system/diagnostics"), refetchInterval: 15000 });
  const d = q.data; if (!d) return <Box className="panel"><Text>{t("در حال بارگذاری…", "Loading…")}</Text></Box>;
  const st = d.sync_tasks || {};
  return <Box className="panel">
    <HStack justify="space-between" mb={3} flexWrap="wrap"><Heading size="md">{t("عیب‌یابی", "Diagnostics")}</Heading><Button size="sm" variant="outline" onClick={() => void q.refetch()}>{t("بروزرسانی", "Refresh")}</Button></HStack>
    <SimpleGrid columns={{ base: 3 }} spacing={3} mb={4}>{[["pending", t("در انتظار", "Pending")], ["failed", t("ناموفق", "Failed")], ["done", t("انجام‌شده", "Done")]].map(([k, l]) => <Box key={k} className="stat" p={3} borderWidth="1px" borderRadius="12px"><Text fontSize="sm" className="muted">{l}</Text><Heading size="md">{st[k] ?? 0}</Heading></Box>)}</SimpleGrid>
    <Heading size="sm" mb={2}>{t("سلامت پنل‌ها", "Panel health")}</Heading>
    <Box className="tscroll" mb={5}><Table size="sm"><Thead><Tr><Th>{t("نام", "Name")}</Th><Th>{t("نوع", "Type")}</Th><Th>{t("وضعیت", "Status")}</Th><Th>{t("آخرین موفقیت", "Last OK")}</Th><Th>{t("خطا", "Error")}</Th></Tr></Thead>
      <Tbody>{d.panels.map((p: any) => <Tr key={p.id}><Td>{p.name}</Td><Td>{p.type}</Td><Td><Badge colorScheme={!p.enabled ? "gray" : p.status === "healthy" ? "green" : "red"}>{p.enabled ? p.status : t("غیرفعال", "disabled")}</Badge></Td><Td className="ltr">{when(p.last_ok_at)}</Td><Td className="ltr" fontSize="xs">{p.last_error || "—"}</Td></Tr>)}</Tbody></Table></Box>
    <Heading size="sm" mb={2}>{t("تسک‌های ناموفق (۵۰ مورد آخر)", "Failed tasks (last 50)")}</Heading>
    <Box className="tscroll"><Table size="sm"><Thead><Tr><Th>#</Th><Th>{t("پنل", "Panel")}</Th><Th>{t("عملیات", "Action")}</Th><Th>{t("تلاش", "Attempts")}</Th><Th>{t("خطا", "Error")}</Th><Th>{t("زمان", "Time")}</Th></Tr></Thead>
      <Tbody>{d.failed_tasks.map((x: any) => <Tr key={x.id}><Td>{x.id}</Td><Td>{x.panel}</Td><Td className="ltr">{x.action}</Td><Td>{x.attempts}</Td><Td className="ltr" fontSize="xs">{x.last_error || "—"}</Td><Td className="ltr">{when(x.created_at)}</Td></Tr>)}
        {d.failed_tasks.length === 0 && <Tr><Td colSpan={6} className="muted">{t("تسک ناموفقی نیست", "No failed tasks")}</Td></Tr>}</Tbody></Table></Box>
  </Box>;
}
