# کاتالوگ دسترسی‌ها: (گروه، [(کلید، برچسب)])
CATALOG = [
    ("کاربران", [
        ("users.view", "مشاهده کاربران"),
        ("users.create", "ساخت کاربر"),
        ("users.edit", "ویرایش کاربر"),
        ("users.delete", "حذف کاربر"),
        ("users.reset", "ریست مصرف"),
        ("users.revoke_sub", "ابطال لینک اشتراک"),
        ("users.next_plan", "فعال‌سازی پلن بعدی"),
        ("users.edit_status", "تغییر وضعیت کاربر"),
        ("users.edit_traffic", "تغییر حجم کاربر"),
        ("users.edit_expire", "تغییر تاریخ انقضا"),
        ("users.edit_note", "ویرایش یادداشت"),
        ("users.on_hold", "ساخت کاربر با شروع از اولین اتصال"),
        ("users.unlimited_traffic", "حجم نامحدود برای کاربر"),
        ("users.unlimited_days", "مدت نامحدود برای کاربر"),
        ("users.create_note", "ثبت یادداشت هنگام ساخت"),
        ("users.create_reset_strategy", "تعیین ریست حجم هنگام ساخت"),
        ("users.create_expire_date", "تعیین تاریخ انقضای دقیق هنگام ساخت"),
        ("users.create_next_plan", "تعریف پلن بعدی هنگام ساخت"),
        ("users.create_bulk", "ساخت گروهی کاربر"),
        ("users.view_sub", "مشاهده/کپی لینک اشتراک و QR"),
        ("users.usage_logs", "مشاهده تاریخچه مصرف"),
    ]),
    ("سایر", [
        ("dashboard.view", "مشاهده داشبورد"),
        ("services.view", "مشاهده سرویس‌ها"),
        ("templates.view", "مشاهده قالب‌ها"),
        ("sub.off_inbound", "نمایش اینباند خاموش به کاربران منقضی/اتمام حجم"),
    ]),
]
KEYS = {k for _, items in CATALOG for k, _ in items}
DEFAULT_OFF = {"sub.off_inbound", "users.create_bulk"}
LEGACY_KEYS = {"users.view", "users.create", "users.edit", "users.delete", "users.reset", "users.revoke_sub", "users.next_plan"}


def has_perm(admin, key: str) -> bool:
    if admin.role == "sudo":
        return True
    p = admin.permissions or {}
    if key in DEFAULT_OFF:  # فقط وقتی مدیر اصلی صریحاً فعال کند
        return bool(p.get("*") and False) or bool(p.get(key))
    if not p:  # ادمین‌های قدیمی بدون تنظیم دسترسی: رفتار قبلی حفظ می‌شود
        return True
    if p.get("*"): return True
    if key in p: return bool(p[key])
    return key not in LEGACY_KEYS  # کلیدهای جدید برای ادمین‌های قدیمی پیش‌فرض مجاز است


def effective(admin) -> dict:
    return {k: has_perm(admin, k) for k in KEYS}
