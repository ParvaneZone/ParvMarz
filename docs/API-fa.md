# راهنمای اتصال ربات‌ها و ابزارهای خارجی به پنل

برای رباتی که پنل شما را مستقیم پشتیبانی نمی‌کند، کافی است آدرس پنل (`PUBLIC_BASE_URL`) را به‌جای آدرس پنل مرزبان/پاسارگارد بدهید و با همین مسیرها کار کنید.

## مستندات تعاملی (Swagger)
- در `.env` مقدار `OPENAPI_ENABLED=true` بگذارید و سرویس را ریستارت کنید.
- Swagger: `/docs` · ReDoc: `/redoc` · اسکیما: `/openapi.json`
- بدون فعال‌سازی بالا: بعد از ورود، `GET /api/docs/openapi.json` و `GET /api/docs/api.md` (نماینده فقط مسیرهای خودش را می‌بیند).
- خروجی آفلاین (مثل `export_openapi.py` در پاسارگارد): `python export_openapi.py` ← `docs/openapi.json` و `docs/API-reference-fa.md` (با `--agent` فقط مسیرهای نماینده).

## احراز هویت
| روش | نحوه |
|---|---|
| توکن | `POST /api/admin/token` با JSON `{"username","password"}` (و `"otp"` اگر 2FA فعال است) ← `{"access_token","token_type":"bearer"}` ← هدر `Authorization: Bearer <token>` |
| کلید API (مناسب ربات) | ساخت: `POST /api/admin/api-keys` ← کلید `pmk_...` ← هدر `X-API-Key: <key>` یا `Authorization: Bearer <key>` |

کلید API همان دسترسی‌های ادمین صاحبش را دارد و نمی‌تواند رمز، 2FA یا کلیدها را مدیریت کند. بعد از ۵ تلاش ناموفق ورود، ۱۵ دقیقه قفل (429) می‌شود.

> خطاها: `{"detail": {"detail": "پیام", "code": "CODE"}}`؛ خطای ورودی (422) قالب FastAPI دارد.

## تفاوت‌ها با مرزبان/پاسارگارد (مهم برای ربات‌ها)
| مورد | مرزبان/پاسارگارد | این پنل |
|---|---|---|
| انتخاب کانفیگ کاربر | `proxies` / `inbounds` / `group_ids` | `service_id` (سرویس ساخته‌شده در پنل) |
| انقضا | عدد unix (ثانیه؛ `0` = نامحدود) | تاریخ ISO-8601 یا `null` = نامحدود؛ هنگام ساخت می‌توان `duration_days` داد |
| حجم | بایت؛ `0` = نامحدود | بایت؛ `null` = نامحدود |
| لینک اشتراک | `subscription_url` کامل | `subscription_url` (مسیر `/sub/...`؛ در حالت جداسازی آدرس کامل) |
| مالک کاربر | ادمین سازنده | ادمین سازنده؛ مدیر اصلی با `set-owner` عوض می‌کند |

## مسیرهای اصلی (سازگار با ربات‌ها)
| متد و مسیر | کار |
|---|---|
| `POST /api/admin/token` | ورود |
| `GET /api/admin` | اطلاعات ادمین جاری و دسترسی‌ها |
| `GET /api/admin/account` | سهمیه، مصرف و انقضای ادمین |
| `GET /api/services` | لیست سرویس‌های مجاز (برای `service_id`) |
| `GET /api/templates` | قالب‌های ساخت کاربر |
| `GET /api/users` | لیست؛ فیلتر: `q, status, service_id, expiring_in_days, near_limit_percent, sort, limit(≤200), offset` |
| `POST /api/user` | ساخت کاربر |
| `POST /api/users/bulk-create` | ساخت گروهی (`prefix, count, start, service_id, ...`) |
| `GET /api/user/{username}` | دریافت کاربر |
| `PUT /api/user/{username}` | ویرایش (فقط فیلدهای ارسال‌شده) — شامل `service_id` برای تغییر سرویس |
| `DELETE /api/user/{username}` | حذف |
| `POST /api/user/{username}/reset` | ریست مصرف |
| `POST /api/user/{username}/revoke_sub` | ابطال و ساخت مجدد لینک اشتراک |
| `GET /api/user/{username}/usage` | تاریخچه مصرف |
| `GET /api/user/{username}/sync-status` | وضعیت همگام‌سازی با پنل‌ها |
| `POST /api/user/{username}/active-next` | فعال‌سازی پلن بعدی |

### نمونه
```bash
BASE=https://panel.example.com
TOKEN=$(curl -s $BASE/api/admin/token -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"***"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# ساخت کاربر: ۳۰ گیگ، ۳۰ روز
curl -s $BASE/api/user -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"username":"ali_01","service_id":1,"data_limit":32212254720,"duration_days":30}'

# تغییر سرویس (حجم و زمان باقی‌مانده حفظ می‌شود؛ در پنل‌های جدید حساب ساخته می‌شود)
curl -s -X PUT $BASE/api/user/ali_01 -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"service_id":2}'
```

```python
import httpx
c = httpx.Client(base_url="https://panel.example.com", headers={"X-API-Key": "pmk_..."})
u = c.post("/api/user", json={"username": "ali_01", "service_id": 1, "data_limit": 10 * 1024**3, "duration_days": 30}).json()
print(u["subscription_url"])
```

## تغییر سرویس کاربر
`PUT /api/user/{username}` با `{"service_id": N}`:
- حساب پنل‌هایی که در سرویس جدید نیستند حذف می‌شود؛ در پنل‌های مشترک حساب فعلی به‌روز می‌شود؛ برای پنل‌های جدید حساب تازه ساخته می‌شود.
- حجم هر حساب بر پایه «حجم باقی‌مانده کاربر» تنظیم می‌شود و انقضا همان انقضای کاربر است؛ پس مجموع هرگز از سقف حجم/زمان بیشتر نمی‌شود.
- سرویس مقصد باید فعال و در `allowed_services` ادمین باشد (۴۰۳/۴۰۴ در غیر این صورت).

## قالب صفحه اشتراک
- ۵ قالب: `classic` (همیشه آزاد) و `aurora`, `midnight`, `paper`, `sunset`.
- مدیر اصلی هنگام ساخت/ویرایش ادمین، دسترسی‌های `sub.tpl.<id>` را روشن یا خاموش می‌کند (پیش‌فرض خاموش).
- ادمین قالب کاربران خودش را انتخاب می‌کند: `GET /api/admin/sub-templates` و `PUT /api/admin/sub-template` با `{"id":"aurora"}`. اگر دسترسی برداشته شود، به `classic` برمی‌گردد.

## ربات تلگرام اعلان‌ها
1. در `.env`: `TELEGRAM_BOT_TOKEN=<توکن BotFather>` (اختیاری: `TELEGRAM_ADMIN_CHAT_ID`). ربات با **وب‌هوک** کار می‌کند و پنل خودش موقع بالا آمدن وب‌هوک را روی `PUBLIC_BASE_URL/api/telegram/webhook` ست می‌کند؛ پس `PUBLIC_BASE_URL` باید HTTPS عمومی (پورت ۴۴۳/۸۰/۸۸/۸۴۴۳) باشد.
2. هر ادمین از «اکانت من ← ربات تلگرام ← اتصال» لینک یک‌بارمصرف می‌گیرد و در تلگرام Start می‌زند. چت بدون اتصال هیچ پیامی نمی‌گیرد.
3. دستورها: `/status` وضعیت اکانت، `/stop` قطع اتصال، `/help`.
4. API: `GET /api/admin/telegram`، `POST /api/admin/telegram/link`، `DELETE /api/admin/telegram` (فقط با ورود عادی، نه کلید API).

| رویداد | مدیر اصلی | ادمین مربوطه |
|---|---|---|
| ورود موفق/ناموفق/قفل‌شدن (نام کاربری + آیپی) | همه | فقط اکانت خودش |
| اتمام حجم، پایان زمان یا نزدیک انقضای کاربر | همه | فقط کاربران خودش |
| اتمام حجم کل یا انقضای اکانت ادمین | همه | فقط اکانت خودش |
| خطای مهم سیستم، قطع/وصل پنل، شکست همگام‌سازی یا پشتیبان | ✔ | ✘ |

پیام‌ها فقط نوع خطا و مسیر را دارند، نه متن استثنا، رمز یا بدنه درخواست.
