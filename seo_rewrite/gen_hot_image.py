"""Gen ảnh người đàn ông tổng tài trẻ nóng bỏng bằng Gemini 2.5 Flash Image."""
import os, sys, json, base64, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

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
MODEL = "gemini-2.5-flash-image"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

OUT_DIR = r"C:\Users\NGHIANGO\.openclaw\workspace\.openclaw-cli-images"
os.makedirs(OUT_DIR, exist_ok=True)

PROMPT = """Cinematic ultra-realistic editorial portrait of a stunning Asian young CEO
in his late 20s, sharp chiseled jawline, jet-black messy bedroom hair,
deep smoldering hooded eyes with intense lustful gaze locking with viewer,
slightly parted full lips, faint sexy smirk,
crisp white dress shirt completely unbuttoned exposing toned muscular chest
and defined collarbone glistening with light sweat, sleeves rolled up showing veiny forearms,
loose black silk tie hanging loose around neck, expensive Patek Philippe gold watch,
sitting on edge of king bed in luxury penthouse master bedroom,
black satin bedsheets crumpled around him, dim moody warm amber lighting,
floor-to-ceiling windows behind showing neon city skyline at midnight,
rain droplets on glass, single whiskey glass on nightstand,
dangerous CEO bad-boy energy, dominant alpha aura, seductive and intimate atmosphere,
photorealistic 8K hyper-detailed skin texture, shot on Sony A7R V with 85mm f/1.2 lens,
shallow depth of field bokeh, dramatic chiaroscuro rim lighting,
GQ magazine cover quality, fashion editorial mood, romance novel cover aesthetic"""

print("Prompt length:", len(PROMPT))
print("Calling Gemini Image API...")

payload = {
    "contents": [{"parts": [{"text": PROMPT}]}],
    "generationConfig": {
        "responseModalities": ["IMAGE"],
    },
}
req = urllib.request.Request(
    ENDPOINT,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print(f"❌ HTTP {e.code}:")
    print(body[:1000])
    sys.exit(1)

if "candidates" not in d:
    print("❌ No candidates in response:")
    print(json.dumps(d, indent=2)[:1500])
    sys.exit(1)

# Parse inline data
saved = []
for cand in d.get("candidates", []):
    for part in cand.get("content", {}).get("parts", []):
        if "inlineData" in part:
            mime = part["inlineData"].get("mimeType", "image/png")
            ext = ".png" if "png" in mime else ".jpg"
            img_bytes = base64.b64decode(part["inlineData"]["data"])
            out = os.path.join(OUT_DIR, f"hot_ceo_{len(saved)+1}{ext}")
            with open(out, "wb") as f:
                f.write(img_bytes)
            saved.append(out)
            print(f"✅ Saved: {out} ({len(img_bytes)} bytes)")
        elif "text" in part:
            print(f"  text part: {part['text'][:200]}")

if not saved:
    print("\n⚠ Không có ảnh nào được trả về. Full response:")
    print(json.dumps(d, indent=2, ensure_ascii=False)[:2000])
else:
    print(f"\n📁 Total: {len(saved)} ảnh")
    for s in saved: print(f"  → {s}")
