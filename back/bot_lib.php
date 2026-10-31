<?php
declare(strict_types=1);
/**
 * bot_lib.php — ربات تلگرام تست/فروش برای هر نماینده (کتابخانه؛ مستقیم اجرا نمی‌شود، توسط core.php خوانده می‌شود).
 * هر نماینده ربات، ظاهر/متن، تنظیمات، پلن، سفارش، کاربران و کیف پول جدا دارد (همه‌چیز با agent_id/bot_id جدا می‌شود).
 * ساخت حساب فقط از مسیر createUserAccount() انجام می‌شود، پس سقف‌های نمایندگی خودکار اعمال می‌شوند.
 */

// ------------------------------------------------------------------ پیش‌فرض‌ها (دکمه‌ها، متن‌ها، تنظیمات)
/** اعتبارسنجی بسته‌های حجم اضافه؛ مقدار ذخیره‌شده فقط داده‌ی هر نماینده است و هرگز به config.php نمی‌رود. */
function botTrafficPacksClean($v): array {
    if (is_string($v)) {
        $raw = trim($v);
        $decoded = json_decode($raw, true);
        if (!is_array($decoded) || json_last_error() !== JSON_ERROR_NONE) fail('قالب بسته‌های حجم باید JSON آرایه‌ای باشد', 'Traffic packs must be a JSON array');
        $v = $decoded;
    }
    if (!is_array($v) || count($v) > 20) fail('حداکثر ۲۰ بسته‌ی حجم مجاز است', 'At most 20 traffic packs are allowed');
    $out = [];
    foreach ($v as $p) {
        if (!is_array($p) || !array_key_exists('gb', $p) || !array_key_exists('price', $p) || !is_numeric($p['gb']) || !is_numeric($p['price']))
            fail('هر بسته باید شامل gb و price عددی باشد', 'Each traffic pack needs numeric gb and price');
        $gb = round((float)$p['gb'], 3); $price = (int)$p['price'];
        if (!is_finite($gb) || $gb <= 0 || $gb > 100000 || $price < 1 || $price > 1000000000)
            fail('حجم یا قیمت یکی از بسته‌ها نامعتبر است', 'A traffic pack has an invalid GB amount or price');
        $out[] = ['gb' => $gb, 'price' => $price];
    }
    return array_values($out);
}
/** دکمه‌های منوی اصلی ربات: کلید => عنوان پیش‌فرض */
function botMenuKeys(): array {
    return ['test' => '🧪 دریافت تست', 'buy' => '🛒 خرید اشتراک', 'wal' => '💰 کیف پول و دعوت', 'acc' => '👤 حساب‌های من', 'dl' => '📥 دانلود برنامه',
            'sup' => '🆘 پشتیبانی', 'tuts' => '📚 آموزش‌ها', 'faqs' => '❓ سوالات متداول', 'club' => '🎁 باشگاه مشتریان'];
}
/** چیدمان پیش‌فرض: هر آیتم k = کلید، on = روشن (۱) یا خاموش (۰)، j = ۱ یعنی کنار دکمه‌ی قبلی در همان ردیف */
function botMenuDefault(): array {
    $j = ['wal' => 1, 'dl' => 1]; $o = [];
    foreach (array_keys(botMenuKeys()) as $k) $o[] = ['k' => $k, 'on' => 1, 'j' => $j[$k] ?? 0];
    return $o;
}
/** ورودی دلخواه را به یک لیست معتبر تبدیل می‌کند: کلیدهای ناشناخته حذف، تکراری حذف، کلیدهای جاافتاده به آخر اضافه می‌شوند */
function botMenuClean($v): array {
    $def = []; foreach (botMenuDefault() as $x) $def[$x['k']] = $x;
    $out = []; $seen = [];
    foreach ((is_array($v) ? $v : []) as $it) {
        if (!is_array($it)) continue;
        $k = (string)($it['k'] ?? '');
        if (!isset($def[$k]) || isset($seen[$k])) continue;
        $seen[$k] = 1;
        $out[] = ['k' => $k, 'on' => !empty($it['on']) ? 1 : 0, 'j' => !empty($it['j']) ? 1 : 0];
    }
    foreach ($def as $k => $x) if (!isset($seen[$k])) $out[] = $x;
    if ($out) $out[0]['j'] = 0;
    return $out;
}
function botDefaults(): array {
    return [
        'menu' => botMenuDefault(),
        't_on' => 1, 't_count' => 1, 't_gb' => 0.3, 't_days' => 1, 't_dev' => '', 's_dev' => '', 'panel' => 0, 'svc' => 0, 'grp' => 0, 'grps' => [],
        'email_domain' => '', 'support' => '', 'dl_url' => '',
        'g_on' => 0, 'g_amt' => 0, 'cb_on' => 0, 'cb_pct' => 0, 'cb_max' => 0, 'ref_on' => 0, 'ref_amt' => 0, 'promo_on' => 0, 'promo_pct' => 0,
        // شارژ کیف پول توسط مشتری (مرحله ۳): topup_min/topup_max به تومان؛ topup_max=0 یعنی بدون سقف
        'topup_on' => 0, 'topup_min' => 10000, 'topup_max' => 50000000,
        // نمایش کارت‌ها (مرحله ۴): all = تا ۳ کارت فعالِ مجازِ آن مبلغ | rotate = هر سفارش یک کارت به‌صورت چرخشی
        'card_mode' => 'all', 'traffic_packs' => [], 'alerts_on' => 1, 'tk_max_open' => 3,
        // باشگاه مشتریان و بکاپ خودکار (مرحله ۸؛ پیش‌فرض خاموش). club_rate = تومانِ هر امتیاز؛ backup_every = day | week
        'club_on' => 0, 'club_points_day' => 10, 'club_streak_n' => 7, 'club_streak_bonus' => 50, 'club_rate' => 10, 'club_min_convert' => 100,
        'backup_on' => 0, 'backup_every' => 'day',
        // گزارش رویدادها (مرحله ۶): گروه اختیاری و نگاشت نوع رویداد → شماره‌ی تاپیک
        'events_chat_id' => '', 'events_topics' => [],
        // عضویت اجباری: fj_on روشن/خاموش؛ fj = حداکثر ۵ خط «@کانال» یا «-100… https://t.me/…»
        'fj_on' => 0, 'fj' => [],
        // l = متن دکمه، e = شناسه‌ی عددی ایموجی سفارشی، s = رنگ (primary آبی | success سبز | danger قرمز | خالی = پیش‌فرض تلگرام)
        'btn' => [
            'test' => ['l' => 'دریافت تست', 'e' => '', 's' => 'success'], 'buy' => ['l' => 'خرید اشتراک', 'e' => '', 's' => 'primary'],
            'wal' => ['l' => 'کیف پول و دعوت', 'e' => '', 's' => ''], 'acc' => ['l' => 'حساب‌های من', 'e' => '', 's' => ''],
            'dl' => ['l' => 'دانلود برنامه', 'e' => '', 's' => 'primary'], 'sup' => ['l' => 'پشتیبانی', 'e' => '', 's' => ''],
            'back' => ['l' => 'بازگشت', 'e' => '', 's' => ''], 'cancel' => ['l' => 'لغو سفارش', 'e' => '', 's' => 'danger'],
            'plan' => ['l' => '', 'e' => '', 's' => 'primary'], 'wpay' => ['l' => 'پرداخت از موجودی', 'e' => '', 's' => 'success'],
            'cpay' => ['l' => 'کارت به کارت', 'e' => '', 's' => 'primary'], 'pass' => ['l' => 'رمز جدید', 'e' => '', 's' => 'primary'],
            'apr' => ['l' => 'تأیید', 'e' => '', 's' => 'success'], 'rej' => ['l' => 'رد', 'e' => '', 's' => 'danger'],
            'adm' => ['l' => 'پنل مدیریت', 'e' => '', 's' => ''],
        ],
        'txt' => [
            'welcome' => 'خوش آمدید! از منوی زیر انتخاب کنید.', 'menu' => 'از منوی زیر انتخاب کنید:', 'plans' => 'یکی از پلن‌ها را انتخاب کنید:',
            'paynote' => 'بعد از واریز، عکس رسید را همین‌جا ارسال کنید.', 't_test' => 'اکانت تست', 't_sale' => 'اشتراک',
            'steps' => "۱) برنامه را از لینک زیر دانلود و نصب کنید.\n۲) با ایمیل و رمز بالا وارد برنامه شوید.",
            'ordered' => 'سفارش شما ثبت شد و پس از بررسی، اطلاعات اکانت همین‌جا ارسال می‌شود.',
        ],
    ];
}
/** عنوان فارسی هر دکمه/متن برای فرم پورتال نماینده */
function botUiMeta(): array {
    return ['btn' => [['test', 'دکمه‌ی دریافت تست'], ['buy', 'دکمه‌ی خرید اشتراک'], ['wal', 'دکمه‌ی کیف پول و دعوت'], ['acc', 'دکمه‌ی حساب‌های من'], ['dl', 'دکمه‌ی دانلود برنامه'],
                      ['sup', 'دکمه‌ی پشتیبانی'], ['back', 'دکمه‌ی بازگشت'], ['cancel', 'دکمه‌ی لغو سفارش'], ['plan', 'ظاهر دکمه‌ی پلن‌ها (متن = نام و قیمت پلن)'],
                      ['wpay', 'دکمه‌ی پرداخت از موجودی'], ['cpay', 'دکمه‌ی پرداخت کارت‌به‌کارت'], ['pass', 'دکمه‌ی رمز جدید'],
                      ['apr', 'دکمه‌ی تأیید (ادمین ربات)'], ['rej', 'دکمه‌ی رد (ادمین ربات)'], ['adm', 'دکمه‌ی پنل مدیریت (فقط ادمین ربات)']],
            'txt' => [['welcome', 'پیام خوش‌آمد'], ['menu', 'متن زیر منو'], ['plans', 'متن انتخاب پلن'], ['paynote', 'متن بعد از اطلاعات کارت'], ['t_test', 'عنوان اکانت تست'],
                      ['t_sale', 'عنوان اکانت خریداری‌شده'], ['steps', 'راهنمای نصب بعد از اطلاعات اکانت'], ['ordered', 'پیام ثبت سفارش']]];
}
function botCfg(PDO $db, int $agId): array {
    $raw = json_decode(ownerGet($db, $agId, 'bot_cfg', ''), true);
    if (!is_array($raw)) $raw = [];
    $d = botDefaults();
    $c = array_merge($d, array_intersect_key($raw, $d));
    $c['fj'] = is_array($c['fj']) ? array_values(array_filter(array_map('strval', $c['fj']), fn($x) => $x !== '')) : [];
    $c['card_mode'] = $c['card_mode'] === 'rotate' ? 'rotate' : 'all';
    $c['backup_every'] = $c['backup_every'] === 'week' ? 'week' : 'day';
    try { $c['traffic_packs'] = botTrafficPacksClean($c['traffic_packs']); } catch (Throwable $e) { $c['traffic_packs'] = []; }
    $c['alerts_on'] = (int)$c['alerts_on'] === 0 ? 0 : 1;
    $c['menu'] = botMenuClean($raw['menu'] ?? null);
    try { $c['events_chat_id'] = botEventChatClean($c['events_chat_id']); } catch (Throwable $e) { $c['events_chat_id'] = ''; }
    try { $c['events_topics'] = $c['events_chat_id'] !== '' ? botEventTopicsClean($c['events_topics']) : []; } catch (Throwable $e) { $c['events_topics'] = []; }
    $c['btn'] = $d['btn'];
    foreach ($d['btn'] as $k => $_) {
        $s = (isset($raw['btn']) && is_array($raw['btn']) && isset($raw['btn'][$k]) && is_array($raw['btn'][$k])) ? $raw['btn'][$k] : null;
        if ($s === null) continue;
        if (isset($s['l']) && $s['l'] !== '') $c['btn'][$k]['l'] = (string)$s['l'];
        if (array_key_exists('e', $s)) $c['btn'][$k]['e'] = (string)$s['e'];
        if (array_key_exists('s', $s)) $c['btn'][$k]['s'] = (string)$s['s'];
    }
    $c['txt'] = $d['txt'];
    foreach ($d['txt'] as $k => $_) {
        $v = (isset($raw['txt']) && is_array($raw['txt']) && isset($raw['txt'][$k])) ? $raw['txt'][$k] : '';
        if (is_string($v) && trim($v) !== '') $c['txt'][$k] = $v;
    }
    if ((!isset($raw['txt']['welcome']) || $raw['txt']['welcome'] === '') && isset($raw['welcome']) && is_string($raw['welcome']) && $raw['welcome'] !== '') $c['txt']['welcome'] = $raw['welcome']; // سازگاری نسخه‌ی قبل
    return $c;
}
function botCleanTxt($v, int $max): string {
    $s = trim((string)preg_replace('/[\x00-\x09\x0B-\x1F\x7F]/u', '', str_replace("\r", '', (string)$v)));
    return mb_substr($s, 0, $max);
}
/** سرویس‌هایی که مدیر برای این نماینده فعال کرده: [[panelId, serviceId], ...] (پنل پیش‌فرض به شناسه‌ی واقعی تبدیل می‌شود) */
/** ربات متعلق به ادمین اصلی است؟ (حساب ادمین: همه‌ی سرویس‌ها و پنل‌ها مجازند و سقف نمایندگی ندارد) */
function botIsAdminOwner(array $agent): bool { return (string)($agent['role'] ?? '') === 'admin'; }
/** شرط SQL مالکیت حساب‌های کاربر (شامل «=?»؛ مقدار bind همان agent_id ربات است). حساب‌های ساخته‌شده توسط ادمین owner_id=NULL دارند و فقط در ربات ادمین مجازند. */
function botOwnSql(PDO $db, string $col, int $agId): string { return ($agId > 0 && $agId === (int)adminId($db)) ? '(' . $col . '=? OR ' . $col . ' IS NULL)' : $col . '=?'; }
function botAllowedSvcs(PDO $db, array $agent): array {
    if (botIsAdminOwner($agent)) return []; // ادمین: سرویس‌های پنلی در botSvcAllowed / botSvcOptions به‌صورت مستقیم از پنل‌های فعال خوانده می‌شوند
    $def = pnDefaultId($db); $o = []; $seen = [];
    foreach (agentSvcTokens($agent) as [$pid, $sid]) {
        if ($sid <= 0) continue;
        $p = $pid === 0 ? (int)$def : (int)$pid;
        if (isset($seen[$p . ':' . $sid])) continue;
        $seen[$p . ':' . $sid] = 1; $o[] = [$p, (int)$sid];
    }
    return $o;
}
function botSvcAllowed(PDO $db, array $agent, int $pid, int $sid): bool {
    if (botIsAdminOwner($agent)) { $r = $pid > 0 && $sid > 0 ? pnRow($db, $pid) : null; return $r && (int)$r['enabled'] === 1; }
    foreach (botAllowedSvcs($db, $agent) as [$p, $s]) if ($p === $pid && $s === $sid) return true;
    return false;
}
/** سرویس‌هایی (گروه‌های اپ) که مدیر از «نمایندگان ← سرویس‌ها» برای این نماینده فعال کرده یا خودِ نماینده ساخته؛ فقط سرویس‌های فعال */
function botGrantedGroups(PDO $db, array $agent): array {
    if (botIsAdminOwner($agent)) { // ادمین اصلی: همه‌ی سرویس‌های فعال
        return $db->query('SELECT g.id, g.name, g.panel_id, g.enabled, COALESCE(p.name, \'\') AS panel_name FROM svc_groups g LEFT JOIN panels p ON p.id=g.panel_id WHERE g.enabled=1 ORDER BY g.id')->fetchAll(PDO::FETCH_ASSOC);
    }
    $q = $db->prepare('SELECT g.id, g.name, g.panel_id, g.enabled, COALESCE(p.name, \'\') AS panel_name FROM svc_groups g LEFT JOIN panels p ON p.id=g.panel_id
        WHERE g.enabled=1 AND (g.owner_id=? OR g.id IN (SELECT group_id FROM agent_svc_grants WHERE agent_id=?)) ORDER BY g.id');
    $q->execute([(int)$agent['id'], (int)$agent['id']]);
    return $q->fetchAll(PDO::FETCH_ASSOC);
}
function botGroupAllowed(PDO $db, array $agent, int $gid): ?array {
    foreach (botGrantedGroups($db, $agent) as $g) if ((int)$g['id'] === $gid) return $g;
    return null;
}
/** گزینه‌های انتخاب سرویس در پورتال: سرویس‌های فعال‌شده‌ی نماینده (گروه‌ها) + سرویس‌های مجازِ پنل */
function botSvcOptions(PDO $db, array $agent): array {
    $out = [];
    if (botIsAdminOwner($agent)) { // ادمین نام پنل‌ها را هم می‌بیند
        foreach (botGrantedGroups($db, $agent) as $g) $out[] = ['key' => 'g:' . (int)$g['id'], 'label' => (string)$g['name'] . ((string)$g['panel_name'] !== '' ? ' — پنل: ' . $g['panel_name'] : '')];
        foreach ($db->query('SELECT id, name FROM panels WHERE enabled=1 ORDER BY id')->fetchAll(PDO::FETCH_ASSOC) as $pn) {
            $r = botTry(fn() => pn_list_services(panel($db, (int)$pn['id'])));
            if ($r['ok'] && !empty($r['v']['ok'])) foreach ((array)$r['v']['services'] as $x) $out[] = ['key' => (int)$pn['id'] . ':' . (int)$x['id'], 'label' => (string)$pn['name'] . ' — ' . (string)($x['name'] ?? $x['title'] ?? ('سرویس ' . (int)$x['id']))];
        }
        return $out;
    }
    foreach (botGrantedGroups($db, $agent) as $g) $out[] = ['key' => 'g:' . (int)$g['id'], 'label' => (string)$g['name']]; // نماینده فقط نام سرویس را می‌بیند، نه نام پنل
    $al = botAllowedSvcs($db, $agent);
    if (!$al) return $out;
    $by = [];
    foreach ($al as [$p, $s]) $by[$p][] = $s;
    $multi = count($by) > 1; $out = [];
    foreach ($by as $p => $sids) {
        $names = [];
        $r = botTry(fn() => pn_list_services(panel($db, (int)$p)));
        if ($r['ok'] && !empty($r['v']['ok'])) foreach ((array)$r['v']['services'] as $x) $names[(int)$x['id']] = (string)($x['name'] ?? $x['title'] ?? '');
        $pn = ''; // نام پنل هرگز به نماینده نشان داده نمی‌شود
        foreach ($sids as $sid) $out[] = ['key' => $p . ':' . $sid, 'label' => $pn . (($names[$sid] ?? '') !== '' ? $names[$sid] : 'سرویس ' . $sid)];
    }
    return $out;
}
/** ورودی را اعتبارسنجی و روی تنظیمات فعلی ادغام می‌کند؛ کلیدهای ارسال‌نشده همان مقدار قبلی می‌مانند. برای تست هیچ سقف سخت‌کدی نیست. */
function botCfgClean(PDO $db, array $agent, array $in): array {
    $c = botCfg($db, (int)$agent['id']);
    foreach (['t_on', 'g_on', 'cb_on', 'ref_on', 'promo_on', 'fj_on', 'topup_on', 'alerts_on', 'club_on', 'backup_on'] as $k) if (array_key_exists($k, $in)) $c[$k] = payFlag($in[$k]);
    foreach (['t_count' => 100000000, 'g_amt' => 100000000, 'cb_max' => 1000000000, 'ref_amt' => 100000000, 'cb_pct' => 100, 'promo_pct' => 90, 't_days' => 36500, 'topup_min' => 1000000000, 'topup_max' => 1000000000, 'tk_max_open' => 50, 'club_points_day' => 1000000, 'club_streak_n' => 365, 'club_streak_bonus' => 1000000, 'club_rate' => 1000000, 'club_min_convert' => 1000000000] as $k => $mx)
        if (array_key_exists($k, $in)) $c[$k] = payInt0($in[$k], $mx); // ۰ = نامحدود/بدون سقف در مواردی که معنا دارد
    if (array_key_exists('tk_max_open', $in)) $c['tk_max_open'] = max(1, (int)$c['tk_max_open']);
    if (array_key_exists('club_min_convert', $in)) $c['club_min_convert'] = max(1, (int)$c['club_min_convert']);
    if (array_key_exists('backup_every', $in)) {
        if (!in_array((string)$in['backup_every'], ['day', 'week'], true)) fail('دوره‌ی بکاپ نامعتبر است', 'Invalid backup period');
        $c['backup_every'] = (string)$in['backup_every'];
    }
    if (array_key_exists('topup_min', $in) || array_key_exists('topup_max', $in)) {
        $c['topup_min'] = max(1000, (int)$c['topup_min']);
        if ((int)$c['topup_max'] > 0 && (int)$c['topup_min'] > (int)$c['topup_max']) fail('حداقل مبلغ شارژ نباید بیشتر از حداکثر باشد', 'Top-up minimum exceeds maximum');
    }
    if (array_key_exists('t_gb', $in)) {
        $g = (float)$in['t_gb'];
        if ($g < 0 || $g > 1000000) fail('حجم تست نامعتبر است', 'Invalid test data amount');
        $c['t_gb'] = $g;
    }
    foreach (['t_dev', 's_dev'] as $k) {
        if (!array_key_exists($k, $in)) continue;
        $v = $in[$k];
        $c[$k] = ($v === null || $v === '') ? '' : (string)max(0, min(50, (int)$v)); // خالی = پیش‌فرض سیستم، ۰ = نامحدود
    }
    if (array_key_exists('svc_keys', $in)) {
        $ids = [];
        foreach ((array)$in['svc_keys'] as $k) if (preg_match('/^g:(\d+)$/', trim((string)$k), $m)) $ids[(int)$m[1]] = 1;
        $ids = array_keys($ids); $pan = 0;
        foreach ($ids as $gid) {
            $g = botGroupAllowed($db, $agent, $gid);
            if (!$g) fail('این سرویس توسط مدیر برای شما فعال نشده است', 'This service is not enabled for you by the admin', 403);
            if ($pan && $pan !== (int)$g['panel_id']) fail('سرویس‌های انتخابی ربات باید همگی روی یک پنل باشند', 'Bot services must all belong to the same panel');
            $pan = (int)$g['panel_id'];
        }
        $c['grps'] = $ids; $c['grp'] = $ids ? (int)$ids[0] : 0;
        if ($ids) { $c['panel'] = $pan; $c['svc'] = 0; $in['svc_key'] = 'keep'; }
    }
    if (array_key_exists('svc_key', $in) && $in['svc_key'] !== 'keep') {
        $key = trim((string)$in['svc_key']);
        if ($key === '') { $c['panel'] = 0; $c['svc'] = 0; $c['grp'] = 0; $c['grps'] = []; }
        elseif (preg_match('/^g:(\d+)$/', $key, $m)) {
            $g = botGroupAllowed($db, $agent, (int)$m[1]);
            if (!$g) fail('این سرویس توسط مدیر برای شما فعال نشده است', 'This service is not enabled for you by the admin', 403);
            $c['grp'] = (int)$g['id']; $c['panel'] = (int)$g['panel_id']; $c['svc'] = 0; $c['grps'] = [$c['grp']];
        }
        else {
            if (!preg_match('/^(\d+):(\d+)$/', $key, $m) || !botSvcAllowed($db, $agent, (int)$m[1], (int)$m[2]))
                fail('این سرویس توسط مدیر برای شما فعال نشده است', 'This service is not enabled for you by the admin', 403);
            $c['panel'] = (int)$m[1]; $c['svc'] = (int)$m[2]; $c['grp'] = 0; $c['grps'] = [];
        }
    }
    if (array_key_exists('email_domain', $in)) {
        $d = strtolower(trim((string)$in['email_domain']));
        if ($d !== '' && !preg_match('/^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+$/', $d)) fail('دامنه‌ی ایمیل نامعتبر است', 'Invalid email domain');
        $c['email_domain'] = $d;
    }
    if (array_key_exists('card_mode', $in)) {
        $m = (string)$in['card_mode'];
        if (!in_array($m, ['all', 'rotate'], true)) fail('حالت نمایش کارت‌ها نامعتبر است', 'Invalid card display mode');
        $c['card_mode'] = $m;
    }
    if (array_key_exists('menu', $in)) $c['menu'] = botMenuClean($in['menu']);
    if (array_key_exists('traffic_packs', $in)) $c['traffic_packs'] = botTrafficPacksClean($in['traffic_packs']);
    if (array_key_exists('events_chat_id', $in)) $c['events_chat_id'] = botEventChatClean($in['events_chat_id']);
    if (array_key_exists('events_topics', $in)) $c['events_topics'] = botEventTopicsClean($in['events_topics']);
    if ($c['events_chat_id'] === '') $c['events_topics'] = [];
    if (array_key_exists('fj', $in)) $c['fj'] = botFjClean($in['fj']);
    if (array_key_exists('support', $in)) $c['support'] = botCleanTxt($in['support'], 400);
    if (array_key_exists('dl_url', $in)) {
        $u = trim((string)$in['dl_url']);
        if ($u !== '' && !preg_match('#^https://[A-Za-z0-9.\-]+(:\d+)?(/[A-Za-z0-9_.~%\-/]*)?(\?[A-Za-z0-9_.~%\-=&+/:]*)?$#', $u)) fail('لینک دانلود باید https:// باشد', 'Download URL must be https://');
        $c['dl_url'] = $u;
    }
    if (isset($in['btn']) && is_array($in['btn'])) {
        foreach ($c['btn'] as $k => $_) {
            if (!isset($in['btn'][$k]) || !is_array($in['btn'][$k])) continue;
            $b = $in['btn'][$k];
            $l = mb_substr(botCleanTxt($b['l'] ?? '', 40), 0, 40);
            $e = preg_replace('/\D/', '', payDigits((string)($b['e'] ?? '')));
            if ($e !== '' && !preg_match('/^\d{5,25}$/', (string)$e)) fail('شناسه‌ی ایموجی نامعتبر است', 'Invalid emoji id');
            $s = (string)($b['s'] ?? '');
            if (!in_array($s, ['', 'primary', 'success', 'danger'], true)) fail('رنگ دکمه نامعتبر است', 'Invalid button style');
            $c['btn'][$k] = ['l' => $l !== '' ? $l : botDefaults()['btn'][$k]['l'], 'e' => (string)$e, 's' => $s];
        }
    }
    if (isset($in['txt']) && is_array($in['txt'])) {
        foreach ($c['txt'] as $k => $_) {
            if (!isset($in['txt'][$k])) continue;
            $t = botCleanTxt($in['txt'][$k], 800);
            $c['txt'][$k] = $t !== '' ? $t : botDefaults()['txt'][$k];
        }
    }
    return $c;
}
/** لیست کانال‌های عضویت اجباری را اعتبارسنجی و یکدست می‌کند (آرایه یا متن چندخطی). کانال عددی (-100…) لینک دعوت https://t.me/… لازم دارد. */
function botFjClean($v): array {
    $lines = is_array($v) ? $v : preg_split('/[\r\n,;]+/u', (string)$v);
    $out = [];
    foreach ($lines as $l) {
        $l = trim((string)preg_replace('/\s+/u', ' ', (string)$l));
        if ($l === '' || $l === '-' || $l === '0') continue;
        if (!preg_match('#^(@[A-Za-z][A-Za-z0-9_]{4,31}|-100\d{5,15})(?: (https://t\.me/[A-Za-z0-9_+/\-]{3,64}))?$#', $l, $m)) fail('کانال نامعتبر است: ' . mb_substr($l, 0, 40), 'Invalid channel');
        if ($m[1][0] === '-' && empty($m[2])) fail('برای کانال عددی، لینک دعوت (https://t.me/...) را بعد از آیدی بنویسید', 'A numeric channel needs an invite link');
        $key = strtolower($m[1]);
        if (!isset($out[$key])) $out[$key] = $l;
    }
    if (count($out) > 5) fail('حداکثر ۵ کانال مجاز است', 'At most 5 channels');
    return array_values($out);
}
/** [['chat' => '@x' | '-100…', 'link' => 'https://t.me/…', 'label' => '@x'], ...] */
function botFjParse(array $cfg): array {
    $o = [];
    foreach ((array)($cfg['fj'] ?? []) as $l) {
        $p = explode(' ', trim((string)$l));
        $chat = (string)($p[0] ?? '');
        if ($chat === '') continue;
        $link = (string)($p[1] ?? '');
        if ($link === '' && $chat[0] === '@') $link = 'https://t.me/' . substr($chat, 1);
        $o[] = ['chat' => $chat, 'link' => $link, 'label' => $chat[0] === '@' ? $chat : 'کانال ' . (count($o) + 1)];
    }
    return $o;
}
function botCfgPatch(PDO $db, array $agent, array $kv): array {
    $c = botCfgClean($db, $agent, $kv);
    ownerSet($db, (int)$agent['id'], 'bot_cfg', json_encode($c, JSON_UNESCAPED_UNICODE));
    return $c;
}

// ------------------------------------------------------------------ API تلگرام
/** آدرس API تلگرام؛ اگر سرور به تلگرام دسترسی مستقیم ندارد، ثابت TG_API_BASE در config.php یا کلید tg_api_base در settings را روی یک رله‌ی https بگذارید */
function tgBase(PDO $db): string {
    $b = defined('TG_API_BASE') ? (string)TG_API_BASE : (string)setting($db, 'tg_api_base');
    $b = rtrim(trim($b), '/');
    return preg_match('#^https://[A-Za-z0-9.\-]+(:\d+)?(/[A-Za-z0-9_.~%\-/]*)?$#', $b) ? $b : 'https://api.telegram.org';
}
function tgCall(PDO $db, string $token, string $method, array $params = [], array $files = []): array {
    if (defined('BOT_TEST_MODE')) { // فقط tests/runner.php این ثابت را تعریف می‌کند: هیچ درخواست HTTP واقعی نمی‌رود
        $GLOBALS['BOT_TG_LOG'][] = ['token' => $token, 'method' => $method, 'params' => $params, 'files' => array_keys($files)];
        $hook = $GLOBALS['BOT_TG_REPLY'][$method] ?? null; // فقط تست‌ها: پاسخ ساختگیِ هر متد، callable(token, params): array
        if (is_callable($hook)) return $hook($token, $params);
        return ['ok' => true, 'result' => []];
    }
    $post = [];
    foreach ($params as $k => $v) $post[$k] = is_array($v) ? json_encode($v, JSON_UNESCAPED_UNICODE) : $v;
    foreach ($files as $k => $path) $post[$k] = new CURLFile($path);
    $ch = curl_init(tgBase($db) . '/bot' . $token . '/' . $method);
    curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_POSTFIELDS => $post, CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 8, CURLOPT_TIMEOUT => 25, CURLOPT_PROTOCOLS => CURLPROTO_HTTPS]);
    $raw = curl_exec($ch); $err = curl_error($ch); curl_close($ch);
    $d = is_string($raw) ? json_decode($raw, true) : null;
    if (!is_array($d)) return ['ok' => false, 'description' => $err !== '' ? $err : 'no response'];
    return $d;
}
function tgDownload(PDO $db, string $token, string $filePath, string $dest): bool {
    if (defined('BOT_TEST_MODE')) return false;
    if (!preg_match('#^[A-Za-z0-9_\-/.]{1,200}$#', $filePath)) return false;
    $fp = @fopen($dest, 'wb');
    if (!$fp) return false;
    $ch = curl_init(tgBase($db) . '/file/bot' . $token . '/' . $filePath);
    curl_setopt_array($ch, [CURLOPT_FILE => $fp, CURLOPT_CONNECTTIMEOUT => 8, CURLOPT_TIMEOUT => 40, CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
        CURLOPT_MAXFILESIZE => RECEIPT_MAX_BYTES, CURLOPT_FAILONERROR => true]);
    $ok = curl_exec($ch) !== false; curl_close($ch); fclose($fp);
    if (!$ok) @unlink($dest);
    return $ok;
}

// ------------------------------------------------------------------ ردیف ربات + اتصال
function botRow(PDO $db, int $agId): ?array {
    $s = $db->prepare('SELECT * FROM tg_bots WHERE agent_id=?'); $s->execute([$agId]);
    $r = $s->fetch(PDO::FETCH_ASSOC);
    return $r ?: null;
}
function botTok(array $b): string { return pnDec((string)$b['token_enc']); }
function botView(array $b): array {
    $t = botTok($b);
    return ['username' => (string)$b['bot_username'], 'enabled' => (int)$b['enabled'], 'admin_chat_id' => (string)$b['admin_chat_id'],
            'token_hint' => $t !== '' ? '••••' . substr($t, -4) : '', 'updated_at' => (int)$b['updated_at']];
}
/** توکن (اختیاری برای تغییر)، chat id ادمین ربات و روشن/خاموش؛ نماینده هر زمان می‌تواند عوض کند */
function botSaveConn(PDO $db, array $agent, string $token, string $adminChat, int $enabled): void {
    $agId = (int)$agent['id']; $row = botRow($db, $agId); $now = time();
    $token = trim($token);
    if ($adminChat !== '' && !preg_match('/^-?\d{4,20}$/', $adminChat)) fail('chat id ادمین ربات باید عدد باشد', 'Admin chat id must be numeric');
    if ($token === '' && !$row) fail('توکن ربات را وارد کنید', 'Bot token is required');
    if ($token !== '' && !preg_match('/^\d{6,12}:[A-Za-z0-9_\-]{30,50}$/', $token)) fail('فرمت توکن ربات نامعتبر است', 'Invalid bot token format');
    $oldToken = $row ? botTok($row) : '';
    $tokenNew = $token !== '' && $token !== $oldToken;
    $newToken = $token !== '' ? $token : $oldToken;
    $username = (string)($row['bot_username'] ?? ''); $tgId = (int)($row['tg_bot_id'] ?? 0);
    if ($tokenNew) {
        $me = tgCall($db, $newToken, 'getMe');
        if (empty($me['ok'])) fail('توکن از طرف تلگرام تأیید نشد یا سرور به تلگرام دسترسی ندارد: ' . mb_substr((string)($me['description'] ?? ''), 0, 120),
            'Telegram rejected the token or the server cannot reach Telegram', 502);
        $tgId = (int)($me['result']['id'] ?? 0); $username = (string)($me['result']['username'] ?? '');
        $dup = $db->prepare('SELECT 1 FROM tg_bots WHERE tg_bot_id=? AND agent_id<>?'); $dup->execute([$tgId, $agId]);
        if ($tgId > 0 && $dup->fetchColumn()) fail('این ربات قبلاً برای نماینده‌ی دیگری ثبت شده است', 'This bot is already registered for another agent', 409);
    }
    $pub = (!$row || $tokenNew) ? bin2hex(random_bytes(12)) : (string)$row['pub_key'];
    $hdr = (!$row || $tokenNew) ? bin2hex(random_bytes(24)) : (string)$row['hdr_secret'];
    if ($enabled === 1) {
        $base = payPublicBase($db);
        if (strpos($base, 'https://') !== 0) fail('برای وب‌هوک تلگرام، «آدرس عمومی بکند» باید https باشد (تنظیمات مدیر)', 'The public backend URL must be https for the Telegram webhook');
        $r = tgCall($db, $newToken, 'setWebhook', ['url' => $base . '/bot.php?k=' . $pub, 'secret_token' => $hdr,
            'allowed_updates' => ['message', 'callback_query'], 'max_connections' => 10]);
        if (empty($r['ok'])) fail('ثبت وب‌هوک ناموفق: ' . mb_substr((string)($r['description'] ?? ''), 0, 120), 'Webhook registration failed', 502);
    } elseif ($row) {
        tgCall($db, $newToken, 'deleteWebhook');
    }
    if ($row) {
        $db->prepare('UPDATE tg_bots SET token_enc=?, bot_username=?, tg_bot_id=?, admin_chat_id=?, enabled=?, pub_key=?, hdr_secret=?, last_update=?, updated_at=? WHERE agent_id=?')
           ->execute([pnEnc($newToken), $username, $tgId, $adminChat, $enabled, $pub, $hdr, $tokenNew ? 0 : (int)$row['last_update'], $now, $agId]);
        if ($tokenNew && $oldToken !== '') tgCall($db, $oldToken, 'deleteWebhook'); // وب‌هوک ربات قبلی بعد از موفقیت جمع می‌شود
    } else {
        $db->prepare('INSERT INTO tg_bots (agent_id, token_enc, bot_username, tg_bot_id, admin_chat_id, enabled, pub_key, hdr_secret, last_update, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,0,?,?)')
           ->execute([$agId, pnEnc($newToken), $username, $tgId, $adminChat, $enabled, $pub, $hdr, $now, $now]);
    }
    $fresh = botRow($db, $agId);
    if (!$fresh) return;
    // مالک جدید دیگر «ادمین فرعی» نیست؛ مالک همه‌ی مجوزها را دارد و ردیف جدا نمی‌خواهد
    if (preg_match('/^\d{4,20}$/', $adminChat)) $db->prepare('DELETE FROM tg_bot_admins WHERE bot_id=? AND chat_id=?')->execute([(int)$fresh['id'], (int)$adminChat]);
    if ($enabled !== 1) return;
    try {
        $oldAdm = (string)($row['admin_chat_id'] ?? '');
        if ($row && !$tokenNew && $oldAdm !== '' && $oldAdm !== $adminChat && preg_match('/^\d{4,20}$/', $oldAdm) && !botIsStaff($db, $fresh, (int)$oldAdm))
            botTg($db, $fresh, 'deleteMyCommands', ['scope' => ['type' => 'chat', 'chat_id' => (int)$oldAdm]]); // مالک قبلی منوی /admin را از دست می‌دهد
        botCommandsRegister($db, $fresh);
    } catch (Throwable $e) { error_log('botSaveConn commands: ' . get_class($e)); } // خطای کامندها ذخیره‌ی اتصال را خراب نمی‌کند
}
/** حذف نماینده: وب‌هوک جمع و داده‌های ربات او پاک می‌شود (حساب‌های ساخته‌شده دست نمی‌خورند) */
function botPurgeAgent(PDO $db, int $agId): void {
    if (function_exists('botEmoPurge')) botEmoPurge($db, $agId);
    $b = botRow($db, $agId);
    if (!$b) return;
    try { tgCall($db, botTok($b), 'deleteWebhook'); } catch (Throwable $e) {}
    $fs = $db->prepare("SELECT receipt_file FROM tg_orders WHERE agent_id=? AND receipt_file<>''"); $fs->execute([$agId]);
    foreach ($fs->fetchAll(PDO::FETCH_COLUMN) as $f) { $p = RECEIPT_DIR . '/' . basename((string)$f); if (is_file($p)) @unlink($p); }
    $bid = (int)$b['id'];
    foreach (['tg_wallet_tx', 'tg_accts', 'tg_orders', 'tg_users', 'tg_bot_admins', 'tg_audit', 'tg_counters', 'tg_coupon_uses', 'tg_coupons'] as $t) $db->prepare("DELETE FROM $t WHERE bot_id=?")->execute([$bid]);
    $db->prepare('DELETE FROM tg_bots WHERE id=?')->execute([$bid]);
    $db->prepare("DELETE FROM plans WHERE owner_id=? AND kind='bot'")->execute([$agId]);
}

// ------------------------------------------------------------------ کمکی‌ها (متن، دکمه، ارسال)
function bh(string $s): string { return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
/** {e:شناسه} یا {e:شناسه:🙂} در متن → ایموجی سفارشی تلگرام (ورودی باید قبلاً escape شده باشد) */
function botEmo(string $escaped): string {
    return (string)preg_replace_callback('/\{e:(\d{5,25})(?::([^{}]{1,4}))?\}/u',
        fn($m) => '<tg-emoji emoji-id="' . $m[1] . '">' . (($m[2] ?? '') !== '' ? $m[2] : '⭐') . '</tg-emoji>', $escaped);
}
function botTx(array $cfg, string $k): string { return botEmo(bh((string)$cfg['txt'][$k])); }
function botGb(int $bytes): string { return $bytes > 0 ? rtrim(rtrim(number_format($bytes / 1073741824, 2, '.', ''), '0'), '.') . ' گیگ' : 'نامحدود'; }
function botMoney(int $n): string { return number_format($n, 0, '.', ',') . ' تومان'; }
function botDlUrl(PDO $db, array $cfg): string { return $cfg['dl_url'] !== '' ? (string)$cfg['dl_url'] : payPublicBase($db) . '/dl.php'; }
/** دکمه با رنگ و ایموجی سفارشی (style / icon_custom_emoji_id در Bot API جدید) */
function botB(array $cfg, string $key, string $label, array $act): array {
    $b = $cfg['btn'][$key] ?? ['l' => '', 'e' => '', 's' => ''];
    $btn = ['text' => $label] + $act;
    if ($b['s'] !== '') $btn['style'] = $b['s'];
    if ($b['e'] !== '') $btn['icon_custom_emoji_id'] = $b['e'];
    return $btn;
}
function botBL(array $cfg, string $key, array $act): array { return botB($cfg, $key, (string)$cfg['btn'][$key]['l'], $act); }
/** دکمه‌ی ساده‌ی پنل مدیریت داخل ربات */
function botAB(string $label, string $cb, string $style = ''): array {
    $b = ['text' => $label, 'callback_data' => $cb];
    if ($style !== '') $b['style'] = $style;
    return $b;
}
function botKbPlain(array $kb): array {
    foreach ($kb as $i => $row) foreach ($row as $j => $b) { unset($b['style'], $b['icon_custom_emoji_id']); $kb[$i][$j] = $b; }
    return $kb;
}
/** اجرای امن: out()/fail() هسته به‌جای خروج، استثنا می‌اندازند؛ خروجی [ok, v | err] */
function botTry(callable $fn): array {
    $GLOBALS['__out_throw'] = true;
    try { return ['ok' => true, 'v' => $fn()]; }
    catch (OutException $e) { error_log('botTry: ' . (string)($e->data['error'] ?? 'error')); return ['ok' => false, 'err' => (string)($e->data['error'] ?? 'error'), 'code' => $e->status]; }
    catch (Throwable $e) { error_log('bot: ' . $e->getMessage()); return ['ok' => false, 'err' => 'internal error', 'code' => 500]; }
    finally { $GLOBALS['__out_throw'] = false; }
}
function botTg(PDO $db, array $bot, string $method, array $p = [], array $f = []): array { return tgCall($db, botTok($bot), $method, $p, $f); }
/** ارسال پیام؛ اگر تلگرام ایموجی سفارشی/رنگ دکمه را نپذیرفت، نسخه‌ی ساده و در نهایت بدون دکمه ارسال می‌شود */
function botSay(PDO $db, array $bot, $chat, string $text, ?array $kb = null): void {
    // پاسخ به زدن دکمه: همان پیامِ دکمه ویرایش می‌شود (فقط اولین پیامِ پاسخ)؛ اگر ویرایش ممکن نبود (مثلاً پیام عکس است) پیام جدید می‌رود
    $ctx = $GLOBALS['botEditCtx'] ?? null;
    if (is_array($ctx) && (string)$ctx['chat'] === (string)$chat && (int)$ctx['mid'] > 0) {
        $GLOBALS['botEditCtx'] = null;
        $e = ['chat_id' => $chat, 'message_id' => (int)$ctx['mid'], 'text' => $text, 'parse_mode' => 'HTML', 'disable_web_page_preview' => 'true',
              'reply_markup' => ['inline_keyboard' => $kb ?: []]];
        $r = botTg($db, $bot, 'editMessageText', $e);
        if (!empty($r['ok']) || stripos((string)($r['description'] ?? ''), 'not modified') !== false) return;
        $e['text'] = (string)preg_replace('#<tg-emoji[^>]*>(.*?)</tg-emoji>#us', '$1', $text);
        if ($kb) $e['reply_markup'] = ['inline_keyboard' => botKbPlain($kb)];
        $r = botTg($db, $bot, 'editMessageText', $e);
        if (!empty($r['ok']) || stripos((string)($r['description'] ?? ''), 'not modified') !== false) return;
    }
    $p = ['chat_id' => $chat, 'text' => $text, 'parse_mode' => 'HTML', 'disable_web_page_preview' => 'true'];
    if ($kb) $p['reply_markup'] = ['inline_keyboard' => $kb];
    $r = botTg($db, $bot, 'sendMessage', $p);
    if (!empty($r['ok'])) return;
    $p['text'] = (string)preg_replace('#<tg-emoji[^>]*>(.*?)</tg-emoji>#us', '$1', $text);
    if ($kb) $p['reply_markup'] = ['inline_keyboard' => botKbPlain($kb)];
    $r = botTg($db, $bot, 'sendMessage', $p);
    if (!empty($r['ok']) || !$kb) return;
    unset($p['reply_markup']);
    botTg($db, $bot, 'sendMessage', $p);
}
function botNotifyAdmin(PDO $db, array $bot, string $text, ?array $kb = null): void {
    if ((string)$bot['admin_chat_id'] === '') return;
    botSay($db, $bot, (string)$bot['admin_chat_id'], $text, $kb);
}
// ------------------------------------------------------------------ گزارش رویدادها (مرحله ۶)
/** نوع رویداد => [عنوان، مجوزِ گیرندگان وقتی گروه تنظیم نیست] */
function botEventTypes(): array {
    return ['order_new' => ['🆕 سفارش جدید', 'orders'], 'sale' => ['🛒 فروش موفق', 'orders'], 'topup' => ['💳 شارژ کیف پول', 'orders'],
            'error' => ['⚠️ خطا', 'settings'], 'ticket' => ['🎫 تیکت', 'tickets']];
}
/** شناسه‌ی گروه گزارش: خالی یا عددِ منفی (مثل -1001234567890) */
function botEventChatClean($v): string {
    $s = trim(payDigits((string)$v));
    if ($s === '' || $s === '-' || $s === '0') return '';
    if (!preg_match('/^-\d{5,20}$/', $s)) fail('شناسه‌ی گروه باید عددِ منفی باشد (مثل -1001234567890)', 'Invalid events chat id');
    return $s;
}
/** نگاشت نوع رویداد → شماره‌ی تاپیک؛ صفر/خالی = بدون تاپیک */
function botEventTopicsClean($v): array {
    if (!is_array($v)) return [];
    $types = botEventTypes(); $o = [];
    foreach ($v as $k => $n) {
        if (!isset($types[(string)$k])) fail('نوع رویداد نامعتبر است', 'Unknown event type');
        if ($n === '' || $n === null || (is_numeric($n) && (int)$n === 0)) continue;
        if (!is_numeric($n) || (int)$n < 1 || (int)$n > 2147483647) fail('شماره‌ی تاپیک نامعتبر است', 'Invalid topic id');
        $o[(string)$k] = (int)$n;
    }
    return $o;
}
/** مالک (یا گروه ادمین) + ادمین‌های دارای مجوز؛ فقط همین ربات */
function botEventRecipients(PDO $db, array $bot, string $perm): array {
    $r = []; $a = (string)$bot['admin_chat_id'];
    if ($a !== '') $r[$a] = $a;
    $s = $db->prepare('SELECT chat_id, perms FROM tg_bot_admins WHERE bot_id=? ORDER BY id'); $s->execute([(int)$bot['id']]);
    foreach ($s->fetchAll(PDO::FETCH_ASSOC) as $x) if (in_array($perm, botPermsParse((string)$x['perms']), true)) $r[(string)$x['chat_id']] = (string)$x['chat_id'];
    return array_values($r);
}
/** ارسال یک رویداد به یک مقصد (عکس اختیاری، تاپیک اختیاری)؛ اگر ایموجی/دکمه رد شد نسخه‌ی ساده می‌فرستد */
function botEventSend(PDO $db, array $bot, $to, ?int $topic, string $text, ?array $kb = null, ?string $photo = null): bool {
    $GLOBALS['botEvLastErr'] = '';
    $th = $topic !== null && $topic > 0 ? ['message_thread_id' => $topic] : [];
    if ($photo !== null && is_file($photo)) {
        $q = ['chat_id' => $to, 'caption' => $text, 'parse_mode' => 'HTML'] + $th;
        if ($kb) $q['reply_markup'] = ['inline_keyboard' => $kb];
        $r = botTg($db, $bot, 'sendPhoto', $q, ['photo' => $photo]);
        if (!empty($r['ok'])) return true;
    }
    $p = ['chat_id' => $to, 'text' => $text, 'parse_mode' => 'HTML', 'disable_web_page_preview' => 'true'] + $th;
    if ($kb) $p['reply_markup'] = ['inline_keyboard' => $kb];
    $r = botTg($db, $bot, 'sendMessage', $p);
    if (!empty($r['ok'])) return true;
    $p['text'] = (string)preg_replace('#<tg-emoji[^>]*>(.*?)</tg-emoji>#us', '$1', $text);
    if ($kb) $p['reply_markup'] = ['inline_keyboard' => botKbPlain($kb)];
    $r = botTg($db, $bot, 'sendMessage', $p);
    if (empty($r['ok'])) $GLOBALS['botEvLastErr'] = (string)($r['description'] ?? '');
    return !empty($r['ok']);
}
/** ساخت تاپیکِ یک نوع رویداد؛ شماره‌ی تاپیک یا ۰ */
function botEventMakeTopic(PDO $db, array $bot, string $chatId, string $type): int {
    $t = botEventTypes()[$type][0] ?? null;
    if ($t === null) return 0;
    $r = botTg($db, $bot, 'createForumTopic', ['chat_id' => $chatId, 'name' => $t]);
    $GLOBALS['botEvMakeErr'] = (string)($r['description'] ?? '');
    return !empty($r['ok']) ? (int)($r['result']['message_thread_id'] ?? 0) : 0;
}
/** برای هر نوع رویدادِ بدون تاپیک، تاپیک می‌سازد (گروه باید فروم باشد و ربات ادمین با مجوز مدیریت تاپیک). $force=true همه را از نو می‌سازد. */
function botEventsAutoTopics(PDO $db, array $bot, array $agent, bool $force = false): array {
    $cfg = botCfg($db, (int)$agent['id']); $cid = (string)$cfg['events_chat_id'];
    if ($cid === '') return ['ok' => false, 'msg' => 'ابتدا گروه گزارش را تنظیم کنید.'];
    $r = botTg($db, $bot, 'getChat', ['chat_id' => $cid]);
    $res = is_array($r['result'] ?? null) ? $r['result'] : [];
    if (empty($r['ok'])) return ['ok' => false, 'msg' => 'تلگرام این گروه را برای ربات پیدا نکرد؛ ابتدا ربات را به گروه اضافه کنید.'];
    if (empty($res['is_forum'])) return ['ok' => false, 'msg' => 'در تنظیمات گروه گزینه‌ی «Topics» را روشن کنید و دوباره بزنید.'];
    $tp = $cfg['events_topics']; $made = 0; $err = '';
    foreach (array_keys(botEventTypes()) as $k) {
        if (!$force && !empty($tp[$k])) continue;
        $id = botEventMakeTopic($db, $bot, $cid, $k);
        if ($id <= 0) { $err = (string)($GLOBALS['botEvMakeErr'] ?? ''); break; }
        $tp[$k] = $id; $made++;
    }
    if ($made > 0) botCfgPatch($db, $agent, ['events_topics' => $tp]);
    if ($err !== '') return ['ok' => false, 'msg' => ($made > 0 ? $made . ' تاپیک ساخته شد، ولی ' : '') . 'ساخت تاپیک ممکن نشد. ربات را ادمین گروه کنید و مجوز «Manage Topics» بدهید. (' . $err . ')'];
    return ['ok' => true, 'msg' => $made > 0 ? $made . ' تاپیک به‌صورت خودکار ساخته شد.' : 'همه‌ی تاپیک‌ها از قبل ساخته شده‌اند.'];
}
/**
 * گزارش یک رویداد برای همین ربات: $type یکی از order_new، sale، topup، error، ticket. $text باید از قبل escape شده باشد.
 * گروه گزارش تنظیم است → همان گروه (و تاپیکِ آن نوع)؛ ارسال به گروه شکست بخورد یا گروه نباشد → ادمین‌های دارای مجوزِ مربوط همین ربات.
 */
function botEvent(PDO $db, array $bot, string $type, string $text, ?array $kb = null, ?string $photo = null): void {
    $types = botEventTypes();
    if (!isset($types[$type]) || trim($text) === '') return;
    try {
        $cfg = botCfg($db, (int)$bot['agent_id']);
        $grp = (string)$cfg['events_chat_id'];
        $tid = (int)($cfg['events_topics'][$type] ?? 0);
        if ($grp !== '' && botEventSend($db, $bot, $grp, $tid, $text, $kb, $photo)) return;
        // تاپیک پاک شده؟ همان‌جا دوباره می‌سازیم و ذخیره می‌کنیم
        if ($grp !== '' && $tid > 0 && stripos((string)($GLOBALS['botEvLastErr'] ?? ''), 'thread') !== false) {
            $ag = botAgentRow($db, (int)$bot['agent_id']);
            $nid = $ag ? botEventMakeTopic($db, $bot, $grp, $type) : 0;
            if ($nid > 0) {
                $tp = $cfg['events_topics']; $tp[$type] = $nid; botCfgPatch($db, $ag, ['events_topics' => $tp]);
                if (botEventSend($db, $bot, $grp, $nid, $text, $kb, $photo)) return;
            }
        }
        foreach (botEventRecipients($db, $bot, $types[$type][1]) as $to) botEventSend($db, $bot, $to, null, $text, $kb, $photo);
    } catch (Throwable $e) { error_log('botEvent: ' . get_class($e) . ' @' . basename($e->getFile()) . ':' . $e->getLine()); }
}
/** ذخیره‌ی گروه/تاپیک‌ها بعد از اعتبارسنجی با getChat. $chatId='' یعنی حذف گروه. @return array{ok:bool,msg:string} */
function botEventsApply(PDO $db, array $bot, array $agent, string $chatId, array $topics): array {
    $cl = botTry(fn() => [botEventChatClean($chatId), botEventTopicsClean($topics)]);
    if (!$cl['ok']) return ['ok' => false, 'msg' => (string)$cl['err']];
    [$cid, $tp] = $cl['v'];
    if ($cid === '') { botCfgPatch($db, $agent, ['events_chat_id' => '', 'events_topics' => []]); return ['ok' => true, 'msg' => 'گروه گزارش حذف شد.']; }
    $r = botTg($db, $bot, 'getChat', ['chat_id' => $cid]);
    $res = is_array($r['result'] ?? null) ? $r['result'] : [];
    if (empty($r['ok'])) return ['ok' => false, 'msg' => 'تلگرام این گروه را برای ربات پیدا نکرد؛ ابتدا ربات را به گروه اضافه کنید.'];
    if (!in_array((string)($res['type'] ?? ''), ['group', 'supergroup'], true) || (string)($res['id'] ?? '') !== $cid) return ['ok' => false, 'msg' => 'این شناسه گروه معتبری نیست.'];
    if ($tp && empty($res['is_forum'])) return ['ok' => false, 'msg' => 'این گروه تاپیک (فروم) ندارد؛ شماره‌ی تاپیک را خالی بگذارید.'];
    $p = botTry(fn() => botCfgPatch($db, $agent, ['events_chat_id' => $cid, 'events_topics' => $tp]));
    return $p['ok'] ? ['ok' => true, 'msg' => 'ذخیره شد.'] : ['ok' => false, 'msg' => (string)$p['err']];
}
function botAdminEvents(PDO $db, array $bot, array $agent, int $chat): void {
    $cfg = botCfg($db, (int)$agent['id']); $types = botEventTypes(); $g = (string)$cfg['events_chat_id'];
    $txt = "📡 <b>گزارش رویدادها</b>\nگروه: " . ($g !== '' ? '<code>' . bh($g) . '</code>' : 'تنظیم نشده (رویدادها به ادمین‌های دارای مجوز در پیوی می‌رود)')
         . "\nربات باید عضو گروه و مجاز به ارسال پیام باشد. برای تاپیک‌ها گروه باید «فروم» باشد.";
    $kb = [[botAB('✏️ تنظیم گروه', 'a:evg', 'primary')]];
    if ($g !== '') {
        $kb[] = [botAB('🧩 ساخت خودکار تاپیک‌ها', 'a:evk', 'success'), botAB('🗑 حذف گروه', 'a:evc', 'danger')];
        foreach (array_keys($types) as $i => $k) $kb[] = [botAB($types[$k][0] . ': ' . (isset($cfg['events_topics'][$k]) ? 'تاپیک ' . (int)$cfg['events_topics'][$k] : 'بدون تاپیک'), 'a:evt:' . $i)];
    }
    $kb[] = [botAB('بازگشت', 'a:home')];
    botSay($db, $bot, $chat, $txt, $kb);
}
// ------------------------------------------------------------------ ادمین‌ها و مجوزها
/** مجوزهای ممکن (کلید => عنوان)؛ ترتیب برای دکمه‌های روشن/خاموش ثابت است */
function botPermList(): array {
    return ['orders' => 'سفارش‌ها', 'users' => 'کاربران', 'wallet' => 'کیف پول', 'broadcast' => 'پیام همگانی', 'tickets' => 'تیکت‌ها', 'settings' => 'تنظیمات', 'stats' => 'آمار', 'admins' => 'ادمین‌ها', 'agents' => 'نمایندگان'];
}
function botPermsParse(string $csv): array {
    $ok = botPermList(); $o = [];
    foreach (explode(',', $csv) as $p) { $p = trim($p); if ($p !== '' && isset($ok[$p])) $o[$p] = $p; }
    return array_values($o);
}
/** مالک ربات = chat id ثبت‌شده در تنظیمات اتصال؛ همه‌ی مجوزها را دارد و حذف‌شدنی نیست */
function botIsOwner(array $bot, int $chat): bool { $a = (string)$bot['admin_chat_id']; return $chat !== 0 && $a !== '' && $a === (string)$chat; }
/** مجوزهای این چت در همین ربات؛ آرایه‌ی خالی = ادمین نیست */
function botAdminPerms(PDO $db, array $bot, int $chat): array {
    if ($chat === 0) return [];
    $all = botIsOwner($bot, $chat);
    if (!$all) {
        $s = $db->prepare('SELECT perms FROM tg_bot_admins WHERE bot_id=? AND chat_id=?'); $s->execute([(int)$bot['id'], $chat]);
        $p = $s->fetchColumn();
        if ($p === false) return [];
        $list = botPermsParse((string)$p);
    } else $list = array_keys(botPermList());
    // مجوز «نمایندگان» فقط در ربات مدیر اصلی (حساب role=admin) معتبر است
    if (in_array('agents', $list, true) && !botPermAgentsOk($db, $bot)) $list = array_values(array_diff($list, ['agents']));
    return $list;
}
function botPermAgentsOk(PDO $db, array $bot): bool {
    $s = $db->prepare("SELECT role FROM accounts WHERE id=?"); $s->execute([(int)$bot['agent_id']]);
    return (string)$s->fetchColumn() === 'admin';
}
function botCan(PDO $db, array $bot, int $chat, string $perm): bool { return in_array($perm, botAdminPerms($db, $bot, $chat), true); }
/** مالک یا ادمین فرعی (حتی بدون مجوز) */
function botIsStaff(PDO $db, array $bot, int $chat): bool {
    if ($chat === 0) return false;
    if (botIsOwner($bot, $chat)) return true;
    $s = $db->prepare('SELECT 1 FROM tg_bot_admins WHERE bot_id=? AND chat_id=?'); $s->execute([(int)$bot['id'], $chat]);
    return (bool)$s->fetchColumn();
}
/** chat idِ خصوصیِ مالک و ادمین‌های همین ربات (برای منوی /admin) */
function botStaffChats(PDO $db, array $bot): array {
    $o = [];
    $a = (string)$bot['admin_chat_id'];
    if (preg_match('/^\d{4,20}$/', $a)) $o[(int)$a] = (int)$a;
    $s = $db->prepare('SELECT chat_id FROM tg_bot_admins WHERE bot_id=? ORDER BY id'); $s->execute([(int)$bot['id']]);
    foreach ($s->fetchAll(PDO::FETCH_COLUMN) as $c) if ((int)$c > 0) $o[(int)$c] = (int)$c;
    return array_values($o);
}
/** گیرندگان اعلان سفارش: مالک (یا گروه ادمین) + ادمین‌های دارای مجوز orders؛ فقط همین ربات */
function botOrderRecipients(PDO $db, array $bot): array {
    $r = []; $a = (string)$bot['admin_chat_id'];
    if ($a !== '') $r[$a] = $a;
    $s = $db->prepare('SELECT chat_id, perms FROM tg_bot_admins WHERE bot_id=? ORDER BY id'); $s->execute([(int)$bot['id']]);
    foreach ($s->fetchAll(PDO::FETCH_ASSOC) as $x) if (in_array('orders', botPermsParse((string)$x['perms']), true)) $r[(string)$x['chat_id']] = (string)$x['chat_id'];
    return array_values($r);
}

// ------------------------------------------------------------------ آدیت
/** ثبت اقدام ادمین؛ $meta آرایه یا متن کوتاه است و هرگز نباید توکن/رمز داشته باشد. */
function botAudit(PDO $db, array $bot, int $actorChat, string $action, string $target = '', $meta = ''): void {
    $m = is_array($meta) ? json_encode($meta, JSON_UNESCAPED_UNICODE) : (string)$meta;
    try {
        $db->prepare('INSERT INTO tg_audit (bot_id, actor_chat, action, target, meta, created_at) VALUES (?,?,?,?,?,?)')
           ->execute([(int)$bot['id'], $actorChat, mb_substr($action, 0, 40), mb_substr($target, 0, 80), mb_substr((string)$m, 0, 400), time()]);
    } catch (Throwable $e) { error_log('botAudit: ' . get_class($e)); }
}
function botAuditLabel(string $a): string {
    return ['order_approve' => 'تأیید سفارش', 'order_reject' => 'رد سفارش', 'topup_approve' => 'تأیید شارژ کیف پول', 'topup_gateway' => 'شارژ کیف پول (درگاه)', 'wallet_adjust' => 'تغییر موجودی', 'ban' => 'مسدود کردن', 'unban' => 'آزادسازی',
            'setting' => 'تغییر تنظیمات', 'admin_add' => 'افزودن ادمین', 'admin_remove' => 'حذف ادمین', 'admin_perms' => 'تغییر مجوز ادمین',
            'coupon_add' => 'افزودن کد تخفیف', 'coupon_toggle' => 'روشن/خاموش کد تخفیف', 'coupon_delete' => 'حذف کد تخفیف',
            'ticket_reply' => 'پاسخ تیکت', 'ticket_close' => 'بستن تیکت', 'canned_add' => 'افزودن پاسخ آماده', 'canned_delete' => 'حذف پاسخ آماده',
            'backup_manual' => 'بکاپ دستی', 'tutorial_add' => 'افزودن آموزش/سوال', 'tutorial_edit' => 'ویرایش آموزش/سوال', 'tutorial_toggle' => 'روشن/خاموش آموزش/سوال',
            'tutorial_delete' => 'حذف آموزش/سوال', 'tutorial_sort' => 'جابجایی ترتیب آموزش/سوال',
            'ag_create' => 'ساخت نماینده', 'ag_set' => 'تغییر تنظیم نماینده', 'ag_extend' => 'تمدید نماینده', 'ag_pass' => 'تغییر رمز نماینده', 'ag_svcreate' => 'اجازه‌ی ساخت سرویس نماینده',
            'ag_grant' => 'واگذاری سرویس به نماینده', 'ag_panels' => 'پنل‌های مجاز نماینده', 'ag_svc' => 'سرویس‌های پنلی نماینده', 'ag_status' => 'فعال/غیرفعال‌کردن نماینده',
            'ag_2fa' => 'ریست دو مرحله‌ای نماینده', 'ag_logout' => 'خروج نشست‌های نماینده', 'ag_delete' => 'حذف نماینده', 'emoji_add' => 'افزودن ایموجی', 'emoji_delete' => 'حذف ایموجی', 'emoji_clear' => 'پاک‌کردن ایموجی‌ها', 'emoji_cap' => 'تغییر سقف ایموجی'][$a] ?? $a;
}
/** ۲۰ رکورد آخرِ همین ربات */
function botAuditView(PDO $db, array $bot, int $chat): void {
    $s = $db->prepare('SELECT * FROM tg_audit WHERE bot_id=? ORDER BY id DESC LIMIT 20'); $s->execute([(int)$bot['id']]);
    $rows = $s->fetchAll(PDO::FETCH_ASSOC);
    $txt = "📜 <b>گزارش فعالیت ادمین‌ها</b> (۲۰ مورد آخر)\n";
    if (!$rows) $txt .= "\nهنوز موردی ثبت نشده است.";
    foreach ($rows as $r) {
        $meta = (string)$r['meta'];
        $txt .= "\n" . date('m/d H:i', (int)$r['created_at']) . ' — ' . bh(botAuditLabel((string)$r['action'])) . ' — ' . ((int)$r['actor_chat'] > 0 ? '<code>' . (int)$r['actor_chat'] . '</code>' : 'پورتال')
              . ((string)$r['target'] !== '' ? ' — ' . bh((string)$r['target']) : '') . ($meta !== '' ? ' — ' . bh(mb_substr($meta, 0, 60)) : '');
    }
    botSay($db, $bot, $chat, mb_substr($txt, 0, 3900), [[botAB('بازگشت', 'a:home')]]);
}

// ------------------------------------------------------------------ مرحله ۷: تیکت‌ها، پاسخ‌های آماده، آموزش و سوالات متداول
function botTicketCleanBody(string $text, int $max = 3500): string {
    return mb_substr(trim(botCleanTxt($text, $max)), 0, $max);
}
function botTicketMaxOpen(array $cfg): int {
    $n = (int)($cfg['tk_max_open'] ?? 3);
    return $n >= 1 && $n <= 50 ? $n : 3;
}
function botTicketOpenCount(PDO $db, array $bot, int $userId): int {
    $q = $db->prepare("SELECT COUNT(*) FROM tg_tickets WHERE bot_id=? AND user_id=? AND status='open'");
    $q->execute([(int)$bot['id'], $userId]); return (int)$q->fetchColumn();
}
/** تیکت مشتری فقط وقتی برمی‌گردد که bot_id، user_id و chat_id هر سه متعلق به همان نشست باشند. */
function botTicketUserOwned(PDO $db, array $bot, array $u, int $ticketId): ?array {
    $q = $db->prepare('SELECT t.*, tu.chat_id, tu.username FROM tg_tickets t JOIN tg_users tu ON tu.id=t.user_id AND tu.bot_id=t.bot_id WHERE t.id=? AND t.bot_id=? AND t.user_id=? AND tu.chat_id=?');
    $q->execute([$ticketId, (int)$bot['id'], (int)$u['id'], (int)$u['chat_id']]); $r = $q->fetch(PDO::FETCH_ASSOC);
    return $r ?: null;
}
/** نسخه‌ی ادمین نیز همیشه با bot_id محدود است. */
function botTicketAdminOwned(PDO $db, array $bot, int $ticketId): ?array {
    $q = $db->prepare('SELECT t.*, tu.chat_id, tu.username FROM tg_tickets t JOIN tg_users tu ON tu.id=t.user_id AND tu.bot_id=t.bot_id WHERE t.id=? AND t.bot_id=?');
    $q->execute([$ticketId, (int)$bot['id']]); $r = $q->fetch(PDO::FETCH_ASSOC); return $r ?: null;
}
function botTicketUserList(PDO $db, array $bot, array $u, int $page = 0): void {
    $page = max(0, min(10000, $page)); $bid = (int)$bot['id']; $uid = (int)$u['id']; $chat = (int)$u['chat_id']; $offset = $page * 10;
    $q = $db->prepare('SELECT id, subject, status, updated_at FROM tg_tickets WHERE bot_id=? AND user_id=? ORDER BY updated_at DESC, id DESC LIMIT 10 OFFSET ?');
    $q->execute([$bid, $uid, $offset]); $rows = $q->fetchAll(PDO::FETCH_ASSOC);
    $n = $db->prepare('SELECT COUNT(*) FROM tg_tickets WHERE bot_id=? AND user_id=?'); $n->execute([$bid, $uid]); $total = (int)$n->fetchColumn();
    $txt = "🎫 <b>تیکت‌های من</b>\n" . ($total ? 'برای مشاهده‌ی گفتگو، روی تیکت بزنید.' : 'هنوز تیکتی ندارید.'); $kb = [];
    foreach ($rows as $r) $kb[] = [botAB((string)$r['subject'] . ' — #' . (int)$r['id'] . ((string)$r['status'] === 'open' ? ' 🟢' : ' 🔒'), 't:view:' . (int)$r['id'])];
    $nav = []; if ($page > 0) $nav[] = botAB('⬅️ قبلی', 't:list:' . ($page - 1)); if ($offset + 10 < $total) $nav[] = botAB('بعدی ➡️', 't:list:' . ($page + 1)); if ($nav) $kb[] = $nav;
    $kb[] = [botAB('🎫 تیکت جدید', 't:new'), botAB('بازگشت', 'm:sup')]; botSay($db, $bot, $chat, $txt, $kb);
}
function botTicketShowUser(PDO $db, array $bot, array $u, int $ticketId): void {
    $ticket = botTicketUserOwned($db, $bot, $u, $ticketId);
    if (!$ticket) { botSay($db, $bot, (int)$u['chat_id'], 'تیکت پیدا نشد.', [[botAB('تیکت‌های من', 't:list:0')]]); return; }
    $q = $db->prepare('SELECT from_admin, text, created_at FROM tg_ticket_msgs WHERE bot_id=? AND ticket_id=? ORDER BY id DESC LIMIT 20');
    $q->execute([(int)$bot['id'], $ticketId]); $msgs = array_reverse($q->fetchAll(PDO::FETCH_ASSOC));
    $txt = '🎫 <b>تیکت #' . $ticketId . ' — ' . bh((string)$ticket['subject']) . "</b>\nوضعیت: " . ((string)$ticket['status'] === 'open' ? 'باز' : 'بسته');
    foreach ($msgs as $m) $txt .= "\n\n<b>" . ((int)$m['from_admin'] === 1 ? 'پشتیبانی' : 'شما') . '</b> — ' . date('m/d H:i', (int)$m['created_at']) . "\n" . nl2br(bh(mb_substr((string)$m['text'], 0, 1600)));
    $txt = mb_substr($txt, 0, 3900); $kb = [];
    if ((string)$ticket['status'] === 'open') $kb[] = [botAB('✍️ ادامه‌ی گفتگو', 't:reply:' . $ticketId, 'primary'), botAB('بستن تیکت', 't:close:' . $ticketId, 'danger')];
    $kb[] = [botAB('تیکت‌های من', 't:list:0'), botAB('بازگشت به پشتیبانی', 'm:sup')];
    botSay($db, $bot, (int)$u['chat_id'], $txt, $kb);
}
function botTicketNotifyAdmins(PDO $db, array $bot, int $ticketId, string $subject, string $message, int $customerChat): void {
    $text = '🎫 <b>پیام جدید در تیکت #' . $ticketId . '</b>\nموضوع: ' . bh($subject) . "\nمشتری: <code>" . $customerChat . "</code>\n\n" . nl2br(bh(mb_substr($message, 0, 2600)));
    $text = mb_substr($text, 0, 3900);
    $kb = [[botAB('مشاهده و پاسخ', 'a:tkt:' . $ticketId)]];
    foreach (botEventRecipients($db, $bot, 'tickets') as $to) botSay($db, $bot, $to, $text, $kb);
    botEvent($db, $bot, 'ticket', $text, $kb);
}
function botTicketUserCallback(PDO $db, array $bot, array $cfg, array $u, string $v): void {
    $chat = (int)$u['chat_id']; $p = explode(':', $v); $act = (string)($p[0] ?? ''); $id = (int)($p[1] ?? 0);
    if ($act === 'new') {
        $open = botTicketOpenCount($db, $bot, (int)$u['id']); $max = botTicketMaxOpen($cfg);
        if ($open >= $max) { botSay($db, $bot, $chat, 'سقف تیکت باز شما پر است (' . $max . '). ابتدا یکی از تیکت‌های باز را ببندید.', [[botAB('تیکت‌های من', 't:list:0')]]); return; }
        $db->prepare('UPDATE tg_users SET state=?, state_val=0, draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['ticket_subject', '', (int)$u['id'], (int)$bot['id'], $chat]);
        botSay($db, $bot, $chat, 'موضوع تیکت را در یک پیام کوتاه بفرستید (حداکثر ۱۰۰ نویسه).'); return;
    }
    if ($act === 'list') { botTicketUserList($db, $bot, $u, $id); return; }
    if ($act === 'view') { botTicketShowUser($db, $bot, $u, $id); return; }
    if ($act === 'reply') {
        $ticket = botTicketUserOwned($db, $bot, $u, $id);
        if (!$ticket || (string)$ticket['status'] !== 'open') { botSay($db, $bot, $chat, 'تیکت باز پیدا نشد.', [[botAB('تیکت‌های من', 't:list:0')]]); return; }
        $db->prepare('UPDATE tg_users SET state=?, state_val=?, draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['ticket_reply', $id, '', (int)$u['id'], (int)$bot['id'], $chat]);
        botSay($db, $bot, $chat, 'پیام خود را برای تیکت #' . $id . ' بفرستید.'); return;
    }
    if ($act === 'close') {
        $ticket = botTicketUserOwned($db, $bot, $u, $id);
        if (!$ticket) { botSay($db, $bot, $chat, 'تیکت پیدا نشد.'); return; }
        $q = $db->prepare("UPDATE tg_tickets SET status='closed', updated_at=? WHERE id=? AND bot_id=? AND user_id=? AND status='open'");
        $q->execute([time(), $id, (int)$bot['id'], (int)$u['id']]);
        if ($q->rowCount() === 1) botAudit($db, $bot, $chat, 'ticket_close', 'ticket:' . $id, ['by' => 'customer']);
        botTicketShowUser($db, $bot, $u, $id); return;
    }
}
function botTicketUserText(PDO $db, array $bot, array $u, string $text): bool {
    $st = (string)($u['state'] ?? '');
    if (!in_array($st, ['ticket_subject', 'ticket_message', 'ticket_reply'], true)) return false;
    $chat = (int)$u['chat_id']; $bid = (int)$bot['id']; $body = botTicketCleanBody($text, $st === 'ticket_subject' ? 100 : 3500);
    if ($body === '') { botSay($db, $bot, $chat, 'متن خالی است؛ دوباره بفرستید.'); return true; }
    if ($st === 'ticket_subject') {
        $db->prepare('UPDATE tg_users SET state=?, state_val=0, draft=? WHERE id=? AND bot_id=? AND chat_id=?')
           ->execute(['ticket_message', json_encode(['ticket_subject' => $body], JSON_UNESCAPED_UNICODE), (int)$u['id'], $bid, $chat]);
        botSay($db, $bot, $chat, 'حالا شرح مشکل را بفرستید (حداکثر ۳۵۰۰ نویسه).'); return true;
    }
    if ($st === 'ticket_message') {
        $d = json_decode((string)($u['draft'] ?? ''), true); $subject = is_array($d) ? trim((string)($d['ticket_subject'] ?? '')) : '';
        $agent = botAgentRow($db, (int)$bot['agent_id']); $cfg = $agent ? botCfg($db, (int)$agent['id']) : botDefaults(); $max = botTicketMaxOpen($cfg);
        if ($subject === '') { $db->prepare('UPDATE tg_users SET state=?, state_val=0, draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['ticket_subject', '', (int)$u['id'], $bid, $chat]); botSay($db, $bot, $chat, 'موضوع نامعتبر است؛ دوباره بفرستید.'); return true; }
        if (botTicketOpenCount($db, $bot, (int)$u['id']) >= $max) { botState($db, $u, ''); $db->prepare('UPDATE tg_users SET draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['', (int)$u['id'], $bid, $chat]); botSay($db, $bot, $chat, 'سقف تیکت باز شما پر شده است (' . $max . ').', [[botAB('تیکت‌های من', 't:list:0')]]); return true; }
        $now = time(); $db->beginTransaction();
        try {
            $db->prepare("INSERT INTO tg_tickets (bot_id, user_id, subject, status, updated_at, created_at) VALUES (?,?,?,'open',?,?)")->execute([$bid, (int)$u['id'], $subject, $now, $now]);
            $ticketId = (int)$db->lastInsertId();
            $db->prepare('INSERT INTO tg_ticket_msgs (bot_id, ticket_id, from_admin, text, created_at) VALUES (?,?,0,?,?)')->execute([$bid, $ticketId, $body, $now]);
            $db->prepare('UPDATE tg_users SET state=?, state_val=0, draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['', '', (int)$u['id'], $bid, $chat]);
            $db->commit();
        } catch (Throwable $e) { if ($db->inTransaction()) $db->rollBack(); error_log('botTicketCreate: ' . get_class($e)); botSay($db, $bot, $chat, 'ثبت تیکت ناموفق بود؛ دوباره تلاش کنید.'); return true; }
        botSay($db, $bot, $chat, '✅ تیکت #' . $ticketId . ' ثبت شد.', [[botAB('مشاهده‌ی تیکت', 't:view:' . $ticketId), botAB('تیکت‌های من', 't:list:0')]]);
        botTicketNotifyAdmins($db, $bot, $ticketId, $subject, $body, $chat); return true;
    }
    $ticketId = (int)($u['state_val'] ?? 0); $ticket = botTicketUserOwned($db, $bot, $u, $ticketId);
    if (!$ticket || (string)$ticket['status'] !== 'open') { botState($db, $u, ''); botSay($db, $bot, $chat, 'تیکت باز پیدا نشد.', [[botAB('تیکت‌های من', 't:list:0')]]); return true; }
    $now = time(); $db->beginTransaction();
    try {
        $db->prepare('INSERT INTO tg_ticket_msgs (bot_id, ticket_id, from_admin, text, created_at) VALUES (?,?,0,?,?)')->execute([$bid, $ticketId, $body, $now]);
        $up = $db->prepare("UPDATE tg_tickets SET updated_at=? WHERE id=? AND bot_id=? AND user_id=? AND status='open'");
        $up->execute([$now, $ticketId, $bid, (int)$u['id']]);
        if ($up->rowCount() !== 1) throw new RuntimeException('ticket closed during customer reply');
        $db->commit();
    } catch (Throwable $e) {
        if ($db->inTransaction()) $db->rollBack(); botState($db, $u, '');
        botSay($db, $bot, $chat, 'ثبت پیام انجام نشد؛ تیکت را دوباره بررسی کنید.', [[botAB('تیکت‌های من', 't:list:0')]]); return true;
    }
    botState($db, $u, ''); botSay($db, $bot, $chat, '✅ پیام شما به تیکت #' . $ticketId . ' اضافه شد.', [[botAB('مشاهده‌ی تیکت', 't:view:' . $ticketId)]]);
    botTicketNotifyAdmins($db, $bot, $ticketId, (string)$ticket['subject'], $body, $chat); return true;
}
function botTicketAdminList(PDO $db, array $bot, int $chat, int $page = 0): void {
    $page = max(0, min(10000, $page)); $bid = (int)$bot['id']; $off = $page * 10;
    $q = $db->prepare("SELECT t.id, t.subject, t.updated_at, u.chat_id, u.username FROM tg_tickets t JOIN tg_users u ON u.id=t.user_id AND u.bot_id=t.bot_id WHERE t.bot_id=? AND t.status='open' ORDER BY t.updated_at DESC, t.id DESC LIMIT 10 OFFSET ?");
    $q->execute([$bid, $off]); $rows = $q->fetchAll(PDO::FETCH_ASSOC);
    $c = $db->prepare("SELECT COUNT(*) FROM tg_tickets WHERE bot_id=? AND status='open'"); $c->execute([$bid]); $total = (int)$c->fetchColumn();
    $txt = '🎫 <b>تیکت‌های باز</b> — ' . $total; $kb = [];
    if (!$rows) $txt .= "\nتیکت بازی وجود ندارد.";
    foreach ($rows as $r) $kb[] = [botAB('#' . (int)$r['id'] . ' — ' . mb_substr((string)$r['subject'], 0, 60) . ' — ' . (int)$r['chat_id'], 'a:tkt:' . (int)$r['id'])];
    $nav = []; if ($page > 0) $nav[] = botAB('⬅️ قبلی', 'a:tk:' . ($page - 1)); if ($off + 10 < $total) $nav[] = botAB('بعدی ➡️', 'a:tk:' . ($page + 1)); if ($nav) $kb[] = $nav;
    $kb[] = [botAB('پاسخ‌های آماده', 'a:ck:0'), botAB('بازگشت', 'a:home')]; botSay($db, $bot, $chat, $txt, $kb);
}
function botTicketAdminView(PDO $db, array $bot, int $chat, int $ticketId): void {
    $ticket = botTicketAdminOwned($db, $bot, $ticketId);
    if (!$ticket) { botSay($db, $bot, $chat, 'تیکت پیدا نشد.', [[botAB('تیکت‌های باز', 'a:tk:0')]]); return; }
    $q = $db->prepare('SELECT from_admin, text, created_at FROM tg_ticket_msgs WHERE bot_id=? AND ticket_id=? ORDER BY id DESC LIMIT 20'); $q->execute([(int)$bot['id'], $ticketId]); $msgs = array_reverse($q->fetchAll(PDO::FETCH_ASSOC));
    $txt = '🎫 <b>تیکت #' . $ticketId . ' — ' . bh((string)$ticket['subject']) . "</b>\nمشتری: <code>" . (int)$ticket['chat_id'] . '</code>' . ((string)$ticket['username'] !== '' ? ' (@' . bh((string)$ticket['username']) . ')' : '') . "\nوضعیت: " . ((string)$ticket['status'] === 'open' ? 'باز' : 'بسته');
    foreach ($msgs as $m) $txt .= "\n\n<b>" . ((int)$m['from_admin'] === 1 ? 'پشتیبانی' : 'مشتری') . '</b> — ' . date('m/d H:i', (int)$m['created_at']) . "\n" . nl2br(bh(mb_substr((string)$m['text'], 0, 1300)));
    $txt = mb_substr($txt, 0, 3900); $kb = [];
    if ((string)$ticket['status'] === 'open') $kb[] = [botAB('✍️ پاسخ به تیکت', 'a:tka:' . $ticketId, 'primary'), botAB('بستن تیکت', 'a:tkc:' . $ticketId, 'danger')];
    $kb[] = [botAB('پاسخ‌های آماده', 'a:ck:' . $ticketId), botAB('تیکت‌های باز', 'a:tk:0')]; botSay($db, $bot, $chat, $txt, $kb);
}
function botTicketAdminReply(PDO $db, array $bot, int $adminChat, int $ticketId, string $message, string $source = 'admin'): bool {
    $ticket = botTicketAdminOwned($db, $bot, $ticketId);
    if (!$ticket || (string)$ticket['status'] !== 'open') { botSay($db, $bot, $adminChat, 'تیکت باز پیدا نشد.', [[botAB('تیکت‌های باز', 'a:tk:0')]]); return false; }
    $body = botTicketCleanBody($message, 3500); if ($body === '') { botSay($db, $bot, $adminChat, 'متن پاسخ خالی است.'); return false; }
    $now = time(); $db->beginTransaction();
    try {
        $db->prepare('INSERT INTO tg_ticket_msgs (bot_id, ticket_id, from_admin, text, created_at) VALUES (?,?,1,?,?)')->execute([(int)$bot['id'], $ticketId, $body, $now]);
        $up = $db->prepare("UPDATE tg_tickets SET updated_at=? WHERE id=? AND bot_id=? AND status='open'"); $up->execute([$now, $ticketId, (int)$bot['id']]);
        if ($up->rowCount() !== 1) throw new RuntimeException('ticket closed during reply');
        $db->commit();
    } catch (Throwable $e) { if ($db->inTransaction()) $db->rollBack(); botSay($db, $bot, $adminChat, 'ثبت پاسخ انجام نشد؛ وضعیت تیکت را بررسی کنید.'); return false; }
    botAudit($db, $bot, $adminChat, 'ticket_reply', 'ticket:' . $ticketId, ['source' => $source]);
    $txt = '🎫 <b>پاسخ پشتیبانی به تیکت #' . $ticketId . '</b>\nموضوع: ' . bh((string)$ticket['subject']) . "\n\n" . nl2br(bh($body));
    $txt = mb_substr($txt, 0, 3900);
    botSay($db, $bot, (int)$ticket['chat_id'], $txt, [[botAB('مشاهده‌ی تیکت', 't:view:' . $ticketId)]]);
    botSay($db, $bot, $adminChat, '✅ پاسخ به تیکت #' . $ticketId . ' ارسال شد.'); botTicketAdminView($db, $bot, $adminChat, $ticketId); return true;
}
function botTicketAdminClose(PDO $db, array $bot, int $adminChat, int $ticketId): void {
    $ticket = botTicketAdminOwned($db, $bot, $ticketId);
    if (!$ticket) { botSay($db, $bot, $adminChat, 'تیکت پیدا نشد.'); return; }
    $q = $db->prepare("UPDATE tg_tickets SET status='closed', updated_at=? WHERE id=? AND bot_id=? AND status='open'"); $q->execute([time(), $ticketId, (int)$bot['id']]);
    if ($q->rowCount() === 1) {
        botAudit($db, $bot, $adminChat, 'ticket_close', 'ticket:' . $ticketId, ['by' => 'admin']);
        botSay($db, $bot, (int)$ticket['chat_id'], 'تیکت #' . $ticketId . ' توسط پشتیبانی بسته شد.', [[botAB('مشاهده‌ی تیکت', 't:view:' . $ticketId)]]);
    } else botSay($db, $bot, $adminChat, 'این تیکت قبلاً بسته شده است.');
    botTicketAdminView($db, $bot, $adminChat, $ticketId);
}
function botCannedAdminList(PDO $db, array $bot, int $chat, int $ticketId = 0): void {
    if ($ticketId > 0) { $t = botTicketAdminOwned($db, $bot, $ticketId); if (!$t || (string)$t['status'] !== 'open') $ticketId = 0; }
    $q = $db->prepare('SELECT id, title FROM tg_canned WHERE bot_id=? ORDER BY id DESC LIMIT 20'); $q->execute([(int)$bot['id']]); $rows = $q->fetchAll(PDO::FETCH_ASSOC);
    $txt = "📝 <b>پاسخ‌های آماده</b>\n" . ($rows ? 'برای استفاده روی عنوان بزنید؛ حذف هر پاسخ هم در دسترس است.' : 'هنوز پاسخ آماده‌ای ثبت نشده است.'); $kb = [];
    foreach ($rows as $r) {
        $label = mb_substr((string)$r['title'], 0, 35);
        if ($ticketId > 0) $kb[] = [botAB('ارسال: ' . $label, 'a:cks:' . $ticketId . ':' . (int)$r['id'], 'success'), botAB('🗑 حذف', 'a:ckd:' . (int)$r['id'] . ':' . $ticketId, 'danger')];
        else $kb[] = [botAB('🗑 حذف: ' . $label, 'a:ckd:' . (int)$r['id'], 'danger')];
    }
    $kb[] = [botAB('➕ افزودن پاسخ آماده', 'a:cka:' . $ticketId)];
    $kb[] = [$ticketId > 0 ? botAB('بازگشت به تیکت', 'a:tkt:' . $ticketId) : botAB('تیکت‌های باز', 'a:tk:0'), botAB('بازگشت', 'a:home')];
    botSay($db, $bot, $chat, $txt, $kb);
}
function botTutorialKind(int $kind): string { return $kind === 1 ? 'faq' : 'tutorial'; }
function botTutorialRow(PDO $db, array $bot, int $id): ?array {
    $q = $db->prepare('SELECT * FROM tg_tutorials WHERE id=? AND bot_id=?'); $q->execute([$id, (int)$bot['id']]); $r = $q->fetch(PDO::FETCH_ASSOC); return $r ?: null;
}
function botTutorialCustomerList(PDO $db, array $bot, int $chat, string $kind): void {
    if (!in_array($kind, ['tutorial', 'faq'], true)) return;
    $q = $db->prepare('SELECT id, title FROM tg_tutorials WHERE bot_id=? AND kind=? AND active=1 ORDER BY sort, id LIMIT 50'); $q->execute([(int)$bot['id'], $kind]); $rows = $q->fetchAll(PDO::FETCH_ASSOC);
    $title = $kind === 'faq' ? '❓ سوالات متداول' : '📚 آموزش‌ها'; $txt = '<b>' . $title . '</b>'; $kb = [];
    foreach ($rows as $r) $kb[] = [botAB(mb_substr((string)$r['title'], 0, 55), 'm:tv:' . (int)$r['id'])];
    if (!$rows) $txt .= "\nمورد فعالی وجود ندارد.";
    $kb[] = [botAB('بازگشت به منو', 'm:home')]; botSay($db, $bot, $chat, $txt, $kb);
}
function botTutorialCustomerView(PDO $db, array $bot, int $chat, int $id): void {
    $q = $db->prepare('SELECT kind, title, body FROM tg_tutorials WHERE id=? AND bot_id=? AND active=1 AND kind IN (\'tutorial\',\'faq\')'); $q->execute([$id, (int)$bot['id']]); $r = $q->fetch(PDO::FETCH_ASSOC);
    if (!$r) { botSay($db, $bot, $chat, 'این آموزش یا سوال متداول پیدا نشد یا غیرفعال است.', [[botAB('بازگشت به منو', 'm:home')]]); return; }
    $txt = '<b>' . bh((string)$r['title']) . "</b>\n\n" . nl2br(bh((string)$r['body']));
    $kb = [[botAB('بازگشت', $r['kind'] === 'faq' ? 'm:faqs' : 'm:tuts'), botAB('منوی اصلی', 'm:home')]]; botSay($db, $bot, $chat, mb_substr($txt, 0, 3900), $kb);
}
function botTutorialAdminHome(PDO $db, array $bot, int $chat): void {
    $bid = (int)$bot['id']; $q = $db->prepare('SELECT kind, COUNT(*) total, SUM(CASE WHEN active=1 THEN 1 ELSE 0 END) active_n FROM tg_tutorials WHERE bot_id=? GROUP BY kind'); $q->execute([$bid]); $counts = [];
    foreach ($q->fetchAll(PDO::FETCH_ASSOC) as $r) $counts[(string)$r['kind']] = (int)$r['total'] . ' (' . (int)$r['active_n'] . ' فعال)';
    $txt = '📚 <b>مدیریت آموزش‌ها و سوالات متداول</b>\nآموزش‌ها: ' . ($counts['tutorial'] ?? '۰') . '\nسوالات متداول: ' . ($counts['faq'] ?? '۰');
    $kb = [[botAB('📚 فهرست آموزش‌ها', 'a:tul:0'), botAB('❓ فهرست سوالات', 'a:tul:1')], [botAB('➕ افزودن آموزش', 'a:tun:0', 'success'), botAB('➕ افزودن سوال', 'a:tun:1', 'success')], [botAB('بازگشت', 'a:home')]];
    botSay($db, $bot, $chat, $txt, $kb);
}
function botTutorialAdminList(PDO $db, array $bot, int $chat, string $kind): void {
    if (!in_array($kind, ['tutorial', 'faq'], true)) { botTutorialAdminHome($db, $bot, $chat); return; }
    $q = $db->prepare('SELECT id, title, active FROM tg_tutorials WHERE bot_id=? AND kind=? ORDER BY sort, id LIMIT 100'); $q->execute([(int)$bot['id'], $kind]); $rows = $q->fetchAll(PDO::FETCH_ASSOC);
    $txt = '<b>' . ($kind === 'faq' ? '❓ سوالات متداول' : '📚 آموزش‌ها') . '</b>'; $kb = [];
    foreach ($rows as $r) $kb[] = [botAB(((int)$r['active'] === 1 ? '✅ ' : '⏸ ') . mb_substr((string)$r['title'], 0, 48) . ' #' . (int)$r['id'], 'a:tuv:' . (int)$r['id'])];
    if (!$rows) $txt .= "\nهنوز موردی ثبت نشده است.";
    $kb[] = [botAB('➕ افزودن', 'a:tun:' . ($kind === 'faq' ? 1 : 0))]; $kb[] = [botAB('بازگشت', 'a:tu'), botAB('پنل اصلی', 'a:home')]; botSay($db, $bot, $chat, $txt, $kb);
}
function botTutorialAdminView(PDO $db, array $bot, int $chat, int $id): void {
    $r = botTutorialRow($db, $bot, $id); if (!$r) { botSay($db, $bot, $chat, 'مورد پیدا نشد.', [[botAB('بازگشت', 'a:tu')]]); return; }
    $kind = (string)$r['kind']; $txt = '<b>' . bh((string)$r['title']) . '</b>\nنوع: ' . ($kind === 'faq' ? 'سوال متداول' : 'آموزش') . '\nوضعیت: ' . ((int)$r['active'] === 1 ? 'فعال' : 'خاموش') . "\nترتیب: " . (int)$r['sort'] . "\n\n" . nl2br(bh((string)$r['body']));
    $kb = [[botAB('✏️ ویرایش عنوان و متن', 'a:tue:' . $id)], [botAB((int)$r['active'] === 1 ? 'خاموش کردن' : 'روشن کردن', 'a:tuo:' . $id), botAB('🗑 حذف', 'a:tud:' . $id, 'danger')], [botAB('⬆️ بالاتر', 'a:tus:' . $id . ':up'), botAB('⬇️ پایین‌تر', 'a:tus:' . $id . ':down')], [botAB('بازگشت به فهرست', 'a:tul:' . ($kind === 'faq' ? 1 : 0)), botAB('پنل مدیریت', 'a:tu')]];
    botSay($db, $bot, $chat, mb_substr($txt, 0, 3900), $kb);
}
function botTutorialMove(PDO $db, array $bot, int $chat, int $id, string $direction): void {
    $row = botTutorialRow($db, $bot, $id); if (!$row || !in_array($direction, ['up', 'down'], true)) { botSay($db, $bot, $chat, 'مورد پیدا نشد.'); return; }
    $kind = (string)$row['kind']; $q = $db->prepare('SELECT id FROM tg_tutorials WHERE bot_id=? AND kind=? ORDER BY sort, id'); $q->execute([(int)$bot['id'], $kind]); $ids = array_map('intval', $q->fetchAll(PDO::FETCH_COLUMN)); $idx = array_search($id, $ids, true);
    if ($idx !== false) { $other = $direction === 'up' ? $idx - 1 : $idx + 1; if ($other >= 0 && $other < count($ids)) { [$ids[$idx], $ids[$other]] = [$ids[$other], $ids[$idx]]; foreach ($ids as $i => $tid) $db->prepare('UPDATE tg_tutorials SET sort=? WHERE id=? AND bot_id=? AND kind=?')->execute([($i + 1) * 10, $tid, (int)$bot['id'], $kind]); botAudit($db, $bot, $chat, 'tutorial_sort', (string)$id, ['direction' => $direction]); } }
    botTutorialAdminView($db, $bot, $chat, $id);
}

function botMenu(array $cfg, bool $admin = false): array {
    $make = function (string $k) use ($cfg): ?array {
        switch ($k) {
            case 'test': return (int)$cfg['t_on'] === 1 ? botBL($cfg, 'test', ['callback_data' => 'm:test']) : null;
            case 'buy': return botBL($cfg, 'buy', ['callback_data' => 'm:buy']);
            case 'wal': return botBL($cfg, 'wal', ['callback_data' => 'm:wal']);
            case 'acc': return botBL($cfg, 'acc', ['callback_data' => 'm:acc']);
            case 'dl': return botBL($cfg, 'dl', ['callback_data' => 'm:dl']);
            case 'sup': return botBL($cfg, 'sup', ['callback_data' => 'm:sup']);
            case 'tuts': return !empty($cfg['_has_tutorials']) ? botAB('📚 آموزش‌ها', 'm:tuts') : null;
            case 'faqs': return !empty($cfg['_has_faq']) ? botAB('❓ سوالات متداول', 'm:faqs') : null;
            case 'club': return (int)($cfg['club_on'] ?? 0) === 1 ? botAB('🎁 باشگاه مشتریان', 'cl:home') : null;
        }
        return null;
    };
    $rows = [];
    foreach (botMenuClean($cfg['menu'] ?? null) as $it) {
        if (!$it['on']) continue;
        $b = $make((string)$it['k']);
        if ($b === null) continue;
        if ($it['j'] && $rows && count($rows[count($rows) - 1]) < 2) $rows[count($rows) - 1][] = $b; else $rows[] = [$b];
    }
    if ($admin) $rows[] = [botBL($cfg, 'adm', ['callback_data' => 'a:home'])];
    return $rows;
}
function botMn(PDO $db, array $bot, array $cfg, int $chat): array {
    $bid = (int)$bot['id'];
    $q = $db->prepare("SELECT kind, COUNT(*) FROM tg_tutorials WHERE bot_id=? AND active=1 AND kind IN ('tutorial','faq') GROUP BY kind");
    $q->execute([$bid]); $has = [];
    foreach ($q->fetchAll(PDO::FETCH_NUM) as $r) $has[(string)$r[0]] = (int)$r[1] > 0;
    $cfg['_has_tutorials'] = !empty($has['tutorial']); $cfg['_has_faq'] = !empty($has['faq']);
    return botMenu($cfg, botIsStaff($db, $bot, $chat));
}
function botAgentRow(PDO $db, int $agId): ?array {
    // ادمین اصلی (role=admin) هم می‌تواند صاحب یک ربات باشد؛ با همان قابلیت‌های ربات نماینده و بدون سقف‌های نمایندگی
    $s = $db->prepare("SELECT * FROM accounts WHERE id=? AND role IN ('agent','admin') AND disabled=0"); $s->execute([$agId]);
    $r = $s->fetch(PDO::FETCH_ASSOC);
    return $r ?: null;
}
function botUser(PDO $db, array $bot, int $chat, string $uname): array {
    $s = $db->prepare('SELECT * FROM tg_users WHERE bot_id=? AND chat_id=?'); $s->execute([(int)$bot['id'], $chat]);
    $u = $s->fetch(PDO::FETCH_ASSOC); $new = false;
    if (!$u) {
        $db->prepare('INSERT OR IGNORE INTO tg_users (bot_id, chat_id, username, created_at) VALUES (?,?,?,?)')->execute([(int)$bot['id'], $chat, $uname, time()]);
        $s->execute([(int)$bot['id'], $chat]); $u = $s->fetch(PDO::FETCH_ASSOC); $new = true;
    } elseif ($uname !== '' && (string)$u['username'] !== $uname) {
        $db->prepare('UPDATE tg_users SET username=? WHERE id=? AND bot_id=?')->execute([$uname, (int)$u['id'], (int)$bot['id']]);
    }
    $u['_new'] = $new;
    return $u;
}
function botState(PDO $db, array $u, string $state, int $val = 0): void {
    $db->prepare('UPDATE tg_users SET state=?, state_val=? WHERE id=? AND bot_id=?')->execute([$state, $val, (int)$u['id'], (int)($u['bot_id'] ?? 0)]);
}
/** مدت مسدودیِ ضد اسپم بعد از تخطیِ n‌ام: min(60·2^n, 86400) ثانیه */
function botSpamSecs(int $n): int { return (int)min(60 * (2 ** min(max($n, 0), 20)), 86400); }
/**
 * سقف ۲۵ درخواست در دقیقه. تخطی: spam_n++ و مسدودی نمایی تا ۲۴ ساعت (در این مدت پاسخی داده نمی‌شود و تخطی جدید شمرده نمی‌شود)؛
 * اگر ۲۴ ساعت از پایان آخرین مسدودی بدون تخطی بگذرد spam_n صفر می‌شود. ادمین‌ها ($staff) فقط سقف دقیقه‌ای را دارند و هرگز قفل نمی‌شوند.
 */
function botRateOk(PDO $db, array $u, bool $staff = false): bool {
    $now = time(); $id = (int)$u['id']; $bid = (int)$u['bot_id'];
    $n = (int)($u['spam_n'] ?? 0); $until = (int)($u['spam_until'] ?? 0);
    if (!$staff) {
        if ($until > $now) return false;
        if ($n > 0 && $now >= $until + 86400) { // ۲۴ ساعت بعد از پایان آخرین مسدودی بدون تخطی
            $db->prepare('UPDATE tg_users SET spam_n=0, spam_until=0 WHERE id=? AND bot_id=?')->execute([$id, $bid]);
        }
    }
    if ((int)$u['rl_at'] < $now - 60) { $db->prepare('UPDATE tg_users SET rl_at=?, rl_n=1 WHERE id=? AND bot_id=?')->execute([$now, $id, $bid]); return true; }
    $db->prepare('UPDATE tg_users SET rl_n=rl_n+1 WHERE id=? AND bot_id=?')->execute([$id, $bid]);
    if ((int)$u['rl_n'] + 1 <= 25) return true;
    if (!$staff) {
        $db->prepare('UPDATE tg_users SET spam_n=spam_n+1 WHERE id=? AND bot_id=?')->execute([$id, $bid]);
        $q = $db->prepare('SELECT spam_n FROM tg_users WHERE id=? AND bot_id=?'); $q->execute([$id, $bid]);
        $db->prepare('UPDATE tg_users SET spam_until=? WHERE id=? AND bot_id=?')->execute([$now + botSpamSecs((int)$q->fetchColumn()), $id, $bid]);
    }
    return false;
}
function botLazy(PDO $db): void {
    $now = time();
    $cp = $db->prepare("SELECT id, bot_id FROM tg_orders WHERE status='awaiting_receipt' AND created_at<? AND coupon_id>0"); $cp->execute([$now - 86400]);
    $withCoupon = $cp->fetchAll(PDO::FETCH_ASSOC);
    $db->prepare("UPDATE tg_orders SET status='cancelled', updated_at=? WHERE status='awaiting_receipt' AND created_at<?")->execute([$now, $now - 86400]);
    foreach ($withCoupon as $o) botCouponReleaseByOrder($db, (int)$o['bot_id'], (int)$o['id']); // فقط اگر سفارش واقعاً لغو شده باشد
    $db->prepare("UPDATE tg_orders SET status='pending_review', updated_at=? WHERE status='approving' AND updated_at<?")->execute([$now, $now - 300]);
}

// ------------------------------------------------------------------ کیف پول ربات (هدیه، کش‌بک، دعوت، شارژ دستی ادمین)
/** تغییر اتمیک موجودی؛ اگر کسر باعث منفی شدن شود null برمی‌گرداند */
function botWalletAdd(PDO $db, array $bot, int $uid, int $delta, string $reason): ?int {
    $u = $db->prepare('UPDATE tg_users SET balance=balance+? WHERE id=? AND bot_id=? AND balance+?>=0');
    $u->execute([$delta, $uid, (int)$bot['id'], $delta]);
    if ($u->rowCount() !== 1) return null;
    $b = $db->prepare('SELECT balance FROM tg_users WHERE id=? AND bot_id=?'); $b->execute([$uid, (int)$bot['id']]);
    $bal = (int)$b->fetchColumn();
    $db->prepare('INSERT INTO tg_wallet_tx (bot_id, user_id, delta, balance_after, reason, created_at) VALUES (?,?,?,?,?,?)')->execute([(int)$bot['id'], $uid, $delta, $bal, $reason, time()]);
    return $bal;
}
function botBalance(PDO $db, int $uid, int $botId): int {
    $b = $db->prepare('SELECT balance FROM tg_users WHERE id=? AND bot_id=?'); $b->execute([$uid, $botId]);
    return (int)$b->fetchColumn();
}
function botPrice(array $cfg, int $price): int {
    if ((int)$cfg['promo_on'] === 1 && (int)$cfg['promo_pct'] > 0) return max(1, (int)round($price * (100 - min(90, (int)$cfg['promo_pct'])) / 100));
    return $price;
}

// ------------------------------------------------------------------ کد تخفیف (مرحله ۴)
/** اجرای $fn زیر قفل نوشتن (BEGIN IMMEDIATE)؛ اگر تراکنش بیرونی باز باشد SAVEPOINT می‌سازد. استثنا = برگشت کامل. */
function botAtomic(PDO $db, callable $fn) {
    $own = !$db->inTransaction();
    if ($own) $db->exec('BEGIN IMMEDIATE'); else $db->exec('SAVEPOINT bot_atomic');
    try {
        $r = $fn();
        $db->exec($own ? 'COMMIT' : 'RELEASE SAVEPOINT bot_atomic');
        return $r;
    } catch (Throwable $e) {
        try { $db->exec($own ? 'ROLLBACK' : 'ROLLBACK TO SAVEPOINT bot_atomic; RELEASE SAVEPOINT bot_atomic'); } catch (Throwable $e2) { /* تراکنش از قبل بسته شده */ }
        throw $e;
    }
}
/** کد را یکدست می‌کند (ارقام فارسی → لاتین، حروف بزرگ)؛ نامعتبر = '' */
function botCouponNorm(string $s): string {
    $s = strtoupper(trim(payDigits($s)));
    return preg_match('/^[A-Z0-9_\-]{3,20}$/', $s) ? $s : '';
}
/** قیمت بعد از کوپن؛ هرگز منفی نمی‌شود و حداقل ۱ تومان است (و هرگز بیشتر از قیمت ورودی نمی‌شود) */
function botCouponCalc(array $cp, int $price): int {
    $v = max(0, (int)$cp['value']);
    $new = (string)$cp['kind'] === 'amount' ? $price - $v : (int)round($price * (100 - min(100, $v)) / 100);
    return max(1, min($price, $new));
}
/**
 * اعتبارسنجی و (با $consume=true) مصرف اتمیک کد تخفیف برای یک خرید. $price = قیمتِ بعد از تخفیف همگانی (promo).
 * فقط کدهای همین ربات معتبرند. $orderId=0 یعنی سفارش هنوز ساخته نشده؛ بعد از ساخت، botCouponAttach صدا زده شود.
 * کوپن روی شارژ کیف پول ($kind='topup') اعمال نمی‌شود. مرحله‌ی ۵ برای تمدید هم از همین تابع و botCouponRelease استفاده می‌کند.
 * @return array{ok:bool,msg:string,price:int,discount:int,coupon_id:int,use_id:int,code:string}
 */
function botCouponApply(PDO $db, array $bot, array $u, string $code, int $price, int $orderId = 0, bool $consume = true, string $kind = 'plan'): array {
    $bad = fn(string $m): array => ['ok' => false, 'msg' => $m, 'price' => $price, 'discount' => 0, 'coupon_id' => 0, 'use_id' => 0, 'code' => ''];
    if ($kind === 'topup') return $bad('کد تخفیف روی شارژ کیف پول قابل استفاده نیست.');
    $c = botCouponNorm($code); $bid = (int)$bot['id']; $uid = (int)($u['id'] ?? 0);
    if ($c === '' || $price < 1 || $uid <= 0 || (int)($u['bot_id'] ?? 0) !== $bid) return $bad('کد تخفیف نامعتبر است.');
    return botAtomic($db, function () use ($db, $bid, $uid, $c, $price, $orderId, $consume, $bad): array {
        $now = time();
        $s = $db->prepare('SELECT * FROM tg_coupons WHERE bot_id=? AND code=?'); $s->execute([$bid, $c]);
        $cp = $s->fetch(PDO::FETCH_ASSOC);
        if (!$cp) return $bad('کد تخفیف نامعتبر است.');
        if ((int)$cp['active'] !== 1 || ((int)$cp['expires_at'] > 0 && (int)$cp['expires_at'] <= $now) || ((int)$cp['max_uses'] > 0 && (int)$cp['used'] >= (int)$cp['max_uses']))
            return $bad('این کد تخفیف دیگر قابل استفاده نیست.');
        if ((int)$cp['per_user'] > 0) {
            $n = $db->prepare('SELECT COUNT(*) FROM tg_coupon_uses WHERE bot_id=? AND coupon_id=? AND user_id=?'); $n->execute([$bid, (int)$cp['id'], $uid]);
            if ((int)$n->fetchColumn() >= (int)$cp['per_user']) return $bad('شما قبلاً از این کد تخفیف استفاده کرده‌اید.');
        }
        $new = botCouponCalc($cp, $price);
        if ($price - $new <= 0) return $bad('این کد روی این مبلغ تخفیفی ندارد.');
        $res = ['ok' => true, 'msg' => '', 'price' => $new, 'discount' => $price - $new, 'coupon_id' => (int)$cp['id'], 'use_id' => 0, 'code' => (string)$cp['code']];
        if (!$consume) return $res;
        $up = $db->prepare('UPDATE tg_coupons SET used=used+1 WHERE id=? AND bot_id=? AND active=1 AND (max_uses=0 OR used<max_uses) AND (expires_at=0 OR expires_at>?)');
        $up->execute([(int)$cp['id'], $bid, $now]);
        if ($up->rowCount() !== 1) return $bad('این کد تخفیف دیگر قابل استفاده نیست.');
        $db->prepare('INSERT INTO tg_coupon_uses (bot_id, coupon_id, user_id, order_id, created_at) VALUES (?,?,?,?,?)')->execute([$bid, (int)$cp['id'], $uid, $orderId, $now]);
        $res['use_id'] = (int)$db->lastInsertId();
        return $res;
    });
}
/** فقط بررسی و محاسبه‌ی قیمت جدید؛ چیزی مصرف نمی‌شود */
function botCouponPreview(PDO $db, array $bot, array $u, string $code, int $price, string $kind = 'plan'): array {
    return botCouponApply($db, $bot, $u, $code, $price, 0, false, $kind);
}
/** سفارش (که بعد از مصرف کوپن ساخته شد) را به ردیف مصرف وصل می‌کند */
function botCouponAttach(PDO $db, array $bot, int $useId, int $orderId): void {
    if ($useId <= 0) return;
    $db->prepare('UPDATE tg_coupon_uses SET order_id=? WHERE id=? AND bot_id=?')->execute([$orderId, $useId, (int)$bot['id']]);
}
/** برگرداندن یک مصرف: ردیف tg_coupon_uses حذف و used یکی کم می‌شود؛ فقط یک‌بار اثر دارد (دوباره صدا زدن بی‌اثر است) */
function botCouponRelease(PDO $db, array $bot, int $useId): bool {
    if ($useId <= 0) return false;
    $bid = (int)$bot['id'];
    return (bool)botAtomic($db, function () use ($db, $bid, $useId): bool {
        $s = $db->prepare('SELECT coupon_id FROM tg_coupon_uses WHERE id=? AND bot_id=?'); $s->execute([$useId, $bid]);
        $cid = $s->fetchColumn();
        if ($cid === false) return false;
        $d = $db->prepare('DELETE FROM tg_coupon_uses WHERE id=? AND bot_id=?'); $d->execute([$useId, $bid]);
        if ($d->rowCount() !== 1) return false;
        $db->prepare('UPDATE tg_coupons SET used=MAX(0, used-1) WHERE id=? AND bot_id=?')->execute([(int)$cid, $bid]);
        return true;
    });
}
/** مصرفِ کوپنِ یک سفارشِ لغو/ردشده را برمی‌گرداند؛ اگر سفارش در این ربات نباشد یا لغو/رد نشده باشد هیچ کاری نمی‌کند */
function botCouponReleaseByOrder(PDO $db, int $botId, int $oid): bool {
    $o = $db->prepare("SELECT 1 FROM tg_orders WHERE id=? AND bot_id=? AND status IN ('cancelled','rejected')"); $o->execute([$oid, $botId]);
    if (!$o->fetchColumn()) return false;
    $s = $db->prepare('SELECT id FROM tg_coupon_uses WHERE bot_id=? AND order_id=?'); $s->execute([$botId, $oid]);
    $ok = false;
    foreach ($s->fetchAll(PDO::FETCH_COLUMN) as $useId) if (botCouponRelease($db, ['id' => $botId], (int)$useId)) $ok = true;
    return $ok;
}
/** سفارش‌های «در انتظار رسید» این چت را لغو می‌کند و کوپنِ آن‌ها را برمی‌گرداند */
function botCancelAwaiting(PDO $db, int $botId, int $chat): void {
    $s = $db->prepare("SELECT id FROM tg_orders WHERE bot_id=? AND chat_id=? AND status='awaiting_receipt'"); $s->execute([$botId, $chat]);
    foreach ($s->fetchAll(PDO::FETCH_COLUMN) as $oid) {
        $u = $db->prepare("UPDATE tg_orders SET status='cancelled', updated_at=? WHERE id=? AND bot_id=? AND chat_id=? AND status='awaiting_receipt'");
        $u->execute([time(), (int)$oid, $botId, $chat]);
        if ($u->rowCount() === 1) botCouponReleaseByOrder($db, $botId, (int)$oid);
    }
}
function botOnNewUser(PDO $db, array $bot, array $cfg, array $u, int $refChat): void {
    $chat = (int)$u['chat_id'];
    if ($refChat > 0 && $refChat !== $chat) {
        $r = $db->prepare('SELECT id FROM tg_users WHERE bot_id=? AND chat_id=?'); $r->execute([(int)$bot['id'], $refChat]);
        if ($r->fetchColumn()) $db->prepare('UPDATE tg_users SET ref_by=? WHERE id=? AND ref_by=0')->execute([$refChat, (int)$u['id']]);
    }
    if ((int)$cfg['g_on'] === 1 && (int)$cfg['g_amt'] > 0 && botWalletAdd($db, $bot, (int)$u['id'], (int)$cfg['g_amt'], 'welcome gift') !== null)
        botSay($db, $bot, $chat, '🎁 هدیه‌ی عضویت: ' . botMoney((int)$cfg['g_amt']) . ' به کیف پول شما اضافه شد.');
}
/** بعد از هر خرید موفق: کش‌بک خریدار + پاداش دعوت‌کننده (فقط اولین خرید دعوت‌شده) */
function botAfterSale(PDO $db, array $bot, array $cfg, int $chat, int $price): void {
    $s = $db->prepare('SELECT * FROM tg_users WHERE bot_id=? AND chat_id=?'); $s->execute([(int)$bot['id'], $chat]);
    $u = $s->fetch(PDO::FETCH_ASSOC);
    if (!$u) return;
    botEvent($db, $bot, 'sale', "🛒 فروش موفق\nمبلغ: " . botMoney($price) . "\nمشتری: <code>" . $chat . '</code>' . ((string)$u['username'] !== '' ? ' @' . bh((string)$u['username']) : ''));
    if ((int)$cfg['cb_on'] === 1 && (int)$cfg['cb_pct'] > 0) {
        $amt = (int)floor($price * (int)$cfg['cb_pct'] / 100);
        if ((int)$cfg['cb_max'] > 0) $amt = min($amt, (int)$cfg['cb_max']);
        if ($amt > 0 && botWalletAdd($db, $bot, (int)$u['id'], $amt, 'cashback') !== null) botSay($db, $bot, $chat, '💰 کش‌بک خرید: ' . botMoney($amt) . ' به کیف پول شما اضافه شد.');
    }
    if ((int)$cfg['ref_on'] === 1 && (int)$cfg['ref_amt'] > 0 && (int)$u['ref_by'] > 0 && (int)$u['ref_paid'] === 0) {
        $m = $db->prepare('UPDATE tg_users SET ref_paid=1 WHERE id=? AND bot_id=? AND ref_paid=0'); $m->execute([(int)$u['id'], (int)$bot['id']]);
        if ($m->rowCount() === 1) {
            $iv = $db->prepare('SELECT * FROM tg_users WHERE bot_id=? AND chat_id=?'); $iv->execute([(int)$bot['id'], (int)$u['ref_by']]);
            $inv = $iv->fetch(PDO::FETCH_ASSOC);
            if ($inv && botWalletAdd($db, $bot, (int)$inv['id'], (int)$cfg['ref_amt'], 'referral') !== null)
                botSay($db, $bot, (int)$inv['chat_id'], '🎉 دوست دعوت‌شده‌ی شما خرید کرد؛ ' . botMoney((int)$cfg['ref_amt']) . ' به کیف پول شما اضافه شد.');
        }
    }
}
function botWalletView(PDO $db, array $bot, array $cfg, array $u): void {
    $chat = (int)$u['chat_id'];
    $txt = 'موجودی کیف پول: <b>' . botMoney(botBalance($db, (int)$u['id'], (int)$bot['id'])) . '</b>';
    if ((int)$cfg['cb_on'] === 1 && (int)$cfg['cb_pct'] > 0) $txt .= "\n\n💰 کش‌بک: " . (int)$cfg['cb_pct'] . '٪ از هر خرید به کیف پول شما برمی‌گردد.';
    if ((int)$cfg['promo_on'] === 1 && (int)$cfg['promo_pct'] > 0) $txt .= "\n🏷 تخفیف فعال روی همه‌ی پلن‌ها: " . (int)$cfg['promo_pct'] . '٪';
    if ((int)$cfg['ref_on'] === 1 && (int)$cfg['ref_amt'] > 0 && (string)$bot['bot_username'] !== '')
        $txt .= "\n\n🎉 دعوت دوستان: با اولین خریدِ هر دوستی که با لینک شما وارد شود، " . botMoney((int)$cfg['ref_amt']) . " به کیف پول شما اضافه می‌شود.\nلینک شما:\n" . bh('https://t.me/' . $bot['bot_username'] . '?start=ref_' . $chat);
    $kb = [];
    if ((int)$cfg['topup_on'] === 1) $kb[] = [botAB('💳 شارژ کیف پول', 'm:topup', 'success')];
    $kb[] = [botAB('📒 تراکنش‌های من', 'm:txs'), botAB('🧾 سفارش‌های من', 'm:ord')];
    $kb[] = [botBL($cfg, 'back', ['callback_data' => 'm:home'])];
    botSay($db, $bot, $chat, $txt, $kb);
}

// ------------------------------------------------------------------ ساخت حساب
function botHostDomain(PDO $db): string {
    $h = strtolower((string)parse_url(payPublicBase($db), PHP_URL_HOST));
    return preg_match('/^[a-z0-9.\-]+\.[a-z]{2,}$/', $h) ? $h : 'example.com';
}
function botGenEmail(PDO $db, array $cfg, string $pfx): string {
    $dom = $cfg['email_domain'] !== '' ? (string)$cfg['email_domain'] : botHostDomain($db);
    for ($i = 0; $i < 8; $i++) {
        $e = $pfx . bin2hex(random_bytes(4)) . '@' . $dom;
        $q = $db->prepare('SELECT 1 FROM accounts WHERE email=?'); $q->execute([$e]);
        if (!$q->fetchColumn()) return $e;
    }
    throw new RuntimeException('email generation failed');
}
function botGenPass(): string {
    $al = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789'; $p = '';
    for ($i = 0; $i < 10; $i++) $p .= $al[random_int(0, strlen($al) - 1)];
    return $p;
}
/** باید داخل botTry صدا زده شود؛ فقط سرویسی ساخته می‌شود که مدیر برای این نماینده فعال کرده */
function botMakeAccount(PDO $db, array $agent, array $cfg, float $gb, int $days, string $dev, string $pfx): array {
    $ids = array_values(array_unique(array_map('intval', (array)($cfg['grps'] ?? [])))); if (!$ids && (int)($cfg['grp'] ?? 0) > 0) $ids = [(int)$cfg['grp']];
    $gl = []; foreach ($ids as $gid) { $x = botGroupAllowed($db, $agent, $gid); if ($x) $gl[] = $x; }
    $g = $gl[0] ?? null; $ag = $agent;
    if ($ids) {
        if (!$g) fail('سرویس ربات تنظیم نشده یا دیگر برای شما فعال نیست', 'The bot service is not set or no longer enabled for you', 403);
        $panelId = pickPanelId($db, $agent, (int)$g['panel_id']); $svc = 0;
        $pt = (string)(pnRow($db, $panelId)['type'] ?? '');
        if (!pnSvcOptional($pt)) { // پنل‌هایی که سرویس پنلی لازم دارند (مثل Rebecca): اولین سرویس مجازِ نماینده روی همین پنل
            if (botIsAdminOwner($agent)) { // ادمین اصلی: اولین سرویسِ خودِ پنل
                $ps = pn_list_services(panel($db, $panelId)); // botMakeAccount از قبل داخل botTry اجرا می‌شود؛ botTry تو‌در‌تو پرچم استثنا را خاموش می‌کند
                $al = !empty($ps['ok']) ? array_values(array_map(fn($x) => (int)$x['id'], (array)$ps['services'])) : [];
                if (!$al) fail('روی این پنل سرویسی پیدا نشد', 'No service found on this panel', 400);
            } else $al = agentAllowedServices($agent, $panelId);
            if (!$al) fail('برای این پنل، سرویس مجازی برای شما تعریف نشده است', 'No panel service is allowed for you on this panel', 403);
            $svc = (int)$al[0];
        } else $ag['agent_services'] = ''; // سرویس را مدیر صریحاً فعال کرده؛ محدودیت قدیمی «سرویس مجاز» مانع نشود
    } else {
        $panelId = pickPanelId($db, $agent, (int)$cfg['panel']); $svc = (int)$cfg['svc'];
        if ($svc <= 0 || !botSvcAllowed($db, $agent, $panelId, $svc))
            fail('سرویس ربات تنظیم نشده یا دیگر برای شما فعال نیست', 'The bot service is not set or no longer enabled for you', 403);
    }
    $email = botGenEmail($db, $cfg, $pfx); $pass = botGenPass();
    createUserAccount($db, $ag, $email, $pass, $svc, $gb, $days, pickMaxDev($dev === '' ? null : $dev), $panelId);
    $q = $db->prepare('SELECT id FROM accounts WHERE email=?'); $q->execute([$email]);
    $id = (int)$q->fetchColumn();
    if ($gl && $id > 0) { $ins = $db->prepare('INSERT OR IGNORE INTO account_services (account_id, group_id) VALUES (?,?)'); foreach ($gl as $x) if ((int)$x['panel_id'] === (int)$g['panel_id']) $ins->execute([$id, (int)$x['id']]); }
    return ['email' => $email, 'pass' => $pass, 'id' => $id];
}
function botRecordAcct(PDO $db, array $bot, int $chat, int $accId, string $kind): void {
    $db->prepare('INSERT INTO tg_accts (bot_id, chat_id, account_id, kind, created_at) VALUES (?,?,?,?,?)')->execute([(int)$bot['id'], $chat, $accId, $kind, time()]);
}
function botSendCreds(PDO $db, array $bot, array $cfg, int $chat, array $acc, string $kind, int $bytes, int $days): void {
    $dl = botDlUrl($db, $cfg);
    $GLOBALS['botEditCtx'] = null; // اطلاعات اکانت همیشه پیام جدید است
    $txt = '✅ ' . botTx($cfg, $kind === 'test' ? 't_test' : 't_sale') . " شما آماده است\n\n"
        . 'ایمیل: <code>' . bh($acc['email']) . "</code>\n"
        . 'رمز عبور: <code>' . bh($acc['pass']) . "</code>\n"
        . 'حجم: ' . botGb($bytes) . ' — مدت: ' . ($days > 0 ? $days . ' روز' : 'بدون انقضا') . "\n\n"
        . botTx($cfg, 'steps') . "\n\nدانلود برنامه: " . bh($dl);
    botSay($db, $bot, $chat, $txt, [[botBL($cfg, 'dl', ['url' => $dl])]]);
}

// ------------------------------------------------------------------ تست
function botGiveTest(PDO $db, array $bot, array $agent, array $cfg, array $u): void {
    $chat = (int)$u['chat_id'];
    if ((int)$cfg['t_on'] !== 1) { botSay($db, $bot, $chat, 'دریافت تست فعلاً فعال نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    $max = (int)$cfg['t_count']; // ۰ = نامحدود
    $r = $db->prepare('UPDATE tg_users SET tests_used=tests_used+1 WHERE id=? AND (CAST(? AS INTEGER)=0 OR tests_used<CAST(? AS INTEGER))');
    $r->execute([(int)$u['id'], $max, $max]);
    if ($r->rowCount() !== 1) { botSay($db, $bot, $chat, 'سهمیه‌ی تست شما تمام شده است. برای ادامه از «خرید اشتراک» استفاده کنید.', botMn($db, $bot, $cfg, $chat)); return; }
    $gb = (float)$cfg['t_gb']; $days = (int)$cfg['t_days'];
    $res = botTry(fn() => botMakeAccount($db, $agent, $cfg, $gb, $days, (string)$cfg['t_dev'], 't'));
    if (!$res['ok']) {
        $db->prepare('UPDATE tg_users SET tests_used=MAX(0, tests_used-1) WHERE id=?')->execute([(int)$u['id']]);
        botSay($db, $bot, $chat, 'ساخت تست با مشکل روبه‌رو شد؛ کمی بعد دوباره امتحان کنید یا به پشتیبانی پیام دهید.', botMn($db, $bot, $cfg, $chat));
        error_log('botGiveTest make-account failed: ' . (string)$res['err']);
        botEvent($db, $bot, 'error', '⚠️ خطا در ساخت تست برای یک کاربر ربات: ' . bh($res['err']));
        return;
    }
    botRecordAcct($db, $bot, $chat, (int)$res['v']['id'], 'test');
    botSendCreds($db, $bot, $cfg, $chat, $res['v'], 'test', gbToBytes($gb), $days);
}

// ------------------------------------------------------------------ خرید
function botPlans(PDO $db, int $agId, bool $onlyActive = true): array {
    $s = $db->prepare("SELECT id, name, data_bytes, days, price, active FROM plans WHERE owner_id=? AND kind='bot'" . ($onlyActive ? ' AND active=1' : '') . ' ORDER BY price, id');
    $s->execute([$agId]);
    $rows = $s->fetchAll(PDO::FETCH_ASSOC);
    foreach ($rows as &$r) { $m = botPlanMeta($db, $agId, (int)$r['id']); $r['max_devices'] = $m['dev']; $r['is_agent'] = $m['ag']; $r['max_users'] = $m['mu']; }
    unset($r);
    return $rows;
}
/** پلنی که مدتش از پایان اعتبار نمایندگی بیشتر شود (یا بی‌انقضا باشد) ساخته نمی‌شود؛ پس به مشتری فروخته نشود */
function botPlanFits(?array $agent, array $p): bool {
    $exp = (int)($agent['agent_expire'] ?? 0); $d = (int)$p['days'];
    return $exp <= 0 || ($d > 0 && time() + $d * 86400 <= $exp);
}
function botShowPlans(PDO $db, array $bot, array $cfg, int $chat): void {
    $ag = botAgentRow($db, (int)$bot['agent_id']);
    $pl = array_values(array_filter(botPlans($db, (int)$bot['agent_id']), fn($p) => botPlanFits($ag, $p) && ($ag && botIsAdminOwner($ag) || !$p['is_agent'])));
    if (!$pl) { botSay($db, $bot, $chat, 'فعلاً پلنی برای فروش ثبت نشده است.', botMn($db, $bot, $cfg, $chat)); return; }
    $kb = [];
    foreach ($pl as $p) {
        $pr = botPrice($cfg, (int)$p['price']);
        $ex = $p['is_agent'] ? ' — ' . ((int)$p['max_users'] > 0 ? (int)$p['max_users'] . ' کاربر' : 'کاربر نامحدود') : '';
        $dv = botPlanDevText((int)$p['max_devices']);
        $kb[] = [botB($cfg, 'plan', ($p['is_agent'] ? '🤝 ' : '') . $p['name'] . ' — ' . botGb((int)$p['data_bytes']) . $ex . ($dv !== '' ? ' — ' . $dv : '') . ' — ' . botMoney($pr) . ($pr < (int)$p['price'] ? ' (تخفیف)' : ''), ['callback_data' => 'p:' . (int)$p['id']])];
    }
    $kb[] = [botBL($cfg, 'back', ['callback_data' => 'm:home'])];
    botSay($db, $bot, $chat, botTx($cfg, 'plans'), $kb);
}
/** انتخاب پلن: اگر موجودی کیف پول کافی باشد، انتخاب بین پرداخت از موجودی و کارت‌به‌کارت */
function botPlanChoose(PDO $db, array $bot, array $cfg, array $u, int $planId): void {
    $chat = (int)$u['chat_id'];
    $ps = $db->prepare("SELECT * FROM plans WHERE id=? AND owner_id=? AND kind='bot' AND active=1"); $ps->execute([$planId, (int)$bot['agent_id']]);
    $pl = $ps->fetch(PDO::FETCH_ASSOC);
    if (!$pl) { botSay($db, $bot, $chat, 'این پلن دیگر موجود نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    if (!botPlanFits(botAgentRow($db, (int)$bot['agent_id']), $pl)) { botSay($db, $bot, $chat, 'این پلن فعلاً قابل خرید نیست؛ لطفاً با پشتیبانی تماس بگیرید.', botMn($db, $bot, $cfg, $chat)); return; }
    if (!botPlanSellable($db, (int)$bot['agent_id'], $planId)) { botSay($db, $bot, $chat, 'این پلن دیگر موجود نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    $price = botPrice($cfg, (int)$pl['price']); $bal = botBalance($db, (int)$u['id'], (int)$bot['id']);
    $spec = botPlanSpecText((string)$pl['name'], (int)$pl['data_bytes'], (int)$pl['days'], botPlanMeta($db, (int)$bot['agent_id'], $planId));
    $gwRows = botGwRows($db, (int)$bot['agent_id'], $price, 'gp:' . $planId);
    if ($gwRows) { // درگاه آنلاین فعال است: انتخاب بین موجودی / کارت‌به‌کارت / درگاه
        $kb = [];
        if ($bal >= $price) $kb[] = [botBL($cfg, 'wpay', ['callback_data' => 'wp:' . $planId])];
        if (botHasCards($db, (int)$bot['agent_id'], $price)) $kb[] = [botBL($cfg, 'cpay', ['callback_data' => 'cp:' . $planId])];
        $kb = array_merge($kb, $gwRows, [[botAB('🏷 کد تخفیف دارم', 'cq:' . $planId)], [botBL($cfg, 'back', ['callback_data' => 'm:buy'])]]);
        botSay($db, $bot, $chat, $spec . "\nمبلغ: <b>" . botMoney($price) . "</b>\nموجودی کیف پول شما: " . botMoney($bal) . "\n\nروش پرداخت را انتخاب کنید:", $kb);
        return;
    }
    if ($bal >= $price) {
        botSay($db, $bot, $chat, $spec . "\nمبلغ: <b>" . botMoney($price) . "</b>\nموجودی کیف پول شما: " . botMoney($bal) . "\n\nروش پرداخت را انتخاب کنید:",
            [[botBL($cfg, 'wpay', ['callback_data' => 'wp:' . $planId]), botBL($cfg, 'cpay', ['callback_data' => 'cp:' . $planId])], [botAB('🏷 کد تخفیف دارم', 'cq:' . $planId)], [botBL($cfg, 'back', ['callback_data' => 'm:buy'])]]);
        return;
    }
    botStartOrder($db, $bot, $cfg, $u, $planId);
}
/** «کد تخفیف دارم»: ورودی بعدیِ کاربر (state=coupon، state_val=شناسه‌ی پلن) به‌عنوان کد خوانده می‌شود */
function botCouponAsk(PDO $db, array $bot, array $cfg, array $u, int $planId): void {
    $chat = (int)$u['chat_id'];
    $ps = $db->prepare("SELECT id FROM plans WHERE id=? AND owner_id=? AND kind='bot' AND active=1"); $ps->execute([$planId, (int)$bot['agent_id']]);
    if (!$ps->fetchColumn()) { botSay($db, $bot, $chat, 'این پلن دیگر موجود نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    botState($db, $u, 'coupon', $planId);
    botSay($db, $bot, $chat, 'کد تخفیف خود را بفرستید:', [[botBL($cfg, 'back', ['callback_data' => 'p:' . $planId])]]);
}
/** دریافت کد: اگر معتبر بود و موجودی کیف پول برای قیمت جدید کافی باشد انتخاب روش پرداخت، وگرنه مستقیم سفارش کارت‌به‌کارت با قیمت جدید (مصرف کوپن در لحظه‌ی پرداخت/ثبت سفارش انجام می‌شود) */
function botCouponText(PDO $db, array $bot, array $cfg, array $u, string $text): void {
    $chat = (int)$u['chat_id']; $planId = (int)$u['state_val'];
    botState($db, $u, '');
    $ps = $db->prepare("SELECT * FROM plans WHERE id=? AND owner_id=? AND kind='bot' AND active=1"); $ps->execute([$planId, (int)$bot['agent_id']]);
    $pl = $ps->fetch(PDO::FETCH_ASSOC);
    if (!$pl) { botSay($db, $bot, $chat, 'این پلن دیگر موجود نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    $base = botPrice($cfg, (int)$pl['price']);
    $r = botCouponPreview($db, $bot, $u, $text, $base);
    if (!$r['ok']) {
        $ao = $db->prepare("SELECT id, receipt_file FROM tg_orders WHERE bot_id=? AND chat_id=? AND status='awaiting_receipt' AND COALESCE(kind,'')<>'topup' ORDER BY id DESC LIMIT 1"); $ao->execute([(int)$bot['id'], $chat]);
        $o = $ao->fetch(PDO::FETCH_ASSOC); // اگر سفارشِ در انتظار رسید دارد، ورودی بعدی‌اش دوباره رسید/شماره پیگیری همان سفارش باشد
        if ($o) botState($db, $u, (string)$o['receipt_file'] !== '' ? 'track' : 'receipt', (int)$o['id']);
        botSay($db, $bot, $chat, '⚠️ ' . bh($r['msg']), [[botAB('🏷 دوباره کد بفرستم', 'cq:' . $planId)], [botBL($cfg, 'back', ['callback_data' => 'p:' . $planId])]]); return; }
    $code = $r['code']; $bal = botBalance($db, (int)$u['id'], (int)$bot['id']);
    if ($bal < $r['price']) { botStartOrder($db, $bot, $cfg, $u, $planId, $code); return; }
    botSay($db, $bot, $chat, 'پلن <b>' . bh((string)$pl['name']) . "</b>\nقیمت: " . botMoney($base) . "\n🏷 کد <code>" . bh($code) . '</code>: −' . botMoney($r['discount'])
        . "\nمبلغ نهایی: <b>" . botMoney($r['price']) . "</b>\nموجودی کیف پول شما: " . botMoney($bal) . "\n\nروش پرداخت را انتخاب کنید:",
        [[botBL($cfg, 'wpay', ['callback_data' => 'wp:' . $planId . ':' . $code]), botBL($cfg, 'cpay', ['callback_data' => 'cp:' . $planId . ':' . $code])], [botBL($cfg, 'back', ['callback_data' => 'p:' . $planId])]]);
}
function botBuyWallet(PDO $db, array $bot, array $agent, array $cfg, array $u, int $planId, string $code = ''): void {
    $chat = (int)$u['chat_id'];
    $ps = $db->prepare("SELECT * FROM plans WHERE id=? AND owner_id=? AND kind='bot' AND active=1"); $ps->execute([$planId, (int)$bot['agent_id']]);
    $pl = $ps->fetch(PDO::FETCH_ASSOC);
    if (!$pl || !botPlanSellable($db, (int)$bot['agent_id'], $planId)) { botSay($db, $bot, $chat, 'این پلن دیگر موجود نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    $base = botPrice($cfg, (int)$pl['price']); $price = $base; $cpn = null;
    if ($code !== '') {
        $cpn = botCouponApply($db, $bot, $u, $code, $base);
        if (!$cpn['ok']) { botSay($db, $bot, $chat, '⚠️ ' . bh($cpn['msg']), [[botBL($cfg, 'back', ['callback_data' => 'p:' . $planId])]]); return; }
        $price = $cpn['price'];
    }
    $relCoupon = function () use ($db, $bot, &$cpn): void { if ($cpn) botCouponRelease($db, $bot, (int)$cpn['use_id']); };
    if (botWalletAdd($db, $bot, (int)$u['id'], -$price, 'buy plan ' . $planId) === null) { $relCoupon(); botSay($db, $bot, $chat, 'موجودی کیف پول کافی نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    $bytes = (int)$pl['data_bytes']; $days = (int)$pl['days'];
    $meta = botPlanMeta($db, (int)$bot['agent_id'], $planId);
    $sn = ['bytes' => $bytes, 'days' => $days, 'dev' => $meta['dev'], 'mu' => $meta['mu']];
    $res = botTry(fn() => $meta['ag'] ? botSellAgent($db, $cfg, $sn) : botMakeAccount($db, $agent, $cfg, $bytes / 1073741824, $days, botDevStr($meta['dev'], $cfg), 'u'));
    if (!$res['ok']) {
        botWalletAdd($db, $bot, (int)$u['id'], $price, 'refund');
        $relCoupon();
        botSay($db, $bot, $chat, 'ساخت اکانت با مشکل روبه‌رو شد؛ مبلغ به کیف پول شما برگشت.', botMn($db, $bot, $cfg, $chat));
        error_log('botBuyWallet make-account failed: ' . (string)$res['err']);
        botEvent($db, $bot, 'error', '⚠️ خطا در ساخت اکانت (پرداخت از موجودی): ' . bh($res['err']));
        return;
    }
    $snap = json_encode(['id' => $planId, 'name' => (string)$pl['name'], 'bytes' => $bytes, 'days' => $days, 'price' => $price, 'base' => $base, 'coupon' => $cpn ? $cpn['code'] : '', 'dev' => $meta['dev'], 'ag' => $meta['ag'], 'mu' => $meta['mu']], JSON_UNESCAPED_UNICODE);
    $now = time();
    $db->prepare("INSERT INTO tg_orders (bot_id, agent_id, chat_id, plan_snapshot, price, status, tracking, account_id, coupon_id, discount, created_at, updated_at) VALUES (?,?,?,?,?,'approved','wallet',?,?,?,?,?)")
       ->execute([(int)$bot['id'], (int)$bot['agent_id'], $chat, $snap, $price, (int)$res['v']['id'], $cpn ? (int)$cpn['coupon_id'] : 0, $cpn ? (int)$cpn['discount'] : 0, $now, $now]);
    if ($cpn) botCouponAttach($db, $bot, (int)$cpn['use_id'], (int)$db->lastInsertId());
    if (!$meta['ag']) botRecordAcct($db, $bot, $chat, (int)$res['v']['id'], 'sale');
    agAudit($db, (int)$agent['id'], 'bot_approve', 0, (int)$res['v']['id'], $price, 'wallet purchase chat=' . $chat);
    if ($meta['ag']) botSendAgentCreds($db, $bot, $cfg, $chat, $res['v'], $sn); else botSendCreds($db, $bot, $cfg, $chat, $res['v'], 'sale', $bytes, $days);
    botAfterSale($db, $bot, $cfg, $chat, $price);
}
function botStartOrder(PDO $db, array $bot, array $cfg, array $u, int $planId, string $code = ''): void {
    $chat = (int)$u['chat_id']; $agId = (int)$bot['agent_id']; $now = time();
    $busy = $db->prepare("SELECT 1 FROM tg_orders WHERE bot_id=? AND chat_id=? AND COALESCE(kind,'')<>'topup' AND status IN ('pending_review','approving')"); $busy->execute([(int)$bot['id'], $chat]);
    if ($busy->fetchColumn()) { botSay($db, $bot, $chat, 'سفارش قبلی شما در انتظار تأیید است؛ لطفاً منتظر بمانید.', botMn($db, $bot, $cfg, $chat)); return; }
    $ps = $db->prepare("SELECT * FROM plans WHERE id=? AND owner_id=? AND kind='bot' AND active=1"); $ps->execute([$planId, $agId]);
    $pl = $ps->fetch(PDO::FETCH_ASSOC);
    if (!$pl || !botPlanSellable($db, $agId, $planId)) { botSay($db, $bot, $chat, 'این پلن دیگر موجود نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    $meta = botPlanMeta($db, $agId, $planId);
    $base = botPrice($cfg, (int)$pl['price']); $price = $base; $pv = null;
    if ($code !== '') { // اول فقط بررسی (کارت‌ها بر اساس قیمت نهایی انتخاب می‌شوند)؛ مصرف بعد از اطمینان از وجود کارت
        $pv = botCouponPreview($db, $bot, $u, $code, $base);
        if (!$pv['ok']) { botSay($db, $bot, $chat, '⚠️ ' . bh($pv['msg']), [[botBL($cfg, 'back', ['callback_data' => 'p:' . $planId])]]); return; }
        $price = $pv['price'];
    }
    $cards = botPayCards($db, $agId, $price, $cfg, (int)$bot['id']);
    if (!$cards) {
        botSay($db, $bot, $chat, 'روش پرداختی برای این مبلغ تنظیم نشده است؛ به پشتیبانی پیام دهید.', botMn($db, $bot, $cfg, $chat));
        botEvent($db, $bot, 'error', '⚠️ یک کاربر ربات خواست خرید کند ولی کارت فعالی برای این مبلغ در «کارت‌ها» ندارید.');
        return;
    }
    $cpn = null;
    if ($pv) {
        $cpn = botCouponApply($db, $bot, $u, $code, $base);
        if (!$cpn['ok'] || (int)$cpn['price'] !== $price) {
            if ($cpn['ok']) botCouponRelease($db, $bot, (int)$cpn['use_id']); // بین بررسی و مصرف کد تغییر کرده؛ با قیمت تازه دوباره امتحان شود
            botSay($db, $bot, $chat, '⚠️ ' . bh($cpn['ok'] ? 'کد تخفیف تغییر کرده است؛ دوباره امتحان کنید.' : $cpn['msg']), [[botBL($cfg, 'back', ['callback_data' => 'p:' . $planId])]]);
            return;
        }
    }
    botCancelAwaiting($db, (int)$bot['id'], $chat);
    $snap = json_encode(['id' => (int)$pl['id'], 'name' => (string)$pl['name'], 'bytes' => (int)$pl['data_bytes'], 'days' => (int)$pl['days'], 'price' => $price, 'base' => $base, 'coupon' => $cpn ? $cpn['code'] : '', 'dev' => $meta['dev'], 'ag' => $meta['ag'], 'mu' => $meta['mu']], JSON_UNESCAPED_UNICODE);
    $csn = json_encode(array_map(fn($c) => ['n' => (string)$c['card_number'], 'h' => (string)$c['card_holder']], $cards), JSON_UNESCAPED_UNICODE);
    try {
        $db->prepare('INSERT INTO tg_orders (bot_id, agent_id, chat_id, plan_snapshot, card_snapshot, price, status, coupon_id, discount, created_at, updated_at) VALUES (?,?,?,?,?,?,\'awaiting_receipt\',?,?,?,?)')
           ->execute([(int)$bot['id'], $agId, $chat, $snap, $csn, $price, $cpn ? (int)$cpn['coupon_id'] : 0, $cpn ? (int)$cpn['discount'] : 0, $now, $now]);
    } catch (Throwable $e) {
        if ($cpn) botCouponRelease($db, $bot, (int)$cpn['use_id']);
        throw $e;
    }
    $oid = (int)$db->lastInsertId();
    if ($cpn) botCouponAttach($db, $bot, (int)$cpn['use_id'], $oid);
    botState($db, $u, 'receipt', $oid);
    $txt = botPlanSpecText((string)$pl['name'], (int)$pl['data_bytes'], (int)$pl['days'], $meta)
         . ($cpn ? "\nقیمت: " . botMoney($base) . "\n🏷 کد <code>" . bh((string)$cpn['code']) . '</code>: −' . botMoney((int)$cpn['discount']) : '')
         . "\nمبلغ: <b>" . botMoney($price) . "</b>\n\nمبلغ را به یکی از کارت‌های زیر واریز کنید:\n";
    foreach ($cards as $c) $txt .= "\n<code>" . bh((string)$c['card_number']) . '</code>' . "\nبه نام: " . bh((string)$c['card_holder']) . "\n";
    $txt .= "\n" . botTx($cfg, 'paynote');
    $kb = [];
    if (!$cpn) $kb[] = [botAB('🏷 کد تخفیف دارم', 'cq:' . (int)$pl['id'])];
    $kb[] = [botBL($cfg, 'cancel', ['callback_data' => 'x:' . $oid])];
    botSay($db, $bot, $chat, $txt, $kb);
}
function botReceipt(PDO $db, array $bot, array $cfg, array $u, array $msg): void {
    $chat = (int)$u['chat_id']; $oid = (int)$u['state_val'];
    $os = $db->prepare("SELECT * FROM tg_orders WHERE id=? AND bot_id=? AND chat_id=? AND status='awaiting_receipt'"); $os->execute([$oid, (int)$bot['id'], $chat]);
    $o = $os->fetch(PDO::FETCH_ASSOC);
    if (!$o) { botState($db, $u, ''); botSay($db, $bot, $chat, 'سفارش فعالی پیدا نشد.', botMn($db, $bot, $cfg, $chat)); return; }
    $fid = ''; $size = 0;
    if (!empty($msg['photo']) && is_array($msg['photo'])) { $ph = end($msg['photo']); $fid = (string)($ph['file_id'] ?? ''); $size = (int)($ph['file_size'] ?? 0); }
    elseif (!empty($msg['document']) && strpos((string)($msg['document']['mime_type'] ?? ''), 'image/') === 0) { $fid = (string)$msg['document']['file_id']; $size = (int)($msg['document']['file_size'] ?? 0); }
    if ($fid === '') { botSay($db, $bot, $chat, 'فقط عکس رسید قابل قبول است.'); return; }
    if ($size > RECEIPT_MAX_BYTES) { botSay($db, $bot, $chat, 'حجم عکس زیاد است (حداکثر ' . (int)(RECEIPT_MAX_BYTES / 1048576) . ' مگابایت).'); return; }
    $g = botTg($db, $bot, 'getFile', ['file_id' => $fid]);
    $fp = (string)($g['result']['file_path'] ?? '');
    if (empty($g['ok']) || $fp === '') { botSay($db, $bot, $chat, 'دریافت عکس ناموفق بود؛ دوباره بفرستید.'); return; }
    payReceiptDir();
    $tmp = RECEIPT_DIR . '/tmp_' . bin2hex(random_bytes(8));
    if (!tgDownload($db, botTok($bot), $fp, $tmp)) { botSay($db, $bot, $chat, 'دریافت عکس ناموفق بود؛ دوباره بفرستید.'); return; }
    $info = @getimagesize($tmp);
    $ext = [IMAGETYPE_JPEG => 'jpg', IMAGETYPE_PNG => 'png', IMAGETYPE_GIF => 'gif', IMAGETYPE_WEBP => 'webp'][$info[2] ?? 0] ?? '';
    if ($ext === '') { @unlink($tmp); botSay($db, $bot, $chat, 'فقط عکس (JPG/PNG/WebP) قابل قبول است.'); return; }
    $hash = hash_file('sha256', $tmp);
    $d1 = $db->prepare("SELECT 1 FROM tg_orders WHERE receipt_hash=?"); $d1->execute([$hash]);
    $d2 = $db->prepare("SELECT 1 FROM payments WHERE receipt_hash=?"); $d2->execute([$hash]);
    if ($d1->fetchColumn() || $d2->fetchColumn()) { @unlink($tmp); botSay($db, $bot, $chat, 'این رسید قبلاً ثبت شده است؛ رسید جدید بفرستید.'); return; }
    $name = bin2hex(random_bytes(16)) . '.' . $ext;
    if (!@rename($tmp, RECEIPT_DIR . '/' . $name)) { @unlink($tmp); botSay($db, $bot, $chat, 'ذخیره‌ی رسید ناموفق بود؛ دوباره بفرستید.'); return; }
    @chmod(RECEIPT_DIR . '/' . $name, 0640);
    try {
        $up = $db->prepare("UPDATE tg_orders SET receipt_file=?, receipt_hash=?, updated_at=? WHERE id=? AND status='awaiting_receipt'");
        $up->execute([$name, $hash, time(), $oid]);
        $okUp = $up->rowCount() === 1;
    } catch (PDOException $e) { $okUp = false; }
    if (!$okUp) { @unlink(RECEIPT_DIR . '/' . $name); botSay($db, $bot, $chat, 'این رسید قبلاً ثبت شده یا سفارش بسته شده است.'); return; }
    botState($db, $u, 'track', $oid);
    botSay($db, $bot, $chat, 'رسید دریافت شد. حالا <b>شماره پیگیری</b> تراکنش را (فقط عدد) بفرستید.');
}
function botTracking(PDO $db, array $bot, array $cfg, array $u, string $text): void {
    $chat = (int)$u['chat_id']; $oid = (int)$u['state_val'];
    $t = preg_replace('/\D/', '', payDigits($text));
    if (!preg_match('/^\d{6,40}$/', (string)$t)) { botSay($db, $bot, $chat, 'شماره پیگیری باید فقط عدد و حداقل ۶ رقم باشد.'); return; }
    $d1 = $db->prepare("SELECT 1 FROM tg_orders WHERE agent_id=? AND tracking=? AND id<>? AND status IN ('pending_review','approving','approved')"); $d1->execute([(int)$bot['agent_id'], $t, $oid]);
    $d2 = $db->prepare("SELECT 1 FROM payments WHERE owner_id=? AND tracking=? AND status IN ('pending_review','approved','flagged')"); $d2->execute([(int)$bot['agent_id'], $t]);
    if ($d1->fetchColumn() || $d2->fetchColumn()) { botSay($db, $bot, $chat, 'این شماره پیگیری قبلاً ثبت شده است.'); return; }
    $up = $db->prepare("UPDATE tg_orders SET tracking=?, status='pending_review', updated_at=? WHERE id=? AND bot_id=? AND chat_id=? AND status='awaiting_receipt' AND receipt_file<>''");
    $up->execute([$t, time(), $oid, (int)$bot['id'], $chat]);
    botState($db, $u, '');
    if ($up->rowCount() !== 1) { botSay($db, $bot, $chat, 'سفارش پیدا نشد؛ دوباره از «خرید اشتراک» شروع کنید.', botMn($db, $bot, $cfg, $chat)); return; }
    $kq = $db->prepare('SELECT kind FROM tg_orders WHERE id=? AND bot_id=?'); $kq->execute([$oid, (int)$bot['id']]);
    botSay($db, $bot, $chat, (string)$kq->fetchColumn() === 'topup' ? 'درخواست شارژ ثبت شد؛ پس از تأیید، مبلغ به کیف پول شما اضافه می‌شود.' : botTx($cfg, 'ordered'), botMn($db, $bot, $cfg, $chat));
    botNotifyOrder($db, $bot, $oid);
}
function botNotifyOrder(PDO $db, array $bot, int $oid): void {
    $cfg = botCfg($db, (int)$bot['agent_id']);
    $os = $db->prepare('SELECT * FROM tg_orders WHERE id=? AND bot_id=?'); $os->execute([$oid, (int)$bot['id']]);
    $o = $os->fetch(PDO::FETCH_ASSOC);
    if (!$o) return;
    $pl = json_decode((string)$o['plan_snapshot'], true) ?: [];
    $kind = (string)($o['kind'] ?? 'plan');
    if ($kind === 'topup') $title = "درخواست شارژ کیف پول #{$oid}";
    elseif ($kind === 'renew') $title = "درخواست تمدید حساب #{$oid}\nحساب/پلن: " . bh((string)($pl['name'] ?? ''));
    elseif ($kind === 'traffic') $title = "درخواست حجم اضافه #{$oid}\nحساب/بسته: " . bh((string)($pl['name'] ?? ''));
    else $title = "سفارش جدید #{$oid}\nپلن: " . bh((string)($pl['name'] ?? ''));
    $cap = $title . "\nمبلغ: " . botMoney((int)$o['price']) . "\nشماره پیگیری: <code>" . bh((string)$o['tracking']) . '</code>';
    if ((int)($o['coupon_id'] ?? 0) > 0) {
        $cq = $db->prepare('SELECT code FROM tg_coupons WHERE id=? AND bot_id=?'); $cq->execute([(int)$o['coupon_id'], (int)$bot['id']]);
        $cc = (string)$cq->fetchColumn();
        $cap .= "\n🏷 کد تخفیف: " . ($cc !== '' ? '<code>' . bh($cc) . '</code> ' : '') . '(−' . botMoney((int)$o['discount']) . ')';
    }
    $kb = [[botBL($cfg, 'apr', ['callback_data' => 'oa:' . $oid]), botBL($cfg, 'rej', ['callback_data' => 'or:' . $oid])]];
    botEvent($db, $bot, 'order_new', $cap, $kb, RECEIPT_DIR . '/' . basename((string)$o['receipt_file']));
}

// ------------------------------------------------------------------ تأیید / رد سفارش (هم از تلگرام، هم از پورتال)
function botOrderApprove(PDO $db, array $bot, array $agent, int $oid, string $by, int $actorChat = 0): array {
    $botId = (int)$bot['id']; $agentId = (int)$bot['agent_id'];
    if ($oid <= 0 || (int)($agent['id'] ?? 0) !== $agentId) return ['ok' => false, 'msg' => 'سفارش پیدا نشد'];
    $kq = $db->prepare('SELECT kind FROM tg_orders WHERE id=? AND bot_id=? AND agent_id=?');
    $kq->execute([$oid, $botId, $agentId]);
    $kind = $kq->fetchColumn();
    if ($kind === false) return ['ok' => false, 'msg' => 'سفارش پیدا نشد'];
    if ((string)$kind === 'topup') return botTopupApprove($db, $bot, $oid, $by, $actorChat);

    // قفل اتمیک مشترک برای همه‌ی سفارش‌ها؛ تأیید هم‌زمان فقط یک‌بار برنده می‌شود.
    $lock = $db->prepare("UPDATE tg_orders SET status='approving', updated_at=? WHERE id=? AND bot_id=? AND agent_id=? AND status='pending_review'");
    $lock->execute([time(), $oid, $botId, $agentId]);
    if ($lock->rowCount() !== 1) return ['ok' => false, 'msg' => 'این سفارش قبلاً بررسی شده است'];
    $os = $db->prepare("SELECT * FROM tg_orders WHERE id=? AND bot_id=? AND agent_id=? AND status='approving'");
    $os->execute([$oid, $botId, $agentId]);
    $o = $os->fetch(PDO::FETCH_ASSOC);
    if (!$o) {
        $db->prepare("UPDATE tg_orders SET status='pending_review', updated_at=? WHERE id=? AND bot_id=? AND agent_id=? AND status='approving'")
            ->execute([time(), $oid, $botId, $agentId]);
        return ['ok' => false, 'msg' => 'سفارش پیدا نشد'];
    }
    $cfg = botCfg($db, $agentId);
    $pl = json_decode((string)$o['plan_snapshot'], true);
    if (!is_array($pl)) $pl = [];
    $chat = (int)$o['chat_id'];

    if (in_array((string)$kind, ['renew', 'traffic'], true)) {
        $accId = (int)($o['ref_account_id'] ?? 0);
        $snapshotAcc = (int)($pl['account_id'] ?? 0);
        if ($accId <= 0 || ($snapshotAcc > 0 && $snapshotAcc !== $accId)) {
            $db->prepare("UPDATE tg_orders SET status='pending_review', updated_at=? WHERE id=? AND bot_id=? AND agent_id=? AND status='approving'")
                ->execute([time(), $oid, $botId, $agentId]);
            return ['ok' => false, 'msg' => 'حساب سفارش معتبر نیست؛ سفارش برای بررسی دوباره بازگردانده شد'];
        }
        $done = botTry(fn() => botApplyAccountService($db, $bot, $agent, $chat, $accId, (string)$kind, $pl));
        $result = ($done['ok'] && is_array($done['v'] ?? null)) ? $done['v'] : ['ok' => false, 'msg' => 'عملیات پنل ناموفق بود.'];
        if (empty($result['ok'])) {
            $db->prepare("UPDATE tg_orders SET status='pending_review', updated_at=? WHERE id=? AND bot_id=? AND agent_id=? AND status='approving'")
                ->execute([time(), $oid, $botId, $agentId]);
            return ['ok' => false, 'msg' => (string)($result['msg'] ?? 'عملیات پنل ناموفق بود؛ سفارش برای بررسی دوباره بازگردانده شد')];
        }
        $up = $db->prepare("UPDATE tg_orders SET status='approved', updated_at=? WHERE id=? AND bot_id=? AND agent_id=? AND status='approving'");
        $up->execute([time(), $oid, $botId, $agentId]);
        if ($up->rowCount() !== 1) return ['ok' => false, 'msg' => 'وضعیت سفارش تغییر کرده است؛ با پشتیبانی تماس بگیرید'];
        agAudit($db, $agentId, 'bot_' . (string)$kind, 0, $accId, (int)$o['price'], 'card order=' . $oid . ' by=' . $by);
        botAudit($db, $bot, $actorChat, 'order_approve', 'order:' . $oid, ['by' => $by, 'kind' => (string)$kind, 'price' => (int)$o['price'], 'account_id' => $accId]);
        botAfterSale($db, $bot, $cfg, $chat, (int)$o['price']);
        $label = (string)$kind === 'renew' ? '✅ حساب با موفقیت تمدید شد.' : '✅ حجم اضافه با موفقیت ثبت شد.';
        botSay($db, $bot, $chat, $label, [[botAB('جزئیات حساب', 'ac:' . $accId, 'success')], [botBL($cfg, 'back', ['callback_data' => 'm:home'])]]);
        return ['ok' => true, 'msg' => 'تأیید شد'];
    }

    if ((string)$kind !== 'plan') {
        $db->prepare("UPDATE tg_orders SET status='pending_review', updated_at=? WHERE id=? AND bot_id=? AND agent_id=? AND status='approving'")
            ->execute([time(), $oid, $botId, $agentId]);
        return ['ok' => false, 'msg' => 'نوع سفارش معتبر نیست'];
    }
    $bytes = (int)($pl['bytes'] ?? 0); $days = (int)($pl['days'] ?? 0); $isAg = !empty($pl['ag']);
    $res = $isAg && !botIsAdminOwner($agent) ? ['ok' => false, 'err' => 'پلن نمایندگی فقط در ربات مدیر اصلی فروخته می‌شود']
        : botTry(fn() => $isAg ? botSellAgent($db, $cfg, $pl) : botMakeAccount($db, $agent, $cfg, $bytes / 1073741824, $days, botDevStr((int)($pl['dev'] ?? -1), $cfg), 'u'));
    if (!$res['ok'] || !is_array($res['v'] ?? null)) {
        $db->prepare("UPDATE tg_orders SET status='pending_review', updated_at=? WHERE id=? AND bot_id=? AND agent_id=? AND status='approving'")
            ->execute([time(), $oid, $botId, $agentId]);
        $why = (string)($res['err'] ?? '');
        error_log('botOrderApprove #' . $oid . ' make-account failed: ' . $why);
        return ['ok' => false, 'msg' => 'ساخت حساب ناموفق بود' . ($why !== '' ? ': ' . $why : '') . ' — سفارش برای بررسی دوباره بازگردانده شد'];
    }
    $up = $db->prepare("UPDATE tg_orders SET status='approved', account_id=?, updated_at=? WHERE id=? AND bot_id=? AND agent_id=? AND status='approving'");
    $up->execute([(int)$res['v']['id'], time(), $oid, $botId, $agentId]);
    if ($up->rowCount() !== 1) return ['ok' => false, 'msg' => 'وضعیت سفارش تغییر کرده است؛ با پشتیبانی تماس بگیرید'];
    if (!$isAg) botRecordAcct($db, $bot, $chat, (int)$res['v']['id'], 'sale');
    agAudit($db, $agentId, 'bot_approve', 0, (int)$res['v']['id'], (int)$o['price'], 'order=' . $oid . ' by=' . $by);
    botAudit($db, $bot, $actorChat, 'order_approve', 'order:' . $oid, ['by' => $by, 'price' => (int)$o['price']]);
    if ($isAg) botSendAgentCreds($db, $bot, $cfg, $chat, $res['v'], $pl); else botSendCreds($db, $bot, $cfg, $chat, $res['v'], 'sale', $bytes, $days);
    botAfterSale($db, $bot, $cfg, $chat, (int)$o['price']);
    return ['ok' => true, 'msg' => 'تأیید شد'];
}
function botOrderReject(PDO $db, array $bot, array $agent, int $oid, string $reason, string $by, int $actorChat = 0): array {
    if ($oid <= 0 || (int)($agent['id'] ?? 0) !== (int)$bot['agent_id']) return ['ok' => false, 'msg' => 'سفارش پیدا نشد'];
    $ex = $db->prepare('SELECT 1 FROM tg_orders WHERE id=? AND bot_id=? AND agent_id=?');
    $ex->execute([$oid, (int)$bot['id'], (int)$bot['agent_id']]);
    if (!$ex->fetchColumn()) return ['ok' => false, 'msg' => 'سفارش پیدا نشد'];
    $up = $db->prepare("UPDATE tg_orders SET status='rejected', note=?, updated_at=? WHERE id=? AND bot_id=? AND agent_id=? AND status='pending_review'");
    $up->execute([$reason, time(), $oid, (int)$bot['id'], (int)$bot['agent_id']]);
    if ($up->rowCount() !== 1) return ['ok' => false, 'msg' => 'این سفارش قبلاً بررسی شده است'];
    $os = $db->prepare('SELECT chat_id, price FROM tg_orders WHERE id=? AND bot_id=?'); $os->execute([$oid, (int)$bot['id']]);
    $o = $os->fetch(PDO::FETCH_ASSOC);
    botCouponReleaseByOrder($db, (int)$bot['id'], $oid); // رد سفارش = مصرف کوپن برمی‌گردد
    agAudit($db, (int)$agent['id'], 'bot_reject', 0, 0, (int)$o['price'], 'order=' . $oid . ' by=' . $by . ($reason !== '' ? ' ' . $reason : ''));
    botAudit($db, $bot, $actorChat, 'order_reject', 'order:' . $oid, ['by' => $by]);
    $cfg = botCfg($db, (int)$agent['id']); $chat = (int)$o['chat_id'];
    botSay($db, $bot, $chat, 'رسید شما تأیید نشد.' . ($reason !== '' ? "\nدلیل: " . bh($reason) : '') . ($cfg['support'] !== '' ? "\n\nپشتیبانی: " . botEmo(bh((string)$cfg['support'])) : ''), botMn($db, $bot, $cfg, $chat));
    return ['ok' => true, 'msg' => 'رد شد'];
}
function botOrdersList(PDO $db, int $agId, string $st): array {
    botLazy($db);
    $w = 'o.agent_id=?'; $args = [$agId];
    if ($st === 'open') $w .= " AND o.status IN ('pending_review','approving')";
    elseif ($st !== 'all') {
        if (!in_array($st, ['approved', 'rejected', 'awaiting_receipt', 'cancelled'], true)) fail('فیلتر نامعتبر', 'Invalid filter');
        $w .= ' AND o.status=?'; $args[] = $st;
    }
    $s = $db->prepare("SELECT o.*, u.username, a.email FROM tg_orders o LEFT JOIN tg_users u ON u.bot_id=o.bot_id AND u.chat_id=o.chat_id LEFT JOIN accounts a ON a.id=o.account_id WHERE $w ORDER BY o.id DESC LIMIT 100");
    $s->execute($args);
    $out = [];
    foreach ($s->fetchAll(PDO::FETCH_ASSOC) as $o) {
        $pl = json_decode((string)$o['plan_snapshot'], true) ?: [];
        $out[] = ['id' => (int)$o['id'], 'username' => (string)($o['username'] ?? ''), 'chat_id' => (string)$o['chat_id'], 'plan' => (string)($o['kind'] ?? '') === 'topup' ? 'شارژ کیف پول' : (string)($pl['name'] ?? ''), 'price' => (int)$o['price'],
                  'status' => (string)$o['status'], 'tracking' => (string)$o['tracking'], 'has_receipt' => $o['receipt_file'] !== '', 'note' => (string)$o['note'],
                  'email' => (string)($o['email'] ?? ''), 'created_at' => (int)$o['created_at']];
    }
    return $out;
}

// ------------------------------------------------------------------ حساب‌های من / رمز جدید
/** حجم برای نمایش؛ صفر = «۰ مگابایت» (برخلاف botGb که صفر را «نامحدود» نشان می‌دهد) */
function botBytes(int $b): string {
    $b = max(0, $b);
    if ($b < 1073741824) return number_format($b / 1048576, $b < 10485760 ? 1 : 0, '.', '') . ' مگابایت';
    return rtrim(rtrim(number_format($b / 1073741824, 2, '.', ''), '0'), '.') . ' گیگ';
}
/**
 * مصرف/حجم/انقضا/وضعیتِ یک حساب از پنل (همان pn_get_user و منطق usage_base که subInfo در core.php دارد، بدون خواندن لینک‌ها و بدون نوشتن در دیتابیس).
 * $acc = ردیف accounts (panel_username, panel_id, usage_base). خروجی null = پنل جواب نداد.
 * @return array{used:int,limit:int,expire:int,status:string}|null
 */
function botAcctInfo(PDO $db, array $acc): ?array {
    $r = botTry(function () use ($db, $acc): ?array {
        if (defined('BOT_TEST_MODE') && is_callable($GLOBALS['BOT_PN_USER'] ?? null)) $g = $GLOBALS['BOT_PN_USER']($acc); // فقط تست‌ها
        else {
            $pu = (string)($acc['panel_username'] ?? '');
            if ($pu === '') return null;
            $g = pn_get_user(accPanel($db, $acc), $pu);
        }
        if (empty($g['ok'])) return null;
        $d = (array)$g['data'];
        $used = (int)($d['used_traffic'] ?? 0); $lim = (int)($d['data_limit'] ?? 0); $base = (int)($acc['usage_base'] ?? 0);
        if ($base > 0 && $used >= $base) { $used -= $base; if ($lim > 0) $lim = max(0, $lim - $base); }
        return ['used' => $used, 'limit' => $lim, 'expire' => (int)($d['expire'] ?? 0), 'status' => (string)($d['status'] ?? '')];
    });
    return $r['ok'] ? $r['v'] : null;
}
function botAcctStatus(array $acc, ?array $i): string {
    if ((int)($acc['disabled'] ?? 0) === 1) return '⛔ غیرفعال';
    if (!$i) return '❔ نامشخص';
    if ($i['expire'] > 0 && $i['expire'] <= time()) return '⌛ منقضی';
    if ($i['limit'] > 0 && $i['used'] >= $i['limit']) return '📵 اتمام حجم';
    return ['active' => '✅ فعال', 'disabled' => '⛔ غیرفعال', 'limited' => '📵 اتمام حجم', 'expired' => '⌛ منقضی', 'on_hold' => '⏸ در انتظار اتصال'][$i['status']] ?? '✅ فعال';
}
/** چند خط متن: مصرف/کل، باقی‌مانده، انقضا و وضعیت */
function botAcctLines(array $acc, ?array $i): string {
    if (!$i) return "مصرف: اطلاعات مصرف الان در دسترس نیست\nوضعیت: " . botAcctStatus($acc, null);
    $left = $i['limit'] > 0 ? botBytes(max(0, $i['limit'] - $i['used'])) : 'نامحدود';
    if ($i['expire'] > 0) $exp = date('Y/m/d', $i['expire']) . ($i['expire'] > time() ? ' (' . (int)ceil(($i['expire'] - time()) / 86400) . ' روز مانده)' : ' (منقضی شده)');
    else $exp = 'بدون انقضا';
    return 'مصرف: ' . botBytes($i['used']) . ' از ' . botGb($i['limit']) . ' — باقی‌مانده: ' . $left . "\nانقضا: " . $exp . "\nوضعیت: " . botAcctStatus($acc, $i);
}
/** ثبت یک هشدارِ تلگرام؛ پاسخ ۴۰۳ کاربر را برای همین ربات مسدود می‌کند تا هشدار دیگری ارسال نشود. */
function botExpiryAlertSend(PDO $db, array $bot, array $acc, int $chat, string $kind, string $ref, string $text): string {
    $botId = (int)$bot['id']; $accountId = (int)$acc['id'];
    $q = $db->prepare('SELECT 1 FROM tg_notify_log WHERE bot_id=? AND account_id=? AND kind=? AND ref=?');
    $q->execute([$botId, $accountId, $kind, $ref]);
    if ($q->fetchColumn()) return 'seen';
    $reply = ['inline_keyboard' => [[botAB('🔄 تمدید حساب', 'rn:' . $accountId, 'success')]]];
    $r = botTg($db, $bot, 'sendMessage', ['chat_id' => $chat, 'text' => $text, 'parse_mode' => 'HTML', 'disable_web_page_preview' => 'true', 'reply_markup' => $reply]);
    if (empty($r['ok'])) {
        if ((int)($r['error_code'] ?? 0) === 403) {
            $db->prepare('UPDATE tg_users SET blocked=1 WHERE bot_id=? AND chat_id=?')->execute([$botId, $chat]);
            return 'blocked';
        }
        return 'retry';
    }
    $db->prepare('INSERT OR IGNORE INTO tg_notify_log (bot_id,account_id,kind,ref,created_at) VALUES (?,?,?,?,?)')
       ->execute([$botId, $accountId, $kind, $ref, time()]);
    return 'sent';
}
/** ادامه‌دار و زمان‌محدود: حداکثر ۲۰۰ حسابِ ثبت‌شده برای هر ربات در هر نوبت. */
function botExpiryAlertBot(PDO $db, array $bot, ?float $deadline = null): void {
    $botId = (int)$bot['id']; $agentId = (int)$bot['agent_id'];
    $deadline = $deadline ?? (isset($GLOBALS['__sched_deadline']) ? (float)$GLOBALS['__sched_deadline'] : microtime(true) + 8.0);
    $db->prepare("INSERT OR IGNORE INTO tg_counters (bot_id,name,val) VALUES (?,'expiry_cursor',0)")->execute([$botId]);
    $cfg = botCfg($db, $agentId);
    if ((int)($cfg['alerts_on'] ?? 1) !== 1) {
        $db->prepare("UPDATE tg_counters SET val=0 WHERE bot_id=? AND name='expiry_cursor'")->execute([$botId]);
        return;
    }
    $c = $db->prepare("SELECT val FROM tg_counters WHERE bot_id=? AND name='expiry_cursor'");
    $c->execute([$botId]); $cursor = max(0, (int)$c->fetchColumn());
    $own = botOwnSql($db, 'a.owner_id', $agentId);
    $fetch = function (int $after) use ($db, $botId, $agentId, $own): array {
        $q = $db->prepare("SELECT t.id AS link_id,t.account_id,t.chat_id,u.blocked,a.*
            FROM tg_accts t JOIN tg_users u ON u.bot_id=t.bot_id AND u.chat_id=t.chat_id
            JOIN accounts a ON a.id=t.account_id
            WHERE t.bot_id=? AND t.id>? AND $own AND a.role='user' AND a.disabled=0
            ORDER BY t.id ASC LIMIT 200");
        $q->execute([$botId, $after, $agentId]);
        return $q->fetchAll(PDO::FETCH_ASSOC);
    };
    $rows = $fetch($cursor);
    if (!$rows && $cursor > 0) {
        $cursor = 0;
        $db->prepare("UPDATE tg_counters SET val=0 WHERE bot_id=? AND name='expiry_cursor'")->execute([$botId]);
        $rows = $fetch(0);
    }
    if (!$rows) return;
    $processed = 0; $last = $cursor; $now = time(); $blockedChats = [];
    foreach ($rows as $acc) {
        if (microtime(true) >= $deadline) break;
        $linkId = (int)$acc['link_id']; $chat = (int)$acc['chat_id'];
        if ((int)$acc['blocked'] === 1 || isset($blockedChats[$chat])) {
            $last = $linkId; $processed++;
            $db->prepare("UPDATE tg_counters SET val=? WHERE bot_id=? AND name='expiry_cursor'")->execute([$last, $botId]);
            continue;
        }
        $bq = $db->prepare('SELECT blocked FROM tg_users WHERE bot_id=? AND chat_id=?');
        $bq->execute([$botId, $chat]);
        if ((int)$bq->fetchColumn() === 1) {
            $last = $linkId; $processed++;
            $db->prepare("UPDATE tg_counters SET val=? WHERE bot_id=? AND name='expiry_cursor'")->execute([$last, $botId]);
            continue;
        }
        $info = botAcctInfo($db, $acc);
        if (!$info) {
            $last = $linkId; $processed++;
            $db->prepare("UPDATE tg_counters SET val=? WHERE bot_id=? AND name='expiry_cursor'")->execute([$last, $botId]);
            continue;
        }
        $email = bh((string)$acc['email']); $alerts = [];
        $expire = (int)$info['expire'];
        if ($expire > $now) {
            $left = $expire - $now; $expRef = (string)$expire;
            if ($left <= 3 * 86400 && $left > 86400) $alerts[] = ['expiry_3d', $expRef, "⏳ انقضای حساب <code>{$email}</code> تا ۳ روز دیگر است. برای تمدید اقدام کنید."];
            elseif ($left <= 86400) $alerts[] = ['expiry_1d', $expRef, "⚠️ حساب <code>{$email}</code> تا ۱ روز دیگر منقضی می‌شود. برای تمدید اقدام کنید."];
        }
        $limit = (int)$info['limit']; $used = max(0, (int)$info['used']);
        if ($limit > 0) {
            $usageRef = $limit . ':' . $expire . ':' . (int)($acc['usage_base'] ?? 0);
            if ($used >= (int)ceil($limit * 0.8)) $alerts[] = ['usage_80', $usageRef, "⚠️ بیش از ۸۰٪ حجم حساب <code>{$email}</code> مصرف شده است (" . botBytes($used) . ' از ' . botBytes($limit) . ').'];
            if ($used >= $limit) $alerts[] = ['usage_100', $usageRef, "🚫 حجم حساب <code>{$email}</code> به پایان رسیده است (" . botBytes($used) . ' از ' . botBytes($limit) . ').'];
        }
        $retryCurrent = false;
        foreach ($alerts as $i => [$kind, $ref, $message]) {
            if (microtime(true) >= $deadline) { $retryCurrent = true; break; }
            $status = botExpiryAlertSend($db, $bot, $acc, $chat, (string)$kind, (string)$ref, (string)$message);
            if ($status === 'blocked') { $blockedChats[$chat] = true; break; }
            if (microtime(true) >= $deadline && $i < count($alerts) - 1) { $retryCurrent = true; break; }
        }
        // اگر بودجه وسط هشدارهای همین حساب تمام شد، cursor روی حساب قبلی می‌ماند؛ هشدارهای باقی‌مانده بعداً ادامه پیدا می‌کنند.
        if ($retryCurrent) break;
        $last = $linkId; $processed++;
        $db->prepare("UPDATE tg_counters SET val=? WHERE bot_id=? AND name='expiry_cursor'")->execute([$last, $botId]);
    }
    if ($processed === count($rows) && count($rows) < 200) {
        $db->prepare("UPDATE tg_counters SET val=0 WHERE bot_id=? AND name='expiry_cursor'")->execute([$botId]);
    } elseif ($processed > 0) {
        $db->prepare("UPDATE tg_counters SET val=? WHERE bot_id=? AND name='expiry_cursor'")->execute([$last, $botId]);
    }
}
/** جاب هشدار انقضا/مصرف حجم: هر ربات فعال، حداکثر ۲۰۰ حساب در هر اجرا. */
function botExpiryAlerts(PDO $db): void {
    if (defined('BOT_TEST_MODE') && !is_callable($GLOBALS['BOT_PN_USER'] ?? null)) return;
    $deadline = isset($GLOBALS['__sched_deadline']) ? (float)$GLOBALS['__sched_deadline'] : microtime(true) + 8.0;
    $q = $db->query("SELECT b.* FROM tg_bots b JOIN accounts ag ON ag.id=b.agent_id WHERE b.enabled=1 AND ag.role IN ('agent','admin') AND ag.disabled=0 ORDER BY b.id");
    foreach ($q->fetchAll(PDO::FETCH_ASSOC) as $bot) {
        if (microtime(true) >= $deadline) return;
        try { botExpiryAlertBot($db, $bot, $deadline); }
        catch (Throwable $e) { error_log('bot_expiry_alerts: ' . get_class($e) . ' @' . basename($e->getFile()) . ':' . $e->getLine()); }
    }
}
/** ثبت هشدارها در زمان‌بند یک‌ساعته‌ی مشترک پروژه؛ نیازی به کرون‌جاب جدا نیست. */
function botSchedJobs(): array {
    return ['bot_expiry_alerts' => [3600, function (PDO $db): void { botExpiryAlerts($db); }],
            'bot_broadcast' => [10, function (PDO $db): void { botBroadcastJob($db); }],
            'bot_backup' => [3600, function (PDO $db): void { botBackupJob($db); }]];
}

/** «حساب‌های من»: فقط tg_accts همین ربات و همین چت، ۱۰تایی؛ دکمه‌ی «رمز جدید» و «جزئیات» برای هر حساب */
function botMyAccounts(PDO $db, array $bot, array $cfg, int $chat, int $page = 0): void {
    $page = max(0, min($page, 1000));
    $s = $db->prepare("SELECT a.id, a.email, a.panel_username, a.panel_id, a.usage_base, a.disabled, t.kind FROM tg_accts t JOIN accounts a ON a.id=t.account_id WHERE t.bot_id=? AND t.chat_id=? AND " . botOwnSql($db, 'a.owner_id', (int)$bot['agent_id']) . " AND a.role='user' ORDER BY t.id DESC LIMIT 11 OFFSET " . ($page * 10));
    $s->execute([(int)$bot['id'], $chat, (int)$bot['agent_id']]);
    $rows = $s->fetchAll(PDO::FETCH_ASSOC); $more = count($rows) > 10; $rows = array_slice($rows, 0, 10);
    if (!$rows) { botSay($db, $bot, $chat, $page === 0 ? 'هنوز حسابی از این ربات ندارید.' : 'حساب بیشتری وجود ندارد.', botMn($db, $bot, $cfg, $chat)); return; }
    $txt = "حساب‌های شما:\n"; $kb = [];
    foreach ($rows as $r) {
        $txt .= "\n<code>" . bh((string)$r['email']) . '</code> — ' . ($r['kind'] === 'test' ? 'تست' : 'اشتراک') . "\n" . bh(botAcctLines($r, botAcctInfo($db, $r))) . "\n";
        $kb[] = [botB($cfg, 'pass', botL($cfg, 'pass') . ': ' . $r['email'], ['callback_data' => 'n:' . (int)$r['id']]), botAB('🔎 جزئیات', 'ac:' . (int)$r['id'])];
    }
    $nav = botPageRow('ak', $page, $more); if ($nav) $kb[] = $nav;
    $kb[] = [botBL($cfg, 'back', ['callback_data' => 'm:home'])];
    botSay($db, $bot, $chat, mb_substr($txt, 0, 3900), $kb);
}
/** صفحه‌ی جزئیات یک حساب؛ فقط حسابِ ثبت‌شده در tg_accts همین ربات و همین چت (id حدسی = «حساب پیدا نشد») */
function botAccountDetail(PDO $db, array $bot, array $cfg, int $chat, int $accId): void {
    $r = botOwnedAccount($db, $bot, $chat, $accId);
    if (!$r) { botSay($db, $bot, $chat, 'حساب پیدا نشد.', botMn($db, $bot, $cfg, $chat)); return; }
    $txt = "🔎 <b>جزئیات حساب</b>\nایمیل: <code>" . bh((string)$r['email']) . "</code>\nنوع: " . ($r['bot_kind'] === 'test' ? 'تست' : 'اشتراک') . "\nتاریخ ساخت: " . date('Y/m/d', (int)$r['created_at'])
         . "\n" . bh(botAcctLines($r, botAcctInfo($db, $r)));
    $kb = [[botB($cfg, 'pass', botL($cfg, 'pass'), ['callback_data' => 'n:' . (int)$r['id']])], [botAB('🔄 تمدید', 'rn:' . (int)$r['id'], 'success')]];
    if (!empty($cfg['traffic_packs'])) $kb[] = [botAB('➕ حجم اضافه', 'tr:' . (int)$r['id'], 'primary')];
    $kb[] = [botAB('◀️ حساب‌های من', 'ak:0'), botBL($cfg, 'back', ['callback_data' => 'm:home'])];
    botSay($db, $bot, $chat, $txt, $kb);
}
/** یک حساب فقط وقتی متعلق به این نماینده/ربات/چت است برمی‌گردد؛ تمام callbackهای تمدید و حجم از این دروازه عبور می‌کنند. */
function botOwnedAccount(PDO $db, array $bot, int $chat, int $accId): ?array {
    if ($accId <= 0) return null;
    $q = $db->prepare("SELECT a.*, t.kind AS bot_kind FROM tg_accts t JOIN accounts a ON a.id=t.account_id
        WHERE t.bot_id=? AND t.chat_id=? AND t.account_id=? AND " . botOwnSql($db, 'a.owner_id', (int)$bot['agent_id']) . " AND a.role='user' LIMIT 1");
    $q->execute([(int)$bot['id'], $chat, $accId, (int)$bot['agent_id']]);
    $r = $q->fetch(PDO::FETCH_ASSOC);
    return $r ?: null;
}
/** اعتبارسنجیِ مجدد هدف عملیات؛ plan و traffic-pack همواره از تنظیمات فعلی همین نماینده خوانده می‌شوند. */
function botServiceTarget(PDO $db, array $bot, array $cfg, int $chat, string $kind, int $accId, int $targetId): array {
    $acc = botOwnedAccount($db, $bot, $chat, $accId);
    if (!$acc) return ['ok' => false, 'msg' => 'حساب پیدا نشد.'];
    if ($kind === 'renew') {
        $q = $db->prepare("SELECT * FROM plans WHERE id=? AND owner_id=? AND kind='bot' AND active=1");
        $q->execute([$targetId, (int)$bot['agent_id']]); $pl = $q->fetch(PDO::FETCH_ASSOC);
        if (!$pl || botPlanMeta($db, (int)$bot['agent_id'], (int)$pl['id'])['ag']) return ['ok' => false, 'msg' => 'پلن تمدید دیگر موجود نیست.'];
        $target = ['id' => (int)$pl['id'], 'name' => (string)$pl['name'], 'bytes' => (int)$pl['data_bytes'], 'days' => (int)$pl['days'],
            'gb' => (int)$pl['data_bytes'] / 1073741824, 'base' => botPrice($cfg, (int)$pl['price'])];
        return ['ok' => true, 'account' => $acc, 'target' => $target];
    }
    if ($kind === 'traffic') {
        $packs = (array)($cfg['traffic_packs'] ?? []);
        if (!isset($packs[$targetId]) || !is_array($packs[$targetId])) return ['ok' => false, 'msg' => 'بسته‌ی حجم دیگر موجود نیست.'];
        $pack = $packs[$targetId];
        return ['ok' => true, 'account' => $acc, 'target' => ['id' => $targetId, 'name' => (string)$pack['gb'] . ' گیگ حجم اضافه',
            'gb' => (float)$pack['gb'], 'bytes' => (int)round((float)$pack['gb'] * 1073741824), 'days' => 0, 'base' => (int)$pack['price']]];
    }
    return ['ok' => false, 'msg' => 'عملیات نامعتبر است.'];
}
function botAccountRenewPage(PDO $db, array $bot, array $cfg, int $chat, int $accId): void {
    $acc = botOwnedAccount($db, $bot, $chat, $accId);
    if (!$acc) { botSay($db, $bot, $chat, 'حساب پیدا نشد.', botMn($db, $bot, $cfg, $chat)); return; }
    $q = $db->prepare("SELECT id,name,data_bytes,days,price FROM plans WHERE owner_id=? AND kind='bot' AND active=1 ORDER BY id");
    $q->execute([(int)$bot['agent_id']]);
    $plans = array_values(array_filter($q->fetchAll(PDO::FETCH_ASSOC), fn($p) => !botPlanMeta($db, (int)$bot['agent_id'], (int)$p['id'])['ag']));
    if (!$plans) { botSay($db, $bot, $chat, 'در حال حاضر پلن فعالی برای تمدید این حساب وجود ندارد.', [[botAB('بازگشت به حساب', 'ac:' . $accId)]]); return; }
    $kb = [];
    foreach ($plans as $p) {
        $price = botPrice($cfg, (int)$p['price']);
        $label = (string)$p['name'] . ' — ' . botGb((int)$p['data_bytes']) . ' / ' . ((int)$p['days'] > 0 ? (int)$p['days'] . ' روز' : 'بدون انقضا') . ' — ' . botMoney($price);
        $kb[] = [botAB($label, 'rp:' . $accId . ':' . (int)$p['id'])];
    }
    $kb[] = [botAB('بازگشت به حساب', 'ac:' . $accId)];
    botSay($db, $bot, $chat, '🔄 <b>تمدید حساب</b>' . "\nحساب: <code>" . bh((string)$acc['email']) . "</code>\nیکی از پلن‌های فعال همین نماینده را انتخاب کنید:", $kb);
}
function botAccountTrafficPage(PDO $db, array $bot, array $cfg, int $chat, int $accId): void {
    $acc = botOwnedAccount($db, $bot, $chat, $accId);
    if (!$acc) { botSay($db, $bot, $chat, 'حساب پیدا نشد.', botMn($db, $bot, $cfg, $chat)); return; }
    $packs = (array)($cfg['traffic_packs'] ?? []);
    if (!$packs) { botSay($db, $bot, $chat, 'بسته‌ی حجم اضافه برای این ربات تعریف نشده است.', [[botAB('بازگشت به حساب', 'ac:' . $accId)]]); return; }
    $kb = [];
    foreach ($packs as $i => $p) $kb[] = [botAB(rtrim(rtrim(number_format((float)$p['gb'], 3, '.', ''), '0'), '.') . ' گیگ — ' . botMoney((int)$p['price']), 'tp:' . $accId . ':' . (int)$i)];
    $kb[] = [botAB('بازگشت به حساب', 'ac:' . $accId)];
    botSay($db, $bot, $chat, '➕ <b>حجم اضافه</b>' . "\nحساب: <code>" . bh((string)$acc['email']) . "</code>\nبسته‌ی موردنظر را انتخاب کنید:", $kb);
}
function botServiceCheckout(PDO $db, array $bot, array $cfg, array $u, string $kind, int $accId, int $targetId, string $code = ''): void {
    $chat = (int)$u['chat_id'];
    $t = botServiceTarget($db, $bot, $cfg, $chat, $kind, $accId, $targetId);
    if (!$t['ok']) { botSay($db, $bot, $chat, (string)$t['msg'], botMn($db, $bot, $cfg, $chat)); return; }
    $acc = $t['account']; $target = $t['target']; $base = (int)$target['base']; $price = $base; $cpn = null;
    if ($code !== '') {
        $cpn = botCouponPreview($db, $bot, $u, $code, $base, $kind);
        if (!$cpn['ok']) { botSay($db, $bot, $chat, '⚠️ ' . bh((string)$cpn['msg']), [[botAB('بازگشت به حساب', 'ac:' . $accId)]]); return; }
        $price = (int)$cpn['price']; $code = (string)$cpn['code'];
    }
    $word = $kind === 'renew' ? 'تمدید حساب' : 'حجم اضافه';
    $txt = '🧾 <b>' . $word . "</b>\nحساب: <code>" . bh((string)$acc['email']) . '</code>' . "\nگزینه: " . bh((string)$target['name']) . "\nقیمت: " . botMoney($base);
    if ($cpn) $txt .= "\n🏷 کد <code>" . bh($code) . '</code>: −' . botMoney((int)$cpn['discount']);
    $txt .= "\nمبلغ نهایی: <b>" . botMoney($price) . '</b>' . "\nموجودی کیف پول: " . botMoney(botBalance($db, (int)$u['id'], (int)$bot['id'])) . "\n\nروش پرداخت را انتخاب کنید:";
    $codeArg = $code !== '' ? ':' . $code : '';
    $walletCb = ($kind === 'renew' ? 'rw:' : 'tw:') . $accId . ':' . $targetId . $codeArg;
    $cardCb = ($kind === 'renew' ? 'rc:' : 'tc:') . $accId . ':' . $targetId . $codeArg;
    $kb = [];
    if ($code === '') $kb[] = [botAB('🏷 کد تخفیف دارم', ($kind === 'renew' ? 'rq:' : 'tq:') . $accId . ':' . $targetId)];
    if (botBalance($db, (int)$u['id'], (int)$bot['id']) >= $price) $kb[] = [botAB('پرداخت از موجودی', $walletCb, 'success'), botAB('کارت‌به‌کارت', $cardCb, 'primary')];
    else $kb[] = [botAB('کارت‌به‌کارت', $cardCb, 'primary')];
    if ($code === '') foreach (botGwRows($db, (int)$bot['agent_id'], $price, ($kind === 'renew' ? 'gr:' : 'gx:') . $accId . ':' . $targetId) as $gr) $kb[] = $gr;
    $kb[] = [botAB('بازگشت', $kind === 'renew' ? 'rn:' . $accId : 'tr:' . $accId)];
    botSay($db, $bot, $chat, $txt, $kb);
}
function botServiceCouponAsk(PDO $db, array $bot, array $cfg, array $u, string $kind, int $accId, int $targetId): void {
    $chat = (int)$u['chat_id'];
    $t = botServiceTarget($db, $bot, $cfg, $chat, $kind, $accId, $targetId);
    if (!$t['ok']) { botSay($db, $bot, $chat, (string)$t['msg'], botMn($db, $bot, $cfg, $chat)); return; }
    $draft = json_encode(['kind' => $kind, 'target_id' => $targetId], JSON_UNESCAPED_UNICODE);
    $db->prepare('UPDATE tg_users SET state=?, state_val=?, draft=? WHERE id=? AND bot_id=? AND chat_id=?')
       ->execute(['svc_coupon', $accId, $draft, (int)$u['id'], (int)$bot['id'], $chat]);
    botSay($db, $bot, $chat, 'کد تخفیف همین عملیات را بفرستید:', [[botAB('بازگشت', $kind === 'renew' ? 'rp:' . $accId . ':' . $targetId : 'tp:' . $accId . ':' . $targetId)]]);
}
function botServiceCouponText(PDO $db, array $bot, array $cfg, array $u, string $text): void {
    $chat = (int)$u['chat_id']; $state = $db->prepare('SELECT draft,state_val FROM tg_users WHERE id=? AND bot_id=? AND chat_id=?');
    $state->execute([(int)$u['id'], (int)$bot['id'], $chat]); $s = $state->fetch(PDO::FETCH_ASSOC);
    $d = json_decode((string)($s['draft'] ?? ''), true);
    $kind = (string)($d['kind'] ?? ''); $targetId = (int)($d['target_id'] ?? 0); $accId = (int)($s['state_val'] ?? 0);
    if (!in_array($kind, ['renew', 'traffic'], true) || ($kind === 'renew' && $targetId <= 0) || ($kind === 'traffic' && $targetId < 0) || $accId <= 0) {
        $db->prepare("UPDATE tg_users SET state='',state_val=0,draft='' WHERE id=? AND bot_id=? AND chat_id=?")->execute([(int)$u['id'], (int)$bot['id'], $chat]);
        botSay($db, $bot, $chat, 'عملیات پیدا نشد؛ از جزئیات حساب دوباره شروع کنید.', botMn($db, $bot, $cfg, $chat)); return;
    }
    $t = botServiceTarget($db, $bot, $cfg, $chat, $kind, $accId, $targetId);
    if (!$t['ok']) {
        $db->prepare("UPDATE tg_users SET state='',state_val=0,draft='' WHERE id=? AND bot_id=? AND chat_id=?")->execute([(int)$u['id'], (int)$bot['id'], $chat]);
        botSay($db, $bot, $chat, (string)$t['msg'], botMn($db, $bot, $cfg, $chat)); return;
    }
    $cpn = botCouponPreview($db, $bot, $u, $text, (int)$t['target']['base'], $kind);
    if (!$cpn['ok']) { botSay($db, $bot, $chat, '⚠️ ' . bh((string)$cpn['msg']) . "\nکد را دوباره بفرستید:", [[botAB('لغو', 'ac:' . $accId)]]); return; }
    $db->prepare("UPDATE tg_users SET state='',state_val=0,draft='' WHERE id=? AND bot_id=? AND chat_id=?")->execute([(int)$u['id'], (int)$bot['id'], $chat]);
    botServiceCheckout($db, $bot, $cfg, $u, $kind, $accId, $targetId, (string)$cpn['code']);
}
/** اعمال تمدید/حجم با همان renewAccount موجود پروژه؛ خطای پنل هیچ تغییر کیف پولی را این‌جا انجام نمی‌دهد. */
function botApplyAccountService(PDO $db, array $bot, array $agent, int $chat, int $accId, string $kind, array $target): array {
    $acc = botOwnedAccount($db, $bot, $chat, $accId);
    if (!$acc) return ['ok' => false, 'msg' => 'حساب پیدا نشد.'];
    if ((string)$acc['panel_username'] === '') return ['ok' => false, 'msg' => 'شناسه‌ی پنل این حساب موجود نیست.'];
    $info = botAcctInfo($db, $acc);
    if (!$info) return ['ok' => false, 'msg' => 'اطلاعات حساب از پنل در دسترس نیست؛ پرداختی انجام نشد.'];
    $oldAlloc = max(0, (int)$acc['alloc_bytes']); $expire = (int)$info['expire'] > 0 ? (int)$info['expire'] : null;
    if ($kind === 'renew') {
        $bytes = max(0, (int)($target['bytes'] ?? 0)); $days = max(0, (int)($target['days'] ?? 0));
        $expire = $days > 0 ? max(time(), (int)$info['expire']) + $days * 86400 : null;
        $newAlloc = $bytes; $appliedBytes = $bytes;
    } elseif ($kind === 'traffic') {
        $limit = (int)$info['limit'];
        if ($limit <= 0) return ['ok' => false, 'msg' => 'این حساب حجم نامحدود دارد و امکان افزودن حجم به آن وجود ندارد.'];
        $added = max(1, (int)round((float)($target['gb'] ?? 0) * 1073741824));
        $appliedBytes = max(0, $limit - (int)$info['used']) + $added;
        $newAlloc = ($oldAlloc > 0 ? $oldAlloc : $limit) + $added;
        $days = 0;
    } else return ['ok' => false, 'msg' => 'عملیات نامعتبر است.'];
    if ((string)($agent['role'] ?? '') === 'agent') {
        $guardDays = $expire !== null ? (int)floor(($expire - time()) / 86400) : 0;
        $guard = botTry(function () use ($db, $agent, $newAlloc, $guardDays, $oldAlloc): bool { agentCheck($db, $agent, $newAlloc, $guardDays, $oldAlloc, false); return true; });
        if (!$guard['ok']) return ['ok' => false, 'msg' => 'تمدید یا حجم اضافه با سقف‌های نمایندگی سازگار نیست.'];
    }
    $panel = botTry(function () use ($db, $acc, $appliedBytes, $expire): array {
        if (defined('BOT_TEST_MODE') && is_callable($GLOBALS['BOT_PN_RENEW'] ?? null)) return $GLOBALS['BOT_PN_RENEW']($acc, $appliedBytes, $expire); // فقط تست‌ها
        return renewAccount($db, accPanel($db, $acc), (string)$acc['panel_username'], $appliedBytes, $expire);
    });
    if (!$panel['ok'] || !is_array($panel['v'] ?? null) || empty($panel['v']['ok'])) return ['ok' => false, 'msg' => 'پنل عملیات را نپذیرفت؛ مبلغ در صورت پرداخت از موجودی برگردانده شد.'];
    $db->prepare('UPDATE accounts SET alloc_bytes=? WHERE id=? AND ' . botOwnSql($db, 'owner_id', (int)$bot['agent_id']))->execute([$newAlloc, $accId, (int)$bot['agent_id']]);
    // با چرخه‌ی جدیدِ مصرف، هشدارهای درصدی دوباره قابل ارسال می‌شوند؛ هشدار انقضا با ref انقضای جدید خودبه‌خود تفکیک می‌شود.
    $db->prepare("DELETE FROM tg_notify_log WHERE bot_id=? AND account_id=? AND kind IN ('usage_80','usage_100')")->execute([(int)$bot['id'], $accId]);
    return ['ok' => true, 'account' => $acc, 'bytes' => $appliedBytes, 'days' => $days, 'expire' => $expire];
}
function botServiceWalletPay(PDO $db, array $bot, array $agent, array $cfg, array $u, string $kind, int $accId, int $targetId, string $code = ''): void {
    $chat = (int)$u['chat_id']; $t = botServiceTarget($db, $bot, $cfg, $chat, $kind, $accId, $targetId);
    if (!$t['ok']) { botSay($db, $bot, $chat, (string)$t['msg'], botMn($db, $bot, $cfg, $chat)); return; }
    $target = $t['target']; $price = (int)$target['base']; $cpn = null;
    if ($code !== '') {
        $cpn = botCouponApply($db, $bot, $u, $code, $price, 0, true, $kind);
        if (!$cpn['ok']) { botSay($db, $bot, $chat, '⚠️ ' . bh((string)$cpn['msg']), [[botAB('بازگشت', ($kind === 'renew' ? 'rp:' : 'tp:') . $accId . ':' . $targetId)]]); return; }
        $price = (int)$cpn['price'];
    }
    $rel = function () use ($db, $bot, &$cpn): void { if ($cpn) botCouponRelease($db, $bot, (int)$cpn['use_id']); };
    if (botWalletAdd($db, $bot, (int)$u['id'], -$price, $kind . ' account ' . $accId) === null) {
        $rel(); botSay($db, $bot, $chat, 'موجودی کیف پول کافی نیست.', botMn($db, $bot, $cfg, $chat)); return;
    }
    $done = botTry(fn() => botApplyAccountService($db, $bot, $agent, $chat, $accId, $kind, $target));
    $result = $done['ok'] && is_array($done['v'] ?? null) ? $done['v'] : ['ok' => false, 'msg' => 'عملیات انجام نشد.'];
    if (!$result['ok']) {
        botWalletAdd($db, $bot, (int)$u['id'], $price, 'refund'); $rel();
        botSay($db, $bot, $chat, '⚠️ ' . bh((string)$result['msg']) . "\nمبلغ از کیف پول برگشت داده شد.", botMn($db, $bot, $cfg, $chat));
        return;
    }
    agAudit($db, (int)$agent['id'], 'bot_' . $kind, 0, $accId, $price, 'wallet chat=' . $chat);
    botAudit($db, $bot, $chat, 'account_' . $kind, 'account:' . $accId, ['payment' => 'wallet', 'price' => $price]);
    botAfterSale($db, $bot, $cfg, $chat, $price);
    botSay($db, $bot, $chat, $kind === 'renew' ? '✅ حساب با موفقیت تمدید شد.' : '✅ حجم اضافه با موفقیت ثبت شد.', [[botAB('جزئیات حساب', 'ac:' . $accId, 'success')], [botBL($cfg, 'back', ['callback_data' => 'm:home'])]]);
}
function botCancelServiceAwaiting(PDO $db, array $bot, int $chat): void {
    $s = $db->prepare("SELECT id FROM tg_orders WHERE bot_id=? AND chat_id=? AND COALESCE(kind,'plan') IN ('plan','renew','traffic') AND status='awaiting_receipt'");
    $s->execute([(int)$bot['id'], $chat]);
    foreach ($s->fetchAll(PDO::FETCH_COLUMN) as $oid) {
        $up = $db->prepare("UPDATE tg_orders SET status='cancelled',updated_at=? WHERE id=? AND bot_id=? AND chat_id=? AND status='awaiting_receipt'");
        $up->execute([time(), (int)$oid, (int)$bot['id'], $chat]);
        if ($up->rowCount() === 1) botCouponReleaseByOrder($db, (int)$bot['id'], (int)$oid);
    }
}
function botServiceCardPay(PDO $db, array $bot, array $cfg, array $u, string $kind, int $accId, int $targetId, string $code = ''): void {
    $chat = (int)$u['chat_id']; $agentId = (int)$bot['agent_id'];
    $t = botServiceTarget($db, $bot, $cfg, $chat, $kind, $accId, $targetId);
    if (!$t['ok']) { botSay($db, $bot, $chat, (string)$t['msg'], botMn($db, $bot, $cfg, $chat)); return; }
    $target = $t['target']; $base = (int)$target['base']; $price = $base; $cpn = null;
    $busy = $db->prepare("SELECT 1 FROM tg_orders WHERE bot_id=? AND chat_id=? AND COALESCE(kind,'plan')<>'topup' AND status IN ('pending_review','approving')");
    $busy->execute([(int)$bot['id'], $chat]);
    if ($busy->fetchColumn()) { botSay($db, $bot, $chat, 'سفارش قبلی شما در انتظار تأیید است؛ لطفاً منتظر بمانید.', botMn($db, $bot, $cfg, $chat)); return; }
    if ($code !== '') {
        $cpn = botCouponApply($db, $bot, $u, $code, $base, 0, true, $kind);
        if (!$cpn['ok']) { botSay($db, $bot, $chat, '⚠️ ' . bh((string)$cpn['msg']), [[botAB('بازگشت', ($kind === 'renew' ? 'rp:' : 'tp:') . $accId . ':' . $targetId)]]); return; }
        $price = (int)$cpn['price'];
    }
    $cards = botPayCards($db, $agentId, $price, $cfg, (int)$bot['id']);
    if (!$cards) {
        if ($cpn) botCouponRelease($db, $bot, (int)$cpn['use_id']);
        botSay($db, $bot, $chat, 'روش پرداختی برای این مبلغ تنظیم نشده است؛ به پشتیبانی پیام دهید.', botMn($db, $bot, $cfg, $chat)); return;
    }
    botCancelServiceAwaiting($db, $bot, $chat);
    $name = ($kind === 'renew' ? 'تمدید: ' : 'حجم اضافه: ') . (string)$target['name'];
    $snap = json_encode(['id' => (int)$target['id'], 'name' => $name, 'action' => $kind, 'account_id' => $accId,
        'bytes' => (int)$target['bytes'], 'days' => (int)$target['days'], 'gb' => (float)$target['gb'], 'price' => $price, 'base' => $base, 'coupon' => $cpn ? $cpn['code'] : ''], JSON_UNESCAPED_UNICODE);
    $csn = json_encode(array_map(fn($c) => ['n' => (string)$c['card_number'], 'h' => (string)$c['card_holder']], $cards), JSON_UNESCAPED_UNICODE);
    $now = time();
    try {
        $db->prepare("INSERT INTO tg_orders (bot_id,agent_id,chat_id,kind,ref_account_id,account_id,plan_snapshot,card_snapshot,price,status,coupon_id,discount,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,'awaiting_receipt',?,?,?,?)")
           ->execute([(int)$bot['id'], $agentId, $chat, $kind, $accId, $accId, $snap, $csn, $price, $cpn ? (int)$cpn['coupon_id'] : 0,
               $cpn ? (int)$cpn['discount'] : 0, $now, $now]);
    } catch (Throwable $e) {
        if ($cpn) botCouponRelease($db, $bot, (int)$cpn['use_id']);
        botSay($db, $bot, $chat, 'ثبت سفارش ناموفق بود؛ دوباره تلاش کنید.', botMn($db, $bot, $cfg, $chat)); return;
    }
    $oid = (int)$db->lastInsertId();
    if ($cpn) botCouponAttach($db, $bot, (int)$cpn['use_id'], $oid);
    botState($db, $u, 'receipt', $oid);
    $txt = '<b>' . bh($name) . "</b>\nحساب: <code>" . bh((string)$t['account']['email']) . '</code>' . "\nمبلغ قابل پرداخت: <b>" . botMoney($price) . "</b>\n\nبه یکی از کارت‌های زیر واریز کنید:\n";
    foreach ($cards as $c) $txt .= "\n<code>" . bh((string)$c['card_number']) . '</code>' . "\nبه نام: " . bh((string)$c['card_holder']) . "\n";
    $txt .= "\n" . botTx($cfg, 'paynote');
    botSay($db, $bot, $chat, $txt, [[botBL($cfg, 'cancel', ['callback_data' => 'x:' . $oid])]]);
}
function botL(array $cfg, string $key): string { return (string)$cfg['btn'][$key]['l']; }
function botNewPassword(PDO $db, array $bot, array $cfg, int $chat, int $accId): void {
    $acc = botOwnedAccount($db, $bot, $chat, $accId);
    if (!$acc) { botSay($db, $bot, $chat, 'حساب پیدا نشد.', botMn($db, $bot, $cfg, $chat)); return; }
    $pass = botGenPass();
    $db->prepare("UPDATE accounts SET pass_hash=? WHERE id=? AND " . botOwnSql($db, 'owner_id', (int)$bot['agent_id']) . " AND role='user'")
       ->execute([password_hash($pass, PASSWORD_DEFAULT), $accId, (int)$bot['agent_id']]);
    killTokens($db, $accId); // نشست‌های قبلی بسته می‌شود
    botSay($db, $bot, $chat, "رمز جدید ثبت شد:\n\nایمیل: <code>" . bh((string)$acc['email']) . "</code>\nرمز: <code>" . bh($pass) . '</code>', botMn($db, $bot, $cfg, $chat));
}

// ------------------------------------------------------------------ شارژ کیف پول توسط مشتری + تاریخچه‌ها (مرحله ۳)
/**
 * کارت‌های فعالِ همین نماینده (owner_id=agent_id) که برای این مبلغ مجازند.
 * card_mode=all (پیش‌فرض): حداکثر ۳ کارت. card_mode=rotate (با $cfg و $botId): فقط یک کارت؛ نوبت با شمارنده‌ی اتمیک tg_counters(bot_id,'card_ptr') جلو می‌رود.
 */
function botPayCards(PDO $db, int $agId, int $amount, ?array $cfg = null, int $botId = 0): array {
    $rot = $cfg !== null && $botId > 0 && (string)($cfg['card_mode'] ?? 'all') === 'rotate';
    $cs = $db->prepare("SELECT * FROM pay_methods WHERE owner_id=? AND type='card' AND enabled=1 AND default_on=1 AND (min_amount=0 OR min_amount<=?) AND (max_amount=0 OR max_amount>=?) ORDER BY id" . ($rot ? '' : ' LIMIT 3'));
    $cs->execute([$agId, $amount, $amount]);
    $all = $cs->fetchAll(PDO::FETCH_ASSOC);
    if (!$rot || !$all) return $all;
    $val = (int)botAtomic($db, function () use ($db, $botId): int {
        $db->prepare('INSERT OR IGNORE INTO tg_counters (bot_id, name, val) VALUES (?,?,0)')->execute([$botId, 'card_ptr']);
        $db->prepare('UPDATE tg_counters SET val=val+1 WHERE bot_id=? AND name=?')->execute([$botId, 'card_ptr']);
        $q = $db->prepare('SELECT val FROM tg_counters WHERE bot_id=? AND name=?'); $q->execute([$botId, 'card_ptr']);
        return (int)$q->fetchColumn();
    });
    return [$all[max(0, $val - 1) % count($all)]];
}
/** [حداقل, حداکثر] مبلغ شارژ؛ حداکثر ۰ = بدون سقف */
function botTopupLimits(array $cfg): array {
    $min = max(1000, (int)$cfg['topup_min']); $max = (int)$cfg['topup_max'];
    return [$min, $max > 0 ? max($max, $min) : 0];
}
function botTopupAsk(PDO $db, array $bot, array $cfg, array $u): void {
    $chat = (int)$u['chat_id'];
    if ((int)$cfg['topup_on'] !== 1) { botSay($db, $bot, $chat, 'شارژ کیف پول در حال حاضر فعال نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    [$min, $max] = botTopupLimits($cfg);
    botState($db, $u, 'topamt');
    botSay($db, $bot, $chat, "مبلغ شارژ را به تومان (فقط عدد) بفرستید.\nحداقل: <b>" . botMoney($min) . '</b>' . ($max > 0 ? "\nحداکثر: <b>" . botMoney($max) . '</b>' : ''),
        [[botBL($cfg, 'back', ['callback_data' => 'm:wal'])]]);
}
/** دریافت مبلغ شارژ و ساخت سفارش کارت‌به‌کارت (kind='topup')؛ ادامه‌ی جریان همان رسید + شماره پیگیری است */
function botTopupAmount(PDO $db, array $bot, array $cfg, array $u, string $text, bool $skipGw = false): void {
    $chat = (int)$u['chat_id']; $agId = (int)$bot['agent_id']; $bid = (int)$bot['id']; $now = time();
    if ((int)$cfg['topup_on'] !== 1) { botState($db, $u, ''); botSay($db, $bot, $chat, 'شارژ کیف پول در حال حاضر فعال نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    $raw = (string)preg_replace('/\D/', '', payDigits($text));
    if ($raw === '' || strlen($raw) > 12) { botSay($db, $bot, $chat, 'مبلغ را فقط به‌صورت عدد (تومان) بفرستید.'); return; }
    $amt = (int)$raw; [$min, $max] = botTopupLimits($cfg);
    if ($amt < $min || ($max > 0 && $amt > $max)) {
        botSay($db, $bot, $chat, 'مبلغ باید حداقل ' . botMoney($min) . ($max > 0 ? ' و حداکثر ' . botMoney($max) : '') . ' باشد.');
        return;
    }
    $open = $db->prepare("SELECT COUNT(*) FROM tg_orders WHERE bot_id=? AND chat_id=? AND kind='topup' AND status IN ('pending_review','approving')"); $open->execute([$bid, $chat]);
    if ((int)$open->fetchColumn() >= 3) { botState($db, $u, ''); botSay($db, $bot, $chat, 'چند درخواست شارژ شما در انتظار تأیید است؛ لطفاً منتظر بمانید.', botMn($db, $bot, $cfg, $chat)); return; }
    if (!$skipGw && ($gwRows = botGwRows($db, $agId, $amt, 'gt'))) { // درگاه آنلاین فعال است: انتخاب روش
        botState($db, $u, '');
        $kb = [];
        if (botHasCards($db, $agId, $amt)) $kb[] = [botAB('💳 کارت‌به‌کارت', 'gt:0:' . $amt)];
        foreach ($gwRows as $gr) { $gr[0]['callback_data'] .= ':' . $amt; $kb[] = $gr; }
        $kb[] = [botBL($cfg, 'back', ['callback_data' => 'm:wal'])];
        botSay($db, $bot, $chat, 'شارژ کیف پول: <b>' . botMoney($amt) . "</b>\n\nروش پرداخت را انتخاب کنید:", $kb);
        return;
    }
    $cards = botPayCards($db, $agId, $amt, $cfg, $bid);
    if (!$cards) {
        botState($db, $u, '');
        botSay($db, $bot, $chat, 'روش پرداختی برای این مبلغ تنظیم نشده است؛ به پشتیبانی پیام دهید.', botMn($db, $bot, $cfg, $chat));
        botEvent($db, $bot, 'error', '⚠️ یک کاربر ربات خواست کیف پول را شارژ کند ولی کارت فعالی برای این مبلغ در «کارت‌ها» ندارید.');
        return;
    }
    botCancelAwaiting($db, $bid, $chat); // سفارش خریدِ در انتظار رسیدِ قبلی (با کوپنش) لغو و کوپن برگردانده می‌شود
    $snap = json_encode(['topup' => $amt], JSON_UNESCAPED_UNICODE);
    $csn = json_encode(array_map(fn($c) => ['n' => (string)$c['card_number'], 'h' => (string)$c['card_holder']], $cards), JSON_UNESCAPED_UNICODE);
    $db->prepare("INSERT INTO tg_orders (bot_id, agent_id, chat_id, kind, plan_snapshot, card_snapshot, price, status, created_at, updated_at) VALUES (?,?,?,'topup',?,?,?,'awaiting_receipt',?,?)")
       ->execute([$bid, $agId, $chat, $snap, $csn, $amt, $now, $now]);
    $oid = (int)$db->lastInsertId();
    botState($db, $u, 'receipt', $oid);
    $txt = 'شارژ کیف پول: <b>' . botMoney($amt) . "</b>\n\nمبلغ را به یکی از کارت‌های زیر واریز کنید:\n";
    foreach ($cards as $c) $txt .= "\n<code>" . bh((string)$c['card_number']) . '</code>' . "\nبه نام: " . bh((string)$c['card_holder']) . "\n";
    $txt .= "\n" . botTx($cfg, 'paynote');
    botSay($db, $bot, $chat, $txt, [[botBL($cfg, 'cancel', ['callback_data' => 'x:' . $oid])]]);
}
/**
 * اعتبار شارژ: فقط یک‌بار و اتمیک. وضعیت سفارش با شرط status IN ($from) به approved می‌رود و فقط اگر rowCount()==1 باشد موجودی (reason='topup') اضافه می‌شود؛
 * هر دو در یک تراکنش‌اند، پس اگر ثبت موجودی شکست بخورد وضعیت برمی‌گردد. $expect = مبلغ پرداخت‌شده‌ی درگاه (نامطابق = رد).
 * @return array{ok:bool,msg:string,amount?:int,balance?:int,chat?:int}
 */
function botTopupCredit(PDO $db, array $bot, int $oid, array $from, ?int $expect = null): array {
    $bid = (int)$bot['id'];
    $os = $db->prepare("SELECT * FROM tg_orders WHERE id=? AND bot_id=? AND agent_id=? AND kind='topup'"); $os->execute([$oid, $bid, (int)$bot['agent_id']]);
    $o = $os->fetch(PDO::FETCH_ASSOC);
    if (!$o) return ['ok' => false, 'msg' => 'سفارش پیدا نشد'];
    $amt = (int)$o['price'];
    if ($amt <= 0 || ($expect !== null && $expect !== $amt)) return ['ok' => false, 'msg' => 'مبلغ پرداخت با سفارش مطابقت ندارد'];
    $us = $db->prepare('SELECT id FROM tg_users WHERE bot_id=? AND chat_id=?'); $us->execute([$bid, (int)$o['chat_id']]);
    $uid = (int)$us->fetchColumn();
    if ($uid <= 0 || !$from) return ['ok' => false, 'msg' => 'سفارش پیدا نشد'];
    $in = implode(',', array_fill(0, count($from), '?'));
    $own = !$db->inTransaction();
    $end = function (bool $commit) use ($db, $own): void {
        if ($own) { if ($commit) $db->commit(); else $db->rollBack(); }
        else $db->exec($commit ? 'RELEASE SAVEPOINT bot_topup' : 'ROLLBACK TO SAVEPOINT bot_topup; RELEASE SAVEPOINT bot_topup');
    };
    try {
        if ($own) $db->beginTransaction(); else $db->exec('SAVEPOINT bot_topup');
        $up = $db->prepare("UPDATE tg_orders SET status='approved', updated_at=? WHERE id=? AND bot_id=? AND agent_id=? AND kind='topup' AND status IN ($in)");
        $up->execute(array_merge([time(), $oid, $bid, (int)$bot['agent_id']], array_values($from)));
        $won = $up->rowCount() === 1;
        $bal = $won ? botWalletAdd($db, $bot, $uid, $amt, 'topup') : null;
        if ($bal === null) { $end(false); return ['ok' => false, 'msg' => $won ? 'ثبت اعتبار ناموفق بود' : 'این سفارش قبلاً بررسی شده است']; }
        $end(true);
    } catch (Throwable $e) {
        try { $end(false); } catch (Throwable $e2) { /* تراکنش از قبل بسته شده */ }
        error_log('botTopupCredit: ' . get_class($e));
        return ['ok' => false, 'msg' => 'خطا در ثبت شارژ'];
    }
    return ['ok' => true, 'msg' => 'تأیید شد', 'amount' => $amt, 'balance' => $bal, 'chat' => (int)$o['chat_id']];
}
function botTopupNotify(PDO $db, array $bot, array $r): void {
    $cfg = botCfg($db, (int)$bot['agent_id']);
    botEvent($db, $bot, 'topup', "💳 شارژ کیف پول\nمبلغ: " . botMoney((int)$r['amount']) . "\nمشتری: <code>" . (int)$r['chat'] . '</code>');
    botSay($db, $bot, (int)$r['chat'], '✅ کیف پول شما ' . botMoney((int)$r['amount']) . " شارژ شد.\nموجودی فعلی: <b>" . botMoney((int)$r['balance']) . '</b>', botMn($db, $bot, $cfg, (int)$r['chat']));
}
/** تأیید ادمین (تلگرام/پورتال) برای سفارش شارژ کارت‌به‌کارت؛ از botOrderApprove صدا زده می‌شود */
function botTopupApprove(PDO $db, array $bot, int $oid, string $by, int $actorChat = 0): array {
    $r = botTopupCredit($db, $bot, $oid, ['pending_review']);
    if (!$r['ok']) return ['ok' => false, 'msg' => $r['msg']];
    botAudit($db, $bot, $actorChat, 'topup_approve', 'order:' . $oid, ['by' => $by, 'amount' => $r['amount']]);
    botTopupNotify($db, $bot, $r);
    return ['ok' => true, 'msg' => 'شارژ تأیید شد'];
}
/**
 * ساخت سفارش شارژ آنلاین (pending_gateway) برای ورودی توابع درگاه؛ gateway_ref در محدوده‌ی همین ربات یکتاست.
 * null = شارژ غیرفعال، مبلغ خارج از بازه، کاربر متعلق به این ربات نیست یا gateway_ref تکراری است.
 */
function botTopupGatewayOrder(PDO $db, array $bot, array $cfg, array $u, int $amount, string $gateway, string $ref): ?int {
    [$min, $max] = botTopupLimits($cfg);
    if ((int)$cfg['topup_on'] !== 1 || (int)$u['bot_id'] !== (int)$bot['id'] || $amount < $min || ($max > 0 && $amount > $max) || $gateway === '' || $ref === '') return null;
    $now = time();
    try {
        $db->prepare("INSERT INTO tg_orders (bot_id, agent_id, chat_id, kind, plan_snapshot, price, status, gateway, gateway_ref, created_at, updated_at) VALUES (?,?,?,'topup',?,?,'pending_gateway',?,?,?,?)")
           ->execute([(int)$bot['id'], (int)$bot['agent_id'], (int)$u['chat_id'], json_encode(['topup' => $amount], JSON_UNESCAPED_UNICODE), $amount, $gateway, $ref, $now, $now]);
    } catch (PDOException $e) { return null; }
    return (int)$db->lastInsertId();
}
/** callback/verify درگاه: سفارش فقط در محدوده‌ی همین ربات/نماینده با (gateway, gateway_ref) پیدا و با مبلغ پرداخت‌شده تطبیق داده می‌شود؛ اعتبار فقط یک‌بار */
function botTopupGatewayDone(PDO $db, array $bot, string $gateway, string $ref, int $paid): array {
    if ($gateway === '' || $ref === '') return ['ok' => false, 'msg' => 'سفارش پیدا نشد'];
    $s = $db->prepare("SELECT id FROM tg_orders WHERE bot_id=? AND agent_id=? AND kind='topup' AND gateway=? AND gateway_ref=?");
    $s->execute([(int)$bot['id'], (int)$bot['agent_id'], $gateway, $ref]);
    $oid = (int)$s->fetchColumn();
    if ($oid <= 0) return ['ok' => false, 'msg' => 'سفارش پیدا نشد'];
    $r = botTopupCredit($db, $bot, $oid, ['awaiting_receipt', 'pending_review', 'pending_gateway'], $paid);
    if (!$r['ok']) return ['ok' => false, 'msg' => $r['msg']];
    botAudit($db, $bot, 0, 'topup_gateway', 'order:' . $oid, ['gateway' => mb_substr($gateway, 0, 20), 'amount' => $r['amount']]);
    botTopupNotify($db, $bot, $r);
    return ['ok' => true, 'msg' => 'تأیید شد'];
}

// ---- تاریخچه‌ها
/** دلیل ثبت‌شده‌ی تراکنش کیف پول → برچسب فارسی */
function botTxLabel(string $reason): string {
    $m = ['welcome gift' => 'هدیه‌ی عضویت', 'cashback' => 'کش‌بک خرید', 'referral' => 'پاداش دعوت دوستان', 'topup' => 'شارژ کیف پول', 'refund' => 'بازگشت وجه',
          'admin adjp' => 'افزایش توسط مدیر', 'admin adjm' => 'کاهش توسط مدیر'];
    if (isset($m[$reason])) return $m[$reason];
    if (preg_match('/^buy plan \d+$/', $reason)) return 'خرید اشتراک با موجودی';
    if (preg_match('/^renew account \d+$/', $reason)) return 'تمدید حساب با موجودی';
    if (preg_match('/^traffic account \d+$/', $reason)) return 'حجم اضافه با موجودی';
    return 'سایر';
}
function botOrderStatusLabel(string $st): string {
    return ['awaiting_receipt' => 'در انتظار رسید', 'pending_review' => 'در انتظار تأیید', 'approving' => 'در حال بررسی', 'approved' => 'تأیید شده', 'rejected' => 'رد شده',
            'cancelled' => 'لغو شده', 'pending_gateway' => 'در انتظار پرداخت آنلاین'][$st] ?? 'نامشخص';
}
/** ردیف دکمه‌های صفحه‌بندی؛ $key = tx یا od */
function botPageRow(string $key, int $page, bool $more): array {
    $r = [];
    if ($page > 0) $r[] = botAB('◀️ قبلی', $key . ':' . ($page - 1));
    if ($more) $r[] = botAB('بعدی ▶️', $key . ':' . ($page + 1));
    return $r;
}
/** «تراکنش‌های من»: فقط tg_wallet_tx همین ربات و همین کاربر، ۱۰تایی */
function botMyTx(PDO $db, array $bot, array $cfg, array $u, int $page): void {
    $chat = (int)$u['chat_id']; $page = max(0, min($page, 1000));
    $s = $db->prepare('SELECT delta, balance_after, reason, created_at FROM tg_wallet_tx WHERE bot_id=? AND user_id=? ORDER BY id DESC LIMIT 11 OFFSET ' . ($page * 10));
    $s->execute([(int)$bot['id'], (int)$u['id']]);
    $rows = $s->fetchAll(PDO::FETCH_ASSOC); $more = count($rows) > 10; $rows = array_slice($rows, 0, 10);
    if (!$rows) { botSay($db, $bot, $chat, $page === 0 ? 'هنوز تراکنشی ندارید.' : 'تراکنش بیشتری وجود ندارد.', [[botBL($cfg, 'back', ['callback_data' => 'm:wal'])]]); return; }
    $txt = "📒 <b>تراکنش‌های من</b>\n";
    foreach ($rows as $r) {
        $d = (int)$r['delta'];
        $txt .= "\n" . date('Y/m/d H:i', (int)$r['created_at']) . ' — ' . ($d >= 0 ? '➕ ' : '➖ ') . botMoney(abs($d)) . ' — ' . bh(botTxLabel((string)$r['reason'])) . ' — مانده: ' . botMoney((int)$r['balance_after']);
    }
    $kb = []; $nav = botPageRow('tx', $page, $more); if ($nav) $kb[] = $nav;
    $kb[] = [botBL($cfg, 'back', ['callback_data' => 'm:wal'])];
    botSay($db, $bot, $chat, $txt, $kb);
}
/** «سفارش‌های من»: فقط tg_orders همین ربات و همین چت، ۱۰تایی */
function botMyOrders(PDO $db, array $bot, array $cfg, array $u, int $page): void {
    $chat = (int)$u['chat_id']; $page = max(0, min($page, 1000));
    $s = $db->prepare('SELECT id, kind, plan_snapshot, price, status, created_at FROM tg_orders WHERE bot_id=? AND chat_id=? ORDER BY id DESC LIMIT 11 OFFSET ' . ($page * 10));
    $s->execute([(int)$bot['id'], $chat]);
    $rows = $s->fetchAll(PDO::FETCH_ASSOC); $more = count($rows) > 10; $rows = array_slice($rows, 0, 10);
    if (!$rows) { botSay($db, $bot, $chat, $page === 0 ? 'هنوز سفارشی ندارید.' : 'سفارش بیشتری وجود ندارد.', botMn($db, $bot, $cfg, $chat)); return; }
    $txt = "🧾 <b>سفارش‌های من</b>\n";
    foreach ($rows as $r) {
        $pl = json_decode((string)$r['plan_snapshot'], true) ?: [];
        $title = (string)$r['kind'] === 'topup' ? 'شارژ کیف پول' : (string)($pl['name'] ?? 'اشتراک');
        $txt .= "\n#" . (int)$r['id'] . ' — ' . date('Y/m/d H:i', (int)$r['created_at']) . ' — ' . bh($title) . ' — ' . botMoney((int)$r['price']) . ' — ' . bh(botOrderStatusLabel((string)$r['status']));
    }
    $kb = []; $nav = botPageRow('od', $page, $more); if ($nav) $kb[] = $nav;
    $kb[] = [botBL($cfg, 'back', ['callback_data' => 'm:home'])];
    botSay($db, $bot, $chat, $txt, $kb);
}
/**
 * ثبت مجدد منوی «/» بعد از تغییر لیست کامندها: نسخه‌ی لیست (crc32) در tg_counters ذخیره می‌شود و فقط وقتی عوض شده باشد، یک‌بار برای همین ربات
 * botCommandsRegister اجرا می‌شود؛ از مسیر ادمین‌های ربات صدا زده می‌شود. اگر هیچ درخواستی موفق نبود، نسخه صفر می‌شود تا دفعه‌ی بعد دوباره تلاش شود.
 */
function botCommandsSync(PDO $db, array $bot): void {
    $ver = (int)sprintf('%u', crc32((string)json_encode(botCommandList(false), JSON_UNESCAPED_UNICODE))); $bid = (int)$bot['id'];
    $db->prepare('INSERT OR IGNORE INTO tg_counters (bot_id, name, val) VALUES (?,?,0)')->execute([$bid, 'cmd_v']);
    $u = $db->prepare('UPDATE tg_counters SET val=? WHERE bot_id=? AND name=? AND val<>?'); $u->execute([$ver, $bid, 'cmd_v', $ver]);
    if ($u->rowCount() !== 1) return;
    $r = botCommandsRegister($db, $bot);
    if ((int)$r['ok'] === 0) $db->prepare('UPDATE tg_counters SET val=0 WHERE bot_id=? AND name=?')->execute([$bid, 'cmd_v']);
}

// ------------------------------------------------------------------ منوی «/» (کامندها)
/** رجیستری کامندهای کاربر؛ مرحله‌های بعد همین‌جا کامند اضافه می‌کنند. cb = دکمه‌ی معادل (k:v) و با همان گیت‌ها اجرا می‌شود. */
function botUserCommands(): array {
    return [
        'start'    => ['desc' => 'شروع و منوی اصلی',        'cb' => 'm:home'],
        'buy'      => ['desc' => 'خرید اشتراک',             'cb' => 'm:buy'],
        'test'     => ['desc' => 'دریافت اکانت تست',        'cb' => 'm:test'],
        'wallet'   => ['desc' => 'کیف پول و دعوت دوستان',   'cb' => 'm:wal'],
        'accounts' => ['desc' => 'حساب‌های من',             'cb' => 'm:acc'],
        'orders'   => ['desc' => 'سفارش‌های من',            'cb' => 'm:ord'],
        'support'  => ['desc' => 'پشتیبانی',                'cb' => 'm:sup'],
        'help'     => ['desc' => 'راهنما و سوالات متداول',  'cb' => 'm:help'],
    ];
}
/** فرمت setMyCommands؛ $admin=true کامند /admin را هم دارد */
function botCommandList(bool $admin): array {
    $o = [];
    foreach (botUserCommands() as $k => $c) $o[] = ['command' => (string)$k, 'description' => (string)$c['desc']];
    if ($admin) $o[] = ['command' => 'admin', 'description' => 'پنل مدیریت ربات'];
    return $o;
}
/**
 * کامندهای قدیمی (scopeهای default و all_private_chats با زبان‌های بدون‌زبان/fa/en) پاک و کامندهای جدید ثبت می‌شود؛
 * /admin فقط برای chat idهای مالک و ادمین‌های همین ربات با scope از نوع chat. همه‌ی درخواست‌ها فقط با توکن همین ربات.
 * @return array{ok:int,failed:int}
 */
function botCommandsRegister(PDO $db, array $bot): array {
    $ok = 0; $bad = 0;
    $call = function (string $m, array $p) use ($db, $bot, &$ok, &$bad): void { $r = botTg($db, $bot, $m, $p); if (!empty($r['ok'])) $ok++; else $bad++; };
    $scopes = [['type' => 'default'], ['type' => 'all_private_chats']];
    foreach ($scopes as $sc) foreach (['', 'fa', 'en'] as $lc) {
        $p = ['scope' => $sc];
        if ($lc !== '') $p['language_code'] = $lc;
        $call('deleteMyCommands', $p);
    }
    foreach ($scopes as $sc) $call('setMyCommands', ['scope' => $sc, 'commands' => botCommandList(false)]);
    foreach (botStaffChats($db, $bot) as $c) $call('setMyCommands', ['scope' => ['type' => 'chat', 'chat_id' => $c], 'commands' => botCommandList(true)]);
    return ['ok' => $ok, 'failed' => $bad];
}
/** null = کامند نیست؛ وگرنه ['cmd','arg','other'] (other = خطاب به رباتِ دیگر: /buy@other_bot) */
function botParseCommand(array $bot, string $text): ?array {
    if ($text === '' || $text[0] !== '/') return null;
    if (!preg_match('~^/([A-Za-z0-9_]{1,32})(?:@([A-Za-z0-9_]{3,64}))?(?:\s+(.*))?$~su', $text, $m)) return ['cmd' => '', 'arg' => '', 'other' => false];
    $to = (string)($m[2] ?? '');
    return ['cmd' => strtolower($m[1]), 'arg' => trim((string)($m[3] ?? '')), 'other' => $to !== '' && strcasecmp($to, (string)$bot['bot_username']) !== 0];
}

// ------------------------------------------------------------------ عضویت اجباری (گیت)
/** عملیات‌های گیت‌شونده → دکمه‌ای که بعد از «عضو شدم» اجرا می‌شود (مرحله‌های بعد شارژ/تمدید را اینجا وصل می‌کنند) */
function botGateActions(): array { return ['buy' => 'm:buy', 'test' => 'm:test', 'charge' => 'm:topup', 'renew' => 'm:home']; }
/** هشدار «بررسی عضویت ممکن نیست» حداکثر روزی یک‌بار به مالک ربات */
function botFjErrorNotice(PDO $db, array $bot): void {
    $day = (int)date('Ymd'); $bid = (int)$bot['id'];
    $db->prepare('INSERT OR IGNORE INTO tg_counters (bot_id, name, val) VALUES (?,?,0)')->execute([$bid, 'fj_err_day']);
    $u = $db->prepare('UPDATE tg_counters SET val=? WHERE bot_id=? AND name=? AND val<>?'); $u->execute([$day, $bid, 'fj_err_day', $day]);
    if ($u->rowCount() === 1) botEvent($db, $bot, 'error', "⚠️ بررسی عضویت اجباری انجام نشد (تلگرام خطا داد).\nربات را در کانال‌های «عضویت اجباری» ادمین کنید. تا آن زمان این شرط اعمال نمی‌شود.");
}
/**
 * قبل از خرید، تست، شارژ و تمدید صدا زده می‌شود. true = ادامه بده؛ false = پیام عضویت فرستاده شد.
 * ادمین‌ها معاف‌اند. نتیجه‌ی مثبت ۶۰ ثانیه در fj_ok_until کش می‌شود. اگر API خطا بدهد fail-open است.
 */
function botGate(PDO $db, array $bot, array $cfg, array $u, string $action): bool {
    if ((int)$cfg['fj_on'] !== 1) return true;
    $chans = botFjParse($cfg);
    if (!$chans) return true;
    $chat = (int)$u['chat_id'];
    if (botIsStaff($db, $bot, $chat)) return true;
    $now = time();
    if ((int)($u['fj_ok_until'] ?? 0) > $now) return true;
    $miss = []; $err = false;
    foreach ($chans as $c) {
        $r = botTg($db, $bot, 'getChatMember', ['chat_id' => $c['chat'], 'user_id' => $chat]);
        $st = (string)($r['result']['status'] ?? '');
        if (empty($r['ok']) || $st === '') { $err = true; continue; }
        $in = in_array($st, ['member', 'administrator', 'creator'], true) || ($st === 'restricted' && !empty($r['result']['is_member']));
        if (!$in) $miss[] = $c;
    }
    if ($err) botFjErrorNotice($db, $bot);
    if (!$miss) {
        if (!$err) $db->prepare('UPDATE tg_users SET fj_ok_until=? WHERE id=? AND bot_id=?')->execute([$now + 60, (int)$u['id'], (int)$bot['id']]);
        return true;
    }
    $kb = [];
    foreach ($miss as $c) if ($c['link'] !== '') $kb[] = [['text' => '📢 عضویت در ' . $c['label'], 'url' => $c['link']]];
    $kb[] = [botAB('✅ عضو شدم', 'fj:' . (preg_replace('/[^a-z]/', '', $action) ?: 'buy'), 'success')];
    botSay($db, $bot, $chat, "برای ادامه، ابتدا در کانال‌های زیر عضو شوید و سپس دکمه‌ی «عضو شدم» را بزنید:\n\n" . implode("\n", array_map(fn($c) => '• ' . bh($c['label']), $miss)), $kb);
    return false;
}

// ------------------------------------------------------------------ مدیریت ادمین‌ها (فقط مالک)
function botAdminSetCommands(PDO $db, array $bot, int $chat, bool $on): void {
    if ($chat <= 0) return;
    try {
        if ($on) botTg($db, $bot, 'setMyCommands', ['scope' => ['type' => 'chat', 'chat_id' => $chat], 'commands' => botCommandList(true)]);
        else botTg($db, $bot, 'deleteMyCommands', ['scope' => ['type' => 'chat', 'chat_id' => $chat]]);
    } catch (Throwable $e) { error_log('botAdminSetCommands: ' . get_class($e)); }
}
function botAdminAdd(PDO $db, array $bot, int $actor, int $chat, array $perms): array {
    if (!botIsOwner($bot, $actor)) return ['ok' => false, 'msg' => 'فقط مالک ربات می‌تواند ادمین‌ها را مدیریت کند.'];
    if ($chat <= 0) return ['ok' => false, 'msg' => 'chat id نامعتبر است.'];
    if (botIsOwner($bot, $chat)) return ['ok' => false, 'msg' => 'این chat id مالک ربات است و همه‌ی مجوزها را دارد.'];
    $n = $db->prepare('SELECT COUNT(*) FROM tg_bot_admins WHERE bot_id=?'); $n->execute([(int)$bot['id']]);
    if ((int)$n->fetchColumn() >= 20) return ['ok' => false, 'msg' => 'حداکثر ۲۰ ادمین مجاز است.'];
    $p = implode(',', botPermsParse(implode(',', $perms)));
    $ins = $db->prepare('INSERT OR IGNORE INTO tg_bot_admins (bot_id, chat_id, perms, added_by, created_at) VALUES (?,?,?,?,?)');
    $ins->execute([(int)$bot['id'], $chat, $p, $actor, time()]);
    if ($ins->rowCount() !== 1) return ['ok' => false, 'msg' => 'این ادمین قبلاً اضافه شده است.'];
    botAudit($db, $bot, $actor, 'admin_add', 'chat:' . $chat, ['perms' => $p]);
    botAdminSetCommands($db, $bot, $chat, true);
    return ['ok' => true, 'msg' => 'ادمین اضافه شد.'];
}
function botAdminSetPerms(PDO $db, array $bot, int $actor, int $chat, array $perms): array {
    if (!botIsOwner($bot, $actor)) return ['ok' => false, 'msg' => 'فقط مالک ربات می‌تواند ادمین‌ها را مدیریت کند.'];
    $p = implode(',', botPermsParse(implode(',', $perms)));
    $up = $db->prepare('UPDATE tg_bot_admins SET perms=? WHERE bot_id=? AND chat_id=?'); $up->execute([$p, (int)$bot['id'], $chat]);
    if ($up->rowCount() !== 1) return ['ok' => false, 'msg' => 'ادمین پیدا نشد.'];
    botAudit($db, $bot, $actor, 'admin_perms', 'chat:' . $chat, ['perms' => $p]);
    return ['ok' => true, 'msg' => 'مجوزها ذخیره شد.'];
}
function botAdminRemove(PDO $db, array $bot, int $actor, int $chat): array {
    if (!botIsOwner($bot, $actor)) return ['ok' => false, 'msg' => 'فقط مالک ربات می‌تواند ادمین‌ها را مدیریت کند.'];
    if (botIsOwner($bot, $chat)) return ['ok' => false, 'msg' => 'مالک ربات قابل حذف نیست.'];
    $d = $db->prepare('DELETE FROM tg_bot_admins WHERE bot_id=? AND chat_id=?'); $d->execute([(int)$bot['id'], $chat]);
    if ($d->rowCount() !== 1) return ['ok' => false, 'msg' => 'ادمین پیدا نشد.'];
    $ph = implode(',', array_fill(0, count(botAdminStates()), '?'));
    $db->prepare("UPDATE tg_users SET state='', state_val=0 WHERE bot_id=? AND chat_id=? AND state IN ($ph)")->execute(array_merge([(int)$bot['id'], $chat], botAdminStates()));
    botAudit($db, $bot, $actor, 'admin_remove', 'chat:' . $chat);
    botAdminSetCommands($db, $bot, $chat, false);
    return ['ok' => true, 'msg' => 'ادمین حذف شد.'];
}
/** ردیف ادمینِ همین ربات با شناسه‌ی ردیف (ضد IDOR) */
function botAdminRow(PDO $db, array $bot, int $rowId): ?array {
    $s = $db->prepare('SELECT * FROM tg_bot_admins WHERE id=? AND bot_id=?'); $s->execute([$rowId, (int)$bot['id']]);
    $r = $s->fetch(PDO::FETCH_ASSOC);
    return $r ?: null;
}
function botAdminList(PDO $db, array $bot, int $chat): void {
    $own = botIsOwner($bot, $chat);
    $s = $db->prepare('SELECT * FROM tg_bot_admins WHERE bot_id=? ORDER BY id LIMIT 50'); $s->execute([(int)$bot['id']]);
    $rows = $s->fetchAll(PDO::FETCH_ASSOC);
    $txt = "👥 <b>ادمین‌های ربات</b>\nمالک: " . ((string)$bot['admin_chat_id'] !== '' ? '<code>' . bh((string)$bot['admin_chat_id']) . '</code>' : '—') . " (همه‌ی مجوزها، غیرقابل حذف)\n"; $kb = [];
    foreach ($rows as $r) {
        $pn = botPermsParse((string)$r['perms']);
        $txt .= "\n• <code>" . (int)$r['chat_id'] . '</code> — ' . count($pn) . ' مجوز';
        if ($own) $kb[] = [botAB((string)$r['chat_id'] . ' — ' . count($pn) . ' مجوز', 'a:ae:' . (int)$r['id'])];
    }
    if (!$rows) $txt .= "\nادمین دیگری ثبت نشده است.";
    if ($own) $kb[] = [botAB('➕ افزودن ادمین', 'a:aa', 'success')];
    else $txt .= "\n\nفقط مالک ربات می‌تواند ادمین‌ها را تغییر دهد.";
    $kb[] = [botAB('بازگشت', 'a:home')];
    botSay($db, $bot, $chat, $txt, $kb);
}
function botAdminEdit(PDO $db, array $bot, int $chat, int $rowId): void {
    $r = botAdminRow($db, $bot, $rowId);
    if (!$r) { botSay($db, $bot, $chat, 'پیدا نشد.', [[botAB('بازگشت', 'a:ad')]]); return; }
    $has = botPermsParse((string)$r['perms']); $kb = []; $i = 0;
    $agOk = botPermAgentsOk($db, $bot);
    foreach (botPermList() as $k => $title) {
        if ($k === 'agents' && !$agOk) { $i++; continue; }
        $on = in_array($k, $has, true);
        $kb[] = [botAB($title . ': ' . ($on ? 'روشن ✅' : 'خاموش ⛔'), 'a:ap:' . $rowId . ':' . $i, $on ? 'success' : 'danger')];
        $i++;
    }
    $kb[] = [botAB('🗑 حذف این ادمین', 'a:ar:' . $rowId, 'danger')];
    $kb[] = [botAB('بازگشت', 'a:ad')];
    botSay($db, $bot, $chat, "👤 <b>مجوزهای ادمین</b> <code>" . (int)$r['chat_id'] . "</code>\nبا زدن هر مورد، مجوز روشن/خاموش می‌شود.\nادمین باید حداقل یک‌بار ربات را استارت کرده باشد.", $kb);
}

// ------------------------------------------------------------------ پنل مدیریت داخل ربات (مالک + ادمین‌ها بر اساس مجوز)
function botSetList(): array {
    return [['t_on', 'دریافت تست', 'toggle'], ['t_count', 'تعداد تست هر کاربر (۰ = نامحدود)', 'num'], ['t_gb', 'حجم تست (گیگ، ۰ = نامحدود)', 'num'], ['t_days', 'مدت تست (روز، ۰ = بدون انقضا)', 'num'],
            ['g_on', 'هدیه‌ی عضویت', 'toggle'], ['g_amt', 'مبلغ هدیه‌ی عضویت (تومان)', 'num'],
            ['cb_on', 'کش‌بک خرید', 'toggle'], ['cb_pct', 'درصد کش‌بک', 'num'], ['cb_max', 'سقف کش‌بک (تومان، ۰ = بدون سقف)', 'num'],
            ['ref_on', 'دعوت دوستان', 'toggle'], ['ref_amt', 'پاداش دعوت (تومان)', 'num'],
            ['promo_on', 'تخفیف همگانی روی پلن‌ها', 'toggle'], ['promo_pct', 'درصد تخفیف همگانی', 'num'],
            ['topup_on', 'شارژ کیف پول توسط مشتری', 'toggle'], ['topup_min', 'حداقل مبلغ شارژ (تومان)', 'num'], ['topup_max', 'حداکثر مبلغ شارژ (تومان، ۰ = بدون سقف)', 'num'],
            ['card_mode', 'نمایش کارت‌ها', 'mode'], ['traffic_packs', 'بسته‌های حجم اضافه (JSON)', 'json'], ['alerts_on', 'هشدار انقضا و مصرف حجم', 'toggle'], ['tk_max_open', 'سقف تیکت باز هر کاربر (۱ تا ۵۰)', 'num'],
            ['club_on', 'باشگاه مشتریان', 'toggle'], ['club_points_day', 'امتیاز چک‌این روزانه', 'num'], ['club_streak_n', 'بونوس هر چند روز متوالی (۰ = بدون بونوس)', 'num'],
            ['club_streak_bonus', 'امتیاز بونوس روزهای متوالی', 'num'], ['club_rate', 'ارزش هر امتیاز (تومان)', 'num'], ['club_min_convert', 'حداقل امتیاز برای تبدیل', 'num'],
            ['backup_on', 'بکاپ خودکار', 'toggle'], ['backup_every', 'دوره‌ی بکاپ خودکار', 'mode']];
}
/** مقدار نمایشی تنظیمِ نوع mode (دو حالتی: all | rotate) */
function botModeLabel(string $key, string $v): string {
    if ($key === 'card_mode') return $v === 'rotate' ? 'چرخشی (هر سفارش یک کارت) ✅' : 'همه (تا ۳ کارت) ⛔';
    if ($key === 'backup_every') return $v === 'week' ? 'هفتگی' : 'روزانه';
    return $v;
}
function botAdminHome(PDO $db, array $bot, int $chat): void {
    $P = botAdminPerms($db, $bot, $chat);
    $has = fn(string $p): bool => in_array($p, $P, true);
    $head = '🛠 <b>پنل مدیریت ربات</b>';
    if ($has('orders')) { $p = $db->prepare("SELECT COUNT(*) FROM tg_orders WHERE bot_id=? AND status='pending_review'"); $p->execute([(int)$bot['id']]); $head .= "\nسفارش در انتظار بررسی: " . (int)$p->fetchColumn(); }
    $kb = []; $r = [];
    if ($has('stats')) $r[] = botAB('آمار', 'a:st:menu', 'primary');
    if ($has('users')) $r[] = botAB('جست‌وجوی کاربر', 'a:find', 'primary');
    if ($r) $kb[] = $r;
    $r = [];
    if ($has('settings')) $r[] = botAB('تنظیمات، هدیه و کش‌بک', 'a:set', 'success');
    if ($has('broadcast')) $r[] = botAB('پیام همگانی', 'a:bc');
    if ($r) $kb[] = $r;
    if ($has('orders')) $kb[] = [botAB('سفارش‌های در انتظار', 'a:pend')];
    if ($has('tickets')) $kb[] = [botAB('🎫 تیکت‌های باز', 'a:tk:0')];
    if ($has('settings')) { $kb[] = [botAB('📚 آموزش‌ها و سوالات متداول', 'a:tu')]; $kb[] = [botAB('📡 گزارش رویدادها', 'a:ev')]; $kb[] = [botAB('🏷 کدهای تخفیف', 'a:cp')]; $kb[] = [botAB('گزارش فعالیت ادمین‌ها', 'a:audit'), botAB('ثبت مجدد کامندها', 'a:cmd')]; $kb[] = [botAB('💾 بکاپ داده‌های ربات', 'a:bk')]; }
    if ($has('agents')) $kb[] = [botAB('🤝 نمایندگان', 'a:ag:l:0', 'primary')];
    if ($has('admins')) $kb[] = [botAB('ادمین‌ها', 'a:ad')];
    $kb[] = [botAB('بازگشت به منو', 'm:home')];
    botSay($db, $bot, $chat, $head, $kb);
}
function botStatsText(PDO $db, int $botId, int $since, string $title): string {
    $q = function (string $sql, array $a) use ($db): array { $s = $db->prepare($sql); $s->execute($a); return (array)$s->fetch(PDO::FETCH_NUM); };
    [$nu] = $q('SELECT COUNT(*) FROM tg_users WHERE bot_id=? AND created_at>=?', [$botId, $since]);
    [$nt] = $q("SELECT COUNT(*) FROM tg_accts WHERE bot_id=? AND kind='test' AND created_at>=?", [$botId, $since]);
    [$ns, $rev] = $q("SELECT COUNT(*), COALESCE(SUM(price),0) FROM tg_orders WHERE bot_id=? AND status='approved' AND updated_at>=?", [$botId, $since]);
    [$nw] = $q("SELECT COUNT(*) FROM tg_orders WHERE bot_id=? AND status='approved' AND tracking='wallet' AND updated_at>=?", [$botId, $since]);
    [$pend] = $q("SELECT COUNT(*) FROM tg_orders WHERE bot_id=? AND status='pending_review'", [$botId]);
    [$tot, $bal] = $q('SELECT COUNT(*), COALESCE(SUM(balance),0) FROM tg_users WHERE bot_id=?', [$botId]);
    return "📊 <b>آمار — " . $title . "</b>\n\nکاربر جدید: " . (int)$nu . "\nتست داده‌شده: " . (int)$nt . "\nفروش: " . (int)$ns . ' (از موجودی: ' . (int)$nw . ")\nدرآمد: " . botMoney((int)$rev)
        . "\n\nسفارش در انتظار: " . (int)$pend . "\nکل کاربران ربات: " . (int)$tot . "\nمجموع موجودی کیف پول کاربران: " . botMoney((int)$bal);
}
function botFind(PDO $db, array $bot, string $q): array {
    $q = trim($q);
    if ($q === '') return [];
    $bid = (int)$bot['id'];
    if (preg_match('/^-?\d{4,20}$/', $q)) {
        $s = $db->prepare('SELECT * FROM tg_users WHERE bot_id=? AND chat_id=? LIMIT 8'); $s->execute([$bid, (int)$q]);
        return $s->fetchAll(PDO::FETCH_ASSOC);
    }
    $like = '%' . str_replace(['\\', '%', '_'], ['\\\\', '\\%', '\\_'], ltrim($q, '@')) . '%';
    $s = $db->prepare("SELECT DISTINCT u.* FROM tg_users u LEFT JOIN tg_accts t ON t.bot_id=u.bot_id AND t.chat_id=u.chat_id LEFT JOIN accounts a ON a.id=t.account_id
        WHERE u.bot_id=? AND (LOWER(u.username)=LOWER(?) OR a.email LIKE ? ESCAPE '\\') LIMIT 8");
    $s->execute([$bid, ltrim($q, '@'), $like]);
    return $s->fetchAll(PDO::FETCH_ASSOC);
}
/** کاربرِ همین ربات با شناسه‌ی ردیف؛ نبودن (یا مالِ ربات دیگر) = null */
function botUserOwned(PDO $db, array $bot, int $uid): ?array {
    $s = $db->prepare('SELECT * FROM tg_users WHERE id=? AND bot_id=?'); $s->execute([$uid, (int)$bot['id']]);
    $u = $s->fetch(PDO::FETCH_ASSOC);
    return $u ?: null;
}
function botUserCard(PDO $db, array $bot, int $adminChat, int $uid): void {
    $u = botUserOwned($db, $bot, $uid);
    if (!$u) { botSay($db, $bot, $adminChat, 'کاربر پیدا نشد.'); return; }
    $a = $db->prepare('SELECT a.email, t.kind FROM tg_accts t JOIN accounts a ON a.id=t.account_id WHERE t.bot_id=? AND t.chat_id=? ORDER BY t.id DESC LIMIT 6');
    $a->execute([(int)$bot['id'], (int)$u['chat_id']]);
    $o = $db->prepare("SELECT COUNT(*), COALESCE(SUM(price),0) FROM tg_orders WHERE bot_id=? AND chat_id=? AND status='approved'"); $o->execute([(int)$bot['id'], (int)$u['chat_id']]);
    [$oc, $os] = (array)$o->fetch(PDO::FETCH_NUM);
    $banned = (int)$u['banned'] === 1;
    $txt = "👤 <b>کاربر</b>\nchat id: <code>" . (int)$u['chat_id'] . "</code>\nیوزرنیم: " . ((string)$u['username'] !== '' ? '@' . bh((string)$u['username']) : '—')
         . "\nموجودی: <b>" . botMoney((int)$u['balance']) . "</b>\nتست دریافت‌شده: " . (int)$u['tests_used']
         . "\nخرید تأییدشده: " . (int)$oc . ' (' . botMoney((int)$os) . ")\nوضعیت: " . ($banned ? '⛔ مسدود' : 'فعال');
    foreach ($a->fetchAll(PDO::FETCH_ASSOC) as $r) $txt .= "\n• <code>" . bh((string)$r['email']) . '</code> — ' . ($r['kind'] === 'test' ? 'تست' : 'اشتراک');
    $kb = [];
    if (botCan($db, $bot, $adminChat, 'wallet')) $kb[] = [botAB('افزایش موجودی', 'a:bp:' . $uid, 'success'), botAB('کسر موجودی', 'a:bm:' . $uid, 'danger')];
    if (botCan($db, $bot, $adminChat, 'users')) $kb[] = [botAB('ریست تست', 'a:rt:' . $uid, 'primary'), botAB($banned ? 'آزاد کردن' : 'مسدود کردن', 'a:bn:' . $uid, $banned ? 'success' : 'danger')];
    $kb[] = [botAB('بازگشت', 'a:home')];
    botSay($db, $bot, $adminChat, $txt, $kb);
}
/** چیدمان منوی اصلی: روشن/خاموش، جابه‌جایی بالا/پایین، کنار هم یا زیر هم */
function botAdminMenuLayout(PDO $db, array $bot, array $agent, int $chat): void {
    $cfg = botCfg($db, (int)$agent['id']); $labels = botMenuKeys(); $kb = []; $txt = "🧩 <b>چیدمان منوی ربات</b>\n";
    $n = count($cfg['menu']);
    foreach ($cfg['menu'] as $i => $it) {
        $k = (string)$it['k']; $name = isset($cfg['btn'][$k]) ? (string)$cfg['btn'][$k]['l'] : $labels[$k];
        $txt .= ($i + 1) . ') ' . bh($name) . ($it['on'] ? '' : ' ⛔') . ($it['j'] && $i > 0 ? ' ↔️' : '') . "\n";
        $row = [botAB(($it['on'] ? '✅ ' : '⛔ ') . $name, 'a:mt:' . $i, $it['on'] ? 'success' : 'danger')];
        if ($i > 0) $row[] = botAB('⬆️', 'a:mu:' . $i);
        if ($i < $n - 1) $row[] = botAB('⬇️', 'a:mu:' . ($i + 1));
        if ($i > 0) $row[] = botAB($it['j'] ? '↔️' : '↕️', 'a:mj:' . $i);
        $kb[] = $row;
    }
    $txt .= "\n✅/⛔ روشن یا خاموش‌کردن دکمه · ⬆️⬇️ جابه‌جایی · ↔️ کنارِ دکمه‌ی قبلی / ↕️ ردیف جدا\nدکمه‌های «تست»، «آموزش‌ها»، «سوالات متداول» و «باشگاه» فقط وقتی نمایش داده می‌شوند که آن بخش فعال/دارای محتوا باشد.";
    $kb[] = [botAB('بازگشت', 'a:set')];
    botSay($db, $bot, $chat, $txt, $kb);
}
function botAdminSettings(PDO $db, array $bot, array $agent, int $chat): void {
    $cfg = botCfg($db, (int)$agent['id']); $kb = [];
    foreach (botSetList() as $i => $s) {
        $v = $cfg[$s[0]];
        if ($s[2] === 'toggle') $kb[] = [botAB($s[1] . ': ' . ((int)$v === 1 ? 'روشن ✅' : 'خاموش ⛔'), 'a:tg:' . $i, (int)$v === 1 ? 'success' : 'danger')];
        elseif ($s[2] === 'mode') $kb[] = [botAB($s[1] . ': ' . botModeLabel((string)$s[0], (string)$v), 'a:tg:' . $i, $v === 'rotate' ? 'success' : '')];
        elseif ($s[2] === 'json') $kb[] = [botAB($s[1] . ': ' . (count((array)$v) > 0 ? count((array)$v) . ' بسته' : 'خالی'), 'a:ed:' . $i)];
        else $kb[] = [botAB($s[1] . ': ' . $v, 'a:ed:' . $i)];
    }
    $kb[] = [botAB('🧩 چیدمان و روشن/خاموش‌کردن دکمه‌های منو', 'a:mn', 'primary')];
    $kb[] = [botAB('🎨 ایموجی‌های پریمیوم', 'a:em', 'primary')];
    $kb[] = [botAB('🏷 کدهای تخفیف', 'a:cp')];
    $kb[] = [botAB('📢 عضویت اجباری در کانال: ' . ((int)$cfg['fj_on'] === 1 ? 'روشن ✅' : 'خاموش ⛔'), 'a:fj')];
    $kb[] = [botAB('بازگشت', 'a:home')];
    botSay($db, $bot, $chat, "⚙️ <b>تنظیمات ربات</b>\nبا زدن هر مورد، روشن/خاموش یا مقدارش تغییر می‌کند.\nهدیه، کش‌بک، دعوت دوستان و تخفیف همگانی ابزارهای جذب مشتری‌اند.", $kb);
}
function botAdminFj(PDO $db, array $bot, array $agent, int $chat): void {
    $cfg = botCfg($db, (int)$agent['id']); $on = (int)$cfg['fj_on'] === 1;
    $txt = "📢 <b>عضویت اجباری</b>\nوضعیت: " . ($on ? 'روشن ✅' : 'خاموش ⛔') . "\nکاربران عادی قبل از خرید، تست، شارژ و تمدید باید در این کانال‌ها عضو باشند (ادمین‌ها معاف‌اند).\n\nکانال‌ها:";
    foreach ((array)$cfg['fj'] as $l) $txt .= "\n• " . bh((string)$l);
    if (!$cfg['fj']) $txt .= "\n(خالی — تا کانالی ثبت نشود شرط اعمال نمی‌شود)";
    $txt .= "\n\n⚠️ ربات باید در همه‌ی این کانال‌ها ادمین باشد.";
    botSay($db, $bot, $chat, $txt, [[botAB('عضویت اجباری: ' . ($on ? 'روشن ✅' : 'خاموش ⛔'), 'a:fjt', $on ? 'success' : 'danger')], [botAB('ویرایش لیست کانال‌ها', 'a:fje', 'primary')], [botAB('بازگشت', 'a:set')]]);
}
// ---- مدیریت کد تخفیف در پنل ربات (مجوز settings)
function botCouponRow(PDO $db, array $bot, int $id): ?array {
    $s = $db->prepare('SELECT * FROM tg_coupons WHERE id=? AND bot_id=?'); $s->execute([$id, (int)$bot['id']]);
    $r = $s->fetch(PDO::FETCH_ASSOC);
    return $r ?: null;
}
function botCouponValueLabel(array $c): string { return (string)$c['kind'] === 'amount' ? botMoney((int)$c['value']) : (int)$c['value'] . '٪'; }
function botAdminCoupons(PDO $db, array $bot, int $chat, int $page = 0): void {
    $page = max(0, min($page, 1000));
    $s = $db->prepare('SELECT * FROM tg_coupons WHERE bot_id=? ORDER BY id DESC LIMIT 11 OFFSET ' . ($page * 10)); $s->execute([(int)$bot['id']]);
    $rows = $s->fetchAll(PDO::FETCH_ASSOC); $more = count($rows) > 10; $rows = array_slice($rows, 0, 10);
    $txt = "🏷 <b>کدهای تخفیف</b>\nکد تخفیف بعد از تخفیف همگانی اعمال می‌شود و روی شارژ کیف پول کاربرد ندارد.";
    if (!$rows) $txt .= $page === 0 ? "\n\nهنوز کدی ثبت نشده است." : "\n\nکد بیشتری وجود ندارد.";
    $kb = [];
    foreach ($rows as $c) $kb[] = [botAB(($c['active'] ? '✅ ' : '⛔ ') . $c['code'] . ' — ' . botCouponValueLabel($c) . ' — ' . (int)$c['used'] . '/' . ((int)$c['max_uses'] > 0 ? (int)$c['max_uses'] : '∞'), 'a:cv:' . (int)$c['id'])];
    $nav = [];
    if ($page > 0) $nav[] = botAB('◀️ قبلی', 'a:cp:' . ($page - 1));
    if ($more) $nav[] = botAB('بعدی ▶️', 'a:cp:' . ($page + 1));
    if ($nav) $kb[] = $nav;
    $kb[] = [botAB('➕ افزودن کد', 'a:ca', 'success')];
    $kb[] = [botAB('بازگشت', 'a:home')];
    botSay($db, $bot, $chat, $txt, $kb);
}
function botAdminCouponView(PDO $db, array $bot, int $chat, int $id): void {
    $c = botCouponRow($db, $bot, $id);
    if (!$c) { botSay($db, $bot, $chat, 'کد پیدا نشد.', [[botAB('بازگشت', 'a:cp')]]); return; }
    $exp = (int)$c['expires_at'];
    $txt = "🏷 <b>کد تخفیف</b> <code>" . bh((string)$c['code']) . "</code>\nنوع: " . ((string)$c['kind'] === 'amount' ? 'مبلغ ثابت' : 'درصدی') . "\nمقدار: " . botCouponValueLabel($c)
         . "\nاستفاده‌شده: " . (int)$c['used'] . ' از ' . ((int)$c['max_uses'] > 0 ? (int)$c['max_uses'] : 'نامحدود')
         . "\nسقف هر کاربر: " . ((int)$c['per_user'] > 0 ? (int)$c['per_user'] : 'نامحدود')
         . "\nانقضا: " . ($exp > 0 ? date('Y/m/d H:i', $exp) . ($exp <= time() ? ' (منقضی شده)' : '') : 'بدون انقضا')
         . "\nوضعیت: " . ((int)$c['active'] === 1 ? 'روشن ✅' : 'خاموش ⛔');
    botSay($db, $bot, $chat, $txt, [[botAB((int)$c['active'] === 1 ? 'خاموش کردن' : 'روشن کردن', 'a:ct:' . $id, (int)$c['active'] === 1 ? 'danger' : 'success'), botAB('🗑 حذف', 'a:cd:' . $id, 'danger')], [botAB('بازگشت', 'a:cp')]]);
}
/** ورودی افزودن: «کد نوع مقدار [سقف‌کل] [سقف‌هرکاربر] [روزانقضا]»؛ خروجی آرایه‌ی داده یا رشته‌ی خطا */
function botCouponParseInput(string $text) {
    $p = preg_split('/\s+/u', trim(payDigits($text)));
    if (count($p) < 3 || count($p) > 6) return 'قالب نادرست است. مثال: EID20 percent 20 100 1 30';
    $code = botCouponNorm((string)$p[0]);
    if ($code === '') return 'کد باید ۳ تا ۲۰ کاراکتر از حروف انگلیسی، عدد، _ یا - باشد.';
    $t = mb_strtolower((string)$p[1]);
    $kind = in_array($t, ['percent', 'pct', '%', 'درصد'], true) ? 'pct' : (in_array($t, ['amount', 'amt', 'مبلغ', 'تومان'], true) ? 'amount' : '');
    if ($kind === '') return 'نوع باید percent (درصد) یا amount (مبلغ ثابت) باشد.';
    foreach (array_slice($p, 2) as $n) if (!preg_match('/^\d{1,10}$/', (string)$n)) return 'مقدارها باید عدد باشند.';
    $val = (int)$p[2]; $max = (int)($p[3] ?? 0); $per = isset($p[4]) ? (int)$p[4] : 1; $days = (int)($p[5] ?? 0);
    if ($kind === 'pct' && ($val < 1 || $val > 100)) return 'درصد باید بین ۱ تا ۱۰۰ باشد.';
    if ($kind === 'amount' && ($val < 1 || $val > 1000000000)) return 'مبلغ تخفیف نامعتبر است.';
    if ($max > 1000000000 || $per > 100000 || $days > 3650) return 'یکی از مقدارها خیلی بزرگ است.';
    return ['code' => $code, 'kind' => $kind, 'value' => $val, 'max_uses' => $max, 'per_user' => $per, 'expires_at' => $days > 0 ? time() + $days * 86400 : 0];
}
// ------------------------------------------------------------------ پیام همگانی با صف (مرحله ۶)
function botBcStatusLabel(string $s): string {
    return ['queued' => '⏳ در صف', 'sending' => '📤 در حال ارسال', 'done' => '✅ تمام شد', 'cancelled' => '🚫 لغو شد'][$s] ?? $s;
}
/** هر خط «عنوان | لینک»؛ حداکثر ۸ دکمه. @return array<int,array{0:string,1:string}>|string آرایه یا متن خطا */
function botBcButtonsParse(string $text) {
    $t = trim($text);
    if ($t === '' || $t === '-') return [];
    $out = [];
    foreach (preg_split('/\r?\n/u', $t) ?: [] as $line) {
        $line = trim($line);
        if ($line === '') continue;
        $p = explode('|', $line, 2);
        if (count($p) !== 2) return 'هر خط باید به شکل «عنوان | لینک» باشد.';
        $title = botCleanTxt($p[0], 40); $url = trim($p[1]);
        if ($title === '') return 'عنوان یکی از دکمه‌ها خالی است.';
        if (strlen($url) > 500 || !preg_match('#^https://[A-Za-z0-9.\-]+(:\d+)?(/[^\s]*)?$#', $url)) return 'لینک باید با https:// شروع شود و معتبر باشد.';
        $out[] = [$title, $url];
        if (count($out) > 8) return 'حداکثر ۸ دکمه مجاز است.';
    }
    return $out;
}
function botBcKb(array $btns): array {
    $kb = [];
    foreach ($btns as $b) $kb[] = [['text' => (string)$b[0], 'url' => (string)$b[1]]];
    return $kb;
}
/** پیش‌نویس ادمین (در tg_users.draft همین کاربر ربات)؛ null = نیست */
function botBcDraft(PDO $db, array $bot, array $u): ?array {
    $s = $db->prepare('SELECT draft FROM tg_users WHERE id=? AND bot_id=?'); $s->execute([(int)$u['id'], (int)$bot['id']]);
    $d = json_decode((string)$s->fetchColumn(), true);
    if (!is_array($d) || empty($d['bc']) || !is_string($d['text'] ?? null) || $d['text'] === '') return null;
    $btns = []; foreach ((array)($d['btns'] ?? []) as $b) if (is_array($b) && count($b) === 2) $btns[] = [(string)$b[0], (string)$b[1]];
    return ['text' => $d['text'], 'btns' => array_slice($btns, 0, 8), 'pin' => (int)($d['pin'] ?? 0) === 1 ? 1 : 0];
}
function botBcDraftSave(PDO $db, array $bot, array $u, ?array $d): void {
    $j = $d === null ? '' : json_encode(['bc' => 1, 'text' => $d['text'], 'btns' => $d['btns'], 'pin' => (int)$d['pin']], JSON_UNESCAPED_UNICODE);
    $db->prepare('UPDATE tg_users SET draft=? WHERE id=? AND bot_id=?')->execute([$j, (int)$u['id'], (int)$bot['id']]);
}
function botBcMenu(PDO $db, array $bot, int $chat): void {
    botSay($db, $bot, $chat, "📣 <b>پیام همگانی</b>\nپیام در صف قرار می‌گیرد و با سرعت مجاز تلگرام برای کاربران همین ربات ارسال می‌شود (کاربران مسدود یا ربات‌را‌بلاک‌کرده حذف می‌شوند).",
        [[botAB('✍️ ارسال جدید', 'a:bcn', 'primary'), botAB('📜 تاریخچه', 'a:bch')], [botAB('بازگشت', 'a:home')]]);
}
function botBcPreview(PDO $db, array $bot, array $u, int $chat): void {
    $d = botBcDraft($db, $bot, $u);
    if (!$d) { botSay($db, $bot, $chat, 'پیش‌نویسی نیست.', [[botAB('بازگشت', 'a:bc')]]); return; }
    $kb = botBcKb($d['btns']);
    $kb[] = [botAB('📌 پین بی‌صدا: ' . ($d['pin'] ? 'روشن ✅' : 'خاموش ⛔'), 'a:bcp', $d['pin'] ? 'success' : '')];
    $kb[] = [botAB('✅ تأیید و قرار دادن در صف', 'a:bcgo', 'success'), botAB('لغو', 'a:bcd', 'danger')];
    botSay($db, $bot, $chat, "پیش‌نمایش پیام همگانی (دکمه‌های لینک همین‌جا هم دیده می‌شوند):\n\n" . botEmo(bh($d['text'])), $kb);
}
function botBcQueue(PDO $db, array $bot, array $u, int $chat): void {
    $d = botBcDraft($db, $bot, $u);
    botBcDraftSave($db, $bot, $u, null);
    if (!$d) { botSay($db, $bot, $chat, 'پیش‌نویسی نیست.', [[botAB('بازگشت', 'a:bc')]]); return; }
    $bid = (int)$bot['id'];
    $id = (int)botAtomic($db, function () use ($db, $bid, $d, $chat): int {
        $q = $db->prepare('SELECT COUNT(*), COALESCE(MAX(id),0) FROM tg_users WHERE bot_id=? AND banned=0 AND blocked=0'); $q->execute([$bid]);
        [$total, $max] = array_map('intval', $q->fetch(PDO::FETCH_NUM));
        if ($total <= 0) return 0;
        $now = time();
        $db->prepare("INSERT INTO tg_broadcasts (bot_id,text,buttons_json,pin,status,total,sent,failed,last_user_id,created_by,updated_at,created_at) VALUES (?,?,?,?,'queued',?,0,0,0,?,?,?)")
           ->execute([$bid, $d['text'], json_encode($d['btns'], JSON_UNESCAPED_UNICODE), $d['pin'], $total, $chat, $now, $now]);
        $id = (int)$db->lastInsertId();
        $db->prepare('INSERT OR REPLACE INTO tg_counters (bot_id,name,val) VALUES (?,?,?)')->execute([$bid, 'bcmax:' . $id, $max]); // کاربران بعد از صف‌شدن دریافت نمی‌کنند
        return $id;
    });
    if ($id <= 0) { botSay($db, $bot, $chat, 'کاربر فعالی برای ارسال وجود ندارد.', [[botAB('بازگشت', 'a:bc')]]); return; }
    botAudit($db, $bot, $chat, 'broadcast_queue', 'bc:' . $id, ['pin' => $d['pin'], 'buttons' => count($d['btns'])]);
    botSay($db, $bot, $chat, '✅ پیام همگانی #' . $id . ' در صف قرار گرفت. پیشرفت را از «تاریخچه» ببینید.', [[botAB('📜 تاریخچه', 'a:bch'), botAB('بازگشت', 'a:home')]]);
}
function botBcRow(PDO $db, array $bot, int $id): ?array {
    if ($id <= 0) return null;
    $s = $db->prepare('SELECT * FROM tg_broadcasts WHERE id=? AND bot_id=?'); $s->execute([$id, (int)$bot['id']]);
    $r = $s->fetch(PDO::FETCH_ASSOC);
    return $r ?: null;
}
function botBcHistory(PDO $db, array $bot, int $chat): void {
    $s = $db->prepare('SELECT * FROM tg_broadcasts WHERE bot_id=? ORDER BY id DESC LIMIT 10'); $s->execute([(int)$bot['id']]);
    $rows = $s->fetchAll(PDO::FETCH_ASSOC);
    if (!$rows) { botSay($db, $bot, $chat, 'هنوز پیام همگانی‌ای ارسال نشده است.', [[botAB('بازگشت', 'a:bc')]]); return; }
    $txt = "📜 <b>۱۰ ارسال آخر</b>\n"; $kb = [];
    foreach ($rows as $r) {
        $txt .= "\n#" . (int)$r['id'] . ' — ' . botBcStatusLabel((string)$r['status']) . ' — ' . (int)$r['sent'] . '/' . (int)$r['total'] . ' — ' . date('Y/m/d H:i', (int)$r['created_at']);
        $kb[] = [botAB('جزئیات #' . (int)$r['id'], 'a:bcv:' . (int)$r['id'])];
    }
    $kb[] = [botAB('بازگشت', 'a:bc')];
    botSay($db, $bot, $chat, $txt, $kb);
}
function botBcView(PDO $db, array $bot, int $chat, int $id): void {
    $r = botBcRow($db, $bot, $id);
    if (!$r) { botSay($db, $bot, $chat, 'ارسال پیدا نشد.', [[botAB('بازگشت', 'a:bch')]]); return; }
    $left = max(0, (int)$r['total'] - (int)$r['sent'] - (int)$r['failed']);
    $btns = json_decode((string)$r['buttons_json'], true); $btns = is_array($btns) ? $btns : [];
    $txt = '📣 <b>ارسال #' . (int)$r['id'] . "</b>\nوضعیت: " . botBcStatusLabel((string)$r['status']) . "\nکل: " . (int)$r['total'] . ' — موفق: ' . (int)$r['sent'] . ' — ناموفق: ' . (int)$r['failed']
         . ((string)$r['status'] === 'done' || (string)$r['status'] === 'cancelled' ? '' : ' — باقی‌مانده: ' . $left)
         . "\nپین: " . ((int)$r['pin'] === 1 ? 'بله' : 'خیر') . ' — دکمه‌ها: ' . count($btns) . "\nساخته‌شده: " . date('Y/m/d H:i', (int)$r['created_at'])
         . "\n\n" . botEmo(bh(mb_substr((string)$r['text'], 0, 600)));
    $kb = [];
    if (in_array((string)$r['status'], ['queued', 'sending'], true)) $kb[] = [botAB('🚫 لغو ارسال', 'a:bcx:' . (int)$r['id'], 'danger')];
    $kb[] = [botAB('بازگشت', 'a:bch')];
    botSay($db, $bot, $chat, $txt, $kb);
}
function botBcCancel(PDO $db, array $bot, int $chat, int $id): void {
    $r = botBcRow($db, $bot, $id);
    if (!$r) { botSay($db, $bot, $chat, 'ارسال پیدا نشد.', [[botAB('بازگشت', 'a:bch')]]); return; }
    $up = $db->prepare("UPDATE tg_broadcasts SET status='cancelled', updated_at=? WHERE id=? AND bot_id=? AND status IN ('queued','sending')");
    $up->execute([time(), $id, (int)$bot['id']]);
    if ($up->rowCount() === 1) botAudit($db, $bot, $chat, 'broadcast_cancel', 'bc:' . $id);
    botBcView($db, $bot, $chat, $id);
}
/**
 * ادامه‌ی ارسال‌های صف‌شده‌ی یک ربات تا $deadline؛ حداکثر ۲۵ تماس API در ثانیه، از last_user_id.
 * ۴۲۹ → retry_after در tg_counters(bc_wait) ثبت و اجرای فعلی قطع می‌شود (همان کاربر دوباره امتحان می‌شود)؛ ۴۰۳ → کاربر blocked=1.
 */
function botBroadcastRun(PDO $db, array $bot, float $deadline): void {
    $bid = (int)$bot['id'];
    $w = $db->prepare("SELECT val FROM tg_counters WHERE bot_id=? AND name='bc_wait'"); $w->execute([$bid]);
    if ((int)$w->fetchColumn() > time()) return;
    $plain = fn(string $t): string => (string)preg_replace('#<tg-emoji[^>]*>(.*?)</tg-emoji>#us', '$1', $t);
    while (microtime(true) < $deadline) {
        $bq = $db->prepare("SELECT * FROM tg_broadcasts WHERE bot_id=? AND status IN ('queued','sending') ORDER BY id LIMIT 1"); $bq->execute([$bid]);
        $bc = $bq->fetch(PDO::FETCH_ASSOC);
        if (!$bc) return;
        $id = (int)$bc['id'];
        if ((string)$bc['status'] === 'queued') $db->prepare("UPDATE tg_broadcasts SET status='sending', updated_at=? WHERE id=? AND bot_id=? AND status='queued'")->execute([time(), $id, $bid]);
        $mx = $db->prepare('SELECT val FROM tg_counters WHERE bot_id=? AND name=?'); $mx->execute([$bid, 'bcmax:' . $id]);
        $max = (int)$mx->fetchColumn();
        $btns = json_decode((string)$bc['buttons_json'], true); $kb = is_array($btns) ? botBcKb($btns) : [];
        $html = botEmo(bh((string)$bc['text'])); $last = (int)$bc['last_user_id'];
        $us = $db->prepare('SELECT id, chat_id FROM tg_users WHERE bot_id=? AND id>? AND id<=? AND banned=0 AND blocked=0 ORDER BY id LIMIT 50');
        $us->execute([$bid, $last, $max]);
        $users = $us->fetchAll(PDO::FETCH_ASSOC);
        if (!$users) {
            $fin = $db->prepare("UPDATE tg_broadcasts SET status='done', updated_at=? WHERE id=? AND bot_id=? AND status='sending'");
            $fin->execute([time(), $id, $bid]);
            if ($fin->rowCount() === 1) {
                $cur = botBcRow($db, $bot, $id);
                if ($cur && (int)$cur['created_by'] > 0) botSay($db, $bot, (int)$cur['created_by'], '✅ پیام همگانی #' . $id . " تمام شد.\nموفق: " . (int)$cur['sent'] . ' — ناموفق: ' . (int)$cur['failed']);
            }
            continue;
        }
        foreach ($users as $usr) {
            if (microtime(true) >= $deadline) return;
            $p = ['chat_id' => (int)$usr['chat_id'], 'text' => $html, 'parse_mode' => 'HTML', 'disable_web_page_preview' => 'true'];
            if ($kb) $p['reply_markup'] = ['inline_keyboard' => $kb];
            $r = botTg($db, $bot, 'sendMessage', $p);
            usleep(40000);
            if (empty($r['ok']) && (int)($r['error_code'] ?? 0) === 400 && strpos($html, '<tg-emoji') !== false) { // ایموجی سفارشی پذیرفته نشد
                $p['text'] = $plain($html); $r = botTg($db, $bot, 'sendMessage', $p); usleep(40000);
            }
            if (empty($r['ok']) && (int)($r['error_code'] ?? 0) === 429) {
                $ra = max(1, min(3600, (int)($r['parameters']['retry_after'] ?? 5)));
                $db->prepare('INSERT OR IGNORE INTO tg_counters (bot_id,name,val) VALUES (?,?,0)')->execute([$bid, 'bc_wait']);
                $db->prepare("UPDATE tg_counters SET val=? WHERE bot_id=? AND name='bc_wait'")->execute([time() + $ra, $bid]);
                return;
            }
            $ok = !empty($r['ok']);
            if (!$ok && (int)($r['error_code'] ?? 0) === 403) $db->prepare('UPDATE tg_users SET blocked=1 WHERE id=? AND bot_id=?')->execute([(int)$usr['id'], $bid]);
            $up = $db->prepare("UPDATE tg_broadcasts SET sent=sent+?, failed=failed+?, last_user_id=?, updated_at=? WHERE id=? AND bot_id=? AND status='sending'");
            $up->execute([$ok ? 1 : 0, $ok ? 0 : 1, (int)$usr['id'], time(), $id, $bid]);
            if ($up->rowCount() !== 1) break; // وسط کار لغو شد
            if ($ok && (int)$bc['pin'] === 1 && (int)($r['result']['message_id'] ?? 0) > 0) {
                botTg($db, $bot, 'pinChatMessage', ['chat_id' => (int)$usr['chat_id'], 'message_id' => (int)$r['result']['message_id'], 'disable_notification' => 'true']);
                usleep(40000);
            }
        }
    }
}
/** جاب زمان‌بند: هر ربات فعال با نماینده‌ی فعال، به‌ترتیب و در بودجه‌ی زمانی زمان‌بند */
function botBroadcastJob(PDO $db): void {
    $deadline = isset($GLOBALS['__sched_deadline']) ? (float)$GLOBALS['__sched_deadline'] : microtime(true) + 8.0;
    $q = $db->query("SELECT b.* FROM tg_bots b JOIN accounts ag ON ag.id=b.agent_id WHERE b.enabled=1 AND ag.role IN ('agent','admin') AND ag.disabled=0
        AND EXISTS (SELECT 1 FROM tg_broadcasts c WHERE c.bot_id=b.id AND c.status IN ('queued','sending')) ORDER BY b.id");
    foreach ($q->fetchAll(PDO::FETCH_ASSOC) as $bot) {
        if (microtime(true) >= $deadline) return;
        try { botBroadcastRun($db, $bot, $deadline); }
        catch (Throwable $e) { error_log('bot_broadcast: ' . get_class($e) . ' @' . basename($e->getFile()) . ':' . $e->getLine()); }
    }
}
/** stateهایی که فقط ادمین دارد و متن بعدی‌اش توسط botAdminText مصرف می‌شود */
function botAdminStates(): array { return ['find', 'adjp', 'adjm', 'set', 'trafficset', 'bc', 'bcb', 'fjset', 'adadd', 'cpadd', 'evchat', 'evtopic', 'ticket_answer', 'canned_title', 'canned_text', 'tut_add_title', 'tut_add_body', 'tut_edit_title', 'tut_edit_body', 'ag_find', 'ag_new_email', 'ag_new_pass', 'ag_new_lim', 'ag_edit', 'ag_pw', 'em_add', 'em_cap']; }
/** دروازه‌ی مجوز هر state: '' = تعریف‌نشده، 'owner' = فقط مالک */
function botStatePerm(string $st): string {
    return ['find' => 'users', 'adjp' => 'wallet', 'adjm' => 'wallet', 'set' => 'settings', 'trafficset' => 'settings', 'fjset' => 'settings', 'bc' => 'broadcast', 'bcb' => 'broadcast', 'adadd' => 'owner', 'cpadd' => 'settings', 'evchat' => 'settings', 'evtopic' => 'settings', 'ticket_answer' => 'tickets', 'canned_title' => 'tickets', 'canned_text' => 'tickets', 'tut_add_title' => 'settings', 'tut_add_body' => 'settings', 'tut_edit_title' => 'settings', 'tut_edit_body' => 'settings', 'ag_find' => 'agents', 'ag_new_email' => 'agents', 'ag_new_pass' => 'agents', 'ag_new_lim' => 'agents', 'ag_edit' => 'agents', 'ag_pw' => 'agents', 'em_add' => 'settings', 'em_cap' => 'settings'][$st] ?? '';
}
/** دروازه‌ی مجوز هر دکمه‌ی a:<act>: '' = هر ادمین، 'owner' = فقط مالک؛ ناشناخته = null (رد) */
function botActPerm(string $act): ?string {
    $m = ['home' => '', 'st' => 'stats', 'find' => 'users', 'u' => 'users', 'rt' => 'users', 'bn' => 'users', 'bp' => 'wallet', 'bm' => 'wallet',
          'set' => 'settings', 'tg' => 'settings', 'ed' => 'settings', 'fj' => 'settings', 'fjt' => 'settings', 'fje' => 'settings', 'audit' => 'settings', 'cmd' => 'settings',
          'cp' => 'settings', 'cv' => 'settings', 'ca' => 'settings', 'ct' => 'settings', 'cd' => 'settings', 'cy' => 'settings',
          'bc' => 'broadcast', 'bcn' => 'broadcast', 'bcp' => 'broadcast', 'bcd' => 'broadcast', 'bcgo' => 'broadcast', 'bch' => 'broadcast', 'bcv' => 'broadcast', 'bcx' => 'broadcast',
          'ev' => 'settings', 'evk' => 'settings', 'mn' => 'settings', 'mt' => 'settings', 'mu' => 'settings', 'mj' => 'settings', 'evg' => 'settings', 'evc' => 'settings', 'evt' => 'settings', 'pend' => 'orders',
          'tk' => 'tickets', 'tkt' => 'tickets', 'tka' => 'tickets', 'tkc' => 'tickets', 'ck' => 'tickets', 'cka' => 'tickets', 'ckd' => 'tickets', 'cks' => 'tickets',
          'bk' => 'settings', 'bkn' => 'settings', 'tu' => 'settings', 'tul' => 'settings', 'tun' => 'settings', 'tuv' => 'settings', 'tue' => 'settings', 'tuo' => 'settings', 'tud' => 'settings', 'tus' => 'settings',
          'em' => 'settings', 'ag' => 'agents', 'ad' => 'admins', 'aa' => 'owner', 'ae' => 'owner', 'ap' => 'owner', 'ar' => 'owner', 'ay' => 'owner'];
    return $m[$act] ?? null;
}
function botCanAct(PDO $db, array $bot, int $chat, ?string $need): bool {
    if ($need === null) return false;
    if ($need === '') return botIsStaff($db, $bot, $chat);
    if ($need === 'owner') return botIsOwner($bot, $chat);
    return botCan($db, $bot, $chat, $need);
}
function botNoAccess(PDO $db, array $bot, int $chat): void { botSay($db, $bot, $chat, '⛔ شما به این بخش دسترسی ندارید.', [[botAB('بازگشت', 'a:home')]]); }
/** متن‌های دریافتی از ادمین در حالت‌های جست‌وجو/شارژ/تنظیم/پیام همگانی/کانال‌ها/افزودن ادمین؛ true = مصرف شد */
function botAdminText(PDO $db, array $bot, array $agent, array $u, string $text): bool {
    $st = (string)$u['state']; $chat = (int)$u['chat_id'];
    $need = botStatePerm($st);
    if ($need === '') return false;
    if (!botCanAct($db, $bot, $chat, $need)) { botState($db, $u, ''); botNoAccess($db, $bot, $chat); return true; }
    if (strncmp($st, 'ag_', 3) === 0) return botAgText($db, $bot, $agent, $u, $text);
    if (strncmp($st, 'em_', 3) === 0) return botEmoText($db, $bot, $agent, $u, $text);
    if ($st === 'ticket_answer') {
        $ticketId = (int)$u['state_val']; botState($db, $u, '');
        $msg = botTicketCleanBody($text, 3500);
        if ($msg === '') { botSay($db, $bot, $chat, 'متن پاسخ خالی است.'); botTicketAdminView($db, $bot, $chat, $ticketId); return true; }
        botTicketAdminReply($db, $bot, $chat, $ticketId, $msg, 'admin');
        return true;
    }
    if ($st === 'canned_title') {
        $title = mb_substr(trim(botCleanTxt($text, 80)), 0, 80);
        if ($title === '') { botSay($db, $bot, $chat, 'عنوان پاسخ آماده را بفرستید.'); return true; }
        $draft = json_encode(['canned_title' => $title], JSON_UNESCAPED_UNICODE);
        $db->prepare('UPDATE tg_users SET draft=?, state=?, state_val=? WHERE id=? AND bot_id=? AND chat_id=?')
           ->execute([$draft, 'canned_text', (int)$u['state_val'], (int)$u['id'], (int)$bot['id'], $chat]);
        botSay($db, $bot, $chat, 'متن پاسخ آماده را بفرستید (حداکثر ۳۵۰۰ نویسه).');
        return true;
    }
    if ($st === 'canned_text') {
        $d = json_decode((string)($u['draft'] ?? ''), true); $title = is_array($d) ? (string)($d['canned_title'] ?? '') : '';
        $body = botTicketCleanBody($text, 3500);
        if ($title === '' || $body === '') { botSay($db, $bot, $chat, 'عنوان یا متن نامعتبر است؛ عنوان را دوباره بفرستید.', [[botAB('بازگشت', 'a:ck:' . (int)$u['state_val'])]]); botState($db, $u, 'canned_title', (int)$u['state_val']); return true; }
        $returnTicket = (int)$u['state_val']; botState($db, $u, '');
        $db->prepare('UPDATE tg_users SET draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['', (int)$u['id'], (int)$bot['id'], $chat]);
        $db->prepare('INSERT INTO tg_canned (bot_id, title, text, created_at) VALUES (?,?,?,?)')->execute([(int)$bot['id'], $title, $body, time()]);
        botAudit($db, $bot, $chat, 'canned_add', $title);
        botSay($db, $bot, $chat, '✅ پاسخ آماده ثبت شد.');
        if ($returnTicket > 0) botCannedAdminList($db, $bot, $chat, $returnTicket); else botCannedAdminList($db, $bot, $chat, 0);
        return true;
    }
    if ($st === 'tut_add_title') {
        $title = mb_substr(trim(botCleanTxt($text, 100)), 0, 100);
        if ($title === '') { botSay($db, $bot, $chat, 'عنوان را بفرستید.'); return true; }
        $draft = json_encode(['tutorial_title' => $title], JSON_UNESCAPED_UNICODE);
        $db->prepare('UPDATE tg_users SET draft=?, state=?, state_val=? WHERE id=? AND bot_id=? AND chat_id=?')
           ->execute([$draft, 'tut_add_body', (int)$u['state_val'], (int)$u['id'], (int)$bot['id'], $chat]);
        botSay($db, $bot, $chat, 'متن آموزش/سوال متداول را بفرستید (حداکثر ۳۵۰۰ نویسه).'); return true;
    }
    if ($st === 'tut_add_body') {
        $d = json_decode((string)($u['draft'] ?? ''), true); $title = is_array($d) ? (string)($d['tutorial_title'] ?? '') : '';
        $body = botTicketCleanBody($text, 3500); $kind = (int)$u['state_val'] === 1 ? 'faq' : 'tutorial';
        if ($title === '' || $body === '') { botSay($db, $bot, $chat, 'عنوان یا متن نامعتبر است؛ عنوان را دوباره بفرستید.', [[botAB('بازگشت', 'a:tu')]]); botState($db, $u, 'tut_add_title', $kind === 'faq' ? 1 : 0); return true; }
        $db->prepare('INSERT INTO tg_tutorials (bot_id, kind, title, body, sort, active, created_at) VALUES (?,?,?,?,(SELECT COALESCE(MAX(sort),0)+10 FROM tg_tutorials WHERE bot_id=? AND kind=?),1,?)')
           ->execute([(int)$bot['id'], $kind, $title, $body, (int)$bot['id'], $kind, time()]);
        botState($db, $u, ''); $db->prepare('UPDATE tg_users SET draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['', (int)$u['id'], (int)$bot['id'], $chat]);
        botAudit($db, $bot, $chat, 'tutorial_add', $kind . ':' . $title);
        botSay($db, $bot, $chat, '✅ مورد ثبت شد.'); botTutorialAdminList($db, $bot, $chat, $kind); return true;
    }
    if ($st === 'tut_edit_title') {
        $id = (int)$u['state_val']; $row = botTutorialRow($db, $bot, $id);
        if (!$row) { botState($db, $u, ''); botSay($db, $bot, $chat, 'مورد پیدا نشد.'); return true; }
        $title = mb_substr(trim(botCleanTxt($text, 100)), 0, 100);
        if ($title === '') { botSay($db, $bot, $chat, 'عنوان را بفرستید.'); return true; }
        $draft = json_encode(['tutorial_title' => $title], JSON_UNESCAPED_UNICODE);
        $db->prepare('UPDATE tg_users SET draft=?, state=?, state_val=? WHERE id=? AND bot_id=? AND chat_id=?')
           ->execute([$draft, 'tut_edit_body', $id, (int)$u['id'], (int)$bot['id'], $chat]);
        botSay($db, $bot, $chat, 'متن جدید را بفرستید.'); return true;
    }
    if ($st === 'tut_edit_body') {
        $id = (int)$u['state_val']; $row = botTutorialRow($db, $bot, $id); $d = json_decode((string)($u['draft'] ?? ''), true);
        $title = is_array($d) ? (string)($d['tutorial_title'] ?? '') : ''; $body = botTicketCleanBody($text, 3500);
        if (!$row) { botState($db, $u, ''); botSay($db, $bot, $chat, 'مورد پیدا نشد.'); return true; }
        if ($title === '' || $body === '') { botSay($db, $bot, $chat, 'عنوان یا متن نامعتبر است؛ عنوان جدید را دوباره بفرستید.', [[botAB('بازگشت', 'a:tuv:' . $id)]]); botState($db, $u, 'tut_edit_title', $id); return true; }
        $db->prepare('UPDATE tg_tutorials SET title=?, body=? WHERE id=? AND bot_id=? AND kind=?')->execute([$title, $body, $id, (int)$bot['id'], (string)$row['kind']]);
        botState($db, $u, ''); $db->prepare('UPDATE tg_users SET draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['', (int)$u['id'], (int)$bot['id'], $chat]);
        botAudit($db, $bot, $chat, 'tutorial_edit', (string)$id); botSay($db, $bot, $chat, '✅ ویرایش شد.'); botTutorialAdminView($db, $bot, $chat, $id); return true;
    }
    if ($st === 'find') {
        botState($db, $u, '');
        $rows = botFind($db, $bot, $text);
        if (!$rows) { botSay($db, $bot, $chat, 'کاربری پیدا نشد.', [[botAB('جست‌وجوی دوباره', 'a:find', 'primary'), botAB('بازگشت', 'a:home')]]); return true; }
        if (count($rows) === 1) { botUserCard($db, $bot, $chat, (int)$rows[0]['id']); return true; }
        $kb = [];
        foreach ($rows as $r) $kb[] = [botAB(((string)$r['username'] !== '' ? '@' . $r['username'] . ' — ' : '') . $r['chat_id'], 'a:u:' . (int)$r['id'])];
        $kb[] = [botAB('بازگشت', 'a:home')];
        botSay($db, $bot, $chat, 'چند کاربر پیدا شد:', $kb);
        return true;
    }
    if ($st === 'adjp' || $st === 'adjm') {
        $amt = (int)preg_replace('/\D/', '', payDigits($text));
        if ($amt <= 0) { botSay($db, $bot, $chat, 'مبلغ را به‌صورت عدد (تومان) بفرستید.'); return true; }
        $uid = (int)$u['state_val']; botState($db, $u, '');
        $tu = botUserOwned($db, $bot, $uid);
        if (!$tu) { botSay($db, $bot, $chat, 'کاربر پیدا نشد.'); return true; }
        $delta = $st === 'adjp' ? $amt : -$amt;
        $nb = botWalletAdd($db, $bot, $uid, $delta, 'admin ' . $st);
        if ($nb === null) { botSay($db, $bot, $chat, 'موجودی کاربر برای این کسر کافی نیست.'); botUserCard($db, $bot, $chat, $uid); return true; }
        botAudit($db, $bot, $chat, 'wallet_adjust', 'user:' . $uid, ['delta' => $delta, 'balance' => $nb]);
        botSay($db, $bot, (int)$tu['chat_id'], 'موجودی کیف پول شما توسط مدیر ' . ($st === 'adjp' ? 'افزایش' : 'کاهش') . ' یافت: ' . botMoney($amt) . "\nموجودی فعلی: " . botMoney($nb));
        botSay($db, $bot, $chat, '✅ انجام شد. موجودی جدید: ' . botMoney($nb));
        if (botCan($db, $bot, $chat, 'users')) botUserCard($db, $bot, $chat, $uid);
        return true;
    }
    if ($st === 'trafficset') {
        $raw = trim($text); $packs = $raw === '-' ? [] : json_decode($raw, true);
        if (!is_array($packs) || json_last_error() !== JSON_ERROR_NONE) {
            botSay($db, $bot, $chat, '⚠️ JSON نامعتبر است. نمونه: <code>[{"gb":5,"price":10000},{"gb":10,"price":18000}]</code>\nبرای خالی‌کردن بسته‌ها، <code>[]</code> بفرستید.');
            return true;
        }
        $old = botCfg($db, (int)$agent['id']);
        $r = botTry(fn() => botCfgPatch($db, $agent, ['traffic_packs' => $packs]));
        if (!$r['ok']) { botSay($db, $bot, $chat, '⚠️ ' . bh((string)$r['err']) . "\nدوباره بفرستید یا با دکمه‌ی بازگشت خارج شوید.", [[botAB('بازگشت', 'a:set')]]); return true; }
        botState($db, $u, '');
        botAudit($db, $bot, $chat, 'setting', 'traffic_packs', json_encode(['old' => $old['traffic_packs'], 'new' => $r['v']['traffic_packs']], JSON_UNESCAPED_UNICODE));
        botSay($db, $bot, $chat, '✅ بسته‌های حجم اضافه ذخیره شد.');
        botAdminSettings($db, $bot, $agent, $chat);
        return true;
    }
    if ($st === 'set') {
        $list = botSetList(); $i = (int)$u['state_val'];
        botState($db, $u, '');
        if (!isset($list[$i])) return true;
        if ($list[$i][2] !== 'num') return true;
        $old = (string)botCfg($db, (int)$agent['id'])[$list[$i][0]];
        $val = preg_replace('/[^0-9.]/', '', payDigits($text));
        $r = botTry(fn() => botCfgPatch($db, $agent, [$list[$i][0] => $val]));
        if ($r['ok']) botAudit($db, $bot, $chat, 'setting', (string)$list[$i][0], $old . ' → ' . (string)$r['v'][$list[$i][0]]);
        botSay($db, $bot, $chat, $r['ok'] ? '✅ ذخیره شد.' : '⚠️ مقدار نامعتبر: ' . bh($r['err']));
        botAdminSettings($db, $bot, $agent, $chat);
        return true;
    }
    if ($st === 'fjset') {
        botState($db, $u, '');
        $old = implode(', ', (array)botCfg($db, (int)$agent['id'])['fj']);
        $r = botTry(fn() => botCfgPatch($db, $agent, ['fj' => $text]));
        if ($r['ok']) botAudit($db, $bot, $chat, 'setting', 'fj', $old . ' → ' . implode(', ', (array)$r['v']['fj']));
        botSay($db, $bot, $chat, $r['ok'] ? '✅ لیست کانال‌ها ذخیره شد.' : '⚠️ ' . bh($r['err']));
        botAdminFj($db, $bot, $agent, $chat);
        return true;
    }
    if ($st === 'adadd') {
        $id = preg_replace('/\D/', '', payDigits($text));
        if (!preg_match('/^\d{4,20}$/', (string)$id)) { botSay($db, $bot, $chat, 'chat id باید عدد باشد (مثلاً 123456789). دوباره بفرستید.'); return true; }
        botState($db, $u, '');
        $r = botAdminAdd($db, $bot, $chat, (int)$id, ['orders']);
        botSay($db, $bot, $chat, ($r['ok'] ? '✅ ' : '⚠️ ') . bh($r['msg']));
        $q = $db->prepare('SELECT id FROM tg_bot_admins WHERE bot_id=? AND chat_id=?'); $q->execute([(int)$bot['id'], (int)$id]);
        $rid = (int)$q->fetchColumn();
        if ($r['ok'] && $rid > 0) botAdminEdit($db, $bot, $chat, $rid); else botAdminList($db, $bot, $chat);
        return true;
    }
    if ($st === 'cpadd') {
        $d = botCouponParseInput($text);
        if (is_string($d)) { botSay($db, $bot, $chat, '⚠️ ' . bh($d) . "\nدوباره بفرستید یا بازگردید.", [[botAB('بازگشت', 'a:cp')]]); return true; }
        botState($db, $u, '');
        $n = $db->prepare('SELECT COUNT(*) FROM tg_coupons WHERE bot_id=?'); $n->execute([(int)$bot['id']]);
        if ((int)$n->fetchColumn() >= 500) { botSay($db, $bot, $chat, '⚠️ حداکثر ۵۰۰ کد تخفیف مجاز است.'); botAdminCoupons($db, $bot, $chat); return true; }
        try {
            $db->prepare('INSERT INTO tg_coupons (bot_id, code, kind, value, max_uses, used, per_user, expires_at, active, created_at) VALUES (?,?,?,?,?,0,?,?,1,?)')
               ->execute([(int)$bot['id'], $d['code'], $d['kind'], $d['value'], $d['max_uses'], $d['per_user'], $d['expires_at'], time()]);
            botAudit($db, $bot, $chat, 'coupon_add', (string)$d['code'], ['kind' => $d['kind'], 'value' => $d['value'], 'max' => $d['max_uses'], 'per_user' => $d['per_user']]);
            botSay($db, $bot, $chat, '✅ کد تخفیف ثبت شد.');
        } catch (PDOException $e) { botSay($db, $bot, $chat, '⚠️ این کد قبلاً ثبت شده است.'); }
        botAdminCoupons($db, $bot, $chat);
        return true;
    }
    if ($st === 'bc') {
        $d = botCleanTxt($text, 3500);
        if ($d === '') return true;
        botBcDraftSave($db, $bot, $u, ['text' => $d, 'btns' => [], 'pin' => 0]);
        botState($db, $u, 'bcb');
        botSay($db, $bot, $chat, "دکمه‌های لینک (اختیاری، حداکثر ۸): هر خط به شکل\n<code>عنوان | https://example.com</code>\nبرای ارسال بدون دکمه، فقط <code>-</code> بفرستید.", [[botAB('لغو', 'a:bcd', 'danger')]]);
        return true;
    }
    if ($st === 'bcb') {
        $btns = botBcButtonsParse($text);
        if (is_string($btns)) { botSay($db, $bot, $chat, '⚠️ ' . bh($btns) . "\nدوباره بفرستید (یا <code>-</code> برای بدون دکمه).", [[botAB('لغو', 'a:bcd', 'danger')]]); return true; }
        $d = botBcDraft($db, $bot, $u);
        botState($db, $u, '');
        if (!$d) { botSay($db, $bot, $chat, 'پیش‌نویسی نیست.', [[botAB('بازگشت', 'a:bc')]]); return true; }
        $d['btns'] = $btns; botBcDraftSave($db, $bot, $u, $d);
        botBcPreview($db, $bot, $u, $chat);
        return true;
    }
    if ($st === 'evchat') {
        botState($db, $u, '');
        $r = botEventsApply($db, $bot, $agent, $text, []);
        if ($r['ok']) botAudit($db, $bot, $chat, 'setting', 'events_chat_id', ['set' => trim($text) === '-' ? 0 : 1]);
        botSay($db, $bot, $chat, ($r['ok'] ? '✅ ' : '⚠️ ') . bh($r['msg']));
        if ($r['ok'] && trim($text) !== '-') { // گروه فروم است → تاپیک‌ها خودکار ساخته می‌شوند
            $a = botEventsAutoTopics($db, $bot, $agent, false);
            if ($a['ok'] || stripos($a['msg'], 'Topics') === false) botSay($db, $bot, $chat, ($a['ok'] ? '✅ ' : '⚠️ ') . bh($a['msg']));
        }
        botAdminEvents($db, $bot, $agent, $chat);
        return true;
    }
    if ($st === 'evtopic') {
        $keys = array_keys(botEventTypes()); $k = $keys[(int)$u['state_val']] ?? null;
        botState($db, $u, '');
        $cfg = botCfg($db, (int)$agent['id']);
        if ($k === null || $cfg['events_chat_id'] === '') { botAdminEvents($db, $bot, $agent, $chat); return true; }
        $n = trim(payDigits($text)); $tp = $cfg['events_topics'];
        if ($n === '-' || $n === '0' || $n === '') unset($tp[$k]); else $tp[$k] = $n;
        $r = botEventsApply($db, $bot, $agent, (string)$cfg['events_chat_id'], $tp);
        if ($r['ok']) botAudit($db, $bot, $chat, 'setting', 'events_topics', ['type' => $k]);
        botSay($db, $bot, $chat, ($r['ok'] ? '✅ ' : '⚠️ ') . bh($r['msg']));
        botAdminEvents($db, $bot, $agent, $chat);
        return true;
    }
    return false;
}
function botAdminCallback(PDO $db, array $bot, array $agent, array $u, string $v): void {
    $chat = (int)$u['chat_id']; $p = explode(':', $v); $act = $p[0]; $arg = (int)($p[1] ?? 0);
    $need = botActPerm($act);
    if ($need === null) return;
    if (!botCanAct($db, $bot, $chat, $need)) { botNoAccess($db, $bot, $chat); return; }
    switch ($act) {
        case 'home': botState($db, $u, ''); botAdminHome($db, $bot, $chat); return;
        case 'st':
            $per = $p[1] ?? 'menu';
            if ($per === 'menu') { botSay($db, $bot, $chat, 'بازه‌ی آمار:', [[botAB('امروز', 'a:st:1', 'primary'), botAB('۷ روز', 'a:st:7', 'primary')], [botAB('۳۰ روز', 'a:st:30', 'primary'), botAB('کل', 'a:st:0')], [botAB('بازگشت', 'a:home')]]); return; }
            $since = $per === '1' ? (int)strtotime('today') : ($per === '7' ? time() - 7 * 86400 : ($per === '30' ? time() - 30 * 86400 : 0));
            $title = $per === '1' ? 'امروز' : ($per === '7' ? '۷ روز اخیر' : ($per === '30' ? '۳۰ روز اخیر' : 'کل'));
            botSay($db, $bot, $chat, botStatsText($db, (int)$bot['id'], $since, $title), [[botAB('بازه‌ی دیگر', 'a:st:menu', 'primary'), botAB('بازگشت', 'a:home')]]);
            return;
        case 'find': botState($db, $u, 'find'); botSay($db, $bot, $chat, "برای جست‌وجو، یکی از این‌ها را بفرستید:\nآیدی عددی تلگرام، یوزرنیم، یا ایمیل (کامل یا بخشی از آن) حساب ساخته‌شده در ربات."); return;
        case 'u': botUserCard($db, $bot, $chat, $arg); return;
        case 'bp': case 'bm':
            if (!botUserOwned($db, $bot, $arg)) { botSay($db, $bot, $chat, 'کاربر پیدا نشد.'); return; }
            botState($db, $u, $act === 'bp' ? 'adjp' : 'adjm', $arg);
            botSay($db, $bot, $chat, ($act === 'bp' ? 'مبلغ افزایش' : 'مبلغ کسر') . ' موجودی را به تومان بفرستید (فقط عدد):');
            return;
        case 'rt':
            $r = $db->prepare('UPDATE tg_users SET tests_used=0 WHERE id=? AND bot_id=?'); $r->execute([$arg, (int)$bot['id']]);
            if ($r->rowCount() === 1) botSay($db, $bot, $chat, '✅ سهمیه‌ی تست کاربر ریست شد.');
            botUserCard($db, $bot, $chat, $arg);
            return;
        case 'bn':
            $r = $db->prepare('UPDATE tg_users SET banned=1-banned WHERE id=? AND bot_id=?'); $r->execute([$arg, (int)$bot['id']]);
            if ($r->rowCount() === 1) { $tu = botUserOwned($db, $bot, $arg); botAudit($db, $bot, $chat, ((int)($tu['banned'] ?? 0) === 1) ? 'ban' : 'unban', 'user:' . $arg); }
            botUserCard($db, $bot, $chat, $arg);
            return;
        case 'set': botAdminSettings($db, $bot, $agent, $chat); return;
        case 'mn': botAdminMenuLayout($db, $bot, $agent, $chat); return;
        case 'mt': case 'mu': case 'mj':
            $cfg = botCfg($db, (int)$agent['id']); $m = $cfg['menu'];
            if (isset($m[$arg])) {
                if ($act === 'mt') $m[$arg]['on'] = $m[$arg]['on'] ? 0 : 1;
                elseif ($act === 'mj' && $arg > 0) $m[$arg]['j'] = $m[$arg]['j'] ? 0 : 1;
                elseif ($act === 'mu' && $arg > 0) { $t = $m[$arg - 1]; $m[$arg - 1] = $m[$arg]; $m[$arg] = $t; }
                $r = botTry(fn() => botCfgPatch($db, $agent, ['menu' => $m]));
                if ($r['ok']) botAudit($db, $bot, $chat, 'setting', 'menu', $act . ':' . (string)($m[min($arg, count($m) - 1)]['k'] ?? ''));
            }
            botAdminMenuLayout($db, $bot, $agent, $chat); return;
        case 'tg':
            $list = botSetList();
            if (isset($list[$arg]) && in_array($list[$arg][2], ['toggle', 'mode'], true)) {
                $k = (string)$list[$arg][0]; $cfg = botCfg($db, (int)$agent['id']); $old = $cfg[$k];
                $new = $list[$arg][2] === 'mode' ? ($k === 'backup_every' ? ($old === 'week' ? 'day' : 'week') : ($old === 'rotate' ? 'all' : 'rotate')) : ((int)$old === 1 ? 0 : 1);
                $r = botTry(fn() => botCfgPatch($db, $agent, [$k => $new]));
                if ($r['ok']) botAudit($db, $bot, $chat, 'setting', $k, (string)$old . ' → ' . (string)$r['v'][$k]);
            }
            botAdminSettings($db, $bot, $agent, $chat);
            return;
        case 'ed':
            $list = botSetList();
            if (!isset($list[$arg]) || !in_array($list[$arg][2], ['num', 'json'], true)) return;
            if ($list[$arg][2] === 'json') {
                botState($db, $u, 'trafficset', $arg);
                botSay($db, $bot, $chat, 'بسته‌ها را به شکل آرایه‌ی JSON بفرستید؛ هر بسته gb و price دارد. نمونه: <code>[{"gb":5,"price":10000},{"gb":10,"price":18000}]</code>\nبرای غیرفعال‌کردن، <code>[]</code> بفرستید.');
            } else {
                botState($db, $u, 'set', $arg);
                botSay($db, $bot, $chat, 'مقدار جدید «' . bh($list[$arg][1]) . '» را بفرستید (فقط عدد):');
            }
            return;
        case 'fj': botAdminFj($db, $bot, $agent, $chat); return;
        case 'fjt':
            $old = (int)botCfg($db, (int)$agent['id'])['fj_on'];
            $r = botTry(fn() => botCfgPatch($db, $agent, ['fj_on' => $old === 1 ? 0 : 1]));
            if ($r['ok']) botAudit($db, $bot, $chat, 'setting', 'fj_on', $old . ' → ' . (int)$r['v']['fj_on']);
            botAdminFj($db, $bot, $agent, $chat);
            return;
        case 'fje':
            botState($db, $u, 'fjset');
            botSay($db, $bot, $chat, "لیست کانال‌ها را بفرستید؛ هر کانال در یک خط (حداکثر ۵):\n@mychannel\nبرای کانال خصوصی: <code>-1001234567890 https://t.me/+AbCdEf</code>\nبرای پاک کردن همه، «-» بفرستید.");
            return;
        case 'audit': botAuditView($db, $bot, $chat); return;
        case 'cmd':
            $r = botCommandsRegister($db, $bot);
            botSay($db, $bot, $chat, '✅ کامندهای ربات دوباره ثبت شد (موفق: ' . (int)$r['ok'] . ' — ناموفق: ' . (int)$r['failed'] . ').' . ((int)$r['failed'] > 0 ? "\nناموفق‌ها معمولاً یعنی ادمینی هنوز ربات را استارت نکرده است." : ''), [[botAB('بازگشت', 'a:home')]]);
            return;
        case 'bc': botState($db, $u, ''); botBcMenu($db, $bot, $chat); return;
        case 'bcn': botBcDraftSave($db, $bot, $u, null); botState($db, $u, 'bc'); botSay($db, $bot, $chat, 'متن پیام همگانی را بفرستید. می‌توانید {e:شناسه_ایموجی} هم بنویسید.', [[botAB('لغو', 'a:bcd', 'danger')]]); return;
        case 'bcd': botState($db, $u, ''); botBcDraftSave($db, $bot, $u, null); botBcMenu($db, $bot, $chat); return;
        case 'bcp':
            $d = botBcDraft($db, $bot, $u);
            if ($d) { $d['pin'] = $d['pin'] ? 0 : 1; botBcDraftSave($db, $bot, $u, $d); }
            botBcPreview($db, $bot, $u, $chat); return;
        case 'bcgo': botBcQueue($db, $bot, $u, $chat); return;
        case 'bch': botBcHistory($db, $bot, $chat); return;
        case 'bcv': botBcView($db, $bot, $chat, $arg); return;
        case 'bcx': botBcCancel($db, $bot, $chat, $arg); return;
        case 'ev': botState($db, $u, ''); botAdminEvents($db, $bot, $agent, $chat); return;
        case 'evg': botState($db, $u, 'evchat'); botSay($db, $bot, $chat, "شناسه‌ی عددی گروه را بفرستید (مثل <code>-1001234567890</code>).\nربات را از قبل به گروه اضافه کنید. برای حذف گروه <code>-</code> بفرستید.", [[botAB('لغو', 'a:ev')]]); return;
        case 'evk':
            $r = botEventsAutoTopics($db, $bot, $agent, false);
            if ($r['ok']) botAudit($db, $bot, $chat, 'setting', 'events_topics', ['auto' => 1]);
            botSay($db, $bot, $chat, ($r['ok'] ? '✅ ' : '⚠️ ') . bh($r['msg']));
            botAdminEvents($db, $bot, $agent, $chat); return;
        case 'evc': botEventsApply($db, $bot, $agent, '-', []); botAudit($db, $bot, $chat, 'setting', 'events_chat_id', ['set' => 0]); botAdminEvents($db, $bot, $agent, $chat); return;
        case 'evt':
            $keys = array_keys(botEventTypes());
            if (!isset($keys[$arg]) || botCfg($db, (int)$agent['id'])['events_chat_id'] === '') { botAdminEvents($db, $bot, $agent, $chat); return; }
            botState($db, $u, 'evtopic', $arg);
            botSay($db, $bot, $chat, "شماره‌ی تاپیک برای «" . bh(botEventTypes()[$keys[$arg]][0]) . "» را بفرستید. برای بدون تاپیک <code>-</code> بفرستید.", [[botAB('لغو', 'a:ev')]]); return;
        case 'pend':
            $s = $db->prepare("SELECT id FROM tg_orders WHERE bot_id=? AND status='pending_review' ORDER BY id LIMIT 5"); $s->execute([(int)$bot['id']]);
            $ids = $s->fetchAll(PDO::FETCH_COLUMN);
            if (!$ids) { botSay($db, $bot, $chat, 'سفارشی در انتظار نیست.', [[botAB('بازگشت', 'a:home')]]); return; }
            foreach ($ids as $id) botNotifyOrder($db, $bot, (int)$id);
            return;
        case 'cp': botState($db, $u, ''); botAdminCoupons($db, $bot, $chat, $arg); return;
        case 'cv': botAdminCouponView($db, $bot, $chat, $arg); return;
        case 'ca':
            botState($db, $u, 'cpadd');
            botSay($db, $bot, $chat, "کد تخفیف جدید را در یک خط بفرستید:\n<code>کد نوع مقدار سقف‌کل سقف‌هرکاربر روزانقضا</code>\n\nنوع: <b>percent</b> (درصد) یا <b>amount</b> (مبلغ ثابت به تومان)\nسقف‌کل: ۰ = نامحدود (پیش‌فرض ۰) — سقف‌هرکاربر: ۰ = نامحدود (پیش‌فرض ۱) — روزانقضا: ۰ = بدون انقضا (پیش‌فرض ۰)\n\nمثال:\n<code>EID20 percent 20 100 1 30</code>\n<code>GIFT50 amount 50000</code>", [[botAB('بازگشت', 'a:cp')]]);
            return;
        case 'ct':
            $c = botCouponRow($db, $bot, $arg);
            if ($c) {
                $new = (int)$c['active'] === 1 ? 0 : 1;
                $db->prepare('UPDATE tg_coupons SET active=? WHERE id=? AND bot_id=?')->execute([$new, $arg, (int)$bot['id']]);
                botAudit($db, $bot, $chat, 'coupon_toggle', (string)$c['code'], (int)$c['active'] . ' → ' . $new);
            }
            botAdminCouponView($db, $bot, $chat, $arg);
            return;
        case 'cd':
            $c = botCouponRow($db, $bot, $arg);
            if (!$c) { botSay($db, $bot, $chat, 'کد پیدا نشد.', [[botAB('بازگشت', 'a:cp')]]); return; }
            botSay($db, $bot, $chat, 'کد تخفیف <code>' . bh((string)$c['code']) . '</code> حذف شود؟', [[botAB('✅ بله، حذف شود', 'a:cy:' . $arg, 'danger'), botAB('لغو', 'a:cv:' . $arg)]]);
            return;
        case 'cy':
            $c = botCouponRow($db, $bot, $arg);
            if (!$c) { botSay($db, $bot, $chat, 'کد پیدا نشد.', [[botAB('بازگشت', 'a:cp')]]); return; }
            botAtomic($db, function () use ($db, $bot, $arg): void {
                $db->prepare('DELETE FROM tg_coupon_uses WHERE coupon_id=? AND bot_id=?')->execute([$arg, (int)$bot['id']]);
                $db->prepare('DELETE FROM tg_coupons WHERE id=? AND bot_id=?')->execute([$arg, (int)$bot['id']]);
            });
            botAudit($db, $bot, $chat, 'coupon_delete', (string)$c['code']);
            botSay($db, $bot, $chat, '✅ کد تخفیف حذف شد.');
            botAdminCoupons($db, $bot, $chat);
            return;
        case 'tk': botTicketAdminList($db, $bot, $chat, $arg); return;
        case 'tkt': botTicketAdminView($db, $bot, $chat, $arg); return;
        case 'tka':
            $ticket = botTicketAdminOwned($db, $bot, $arg);
            if (!$ticket || (string)$ticket['status'] !== 'open') { botSay($db, $bot, $chat, 'تیکت باز پیدا نشد.', [[botAB('بازگشت', 'a:tk:0')]]); return; }
            botState($db, $u, 'ticket_answer', $arg);
            $db->prepare('UPDATE tg_users SET draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['', (int)$u['id'], (int)$bot['id'], $chat]);
            botSay($db, $bot, $chat, 'پاسخ تیکت #' . $arg . ' را بفرستید.'); return;
        case 'tkc': botTicketAdminClose($db, $bot, $chat, $arg); return;
        case 'ck': botCannedAdminList($db, $bot, $chat, $arg); return;
        case 'cka':
            $returnTicket = $arg > 0 && botTicketAdminOwned($db, $bot, $arg) ? $arg : 0;
            botState($db, $u, 'canned_title', $returnTicket);
            $db->prepare('UPDATE tg_users SET draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['', (int)$u['id'], (int)$bot['id'], $chat]);
            botSay($db, $bot, $chat, 'عنوان پاسخ آماده را بفرستید.'); return;
        case 'ckd':
            $returnTicket = (int)($p[2] ?? 0);
            $q = $db->prepare('SELECT title FROM tg_canned WHERE id=? AND bot_id=?'); $q->execute([$arg, (int)$bot['id']]); $title = $q->fetchColumn();
            if ($title !== false) { $db->prepare('DELETE FROM tg_canned WHERE id=? AND bot_id=?')->execute([$arg, (int)$bot['id']]); botAudit($db, $bot, $chat, 'canned_delete', (string)$title); }
            botSay($db, $bot, $chat, $title === false ? 'پاسخ آماده پیدا نشد.' : 'پاسخ آماده حذف شد.'); botCannedAdminList($db, $bot, $chat, $returnTicket); return;
        case 'cks':
            $ticketId = (int)($p[1] ?? 0); $cannedId = (int)($p[2] ?? 0);
            $ticket = botTicketAdminOwned($db, $bot, $ticketId); $q = $db->prepare('SELECT title, text FROM tg_canned WHERE id=? AND bot_id=?'); $q->execute([$cannedId, (int)$bot['id']]); $canned = $q->fetch(PDO::FETCH_ASSOC);
            if (!$ticket || (string)$ticket['status'] !== 'open' || !$canned) { botSay($db, $bot, $chat, 'تیکت یا پاسخ آماده پیدا نشد.'); return; }
            botTicketAdminReply($db, $bot, $chat, $ticketId, (string)$canned['text'], 'canned'); return;
        case 'bk': botAdminBackup($db, $bot, $agent, $chat); return;
        case 'bkn':
            $r = botBackupManual($db, $bot, $chat);
            if (($r['status'] ?? '') === 'wait') botSay($db, $bot, $chat, '⏳ بکاپ دستی حداکثر ساعتی یک‌بار مجاز است؛ ' . (int)ceil((int)$r['wait'] / 60) . ' دقیقه‌ی دیگر دوباره امتحان کنید.', [[botAB('بازگشت', 'a:bk')]]);
            else botSay($db, $bot, $chat, $r['ok'] ? '✅ بکاپ ارسال شد.' : ($r['status'] === 'blocked' ? '⛔ بکاپ به‌دلیل خطای اعتبارسنجی ارسال نشد.' : '⚠️ ارسال بکاپ ناموفق بود.'), [[botAB('بازگشت', 'a:bk')]]);
            return;
        case 'tu': botTutorialAdminHome($db, $bot, $chat); return;
        case 'tul': botTutorialAdminList($db, $bot, $chat, $arg === 1 ? 'faq' : 'tutorial'); return;
        case 'tun':
            $kind = $arg === 1 ? 'faq' : 'tutorial'; botState($db, $u, 'tut_add_title', $kind === 'faq' ? 1 : 0);
            $db->prepare('UPDATE tg_users SET draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['', (int)$u['id'], (int)$bot['id'], $chat]);
            botSay($db, $bot, $chat, 'عنوان ' . ($kind === 'faq' ? 'سوال متداول' : 'آموزش') . ' را بفرستید.'); return;
        case 'tuv': botTutorialAdminView($db, $bot, $chat, $arg); return;
        case 'tue':
            if (!botTutorialRow($db, $bot, $arg)) { botSay($db, $bot, $chat, 'مورد پیدا نشد.'); return; }
            botState($db, $u, 'tut_edit_title', $arg); $db->prepare('UPDATE tg_users SET draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute(['', (int)$u['id'], (int)$bot['id'], $chat]);
            botSay($db, $bot, $chat, 'عنوان جدید را بفرستید.'); return;
        case 'tuo':
            $row = botTutorialRow($db, $bot, $arg);
            if (!$row) { botSay($db, $bot, $chat, 'مورد پیدا نشد.'); return; }
            $new = (int)$row['active'] === 1 ? 0 : 1;
            $db->prepare('UPDATE tg_tutorials SET active=? WHERE id=? AND bot_id=? AND kind=?')->execute([$new, $arg, (int)$bot['id'], (string)$row['kind']]);
            botAudit($db, $bot, $chat, 'tutorial_toggle', (string)$arg, ['active' => $new]); botTutorialAdminView($db, $bot, $chat, $arg); return;
        case 'tud':
            $row = botTutorialRow($db, $bot, $arg);
            if (!$row) { botSay($db, $bot, $chat, 'مورد پیدا نشد.', [[botAB('بازگشت', 'a:tu')]]); return; }
            $db->prepare('DELETE FROM tg_tutorials WHERE id=? AND bot_id=? AND kind=?')->execute([$arg, (int)$bot['id'], (string)$row['kind']]);
            botAudit($db, $bot, $chat, 'tutorial_delete', (string)$arg); botSay($db, $bot, $chat, 'مورد حذف شد.'); botTutorialAdminList($db, $bot, $chat, (string)$row['kind']); return;
        case 'tus':
            $direction = (string)($p[2] ?? '');
            botTutorialMove($db, $bot, $chat, $arg, $direction); return;
        case 'ag': botAgCallback($db, $bot, $agent, $u, $p); return;
        case 'em': botEmoCallback($db, $bot, $agent, $u, $p); return;
        case 'ad': botAdminList($db, $bot, $chat); return;
        case 'aa':
            botState($db, $u, 'adadd');
            botSay($db, $bot, $chat, "chat id عددی ادمین جدید را بفرستید.\n(هر کاربر می‌تواند آیدی عددی خود را از ربات‌هایی مثل @userinfobot بگیرد؛ ادمین باید ربات را استارت کرده باشد.)\nمجوز پیش‌فرض: سفارش‌ها؛ بعد از افزودن می‌توانید تغییر دهید.");
            return;
        case 'ae': botAdminEdit($db, $bot, $chat, $arg); return;
        case 'ap':
            $row = botAdminRow($db, $bot, $arg); $idx = (int)($p[2] ?? -1); $keys = array_keys(botPermList());
            if (!$row || !isset($keys[$idx])) { botSay($db, $bot, $chat, 'پیدا نشد.', [[botAB('بازگشت', 'a:ad')]]); return; }
            $has = botPermsParse((string)$row['perms']); $k = $keys[$idx];
            $has = in_array($k, $has, true) ? array_values(array_diff($has, [$k])) : array_merge($has, [$k]);
            botAdminSetPerms($db, $bot, $chat, (int)$row['chat_id'], $has);
            botAdminEdit($db, $bot, $chat, $arg);
            return;
        case 'ar':
            $row = botAdminRow($db, $bot, $arg);
            if (!$row) { botSay($db, $bot, $chat, 'پیدا نشد.', [[botAB('بازگشت', 'a:ad')]]); return; }
            botSay($db, $bot, $chat, 'ادمین <code>' . (int)$row['chat_id'] . '</code> حذف شود؟', [[botAB('✅ بله، حذف شود', 'a:ay:' . $arg, 'danger'), botAB('لغو', 'a:ae:' . $arg)]]);
            return;
        case 'ay':
            $row = botAdminRow($db, $bot, $arg);
            if (!$row) { botSay($db, $bot, $chat, 'پیدا نشد.', [[botAB('بازگشت', 'a:ad')]]); return; }
            $r = botAdminRemove($db, $bot, $chat, (int)$row['chat_id']);
            botSay($db, $bot, $chat, ($r['ok'] ? '✅ ' : '⚠️ ') . bh($r['msg']));
            botAdminList($db, $bot, $chat);
            return;
    }
}

// ------------------------------------------------------------------ مسیریابی پیام‌ها
function botSupportView(PDO $db, array $bot, array $cfg, int $chat): void {
    $t = trim((string)$cfg['support']);
    $text = $t !== '' ? botEmo(bh($t)) : 'پشتیبانی هنوز تنظیم نشده است.';
    $kb = [[botAB('🎫 تیکت جدید', 't:new', 'primary'), botAB('تیکت‌های من', 't:list:0')], [botAB('بازگشت به منو', 'm:home')]];
    botSay($db, $bot, $chat, $text, $kb);
}
/** دکمه‌های کاربر (و کامندهای معادل‌شان). خرید/تست/شارژ/تمدید از botGate رد می‌شوند. */
function botUserCb(PDO $db, array $bot, array $agent, array $cfg, array $u, string $k, string $v): void {
    $chat = (int)$u['chat_id'];
    // callbackهای دارای شناسه‌ی حساب، حتی پیش از تغییر state یا بررسی عضویت، مالکیت ربات و چت را اعتبارسنجی می‌کنند.
    $accountId = null;
    if (in_array($k, ['ac', 'rn', 'tr', 'n'], true)) $accountId = (int)$v;
    elseif (in_array($k, ['rp', 'tp', 'rq', 'tq', 'rw', 'tw', 'rc', 'tc', 'gr', 'gx'], true)) {
        [$accountPart] = array_pad(explode(':', $v, 2), 2, '0');
        $accountId = (int)$accountPart;
    }
    if ($accountId !== null && !botOwnedAccount($db, $bot, $chat, $accountId)) {
        $resume = json_decode((string)($u['draft'] ?? ''), true);
        if (is_array($resume) && ($resume['bot_gate_resume'] ?? '') === 'rn' && (int)($resume['account_id'] ?? 0) === $accountId)
            $db->prepare("UPDATE tg_users SET draft='' WHERE id=? AND bot_id=? AND chat_id=?")->execute([(int)$u['id'], (int)$bot['id'], $chat]);
        botSay($db, $bot, $chat, 'حساب پیدا نشد.', botMn($db, $bot, $cfg, $chat));
        return;
    }
    if ($k === 'm' && in_array($v, ['test', 'buy', 'wal', 'acc', 'dl', 'sup'], true) && !botIsStaff($db, $bot, $chat)) { // دکمه‌ی خاموش‌شده
        foreach (botMenuClean($cfg['menu'] ?? null) as $it) if ($it['k'] === $v && !$it['on']) { botSay($db, $bot, $chat, 'این بخش فعلاً غیرفعال است.', botMn($db, $bot, $cfg, $chat)); return; }
    }
    $mn = botMn($db, $bot, $cfg, $chat);
    if (in_array((string)$u['state'], ['ticket_subject', 'ticket_message', 'ticket_reply'], true) && $k !== 't') { // خروج از گفتگوی تیکت با هر دکمه/کامند دیگر
        $db->prepare("UPDATE tg_users SET state='',state_val=0,draft='' WHERE id=? AND bot_id=? AND chat_id=?")->execute([(int)$u['id'], (int)$bot['id'], $chat]);
        $u['state'] = ''; $u['state_val'] = 0; $u['draft'] = '';
    }
    if ((string)$u['state'] === 'coupon' && $k !== 'cq') botState($db, $u, ''); // از انتظار «کد تخفیف» با هر دکمه‌ی دیگر خارج می‌شود
    elseif ((string)$u['state'] === 'svc_coupon' && !in_array($k, ['rq', 'tq'], true)) {
        $db->prepare("UPDATE tg_users SET state='',state_val=0,draft='' WHERE id=? AND bot_id=? AND chat_id=?")
           ->execute([(int)$u['id'], (int)$bot['id'], $chat]);
        $u['state'] = ''; $u['state_val'] = 0; $u['draft'] = '';
    }
    switch ($k) {
        case 't': botTicketUserCallback($db, $bot, $cfg, $u, $v); return;
        case 'cl': botClubCallback($db, $bot, $cfg, $u, $v); return;
        case 'm':
            if ($v === 'test') { if (botGate($db, $bot, $cfg, $u, 'test')) botGiveTest($db, $bot, $agent, $cfg, $u); }
            elseif ($v === 'buy') { if (botGate($db, $bot, $cfg, $u, 'buy')) botShowPlans($db, $bot, $cfg, $chat); }
            elseif ($v === 'wal') botWalletView($db, $bot, $cfg, $u);
            elseif ($v === 'acc') botMyAccounts($db, $bot, $cfg, $chat, 0);
            elseif ($v === 'topup') { if (botGate($db, $bot, $cfg, $u, 'charge')) botTopupAsk($db, $bot, $cfg, $u); }
            elseif ($v === 'txs') botMyTx($db, $bot, $cfg, $u, 0);
            elseif ($v === 'ord') botMyOrders($db, $bot, $cfg, $u, 0);
            elseif ($v === 'dl') botSay($db, $bot, $chat, 'لینک دانلود برنامه:' . "\n" . bh(botDlUrl($db, $cfg)), $mn);
            elseif ($v === 'sup') botSupportView($db, $bot, $cfg, $chat);
            elseif ($v === 'tuts') botTutorialCustomerList($db, $bot, $chat, 'tutorial');
            elseif ($v === 'faqs') botTutorialCustomerList($db, $bot, $chat, 'faq');
            elseif (strpos($v, 'tv:') === 0) botTutorialCustomerView($db, $bot, $chat, (int)substr($v, 3));
            elseif ($v === 'help') botSay($db, $bot, $chat, 'راهنما: از منوی اصلی آموزش‌ها و سوالات متداول را ببینید؛ برای گفتگو با پشتیبانی، بخش «پشتیبانی» و سپس «تیکت جدید» را باز کنید.', $mn);
            else botSay($db, $bot, $chat, botTx($cfg, 'menu'), $mn);
            return;
        case 'fj': // «عضو شدم»: کش پاک و دوباره بررسی؛ در صورت موفقیت همان عملیات اجرا می‌شود
            $act = (string)preg_replace('/[^a-z]/', '', $v); $map = botGateActions();
            $db->prepare('UPDATE tg_users SET fj_ok_until=0 WHERE id=? AND bot_id=?')->execute([(int)$u['id'], (int)$bot['id']]);
            $u['fj_ok_until'] = 0;
            if (!isset($map[$act])) { botSay($db, $bot, $chat, botTx($cfg, 'menu'), $mn); return; }
            if (!botGate($db, $bot, $cfg, $u, $act)) return;
            $u['fj_ok_until'] = time() + 60; // همین دور دوباره API صدا زده نشود
            $resume = json_decode((string)($u['draft'] ?? ''), true);
            if ($act === 'renew' && is_array($resume) && ($resume['bot_gate_resume'] ?? '') === 'rn' && (int)($resume['account_id'] ?? 0) > 0) {
                $db->prepare("UPDATE tg_users SET draft='' WHERE id=? AND bot_id=? AND chat_id=?")->execute([(int)$u['id'], (int)$bot['id'], $chat]);
                botUserCb($db, $bot, $agent, $cfg, $u, 'rn', (string)(int)$resume['account_id']);
                return;
            }
            [$k2, $v2] = explode(':', $map[$act], 2);
            botUserCb($db, $bot, $agent, $cfg, $u, $k2, $v2);
            return;
        case 'p': if (botGate($db, $bot, $cfg, $u, 'buy')) botPlanChoose($db, $bot, $cfg, $u, (int)$v); return;
        case 'cp': // cp:<planId> یا cp:<planId>:<کد تخفیف>
            [$pid, $cd] = array_pad(explode(':', $v, 2), 2, '');
            if (botGate($db, $bot, $cfg, $u, 'buy')) botStartOrder($db, $bot, $cfg, $u, (int)$pid, $cd);
            return;
        case 'wp':
            [$pid, $cd] = array_pad(explode(':', $v, 2), 2, '');
            if (botGate($db, $bot, $cfg, $u, 'buy')) botBuyWallet($db, $bot, $agent, $cfg, $u, (int)$pid, $cd);
            return;
        case 'cq': if (botGate($db, $bot, $cfg, $u, 'buy')) botCouponAsk($db, $bot, $cfg, $u, (int)$v); return;
        case 'gp': // gp:<planId>:<methodId>
            [$pid, $mid] = array_pad(explode(':', $v, 2), 2, '0');
            if (botGate($db, $bot, $cfg, $u, 'buy')) botGwPlan($db, $bot, $cfg, $u, (int)$pid, (int)$mid);
            return;
        case 'gr': case 'gx': // gr|gx:<accId>:<targetId>:<methodId>
            [$accId, $targetId, $mid] = array_pad(explode(':', $v, 3), 3, '0');
            if (botGate($db, $bot, $cfg, $u, 'renew')) botGwService($db, $bot, $cfg, $u, $k === 'gr' ? 'renew' : 'traffic', (int)$accId, (int)$targetId, (int)$mid);
            return;
        case 'gt': // gt:<methodId|0=کارت>:<مبلغ>
            [$mid, $amt] = array_pad(explode(':', $v, 2), 2, '0');
            if (botGate($db, $bot, $cfg, $u, 'charge')) botGwTopup($db, $bot, $cfg, $u, (int)$mid, (int)$amt);
            return;
        case 'gc': botGwCheck($db, $bot, $agent, $cfg, $u, (int)$v); return;
        case 'ak': botMyAccounts($db, $bot, $cfg, $chat, (int)$v); return;
        case 'ac': botAccountDetail($db, $bot, $cfg, $chat, (int)$v); return;
        case 'rn':
            if (botGate($db, $bot, $cfg, $u, 'renew')) {
                $resume = json_decode((string)($u['draft'] ?? ''), true);
                if (is_array($resume) && ($resume['bot_gate_resume'] ?? '') === 'rn')
                    $db->prepare("UPDATE tg_users SET draft='' WHERE id=? AND bot_id=? AND chat_id=?")->execute([(int)$u['id'], (int)$bot['id'], $chat]);
                botAccountRenewPage($db, $bot, $cfg, $chat, (int)$v);
            } else {
                // عضویت اجباری نباید دکمه‌ی مستقیم تمدید را پس از تأیید عضویت به صفحه‌ی عمومی منحرف کند.
                $draft = json_encode(['bot_gate_resume' => 'rn', 'account_id' => (int)$v], JSON_UNESCAPED_UNICODE);
                $db->prepare('UPDATE tg_users SET draft=? WHERE id=? AND bot_id=? AND chat_id=?')->execute([$draft, (int)$u['id'], (int)$bot['id'], $chat]);
            }
            return;
        case 'rp':
            [$accId, $targetId] = array_pad(explode(':', $v, 2), 2, '0');
            if (botGate($db, $bot, $cfg, $u, 'renew')) botServiceCheckout($db, $bot, $cfg, $u, 'renew', (int)$accId, (int)$targetId);
            return;
        case 'tr':
            if (botGate($db, $bot, $cfg, $u, 'renew')) botAccountTrafficPage($db, $bot, $cfg, $chat, (int)$v);
            return;
        case 'tp':
            [$accId, $targetId] = array_pad(explode(':', $v, 2), 2, '0');
            if (botGate($db, $bot, $cfg, $u, 'renew')) botServiceCheckout($db, $bot, $cfg, $u, 'traffic', (int)$accId, (int)$targetId);
            return;
        case 'rq': case 'tq':
            [$accId, $targetId] = array_pad(explode(':', $v, 2), 2, '0');
            $kind = $k === 'rq' ? 'renew' : 'traffic';
            if (botGate($db, $bot, $cfg, $u, 'renew')) botServiceCouponAsk($db, $bot, $cfg, $u, $kind, (int)$accId, (int)$targetId);
            return;
        case 'rw': case 'tw': case 'rc': case 'tc':
            [$accId, $targetId, $code] = array_pad(explode(':', $v, 3), 3, '');
            $kind = in_array($k, ['rw', 'rc'], true) ? 'renew' : 'traffic';
            if (botGate($db, $bot, $cfg, $u, 'renew')) {
                if (in_array($k, ['rw', 'tw'], true)) botServiceWalletPay($db, $bot, $agent, $cfg, $u, $kind, (int)$accId, (int)$targetId, $code);
                else botServiceCardPay($db, $bot, $cfg, $u, $kind, (int)$accId, (int)$targetId, $code);
            }
            return;
        case 'n': botNewPassword($db, $bot, $cfg, $chat, (int)$v); return;
        case 'tx': botMyTx($db, $bot, $cfg, $u, (int)$v); return;
        case 'od': botMyOrders($db, $bot, $cfg, $u, (int)$v); return;
        case 'x':
            $cx = $db->prepare("UPDATE tg_orders SET status='cancelled', updated_at=? WHERE id=? AND bot_id=? AND chat_id=? AND status='awaiting_receipt'");
            $cx->execute([time(), (int)$v, (int)$bot['id'], $chat]);
            if ($cx->rowCount() === 1) botCouponReleaseByOrder($db, (int)$bot['id'], (int)$v);
            botState($db, $u, '');
            botSay($db, $bot, $chat, 'سفارش لغو شد.', $mn);
            return;
    }
}
/** اجرای کامند؛ ناشناخته = منوی اصلی. /admin فقط برای ادمین‌ها. */
function botCommand(PDO $db, array $bot, array $agent, array $cfg, array $u, array $pc, bool $staff): void {
    $chat = (int)$u['chat_id']; $cmd = (string)$pc['cmd'];
    botState($db, $u, '');
    if ($cmd === 'start') {
        if (!empty($u['_new'])) { $ref = preg_match('#^ref_(\d{4,20})$#', (string)$pc['arg'], $mm) ? (int)$mm[1] : 0; botOnNewUser($db, $bot, $cfg, $u, $ref); }
        botSay($db, $bot, $chat, botTx($cfg, 'welcome'), botMn($db, $bot, $cfg, $chat));
        return;
    }
    if (($cmd === 'admin' || $cmd === 'panel') && $staff) { botAdminHome($db, $bot, $chat); return; }
    $reg = botUserCommands();
    if (isset($reg[$cmd])) { [$k, $v] = explode(':', (string)$reg[$cmd]['cb'], 2); botUserCb($db, $bot, $agent, $cfg, $u, $k, $v); return; }
    botSay($db, $bot, $chat, botTx($cfg, 'menu'), botMn($db, $bot, $cfg, $chat));
}
function botHandleUpdate(PDO $db, array $bot, array $upd): void {
    $GLOBALS['botEditCtx'] = null;
    botLazy($db);
    if (isset($upd['callback_query']) && is_array($upd['callback_query'])) { botOnCallback($db, $bot, $upd['callback_query']); return; }
    $m = $upd['message'] ?? null;
    if (!is_array($m) || (string)($m['chat']['type'] ?? '') !== 'private') return;
    $chat = (int)$m['chat']['id'];
    $agent = botAgentRow($db, (int)$bot['agent_id']);
    if (!$agent) { botSay($db, $bot, $chat, 'سرویس موقتاً در دسترس نیست.'); return; }
    $cfg = botCfg($db, (int)$agent['id']);
    $u = botUser($db, $bot, $chat, (string)($m['from']['username'] ?? ''));
    $staff = botIsStaff($db, $bot, $chat);
    if ((int)$u['banned'] === 1 && !$staff) return;
    if (!botRateOk($db, $u, $staff)) return;
    if ($staff) botCommandsSync($db, $bot);
    $text = trim((string)($m['text'] ?? ''));
    $st = (string)$u['state'];
    $pc = botParseCommand($bot, $text);
    if ($pc !== null) {
        if ($pc['other']) return; // خطاب به رباتِ دیگر
        $known = in_array($pc['cmd'], ['start', 'admin', 'panel'], true) || isset(botUserCommands()[$pc['cmd']]);
        // ادمینِ وسط ورودی متن (مثلاً پیام همگانی) که با «/» شروع می‌کند، متنش مصرف می‌شود؛ بقیه‌ی کامندهای ناشناخته = منوی اصلی
        if ($known || !($staff && in_array($st, botAdminStates(), true))) { botCommand($db, $bot, $agent, $cfg, $u, $pc, $staff); return; }
    }
    if ($staff && $st === 'em_add' && $text !== '' && botCanAct($db, $bot, $chat, 'settings') && botEmoHandle($db, $bot, $agent, $u, $m)) return; // ایموجی پریمیوم: entityها فقط از خود پیام خوانده می‌شود
    if ($staff && $text !== '' && in_array($st, botAdminStates(), true) && botAdminText($db, $bot, $agent, $u, $text)) return;
    if ($text !== '' && botTicketUserText($db, $bot, $u, $text)) return;
    if ($st === 'topamt' && $text !== '') { botTopupAmount($db, $bot, $cfg, $u, $text); return; }
    if ($st === 'svc_coupon' && $text !== '') { botServiceCouponText($db, $bot, $cfg, $u, $text); return; }
    if ($st === 'coupon' && $text !== '') { botCouponText($db, $bot, $cfg, $u, $text); return; }
    if ($st === 'receipt' && (!empty($m['photo']) || !empty($m['document']))) { botReceipt($db, $bot, $cfg, $u, $m); return; }
    if ($st === 'receipt') { botSay($db, $bot, $chat, 'لطفاً <b>عکس رسید</b> را بفرستید یا سفارش را لغو کنید.', [[botBL($cfg, 'cancel', ['callback_data' => 'x:' . (int)$u['state_val']])]]); return; }
    if ($st === 'track' && $text !== '') { botTracking($db, $bot, $cfg, $u, $text); return; }
    botSay($db, $bot, $chat, botTx($cfg, 'menu'), botMn($db, $bot, $cfg, $chat));
}
function botOnCallback(PDO $db, array $bot, array $cb): void {
    botTg($db, $bot, 'answerCallbackQuery', ['callback_query_id' => (string)($cb['id'] ?? '')]);
    $data = (string)($cb['data'] ?? '');
    $from = (int)($cb['from']['id'] ?? 0);
    $mchat = (string)($cb['message']['chat']['id'] ?? '');
    $agent = botAgentRow($db, (int)$bot['agent_id']);
    $parts = explode(':', $data, 2); $k = $parts[0]; $v = $parts[1] ?? '';
    // ---- دکمه‌های تأیید/رد سفارش: ادمینِ دارای مجوز orders (پیوی) یا هر عضو گروهِ ادمینِ ثبت‌شده برای همین ربات
    if ($k === 'oa' || $k === 'or') {
        $adm = (string)$bot['admin_chat_id'];
        $inGroup = $adm !== '' && $mchat === $adm;
        if (!$inGroup && !($from > 0 && botCan($db, $bot, $from, 'orders'))) return;
        $evg = (!$inGroup && $mchat !== '' && $mchat[0] === '-') ? (string)botCfg($db, (int)$bot['agent_id'])['events_chat_id'] : '';
        $inEv = $evg !== '' && $mchat === $evg; // دکمه‌ی گروه گزارش: فقط کسی که مجوز orders دارد (بالا چک شد)
        $reply = ($inGroup || $inEv) ? $mchat : (string)$from;
        if (!$agent) { botSay($db, $bot, $reply, 'حساب نماینده غیرفعال است.'); return; }
        $oid = (int)$v;
        $r = $k === 'oa' ? botOrderApprove($db, $bot, $agent, $oid, 'telegram', $from) : botOrderReject($db, $bot, $agent, $oid, '', 'telegram', $from);
        if ($mchat === $reply && isset($cb['message']['message_id'])) botTg($db, $bot, 'editMessageReplyMarkup', ['chat_id' => $mchat, 'message_id' => (int)$cb['message']['message_id'], 'reply_markup' => ['inline_keyboard' => []]]);
        $rmsg = 'سفارش #' . $oid . ': ' . bh($r['msg']);
        if ($inEv) { $thr = (int)($cb['message']['message_thread_id'] ?? 0); botEventSend($db, $bot, $mchat, $thr > 0 ? $thr : null, $rmsg); }
        else botSay($db, $bot, $reply, $rmsg);
        return;
    }
    // ---- بقیه‌ی دکمه‌ها فقط از چت خصوصی خودِ کاربر
    $chat = $from;
    if ($chat === 0 || (string)($cb['message']['chat']['type'] ?? 'private') !== 'private') return;
    if (!$agent) { botSay($db, $bot, $chat, 'سرویس موقتاً در دسترس نیست.'); return; }
    $cfg = botCfg($db, (int)$agent['id']);
    $u = botUser($db, $bot, $chat, (string)($cb['from']['username'] ?? ''));
    $staff = botIsStaff($db, $bot, $chat);
    if ((int)$u['banned'] === 1 && !$staff) return;
    if (!botRateOk($db, $u, $staff)) return;
    $mid = (int)($cb['message']['message_id'] ?? 0);
    $GLOBALS['botEditCtx'] = $mid > 0 ? ['chat' => $chat, 'mid' => $mid] : null;
    try {
        if ($k === 'a') { if ($staff) botAdminCallback($db, $bot, $agent, $u, $v); return; }
        botUserCb($db, $bot, $agent, $cfg, $u, $k, $v);
    } finally { $GLOBALS['botEditCtx'] = null; }
}

// ------------------------------------------------------------------ ربات ادمین اصلی (وب‌پنل مدیر ← تب «ربات تلگرام»)
/**
 * مسیرهای API وب‌پنل برای ربات خودِ ادمین اصلی؛ همان قابلیت‌های پورتال نماینده (اتصال، تنظیمات، ظاهر و متن، پلن‌ها، سفارش‌ها).
 * فقط نشست وب‌پنل مدیر (needWebAdmin). از api.php در مسیر default صدا زده می‌شود؛ نام مسیر ناشناخته ← false.
 * ربات ادمین با agent_id = شناسه‌ی حساب ادمین ذخیره می‌شود؛ ربات‌های نمایندگان دست‌نخورده می‌مانند.
 */
function botAdminRoute(PDO $db, string $a, array $in): bool {
    if (strncmp($a, 'bot_', 4) !== 0) return false;
    switch ($a) {
    case 'bot_get':
        $me = needWebAdmin($db);
        $b = botRow($db, (int)$me['id']); $cfg = botCfg($db, (int)$me['id']); $base = payPublicBase($db);
        out(['bot' => $b ? botView($b) : null, 'cfg' => $cfg,
             'svc_keys' => array_map(fn($x) => 'g:' . (int)$x, ((array)($cfg['grps'] ?? [])) ?: (((int)($cfg['grp'] ?? 0) > 0) ? [(int)$cfg['grp']] : [])),
             'svc_key' => (((int)$cfg['svc'] > 0) ? ((int)$cfg['panel'] . ':' . (int)$cfg['svc']) : ''),
             'meta' => botUiMeta(), 'dl' => $base . '/dl.php', 'https' => strpos($base, 'https://') === 0]);
    case 'bot_save': // توکن (خالی = بدون تغییر)، chat id ادمین ربات، روشن/خاموش
        $me = needWebAdmin($db);
        botSaveConn($db, $me, (string)($in['token'] ?? ''), trim((string)($in['admin_chat_id'] ?? '')), payFlag($in['enabled'] ?? 1));
        out(['ok' => true]);
    case 'bot_cfg_save':
        $me = needWebAdmin($db);
        $c = botCfgClean($db, $me, $in);
        ownerSet($db, (int)$me['id'], 'bot_cfg', json_encode($c, JSON_UNESCAPED_UNICODE));
        out(['ok' => true, 'cfg' => $c]);
    case 'bot_options':
        $me = needWebAdmin($db);
        out(['options' => botSvcOptions($db, $me)]);
    case 'bot_plans':
        $me = needWebAdmin($db);
        out(['plans' => botPlans($db, (int)$me['id'], false)]);
    case 'bot_plan_save':
        $me = needWebAdmin($db); $oid = (int)$me['id'];
        $name = payClean($in['name'] ?? '', 60);
        if ($name === '') fail('نام پلن لازم است', 'Plan name is required');
        $gb = (float)($in['data_gb'] ?? 0);
        if ($gb < 0 || $gb > 100000) fail('حجم نامعتبر', 'Invalid data amount');
        $bytes = gbToBytes($gb); $days = payInt0($in['days'] ?? 0, 3650); $price = payInt($in['price'] ?? 0, 1, PAY_MAX_AMOUNT);
        $active = payFlag($in['active'] ?? 1);
        $id = (int)($in['id'] ?? 0);
        if (payFlag($in['is_agent'] ?? 0) && $bytes <= 0 && $days <= 0 && (int)($in['max_users'] ?? 0) <= 0) fail('برای پلن نمایندگی حداقل یکی از حجم، مدت یا تعداد کاربر لازم است', 'An agent plan needs at least one of data, days or users');
        if ($id > 0) {
            $u = $db->prepare("UPDATE plans SET name=?, data_bytes=?, days=?, price=?, active=? WHERE id=? AND owner_id=? AND kind='bot'");
            $u->execute([$name, $bytes, $days, $price, $active, $id, $oid]);
            if ($u->rowCount() !== 1) fail('پلن پیدا نشد', 'Plan not found', 404);
        } else {
            $c = $db->prepare("SELECT COUNT(*) FROM plans WHERE owner_id=? AND kind='bot'"); $c->execute([$oid]);
            if ((int)$c->fetchColumn() >= 100) fail('حداکثر ۱۰۰ پلن', 'At most 100 plans');
            $db->prepare("INSERT INTO plans (owner_id, kind, name, data_bytes, days, price, add_users, active, created_at) VALUES (?, 'bot', ?,?,?,?,0,?,?)")
               ->execute([$oid, $name, $bytes, $days, $price, $active, time()]);
            $id = (int)$db->lastInsertId();
        }
        botPlanMetaSet($db, $oid, $id, $in, true);
        out(['ok' => true, 'id' => $id]);
    case 'bot_plan_delete':
        $me = needWebAdmin($db);
        $d = $db->prepare("DELETE FROM plans WHERE id=? AND owner_id=? AND kind='bot'"); $d->execute([(int)($in['id'] ?? 0), (int)$me['id']]);
        if ($d->rowCount() === 1) botPlanMetaDel($db, (int)$me['id'], (int)($in['id'] ?? 0));
        out(['ok' => true]);
    case 'bot_orders':
        $me = needWebAdmin($db);
        out(['orders' => botOrdersList($db, (int)$me['id'], (string)($in['status'] ?? 'open'))]);
    case 'bot_order_approve':
        $me = needWebAdmin($db);
        $b = botRow($db, (int)$me['id']);
        if (!$b) fail('ربات ثبت نشده', 'No bot configured', 404);
        $r = botOrderApprove($db, $b, $me, (int)($in['id'] ?? 0), 'portal');
        if (!$r['ok']) fail($r['msg'], $r['msg'], 409);
        out(['ok' => true]);
    case 'bot_order_reject':
        $me = needWebAdmin($db);
        $b = botRow($db, (int)$me['id']);
        if (!$b) fail('ربات ثبت نشده', 'No bot configured', 404);
        $r = botOrderReject($db, $b, $me, (int)($in['id'] ?? 0), payClean($in['reason'] ?? '', 200), 'portal');
        if (!$r['ok']) fail($r['msg'], $r['msg'], 409);
        out(['ok' => true]);
    case 'bot_order_image': // POST؛ تصویر رسید به‌صورت data: URI (CSP وب‌پنل فقط img-src 'self' data: را می‌پذیرد). فقط رسید سفارش‌های ربات خودِ ادمین
        $me = needWebAdmin($db);
        $s = $db->prepare('SELECT id, receipt_file FROM tg_orders WHERE id=? AND agent_id=?'); $s->execute([(int)($in['id'] ?? 0), (int)$me['id']]);
        $o = $s->fetch(PDO::FETCH_ASSOC);
        $fn = $o ? basename((string)$o['receipt_file']) : '';
        $path = RECEIPT_DIR . '/' . $fn;
        if ($fn === '' || !is_file($path)) fail('رسید پیدا نشد', 'Receipt not found', 404);
        $mime = ['jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg', 'png' => 'image/png', 'gif' => 'image/gif', 'webp' => 'image/webp'][strtolower(pathinfo($fn, PATHINFO_EXTENSION))] ?? '';
        if ($mime === '' || filesize($path) > 12 * 1048576) fail('این فایل قابل نمایش نیست', 'This file cannot be previewed', 415);
        out(['src' => 'data:' . $mime . ';base64,' . base64_encode((string)file_get_contents($path))]);
    }
    return false;
}

require_once __DIR__ . '/bot_ext8.php'; // مرحله ۸: باشگاه مشتریان و بکاپ نماینده
require_once __DIR__ . '/bot_emoji.php'; // v16: کتابخانه‌ی ایموجی پریمیوم (ربات مدیر و نماینده)
require_once __DIR__ . '/bot_gw.php'; // v17: دستگاه/پلن نمایندگی در پلن ربات + درگاه آنلاین
require_once __DIR__ . '/bot_agents.php'; // v15: اعطا و مدیریت نماینده از ربات مدیر اصلی
