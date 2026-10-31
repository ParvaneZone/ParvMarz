<?php
/**
 * v17 — (۱) پلن‌های ربات با «تعداد دستگاه» و «پلن نمایندگی» (فقط ربات مدیر اصلی)  (۲) درگاه آنلاین (تون‌پی/اطلس‌پی) در ربات مدیر و ربات نماینده.
 * فراداده‌ی پلن در جدول موجود settings (کلید o<صاحب>:pm:<شناسه‌ی پلن>) ذخیره می‌شود؛ ستون/جدول جدید لازم نیست (SQLite و MySQL یکسان).
 */

// ------------------------------------------------------------------ فراداده‌ی پلن
/** dev: -1 = پیش‌فرض تنظیمات ربات، ۰ = نامحدود، n = تعداد؛ ag: ۱ = پلن نمایندگی؛ mu: سقف کاربر نماینده (۰ = نامحدود) */
function botPlanMeta(PDO $db, int $ownerId, int $planId): array {
    $d = json_decode(ownerGet($db, $ownerId, 'pm:' . $planId, ''), true);
    if (!is_array($d)) return ['dev' => -1, 'ag' => 0, 'mu' => 0];
    return ['dev' => isset($d['d']) ? (int)$d['d'] : -1, 'ag' => !empty($d['a']) ? 1 : 0, 'mu' => max(0, (int)($d['u'] ?? 0))];
}
function botPlanMetaSet(PDO $db, int $ownerId, int $planId, array $in, bool $canAgent): void {
    $raw = $in['max_devices'] ?? '';
    $dev = ($raw === '' || $raw === null) ? -1 : max(0, min(1000, (int)$raw));
    $ag = $canAgent ? payFlag($in['is_agent'] ?? 0) : 0;
    $mu = $ag ? max(0, min(100000, (int)($in['max_users'] ?? 0))) : 0;
    ownerSet($db, $ownerId, 'pm:' . $planId, json_encode(['d' => $dev, 'a' => $ag, 'u' => $mu]));
}
function botPlanMetaDel(PDO $db, int $ownerId, int $planId): void {
    $db->prepare('DELETE FROM settings WHERE k=?')->execute(["o$ownerId:pm:$planId"]);
}
/** رشته‌ی دستگاه برای botMakeAccount: دستگاهِ پلن، وگرنه پیش‌فرض تنظیمات ربات */
function botDevStr(int $dev, array $cfg): string { return $dev >= 0 ? (string)$dev : (string)$cfg['s_dev']; }
function botPlanDevText(int $dev): string { return $dev < 0 ? '' : ($dev === 0 ? 'دستگاه نامحدود' : $dev . ' دستگاه'); }
/** پلن نمایندگی فقط در ربات مدیر اصلی فروخته می‌شود */
function botPlanSellable(PDO $db, int $agId, int $planId): bool {
    $m = botPlanMeta($db, $agId, $planId);
    if (!$m['ag']) return true;
    $a = botAgentRow($db, $agId);
    return $a && botIsAdminOwner($a);
}

/** مشخصات کامل پلن (نام، حجم، مدت، نمایندگی/سقف کاربر، دستگاه) برای نمایش قبل از اطلاعات پرداخت */
function botPlanSpecText(string $name, int $bytes, int $days, array $meta): string {
    $dv = botPlanDevText((int)$meta['dev']);
    return 'پلن: <b>' . bh($name) . "</b>\nحجم: " . botGb($bytes) . ' — مدت: ' . ($days > 0 ? $days . ' روز' : 'بدون انقضا')
        . ($meta['ag'] ? ' — نمایندگی' . ((int)$meta['mu'] > 0 ? ' (' . (int)$meta['mu'] . ' کاربر)' : '') : '') . ($dv !== '' ? ' — ' . $dv : '');
}

// ------------------------------------------------------------------ فروش پلن نمایندگی
/** ساخت نماینده از اسنپ‌شات پلن؛ همان شکل خروجی botMakeAccount (email, pass, id) و در خطا استثنا */
function botSellAgent(PDO $db, array $cfg, array $snap): array {
    $email = botGenEmail($db, $cfg, 'ag'); $pass = botGenPass();
    $dev = (int)($snap['dev'] ?? -1);
    $r = botAgCreate($db, $email, $pass, ['max_users' => (int)($snap['mu'] ?? 0), 'traffic_gb' => ((int)($snap['bytes'] ?? 0)) / 1073741824,
        'days' => (int)($snap['days'] ?? 0), 'max_devices' => $dev >= 0 ? $dev : null, 'note' => 'bot sale']);
    if (empty($r['ok'])) throw new RuntimeException((string)($r['msg'] ?? 'agent create failed'));
    return ['email' => $email, 'pass' => $pass, 'id' => (int)$r['id']];
}
function botSendAgentCreds(PDO $db, array $bot, array $cfg, int $chat, array $acc, array $snap): void {
    $GLOBALS['botEditCtx'] = null;
    $dev = botPlanDevText((int)($snap['dev'] ?? -1));
    $txt = "✅ حساب نمایندگی شما آماده است\n\n"
        . 'ایمیل: <code>' . bh($acc['email']) . "</code>\n"
        . 'رمز عبور: <code>' . bh($acc['pass']) . "</code>\n"
        . 'سقف کاربر: ' . ((int)($snap['mu'] ?? 0) > 0 ? (int)$snap['mu'] : 'نامحدود') . ' — حجم: ' . botGb((int)($snap['bytes'] ?? 0))
        . ' — مدت: ' . ((int)($snap['days'] ?? 0) > 0 ? (int)$snap['days'] . ' روز' : 'بدون انقضا') . ($dev !== '' ? ' — ' . $dev : '')
        . "\n\nپورتال نماینده: " . bh(botAgPortalUrl($db)) . "\nبعد از اولین ورود، رمز را تغییر دهید و دو مرحله‌ای را فعال کنید.";
    botSay($db, $bot, $chat, $txt, [[botBL($cfg, 'dl', ['url' => botAgPortalUrl($db)])]]);
}

// ------------------------------------------------------------------ درگاه آنلاین در ربات
function botGwTypes(): array { return ['tonpays' => 'تون‌پی', 'atlaspay' => 'اطلس‌پی']; }
function botGwMethods(PDO $db, int $agId, int $amount): array {
    $s = $db->prepare("SELECT * FROM pay_methods WHERE owner_id=? AND type IN ('tonpays','atlaspay') AND enabled=1 AND default_on=1 AND api_key<>'' AND (min_amount=0 OR min_amount<=?) AND (max_amount=0 OR max_amount>=?) ORDER BY id LIMIT 6");
    $s->execute([$agId, $amount, $amount]);
    return $s->fetchAll(PDO::FETCH_ASSOC);
}
function botGwMethod(PDO $db, int $agId, int $mid, int $amount): ?array {
    foreach (botGwMethods($db, $agId, $amount) as $m) if ((int)$m['id'] === $mid) return $m;
    return null;
}
function botHasCards(PDO $db, int $agId, int $amount): bool {
    $s = $db->prepare("SELECT 1 FROM pay_methods WHERE owner_id=? AND type='card' AND enabled=1 AND default_on=1 AND (min_amount=0 OR min_amount<=?) AND (max_amount=0 OR max_amount>=?) LIMIT 1");
    $s->execute([$agId, $amount, $amount]);
    return (bool)$s->fetchColumn();
}
/** ردیف دکمه‌های درگاه؛ $prefix مثل 'gp:12' و شناسه‌ی روش در انتها اضافه می‌شود */
function botGwRows(PDO $db, int $agId, int $amount, string $prefix): array {
    $rows = [];
    foreach (botGwMethods($db, $agId, $amount) as $m)
        $rows[] = [botAB('🌐 ' . ((string)$m['title'] !== '' ? (string)$m['title'] : 'پرداخت آنلاین (' . (botGwTypes()[$m['type']] ?? '') . ')'), $prefix . ':' . (int)$m['id'], 'primary')];
    return $rows;
}
function botGwSig(PDO $db, int $oid): string { return hash_hmac('sha256', 'bgw:' . $oid, appSecret($db)); }

/** ساخت سفارش pending_gateway + فاکتور در درگاه + ارسال لینک پرداخت به مشتری */
function botGwStart(PDO $db, array $bot, array $cfg, array $u, int $mid, string $kind, array $snap, int $price, int $refAcc = 0): void {
    $chat = (int)$u['chat_id']; $agId = (int)$bot['agent_id']; $bid = (int)$bot['id']; $now = time();
    $m = botGwMethod($db, $agId, $mid, $price);
    if (!$m) { botSay($db, $bot, $chat, 'این روش پرداخت برای این مبلغ در دسترس نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    $open = $db->prepare("SELECT COUNT(*) FROM tg_orders WHERE bot_id=? AND chat_id=? AND status='pending_gateway' AND created_at>?"); $open->execute([$bid, $chat, $now - 3600]);
    if ((int)$open->fetchColumn() >= 5) { botSay($db, $bot, $chat, 'چند پرداخت آنلاین باز دارید؛ ابتدا آن‌ها را تکمیل کنید یا کمی صبر کنید.', botMn($db, $bot, $cfg, $chat)); return; }
    $snap['pm'] = (int)$m['id'];
    $db->prepare("INSERT INTO tg_orders (bot_id, agent_id, chat_id, kind, ref_account_id, account_id, plan_snapshot, price, status, gateway, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,'pending_gateway',?,?,?)")
       ->execute([$bid, $agId, $chat, $kind, $refAcc, $refAcc, json_encode($snap, JSON_UNESCAPED_UNICODE), $price, (string)$m['type'], $now, $now]);
    $oid = (int)$db->lastInsertId();
    $ref = 'B' . $oid . '_' . bin2hex(random_bytes(3));
    $base = payPublicBase($db); $cb = strpos($base, 'https://') === 0 ? $base . '/api.php?a=botgw_cb&o=' . $oid . '&s=' . botGwSig($db, $oid) : '';
    $fail = function (string $why) use ($db, $bot, $cfg, $chat, $oid): void {
        $db->prepare("UPDATE tg_orders SET status='cancelled', note=?, updated_at=? WHERE id=? AND status='pending_gateway'")->execute([mb_substr($why, 0, 200), time(), $oid]);
        botSay($db, $bot, $chat, 'ساخت پرداخت در درگاه ناموفق بود؛ کمی بعد دوباره تلاش کنید یا روش دیگری انتخاب کنید.', botMn($db, $bot, $cfg, $chat));
        botEvent($db, $bot, 'error', '⚠️ ساخت فاکتور درگاه ناموفق بود (سفارش #' . $oid . '): ' . bh($why));
    };
    if ($m['type'] === 'atlaspay') {
        $body = ['merchantOrderRef' => $ref, 'baseAmountToman' => $price];
        if (($m['buyer_mode'] ?? 'none') === 'ask') $body['customerTelegramId'] = $chat;
        if ($cb !== '') $body['webhookUrl'] = $cb;
        $r = apCall($db, (string)$m['api_key'], 'POST', '/orders', $body); $d = $r['data'] ?? [];
        $iid = (int)($d['orderId'] ?? 0); $url = (string)($d['customerStartLink'] ?? ''); $final = (int)($d['totalAmountToman'] ?? 0);
        if (!$r['ok'] || $iid <= 0 || strpos($url, 'https://t.me/') !== 0 || $final < $price || $final > $price * 2 + 100000) { $fail('atlaspay ' . $r['code'] . ' ' . $r['error']); return; }
        $gref = 'ap:' . $iid;
    } else {
        $body = ['amount' => $price, 'order_id' => $ref];
        if (($m['buyer_mode'] ?? 'none') === 'ask') $body['buyer_chat_id'] = $chat;
        if ($cb !== '') $body['callback_url'] = $cb;
        $r = tpCall($db, (string)$m['api_key'], 'POST', '/api/v1/invoices/create', $body, (string)($m['base_url'] ?? '')); $d = $r['data'] ?? [];
        $iid = (string)($d['invoice_id'] ?? ''); $url = (string)($d['web_invoice_url'] ?? ''); if (strpos($url, 'https://') !== 0) $url = (string)($d['invoice_url'] ?? '');
        $final = (int)($d['final_amount'] ?? $price);
        if (!$r['ok'] || $iid === '' || strpos($url, 'https://') !== 0 || (int)($d['request_amount'] ?? -1) !== $price) { $fail('tonpays ' . $r['code'] . ' ' . $r['error']); return; }
        $gref = 'tp:' . $iid;
    }
    $snap['gw'] = ['ref' => $ref, 'final' => $final, 'id' => (string)$iid, 't' => (string)$m['type']];
    try {
        $db->prepare("UPDATE tg_orders SET gateway_ref=?, plan_snapshot=?, updated_at=? WHERE id=? AND status='pending_gateway'")
           ->execute([$gref, json_encode($snap, JSON_UNESCAPED_UNICODE), time(), $oid]);
    } catch (Throwable $e) { $fail('duplicate ref'); return; }
    $head = $kind === 'plan' ? botPlanSpecText((string)($snap['name'] ?? ''), (int)($snap['bytes'] ?? 0), (int)($snap['days'] ?? 0), ['dev' => (int)($snap['dev'] ?? -1), 'ag' => (int)($snap['ag'] ?? 0), 'mu' => (int)($snap['mu'] ?? 0)])
        : '<b>' . bh($kind === 'topup' ? 'شارژ کیف پول' : (string)($snap['name'] ?? '')) . '</b>';
    $txt = $head . "\nمبلغ: <b>" . botMoney($price) . '</b>' . ($final > $price ? "\nمبلغ قابل پرداخت (با کارمزد): <b>" . botMoney($final) . '</b>' : '')
         . "\n\nاز دکمه‌ی زیر پرداخت کنید؛ بعد از پرداخت، خودکار تأیید می‌شود. اگر پیام تأیید نیامد، «بررسی پرداخت» را بزنید.";
    botSay($db, $bot, $chat, $txt, [[botB($cfg, 'dl', '💳 پرداخت آنلاین', ['url' => $url])], [botAB('✅ بررسی پرداخت', 'gc:' . $oid, 'success')], [botBL($cfg, 'back', ['callback_data' => 'm:home'])]]);
}

/** استعلام از خود درگاه (با کلید صاحب ربات)؛ فقط با تطابق کامل مبلغ/شناسه اعتبار می‌دهد. خروجی: paid | pending | failed | flagged | done */
function botGwSync(PDO $db, array $bot, array $agent, int $oid): string {
    $os = $db->prepare("SELECT * FROM tg_orders WHERE id=? AND bot_id=? AND agent_id=? AND gateway IN ('tonpays','atlaspay')"); $os->execute([$oid, (int)$bot['id'], (int)$bot['agent_id']]);
    $o = $os->fetch(PDO::FETCH_ASSOC);
    if (!$o) return 'done';
    if ($o['status'] !== 'pending_gateway') return 'done';
    $snap = json_decode((string)$o['plan_snapshot'], true) ?: []; $gw = $snap['gw'] ?? null;
    if (!is_array($gw)) return 'pending';
    $ms = $db->prepare('SELECT * FROM pay_methods WHERE id=? AND owner_id=? AND type=?'); $ms->execute([(int)($snap['pm'] ?? 0), (int)$bot['agent_id'], (string)$o['gateway']]);
    $m = $ms->fetch(PDO::FETCH_ASSOC);
    if (!$m || $m['api_key'] === '') return 'pending';
    $paid = false; $bad = false; $dead = false;
    if ($o['gateway'] === 'atlaspay') {
        $r = apCall($db, (string)$m['api_key'], 'GET', '/orders/' . (int)$gw['id']);
        if (!$r['ok'] || (($r['data']['success'] ?? true) === false)) return 'pending';
        $d = $r['data']; $st = strtolower((string)($d['status'] ?? ''));
        $match = (int)($d['id'] ?? 0) === (int)$gw['id'] && (string)($d['merchantOrderRef'] ?? '') === (string)$gw['ref'] && isset($d['totalAmountToman']) && (int)$d['totalAmountToman'] === (int)$gw['final'];
        if (in_array($st, ['confirmed', 'settled'], true)) { if ($match && ($d['requiresManualDelivery'] ?? null) === false) $paid = true; else $bad = true; }
        elseif (in_array($st, ['rejected', 'expired', 'cancelled'], true)) $dead = true;
    } else {
        $r = tpCall($db, (string)$m['api_key'], 'GET', '/api/v1/invoices/check/' . rawurlencode((string)$gw['id']), null, (string)($m['base_url'] ?? ''));
        if (!$r['ok']) return 'pending';
        $d = $r['data']; $isPaid = ($d['paid'] ?? false) === true; $st = strtolower((string)($d['status'] ?? ''));
        $match = (string)($d['invoice_id'] ?? '') === (string)$gw['id'] && (!isset($d['order_id']) || (string)$d['order_id'] === (string)$gw['ref']) && isset($d['request_amount']) && (int)$d['request_amount'] === (int)$o['price'];
        if ($isPaid && $match && $st === 'completed') $paid = true;
        elseif ($isPaid) $bad = true;
        elseif (in_array($st, ['rejected', 'expired', 'cancelled', 'canceled', 'failed'], true)) $dead = true;
    }
    if ($bad) {
        if ((string)$o['note'] !== 'mismatch') {
            $db->prepare("UPDATE tg_orders SET note='mismatch', updated_at=? WHERE id=? AND status='pending_gateway'")->execute([time(), $oid]);
            botEvent($db, $bot, 'error', '⚠️ پرداخت درگاه برای سفارش #' . $oid . ' با اطلاعات سفارش نمی‌خواند (مغایرت/کسری)؛ اعتبار خودکار داده نشد و باید دستی بررسی شود.');
        }
        return 'flagged';
    }
    if ($dead) {
        $up = $db->prepare("UPDATE tg_orders SET status='cancelled', note=?, updated_at=? WHERE id=? AND status='pending_gateway'"); $up->execute([mb_substr((string)$st, 0, 30), time(), $oid]);
        return 'failed';
    }
    if (!$paid) return 'pending';
    // قفل اتمیک: فقط یک تماس برنده است؛ بعد همان مسیر تأیید سفارش (ساخت حساب/تمدید/شارژ) اجرا می‌شود
    $lk = $db->prepare("UPDATE tg_orders SET status='pending_review', tracking=?, updated_at=? WHERE id=? AND status='pending_gateway'");
    $lk->execute([mb_substr('gw:' . $gw['ref'], 0, 60), time(), $oid]);
    if ($lk->rowCount() !== 1) return 'done';
    $res = botOrderApprove($db, $bot, $agent, $oid, 'gateway', 0);
    if (empty($res['ok'])) {
        botEvent($db, $bot, 'error', '⚠️ پرداخت آنلاین سفارش #' . $oid . ' انجام شده ولی تأیید خودکار ناموفق بود: ' . bh((string)($res['msg'] ?? '')) . "\nسفارش در «در انتظار بررسی» مانده است؛ دستی تأیید کنید.");
    }
    return 'paid';
}
function botGwCheck(PDO $db, array $bot, array $agent, array $cfg, array $u, int $oid): void {
    $chat = (int)$u['chat_id'];
    $q = $db->prepare('SELECT id, status FROM tg_orders WHERE id=? AND bot_id=? AND chat_id=?'); $q->execute([$oid, (int)$bot['id'], $chat]);
    $o = $q->fetch(PDO::FETCH_ASSOC);
    if (!$o) { botSay($db, $bot, $chat, 'سفارش پیدا نشد.', botMn($db, $bot, $cfg, $chat)); return; }
    $r = botGwSync($db, $bot, $agent, $oid);
    if ($r === 'paid') return; // پیام نتیجه را خودِ تأیید سفارش می‌فرستد
    $msg = ['pending' => 'هنوز پرداختی برای این سفارش تأیید نشده است. بعد از پرداخت دوباره بزنید.', 'failed' => 'این پرداخت لغو یا منقضی شد.',
            'flagged' => 'پرداخت شما با سفارش مطابقت کامل نداشت؛ برای بررسی به پشتیبانی پیام دهید.',
            'done' => in_array($o['status'], ['approved', 'pending_review', 'approving'], true) ? 'این پرداخت قبلاً ثبت شده است.' : 'این سفارش دیگر فعال نیست.'][$r] ?? 'نامشخص';
    botSay($db, $bot, $chat, $msg, [[botAB('✅ بررسی پرداخت', 'gc:' . $oid, 'success')], [botBL($cfg, 'back', ['callback_data' => 'm:home'])]]);
}
/** webhook درگاه (بدون ورود؛ فقط با امضا). وضعیت از خود درگاه استعلام می‌شود، نه از بدنه */
function botGwCallback(PDO $db, int $oid, string $sig): array {
    if ($oid <= 0 || !hash_equals(botGwSig($db, $oid), $sig)) return ['ok' => false];
    $os = $db->prepare('SELECT bot_id, agent_id FROM tg_orders WHERE id=?'); $os->execute([$oid]);
    $o = $os->fetch(PDO::FETCH_ASSOC);
    if (!$o) return ['ok' => false];
    $bs = $db->prepare('SELECT * FROM tg_bots WHERE id=?'); $bs->execute([(int)$o['bot_id']]);
    $bot = $bs->fetch(PDO::FETCH_ASSOC); $agent = $bot ? botAgentRow($db, (int)$bot['agent_id']) : null;
    if (!$bot || !$agent) return ['ok' => false];
    $r = botTry(fn() => botGwSync($db, $bot, $agent, $oid));
    return ['ok' => true, 'status' => $r['ok'] ? $r['v'] : 'error'];
}

// ------------------------------------------------------------------ ورودی دکمه‌ها
function botGwPlan(PDO $db, array $bot, array $cfg, array $u, int $planId, int $mid): void {
    $chat = (int)$u['chat_id']; $agId = (int)$bot['agent_id'];
    $ps = $db->prepare("SELECT * FROM plans WHERE id=? AND owner_id=? AND kind='bot' AND active=1"); $ps->execute([$planId, $agId]);
    $pl = $ps->fetch(PDO::FETCH_ASSOC);
    if (!$pl || !botPlanFits(botAgentRow($db, $agId), $pl) || !botPlanSellable($db, $agId, $planId)) { botSay($db, $bot, $chat, 'این پلن دیگر موجود نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    $meta = botPlanMeta($db, $agId, $planId); $price = botPrice($cfg, (int)$pl['price']);
    botGwStart($db, $bot, $cfg, $u, $mid, 'plan', ['id' => (int)$pl['id'], 'name' => (string)$pl['name'], 'bytes' => (int)$pl['data_bytes'], 'days' => (int)$pl['days'],
        'price' => $price, 'base' => $price, 'coupon' => '', 'dev' => $meta['dev'], 'ag' => $meta['ag'], 'mu' => $meta['mu']], $price);
}
function botGwService(PDO $db, array $bot, array $cfg, array $u, string $kind, int $accId, int $targetId, int $mid): void {
    $chat = (int)$u['chat_id'];
    $t = botServiceTarget($db, $bot, $cfg, $chat, $kind, $accId, $targetId);
    if (!$t['ok']) { botSay($db, $bot, $chat, (string)$t['msg'], botMn($db, $bot, $cfg, $chat)); return; }
    $target = $t['target']; $price = (int)$target['base'];
    $name = ($kind === 'renew' ? 'تمدید: ' : 'حجم اضافه: ') . (string)$target['name'];
    botGwStart($db, $bot, $cfg, $u, $mid, $kind, ['id' => (int)$target['id'], 'name' => $name, 'action' => $kind, 'account_id' => $accId, 'bytes' => (int)$target['bytes'],
        'days' => (int)$target['days'], 'gb' => (float)$target['gb'], 'price' => $price, 'base' => $price, 'coupon' => ''], $price, $accId);
}
function botGwTopup(PDO $db, array $bot, array $cfg, array $u, int $mid, int $amt): void {
    $chat = (int)$u['chat_id'];
    [$min, $max] = botTopupLimits($cfg);
    if ((int)$cfg['topup_on'] !== 1 || $amt < $min || ($max > 0 && $amt > $max)) { botSay($db, $bot, $chat, 'شارژ کیف پول با این مبلغ ممکن نیست.', botMn($db, $bot, $cfg, $chat)); return; }
    if ($mid === 0) { botTopupAmount($db, $bot, $cfg, $u, (string)$amt, true); return; }
    botGwStart($db, $bot, $cfg, $u, $mid, 'topup', ['topup' => $amt], $amt);
}
