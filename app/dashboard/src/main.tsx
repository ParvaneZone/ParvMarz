import React from "react";
import { createRoot } from "react-dom/client";
import { ChakraProvider, useColorMode, Checkbox, Box, Heading, Text, SimpleGrid, Stat, StatLabel, StatNumber, Table, Thead, Tbody, Tr, Th, Td, Badge, Button, HStack, VStack, Input, Select, FormControl, FormLabel, useToast, Textarea, Switch, Drawer, DrawerOverlay, DrawerContent, DrawerBody, DrawerCloseButton, DrawerHeader, Modal, ModalOverlay, ModalContent, ModalHeader, ModalCloseButton, ModalBody, Image } from "@chakra-ui/react";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import QRCode from "qrcode";
import "./style.css";
import { UsersList } from "./UsersList";
import { Icon } from "./Icon";
import { Logo } from "./Brand";
import { BgScene, useScrollMotion } from "./Motion";
import { copyText } from "./copy";
import { api, errMsg, subUrl } from "./api";
import { NAV_GROUPS, TAB_IDS, canOpen } from "./nav";
import type { Prefs } from "./theme";
import { loadPrefs, savePrefs, normPrefs, applyPrefs, buildTheme, isDark } from "./theme";

// Tabs and heavy modals are loaded on demand so the first paint (login / users list) ships a much smaller bundle.
const lz=(load:()=>Promise<any>,name:string)=>React.lazy(()=>load().then(m=>({default:m[name] as React.ComponentType<any>})));
const PanelsTab=lz(()=>import("./Manage"),"PanelsTab");
const ServicesTab=lz(()=>import("./Manage"),"ServicesTab");
const TemplatesTab=lz(()=>import("./Manage"),"TemplatesTab");
const AdminsTab=lz(()=>import("./Manage"),"AdminsTab");
const SystemTab=lz(()=>import("./Manage"),"SystemTab");
const InboundsTab=lz(()=>import("./Manage"),"InboundsTab");
const DashboardTab=lz(()=>import("./Manage"),"DashboardTab");
const UserEditModal=lz(()=>import("./Manage"),"UserEditModal");
const BulkBar=lz(()=>import("./Manage"),"BulkBar");
const AccountTab=lz(()=>import("./Account"),"AccountTab");
const UsageTab=lz(()=>import("./Usage"),"UsageTab");
const ActionsTab=lz(()=>import("./Ops"),"ActionsTab");
const LiveTab=lz(()=>import("./Ops"),"LiveTab");
const GeoTab=lz(()=>import("./Ops"),"GeoTab");
const DiagnosticsTab=lz(()=>import("./Ops"),"DiagnosticsTab");
const GuideTab=lz(()=>import("./Guide"),"GuideTab");

type User = {id:number; username:string; admin_id:number; service_id:number; status:string; data_limit:number|null; used_traffic:number; expire:string|null; note:string; subscription_url:string|null; created_at?:string};
type Panel = {id:number;name:string;type:string;base_url:string;enabled:boolean;status:string;last_ok_at:string|null;last_error:string|null};
type Service = {id:number;name:string;display_name:string;enabled:boolean;description:string};
try{localStorage.removeItem("jx_token");localStorage.removeItem("subhub_token")}catch{} // session lives in an HttpOnly cookie now: nothing for XSS to steal
const PAGE_SIZE = 50;
const faStatus:Record<string,string>={active:"فعال",disabled:"غیرفعال",limited:"محدود",expired:"منقضی",on_hold:"در انتظار",healthy:"سالم",unhealthy:"ناسالم",down:"قطع",unknown:"نامشخص"};
function QrModal({url,onClose}:{url:string;onClose:()=>void}){const [img,setImg]=React.useState("");React.useEffect(()=>{if(url)void QRCode.toDataURL(url,{width:320,margin:2}).then(setImg)},[url]);return <Modal isOpen={!!url} onClose={onClose} isCentered><ModalOverlay/><ModalContent><ModalHeader>QR</ModalHeader><ModalCloseButton/><ModalBody pb={6}>{img&&<Image src={img} mx="auto" mb={3}/>}<Input readOnly value={url} onFocus={e=>e.currentTarget.select()}/></ModalBody></ModalContent></Modal>}

function App({prefs,setPrefs}:{prefs:Prefs;setPrefs:(p:Prefs)=>void}){
 const lang=prefs.lang, theme=prefs.theme; const setLang=(l:"fa"|"en")=>setPrefs({...prefs,lang:l}); const setTheme=(m:"light"|"dark"|"oled")=>setPrefs({...prefs,theme:m});
 const [otp,setOtp]=React.useState(""); const [need2fa,setNeed2fa]=React.useState(false);
 const [token,setToken]=React.useState(""); const [ready,setReady]=React.useState(false); React.useEffect(()=>{api("/api/admin").then(()=>setToken("1")).catch(()=>{}).finally(()=>setReady(true))},[]); const [username,setUsername]=React.useState(""); const [password,setPassword]=React.useState(""); const fromHash=()=>{const h=location.hash.replace("#/","").replace("#","");return TAB_IDS.includes(h)?h:"users"}; const [tab,setTabState]=React.useState(fromHash()); const [menu,setMenu]=React.useState(false); const setTab=(id:string)=>{location.hash="/"+id;setTabState(id);setMenu(false)}; React.useEffect(()=>{const f=()=>setTabState(fromHash());window.addEventListener("hashchange",f);return()=>window.removeEventListener("hashchange",f)},[]); const [search,setSearch]=React.useState(""); const [status,setStatus]=React.useState(""); const [page,setPage]=React.useState(0); const [fAdmin,setFAdmin]=React.useState(""); const [fService,setFService]=React.useState(""); const [sort,setSort]=React.useState("-id"); const [showCreate,setShowCreate]=React.useState(false); const [adv,setAdv]=React.useState(false); const [cg,setCg]=React.useState("30"); const [cd,setCd]=React.useState("30"); const toast=useToast(); const qc=useQueryClient(); const fa=lang==="fa";
 const t=(faText:string,enText:string)=>fa?faText:enText; useScrollMotion(token);
 const stLabel=(v:string)=>fa?(faStatus[v]??v):v;
 const themeLabel=theme==="light"?t("روشن","Light"):theme==="dark"?t("تیره","Dark"):"OLED";
 const nextTheme=()=>setTheme(theme==="light"?"dark":theme==="dark"?"oled":"light");
 const {setColorMode}=useColorMode();
 React.useLayoutEffect(()=>{applyPrefs(prefs);setColorMode(isDark(prefs)?"dark":"light");savePrefs(prefs);},[prefs,setColorMode]);
 const synced=React.useRef(false); const lastPushed=React.useRef(""); const [syncTick,setSyncTick]=React.useState(0);
 React.useEffect(()=>{ if(!token){synced.current=false;return} let dead=false;
  api("/api/admin/preferences").then(r=>{ if(dead)return; if(r&&Object.keys(r).length){const np=normPrefs(r,prefs); lastPushed.current=JSON.stringify(np); setPrefs(np);} synced.current=true; setSyncTick(x=>x+1)}).catch(()=>{ if(!dead){synced.current=true; setSyncTick(x=>x+1)} });
  return()=>{dead=true}; // eslint-disable-next-line react-hooks/exhaustive-deps
 },[token]);
 React.useEffect(()=>{ if(!token||!synced.current)return; const body=JSON.stringify(prefs); if(body===lastPushed.current)return;
  const h=setTimeout(()=>{api("/api/admin/preferences",{method:"PUT",body}).then(()=>{lastPushed.current=body}).catch(()=>{})},600); return()=>clearTimeout(h)},[prefs,token,syncTick]);
 React.useEffect(()=>{document.documentElement.lang=lang;document.documentElement.dir=lang==="fa"?"rtl":"ltr";},[lang]);
 const login=async()=>{try{const d=await api("/api/admin/token",{method:"POST",body:JSON.stringify({username,password,...(need2fa?{otp}:{})})});if(d.two_factor_required){setNeed2fa(true);toast({title:t("کد دو مرحله‌ای را وارد کنید","Enter your 2FA code"),status:"info"});return}setToken("1");setNeed2fa(false);setOtp("");setPassword("");toast({title:t("ورود موفق بود","Signed in"),status:"success"})}catch(e){toast({title:errMsg(e),status:"error"})}};
 const users=useQuery({queryKey:["users",search,status,fAdmin,fService,sort,page],queryFn:()=>api(`/api/users?limit=${PAGE_SIZE}&offset=${page*PAGE_SIZE}&sort=${sort}${search?`&q=${encodeURIComponent(search)}`:""}${status?`&status=${status}`:""}${fAdmin?`&admin_id=${fAdmin}`:""}${fService?`&service_id=${fService}`:""}`),enabled:!!token,placeholderData:(p:any)=>p});
 const panels=useQuery({queryKey:["panels"],queryFn:()=>api("/api/panels"),enabled:!!token&&tab==="panels"});
 const services=useQuery({queryKey:["services"],queryFn:()=>api("/api/services"),enabled:!!token&&(tab==="services"||tab==="users"||showCreate)});
 const me=useQuery({queryKey:["me"],queryFn:()=>api("/api/admin"),enabled:!!token}); const isSudo=me.data?.role==="sudo";
 const adminsQ=useQuery({queryKey:["admins"],queryFn:()=>api("/api/admins"),enabled:!!token&&isSudo&&tab==="users"});
 const total:number=users.data?.total??0; const pageFrom=total?page*PAGE_SIZE+1:0; const pageTo=Math.min(total,(page+1)*PAGE_SIZE);
 const filt=(fn:()=>void)=>{fn();setPage(0);setSel([])};
  const [qrUrl,setQrUrl]=React.useState(""); const [editUser,setEditUser]=React.useState<User|null>(null); const [sel,setSel]=React.useState<number[]>([]);
  const can=(k:string)=>isSudo||!!me.data?.permissions?.[k]; const open=(id:string)=>canOpen(id,isSudo,can); const ctx={api,t,toast};
 const downloadDocs=async()=>{try{const d=await api("/api/docs/openapi.json");const u=URL.createObjectURL(new Blob([JSON.stringify(d,null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=u;a.download="openapi.json";a.click();URL.revokeObjectURL(u)}catch(e){toast({title:errMsg(e),status:"error"})}};
 const logout=()=>{void api("/api/admin/logout",{method:"POST"}).catch(()=>{});setToken("");qc.clear();};
 const createUser=async(form:FormData)=>{try{const cnt=Number(form.get("count")||1); if(cnt>1&&can("users.create_bulk")){const r=await api("/api/users/bulk-create",{method:"POST",body:JSON.stringify({prefix:String(form.get("username")),count:cnt,service_id:Number(form.get("service_id")),data_limit:form.get("unlimited")==="on"?null:Number(form.get("data_limit"))*1024*1024*1024,duration_days:Number(form.get("duration_days")||30),on_hold:form.get("on_hold")==="on",note:String(form.get("note")||"")})});setShowCreate(false);await qc.invalidateQueries({queryKey:["users"]});toast({title:r.error?String(r.error.detail||r.error):t(`${r.created.length} کاربر در صف ساخت قرار گرفتند`,`${r.created.length} users queued`),status:r.error?"error":"success"});return}await api("/api/user",{method:"POST",body:JSON.stringify({data_limit_reset_strategy:String(form.get("reset")||"no_reset"),expire:form.get("expire")?new Date(String(form.get("expire"))).toISOString():null,username:String(form.get("username")),service_id:Number(form.get("service_id")),data_limit:form.get("unlimited")==="on"?null:Number(form.get("data_limit"))*1024*1024*1024,duration_days:Number(form.get("duration_days")||30),status:"active",on_hold:form.get("on_hold")==="on",note:String(form.get("note")||"")})});setShowCreate(false);await qc.invalidateQueries({queryKey:["users"]});toast({title:t("کاربر در صف ساخت قرار گرفت","User queued for creation"),status:"success"})}catch(e){toast({title:errMsg(e),status:"error"})}};
 const action=async(path:string,method="POST")=>{try{await api(path,{method});await qc.invalidateQueries({queryKey:["users"]});toast({title:t("انجام شد","Done"),status:"success"})}catch(e){toast({title:errMsg(e),status:"error"})}};
 if(!ready) return null;
 if(!token) return <Box className={`shell ${theme}`} dir={fa?"rtl":"ltr"}><Box className="login"><VStack spacing={2} mb={2}><Logo size={84}/><Heading>Jinx Data</Heading></VStack><Text className="muted" mb={6} textAlign="center">{t("ورود به پنل مدیریت اشتراک","Sign in to subscription management")}</Text><VStack spacing={3}>{!need2fa?<><Input placeholder={t("نام کاربری","Username")} value={username} onChange={e=>setUsername(e.target.value)}/><Input placeholder={t("رمز عبور","Password")} type="password" value={password} onChange={e=>setPassword(e.target.value)} onKeyDown={e=>e.key==="Enter"&&login()}/></>:<><Text className="muted" fontSize="sm" alignSelf="flex-start">{t("کد ۶ رقمی Google Authenticator یا یک کد بازیابی","6-digit Google Authenticator code or a recovery code")}</Text><Input className="ltr" autoFocus inputMode="text" autoComplete="one-time-code" placeholder="123456" value={otp} onChange={e=>setOtp(e.target.value)} onKeyDown={e=>e.key==="Enter"&&login()}/></>}<Button colorScheme="blue" width="100%" onClick={login}>{need2fa?t("تأیید و ورود","Verify & sign in"):t("ورود","Sign in")}</Button>{need2fa&&<Button variant="link" onClick={()=>{setNeed2fa(false);setOtp("")}}>{t("بازگشت","Back")}</Button>}<HStack><Button variant="ghost" onClick={()=>setLang(fa?"en":"fa")}>{fa?"English":"فارسی"}</Button><Button variant="ghost" onClick={nextTheme}>{themeLabel}</Button></HStack></VStack></Box></Box>;
 return <Box className={`shell ${theme}`} dir={fa?"rtl":"ltr"}>
 <HStack className="hdr" justify="space-between" mb={6} flexWrap="wrap" spacing={3}><HStack spacing={3}><Button variant="outline" aria-label={t("منو","Menu")} onClick={()=>setMenu(true)}><Icon name="menu"/></Button><Logo size={44}/><Box><Heading size="lg">Jinx Data</Heading><Text className="muted">{t("پنل مرکزی مدیریت اشتراک","Central subscription management")}</Text></Box></HStack><HStack flexWrap="wrap" spacing={2}><Button variant="outline" leftIcon={<Icon name="globe"/>} onClick={()=>setLang(fa?"en":"fa")}>{fa?"English":"فارسی"}</Button><Button variant="outline" leftIcon={<Icon name={theme==="light"?"sun":"moon"}/>} onClick={nextTheme}>{themeLabel}</Button><Button variant="outline" aria-label={t("رنگ‌ها","Colors")} title={t("پالت رنگ","Color palette")} onClick={()=>setTab("account")}><Icon name="palette"/></Button><Button variant="outline" leftIcon={<Icon name="logout"/>} onClick={logout}>{t("خروج","Logout")}</Button></HStack></HStack>
 <QrModal url={qrUrl} onClose={()=>setQrUrl("")}/>{editUser&&<React.Suspense fallback={null}><UserEditModal c={ctx} user={editUser} onClose={()=>setEditUser(null)}/></React.Suspense>}
 <Drawer isOpen={menu} placement={fa?"right":"left"} onClose={()=>setMenu(false)}><DrawerOverlay/><DrawerContent><DrawerCloseButton/><DrawerHeader fontWeight={800}><HStack spacing={3}><Logo size={34}/><span>Jinx Data</span></HStack></DrawerHeader><DrawerBody>{NAV_GROUPS.map(g=>{const v=g.items.filter(i=>open(i.id));return v.length?<Box key={g.en} mb={4}><Text className="menu-sec">{t(g.fa,g.en)}</Text><VStack align="stretch" spacing={1}>{v.map(i=><Button key={i.id} justifyContent="flex-start" fontWeight={tab===i.id?700:500} leftIcon={<Icon name={i.icon}/>} variant={tab===i.id?"solid":"ghost"} colorScheme={tab===i.id?"blue":"gray"} onClick={()=>i.action==="docs"?void downloadDocs():setTab(i.id)}>{t(i.fa,i.en)}</Button>)}</VStack></Box>:null})}</DrawerBody></DrawerContent></Drawer>
 <React.Suspense fallback={<Box className="panel"><Text className="muted">{t("در حال بارگذاری…","Loading…")}</Text></Box>}>
 {tab==="dashboard"&&open("dashboard")&&<DashboardTab {...ctx}/>}
 {tab==="inbounds"&&open("inbounds")&&<InboundsTab {...ctx}/>}
 {tab==="users"&&<Box className="panel"><HStack justify="space-between" mb={4} flexWrap="wrap"><Heading size="md">{t("کاربران","Users")}</Heading>{can("users.create")&&<Button colorScheme="blue" onClick={()=>setShowCreate(!showCreate)}>{t("کاربر جدید","New user")}</Button>}</HStack>
 {showCreate&&<Box as="form" className="create-form" onSubmit={(e:React.FormEvent<HTMLFormElement>)=>{e.preventDefault();void createUser(new FormData(e.currentTarget))}}><SimpleGrid columns={{base:1,md:2}} spacing={4}><FormControl isRequired><FormLabel>{t("نام کاربری","Username")}</FormLabel><Input name="username" autoFocus/></FormControl><FormControl isRequired><FormLabel>{t("سرویس","Service")}</FormLabel><Select name="service_id" key={(services.data||[]).length} defaultValue={(services.data||[])[0]?.id}>{(services.data||[]).map((s:Service)=><option key={s.id} value={s.id}>{s.display_name}</option>)}</Select></FormControl><FormControl><FormLabel>{t("حجم (GB)","Traffic (GB)")}</FormLabel><Input name="data_limit" type="number" min="0" value={cg} onChange={e=>setCg(e.target.value)}/><HStack mt={2} spacing={2} flexWrap="wrap">{["10","30","50","100","200"].map(v=><Button key={v} size="xs" variant={cg===v?"solid":"outline"} colorScheme={cg===v?"blue":"gray"} onClick={()=>setCg(v)}>{v}</Button>)}{can("users.unlimited_traffic")&&<Checkbox name="unlimited" ml={2}>{t("نامحدود","Unlimited")}</Checkbox>}</HStack></FormControl><FormControl><FormLabel>{t("مدت (روز)","Duration (days)")}</FormLabel><Input name="duration_days" type="number" min="1" value={cd} onChange={e=>setCd(e.target.value)}/><HStack mt={2} spacing={2} flexWrap="wrap">{["7","30","60","90","180"].map(v=><Button key={v} size="xs" variant={cd===v?"solid":"outline"} colorScheme={cd===v?"blue":"gray"} onClick={()=>setCd(v)}>{v}</Button>)}</HStack></FormControl></SimpleGrid>
 <Button mt={4} size="sm" variant="link" onClick={()=>setAdv(!adv)}>{adv?t("گزینه‌های کمتر","Fewer options"):t("گزینه‌های بیشتر","More options")}</Button>
 {adv&&<SimpleGrid mt={3} columns={{base:1,md:2}} spacing={4}>{can("users.create_note")&&<FormControl><FormLabel>{t("یادداشت","Note")}</FormLabel><Input name="note"/></FormControl>}{can("users.create_bulk")&&<FormControl><FormLabel>{t("تعداد (ساخت گروهی؛ نام = پیشوند+شماره)","Count (bulk; name = prefix+number)")}</FormLabel><Input name="count" type="number" min="1" max="100" defaultValue="1"/></FormControl>}{can("users.create_reset_strategy")&&<FormControl><FormLabel>{t("ریست حجم","Reset")}</FormLabel><Select name="reset" defaultValue="no_reset">{["no_reset","day","week","month","year"].map(x=><option key={x}>{x}</option>)}</Select></FormControl>}{can("users.create_expire_date")&&<FormControl><FormLabel>{t("تاریخ انقضا (به‌جای مدت)","Expire date (overrides days)")}</FormLabel><Input name="expire" type="date"/></FormControl>}{can("users.on_hold")&&<FormControl display="flex" alignItems="center" gap={3}><Switch name="on_hold"/><FormLabel m={0}>{t("شروع با اولین اتصال","Start on first connection")}</FormLabel></FormControl>}</SimpleGrid>}
 <HStack mt={5}><Button type="submit" colorScheme="blue">{t("ایجاد","Create")}</Button><Button onClick={()=>setShowCreate(false)}>{t("انصراف","Cancel")}</Button></HStack></Box>}
 <HStack mb={4} flexWrap="wrap" spacing={2} align="stretch"><Input flex="1 1 180px" placeholder={t("جست‌وجوی نام کاربری","Search username")} value={search} onChange={e=>filt(()=>setSearch(e.target.value))}/><Select maxW="220px" value={status} onChange={e=>filt(()=>setStatus(e.target.value))}><option value="">{t("همه وضعیت‌ها","All statuses")}</option>{["active","disabled","limited","expired","on_hold"].map(s=><option key={s} value={s}>{stLabel(s)}</option>)}</Select>{isSudo&&<Select maxW="220px" value={fAdmin} onChange={e=>filt(()=>setFAdmin(e.target.value))}><option value="">{t("همه ادمین‌ها","All admins")}</option>{(adminsQ.data||[]).map((a:any)=><option key={a.id} value={a.id}>{a.username}</option>)}</Select>}<Select maxW="220px" value={fService} onChange={e=>filt(()=>setFService(e.target.value))}><option value="">{t("همه سرویس‌ها","All services")}</option>{(services.data||[]).map((s:Service)=><option key={s.id} value={s.id}>{s.display_name||s.name}</option>)}</Select><Select maxW="220px" value={sort} onChange={e=>filt(()=>setSort(e.target.value))}><option value="-id">{t("جدیدترین","Newest")}</option><option value="-used_traffic">{t("مصرف","Usage")}</option><option value="expire">{t("انقضا","Expiry")}</option><option value="username">{t("نام","Name")}</option></Select><Button onClick={()=>void users.refetch()}>{t("بروزرسانی","Refresh")}</Button></HStack>
 {isSudo&&sel.length>0&&<BulkBar c={ctx} ids={sel} clear={()=>setSel([])}/>}<UsersList c={ctx} loading={users.isLoading} items={users.data?.items||[]} isSudo={isSudo} can={can} sel={sel} setSel={setSel} stLabel={stLabel} subUrl={subUrl} onEdit={setEditUser} onQr={setQrUrl} action={action} meName={me.data?.username}/>
 <HStack mt={4} justify="space-between"><Button variant="outline" isDisabled={page===0} onClick={()=>{setPage(page-1);setSel([])}}>{t("قبلی","Previous")}</Button><Text fontSize="sm" className="ltr">{pageFrom}-{pageTo} / {total}</Text><Button variant="outline" isDisabled={pageTo>=total} onClick={()=>{setPage(page+1);setSel([])}}>{t("بعدی","Next")}</Button></HStack></Box>}
 {tab==="account"&&<AccountTab c={ctx} prefs={prefs} setPrefs={setPrefs}/>}
 {tab==="panels"&&open("panels")&&<PanelsTab {...ctx}/>}
 {tab==="services"&&open("services")&&<ServicesTab {...ctx}/>}
 {tab==="templates"&&open("templates")&&<TemplatesTab {...ctx}/>}
 {tab==="admins"&&open("admins")&&<AdminsTab {...ctx}/>}
 {tab==="usage"&&open("usage")&&<UsageTab {...ctx}/>}
 {tab==="live"&&open("live")&&<LiveTab {...ctx}/>}
 {tab==="geo"&&open("geo")&&<GeoTab {...ctx}/>}
 {tab==="actions"&&open("actions")&&<ActionsTab {...ctx}/>}
 {tab==="diagnostics"&&open("diagnostics")&&<DiagnosticsTab {...ctx}/>}
 {tab==="system"&&open("system")&&<SystemTab {...ctx}/>}
 {tab==="guide"&&<GuideTab t={t} isSudo={isSudo}/>}
 </React.Suspense>
 <Text mt={6} fontSize="sm" className="muted">Jinx Data</Text></Box>;
}
const client=new QueryClient({defaultOptions:{queries:{refetchOnWindowFocus:false,staleTime:10_000,gcTime:120_000,retry:1}}});
function Root(){
 const [prefs,setPrefsState]=React.useState<Prefs>(()=>{const p=loadPrefs();applyPrefs(p);return p});
 const theme=React.useMemo(()=>buildTheme(prefs),[prefs.accent]); // eslint-disable-line react-hooks/exhaustive-deps
 return <ChakraProvider theme={theme}><QueryClientProvider client={client}><BgScene/><App prefs={prefs} setPrefs={setPrefsState}/></QueryClientProvider></ChakraProvider>}
createRoot(document.getElementById("root")!).render(<Root/>);
