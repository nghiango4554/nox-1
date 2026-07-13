"""FAQ schema cho bai blog — module dung chung (script bulk, hub push, nut bam).

BOI CANH (2 bay da dinh, dung go):
- Haravan STRIP <script> khoi body_html cua article -> khong nhet thang JSON-LD vao bai duoc.
  Giai phap: nhet JSON vao HTML COMMENT (comment thi Haravan giu), theme templates/article.liquid
  cat comment do ra va in <script type="application/ld+json">.
- Liquid Haravan BO phan tu rong khi split -> theme khong duoc dua vao forloop.first (xem article.liquid).

Theme chay 2 tang: (1) co comment FAQJSON -> dung comment (chinh xac);
(2) khong co -> theme tu doc khoi FAQ hien thi trong bai.
Module nay lo tang (1).

Luat Google: schema PHAI khop noi dung nhin thay -> chi boc tu khoi FAQ that trong body,
khong bao gio bia cau hoi.
"""
from __future__ import annotations

import html as htmllib
import json
import re

FAQ_H2 = re.compile(r"câu hỏi thường gặp|hỏi\s*[-–&]?\s*đáp|\bFAQ\b|giải đáp thắc mắc", re.I)
MARK_OPEN = "<!--FAQJSON:"
MARK_CLOSE = ":FAQJSON-->"
_COMMENT_RE = re.compile(re.escape(MARK_OPEN) + r".*?" + re.escape(MARK_CLOSE), re.S)
MIN_ANSWER_LEN = 40  # cau tra loi ngan hon = cut, bo qua
MIN_QUESTIONS = 2


def _text(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", htmllib.unescape(s)).strip()


def extract_faq(body_html: str) -> list[dict]:
    """Boc [{'q','a'}] tu khoi FAQ HIEN THI: H2 kieu 'Cau hoi thuong gap'/'FAQ',
    moi H3 duoi do = cau hoi, van ban ngay duoi = cau tra loi.

    Quet MOI section FAQ va cong don — KHONG dung o section dau tien.
    Ly do (13/7): bai co san 1 H2 'FAQ' viet sai khuon (cau hoi de trong <p><strong>
    thay vi H3) -> neu dung o do se khong bao gio thay khoi FAQ moi chen sau. Theme
    article.liquid cung quet het moi H2 -> Python phai khop hanh vi voi theme."""
    blocks = list(re.finditer(r"<(h2|h3)[^>]*>(.*?)</\1>", body_html or "", re.S | re.I))
    faqs, in_faq = [], False
    for i, m in enumerate(blocks):
        tag, txt = m.group(1).lower(), _text(m.group(2))
        if tag == "h2":
            in_faq = bool(FAQ_H2.search(txt))  # roi section nay -> tat, gap section FAQ khac -> bat lai
        elif in_faq and tag == "h3" and txt:
            end = blocks[i + 1].start() if i + 1 < len(blocks) else len(body_html)
            ans = _text(body_html[m.end():end])
            if len(ans) >= MIN_ANSWER_LEN:
                faqs.append({"q": txt, "a": ans})
    return faqs


def build_comment(faqs: list[dict]) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": f["q"],
             "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
            for f in faqs
        ],
    }
    payload = json.dumps(data, ensure_ascii=False).replace("--", "––")  # '--' pha vo HTML comment
    return f"\n{MARK_OPEN}{payload}{MARK_CLOSE}"


def strip_comment(body_html: str) -> str:
    return _COMMENT_RE.sub("", body_html or "").rstrip()


def attach(body_html: str) -> tuple[str, int]:
    """Gan/lam moi comment FAQ schema vao body. Tra ve (body_moi, so_cau_hoi).

    Idempotent: comment cu bi go roi dung lai tu noi dung hien tai -> sua bai roi
    day lai thi schema tu cap nhat theo, khong bao gio lech voi bai."""
    clean = strip_comment(body_html or "")
    faqs = extract_faq(clean)
    if len(faqs) < MIN_QUESTIONS:
        return clean, 0
    return clean + build_comment(faqs), len(faqs)
