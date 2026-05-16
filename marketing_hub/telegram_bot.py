# -*- coding: utf-8 -*-
"""Telegram bot self-service cho marketing_hub.

Commands:
  /status   — web up/down, jobs pending/processing, DB size, uptime
  /jobs     — list 5 job mới nhất + status
  /audit    — chạy audit kho AI (count meta sai length, filler, trùng)
  /help     — list commands

Auth: chỉ chat_id trong AUTHORIZED_CHATS được dùng.
Token: load từ .env/telegram_bot_token.txt (vợ tạo bot qua @BotFather rồi paste).

Run: python telegram_bot.py  (hoặc start_telegram_bot.bat)
"""
import os, sys, io, time, json, sqlite3, requests, datetime
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(ROOT, '.env', 'telegram_bot_token.txt')
DB_PATH = os.path.join(ROOT, 'data', 'posts.db')
WEB_URL = 'http://127.0.0.1:5055'

# Auth: chỉ vợ Nghia (chat_id Telegram)
AUTHORIZED_CHATS = {6593753113}

POLL_TIMEOUT = 30  # seconds long-poll
START_TIME = time.time()


def load_token() -> str:
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError(
            f'Token file not found: {TOKEN_FILE}\n'
            f'Tao bot qua @BotFather tren Telegram, copy token, paste vao file nay.'
        )
    return open(TOKEN_FILE, encoding='utf-8').read().strip()


def tg_api(token: str, method: str, **params):
    url = f'https://api.telegram.org/bot{token}/{method}'
    try:
        r = requests.post(url, json=params, timeout=POLL_TIMEOUT + 5)
        return r.json()
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def fmt_uptime(secs: float) -> str:
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f'{h}h {m}m {s}s'


def cmd_help() -> str:
    return (
        'Marketing Hub Bot\n\n'
        '/status — web + DB status\n'
        '/jobs — 5 job mới nhất\n'
        '/audit — audit kho AI gen\n'
        '/help — danh sách lệnh\n\n'
        f'Web: {WEB_URL}'
    )


def cmd_status() -> str:
    # Web up?
    web_status = '🔴 DOWN'
    try:
        r = requests.get(WEB_URL, timeout=3)
        if r.status_code in (200, 302, 304):
            web_status = '🟢 UP'
    except Exception:
        pass

    # DB stats
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT status, COUNT(*) FROM content_jobs GROUP BY status")
        job_counts = dict(cur.fetchall())
        conn.close()
        db_size = os.path.getsize(DB_PATH) / 1024 / 1024
    except Exception as e:
        return f'❌ DB error: {e}'

    bot_uptime = fmt_uptime(time.time() - START_TIME)

    return (
        f'Marketing Hub Status\n\n'
        f'Web: {web_status}\n'
        f'URL: {WEB_URL}\n'
        f'DB: {db_size:.1f} MB\n'
        f'Bot uptime: {bot_uptime}\n\n'
        f'Jobs:\n' + '\n'.join(f'  {k}: {v}' for k, v in sorted(job_counts.items()))
    )


def cmd_jobs() -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, product_title, status, updated_at FROM content_jobs "
            "ORDER BY updated_at DESC LIMIT 5"
        )
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        return f'❌ DB error: {e}'

    if not rows:
        return 'Chưa có job nào.'

    lines = ['5 jobs mới nhất:']
    for r in rows:
        title = (r['product_title'] or '')[:55]
        lines.append(f'  #{r["id"]} [{r["status"]}] {title}')
    return '\n'.join(lines)


def cmd_audit() -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT ai_titles_json, ai_metas_json FROM content_jobs "
            "WHERE status IN ('draft','approved','synced','text_done') "
            "AND ai_titles_json IS NOT NULL"
        )
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        return f'❌ DB error: {e}'

    bad_t = 0
    bad_m = 0
    bad_filler = 0
    total_t = 0
    total_m = 0
    FILLERS = ['bền bỉ', 'đẹp mắt', 'free ship']

    for tj, mj in rows:
        try:
            titles = json.loads(tj or '[]')
            metas = json.loads(mj or '[]')
        except Exception:
            continue
        for t in titles:
            total_t += 1
            if not (30 <= len(t) <= 61):
                bad_t += 1
        for m in metas:
            total_m += 1
            if not (140 <= len(m) <= 160):
                bad_m += 1
            for f in FILLERS:
                if f.lower() in m.lower():
                    bad_filler += 1
                    break

    return (
        f'Audit kho AI gen ({len(rows)} jobs):\n\n'
        f'Title sai length: {bad_t}/{total_t}\n'
        f'Meta sai length: {bad_m}/{total_m}\n'
        f'Meta có filler: {bad_filler}\n'
    )


def handle_command(text: str) -> str:
    cmd = text.strip().split()[0].lower() if text.strip() else ''
    if cmd in ('/start', '/help'):
        return cmd_help()
    if cmd == '/status':
        return cmd_status()
    if cmd == '/jobs':
        return cmd_jobs()
    if cmd == '/audit':
        return cmd_audit()
    return 'Lệnh không nhận diện. Gõ /help để xem danh sách.'


def main():
    token = load_token()
    print(f'[bot] Token loaded ({len(token)} chars)')

    me = tg_api(token, 'getMe')
    if not me.get('ok'):
        print(f'[bot] getMe fail: {me}')
        sys.exit(1)
    print(f'[bot] Logged in as @{me["result"]["username"]}')

    offset = 0
    print(f'[bot] Polling... (authorized chats: {AUTHORIZED_CHATS})')

    while True:
        try:
            updates = tg_api(token, 'getUpdates', offset=offset, timeout=POLL_TIMEOUT)
            if not updates.get('ok'):
                time.sleep(5)
                continue
            for u in updates.get('result', []):
                offset = u['update_id'] + 1
                msg = u.get('message') or {}
                chat_id = msg.get('chat', {}).get('id')
                text = msg.get('text', '')
                if not chat_id or not text:
                    continue
                if chat_id not in AUTHORIZED_CHATS:
                    print(f'[bot] Reject unauthorized chat_id={chat_id}')
                    tg_api(token, 'sendMessage', chat_id=chat_id,
                           text='Chat khong duoc phep. Bot rieng tu.')
                    continue
                print(f'[bot] {chat_id} -> {text[:60]}')
                reply = handle_command(text)
                # Plain text — tránh hoàn toàn Markdown parse error
                resp = tg_api(token, 'sendMessage', chat_id=chat_id, text=reply)
                if not resp.get('ok'):
                    print(f'[bot] sendMessage fail: {resp.get("description")}')
        except KeyboardInterrupt:
            print('\n[bot] Stopped by user'); break
        except Exception as e:
            print(f'[bot] Loop error: {e}')
            time.sleep(5)


if __name__ == '__main__':
    main()
