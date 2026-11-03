import type { IconName } from "./Icon";

/** Single source of truth for dashboard navigation: menu entries, valid #/hash tabs and who may open them.
 *  access: "all" = every admin, "sudo" = sudo only, anything else = a permission key (sudo always passes). */
export type NavItem = { id: string; fa: string; en: string; icon: IconName; access: string; action?: "docs" };
export type NavGroup = { fa: string; en: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
 { fa: "اصلی", en: "Main", items: [
  { id: "dashboard", fa: "داشبورد", en: "Dashboard", icon: "dashboard", access: "dashboard.view" },
  { id: "users", fa: "کاربران", en: "Users", icon: "users", access: "all" },
  { id: "account", fa: "اکانت من", en: "My account", icon: "user", access: "all" },
 ] },
 { fa: "مدیریت", en: "Management", items: [
  { id: "panels", fa: "پنل‌ها", en: "Panels", icon: "server", access: "sudo" },
  { id: "inbounds", fa: "نام اینباندها", en: "Inbound names", icon: "inbound", access: "sudo" },
  { id: "services", fa: "سرویس‌ها", en: "Services", icon: "layers", access: "services.view" },
  { id: "templates", fa: "قالب‌ها", en: "Templates", icon: "template", access: "templates.view" },
  { id: "admins", fa: "ادمین‌ها", en: "Admins", icon: "shield", access: "sudo" },
 ] },
 { fa: "پایش", en: "Monitoring", items: [
  { id: "usage", fa: "مصرف", en: "Usage", icon: "activity", access: "sudo" },
  { id: "live", fa: "اتصالات زنده", en: "Live connections", icon: "wifi", access: "sudo" },
  { id: "geo", fa: "موقعیت کاربران", en: "User locations", icon: "wifi", access: "sudo" },
  { id: "actions", fa: "اقدامات اخیر", en: "Recent actions", icon: "clock", access: "sudo" },
  { id: "diagnostics", fa: "عیب‌یابی", en: "Diagnostics", icon: "gauge", access: "sudo" },
 ] },
 { fa: "سیستم", en: "System", items: [
  { id: "system", fa: "سیستم", en: "System", icon: "settings", access: "sudo" },
  { id: "apidocs", fa: "مستندات API (JSON)", en: "API docs (JSON)", icon: "link", access: "sudo", action: "docs" },
  { id: "guide", fa: "راهنما", en: "Guide", icon: "book", access: "all" },
 ] },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap(g => g.items);
/** Ids that can appear in the URL hash (menu actions such as the API-docs download are not tabs). */
export const TAB_IDS: string[] = NAV_ITEMS.filter(i => !i.action).map(i => i.id);

export const canOpen = (id: string, isSudo: boolean, can: (k: string) => boolean): boolean => {
 const n = NAV_ITEMS.find(i => i.id === id);
 if (!n) return false;
 return isSudo || n.access === "all" || (n.access !== "sudo" && can(n.access));
};
