"""Fill 50 hàng đầu chưa có title+meta đề xuất trong tab '2. URL Rewrite'.
Dùng Gemini Flash Lite để sinh 3 title + 3 meta, validate length, push sheet."""
import os, sys, json, time, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

API_KEY = "AIzaSyAXk2hMOvGUi5h4ekXmT-gmCKG5COPN6_4"
MODEL = "gemini-2.5-flash-lite"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"
BATCH_SIZE = 50

SYSTEM_PROMPT = """Bạn là chuyên gia SEO cho Sintech.vn (shop PC/laptop/gaming gear, nền tảng Haravan).
NHIỆM VỤ: Viết 3 title + 3 meta description khác nhau cho 1 trang.

⚠️ LIMIT KÝ TỰ — TUÂN THỦ TUYỆT ĐỐI:
- Mỗi TITLE: 45-58 ký tự (tối đa tuyệt đối 61). VƯỢT 58 → REWRITE.
- Mỗi META: 145-158 ký tự (tối thiểu 140, tối đa 160). NGẮN HƠN 145 hoặc DÀI HƠN 158 → REWRITE.
- TRƯỚC KHI TRẢ VỀ: tự đếm len(title), len(meta), nếu vi phạm phải sửa.

LUẬT TITLE:
- KHÔNG chứa "Sintech" (Haravan tự thêm " – Sintech" sau)
- BẮT BUỘC: tên model/SP + spec mạnh nhất + ngữ cảnh dùng/mua
- Chuẩn hóa kỹ thuật: GDDR6 (không viết DDR6), độ phân giải đúng
- WiFi chỉ ghi khi mã SP thực sự có WiFi
- TRÁNH: nhồi keyword, lặp từ, lan man, spec không chắc

LUẬT META:
- BẮT BUỘC: keyword chính/tên SP + 1 lợi ích rõ + 1 ngữ cảnh dùng + CTA nhẹ
- CTA viết IN HOA: "XEM NGAY tại Sintech", "THAM KHẢO NGAY tại Sintech", "KHÁM PHÁ NGAY", "CHỌN NGAY mẫu phù hợp tại Sintech"
- Tone mượt, buyer-facing, KHÔNG sáo rỗng
- 3 meta dùng 3 CTA khác nhau

QUY TẮC:
- Spec không chắc → viết an toàn theo tên + nhu cầu, KHÔNG bịa
- 3 title KHÁC nhau rõ rệt (theo spec / theo nhu cầu / theo brand)
- Bài blog (URL có /blogs/) → focus theo chủ đề bài, không spec SP

OUTPUT BẮT BUỘC: chỉ JSON.
{"titles": ["...","...","..."], "metas": ["...","...","..."]}"""


def call_gemini(user_msg, hint=""):
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_msg + hint}]}],
        "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"},
    }
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(4):
        req = urllib.request.Request(
            ENDPOINT, data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Parse retry hint từ body nếu có
                wait = 22 + attempt * 10
                print(f"  [429 quota, sleep {wait}s]", end=" ", flush=True)
                time.sleep(wait)
                continue
            return None, f"HTTP {e.code}"
        except Exception as e:
            return None, f"err: {e}"
    else:
        return None, "429 quota exhausted"
    if "candidates" not in d:
        return None, f"no candidates"
    txt = d["candidates"][0]["content"]["parts"][0]["text"]
    try:
        return json.loads(txt), None
    except Exception as e:
        return None, f"parse: {e}"


def gen_for_row(url, name, cur_title, cur_meta):
    user = f"""URL: {url}
Tên hiện tại: {name}
Title hiện tại: {cur_title}
Meta hiện tại: {cur_meta}

Viết 3 title (45-58 ký tự) + 3 meta (145-158 ký tự) tốt hơn bản hiện tại."""
    for attempt in range(2):
        result, err = call_gemini(user, "" if attempt == 0 else "\n\nLẦN TRƯỚC VI PHẠM LENGTH. Đếm kỹ và sửa.")
        if not result or "titles" not in result or "metas" not in result:
            continue
        titles = result["titles"][:3]
        metas = result["metas"][:3]
        # Validate
        bad = []
        for i, t in enumerate(titles):
            if len(t) > 61: bad.append(f"T{i+1}={len(t)}")
        for i, m in enumerate(metas):
            if len(m) < 140 or len(m) > 160: bad.append(f"M{i+1}={len(m)}")
        if not bad or attempt == 1:
            return titles, metas, bad
    return None, None, ["call failed"]


def main():
    creds = Credentials.from_authorized_user_file(TOKEN)
    svc = build("sheets", "v4", credentials=creds)
    res = svc.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O").execute()
    rows = res.get("values", [])
    data = rows[1:]

    def cell(r, idx): return r[idx] if idx < len(r) else ""
    def empty(s): return not str(s).strip()

    todo = []
    for i, r in enumerate(data, start=2):
        title = cell(r, 5)
        meta = cell(r, 8)
        status = cell(r, 11)
        if not (empty(title) and empty(meta)): continue
        if status == "404 - bỏ qua": continue
        url = cell(r, 1)
        if not url.startswith("http"): continue
        name = cell(r, 2); cur_t = cell(r, 3); cur_m = cell(r, 4)
        todo.append((i, url, name, cur_t, cur_m))

    todo = todo[:BATCH_SIZE]
    print(f"Sẽ fill {len(todo)} hàng (batch {BATCH_SIZE} đầu).\n")

    sheet_updates = []
    ok = fail = 0
    for idx, (row, url, name, ct, cm) in enumerate(todo, 1):
        print(f"[{idx}/{len(todo)}] Row {row}: {url[35:][:60]}", end=" ", flush=True)
        titles, metas, bad = gen_for_row(url, name, ct, cm)
        if not titles:
            print(f"FAIL ({','.join(bad)})")
            fail += 1
            continue
        # Push F-L: F-H = titles, I-K = metas, L = "Đã sinh"
        values = [titles + metas + ["Đã sinh"]]
        sheet_updates.append({
            "range": f"'{TAB}'!F{row}:L{row}",
            "values": values,
        })
        flag = " ⚠"+",".join(bad) if bad else ""
        print(f"OK{flag}")
        ok += 1
        time.sleep(3.3)  # ≤20 RPM free tier
        # Flush mỗi 10 hàng
        if len(sheet_updates) >= 10:
            svc.spreadsheets().values().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={"valueInputOption": "USER_ENTERED", "data": sheet_updates},
            ).execute()
            print(f"  → flushed {len(sheet_updates)} rows lên sheet")
            sheet_updates = []

    if sheet_updates:
        svc.spreadsheets().values().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"valueInputOption": "USER_ENTERED", "data": sheet_updates},
        ).execute()
        print(f"  → flushed {len(sheet_updates)} rows cuối lên sheet")

    print(f"\n=== {ok} OK / {fail} FAIL / {len(todo)} total ===")


if __name__ == "__main__":
    main()
