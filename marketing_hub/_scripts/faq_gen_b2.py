"""FAQ nhom B (tin ra mat/ro ri) — ban B2, viet lai voi THONG SO CHINH THUC da tu kiem chung.

Sua 3 loi cua ban B1:
1. TIEU DE KHOI FAQ BI CAT CUT ("...RX 9050 'lộ diện' tình") — do cat may moc 7 tu dau title.
   -> AI tra ve truong "topic" ngan gon do NO tu dat.
2. LAP MOC THOI GIAN o MOI cau ("Theo thông tin công bố thời điểm 2025-03-28...") — may moc.
   -> 1 dong "Lưu ý" DUY NHAT truoc khoi FAQ, cac cau tra loi di thang vao van de.
3. TIN RO RI DA THANH SAN PHAM CHINH THUC ma FAQ van noi "dự kiến/nếu ra mắt".
   -> Bom OFFICIAL_FACTS (tra tu trang hang 13/7/2026) vao prompt, bat AI viet theo TRANG THAI HIEN TAI.

Cung cam claim benchmark/FPS/dien nang khong nguon; cam "nguon yeu lam HONG linh kien"
(thuc te: mat on dinh, tat may, khoi dong lai).

Chay:  py -3.12 _scripts/faq_gen_b2.py --dual
"""
import argparse
import html as htmllib
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
from faq_gen import H2, H3, P, _plain, gather_hints

PRIO = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_preview\faq_priority.json")
OUT_DIR = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_preview")
PROVIDERS = ["codex", "claude"]

# ── SU THAT CHINH THUC — anh tu tra trang hang/nguon uy tin ngay 13/7/2026 ──────────
# Bai tin cu hay noi tin don nhu su that => phai bom su that HIEN TAI vao prompt.
OFFICIAL_FACTS = {
    "amd-radeon-rx-9050-lo-dien-tinh-co-tren-trang-cua-hang-dien-tu-ban-l": """
TÍNH ĐẾN THÁNG 7/2026 (đã tra cứu):
- AMD VẪN CHƯA công bố chính thức RX 9050. Đây vẫn là TIN RÒ RỈ (rò rỉ mới nhất giữa tháng 5/2026).
- Thông số rò rỉ: Navi 44, 2048 Stream Processor, 8GB GDDR6, bus 128-bit, ~288 GB/s.
- Dòng RDNA4 đã ra chính thức gồm: RX 9070 XT, RX 9070, RX 9070 GRE, RX 9060 XT.
=> FAQ phải nói RÕ đây là tin đồn CHƯA được AMD xác nhận, và gợi ý card đang bán thật cho người cần mua ngay.""",

    "lo-dien-geforce-rtx-5060-5050-laptop-asus-xac-nhan-ca-hai-deu-dung": """
TÍNH ĐẾN THÁNG 7/2026 (đã tra cứu, NVIDIA đã ra mắt chính thức):
- RTX 5050 Laptop: 2.560 CUDA core, 8GB GDDR7, bus 128-bit.
- RTX 5060 Laptop: 3.328 CUDA core (nhiều hơn ~30%), 8GB GDDR7.
- CẢ HAI đều dùng GDDR7 (tranh cãi GDDR6 hồi 3/2025 đã ngã ngũ), TGP tối đa 115W (100W + 15W Dynamic Boost).
- Hiệu năng: RTX 5060 nhanh hơn RTX 5050 trung bình ~21-22% theo test của hãng laptop.
=> CẤM viết "nếu thực sự dùng GDDR7". Phải nhắc TGP: cùng GPU nhưng khác laptop thì hiệu năng khác nhau.""",

    "amd-radeon-rx-7700-non-xt-ra-mat-am-tham-voi-16gb-vram-gpu-rdna-3": """
THÔNG SỐ CHÍNH THỨC AMD (đã tra cứu 13/7/2026):
- 40 Compute Unit, 2.560 Stream Processor, 16GB GDDR6, bus 256-bit, 19.5 Gbps.
- Điện năng bo mạch (TBP): 263W.
- NGUỒN KHUYẾN NGHỊ CHÍNH THỨC: 700W trở lên (KHÔNG PHẢI 650W).
=> Nguồn thiếu công suất gây MẤT ỔN ĐỊNH, tắt máy, khởi động lại — KHÔNG được viết "làm hỏng linh kiện".
=> CẤM claim "chậm hơn XT 15-20%" (không có nguồn benchmark). Viết "thấp hơn, mức chênh tuỳ game".
=> CẤM kết luận "16GB nên tốt hơn RTX 4070 cho AI" — AI còn phụ thuộc hệ sinh thái phần mềm.""",

    "amd-chuan-bi-ra-mat-radeon-rx-9070-gre-voi-hieu-nang-manh-gia-canh-tr": """
⚠️ TIN NÀY ĐÃ CŨ — SẢN PHẨM ĐÃ RA MẮT THẬT (tra cứu 13/7/2026):
- RX 9070 GRE ĐÃ bán TOÀN CẦU (không còn giới hạn Trung Quốc), giá đề xuất 549 USD, từ 2/6.
- Thông số chính thức: Navi 48 rút gọn, 48 Compute Unit, 3.072 Stream Processor, 12GB GDDR6,
  bus 192-bit, băng thông ~432 GB/s, xung boost tới 2.79 GHz, điện năng bo mạch 220W.
- Vị trí: lấp khoảng giữa RX 9060 XT 16GB và RX 9070 (RX 9070 có 16GB, bus 256-bit).
=> CẤM viết "chuẩn bị ra mắt", "nếu xuất hiện", "chưa được AMD xác nhận". Viết như SẢN PHẨM ĐANG BÁN.""",

    "nvidia-tung-rtx-5060-ti-ngay-khi-het-lenh-cam-review-rtx-5060-ra-mat": """
NGÀY RA MẮT CHÍNH THỨC (tra cứu 13/7/2026, KHÁC mốc rò rỉ trong bài):
- RTX 5060 Ti: bán từ 16/4 — bản 8GB giá từ 379 USD, bản 16GB từ 429 USD.
- RTX 5060: bán từ 19/5, giá từ 299 USD.
=> CẤM dùng mốc "dự kiến 15-16/5" của tin rò rỉ. CẤM claim "hay hết hàng trong vài phút" (không nguồn).
=> CẤM hứa Sintech báo tình trạng hàng dòng này.""",

    "thong-so-intel-arc-b570-gpu-ro-ri-thong-tin-suc-manh-card-tam-trung-d": """
LƯU Ý (13/7/2026): Arc B570 KHÔNG còn là tin rò rỉ — đã là sản phẩm bán chính thức.
=> Viết theo thông số chính thức, tách rõ: thông số Intel công bố vs thông số riêng của bản card từng hãng
   (cổng xuất hình, kích thước, xung, đầu nguồn là của TỪNG MODEL, không đại diện mọi B570).
=> CẤM suy luận công suất card từ "1 đầu 8-pin + 75W khe PCIe" — đó là giới hạn cấp điện lý thuyết,
   không phải cách tư vấn nguồn.
=> Nên có câu về Resizable BAR (quan trọng thật với Intel Arc).""",
}

# Bai chi sua nhe, khong co su that moi can bom
LIGHT = {"corsair-ra-mat-ws3000-bo-nguon-3000w-atx-3-1-cho-may-tram-hieu-nang": """
Bài này ổn. Chỉ lưu ý: câu về điện Việt Nam KHÔNG được kết luận đơn giản "điện 220V nên dùng được".
Phải nói: WS3000 cần 220-240V, nhưng dùng thực tế còn phụ thuộc đường điện, ổ cắm, dây dẫn và TỔNG TẢI
hệ thống; workstation nhiều GPU nên để kỹ thuật viên điện kiểm tra đường cấp riêng trước khi vận hành."""}

TARGETS = list(OFFICIAL_FACTS) + list(LIGHT)

SYSTEM = """Bạn viết mục "Câu hỏi thường gặp" cho bài blog của Sintech — cửa hàng linh kiện máy tính TP.HCM.
Hôm nay là tháng 7/2026.

BÀI NÀY LÀ TIN CÔNG NGHỆ CŨ. Người đọc hôm nay cần biết TRẠNG THÁI HIỆN TẠI, không cần nghe lại tin đồn.

LUẬT CỨNG:
- Phần "SỰ THẬT ĐÃ KIỂM CHỨNG" bên dưới là ĐÚNG tại tháng 7/2026 và GHI ĐÈ mọi thông tin cũ trong bài.
  Bài nói "dự kiến/rò rỉ/chưa xác nhận" mà sự thật nói đã ra mắt → viết theo SỰ THẬT.
- Sản phẩm CHƯA chính thức: nói thẳng "chưa được hãng công bố chính thức tính đến tháng 7/2026",
  và gợi ý sản phẩm ĐANG BÁN cho người cần mua ngay.
- KHÔNG lặp mốc thời gian ở mọi câu. Đã có 1 dòng "Lưu ý" đặt trước khối FAQ rồi — câu trả lời đi thẳng vào vấn đề.
- CẤM claim không nguồn: con số benchmark/FPS/%, "nhanh hơn X 15-20%", "hay hết hàng trong vài phút".
  Không chắc thì nói định tính ("thấp hơn, mức chênh tuỳ game").
- Nguồn điện thiếu công suất → "mất ổn định, tắt máy, khởi động lại". CẤM viết "làm hỏng linh kiện".
- Tách rõ: thông số hãng công bố ≠ thông số bản card riêng của từng nhà sản xuất.
- Câu trả lời TỰ ĐỨNG ĐỘC LẬP: cấm "theo bài", "trong bài", "nội dung cho biết".
- Xưng "bạn". Không nhắc giá bán tại Việt Nam. 3-5 câu, mỗi câu trả lời 2-4 câu văn.

Trả về DUY NHẤT 1 JSON object, không bọc markdown:
{"topic": "<chủ đề NGẮN cho tiêu đề khối, ví dụ 'Radeon RX 7700 16GB'>",
 "note": "<1 dòng lưu ý về mốc thời gian/trạng thái sản phẩm>",
 "faqs": [{"q": "câu hỏi?", "a": "câu trả lời."}]}"""


def render(topic: str, note: str, faqs: list) -> str:
    NOTE = ('font-family: Arial, sans-serif; font-size: 11.5pt; font-style: italic; '
            'line-height: 1.6; margin: 10px 0px; padding: 10px 14px; color: rgb(90, 90, 90); '
            'background: rgb(248, 248, 248); border-left: 3px solid rgb(231, 76, 60);')
    parts = [f'<h2 style="{H2}">Câu hỏi thường gặp về {htmllib.escape(topic)}</h2>']
    if note:
        parts.append(f'<p style="{NOTE}">{htmllib.escape(note)}</p>')
    for f in faqs:
        parts.append(f'<h3 style="{H3}">{htmllib.escape(f["q"])}</h3>')
        parts.append(f'<p style="{P}">{htmllib.escape(f["a"])}</p>')
    return "\n".join(parts)


def gen(r, hints, provider=None):
    facts = OFFICIAL_FACTS.get(r["handle"]) or LIGHT.get(r["handle"]) or ""
    keys = r.get("top_keys") or []
    kw = "\n".join(f"- {k['kw']} ({k['imp']} hiển thị)" for k in keys[:6]) or "(chưa có)"
    msg = f"""BÀI BLOG: {r['title']}
Ngày đăng: {r.get('published') or '?'}

=== SỰ THẬT ĐÃ KIỂM CHỨNG (tháng 7/2026) — GHI ĐÈ nội dung cũ trong bài ===
{facts}

TRUY VẤN THẬT bài đang có hiển thị:
{kw}

GỢI Ý AUTOCOMPLETE: {', '.join(hints[:8]) or '(không)'}

NỘI DUNG BÀI CŨ (bối cảnh — KHÔNG được chép lại tin đồn đã lỗi thời):
{_plain(r['body'], 5000)}

Viết JSON object (topic + note + faqs)."""
    raw = (ai_provider.call_ai_single(provider, SYSTEM, msg, timeout=240) if provider
           else ai_provider.call_ai(SYSTEM, msg, timeout=240))
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"AI khong tra JSON: {raw[:100]}")
    d = json.loads(m.group(0))
    faqs = [{"q": f["q"].strip(), "a": f["a"].strip()} for f in d.get("faqs", [])
            if f.get("q") and len(f.get("a", "")) >= faq_schema.MIN_ANSWER_LEN]
    return d.get("topic", "").strip(), d.get("note", "").strip(), faqs


BAD = re.compile(r"(trong|theo)\s+(bài|nội dung)|nội dung\s+(cho biết|nêu)|làm hỏng linh kiện"
                 r"|hư hỏng linh kiện|nếu (thực sự|sản phẩm) ", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dual", action="store_true")
    a = ap.parse_args()

    rows = {r["handle"]: r for r in json.loads(PRIO.read_text(encoding="utf-8"))}
    sel = [rows[h] for h in TARGETS if h in rows]
    print(f"=== FAQ nhóm B (bản B2) — {len(sel)} bài, có bơm sự thật đã kiểm chứng ===\n", flush=True)

    lock, res = threading.Lock(), []

    def work(job):
        i, r = job
        prov = PROVIDERS[i % len(PROVIDERS)] if a.dual else None
        try:
            topic, note, faqs = gen(r, gather_hints(r["title"]), provider=prov)
        except Exception as e:
            print(f"  LỖI {type(e).__name__}: {str(e)[:60]} — {r['handle'][:36]}", flush=True)
            return
        bad = [f["q"] for f in faqs if BAD.search(f["a"])]
        faqs = [f for f in faqs if not BAD.search(f["a"])]
        if len(faqs) < faq_schema.MIN_QUESTIONS:
            print(f"  BỎ (còn {len(faqs)} câu sau QC) — {r['title'][:40]}", flush=True)
            return
        with lock:
            res.append({**{k: r[k] for k in ("blog_id", "id", "handle", "title", "url", "imp", "key_chinh")},
                        "topic": topic, "note": note, "faqs": faqs,
                        "block_html": render(topic, note, faqs)})
        print(f"  [{len(res)}/{len(sel)}] {len(faqs)} câu · {r['imp']:>4} imp · H2: “{topic}”"
              + (f" · QC loại {len(bad)}" if bad else ""), flush=True)

    if a.dual:
        with ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(work, enumerate(sel)))
    else:
        for j in enumerate(sel):
            work(j)

    f = OUT_DIR / f"faq_b2_{datetime.now():%Y%m%d-%H%M%S}.json"
    f.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[XONG] {len(res)}/{len(sel)} bài · {sum(len(r['faqs']) for r in res)} câu")
    print(f"  File: {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
