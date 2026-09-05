"""Gọi Gemini sinh 3 title + 3 meta cho từng product theo rules vợ.
Input: list product info (JSON từ Sintech)
Output: list rows ready để push lên sheet
"""
import os, sys, json, time, re
sys.stdout.reconfigure(encoding="utf-8")
import urllib.request

def _doc_khoa():
    """Đọc khoá Google từ biến môi trường hoặc `.secrets/google.env`.

    KHÔNG dán khoá thẳng vào file này. Bản trước ghi cứng khoá ở đây, khoá đó
    đã bị Google chặn ngày 16/8/2026 với lý do "reported as leaked" — mà cả 4
    script đều chép cùng một khoá nên chết đồng loạt, sửa phải sửa 12 chỗ.
    """
    k = os.environ.get("GOOGLE_API_KEY")
    if k:
        return k.strip()
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        for p in (os.path.join(d, ".secrets", "google.env"),
                  os.path.join(d, "nox-1", ".secrets", "google.env")):
            if os.path.isfile(p):
                # utf-8-sig: Notepad/PowerShell hay chèn BOM, utf-8 thường sẽ
                # đọc lẫn BOM vào tên khoá rồi so sánh trượt mà không báo gì
                for dong in open(p, encoding="utf-8-sig"):
                    if dong.startswith("GOOGLE_API_KEY="):
                        return dong.split("=", 1)[1].strip()
        d = os.path.dirname(d)
    raise SystemExit("Thiếu GOOGLE_API_KEY — đặt biến môi trường, "
                     "hoặc thêm dòng GOOGLE_API_KEY=... vào nox-1/.secrets/google.env")


API_KEY = _doc_khoa()
MODEL = "gemini-2.5-flash-lite"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

# Rules — copy nguyên từ JSON vợ gửi, cô đọng cho prompt
SYSTEM_PROMPT = """Bạn là chuyên gia SEO cho Sintech.vn (shop PC/laptop/gaming gear, nền tảng Haravan).
NHIỆM VỤ: Viết 3 title + 3 meta description khác nhau cho 1 trang sản phẩm.

⚠️ LIMIT KÝ TỰ — TUÂN THỦ TUYỆT ĐỐI:
- Mỗi TITLE: 45-58 ký tự (TỐI ĐA TUYỆT ĐỐI là 61, nhưng target 45-58 cho an toàn). NẾU VƯỢT 58 → REWRITE NGẮN HƠN trước khi trả về.
- Mỗi META: 145-158 ký tự (TỐI THIỂU 140, TỐI ĐA 160). NẾU NGẮN HƠN 145 hoặc DÀI HƠN 158 → REWRITE LẠI.
- TRƯỚC KHI TRẢ VỀ: tự đếm len(title) và len(meta), nếu vi phạm phải rewrite.

LUẬT TITLE:
- KHÔNG chứa từ "Sintech" (Haravan tự thêm " – Sintech" sau)
- BẮT BUỘC có: tên model/sản phẩm + spec mạnh nhất + ngữ cảnh dùng/mua
- Chuẩn hóa kỹ thuật: GDDR6 (không viết DDR6), giữ đúng độ phân giải/tỷ lệ thật
- WiFi chỉ ghi khi mã sản phẩm thực sự có WiFi
- TRÁNH: nhồi keyword, lặp từ, lan man, spec không chắc

LUẬT META DESCRIPTION:
- BẮT BUỘC có: keyword chính/tên SP + 1 lợi ích rõ + 1 ngữ cảnh dùng + CTA nhẹ
- CTA viết IN HOA cụm hành động: "XEM NGAY tại Sintech", "THAM KHẢO NGAY tại Sintech", "KHÁM PHÁ NGAY", "CHỌN NGAY mẫu phù hợp tại Sintech"
- Tone: mượt, buyer-facing, bán hàng nhẹ, KHÔNG sáo rỗng
- 3 meta dùng 3 CTA khác nhau

QUY TẮC NGHIÊM:
- Nếu spec không chắc → viết an toàn theo tên + nhu cầu, KHÔNG bịa
- 3 title phải KHÁC nhau rõ rệt (theo spec / theo nhu cầu / theo brand)

OUTPUT BẮT BUỘC: chỉ JSON, không text gì khác.
{
  "titles": ["...", "...", "..."],
  "metas": ["...", "...", "..."]
}
"""


def _call_gemini(user_msg, retry_hint=""):
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_msg + retry_hint}]}],
        "generationConfig": {
            "temperature": 0.6,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} {e.read().decode('utf-8',errors='replace')[:200]}"
    if "candidates" not in d:
        return None, f"no candidates: {json.dumps(d)[:300]}"
    txt = d["candidates"][0]["content"]["parts"][0]["text"]
    try:
        return json.loads(txt), None
    except Exception as e:
        return None, f"parse err: {e} | text: {txt[:300]}"


def gen_for_product(p, max_retry=2):
    """Sinh + auto-retry nếu vi phạm length."""
    user = f"""Sản phẩm cần viết:
- Tên: {p.get('name')}
- Vendor/Hãng: {p.get('vendor')}
- Loại (Type): {p.get('type')}
- Giá: {p.get('price')}đ
- Title hiện tại: {p.get('current_title','')[:120]}
- Meta hiện tại: {p.get('current_meta','')[:200]}
- Mô tả tóm tắt (verify spec từ đây):
{p.get('desc_300','')[:1500]}

→ Viết 3 title + 3 meta theo đúng rules."""

    last_err = None
    for attempt in range(max_retry + 1):
        hint = ""
        if attempt > 0 and last_err:
            hint = f"\n\n⚠️ LẦN TRƯỚC SAI: {last_err}\nLần này TỰ ĐẾM ký tự trước khi trả về. Title 45-58c. Meta 145-158c."
        gen, err = _call_gemini(user, hint)
        if err:
            return None, err
        # Validate
        titles = gen.get("titles", [])
        metas = gen.get("metas", [])
        bad = []
        for i, t in enumerate(titles[:3]):
            if len(t) > 61:
                bad.append(f"Title {i+1} dài {len(t)}c (max 61)")
        for i, m in enumerate(metas[:3]):
            if len(m) < 140:
                bad.append(f"Meta {i+1} ngắn {len(m)}c (min 140)")
            elif len(m) > 160:
                bad.append(f"Meta {i+1} dài {len(m)}c (max 160)")
        if not bad:
            return gen, None
        last_err = "; ".join(bad)
        if attempt < max_retry:
            time.sleep(1)
    # Hết retry — trả về best-effort
    return gen, f"PARTIAL (sau {max_retry} retry): {last_err}"


def validate_and_format_row(p, gen):
    """Build row 10 cột [URL, name, current_title, current_meta, T1, T2, T3, M1, M2, M3]."""
    titles = gen.get("titles", []) + ["", "", ""]
    metas = gen.get("metas", []) + ["", "", ""]
    return [
        p["url"],
        p.get("name", ""),
        p.get("current_title", ""),
        p.get("current_meta", "")[:300],
        titles[0], titles[1], titles[2],
        metas[0], metas[1], metas[2],
    ], {
        "t_lens": [len(t) for t in titles[:3]],
        "m_lens": [len(m) for m in metas[:3]],
    }


if __name__ == "__main__":
    # Test 3 sản phẩm từ batch_01_data
    with open(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-1\seo_rewrite\batch_01_data.json", encoding="utf-8") as f:
        items = json.load(f)
    test_items = [items[0], items[3], items[4]]  # Delta L24 trắng, Sigma L36 PRO, Segotep MU-360

    for p in test_items:
        print(f"\n{'='*70}\n{p['name']}")
        gen, err = gen_for_product(p)
        if err:
            print(f"  ❌ {err}")
            continue
        row, lens = validate_and_format_row(p, gen)
        for i, t in enumerate(row[4:7], 1):
            flag = "✓" if len(t) <= 61 else "❌"
            print(f"  T{i} [{len(t):>2}c {flag}]: {t}")
        for i, m in enumerate(row[7:10], 1):
            flag = "✓" if 140 <= len(m) <= 160 else ("⚠ngắn" if len(m)<140 else "❌dài")
            print(f"  M{i} [{len(m):>3}c {flag}]: {m}")
