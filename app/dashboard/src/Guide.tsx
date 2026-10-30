import React from "react";
import { Box, Heading, Text, VStack, HStack } from "@chakra-ui/react";
import { Icon } from "./Icon";
import type { IconName } from "./Icon";

type Item = [IconName, string, string, string, string, boolean];

export function GuideTab({ t, isSudo }: { t: (fa: string, en: string) => string; isSudo: boolean }) {
  const items: Item[] = [
    ["dashboard", "داشبورد", "Dashboard", "نمای کلی سیستم: تعداد کاربران، کاربران فعال و مصرف کل ترافیک. برای ادمین معمولی فقط آمار خودش نمایش داده می‌شود و برای ادمین کل، آمار کل سیستم.", "Overview of the system: user count, active users and total traffic usage. A regular admin sees only their own stats; the sudo admin sees the whole system.", false],
    ["user", "اکانت من", "My account", "مشاهده و ویرایش اطلاعات حساب خودتان، تغییر رمز عبور، فعال‌سازی احراز هویت دو مرحله‌ای (Google Authenticator) و تنظیم ظاهر و رنگ‌های پنل.", "View and edit your own account, change your password, enable two-factor authentication (Google Authenticator) and customize the panel appearance and colors.", false],
    ["users", "کاربران", "Users", "ساخت، ویرایش و حذف کاربران. برای هر کاربر حجم، تاریخ انقضا، سرویس و لینک اشتراک (همراه با QR) مدیریت می‌شود. عملیات گروهی (بالک) روی چند کاربر هم‌زمان در همین بخش است.", "Create, edit and delete users. Per user you manage data limit, expiry, service and the subscription link (with QR). Bulk actions on several users at once are in this section too.", false],
    ["server", "پنل‌ها", "Panels", "مدیریت پنل‌های بالادستی (Marzban، Rebecca، PasarGuard و ...) که کاربران روی آن‌ها ساخته می‌شوند. افزودن، ویرایش، تست اتصال و حذف پنل در این بخش انجام می‌شود. فقط ادمین کل.", "Manage the upstream panels (Marzban, Rebecca, PasarGuard, ...) where users are created. Add, edit, test connection and remove panels here. Sudo admin only.", true],
    ["inbound", "نام اینباندها", "Inbound names", "نام نمایشی اینباندهای هر پنل را تعیین می‌کنید تا در لینک‌ها و لیست‌ها به‌صورت خوانا نمایش داده شوند. فقط ادمین کل.", "Set display names for each panel's inbounds so they show readably in links and lists. Sudo admin only.", true],
    ["layers", "سرویس‌ها", "Services", "هر سرویس مجموعه‌ای از پنل‌ها و اینباندهاست که هنگام ساخت کاربر انتخاب می‌شود. با سرویس‌ها تعیین می‌کنید هر کاربر به کدام سرورها دسترسی داشته باشد.", "A service is a set of panels and inbounds chosen when creating a user. Services decide which servers each user can access.", false],
    ["template", "قالب‌ها", "Templates", "قالب‌های آماده کاربر (حجم، مدت، سرویس) برای ساخت سریع کاربر بدون پر کردن دستی همه فیلدها.", "Ready-made user templates (data, duration, service) to create users quickly without filling every field by hand.", false],
    ["shield", "ادمین‌ها", "Admins", "ساخت و مدیریت ادمین‌ها با تعیین سرویس‌های مجاز، سهمیه‌ها (خالی = نامحدود) و دسترسی‌های دقیق هر ادمین. فقط ادمین کل.", "Create and manage admins with allowed services, quotas (empty = unlimited) and fine-grained permissions per admin. Sudo admin only.", true],
    ["settings", "سیستم", "System", "وضعیت زنده سرور (CPU، RAM، Swap، دیسک و آپتایم)، تنظیمات سیستم و لاگ عملیات برای پیگیری کارهای انجام‌شده. فقط ادمین کل.", "Live server status (CPU, RAM, swap, disk and uptime), system settings and the audit log of performed actions. Sudo admin only.", true],
  ];
  const list = items.filter((i) => isSudo || !i[5]);
  return (
    <Box className="panel">
      <Heading size="md" mb={4}>{t("راهنمای بخش‌ها", "Sections guide")}</Heading>
      <VStack align="stretch" spacing={3}>
        {list.map(([ic, fa, en, dfa, den]) => (
          <HStack key={ic} align="flex-start" spacing={3}>
            <Box mt={1}><Icon name={ic} /></Box>
            <Box>
              <Heading size="sm" mb={1}>{t(fa, en)}</Heading>
              <Text>{t(dfa, den)}</Text>
            </Box>
          </HStack>
        ))}
      </VStack>
    </Box>
  );
}
