import React from "react";
import { Box, Heading, Text, Table, Thead, Tbody, Tr, Th, Td, Badge, Button, HStack, Progress, SimpleGrid, Checkbox, Modal, ModalOverlay, ModalContent, ModalHeader, ModalCloseButton, ModalBody } from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import type { Ctx } from "./Manage";
import { copyText } from "./copy";
import { useConfirm } from "./ConfirmModal";

export type UserRow = { id: number; username: string; admin_id: number; service_id: number; status: string; data_limit: number | null; used_traffic: number; expire: string | null; note: string; subscription_url: string | null; created_at?: string };

const GB = 1024 ** 3;
const gb = (n: number) => (n / GB).toFixed(2);
const tone = (s: string) => (s === "active" ? "green" : s === "limited" || s === "expired" ? "red" : s === "on_hold" ? "orange" : "gray");
/** Backend datetimes may come without a timezone (SQLite); they are UTC. */
const parse = (v?: string | null) => (v ? new Date(/(Z|[+-]\d\d:?\d\d)$/i.test(v) ? v : v + "Z") : null);
const fmt = (v?: string | null) => { const d = parse(v); return d && !isNaN(+d) ? d.toLocaleString() : ""; };

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return <HStack justify="space-between" align="flex-start" py={2} borderBottomWidth="1px" borderStyle="dashed" spacing={4}>
    <Text className="muted" fontSize="sm" flexShrink={0}>{k}</Text><Text fontWeight={600} fontSize="sm" textAlign="end" wordBreak="break-word">{children}</Text></HStack>;
}

type Props = { c: Ctx; loading: boolean; items: UserRow[]; isSudo: boolean; can: (k: string) => boolean; sel: number[]; setSel: (v: number[]) => void; stLabel: (s: string) => string; subUrl: (u: { subscription_url: string | null }) => string; onEdit: (u: any) => void; onQr: (url: string) => void; action: (path: string, method?: string) => Promise<void>; meName?: string };

export function UsersList({ c, loading, items, isSudo, can, sel, setSel, stLabel, subUrl, onEdit, onQr, action, meName }: Props) {
  const { t, toast, api } = c;
  const [openId, setOpenId] = React.useState<number | null>(null);
  const [ask, confirmNode] = useConfirm(t);
  const admins = useQuery({ queryKey: ["admins"], queryFn: () => api("/api/admins"), enabled: isSudo });
  const svcs = useQuery({ queryKey: ["services"], queryFn: () => api("/api/services") });
  const online = useQuery({ queryKey: ["users-online"], queryFn: () => api("/api/users/online"), refetchInterval: 30000 });
  const u = items.find(x => x.id === openId) || null;
  const owner = (id: number) => (isSudo ? (admins.data || []).find((a: any) => a.id === id)?.username : meName) ?? `#${id}`;
  const svcName = (id: number) => { const s = (svcs.data || []).find((x: any) => x.id === id); return s ? (s.display_name || s.name) : `#${id}`; };
  const seen = (id: number): string | null | undefined => online.data?.items?.[String(id)];
  const isOnline = (id: number) => { const d = parse(seen(id)); return !!d && Date.now() - +d < 3 * 60 * 1000; };
  const pct = (x: UserRow) => (x.data_limit ? Math.min(100, (x.used_traffic / x.data_limit) * 100) : 0);
  const bar = (x: UserRow) => (pct(x) > 90 ? "red" : pct(x) > 70 ? "orange" : "blue");
  const usage = (x: UserRow) => `${gb(x.used_traffic)} / ${x.data_limit == null ? "∞" : gb(x.data_limit)} GB`;
  const daysLeft = (x: UserRow) => { const d = parse(x.expire); return d ? Math.ceil((+d - Date.now()) / 86400000) : null; };
  const enc = (x: UserRow) => `/api/user/${encodeURIComponent(x.username)}`;
  const run = (fn: () => void) => { setOpenId(null); fn(); };

  if (loading) return <Text>{t("در حال بارگذاری…", "Loading…")}</Text>;
  if (!items.length) return <Text className="muted">{t("کاربری پیدا نشد.", "No users found.")}</Text>;
  return <>
    {confirmNode}
    <Text className="muted" fontSize="sm" mb={2}>{t("برای جزئیات و عملیات، روی هر کاربر ضربه بزنید.", "Tap a user for details and actions.")}</Text>
    <Box className="tscroll"><Table size="sm"><Thead><Tr>{isSudo && <Th w="1%" />}<Th>{t("نام کاربری", "Username")}</Th><Th>{t("وضعیت", "Status")}</Th><Th>{t("مصرف", "Usage")}</Th><Th display={{ base: "none", md: "table-cell" }}>{t("انقضا", "Expires")}</Th></Tr></Thead>
      <Tbody>{items.map(x => <Tr key={x.id} cursor="pointer" _hover={{ bg: "blackAlpha.50", _dark: { bg: "whiteAlpha.100" } }} onClick={() => setOpenId(x.id)}>
        {isSudo && <Td onClick={e => e.stopPropagation()}><Checkbox isChecked={sel.includes(x.id)} onChange={e => setSel(e.target.checked ? [...sel, x.id] : sel.filter(i => i !== x.id))} /></Td>}
        <Td fontWeight={600} className="ltr">{x.username}{isOnline(x.id) && <Badge ms={2} colorScheme="green">{t("آنلاین", "online")}</Badge>}</Td>
        <Td><Badge colorScheme={tone(x.status)}>{stLabel(x.status)}</Badge></Td>
        <Td minW="150px"><Text fontSize="sm" className="ltr">{usage(x)}</Text><Progress mt={1} value={pct(x)} size="xs" borderRadius="full" colorScheme={bar(x)} /></Td>
        <Td display={{ base: "none", md: "table-cell" }} className="ltr">{x.expire ? parse(x.expire)!.toLocaleDateString() : "—"}</Td></Tr>)}</Tbody></Table></Box>
    <Modal isOpen={!!u} onClose={() => setOpenId(null)} isCentered scrollBehavior="inside"><ModalOverlay />
      {u && <ModalContent mx={3}><ModalHeader pb={1}><HStack spacing={3} flexWrap="wrap"><Heading size="md" className="ltr" wordBreak="break-all">{u.username}</Heading><Badge colorScheme={tone(u.status)}>{stLabel(u.status)}</Badge>{isOnline(u.id) && <Badge colorScheme="green">{t("آنلاین", "online")}</Badge>}</HStack></ModalHeader><ModalCloseButton />
        <ModalBody pb={5}>
          <Box mb={3}><HStack justify="space-between" mb={1}><Text className="muted" fontSize="sm">{t("مصرف", "Usage")}</Text><Text fontSize="sm" fontWeight={600} className="ltr">{usage(u)}</Text></HStack><Progress value={pct(u)} size="sm" borderRadius="full" colorScheme={bar(u)} />
            {u.data_limit != null && <Text className="muted ltr" fontSize="xs" mt={1}>{t("باقی‌مانده: ", "Remaining: ")}{gb(Math.max(0, u.data_limit - u.used_traffic))} GB</Text>}</Box>
          <Row k={t("ساخته‌شده توسط ادمین", "Created by admin")}>{owner(u.admin_id)}</Row>
          <Row k={t("سرویس", "Service")}>{svcName(u.service_id)}</Row>
          <Row k={t("آخرین آنلاین", "Last online")}>{isOnline(u.id) ? t("همین الان", "Now") : fmt(seen(u.id)) || t("هنوز متصل نشده", "Never")}</Row>
          <Row k={t("تاریخ ساخت", "Created")}>{fmt(u.created_at) || "—"}</Row>
          <Row k={t("انقضا", "Expires")}>{u.expire ? `${parse(u.expire)!.toLocaleDateString()} (${daysLeft(u)} ${t("روز", "d")})` : t("نامحدود", "Never")}</Row>
          {u.note && <Row k={t("یادداشت", "Note")}>{u.note}</Row>}
          {can("users.edit") && <Button mt={4} w="100%" h="46px" colorScheme="blue" onClick={() => run(() => onEdit(u))}>{t("ویرایش کاربر", "Edit user")}</Button>}
          <SimpleGrid columns={2} spacing={2} mt={2}>
            {u.subscription_url && <Button h="44px" variant="outline" onClick={() => void copyText(subUrl(u)).then(ok => toast({ title: ok ? t("کپی شد", "Copied") : t("کپی نشد", "Copy failed"), status: ok ? "success" : "error", duration: 1500 }))}>{t("کپی لینک", "Copy link")}</Button>}
            {u.subscription_url && <Button h="44px" variant="outline" onClick={() => run(() => onQr(subUrl(u)))}>QR</Button>}
            {can("users.reset") && <Button h="44px" variant="outline" onClick={() => ask({ title: t("مصرف ریست شود؟", "Reset usage?"), body: u.username, danger: true, confirmLabel: t("ریست مصرف", "Reset usage") }, () => void action(`${enc(u)}/reset`))}>{t("ریست مصرف", "Reset usage")}</Button>}
            {can("users.revoke_sub") && <Button h="44px" variant="outline" onClick={() => ask({ title: t("لینک اشتراک ابطال شود؟", "Revoke subscription link?"), body: u.username, danger: true, confirmLabel: t("ابطال لینک", "Revoke link") }, () => void action(`${enc(u)}/revoke_sub`))}>{t("ابطال لینک", "Revoke link")}</Button>}
          </SimpleGrid>
          {can("users.delete") && <Button mt={5} w="100%" h="44px" variant="outline" colorScheme="red" onClick={() => ask({ title: t("کاربر حذف شود؟", "Delete user?"), body: u.username, danger: true, confirmLabel: t("حذف", "Delete") }, () => run(() => void action(enc(u), "DELETE")))}>{t("حذف کاربر", "Delete user")}</Button>}
        </ModalBody></ModalContent>}
    </Modal>
  </>;
}
