"""Gen khoi FAQ cho bai blog CHUA co FAQ -> luu ra file de vo DUYET (khong tu day len).

Luong: chon bai theo impressions GSC -> lay cum nguoi that go (Google Autocomplete)
-> AI viet 4-6 cau hoi bam NOI DUNG BAI -> render HTML chuan BLOG -> luu preview.
Day len Haravan = buoc rieng: faq_push.py (sau khi vo duyet).

Luat cung:
- Cau tra loi chi duoc dua tren noi dung bai. KHONG bia spec/gia/so lieu moi.
- Chuan format BLOG: h2 17pt #e74c3c · h3 13pt · p Arial 12pt line-height 1.65 (KHONG phai chuan SP).
- Xung "ban", khong "anh". Khong nhac gia. Khong tu cam: research/SERP/doi thu/tai day.

Chay:  py -3.12 _scripts/faq_gen.py --n 10
"""
import argparse
import html as htmllib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import ai_provider
import faq_schema
import haravan_blog as hb
import kw_suggest

BLOG_IDS = {1000906526: "news", 1000960873: "huong-dan"}
OUT_DIR = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_preview")
GSC = Path(__file__).resolve().parent.parent / "data" / "gsc_cache.json"

H2 = ('font-size: 17pt; font-weight: 700; color: rgb(231, 76, 60); margin: 24px 0px 5px; '
      'line-height: 1.38; font-family: Arial, sans-serif;')
H3 = ('font-size: 13pt; font-weight: 700; color: rgb(0, 0, 0); margin: 18px 0px 4px; '
      'line-height: 1.4; font-family: Arial, sans-serif;')
P = ('font-family: Arial, sans-serif; font-size: 12pt; font-weight: 500; '
     'line-height: 1.65; margin: 10px 0px; color: rgb(0, 0, 0);')

SYSTEM = """Bạn viết mục "Câu hỏi thường gặp" (FAQ) cho bài blog của Sintech — cửa hàng linh kiện máy tính TP.HCM.

LUẬT CỨNG:
- Câu trả lời CHỈ được dựa trên nội dung bài được đưa. TUYỆT ĐỐI không bịa thông số, giá, số liệu, model không có trong bài. Không chắc thì không viết câu đó.
- Câu trả lời 2-3 câu, 40-320 ký tự, trả lời thẳng ngay câu đầu rồi mới giải thích.
- Xưng hô "bạn". KHÔNG nhắc giá tiền. KHÔNG dùng từ: research, SERP, đối thủ, tại đây.
- 4-6 câu hỏi, không trùng ý nhau, không lặp lại nguyên văn tiêu đề bài.

CÂU HỎI — viết như người thật hỏi, KHÔNG như máy nhồi từ khoá:
- Cụm gợi ý chỉ để BIẾT người ta quan tâm gì. Diễn đạt lại tự nhiên, TUYỆT ĐỐI KHÔNG chèn cụm nguyên văn vào mọi câu.
- CẤM lặp cùng một cụm mở đầu ở nhiều câu (ví dụ 6 câu đều mở bằng "Intel ra mắt..." là SAI).
- Viết HOA chữ cái đầu mỗi câu hỏi.
- CẤM nhắc tới bài viết: không dùng "trong bài này", "bài viết", "theo bài". Người gõ Google không biết bài của bạn tồn tại.
- Hỏi thứ người mua thật sự phân vân (hợp với ai, chọn cái nào, có cần không, khác nhau ra sao), không hỏi thứ chỉ để nhắc lại tiêu đề.

Trả về DUY NHẤT một JSON array, không bọc markdown:
[{"q": "câu hỏi?", "a": "câu trả lời."}]"""


def _plain(html_s: str, limit: int = 6000) -> str:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_s or "", flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", htmllib.unescape(t)).strip()[:limit]


STOP_TAIL = re.compile(r"\b(trên|cho|tại|của|và|với|năm|full|chi tiết|mới nhất)\b.*$", re.I)
SUFFIXES = ["", " có", " cách", " bao nhiêu", " là gì", " nên chọn"]


def _seeds_from_title(title: str) -> list:
    """Seed NGAN moi ra goi y. Seed 6 tu dau tieu de = Google tra 0 (da dinh 13/7)."""
    t = re.sub(r"[^\w\sÀ-ỹ]", " ", (title or "").split("?")[0].split(":")[0])
    t = re.sub(r"\s+", " ", t).strip().lower()
    t = STOP_TAIL.sub("", t).strip()
    w = t.split()
    seeds = []
    for k in (4, 3, 2):
        if len(w) >= k:
            s = " ".join(w[:k])
            if s not in seeds:
                seeds.append(s)
    return seeds or ([t] if t else [])


def gather_hints(title: str, cap: int = 15) -> list:
    """Cum nguoi that go: suggest(seed) + suggest(seed + hau to). Uu tien cum dang CAU HOI."""
    hints, seen = [], set()
    for seed in _seeds_from_title(title):
        for sfx in SUFFIXES:
            try:
                res = kw_suggest.suggest(seed + sfx)
            except Exception:
                res = []
            time.sleep(0.15)
            for r in res:
                r = r.strip()
                if r and r.lower() not in seen:
                    seen.add(r.lower())
                    hints.append(r)
            if len(hints) >= cap * 2:
                break
        if len(hints) >= cap * 2:
            break
    q = [h for h in hints if re.search(r"\b(có|là gì|bao nhiêu|nào|sao|cách|nên)\b", h, re.I)]
    rest = [h for h in hints if h not in q]
    return (q + rest)[:cap]


def gen_faq(title: str, body_text: str, hints: list, provider: str = None) -> list:
    """provider=None -> fallback chain (codex->claude->gemini).
    provider='codex'/'claude' -> GHIM CUNG 1 AI, khong fallback cheo (dung cho dual-AI:
    moi worker mot AI, het quota thi worker do dung, khong an quota cua worker kia)."""
    hint_txt = "\n".join(f"- {h}" for h in hints[:12]) or "(không có)"
    msg = f"""BÀI BLOG: {title}

NỘI DUNG BÀI (chỉ được dựa vào đây để trả lời):
{body_text}

CỤM NGƯỜI THẬT GÕ GOOGLE (bám vào để đặt câu hỏi, bỏ cụm không liên quan bài):
{hint_txt}

Viết 4-6 câu hỏi thường gặp + câu trả lời. JSON array thuần."""
    if provider:
        raw = ai_provider.call_ai_single(provider, SYSTEM, msg, timeout=240)
    else:
        raw = ai_provider.call_ai(SYSTEM, msg, timeout=240)
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        raise ValueError(f"AI khong tra JSON array: {raw[:120]}")
    items = json.loads(m.group(0))
    out = []
    for it in items:
        q, a = (it.get("q") or "").strip(), (it.get("a") or "").strip()
        if q and len(a) >= faq_schema.MIN_ANSWER_LEN:
            out.append({"q": q, "a": a})
    return out


def render_block(title: str, faqs: list) -> str:
    topic = re.split(r"[:\-–|]", title)[0].strip()
    parts = [f'<h2 style="{H2}">Câu hỏi thường gặp về {topic}</h2>']
    for f in faqs:
        parts.append(f'<h3 style="{H3}">{htmllib.escape(f["q"])}</h3>')
        parts.append(f'<p style="{P}">{htmllib.escape(f["a"])}</p>')
    return "\n".join(parts)


def pick_targets(n: int) -> list:
    imp = {}
    try:
        g = json.loads(GSC.read_text(encoding="utf-8"))
        for row in g["performance"]["pages"]:
            imp[row["url"].rstrip("/")] = row.get("imp", 0)
    except Exception as e:
        print(f"[WARN] khong doc duoc GSC cache: {e}")

    rows = []
    for bid, slug in BLOG_IDS.items():
        page = 1
        while True:
            arts = hb.list_articles(bid, limit=50, page=page)
            if not arts:
                break
            for a in arts:
                body = a.get("body_html") or ""
                if len(faq_schema.extract_faq(body)) >= faq_schema.MIN_QUESTIONS:
                    continue  # da co FAQ
                url = f"https://sintech.vn/blogs/{slug}/{a.get('handle')}"
                rows.append({"blog_id": bid, "id": a["id"], "handle": a.get("handle"),
                             "title": a.get("title"), "url": url,
                             "imp": imp.get(url, 0), "body": body})
            page += 1
    rows.sort(key=lambda r: -r["imp"])
    return rows[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    a = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = pick_targets(a.n)
    print(f"=== Gen FAQ cho {len(targets)} bai (uu tien impressions GSC) ===\n", flush=True)

    results = []
    for i, t in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {t['title'][:60]} — {t['imp']} imp", flush=True)
        try:
            sug = gather_hints(t["title"])
        except Exception:
            sug = []
        try:
            faqs = gen_faq(t["title"], _plain(t["body"]), sug)
        except Exception as e:
            print(f"      LOI: {type(e).__name__}: {str(e)[:90]}", flush=True)
            continue
        if len(faqs) < faq_schema.MIN_QUESTIONS:
            print("      BO: AI tra it hon 2 cau", flush=True)
            continue
        block = render_block(t["title"], faqs)
        results.append({**{k: t[k] for k in ("blog_id", "id", "handle", "title", "url", "imp")},
                        "faqs": faqs, "block_html": block})
        print(f"      OK {len(faqs)} cau | goi y GG: {len(sug)}", flush=True)
        for f in faqs:
            print(f"        - {f['q']}", flush=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    jf = OUT_DIR / f"faq_batch_{stamp}.json"
    jf.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    # preview HTML de vo doc nhu tren web
    pv = ['<meta charset="utf-8"><body style="max-width:820px;margin:24px auto;font-family:Arial">',
          f"<h1>Duyệt FAQ — {len(results)} bài</h1>"]
    for r in results:
        pv.append(f'<hr><p><b>{r["title"]}</b> — {r["imp"]} lượt hiển thị<br>'
                  f'<a href="{r["url"]}" target="_blank">{r["url"]}</a></p>')
        pv.append(r["block_html"])
    pv.append("</body>")
    hf = OUT_DIR / f"faq_batch_{stamp}.html"
    hf.write_text("\n".join(pv), encoding="utf-8")

    print(f"\n[XONG] {len(results)}/{len(targets)} bai")
    print(f"  JSON    : {jf}")
    print(f"  PREVIEW : {hf}")
    print("  -> Vo duyet xong thi day len bang: py -3.12 _scripts/faq_push.py <file json>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
