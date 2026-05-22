"""Crawl minhtuanmobile.com → rút PATTERN SEO title/meta (KHÔNG lưu/copy nội dung).
Chỉ lấy metadata cấu trúc (title/meta/H1/H2/wordcount/schema/CTA) + suy ra pattern.
Output: CSV + stats JSON. Lịch sự: sequential + delay.
"""
import csv, json, re, sys, time
import requests
from bs4 import BeautifulSoup
from collections import Counter

BASE = "https://minhtuanmobile.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
DELAY = 0.45

COLLECTIONS = [
    "/dien-thoai/", "/dien-thoai/iphone/", "/dien-thoai/samsung/",
    "/laptop/mac/", "/laptop/mac/macbook-air/", "/laptop/mac/macbook-pro/",
    "/hang-cu/iphone/",
]

# Benefit token (USP) nhận diện trong title/meta
BENEFIT = {
    "giá rẻ/tốt": r"giá rẻ|giá tốt|giá hời",
    "trả góp 0%": r"trả góp 0%|góp 0%|trả góp",
    "chính hãng": r"chính hãng",
    "bảo hành/1đổi1": r"bảo hành|bh 1 đổi 1|1 đổi 1|bh vip",
    "thu cũ/trợ giá": r"thu cũ|trợ giá|đổi mới",
    "ưu đãi/sốc/sale": r"ưu đãi|sốc|sale|giảm|deal|khuyến mãi",
    "miễn phí/giao nhanh": r"miễn phí|giao hàng|freeship|giao nhanh",
}
CTA_TOKENS = ["mua ngay", "xem ngay", "đặt ngay", "đặt hàng", "liên hệ",
              "khám phá", "tìm hiểu", "xem thêm", "thêm vào giỏ"]


def get(url):
    return requests.get(url, headers=UA, timeout=20, allow_redirects=True)


def sitemap_locs(url):
    try:
        r = get(url)
        return re.findall(r"<loc>(.*?)</loc>", r.text)
    except Exception:
        return []


def jsonld_types(soup):
    types = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "{}")
        except Exception:
            continue
        for it in (data if isinstance(data, list) else [data]):
            if isinstance(it, dict):
                if it.get("@type"):
                    types.append(str(it["@type"]))
                for node in (it.get("@graph") or []):
                    if isinstance(node, dict) and node.get("@type"):
                        types.append(str(node["@type"]))
    return sorted(set(types))


def detect_tokens(text):
    t = text.lower()
    return [name for name, pat in BENEFIT.items() if re.search(pat, t)]


def has_cta(text):
    t = text.lower()
    return any(c in t for c in CTA_TOKENS)


def title_signature(title):
    """Chuẩn hoá title → signature pattern (ẩn tên SP, giữ khung)."""
    seps = [s for s in ["|", "–", "-", ":", ","] if s in title]
    primary = "|" if "|" in title else ("–" if "–" in title else
              (":" if ":" in title else ("-" if "-" in title else
              ("," if "," in title else "none"))))
    toks = detect_tokens(title)
    sig = f"[NAME] {primary} " + " + ".join(sorted(toks)) if toks else f"[NAME] {primary} (no-USP)"
    return sig, primary, toks


def meta_signature(meta):
    toks = detect_tokens(meta)
    cta = has_cta(meta)
    # lead verb
    first = (meta.split()[0] if meta.split() else "").lower().strip(".,!")
    lead = first if first in ("mua", "sở", "sắm", "chọn", "với", "hệ", "chuyên", "cập") else "[other]"
    sig = ("LEAD=" + lead + " | USP=" + ("+".join(sorted(toks)) if toks else "none")
           + " | CTA=" + ("yes" if cta else "no"))
    return sig, toks, cta


NEWS_RULES = [
    ("hướng dẫn", r"cách |hướng dẫn|thủ thuật|mẹo |làm sao|làm thế nào|fix |sửa lỗi|kích hoạt|cài đặt|cài "),
    ("review/đánh giá", r"đánh giá|review|trên tay|trải nghiệm|test |sau \d+ (giờ|ngày|tuần)"),
    ("so sánh", r"so sánh| vs | hay |nên mua|khác nhau|chọn .* nào|đáng mua"),
    ("khuyến mãi", r"giảm|sale|khuyến mãi|deal|ưu đãi|giá|trợ giá|sốc|miễn phí|trả góp"),
    ("game/app", r"game|tải |download|liên quân|wukong|roblox|genshin|app |ứng dụng|chơi "),
    ("tin công nghệ", r"ios |android|ra mắt|phát hành|cập nhật|rò rỉ|lộ diện|apple|samsung|google|ai |gemini|chatgpt"),
]


def classify_news(title):
    t = title.lower()
    for label, pat in NEWS_RULES:
        if re.search(pat, t):
            return label
    return "tin công nghệ"


def note_for(ptype, title, meta, toks_t, toks_m, cta, words, schema):
    bits = []
    if ptype == "product":
        bits.append("USP nhồi ngay sau tên" if toks_t else "title thiếu USP")
    if ptype == "collection":
        bits.append("title kèm brand + USP" if toks_t else "title trơn")
    if ptype == "news":
        bits.append("title dạng " + classify_news(title))
    bits.append("meta có CTA" if cta else "meta KHÔNG CTA")
    if "Product" not in " ".join(schema) and ptype == "product":
        bits.append("thiếu Product schema")
    bits.append(f"~{words} từ")
    return "; ".join(bits)


def extract(url, ptype):
    r = get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    md = soup.find("meta", attrs={"name": "description"})
    meta = (md.get("content").strip() if md and md.get("content") else "")
    h1el = soup.find("h1")
    h1 = h1el.get_text(" ", strip=True) if h1el else ""
    h2s = [h.get_text(" ", strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)]
    schema = jsonld_types(soup)
    # word count nội dung (bỏ nav/script/style/header/footer)
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    words = len(soup.get_text(" ", strip=True).split())
    body_for_cta = (title + " " + meta + " " + " ".join(h2s)).lower()
    cta = has_cta(body_for_cta)
    t_sig, t_sep, t_toks = title_signature(title)
    m_sig, m_toks, m_cta = meta_signature(meta)
    return {
        "url": url, "page_type": ptype, "title": title, "title_len": len(title),
        "meta_desc": meta, "meta_len": len(meta), "h1": h1,
        "h2_list": " || ".join(h2s[:12]), "h2_count": len(h2s),
        "word_count": words, "schema_type": ",".join(schema) or "(none)",
        "cta_present": "yes" if (cta or m_cta) else "no",
        "title_pattern": t_sig, "meta_pattern": m_sig,
        "news_category": classify_news(title) if ptype == "news" else "",
        "note": note_for(ptype, title, meta, t_toks, m_toks, (cta or m_cta), words, schema),
        "_t_toks": t_toks, "_m_toks": m_toks, "_t_sep": t_sep, "_m_cta": m_cta,
    }


def pick_products(prod_urls, per_bucket=8):
    buckets = {
        "iphone": r"/iphone|iphone-", "samsung": r"samsung|galaxy",
        "macbook": r"macbook|/mac/", "ipad": r"ipad",
        "phu-kien": r"phu-kien|op-lung|sac|cap|tai-nghe|airpod|airtag|cuong-luc|bao-da",
    }
    chosen, seen = [], set()
    for key, pat in buckets.items():
        cnt = 0
        for u in prod_urls:
            if cnt >= per_bucket:
                break
            if re.search(pat, u, re.I) and u not in seen:
                chosen.append(u); seen.add(u); cnt += 1
    # top up nếu chưa đủ 30
    for u in prod_urls:
        if len(chosen) >= 35:
            break
        if u not in seen:
            chosen.append(u); seen.add(u)
    return chosen


def main(out_csv, out_stats):
    rows = []
    # 1) Collections (theo spec)
    print("[collections]")
    for path in COLLECTIONS:
        try:
            rows.append(extract(BASE + path, "collection"))
            print("  ok", path)
        except Exception as e:
            print("  ERR", path, e)
        time.sleep(DELAY)
    # 2) Products từ sitemap-product.xml
    print("[products] fetch sitemap")
    prod_urls = sitemap_locs(BASE + "/sitemap-product.xml")
    prod_urls = [u for u in prod_urls if "/tin-tuc/" not in u]
    picks = pick_products(prod_urls)
    print(f"  sitemap {len(prod_urls)} prod → chọn {len(picks)}")
    for u in picks:
        try:
            rows.append(extract(u, "product")); print("  ok", u[-50:])
        except Exception as e:
            print("  ERR", u, e)
        time.sleep(DELAY)
    # 3) News từ sitemap-news.xml (fallback sitemap-blog)
    print("[news] fetch sitemap")
    news_urls = sitemap_locs(BASE + "/sitemap-news.xml")
    if len(news_urls) < 50:
        news_urls += sitemap_locs(BASE + "/sitemap-blog.xml")
    news_urls = [u for u in news_urls if "/tin-tuc/" in u and u.rstrip("/") != BASE + "/tin-tuc"]
    news_urls = list(dict.fromkeys(news_urls))[:55]
    print(f"  news → {len(news_urls)}")
    for u in news_urls:
        try:
            rows.append(extract(u, "news"));
        except Exception as e:
            print("  ERR", u, e)
        time.sleep(DELAY)
    print(f"[done] {len(rows)} rows")

    # CSV
    cols = ["url", "page_type", "title", "title_len", "meta_desc", "meta_len",
            "h1", "h2_list", "h2_count", "word_count", "schema_type",
            "cta_present", "title_pattern", "meta_pattern", "news_category", "note"]
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Stats
    def stats_for(ptype):
        sub = [r for r in rows if r["page_type"] == ptype]
        if not sub:
            return {}
        return {
            "n": len(sub),
            "title_len_avg": round(sum(r["title_len"] for r in sub) / len(sub), 1),
            "title_len_min": min(r["title_len"] for r in sub),
            "title_len_max": max(r["title_len"] for r in sub),
            "meta_len_avg": round(sum(r["meta_len"] for r in sub) / len(sub), 1),
            "meta_len_min": min(r["meta_len"] for r in sub),
            "meta_len_max": max(r["meta_len"] for r in sub),
            "cta_yes": sum(1 for r in sub if r["cta_present"] == "yes"),
            "title_patterns": Counter(r["title_pattern"] for r in sub).most_common(10),
            "meta_patterns": Counter(r["meta_pattern"] for r in sub).most_common(10),
            "title_usp_freq": Counter(t for r in sub for t in r["_t_toks"]).most_common(),
            "meta_usp_freq": Counter(t for r in sub for t in r["_m_toks"]).most_common(),
            "schema_freq": Counter(r["schema_type"] for r in sub).most_common(),
        }

    stats = {
        "total": len(rows),
        "by_type": {pt: sum(1 for r in rows if r["page_type"] == pt)
                    for pt in ("collection", "product", "news")},
        "collection": stats_for("collection"),
        "product": stats_for("product"),
        "news": stats_for("news"),
        "title_patterns_all": Counter(r["title_pattern"] for r in rows).most_common(10),
        "meta_patterns_all": Counter(r["meta_pattern"] for r in rows).most_common(10),
        "news_categories": Counter(r["news_category"] for r in rows if r["page_type"] == "news").most_common(),
    }
    with open(out_stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print("WROTE", out_csv, "+", out_stats)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
