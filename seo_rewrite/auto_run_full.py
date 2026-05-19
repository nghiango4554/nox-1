"""Auto-run full: Gemini generate 463 URL còn lại → push sheet.
- Fetch product info
- Gemini sinh 3T + 3M (auto retry 1 lần nếu vi phạm)
- Validate → log vi phạm
- Push batch 10 URL/lần lên sheet (cột E-N)
- Resume nếu interrupt (lưu processed.json)
"""
import os, sys, json, time, csv, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# === CONFIG ===
API_KEY = "AIzaSyAXk2hMOvGUi5h4ekXmT-gmCKG5COPN6_4"
MODEL = "gemini-2.5-flash-lite"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
TSV_FILE = os.path.join(WS, "seo_duplicates.tsv")
TOKEN = os.path.join(WS, ".secrets", "google_token.json")
PROGRESS_DIR = os.path.join(WS, "seo_rewrite", "auto_run")
os.makedirs(PROGRESS_DIR, exist_ok=True)
PROCESSED_FILE = os.path.join(PROGRESS_DIR, "processed.json")
LOG_FILE = os.path.join(PROGRESS_DIR, "progress.log")
VIOLATION_FILE = os.path.join(PROGRESS_DIR, "violations.json")

SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "SEO Duplicates"
START_ROW = 17  # row 1=header, 2-6=demo, 7-16=batch 1 → tiếp từ 17

UA = "Mozilla/5.0"

# 15 URL đã làm (5 demo + 10 batch 1)
DONE_URLS = {
    "https://sintech.vn/products/ram-apacer-ddr5-16gb-5600mhz-oc-nox-white-16x1",
    "https://sintech.vn/products/mainboard-asus-rog-strix-b860-a-wifi-ddr5",
    "https://sintech.vn/products/chuot-co-day-hp-gaming-mouse-x600-co-led",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-th360-v2-argb-snow",
    "https://sintech.vn/products/laptop-asus-rog-strix-g15-g513ic-hn002t-cu-dep",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-ocypus-delta-l24-bk-argb-v2-trang",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-ocypus-delta-l24-bk-argb-v2-den",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-ocypus-delta-l36-bk-argb-v2-den",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-ocypus-sigma-l36-pro-den",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-segotep-kunlun-mu-360-a-rgb",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-magfloe-420-ultra-argb",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-magfloe-360-ultra-argb",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-la240-s-argb-sync",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-th360-v2-ultra-argb-snow",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-th360-v2-ultra-argb-black",
}

SYSTEM_PROMPT = """Bạn là chuyên gia SEO cho Sintech.vn (shop PC/laptop/gaming gear, nền tảng Haravan).
NHIỆM VỤ: Viết 3 title + 3 meta description khác nhau cho 1 trang sản phẩm.

⚠️ LIMIT KÝ TỰ — TUÂN THỦ TUYỆT ĐỐI:
- Mỗi TITLE: 45-58 ký tự (TỐI ĐA TUYỆT ĐỐI là 61). NẾU VƯỢT 58 → REWRITE NGẮN HƠN.
- Mỗi META: 145-158 ký tự (TỐI THIỂU 140, TỐI ĐA 160). NẾU NGẮN HƠN 145 hoặc DÀI HƠN 158 → REWRITE LẠI.
- TRƯỚC KHI TRẢ VỀ: tự đếm len(title) và len(meta), nếu vi phạm phải rewrite.

LUẬT TITLE:
- KHÔNG chứa "Sintech" (Haravan tự thêm " – Sintech" sau)
- BẮT BUỘC có: tên model/sản phẩm + spec mạnh nhất + ngữ cảnh dùng/mua
- Chuẩn hóa kỹ thuật: GDDR6 (không viết DDR6), giữ đúng độ phân giải/tỷ lệ thật
- WiFi chỉ ghi khi mã sản phẩm thực sự có WiFi
- TRÁNH: nhồi keyword, lặp từ, lan man, spec không chắc

LUẬT META:
- BẮT BUỘC có: keyword chính/tên SP + 1 lợi ích rõ + 1 ngữ cảnh dùng + CTA nhẹ
- CTA viết IN HOA cụm hành động: "XEM NGAY tại Sintech", "THAM KHẢO NGAY tại Sintech", "KHÁM PHÁ NGAY", "CHỌN NGAY mẫu phù hợp tại Sintech"
- Tone: mượt, buyer-facing, bán hàng nhẹ, KHÔNG sáo rỗng
- 3 meta dùng 3 CTA khác nhau

QUY TẮC NGHIÊM:
- Spec không chắc → viết an toàn theo tên + nhu cầu, KHÔNG bịa
- 3 title KHÁC nhau rõ rệt (theo spec / theo nhu cầu / theo brand)

OUTPUT BẮT BUỘC: chỉ JSON.
{"titles": ["...","...","..."], "metas": ["...","...","..."]}
"""


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch_product(url):
    import re, html as h
    try:
        req = urllib.request.Request(url + ".json", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            p = json.loads(r.read().decode("utf-8"))["product"]
        # Fetch HTML cho title/meta hiện tại
        req2 = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req2, timeout=15) as r:
            html_s = r.read().decode("utf-8", errors="replace")
        t = re.search(r"<title>([^<]+)</title>", html_s, re.I)
        m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html_s, re.I)
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p.get("body_html", "")))
        return {
            "url": url,
            "name": p.get("title", ""),
            "vendor": p.get("vendor", ""),
            "type": p.get("product_type", ""),
            "price": (p.get("variants") or [{}])[0].get("price", ""),
            "current_title": h.unescape((t.group(1) if t else "").strip().replace("\n", " ").replace("        ", " ")),
            "current_meta": h.unescape((m.group(1) if m else "").strip()),
            "desc_300": body[:1500],
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


def call_gemini(user_msg, retry_hint=""):
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_msg + retry_hint}]}],
        "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"},
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return None, f"HTTP {e.code}: {body[:200]}"
    if "candidates" not in d:
        return None, f"no candidates: {json.dumps(d)[:200]}"
    txt = d["candidates"][0]["content"]["parts"][0]["text"]
    try:
        return json.loads(txt), None
    except Exception as e:
        return None, f"parse err: {e}"


def gen_for(p, max_retry=1):
    user = f"""Sản phẩm cần viết:
- Tên: {p.get('name')}
- Vendor/Hãng: {p.get('vendor')}
- Loại: {p.get('type')}
- Giá: {p.get('price')}đ
- Title hiện tại: {p.get('current_title','')[:120]}
- Meta hiện tại: {p.get('current_meta','')[:200]}
- Mô tả tóm tắt:
{p.get('desc_300','')[:1500]}

→ Viết 3 title + 3 meta đúng rules."""

    last_err = None
    last_gen = None
    for attempt in range(max_retry + 1):
        hint = ""
        if attempt > 0 and last_err:
            hint = f"\n\n⚠️ LẦN TRƯỚC SAI: {last_err}\nLần này TỰ ĐẾM ký tự. Title 45-58c. Meta 145-158c."
        gen, err = call_gemini(user, hint)
        if err:
            return None, err
        last_gen = gen
        bad = []
        for i, t in enumerate(gen.get("titles", [])[:3]):
            if len(t) > 61: bad.append(f"T{i+1}={len(t)}c")
        for i, m in enumerate(gen.get("metas", [])[:3]):
            if len(m) < 140: bad.append(f"M{i+1}={len(m)}c<140")
            elif len(m) > 160: bad.append(f"M{i+1}={len(m)}c>160")
        if not bad:
            return gen, None
        last_err = ",".join(bad)
        if attempt < max_retry:
            time.sleep(0.5)
    return last_gen, f"PARTIAL:{last_err}"


def build_row(p, gen):
    titles = (gen.get("titles", []) + ["", "", ""])[:3]
    metas = (gen.get("metas", []) + ["", "", ""])[:3]
    return [
        p["url"], p.get("name", ""), p.get("current_title", ""), p.get("current_meta", "")[:300],
        titles[0], titles[1], titles[2],
        metas[0], metas[1], metas[2],
    ]


def push_rows(svc, rows, start_row):
    body = {"values": rows}
    svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!E{start_row}",
        valueInputOption="RAW", body=body,
    ).execute()


def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"urls": [], "next_row": START_ROW, "violations": []}


def save_processed(state):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_all_urls():
    urls_seen = []
    seen_set = set()
    with open(TSV_FILE, encoding="utf-8") as f:
        rd = csv.reader(f, delimiter="\t")
        next(rd)
        for row in rd:
            for u in row[3].split(" | "):
                u = u.strip()
                if u and u not in seen_set:
                    seen_set.add(u)
                    urls_seen.append(u)
    return urls_seen


def main():
    creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
    svc = build("sheets", "v4", credentials=creds)

    state = load_processed()
    done_set = DONE_URLS | set(state["urls"])
    all_urls = load_all_urls()
    todo = [u for u in all_urls if u not in done_set]
    log(f"START: {len(todo)} URL còn lại / {len(all_urls)} tổng. Resume từ row {state['next_row']}")

    BATCH = 10
    pending_rows = []
    for idx, url in enumerate(todo, start=1):
        p = fetch_product(url)
        if "error" in p:
            log(f"  [{idx}/{len(todo)}] ❌ FETCH FAIL {url}: {p['error'][:80]}")
            continue
        gen, err = gen_for(p)
        if not gen:
            log(f"  [{idx}/{len(todo)}] ❌ GEMINI FAIL {url}: {err[:80]}")
            continue
        row = build_row(p, gen)
        pending_rows.append(row)
        if err and err.startswith("PARTIAL"):
            state["violations"].append({"url": url, "issue": err, "row": state["next_row"] + len(pending_rows) - 1})
            log(f"  [{idx}/{len(todo)}] ⚠ {p['name'][:50]} | {err}")
        else:
            log(f"  [{idx}/{len(todo)}] ✓ {p['name'][:50]}")

        # Push mỗi 10 URL
        if len(pending_rows) >= BATCH:
            try:
                push_rows(svc, pending_rows, state["next_row"])
                state["urls"].extend([r[0] for r in pending_rows])
                state["next_row"] += len(pending_rows)
                save_processed(state)
                log(f"  >> Pushed {len(pending_rows)} rows. Total done: {len(state['urls'])}/{len(all_urls)-len(DONE_URLS)}. Violations: {len(state['violations'])}")
                pending_rows = []
            except Exception as e:
                log(f"  !! PUSH ERR: {e}")
        time.sleep(2.2)  # ~27 RPM (giới hạn 30)

    # Push remainder
    if pending_rows:
        try:
            push_rows(svc, pending_rows, state["next_row"])
            state["urls"].extend([r[0] for r in pending_rows])
            state["next_row"] += len(pending_rows)
            save_processed(state)
            log(f"  >> Final push {len(pending_rows)} rows.")
        except Exception as e:
            log(f"  !! FINAL PUSH ERR: {e}")

    log(f"DONE! Total: {len(state['urls'])} URL processed. Violations: {len(state['violations'])}")
    with open(VIOLATION_FILE, "w", encoding="utf-8") as f:
        json.dump(state["violations"], f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
