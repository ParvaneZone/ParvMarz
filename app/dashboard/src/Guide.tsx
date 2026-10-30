import React from "react";
import { Box, Heading, Text, Accordion, AccordionItem, AccordionButton, AccordionPanel, AccordionIcon } from "@chakra-ui/react";
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
    ["activity", "مصرف", "Usage", "نمودار مصرف در طول زمان و توزیع ترافیک بین ادمین‌ها، سرویس‌ها، پنل‌ها و نودها، با انتخاب بازه‌ی زمانی (حداکثر ۴۰۰ روز). بخش «مسیرهای مصرف» نشان می‌دهد ترافیک از کدام مبدأ به کدام مقصد رفته است. فقط ادمین کل.", "Usage-over-time chart and traffic distribution across admins, services, panels and nodes, with a selectable range (max 400 days). “Traffic routes” shows which source the traffic flowed to which target. Sudo admin only.", true],
    ["wifi", "اتصالات زنده", "Live connections", "کاربرانی که در ۳ دقیقه‌ی اخیر مصرف داشته‌اند؛ هر ۱۰ ثانیه خودکار به‌روز می‌شود. فقط ادمین کل.", "Users with traffic in the last 3 minutes; refreshes automatically every 10 seconds. Sudo admin only.", true],
    ["globe", "موقعیت کاربران", "User locations", "موقعیت تقریبی کاربران بر اساس IP دریافت‌کننده‌ی اشتراک و اینباندهایی که به او داده شده است. فقط ادمین کل.", "Approximate user locations based on the IP that fetched the subscription and the inbounds served to it. Sudo admin only.", true],
    ["clock", "اقدامات اخیر", "Recent actions", "فهرست آخرین عملیات انجام‌شده روی پنل (ساخت، ویرایش، حذف و ...) برای پیگیری اینکه چه کسی چه کاری کرده است. فقط ادمین کل.", "A list of the latest actions performed on the panel (create, edit, delete, ...) to track who did what. Sudo admin only.", true],
    ["gauge", "عیب‌یابی", "Diagnostics", "سلامت پنل‌های متصل و ۵۰ تسک ناموفق آخر را نشان می‌دهد تا مشکل اتصال یا ساخت کاربر را سریع پیدا کنید. فقط ادمین کل.", "Shows the health of connected panels and the last 50 failed tasks so you can quickly find connection or user-creation problems. Sudo admin only.", true],
    ["link", "مستندات API", "API docs", "از منوی کناری، فایل openapi.json دانلود می‌شود تا با API پنل (کلید API، ساخت کاربر و ...) کار کنید. فقط ادمین کل.", "From the side menu, downloads openapi.json so you can integrate with the panel API (API keys, user creation, ...). Sudo admin only.", true],
    ["book", "راهنما", "Guide", "همین صفحه: توضیح هر بخش پنل. روی عنوان هر مورد بزنید تا باز شود.", "This page: an explanation of every section. Tap an item's title to expand it.", false],
  ];
  const list = items.filter((i) => isSudo || !i[5]);
  return (
    <Box className="panel">
      <Heading size="md" mb={1}>{t("راهنمای بخش‌ها", "Sections guide")}</Heading>
      <Text className="muted" fontSize="sm" mb={4}>{t("برای دیدن توضیحات، روی عنوان هر بخش بزنید.", "Tap a section title to read its description.")}</Text>
      <Accordion allowMultiple allowToggle className="guide">
        {list.map(([ic, fa, en, dfa, den], i) => (
          <AccordionItem key={ic + i}>
            <h3>
              <AccordionButton py={3} px={2} gap={3}>
                <Icon name={ic} />
                <Box flex="1" textAlign="start" fontWeight={600}>{t(fa, en)}</Box>
                <AccordionIcon />
              </AccordionButton>
            </h3>
            <AccordionPanel px={2} pb={4} pt={1} className="muted" lineHeight="1.9">{t(dfa, den)}</AccordionPanel>
          </AccordionItem>
        ))}
      </Accordion>
    </Box>
  );
}
