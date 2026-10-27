# SubHub — پنل مرکزی مدیریت و ادغام اشتراک

نسخهٔ فعلی یک پیاده‌سازی توسعه‌ای چندبخشی است که API، مدل داده، صف Outbox، همگام‌سازی مصرف، توکن اشتراک، خروجی‌های اولیهٔ چند کلاینت، داشبورد React و استقرار Docker را کنار هم قرار می‌دهد. **این نسخه هنوز پذیرش تولیدی همهٔ فازهای پرامپت اصلی را پاس نکرده است.** پیش از اتصال به سرویس واقعی و ارائه به مشتری، بخش‌های «محدودیت‌های فعلی» را بررسی کنید.

## نصب سریع (روی سرور اوبونتو/دبیان، با کاربر root)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/ParvaneZone/ParvMarz/main/install.sh)
```

اسکریپت در صورت نیاز Docker را نصب می‌کند، نام‌کاربری/رمز مدیر و پورت را می‌پرسد (یا خودش می‌سازد)، رازهای تصادفی قوی تولید می‌کند و پنل را بالا می‌آورد. سپس `http://IP:8000/dashboard/` را باز کنید. به‌روزرسانی: همان دستور با `update` در انتها. مسیر نصب: `/opt/parvmarz`.

## اجرا با Docker (فقط Docker لازم است)

```bash
cp .env.example .env      # اختیاری؛ بدون آن هم بالا می‌آید
docker compose up -d --build
```

- کلیدهای `JWT_SECRET`، `SUBSCRIPTION_HMAC_KEY` و `CREDENTIALS_ENCRYPTION_KEY` اگر خالی/placeholder باشند در اولین اجرا خودکار ساخته و در volume داده (`/app/data/secrets.json`) ذخیره می‌شوند؛ نیازی به `python`/`openssl`/`parvmarz` روی میزبان نیست.
- اگر `INITIAL_ADMIN_USERNAME` خالی باشد `admin` و اگر `INITIAL_ADMIN_PASSWORD` خالی باشد رمز تصادفی ساخته می‌شود. رمز در لاگ چاپ **نمی‌شود**؛ با این دستور بخوانید:

```bash
docker compose exec subhub cat /app/data/initial-admin.txt
```

- **پورت**: اگر ۸۰۰۰ روی سرور اشغال است، در `.env` مقدار `PORT=8080` (یا هر پورت آزاد) بگذارید؛ داشبورد روی `http://IP:PORT/dashboard/` است.
- `PUBLIC_BASE_URL` خالی = `http://localhost:PORT`. برای لینک اشتراک درست، آن را روی آدرس واقعی (`http://IP:PORT` یا `https://دامنه`) بگذارید و `docker compose up -d` را دوباره بزنید.
- شبکهٔ کند/ایران: در `.env` مقدار `NPM_REGISTRY=https://registry.npmmirror.com` (و در صورت نیاز `PIP_INDEX_URL`) را بگذارید. تایم‌اوت و retry پیش‌فرض بالاست.
- سلامت: `/health` و `/api/health`؛ داشبورد: `/dashboard/`؛ مستندات: `/docs`.

### رمز مدیر

مدیر اولیه فقط وقتی ساخته می‌شود که وجود نداشته باشد؛ تغییر `INITIAL_ADMIN_PASSWORD` در `.env` بعد از ساخته شدن اثری ندارد. برای ریست رمز:

```bash
docker compose exec subhub python -m cli reset-admin-password --username admin
```

### قفل ورود

۵ تلاش ناموفق برای هر ترکیب IP+نام‌کاربری = ۱۵ دقیقه قفل (شمارنده در حافظه است). برای پاک کردن: `docker compose restart subhub`. فقط برای تست: `LOGIN_RATE_LIMIT_ENABLED=false`.

### HTTP یا HTTPS

احراز هویت با توکن Bearer است (کوکی استفاده نمی‌شود)، پس روی HTTP ساده هم کار می‌کند. اما در اینترنت عمومی رمز و توکن بدون رمزگذاری می‌رود؛ برای استفادهٔ واقعی پشت HTTPS (`deploy/Caddyfile.example` یا `deploy/nginx.conf.example`) بروید.

## منوی ترمینال

دستور `parvmarz` (توسط install.sh نصب می‌شود؛ یا داخل پوشهٔ پروژه `bash parvmarz.sh`) منویی دارد برای: وضعیت، لاگ، استارت/استاپ/ری‌استارت، آپدیت، ویرایش `.env`، تغییر پورت/آدرس، ریست رمز مدیر، نمایش رمز اولیه، پاک کردن قفل ورود، بکاپ، بیلد مجدد و حذف.

## اجرای توسعه

Python 3.12 یا جدیدتر:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env
subhub-cli init-db
subhub-cli admin-create
uvicorn app.main:app --reload
pytest -q
```

## قابلیت‌های موجود

- مدل‌های Admin، Panel، PanelInbound، Service، ServiceItem، User، UserPanelAccount، UserTemplate، UsageLog، AuditLog، SyncTask و Setting.
- احراز هویت JWT، هش رمز bcrypt، ابطال توکن‌های مدیر پس از تغییر رمز، قفل موقت تلاش‌های ورود و رمزنگاری Fernet برای اعتبارنامهٔ پنل.
- API پایه برای مدیریت پنل، سرویس، مدیر، کاربر، قالب، عملیات گروهی، آمار، audit و تنظیمات.
- ایجاد تسک Outbox در تغییرات کاربر، retry با backoff، worker دوره‌ای، پایش سلامت پنل، همگام‌سازی مصرف و تشخیص انقضا/محدودیت.
- HMAC برای لینک اشتراک؛ اعتبارسنجی نسخهٔ توکن پیش از استفاده از کش؛ کش کوتاه‌مدت در حافظه و دیتابیس؛ stale-if-error برای لینک‌های بالادستی.
- ادغام و حذف لینک‌های تکراری و خروجی اولیهٔ V2Ray، Clash و sing-box.
- رابط React دوزبانهٔ پایه با فهرست کاربران، فیلترها، ایجاد کاربر، عملیات سریع، پنل‌ها و سرویس‌ها.
- Docker چندمرحله‌ای، Compose، Alembic، CLI، بکاپ چرخشی SQLite، مثال‌های Caddy/Nginx و CI.

## درایورها و سازگاری API

درایور Marzban/Marzdar و adapter سازگار با API آن برای PasarGuard در این نسخه موجود است. آدرس‌ها و payloadها باید با Swagger همان نسخهٔ سرور واقعی بررسی شوند. **درایورهای Marzban/Marzdar/Marzyar (API یکسان Marzban، با ادمین نمایندگی) و PasarGuard (کلید `pg_key_...` یا ورود، گروه‌ها) نیز موجودند؛ درایور Rebecca (ویژهٔ ادمین نمایندگی/ساده با کلید API به‌شکل `rk_...` در فیلد رمز؛ سرویس‌های Rebecca به‌عنوان «گروه» خوانده می‌شوند) بر پایهٔ openapi.json ساخته شده ولی روی پنل واقعی آزموده نشده است.**؛ افزودن آن‌ها به فهرست نوع پنل به معنی پشتیبانی عملیاتی نیست. بدون نمونهٔ دسترسی به `/openapi.json` یا `/docs` همان پنل، نباید سازگاری آن‌ها را فرض کرد.

## محدودیت‌های فعلی — مهم

- برای دریافت لینک اشتراک از پنل واقعی، ساخت کاربر و قالب payload باید با نسخهٔ دقیق API آن پنل آزموده شود. مسیرها و schemaهای API بین نسخه‌ها ممکن است فرق داشته باشند.
- خروجی Clash و sing-box پوشش کامل همهٔ پارامترهای Reality، TLS، Hysteria2 و Shadowsocks را ندارد؛ باید با کانفیگ‌های واقعی و کلاینت‌های هدف اعتبارسنجی شود.
- داشبورد هنوز فرم‌های کامل ساخت/ویرایش پنل، سرویس، مدیر و قالب، مدیریت همهٔ تنظیمات و همهٔ عملیات گروهی را ندارد؛ این عملیات از API قابل دسترسی‌اند.
- محدودسازی تلاش ورود در حافظهٔ همان پروسه است، نه Redis/دیتابیس؛ برای چند worker یا چند replica باید shared rate limiter اضافه شود.
- قفل per-user بین چند worker به‌صورت توزیع‌شده پیاده‌سازی نشده است. برای production چند replica، قفل دیتابیسی/Redis و یک scheduler اختصاصی لازم است.
- بکاپ خودکار فعلی برای SQLite است؛ برای MariaDB/MySQL/PostgreSQL باید dump/restore اختصاصی همان موتور اضافه و تست شود.
- مهاجرت اولیه از metadata مدل ساخته می‌شود؛ برای ارتقای نسخه‌های بعدی باید migrationهای Alembic افزایشی و مستقل نوشته شوند.
- محافظت SSRF با `PANEL_ALLOW_PRIVATE_ADDRESSES=false` شامل resolve کردن DNS است؛ جلوگیری از DNS rebinding هنگام اتصال و کنترل مقصد پس از redirect هنوز باقی است.
- تست‌های واحد فعلی (شامل فرمت‌های Clash/sing-box/v2ray-json) با موفقیت اجرا شده‌اند. تست یکپارچه روی پنل واقعی، lint/type-check نهایی، build فرانت‌اند و ساخت/اجرای نهایی Docker در محیط فعلی به‌دلیل نبود دسترسی شبکه اجرا نشده‌اند؛ بنابراین این موارد هنوز معیار پذیرش تأییدشده محسوب نمی‌شوند.

## امنیت عملیاتی

کلیدهای `.env` را commit نکنید. در محیط تولید، HTTPS، CORS محدود، کلیدهای مستقل و تصادفی، پشتیبان‌گیری خارج از سرور و دسترسی محدود به `/docs` را تنظیم کنید. پیش از استفادهٔ واقعی، درایورها و خروجی اشتراک را با پنل و کلاینت واقعی تست کنید.
