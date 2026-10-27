import React from "react";
import { Box, Heading, Text, Table, Thead, Tbody, Tr, Th, Td, Badge, Button, HStack, Input, Select, FormControl, FormLabel, Textarea, Switch, SimpleGrid, Modal, ModalOverlay, ModalContent, ModalHeader, ModalCloseButton, ModalBody, Checkbox } from "@chakra-ui/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

export type Ctx = { api: (p: string, i?: RequestInit) => Promise<any>; t: (fa: string, en: string) => string; toast: (o: any) => void };
const GB = 1024 ** 3;
const J = (m: string, b?: unknown): RequestInit => ({ method: m, body: b === undefined ? undefined : JSON.stringify(b) });
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e));

function useRun({ api, t, toast }: Ctx, keys: string[]) {
  const qc = useQueryClient();
  return async (path: string, init: RequestInit, after?: () => void) => {
    try { const r = await api(path, init); await Promise.all(keys.map(k => qc.invalidateQueries({ queryKey: [k] }))); toast({ title: t("انجام شد", "Done"), status: "success" }); after?.(); return r; }
    catch (e) { toast({ title: msg(e), status: "error" }); }
  };
}
const F = ({ label, children }: { label: string; children: React.ReactNode }) => <FormControl><FormLabel>{label}</FormLabel>{children}</FormControl>;
const num = (v: string) => (v === "" ? null : Number(v));

/* ---------------- Panels ---------------- */
export function PanelsTab(c: Ctx) {
  const { api, t } = c; const run = useRun(c, ["panels"]);
  const q = useQuery({ queryKey: ["panels"], queryFn: () => api("/api/panels") });
  const empty = { name: "", type: "marzban", base_url: "", username: "", password: "", verify_ssl: true, enabled: true, username_prefix: "", sync_interval: 60 };
  const [f, setF] = React.useState<any>(null); const [editId, setEditId] = React.useState<number | null>(null);
  const [inb, setInb] = React.useState<any[] | null>(null);
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const save = () => run(editId ? `/api/panels/${editId}` : "/api/panels", J(editId ? "PUT" : "POST", { ...f, sync_interval: Number(f.sync_interval) }), () => { setF(null); setEditId(null); });
  return <Box className="panel">
    <HStack justify="space-between" mb={4}><Heading size="md">{t("پنل‌های بالادستی", "Upstream panels")}</Heading><Button colorScheme="blue" onClick={() => { setEditId(null); setF(empty); }}>{t("افزودن پنل", "Add panel")}</Button></HStack>
    {f && <Box className="create-form" mb={4}><SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
      <F label={t("نام", "Name")}><Input value={f.name} onChange={e => set("name", e.target.value)} /></F>
      <F label={t("نوع", "Type")}><Select value={f.type} onChange={e => set("type", e.target.value)}>{["marzban", "marzdar", "marzyar", "pasarguard", "rebecca"].map(x => <option key={x}>{x}</option>)}</Select></F>
      <F label="URL"><Input className="ltr" value={f.base_url} onChange={e => set("base_url", e.target.value)} placeholder="https://panel.example.com" /></F>
      <F label={t("پیشوند نام کاربری", "Username prefix")}><Input className="ltr" value={f.username_prefix} onChange={e => set("username_prefix", e.target.value)} /></F>
      <F label={t("نام کاربری ادمین پنل", "Panel admin username")}><Input className="ltr" value={f.username} onChange={e => set("username", e.target.value)} /></F>
      <F label={t("رمز عبور", "Password")}><Input type="password" value={f.password} onChange={e => set("password", e.target.value)} /></F>
      <F label={t("بازه همگام‌سازی (ثانیه)", "Sync interval (s)")}><Input type="number" min={15} value={f.sync_interval} onChange={e => set("sync_interval", e.target.value)} /></F>
      <HStack><Checkbox isChecked={f.verify_ssl} onChange={e => set("verify_ssl", e.target.checked)}>SSL</Checkbox><Checkbox isChecked={f.enabled} onChange={e => set("enabled", e.target.checked)}>{t("فعال", "Enabled")}</Checkbox></HStack>
    </SimpleGrid><HStack mt={4}><Button colorScheme="blue" onClick={save}>{t("ذخیره", "Save")}</Button><Button onClick={() => setF(null)}>{t("انصراف", "Cancel")}</Button></HStack>
      {editId && <Text mt={2} fontSize="sm" className="muted">{t("برای ویرایش، نام کاربری و رمز پنل باید دوباره وارد شود.", "Re-enter panel credentials when editing.")}</Text>}</Box>}
    <Box overflowX="auto"><Table size="sm"><Thead><Tr><Th>ID</Th><Th>{t("نام", "Name")}</Th><Th>{t("نوع", "Type")}</Th><Th>URL</Th><Th>{t("سلامت", "Health")}</Th><Th>{t("عملیات", "Actions")}</Th></Tr></Thead>
      <Tbody>{(q.data || []).map((p: any) => <Tr key={p.id}><Td>{p.id}</Td><Td>{p.name}</Td><Td>{p.type}</Td><Td className="ltr">{p.base_url}</Td>
        <Td><Badge colorScheme={p.status === "healthy" ? "green" : "red"}>{p.status}</Badge>{p.last_error && <Text fontSize="xs">{p.last_error}</Text>}</Td>
        <Td><HStack flexWrap="wrap" spacing={2}>
          <Button size="xs" onClick={() => run(`/api/panels/${p.id}/test`, J("POST"))}>{t("تست", "Test")}</Button>
          <Button size="xs" onClick={() => run(`/api/panels/${p.id}/sync`, J("POST"))}>{t("همگام‌سازی", "Sync")}</Button>
          <Button size="xs" onClick={async () => setInb(await api(`/api/panels/${p.id}/inbounds`).catch(() => []))}>Inbounds</Button>
          <Button size="xs" onClick={() => { setEditId(p.id); setF({ ...empty, name: p.name, type: p.type, base_url: p.base_url, enabled: p.enabled }); }}>{t("ویرایش", "Edit")}</Button>
          <Button size="xs" colorScheme="red" onClick={() => confirm(t("حذف شود؟", "Delete?")) && run(`/api/panels/${p.id}`, J("DELETE"))}>{t("حذف", "Delete")}</Button>
        </HStack></Td></Tr>)}</Tbody></Table></Box>
    <Modal isOpen={!!inb} onClose={() => setInb(null)} size="xl" isCentered><ModalOverlay /><ModalContent><ModalHeader>Inbounds</ModalHeader><ModalCloseButton /><ModalBody pb={6} overflowX="auto">
      <Table size="sm"><Thead><Tr><Th>remote_id</Th><Th>tag</Th><Th>protocol</Th><Th>network</Th><Th>security</Th></Tr></Thead><Tbody>{(inb || []).map((x: any) => <Tr key={x.id}><Td>{x.remote_id}</Td><Td>{x.tag}</Td><Td>{x.protocol}</Td><Td>{x.network}</Td><Td>{x.security}</Td></Tr>)}</Tbody></Table></ModalBody></ModalContent></Modal>
  </Box>;
}

/* ---------------- Services ---------------- */
function ItemAdder({ c, service, done }: { c: Ctx; service: any; done: () => void }) {
  const { api, t } = c; const run = useRun(c, ["services"]);
  const panels = useQuery({ queryKey: ["panels"], queryFn: () => api("/api/panels") });
  const [pid, setPid] = React.useState(""); const [inb, setInb] = React.useState<any[]>([]); const [sel, setSel] = React.useState<string[]>([]); const [prio, setPrio] = React.useState("0");
  React.useEffect(() => { setSel([]); setInb([]); if (pid) void api(`/api/panels/${pid}/inbounds`).then(setInb).catch(() => setInb([])); }, [pid]);
  return <Box mt={3} p={3} borderWidth="1px" borderRadius="12px">
    <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
      <F label={t("پنل", "Panel")}><Select placeholder="—" value={pid} onChange={e => setPid(e.target.value)}>{(panels.data || []).map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></F>
      <F label={t("اولویت", "Priority")}><Input type="number" value={prio} onChange={e => setPrio(e.target.value)} /></F></SimpleGrid>
    {pid && <Box mt={2}><Text fontSize="sm" mb={1}>{t("اینباندها (خالی = همه)", "Inbounds (empty = all)")}</Text><HStack flexWrap="wrap" spacing={3}>{inb.filter(x => x.kind !== "group").map(x => { const k = String(x.tag ?? x.remote_id ?? x.id); return <Checkbox key={x.id} isChecked={sel.includes(k)} onChange={e => setSel(e.target.checked ? [...sel, k] : sel.filter(s => s !== k))}>{x.tag || x.remote_id}{x.protocol ? ` · ${x.protocol}` : ""}</Checkbox>; })}
      {inb.length === 0 && <Text fontSize="sm" className="muted">{t("اینباندی در کش نیست؛ ابتدا در تب پنل‌ها «همگام‌سازی» بزنید.", "No inbounds cached; press Sync in the Panels tab first.")}</Text>}</HStack></Box>}
    <Button mt={3} size="sm" colorScheme="blue" isDisabled={!pid} onClick={() => run(`/api/services/${service.id}/items`, J("POST", { panel_id: Number(pid), selected_items: sel, priority: Number(prio) }), done)}>{t("افزودن پنل به سرویس", "Attach panel")}</Button>
  </Box>;
}
export function ServicesTab(c: Ctx) {
  const { api, t } = c; const run = useRun(c, ["services"]);
  const q = useQuery({ queryKey: ["services"], queryFn: () => api("/api/services") });
  const panels = useQuery({ queryKey: ["panels"], queryFn: () => api("/api/panels") });
  const pname = (id: number) => (panels.data || []).find((p: any) => p.id === id)?.name ?? id;
  const empty = { name: "", display_name: "", description: "", enabled: true, sort_order: 0, sub_remark_template: "{service} | {server}" };
  const [f, setF] = React.useState<any>(null); const [editId, setEditId] = React.useState<number | null>(null); const [addFor, setAddFor] = React.useState<number | null>(null);
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  return <Box className="panel">
    <HStack justify="space-between" mb={4}><Heading size="md">{t("سرویس‌ها", "Services")}</Heading><Button colorScheme="blue" onClick={() => { setEditId(null); setF(empty); }}>{t("سرویس جدید", "New service")}</Button></HStack>
    {f && <Box className="create-form" mb={4}><SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
      <F label={t("نام داخلی", "Name")}><Input className="ltr" value={f.name} onChange={e => set("name", e.target.value)} /></F>
      <F label={t("نام نمایشی", "Display name")}><Input value={f.display_name} onChange={e => set("display_name", e.target.value)} /></F>
      <F label={t("توضیحات", "Description")}><Input value={f.description} onChange={e => set("description", e.target.value)} /></F>
      <F label={t("ترتیب", "Sort order")}><Input type="number" value={f.sort_order} onChange={e => set("sort_order", Number(e.target.value))} /></F>
      <F label={t("قالب ریمارک", "Remark template")}><Input className="ltr" value={f.sub_remark_template} onChange={e => set("sub_remark_template", e.target.value)} /><Chips opts={[[t("+ نام سرویس", "+ service"), "{service}"], [t("+ نام سرور", "+ server"), "{server}"], ["|", " | "], ["-", " - "]]} onPick={x => set("sub_remark_template", (f.sub_remark_template || "") + x)} /></F>
      <F label={t("فعال", "Enabled")}><Switch isChecked={f.enabled} onChange={e => set("enabled", e.target.checked)} /></F>
    </SimpleGrid><HStack mt={4}><Button colorScheme="blue" onClick={() => run(editId ? `/api/services/${editId}` : "/api/services", J(editId ? "PUT" : "POST", f), () => setF(null))}>{t("ذخیره", "Save")}</Button><Button onClick={() => setF(null)}>{t("انصراف", "Cancel")}</Button></HStack></Box>}
    {(q.data || []).map((s: any) => <Box key={s.id} mb={4} p={3} borderWidth="1px" borderRadius="12px">
      <HStack justify="space-between" flexWrap="wrap"><Box><Heading size="sm">{s.display_name} <Badge>{s.name}</Badge> {!s.enabled && <Badge colorScheme="red">off</Badge>}</Heading><Text fontSize="sm" className="muted">{s.description}</Text></Box>
        {!s.inbound_names && <HStack spacing={2}><Button size="xs" onClick={() => setAddFor(addFor === s.id ? null : s.id)}>{t("افزودن پنل", "Add panel")}</Button>
          <Button size="xs" onClick={() => { setEditId(s.id); setF({ ...empty, name: s.name, display_name: s.display_name, description: s.description, enabled: s.enabled, sort_order: s.sort_order, sub_remark_template: s.sub_remark_template || empty.sub_remark_template }); }}>{t("ویرایش", "Edit")}</Button>
          <Button size="xs" colorScheme="red" onClick={() => confirm(t("حذف شود؟", "Delete?")) && run(`/api/services/${s.id}`, J("DELETE"))}>{t("حذف", "Delete")}</Button></HStack>}</HStack>
      {s.inbound_names?.length > 0 && <Text fontSize="sm" mt={2}>{s.inbound_names.join("، ")}</Text>}
      <Table size="sm" mt={2}><Tbody>{s.items.map((i: any) => <Tr key={i.id}><Td>{pname(i.panel_id)}</Td><Td className="ltr">{(i.selected_items || []).join(", ") || t("همه", "all")}</Td><Td>P{i.priority}</Td><Td><Button size="xs" colorScheme="red" variant="outline" onClick={() => run(`/api/services/${s.id}/items/${i.id}`, J("DELETE"))}>✕</Button></Td></Tr>)}</Tbody></Table>
      {addFor === s.id && <ItemAdder c={c} service={s} done={() => setAddFor(null)} />}
    </Box>)}
  </Box>;
}

/* ---------------- Templates ---------------- */
export function TemplatesTab(c: Ctx) {
  const { api, t } = c; const run = useRun(c, ["templates"]);
  const q = useQuery({ queryKey: ["templates"], queryFn: () => api("/api/templates") });
  const sv = useQuery({ queryKey: ["services"], queryFn: () => api("/api/services") });
  const empty = { name: "", service_id: "", data_gb: "30", duration: "30", username_prefix: "", username_suffix: "", reset_strategy: "no_reset", add_remaining_traffic: false };
  const [f, setF] = React.useState<any>(null); const [editId, setEditId] = React.useState<number | null>(null);
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const body = () => ({ name: f.name, service_id: Number(f.service_id), data_limit: f.data_gb === "" ? null : Math.round(Number(f.data_gb) * GB), duration: num(f.duration), username_prefix: f.username_prefix, username_suffix: f.username_suffix, reset_strategy: f.reset_strategy, add_remaining_traffic: f.add_remaining_traffic });
  return <Box className="panel">
    <HStack justify="space-between" mb={4}><Heading size="md">{t("قالب‌های کاربر", "User templates")}</Heading><Button colorScheme="blue" onClick={() => { setEditId(null); setF(empty); }}>{t("قالب جدید", "New template")}</Button></HStack>
    {f && <Box className="create-form" mb={4}><SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
      <F label={t("نام", "Name")}><Input value={f.name} onChange={e => set("name", e.target.value)} /></F>
      <F label={t("سرویس", "Service")}><Select placeholder="—" value={f.service_id} onChange={e => set("service_id", e.target.value)}>{(sv.data || []).map((s: any) => <option key={s.id} value={s.id}>{s.display_name}</option>)}</Select></F>
      <F label={t("حجم (GB)", "Traffic GB")}><Input type="number" value={f.data_gb} onChange={e => set("data_gb", e.target.value)} /><Chips opts={[["10", "10"], ["30", "30"], ["50", "50"], ["100", "100"], ["200", "200"], [t("نامحدود", "∞"), ""]]} onPick={v => set("data_gb", v)} /></F>
      <F label={t("مدت (روز)", "Days")}><Input type="number" value={f.duration} onChange={e => set("duration", e.target.value)} /><Chips opts={[["7", "7"], ["30", "30"], ["60", "60"], ["90", "90"], ["365", "365"], [t("نامحدود", "∞"), ""]]} onPick={v => set("duration", v)} /></F>
      <F label={t("پیشوند", "Prefix")}><Input className="ltr" value={f.username_prefix} onChange={e => set("username_prefix", e.target.value)} /></F>
      <F label={t("پسوند", "Suffix")}><Input className="ltr" value={f.username_suffix} onChange={e => set("username_suffix", e.target.value)} /></F>
      <F label={t("ریست حجم", "Reset strategy")}><Select value={f.reset_strategy} onChange={e => set("reset_strategy", e.target.value)}>{[["no_reset", "بدون ریست"], ["day", "روزانه"], ["week", "هفتگی"], ["month", "ماهانه"], ["year", "سالانه"]].map(([x, l]) => <option key={x} value={x}>{t(l, x)}</option>)}</Select></F>
      <Checkbox isChecked={f.add_remaining_traffic} onChange={e => set("add_remaining_traffic", e.target.checked)}>{t("اضافه شدن حجم باقی‌مانده", "Add remaining traffic")}</Checkbox>
    </SimpleGrid><HStack mt={4}><Button colorScheme="blue" onClick={() => run(editId ? `/api/templates/${editId}` : "/api/templates", J(editId ? "PUT" : "POST", body()), () => setF(null))}>{t("ذخیره", "Save")}</Button><Button onClick={() => setF(null)}>{t("انصراف", "Cancel")}</Button></HStack></Box>}
    <Box overflowX="auto"><Table size="sm"><Thead><Tr><Th>{t("نام", "Name")}</Th><Th>{t("سرویس", "Service")}</Th><Th>{t("حجم", "Traffic")}</Th><Th>{t("مدت", "Days")}</Th><Th /></Tr></Thead>
      <Tbody>{(q.data || []).map((x: any) => <Tr key={x.id}><Td>{x.name}</Td><Td>{(sv.data || []).find((s: any) => s.id === x.service_id)?.display_name ?? x.service_id}</Td><Td>{x.data_limit == null ? "∞" : (x.data_limit / GB).toFixed(1) + " GB"}</Td><Td>{x.duration ?? "∞"}</Td>
        <Td><HStack spacing={2}><Button size="xs" onClick={() => { setEditId(x.id); setF({ name: x.name, service_id: String(x.service_id), data_gb: x.data_limit == null ? "" : String(x.data_limit / GB), duration: x.duration == null ? "" : String(x.duration), username_prefix: x.username_prefix, username_suffix: x.username_suffix, reset_strategy: x.reset_strategy, add_remaining_traffic: x.add_remaining_traffic }); }}>{t("ویرایش", "Edit")}</Button>
          <Button size="xs" colorScheme="red" onClick={() => confirm(t("حذف شود؟", "Delete?")) && run(`/api/templates/${x.id}`, J("DELETE"))}>{t("حذف", "Delete")}</Button></HStack></Td></Tr>)}</Tbody></Table></Box>
  </Box>;
}

/* ---------------- Admins ---------------- */
const toGB = (v: any) => (v == null ? "" : String(+(v / GB).toFixed(2)));
const fromGB = (v: string) => (v === "" ? null : Math.round(Number(v) * GB));
function Chips({ opts, onPick }: { opts: [string, string][]; onPick: (v: string) => void }) {
  return <HStack mt={1} spacing={1} flexWrap="wrap">{opts.map(([l, v]) => <Button key={l} size="xs" variant="outline" onClick={() => onPick(v)}>{l}</Button>)}</HStack>;
}
export function AdminsTab(c: Ctx) {
  const { api, t } = c; const run = useRun(c, ["admins"]);
  const q = useQuery({ queryKey: ["admins"], queryFn: () => api("/api/admins") });
  const cat = useQuery({ queryKey: ["perm-catalog"], queryFn: () => api("/api/admins/permissions") });
  const sv = useQuery({ queryKey: ["services"], queryFn: () => api("/api/services") });
  const empty = { username: "", password: "", role: "admin", max_users: "", max_total_gb: "", max_user_gb: "", max_user_days: "", expire: "", services: [] as number[], perms: {} as Record<string, boolean> };
  const [f, setF] = React.useState<any>(null); const [editId, setEditId] = React.useState<number | null>(null);
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const [pw, setPw] = React.useState({ current_password: "", new_password: "" });
  const allKeys: string[] = (cat.data || []).flatMap((g: any) => g.items.map((i: any) => i.key));
  const allSv: number[] = (sv.data || []).map((s: any) => s.id);
  const toggle = (arr: any[], v: any, on: boolean) => (on ? [...arr, v] : arr.filter(x => x !== v));
  const limits = () => ({ max_users: num(f.max_users), max_total_traffic: fromGB(f.max_total_gb), max_user_traffic: fromGB(f.max_user_gb), max_user_days: num(f.max_user_days), expire: f.expire ? new Date(f.expire + "T23:59:59").toISOString() : null, allowed_services: f.services, permissions: Object.fromEntries(allKeys.map(k => [k, !!f.perms[k]])) });
  const save = () => editId
    ? run(`/api/admins/${editId}`, J("PATCH", limits()), () => { setF(null); setEditId(null); })
    : run("/api/admins", J("POST", { username: f.username, password: f.password, role: f.role, ...limits() }), () => setF(null));
  const edit = (a: any) => { setEditId(a.id); setF({ ...empty, username: a.username, role: a.role, max_users: a.max_users ?? "", max_total_gb: toGB(a.max_total_traffic), max_user_gb: toGB(a.max_user_traffic), max_user_days: a.max_user_days ?? "", expire: a.expire ? a.expire.slice(0, 10) : "", services: a.allowed_services || [], perms: Object.keys(a.permissions || {}).length ? a.permissions : Object.fromEntries(allKeys.map(k => [k, true])) }); };
  const isAdmin = f?.role === "admin";
  return <Box className="panel">
    <HStack justify="space-between" mb={4}><Heading size="md">{t("ادمین‌ها", "Admins")}</Heading><Button colorScheme="blue" onClick={() => { setEditId(null); setF(empty); }}>{t("ادمین جدید", "New admin")}</Button></HStack>
    {f && <Box className="create-form" mb={4}>
      <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
        <F label={t("نام کاربری", "Username")}><Input className="ltr" isDisabled={!!editId} value={f.username} onChange={e => set("username", e.target.value)} /></F>
        {!editId && <F label={t("رمز (حداقل ۱۲ کاراکتر)", "Password (min 12)")}><Input type="password" value={f.password} onChange={e => set("password", e.target.value)} /></F>}
        {!editId && <F label={t("نقش", "Role")}><Select value={f.role} onChange={e => set("role", e.target.value)}><option value="admin">{t("ادمین (دسترسی محدود)", "Admin (limited)")}</option><option value="sudo">{t("مدیر اصلی (همه دسترسی‌ها)", "Sudo (full access)")}</option></Select></F>}
      </SimpleGrid>
      {isAdmin && <>
        <Heading size="sm" mt={5} mb={2}>{t("دسترسی‌ها", "Permissions")}</Heading>
        <HStack mb={2}><Button size="xs" onClick={() => set("perms", Object.fromEntries(allKeys.map(k => [k, true])))}>{t("انتخاب همه", "Select all")}</Button><Button size="xs" onClick={() => set("perms", Object.fromEntries(allKeys.map(k => [k, false])))}>{t("هیچ‌کدام", "None")}</Button></HStack>
        {(cat.data || []).map((g: any) => <Box key={g.group} mb={3}><Text fontSize="sm" className="muted" mb={1}>{g.group}</Text><SimpleGrid columns={{ base: 1, md: 3 }} spacing={2}>{g.items.map((i: any) => <Checkbox key={i.key} isChecked={!!f.perms[i.key]} onChange={e => set("perms", { ...f.perms, [i.key]: e.target.checked })}>{i.label}</Checkbox>)}</SimpleGrid></Box>)}
        <Heading size="sm" mt={4} mb={2}>{t("سرویس‌های مجاز", "Allowed services")}</Heading>
        <HStack mb={2}><Button size="xs" onClick={() => set("services", allSv)}>{t("همه", "All")}</Button><Button size="xs" onClick={() => set("services", [])}>{t("هیچ‌کدام", "None")}</Button></HStack>
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={2}>{(sv.data || []).map((s: any) => <Checkbox key={s.id} isChecked={f.services.includes(s.id)} onChange={e => set("services", toggle(f.services, s.id, e.target.checked))}>{s.display_name}</Checkbox>)}</SimpleGrid>
        <Heading size="sm" mt={4} mb={2}>{t("سهمیه‌ها (خالی = نامحدود)", "Quotas (empty = unlimited)")}</Heading>
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
          <F label={t("حداکثر کاربر", "Max users")}><Input type="number" value={f.max_users} onChange={e => set("max_users", e.target.value)} /><Chips opts={[["10", "10"], ["50", "50"], ["100", "100"], ["∞", ""]]} onPick={v => set("max_users", v)} /></F>
          <F label={t("سقف کل حجم (GB)", "Total traffic cap (GB)")}><Input type="number" value={f.max_total_gb} onChange={e => set("max_total_gb", e.target.value)} /><Chips opts={[["500", "500"], ["1000", "1000"], ["5000", "5000"], ["∞", ""]]} onPick={v => set("max_total_gb", v)} /></F>
          <F label={t("سقف حجم هر کاربر (GB)", "Per-user cap (GB)")}><Input type="number" value={f.max_user_gb} onChange={e => set("max_user_gb", e.target.value)} /><Chips opts={[["30", "30"], ["50", "50"], ["100", "100"], ["∞", ""]]} onPick={v => set("max_user_gb", v)} /></F>
          <F label={t("انقضای حساب ادمین", "Admin expiry")}><Input type="date" value={f.expire} onChange={e => set("expire", e.target.value)} /></F>
          <F label={t("سقف روز هر کاربر", "Max user days")}><Input type="number" value={f.max_user_days} onChange={e => set("max_user_days", e.target.value)} /><Chips opts={[["30", "30"], ["60", "60"], ["90", "90"], ["365", "365"], ["∞", ""]]} onPick={v => set("max_user_days", v)} /></F>
        </SimpleGrid></>}
      <HStack mt={4}><Button colorScheme="blue" onClick={save}>{editId ? t("ذخیره", "Save") : t("ایجاد", "Create")}</Button><Button onClick={() => { setF(null); setEditId(null); }}>{t("انصراف", "Cancel")}</Button></HStack></Box>}
    <Box overflowX="auto"><Table size="sm"><Thead><Tr><Th>ID</Th><Th>{t("نام کاربری", "Username")}</Th><Th>{t("نقش", "Role")}</Th><Th>{t("سرویس‌ها", "Services")}</Th><Th>{t("وضعیت", "Status")}</Th><Th>{t("عملیات", "Actions")}</Th></Tr></Thead>
      <Tbody>{(q.data || []).map((a: any) => <Tr key={a.id}><Td>{a.id}</Td><Td>{a.username}</Td><Td>{a.role === "sudo" ? t("مدیر اصلی", "Sudo") : t("ادمین", "Admin")}</Td><Td>{a.role === "sudo" ? t("همه", "All") : (a.allowed_services || []).map((id: number) => (sv.data || []).find((s: any) => s.id === id)?.display_name ?? id).join("، ") || "—"}</Td><Td><Badge colorScheme={a.state === "active" ? "green" : a.state === "disabled" ? "red" : "orange"}>{({ active: t("فعال", "on"), disabled: t("غیرفعال", "off"), expired: t("زمان تمام", "expired"), traffic_exhausted: t("حجم تمام", "no traffic") } as any)[a.state] ?? a.state}</Badge>{a.role !== "sudo" && <Text fontSize="xs" className="ltr">{(a.used_traffic / GB).toFixed(1)}/{a.max_total_traffic == null ? "∞" : (a.max_total_traffic / GB).toFixed(0)} GB{a.expire ? " · " + a.expire.slice(0, 10) : ""}</Text>}</Td>
        <Td><HStack flexWrap="wrap" spacing={2}>
          {a.role !== "sudo" && <Button size="xs" colorScheme="blue" onClick={() => edit(a)}>{t("ویرایش دسترسی", "Edit access")}</Button>}
          {a.role !== "sudo" && <Button size="xs" colorScheme="green" onClick={() => { const d = prompt(t("روز شارژ", "Days to add"), "30"); if (d === null) return; const g = prompt(t("حجم شارژ (GB)", "GB to add"), "0"); if (g === null) return; const r = confirm(t("مصرف کاربران ریست شود؟", "Reset users' usage?")); void run(`/api/admins/${a.id}/recharge`, J("POST", { add_days: Number(d) || 0, add_traffic: Math.round((Number(g) || 0) * GB), reset_usage: r })); }}>{t("شارژ", "Recharge")}</Button>}
          <Button size="xs" onClick={() => run(`/api/admins/${a.id}`, J("PATCH", { disabled: !a.disabled }))}>{a.disabled ? t("فعال‌سازی", "Enable") : t("غیرفعال", "Disable")}</Button>
          <Button size="xs" onClick={() => run(`/api/admins/${a.id}/users-status`, J("POST", { status: "disabled" }))}>{t("غیرفعال‌کردن کاربران", "Disable users")}</Button>
          <Button size="xs" onClick={() => run(`/api/admins/${a.id}/users-status`, J("POST", { status: "active" }))}>{t("فعال‌کردن کاربران", "Enable users")}</Button>
          {a.totp_enabled && <Button size="xs" onClick={() => confirm(t("2FA این ادمین غیرفعال شود؟", "Disable this admin's 2FA?")) && run(`/api/admins/${a.id}/reset-2fa`, J("POST"))}>{t("ریست 2FA", "Reset 2FA")}</Button>}
          <Button size="xs" onClick={() => confirm(t("مصرف کاربران صفر شود؟", "Reset usage?")) && run(`/api/admins/${a.id}/reset-usage`, J("POST"))}>{t("ریست مصرف", "Reset usage")}</Button>
        </HStack></Td></Tr>)}</Tbody></Table></Box>
    <Heading size="sm" mt={6} mb={2}>{t("تغییر رمز من", "Change my password")}</Heading>
    <HStack flexWrap="wrap"><Input maxW="240px" type="password" placeholder={t("رمز فعلی", "Current")} value={pw.current_password} onChange={e => setPw({ ...pw, current_password: e.target.value })} /><Input maxW="240px" type="password" placeholder={t("رمز جدید", "New")} value={pw.new_password} onChange={e => setPw({ ...pw, new_password: e.target.value })} /><Button onClick={() => run("/api/admin/password", J("POST", pw), () => setPw({ current_password: "", new_password: "" }))}>{t("تغییر", "Change")}</Button></HStack>
  </Box>;
}

/* ---------------- System ---------------- */
type SField = { key: string; fa: string; en: string; type: "text" | "number" | "bool" | "select"; opts?: [string, string][] };
const SETTING_FIELDS: SField[] = [
  { key: "brand_name", fa: "نام برند", en: "Brand name", type: "text" },
  { key: "support_telegram", fa: "آیدی تلگرام پشتیبانی", en: "Support Telegram", type: "text" },
  { key: "announcement", fa: "اطلاعیه برای کاربران", en: "Announcement", type: "text" },
  { key: "default_data_gb", fa: "حجم پیش‌فرض کاربر جدید (GB)", en: "Default traffic (GB)", type: "number" },
  { key: "default_duration_days", fa: "مدت پیش‌فرض کاربر جدید (روز)", en: "Default days", type: "number" },
  { key: "default_reset_strategy", fa: "ریست حجم پیش‌فرض", en: "Default reset", type: "select", opts: [["no_reset", "بدون ریست"], ["day", "روزانه"], ["week", "هفتگی"], ["month", "ماهانه"], ["year", "سالانه"]] },
  { key: "sub_update_interval_hours", fa: "بازه به‌روزرسانی اشتراک (ساعت)", en: "Sub update interval (h)", type: "number" },
  { key: "off_name_expired", fa: "نام اینباند خاموش — زمان تمام (چند نام با |)", en: "Off inbound name — expired (split by |)", type: "text" },
  { key: "off_name_limited", fa: "نام اینباند خاموش — حجم تمام", en: "Off inbound name — traffic ended", type: "text" },
  { key: "off_name_disabled", fa: "نام اینباند خاموش — غیرفعال", en: "Off inbound name — disabled", type: "text" },
  { key: "auto_backup", fa: "پشتیبان‌گیری خودکار", en: "Auto backup", type: "bool" },
  { key: "backup_keep", fa: "تعداد نسخه پشتیبان نگه‌داری‌شده", en: "Backups to keep", type: "number" },
];
export function SystemTab(c: Ctx) {
  const { api, t } = c; const run = useRun(c, ["settings"]);
  const st = useQuery({ queryKey: ["settings"], queryFn: () => api("/api/system/settings") });
  const au = useQuery({ queryKey: ["audit"], queryFn: () => api("/api/system/audit?limit=50") });
  const [v, setV] = React.useState<Record<string, any>>({}); const [exp, setExp] = React.useState<any>(null);
  React.useEffect(() => { if (st.data) setV(st.data); }, [st.data]);
  const known = SETTING_FIELDS.map(x => x.key); const extra = Object.keys(v).filter(k => !known.includes(k));
  const save = () => { const body: Record<string, any> = {}; Object.entries(v).forEach(([k, val]) => { if (val !== "" && val !== undefined) body[k] = val; }); void run("/api/system/settings", J("PUT", body)); };
  return <Box className="panel">
    <Heading size="md" mb={3}>{t("تنظیمات سیستم", "System settings")}</Heading>
    <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
      {SETTING_FIELDS.map(x => <F key={x.key} label={t(x.fa, x.en)}>
        {x.type === "bool" ? <Switch isChecked={!!v[x.key]} onChange={e => setV({ ...v, [x.key]: e.target.checked })} />
          : x.type === "select" ? <Select placeholder="—" value={v[x.key] ?? ""} onChange={e => setV({ ...v, [x.key]: e.target.value })}>{x.opts!.map(([o, l]) => <option key={o} value={o}>{l}</option>)}</Select>
          : <Input type={x.type} value={v[x.key] ?? ""} onChange={e => setV({ ...v, [x.key]: x.type === "number" && e.target.value !== "" ? Number(e.target.value) : e.target.value })} />}</F>)}
    </SimpleGrid>
    {extra.length > 0 && <Box mt={4}><Text fontSize="sm" className="muted" mb={2}>{t("سایر تنظیمات ذخیره‌شده", "Other stored settings")}</Text><SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>{extra.map(k => <F key={k} label={k}><HStack><Input className="ltr" value={typeof v[k] === "object" ? JSON.stringify(v[k]) : String(v[k] ?? "")} isReadOnly={typeof v[k] === "object"} onChange={e => setV({ ...v, [k]: e.target.value })} /></HStack></F>)}</SimpleGrid></Box>}
    <HStack mt={4} flexWrap="wrap"><Button colorScheme="blue" onClick={save}>{t("ذخیره تنظیمات", "Save settings")}</Button><Button onClick={() => run("/api/system/backup", J("POST"))}>{t("پشتیبان‌گیری", "Backup now")}</Button>
      <Button onClick={async () => setExp(await api("/api/users/expired").catch(() => null))}>{t("کاربران منقضی", "Expired users")}</Button>
      {exp && exp.count > 0 && <Button colorScheme="red" onClick={() => confirm(t(`${exp.count} کاربر حذف شود؟`, `Delete ${exp.count} users?`)) && run("/api/users/expired?dry_run=false", J("DELETE"), () => setExp(null))}>{t("حذف منقضی‌ها", "Delete expired")} ({exp.count})</Button>}</HStack>
    {exp && <Text mt={2} fontSize="sm" className="ltr">{exp.count}: {exp.users.slice(0, 30).join(", ")}</Text>}
    <Heading size="md" mt={6} mb={3}>{t("لاگ عملیات", "Audit log")}</Heading>
    <Box overflowX="auto" maxH="360px" overflowY="auto"><Table size="sm"><Thead><Tr><Th>#</Th><Th>Admin</Th><Th>Action</Th><Th>Object</Th><Th>{t("زمان", "Time")}</Th></Tr></Thead>
      <Tbody>{(au.data?.items || []).map((x: any) => <Tr key={x.id}><Td>{x.id}</Td><Td>{x.actor_admin_id}</Td><Td>{x.action}</Td><Td>{x.object_type}:{x.object_id}</Td><Td className="ltr">{new Date(x.created_at).toLocaleString()}</Td></Tr>)}</Tbody></Table></Box>
  </Box>;
}

/* ---------------- User edit modal ---------------- */
export function UserEditModal({ c, user, onClose }: { c: Ctx; user: any | null; onClose: () => void }) {
  const { t } = c; const run = useRun(c, ["users"]);
  const [f, setF] = React.useState<any>({}); const [owner, setOwner] = React.useState("");
  React.useEffect(() => { if (user) setF({ status: user.status, data_gb: user.data_limit == null ? "" : String(user.data_limit / GB), expire: user.expire ? user.expire.slice(0, 10) : "", note: user.note || "" }); }, [user]);
  if (!user) return null;
  const u = `/api/user/${encodeURIComponent(user.username)}`;
  const save = () => { const b: any = {}; const lim = f.data_gb === "" ? null : Math.round(Number(f.data_gb) * GB); const exp = f.expire ? new Date(f.expire).toISOString() : null;
    if (f.status !== user.status) b.status = f.status; if (lim !== user.data_limit) b.data_limit = lim; if ((f.expire || "") !== (user.expire ? user.expire.slice(0, 10) : "")) b.expire = exp; if (f.note !== (user.note || "")) b.note = f.note;
    return Object.keys(b).length ? run(u, J("PUT", b), onClose) : onClose(); };
  return <Modal isOpen onClose={onClose} isCentered><ModalOverlay /><ModalContent><ModalHeader>{user.username}</ModalHeader><ModalCloseButton /><ModalBody pb={6}>
    <SimpleGrid columns={1} spacing={3}>
      <F label={t("وضعیت", "Status")}><Select value={f.status} onChange={e => setF({ ...f, status: e.target.value })}>{["active", "disabled", "limited", "expired", "on_hold"].map(x => <option key={x}>{x}</option>)}</Select></F>
      <F label={t("حجم (GB، خالی = نامحدود)", "Traffic GB (empty = unlimited)")}><Input type="number" value={f.data_gb ?? ""} onChange={e => setF({ ...f, data_gb: e.target.value })} /></F>
      <F label={t("انقضا", "Expire")}><Input type="date" value={f.expire ?? ""} onChange={e => setF({ ...f, expire: e.target.value })} /></F>
      <F label={t("یادداشت", "Note")}><Input value={f.note ?? ""} onChange={e => setF({ ...f, note: e.target.value })} /></F>
      <HStack flexWrap="wrap"><Button colorScheme="blue" onClick={save}>{t("ذخیره", "Save")}</Button><Button onClick={() => run(`${u}/active-next`, J("POST"), onClose)}>{t("فعال‌سازی پلن بعدی", "Activate next plan")}</Button></HStack>
      <HStack><Input placeholder={t("شناسه ادمین مالک", "Owner admin ID")} value={owner} onChange={e => setOwner(e.target.value)} /><Button onClick={() => run(`${u}/set-owner`, J("POST", { admin_id: Number(owner) }), onClose)}>{t("انتقال", "Set owner")}</Button></HStack>
    </SimpleGrid></ModalBody></ModalContent></Modal>;
}

/* ---------------- Bulk bar ---------------- */
export function BulkBar({ c, ids, clear }: { c: Ctx; ids: number[]; clear: () => void }) {
  const { t } = c; const run = useRun(c, ["users"]); const [n, setN] = React.useState("10");
  if (!ids.length) return null;
  return <HStack mb={3} flexWrap="wrap" spacing={2}><Badge>{ids.length}</Badge>
    {["active", "disabled", "on_hold"].map(s => <Button key={s} size="xs" onClick={() => run(`/api/bulk/status?status=${s}`, J("POST", { user_ids: ids }), clear)}>{s}</Button>)}
    <Input size="xs" maxW="70px" type="number" value={n} onChange={e => setN(e.target.value)} />
    <Button size="xs" onClick={() => run("/api/bulk/extend", J("POST", { user_ids: ids, amount: Number(n) }), clear)}>+{t("روز", "days")}</Button>
    <Button size="xs" onClick={() => run("/api/bulk/traffic", J("POST", { user_ids: ids, amount: Math.round(Number(n) * GB) }), clear)}>+GB</Button></HStack>;
}

/* ---------------- Inbound names ---------------- */
export function InboundsTab(c: Ctx) {
  const { api, t } = c; const run = useRun(c, ["inbounds"]);
  const q = useQuery({ queryKey: ["inbounds"], queryFn: () => api("/api/inbounds") });
  const [v, setV] = React.useState<Record<string, string>>({});
  const key = (x: any) => `${x.panel_id}|${x.tag}`;
  return <Box className="panel">
    <Heading size="md" mb={1}>{t("نام اینباندها", "Inbound names")}</Heading>
    <Text fontSize="sm" className="muted" mb={4}>{t("این نام به‌جای نام اصلی برای کاربران و ادمین‌ها نمایش داده می‌شود. خالی = نام اصلی. ابتدا پنل را همگام‌سازی کنید.", "Shown to users and admins instead of the original name. Empty = original. Sync the panel first.")}</Text>
    <Box overflowX="auto"><Table size="sm"><Thead><Tr><Th>{t("پنل", "Panel")}</Th><Th>{t("نام اصلی", "Original")}</Th><Th>{t("نوع", "Type")}</Th><Th>{t("نام نمایشی", "Display name")}</Th><Th /></Tr></Thead>
      <Tbody>{(q.data || []).map((x: any) => <Tr key={key(x)}><Td>{x.panel_name}</Td><Td className="ltr">{x.tag}</Td><Td className="ltr">{[x.protocol, x.network, x.security].filter(Boolean).join(" / ")}</Td>
        <Td><Input size="sm" value={v[key(x)] ?? x.display_name} onChange={e => setV({ ...v, [key(x)]: e.target.value })} /></Td>
        <Td><Button size="xs" colorScheme="blue" onClick={() => run("/api/inbounds", J("PUT", { panel_id: x.panel_id, tag: x.tag, display_name: v[key(x)] ?? x.display_name }))}>{t("ذخیره", "Save")}</Button></Td></Tr>)}</Tbody></Table></Box>
  </Box>;
}

/* ---------------- Dashboard ---------------- */
const fmtB = (n: number | null | undefined) => { if (n == null) return "∞"; const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0, x = n; while (x >= 1024 && i < 4) { x /= 1024; i++; } return x.toFixed(i ? 2 : 0) + " " + u[i]; };
const fmtUp = (s?: number) => s == null ? "—" : `${Math.floor(s / 86400)}d ${Math.floor(s % 86400 / 3600)}h ${Math.floor(s % 3600 / 60)}m`;
export function DashboardTab({ api, t }: Ctx) {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api("/api/system/dashboard"), refetchInterval: 10000 });
  const d = q.data; if (!d) return <Box className="panel"><Text>{t("در حال بارگذاری…", "Loading…")}</Text></Box>;
  const sys = d.system; const pct = (x: any) => x?.percent != null ? `${x.percent}%` : "—";
  const card = (label: string, value: any, sub?: string) => <Box key={label} className="stat" p={4} borderWidth="1px" borderRadius="12px"><Text fontSize="sm" className="muted">{label}</Text><Heading size="md" className="ltr">{value}</Heading>{sub && <Text fontSize="xs" className="muted ltr">{sub}</Text>}</Box>;
  return <Box className="panel">
    <Heading size="md" mb={3}>{d.scope === "all" ? t("داشبورد (کل سیستم)", "Dashboard (all)") : t("داشبورد من", "My dashboard")}</Heading>
    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={3}>
      {card(t("حجم کل", "Total traffic"), fmtB(d.traffic_total))}
      {card(t("حجم مصرف‌شده", "Used"), fmtB(d.traffic_used))}
      {card(t("حجم باقی‌مانده", "Remaining"), fmtB(d.traffic_remaining))}
      {card(t("حجم ساخته‌شده", "Allocated"), fmtB(d.traffic_created), d.unlimited_users ? `${d.unlimited_users} ${t("نامحدود", "unlimited")}` : undefined)}
      {card(t("کل کاربران", "Total users"), d.total_users, d.max_users != null ? `/ ${d.max_users}` : undefined)}
      {card(t("کاربران فعال", "Active"), d.active_users)}
      {card(t("کاربران آنلاین", "Online"), d.online_users)}
      {card(t("کاربران خاموش", "Disabled"), d.disabled_users)}
      {card(t("کاربران منقضی", "Expired"), d.expired_users)}
      {card(t("حجم تمام‌شده", "Limited"), d.limited_users)}
      {card(t("در انتظار", "On hold"), d.on_hold_users)}
      {card(t("انقضا تا ۳ روز", "Expiring ≤3d"), d.expiring_soon)}
    </SimpleGrid>
    {sys && <>
      <Heading size="sm" mt={6} mb={3}>{t("وضعیت سیستم", "System")}</Heading>
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={3}>
        {card("CPU", sys.cpu_percent != null ? `${sys.cpu_percent}%` : "—", sys.load_avg ? `load ${sys.load_avg.map((x: number) => x.toFixed(2)).join(" ")} · ${sys.cpu_count} cores` : undefined)}
        {card("RAM", pct(sys.memory), sys.memory ? `${fmtB(sys.memory.used)} / ${fmtB(sys.memory.total)}` : undefined)}
        {card("Swap", pct(sys.swap), sys.swap?.total ? `${fmtB(sys.swap.used)} / ${fmtB(sys.swap.total)}` : undefined)}
        {card("Disk", pct(sys.disk), sys.disk ? `${fmtB(sys.disk.used)} / ${fmtB(sys.disk.total)}` : undefined)}
        {card("Uptime", fmtUp(sys.uptime_seconds))}
        {card(t("شبکه ↓", "Net ↓"), fmtB(sys.network?.rx_bytes))}
        {card(t("شبکه ↑", "Net ↑"), fmtB(sys.network?.tx_bytes))}
        {card(t("پنل‌های سالم", "Healthy panels"), `${d.panels.healthy}/${d.panels.total}`)}
        {card(t("ادمین‌ها", "Admins"), d.admins_total)}
        {card(t("تسک در انتظار", "Pending sync"), d.pending_sync_tasks)}
        {card(t("تسک ناموفق", "Failed sync"), d.failed_sync_tasks)}
      </SimpleGrid></>}
  </Box>;
}
