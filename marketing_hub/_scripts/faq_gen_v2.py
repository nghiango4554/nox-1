"""FAQ v2 — viet lai theo tieu chuan moi (sau khi biet Google GO FAQ rich result 7/5/2026).

KHAC v1 (nhung thu v1 lam SAI):
- v1 ep 4-6 cau -> 172/189 bai ra dung 6 cau = dau vet san xuat hang loat. v2: 3-6 cau,
  chi viet cau THAT SU co nhu cau; thieu thi tra it hon, KHONG che cho du so.
- v1 khong dua key GSC vao prompt -> cau hoi bam noi dung bai, khong bam truy van that.
  v2: bom KEY CHINH + top query GSC that cua chinh bai do; BAT BUOC 1 cau phu key chinh.
- v1 de AI viet "Nội dung cho biết...", "Bài cũng nêu..." (93 cau) -> nghe nhu tom tat tai lieu.
  v2: CAM tuyet doi; cau tra loi phai tu dung doc lap (AI Overview trich 1 doan, khong co ngu canh).
- v2: viec nguy hiem (flash BIOS, sua Registry, keo kim loai long, thao lap) phai kem dieu kien + rui ro.
- v2: bai tin cu (nhom B) phai GAN MOC THOI GIAN, khong noi tin don nhu su that hien tai.

Chay:  py -3.12 _scripts/faq_gen_v2.py --group A --dual
       py -3.12 _scripts/faq_gen_v2.py --rework          # ra soat lai 10 bai da day
"""
import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import ai_provider
import faq_schema
from faq_gen import _plain, gather_hints, render_block

PRIO = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_preview\faq_priority.json")
OUT_DIR = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_preview")
PROVIDERS = ["codex", "claude"]
TODAY = "tháng 7/2026"

SYSTEM = f"""Bạn viết mục "Câu hỏi thường gặp" cho bài blog của Sintech — cửa hàng linh kiện máy tính TP.HCM.
Hôm nay là {TODAY}.

MỤC ĐÍCH: trả lời đúng thứ người dùng ĐANG GÕ GOOGLE về chủ đề này. Không phải tóm tắt lại bài.

SỐ CÂU: 3-6 câu, tuỳ nhu cầu THẬT.
- Chỉ viết câu có người thật sự thắc mắc. Không đủ ý thì viết ÍT hơn — thà 3 câu tốt còn hơn 6 câu chèn cho đủ.
- Nếu chủ đề không có nhu cầu hỏi đáp, trả về mảng rỗng [].

BÁM TRUY VẤN THẬT:
- Nên có 1 câu phủ KEY CHÍNH được đưa — nhưng diễn đạt thành câu hỏi TỰ NHIÊN, không chép nguyên cụm.
- ⚠️ Key GSC có thể là cụm SAI/GÕ NHẦM (ví dụ "google vs corsair" khi bài nói về G.Skill vs Corsair).
  Nếu key vô nghĩa hoặc lệch chủ đề bài: HIỂU Ý ĐỊNH ĐẰNG SAU rồi viết câu hỏi ĐÚNG, TUYỆT ĐỐI KHÔNG
  lặp lại cụm sai trong câu hỏi, không hỏi kiểu "X có phải là Y không?".
- Nên có thêm câu phủ biến thể trong danh sách truy vấn, câu về trở ngại/lỗi hay gặp, câu giúp ra quyết định.

CÂU TRẢ LỜI — phải TỰ ĐỨNG ĐỘC LẬP:
- Người đọc (và AI) có thể chỉ thấy MỖI câu trả lời này, không thấy bài. Nên phải có chủ thể rõ, đủ ngữ cảnh.
- CẤM TUYỆT ĐỐI các lối viết: "nội dung cho biết", "bài viết nêu", "theo bài", "được nhắc", "nội dung cũng ghi".
- Nêu điều kiện/giới hạn khi cần: tuỳ BIOS, tuỳ phiên bản, tuỳ mainboard, tuỳ khu vực...
- Việc có RỦI RO (flash BIOS, sửa Registry, keo tản nhiệt kim loại lỏng, tháo lắp linh kiện, chẩn đoán nguồn):
  phải nêu điều kiện thực hiện + rủi ro + khi nào nên dừng và mang tới kỹ thuật viên.
- 2-4 câu, trả lời thẳng ngay câu đầu.

KHÔNG BỊA: chỉ dùng thông tin có trong bài. Không chắc thì bỏ câu đó. Không bịa thông số/giá/model.

TỰ QUẢNG CÁO: tối đa 1 câu dạng "Sintech có..." trong cả khối. Ưu tiên câu người ta thật sự cần
(chi phí, thời gian xử lý, có báo giá trước không, khu vực phục vụ, bảo hành dịch vụ).

XƯNG HÔ: "bạn". Không nhắc giá tiền cụ thể. Không dùng từ: research, SERP, đối thủ, tại đây.

Trả về DUY NHẤT JSON array, không bọc markdown:
[{{"q": "câu hỏi?", "a": "câu trả lời."}}]"""

STALE = """
⚠️ BÀI NÀY LÀ TIN RA MẮT/RÒ RỈ ĐÃ CŨ (đăng {pub}, nay là {today}).
- CẤM viết tin đồn/dự đoán như thể đang là sự thật hiện tại.
- Mọi mốc thời gian, tin rò rỉ, giá dự kiến phải GẮN MỐC rõ: "theo thông tin công bố thời điểm {pub}...".
- Ưu tiên câu hỏi có giá trị lâu dài (sản phẩm này hợp với ai, khác gì đời trước, cần lưu ý gì khi chọn),
  tránh câu kiểu "khi nào ra mắt", "giá bao nhiêu" vì đã hết hạn.
- Gắn mốc bằng "theo thông tin công bố thời điểm {pub}" — KHÔNG được viết "theo bài", "trong bài",
  "bài viết nêu". Người đọc chỉ thấy câu trả lời, không thấy bài.
"""


def gen_v2(r: dict, hints: list, provider: str = None) -> list:
    keys = r.get("top_keys") or []
    kw_txt = "\n".join(f"- {k['kw']} ({k['imp']} lượt hiển thị, hạng {k['pos']})" for k in keys[:8]) or "(chưa có)"
    hint_txt = "\n".join(f"- {h}" for h in hints[:10]) or "(không có)"
    stale = STALE.format(pub=r.get("published") or "trước đây", today=TODAY) if r["group"] == "B_TIN_CU" else ""

    msg = f"""BÀI BLOG: {r['title']}
Ngày đăng: {r.get('published') or '?'}
{stale}
KEY CHÍNH trên Google Search Console (nên có 1 câu phủ ý định này — nhưng nếu key gõ sai/lệch chủ đề thì diễn giải lại cho đúng, KHÔNG lặp cụm sai): {r.get('key_chinh') or '(chưa có)'}

TRUY VẤN THẬT bài này đang có hiển thị:
{kw_txt}

GỢI Ý GOOGLE AUTOCOMPLETE (tham khảo, bỏ cụm không liên quan):
{hint_txt}

NỘI DUNG BÀI (chỉ được dựa vào đây để trả lời):
{_plain(r['body'])}

Viết mục Câu hỏi thường gặp. JSON array thuần."""

    raw = (ai_provider.call_ai_single(provider, SYSTEM, msg, timeout=240) if provider
           else ai_provider.call_ai(SYSTEM, msg, timeout=240))
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        raise ValueError(f"AI khong tra JSON: {raw[:100]}")
    out = []
    for it in json.loads(m.group(0)):
        q, a = (it.get("q") or "").strip(), (it.get("a") or "").strip()
        if q and len(a) >= faq_schema.MIN_ANSWER_LEN:
            out.append({"q": q, "a": a})
    return out


# Bat MOI cach nhac toi bai viet (v2 dot 1 van lot "Theo thông tin trong bài", "Bài viết chỉ nêu")
BAD = re.compile(r"(trong|theo|ở)\s+(bài|nội dung)|bài\s+(viết\s+)?(này\s+)?(chỉ\s+)?(nêu|cho biết|ghi|đề cập|không)"
                 r"|nội dung\s+(bài|cho biết|cũng|nêu|ghi)|được nhắc|theo nội dung", re.I)


def qc(faqs: list, r: dict, seen: set) -> tuple:
    """Loc chat luong: bo cau viet kieu tom tat tai lieu, cau trung bai khac."""
    kept, drop = [], []
    for f in faqs:
        key = f["q"].strip().lower()
        if BAD.search(f["a"]):
            drop.append(("lối viết tóm tắt tài liệu", f["q"]))
        elif key in seen:
            drop.append(("trùng câu hỏi bài khác", f["q"]))
        else:
            seen.add(key)
            kept.append(f)
    return kept, drop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="A", help="A | B | AB")
    ap.add_argument("--rework", action="store_true", help="Chi lam bai DA DAY (ra soat lai)")
    ap.add_argument("--dual", action="store_true")
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--handles", type=str, default=None,
                    help="File txt: moi dong 1 handle. CHI lam cac bai nay (an toan cho rework: "
                         "khong dung vao 55 bai FAQ von co san cua team).")
    a = ap.parse_args()

    rows = json.loads(PRIO.read_text(encoding="utf-8"))
    want = {"A": ["A_EVERGREEN"], "B": ["B_TIN_CU"], "AB": ["A_EVERGREEN", "B_TIN_CU"]}[a.group.upper()]
    sel = [r for r in rows if r["group"] in want]
    sel = [r for r in sel if (r["da_day"] if a.rework else not r["da_day"])]
    if a.handles:
        want_h = {l.strip() for l in Path(a.handles).read_text(encoding="utf-8").splitlines() if l.strip()}
        sel = [r for r in sel if r["handle"] in want_h]
    if a.n:
        sel = sel[:a.n]
    print(f"=== FAQ v2 · {'RÀ SOÁT LẠI bài đã đẩy' if a.rework else 'bài chưa có FAQ'} · nhóm {a.group}: {len(sel)} bài ===\n", flush=True)

    # Chong trung cheo bai: gom cau hoi DANG SONG tren web.
    # ⚠️ Tru chinh cac bai dang lam lai (rework) — khong thi cau moi trung y cau cu cua CHINH NO
    # se bi loai oan, bai ra 0 cau.
    target_ids = {r["id"] for r in sel}
    seen = set()
    for r in rows:
        if r["da_day"] and r["id"] not in target_ids:
            for f in faq_schema.extract_faq(r["body"]):
                seen.add(f["q"].strip().lower())

    lock = threading.Lock()
    res, drops = [], []

    def work(job):
        i, r = job
        prov = PROVIDERS[i % len(PROVIDERS)] if a.dual else None
        try:
            hints = gather_hints(r["title"])
            faqs = gen_v2(r, hints, provider=prov)
        except Exception as e:
            print(f"  LOI {type(e).__name__}: {str(e)[:60]} — {r['handle'][:40]}", flush=True)
            return
        with lock:
            kept, drop = qc(faqs, r, seen)
            drops.extend((r["handle"], why, q) for why, q in drop)
            if len(kept) < faq_schema.MIN_QUESTIONS:
                print(f"  BỎ (còn {len(kept)} câu sau QC) — {r['title'][:44]}", flush=True)
                return
            res.append({**{k: r[k] for k in ("group", "blog_id", "id", "handle", "title", "url",
                                             "imp", "key_chinh", "published")},
                        "faqs": kept, "block_html": render_block(r["title"], kept)})
            n = len(res)
        print(f"  [{n}/{len(sel)}] {len(kept)} câu · {r['imp']:>5} imp — {r['title'][:44]}", flush=True)

    if a.dual:
        with ThreadPoolExecutor(max_workers=len(PROVIDERS)) as ex:
            list(ex.map(work, enumerate(sel)))
    else:
        for job in enumerate(sel):
            work(job)

    tag = "rework" if a.rework else f"group{a.group}"
    f = OUT_DIR / f"faq_v2_{tag}_{datetime.now():%Y%m%d-%H%M%S}.json"
    f.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    n_q = sum(len(r["faqs"]) for r in res)
    dist = {}
    for r in res:
        dist[len(r["faqs"])] = dist.get(len(r["faqs"]), 0) + 1
    print(f"\n[XONG] {len(res)}/{len(sel)} bài · {n_q} câu (TB {n_q/max(1,len(res)):.1f}/bài)")
    print(f"  Phân bố số câu: {dict(sorted(dist.items()))}  <- v1 là 91% bài đúng 6 câu")
    print(f"  QC loại: {len(drops)} câu")
    for h, why, q in drops[:8]:
        print(f"     [{why}] {q[:56]} — {h[:30]}")
    print(f"  File: {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
