# عیب‌یابی SubHub / ParvMarz

فهرست مشکلاتی که هنگام نصب و آپدیت دیده شده و راه‌حل هرکدام. (همه‌ی اصلاح‌های کد در همین ریپو اعمال شده‌اند.)

## ۱) بیلد داشبورد: `TS7006 Parameter 'e' implicitly has an 'any' type`
- **علت:** `tsconfig` در حالت `strict` است و پارامتر `onSubmit` تایپ نداشت.
- **اصلاح:** در `app/dashboard/src/main.tsx` تایپ `React.FormEvent<HTMLFormElement>` به `onSubmit` اضافه شد.

## ۲) کانتینر مدام ری‌استارت می‌شود: `FAILED: No 'script_location' key found in configuration`
- **علت:** `alembic.ini` داخل ایمیج کپی نشده بود.
- **اصلاح:** در `Dockerfile` خط `COPY alembic.ini ./` اضافه شد. (در `.dockerignore` هم نباید باشد.)

## ۳) صفحه‌ی داشبورد کاملاً سفید است (در لاگ: `GET /dashboard/assets/... 404`)
- **علت:** فقط `index.html` سرو می‌شد و برای `/dashboard/assets/` مسیری تعریف نشده بود.
- **اصلاح:** در `app/main.py` پوشه‌ی `dist/assets` روی `/dashboard/assets` mount شد.

## ۴) لاگین «نام کاربری یا رمز عبور نادرست است» با رمز درست
- **علت:** Docker Compose علامت `$` را در مقدار `.env` متغیر حساب می‌کند. رمزی مثل `abc$$` در واقع چیز دیگری ذخیره می‌شود.
- **راه‌حل:** رمز را فقط با حرف و عدد بگذارید، یا داخل تک‌کوتیشن: `INITIAL_ADMIN_PASSWORD='abc$123'`.
- مدیر اولیه فقط وقتی ساخته می‌شود که وجود نداشته باشد؛ بعد از ساخته شدن، تغییر `.env` اثری ندارد. برای ریست رمز:
  ```bash
  docker compose exec subhub python -m cli reset-admin-password --username admin
  ```
  یا (فقط روی نصب تازه و بدون داده) `docker compose down -v && docker compose up -d`.
- نکته: `parvmarz.sh` از این نسخه به بعد مقدارهای دارای `$` را خودکار تک‌کوتیشن می‌کند.

## ۵) نام سرویس و دستور CLI
- نام سرویس در `docker-compose.yml` برابر `subhub` است (نه `app`).
- دستور CLI داخل کانتینر اجرا می‌شود:
  ```bash
  docker compose exec subhub subhub-cli --help
  docker compose exec subhub python -m cli --help
  ```
- منوی ترمینال روی میزبان: `parvmarz` (یا `bash /opt/parvmarz/parvmarz.sh`).

## ۶) آپدیت روی سرور
```bash
cd /opt/parvmarz
git pull origin main          # اگر نصب با git بوده
docker compose up -d --build
docker compose logs -f --tail=50 subhub
```
اگر نصب با zip بوده، کد جدید را با `rsync -a --exclude .git --exclude .env` روی پوشه کپی کنید، سپس همان `up -d --build`. فایل `.env` و ولوم داده دست نمی‌خورند.
مهاجرت دیتابیس (`alembic upgrade head`) موقع بالا آمدن کانتینر خودکار اجرا می‌شود.

## ۷) پوش به گیت‌هاب (Termux)
- گیت‌هاب رمز حساب را قبول نمی‌کند؛ در Password باید **Personal Access Token** (با دسترسی `repo`) بدهید.
- `nothing to commit` یعنی فایل‌ها با ریپو یکی هستند.
- ذخیره‌ی توکن: `git config --global credential.helper store`.
- توکن را جای عمومی یا چت نفرستید. اگر فرستاده‌اید، از Settings ← Developer settings باطلش کنید.

## ۸) ظاهر داشبورد (حالت تیره / OLED)
- رنگ‌ها با متغیرهای CSS (`--bg`, `--card`, `--fg`, `--muted`...) در `app/dashboard/src/style.css` تعریف شده‌اند و حالت رنگی Chakra با تم انتخابی همگام می‌شود؛ قبلاً ورودی‌ها و جدول‌ها در حالت تیره روشن می‌ماندند و خوانا نبودند.
- سربرگ جدول‌ها دیگر فاصله‌ی حروف/بزرگ‌سازی نمی‌گیرد (فاصله‌ی حروف اتصال فارسی را می‌شکند).
- آدرس‌ها و اعداد چپ‌به‌راست نمایش داده می‌شوند و تب‌ها روی موبایل اسکرول افقی دارند.
