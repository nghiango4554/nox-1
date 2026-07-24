"""Research spec THẲNG TỪ TRANG HÃNG — thay vì hỏi Google bằng tên tiếng Việt.

Vì sao cần (đo 23/7): engine cũ hỏi `"<tên SP tiếng Việt> thông số kỹ thuật"` nên
top kết quả luôn là shop bán lẻ VN. Trang hãng viết tiếng Anh, tên khác hẳn
("M.2 NGFF SSD Enclosure" chứ không phải "Box đọc ổ cứng") nên không bao giờ lọt.
Kết quả: chỉ 18/1955 SP lấy được từ trang hãng, và shop thì sai thật (ORICO
M2PF-C3: shop ghi 108x29x11.5mm + "hợp kim nhôm", hãng ghi 108x29.5x13.5mm +
"nhôm + nhựa ABS").

Cách làm: với mỗi SP, tra `site:<tên miền hãng> <mã model>` rồi bóc spec từ đúng
trang hãng. Mọi cổng lọc của spec_research đều được áp lại.

    python brand_research.py --status
    python brand_research.py --brand JONSBO --max 40
    python brand_research.py --all --max 2000     # chạy tới khi hết SP hoặc hết quota
"""

import io
import json
import re
import sys
import time
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace",
                              line_buffering=True)

import requests
import urllib3

import db
import serper_search as ss
import spec_research as sr

urllib3.disable_warnings()
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

BRAND_DOMAIN = {
    "MSI": "msi.com", "ASUS": "asus.com", "GIGABYTE": "gigabyte.com",
    "ASROCK": "asrock.com", "COLORFUL": "colorful.cn", "INTEL": "intel.com",
    "AULA": "aulastar.com", "JONSBO": "jonsbo.com", "DARKFLASH": "darkflash.com",
    "THERMALTAKE": "thermaltake.com", "MONTECH": "montechpc.com",
    "SEGOTEP": "segotep.com", "GAMDIAS": "gamdias.com", "XIGMATEK": "xigmatek.com",
    "1ST PLAYER": "1stplayer.com", "SUPERFLOWER": "super-flower.com.tw",
    "MACHENIKE": "machenike.com", "EDIFIER": "edifier.com", "XIBERIA": "xiberia.com.vn",
    "VEGGIEG": "veggieg.com", "APACER": "apacer.com", "CENTAUR": "centaur.vn",
    "EDRA": "e-dra.vn", "E-DRA": "e-dra.vn", "VSP": "vsptech.vn",
    "ORICO": "orico.cc", "TP-LINK": "tp-link.com", "TPLINK": "tp-link.com",
    "MERCUSYS": "mercusys.com", "LEXAR": "lexar.com", "KINGSTON": "kingston.com",
    "PATRIOT": "patriotmemory.com", "SILICON POWER": "silicon-power.com",
    "LOGITECH": "logitech.com", "RAZER": "razer.com", "CORSAIR": "corsair.com",
    "SEAGATE": "seagate.com", "SAMSUNG": "samsung.com",
    "WESTERN DIGITAL": "westerndigital.com", "ZOTAC": "zotac.com",
    "PALIT": "palit.com", "INNO3D": "inno3d.com", "SPARKLE": "sparkle.com.tw",
    "OCYPUS": "ocypus.com", "DEEPCOOL": "deepcool.com",
    "COOLER MASTER": "coolermaster.com", "ADATA": "adata.com",
    "TEAMGROUP": "teamgroupinc.com", "IMOU": "imou.com", "DAREU": "dareu.com",
    "LEOBOG": "leobog.net", "KTC": "ktcmonitor.com", "AOC": "aoc.com",
    "LG": "lg.com", "DELL": "dell.com", "HP": "hp.com", "LENOVO": "lenovo.com",
    "ACER": "acer.com", "BROTHER": "brother.com.vn",
    "THONET & VANDER": "thonet-vander.com", "THONET AND VANDER": "thonet-vander.com",
    "T-WOLF": "t-wolf.vn", "UGREEN": "ugreen.com", "NETAC": "netac.com",
    "BIWIN": "biwin.com.cn", "SSTC": "sstc.vn", "JETEK": "jetek.vn",
    "COOLERPLUS": "coolerplus.vn", "DARMOSHARK": "darmoshark.vn",
    "MAGIC": "magicpc.vn", "SSK": "ssk.cc", "TRYX": "tryx.com",
}


def brand_of(vendor: str, title: str):
    """(tên hãng, tên miền). Ưu tiên trường vendor, không có thì dò trong tên SP."""
    v = (vendor or "").strip().upper()
    if v in BRAND_DOMAIN:
        return v, BRAND_DOMAIN[v]
    t = (title or "").upper()
    for name, dom in BRAND_DOMAIN.items():
        if re.search(rf"(?<![A-Z0-9]){re.escape(name)}(?![A-Z0-9])", t):
            return name, dom
    return "", ""


def targets(brand: str = "", limit: int = 0) -> list:
    """SP trong phạm vi chưa có nguồn TRANG HÃNG."""
    conn = db.get_conn()
    rows = conn.execute("""SELECT p.haravan_id, p.title, p.product_type, p.vendor
        FROM product_spec_index p
        WHERE p.condition_kind='new' AND COALESCE(p.is_service,0)=0
          AND COALESCE(p.skipped,0)=0 AND COALESCE(p.published,1)=1
          AND p.haravan_id NOT IN (
              SELECT haravan_id FROM spec_research_source
              WHERE status='dung' AND COALESCE(reason,'') LIKE '%TRANG HÃNG%')
        ORDER BY p.vendor, p.title""").fetchall()
    conn.close()
    out = []
    for hid, title, ptype, vendor in rows:
        b, d = brand_of(vendor, title)
        if not d:
            continue
        if brand and b != brand.upper():
            continue
        out.append({"hid": hid, "title": title, "type": ptype or "",
                    "brand": b, "domain": d})
    return out[:limit] if limit else out


# ── 3 cổng chặn thêm sau lần chạy hỏng 23/7 ──────────────────────────────────
# 1) Bài viết / tin tức KHÔNG phải trang sản phẩm: 2 bo mạch ROG khác nhau cùng
#    trỏ về 1 URL /articles/ và nhận spec y hệt nhau.
BAD_URL = re.compile(r"(?i)/(articles?|news|blog|blogs|press|event|promotion|review"
                     r"|support|download|forum|community)(/|$|\?)")
# ⚠️ Bẫy 23/7: lấy trúng aoc.com/**it**/ và aoc.com/**hu**/ → spec ra tiếng Ý
# ("Rapporto di contrasto", "Formato"), vô dụng cho khách Việt. Chỉ nhận trang
# tiếng Anh / tiếng Việt / trang toàn cầu không gắn mã ngôn ngữ.
BAD_LANG = re.compile(r"(?i)^https?://[^/]+/(it|hu|de|fr|es|pt|pl|ru|tr|cz|sk|nl|ro"
                      r"|gr|el|se|dk|fi|no|jp|kr|th|id|ms|ar|he|uk|bg|hr|sr|si|lt|lv"
                      r"|ee|is|ca|br|mx|ar-es|tw|hk|cn|zh)(/|$)")
# 2) Trang hãng không có heading spec → code rơi xuống quét cả trang → vớ MENU.
MENU_LBL = re.compile(r"(?i)^(laptops?|handhelds?|displays?|desktops?|motherboards?"
                      r"|components?|networking|iot|servers?|phones?|tablets?|monitors?"
                      r"|accessor(y|ies)|wearables?|software|services?|support|store"
                      r"|for (home|work|business|gaming|creators?|students?)"
                      r"|mobile|healthcare|solutions?|products?|company|about)\b")


def _looks_like_menu(rows: list) -> bool:
    hit = sum(1 for k, _v in rows if MENU_LBL.match(str(k).strip()))
    return hit >= 3 or (rows and hit / len(rows) > 0.35)


def _model_in_url(model: str, url: str) -> bool:
    """Trang SP thật gần như luôn có mã model trong đường dẫn."""
    a = re.sub(r"[^a-z0-9]", "", (model or "").lower())
    b = re.sub(r"[^a-z0-9]", "", (url or "").lower())
    return bool(a) and len(a) >= 4 and a in b


# ⚠️ Cùng chip nhưng KHÁC DÒNG là 2 sản phẩm khác hẳn, giá chênh cả triệu.
# Ca thật 23/7: "ASUS Dual RTX 4060 EVO" vớ trang "ROG Strix RTX 4060" chỉ vì
# URL có "rtx4060". Nếu tên SP nêu rõ dòng thì URL phải có đúng dòng đó.
SERIES = ["rog strix", "rog", "strix", "tuf", "prime", "dual", "ventus", "gaming x",
          "windforce", "eagle", "aorus", "twin", "phoenix", "verto", "megalodon",
          "trinity", "amp", "vulcan", "icraft", "battle ax", "geforce rtx"]


def _series_ok(title: str, url: str) -> bool:
    t = " " + re.sub(r"[^a-z0-9 ]", " ", (title or "").lower()) + " "
    u = re.sub(r"[^a-z0-9]", "", (url or "").lower())
    found = [s for s in SERIES if f" {s} " in t and s != "geforce rtx"]
    if not found:
        return True                       # tên SP không nêu dòng → không ràng buộc
    # chỉ cần MỘT dòng nêu trong tên xuất hiện trong URL là được
    return any(re.sub(r"[^a-z0-9]", "", s) in u for s in found)


_SESS = requests.Session()          # tái dùng kết nối, đỡ bắt tay TLS mỗi lần


def _fetch(url: str) -> str:
    # timeout ngắn: trang hãng nước ngoài hay treo, 25s x 8 URL = 3 phút/SP → không xong nổi
    r = _SESS.get(url, headers=HEAD, timeout=(6, 10), verify=False)
    # trang hãng hay thiếu charset → requests đoán ISO-8859-1 → chữ hỏng
    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
        r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def research_one(it: dict) -> dict:
    """Tra 1 SP trên đúng trang hãng. Trả {ok, rows, url, reason}."""
    models = sr.model_tokens(it["title"])
    if not models:
        return {"ok": False, "reason": "tên SP không có mã model để tra"}
    dom = it["domain"]
    # chỉ 1 truy vấn: query thứ 2 gần như luôn trả shop VN, đã bị lọc hết ở dưới
    queries = [f'site:{dom} {models[0]}']
    seen = []
    for q in queries:
        try:
            hits = ss.search_google(q, num=8)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "reason": f"lỗi search: {str(e)[:60]}", "quota": True}
        for h in hits:
            u = h.get("link") or ""
            host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0].lower()
            if dom not in host:
                continue
            if u in seen or BAD_URL.search(u) or BAD_LANG.search(u):
                continue
            if not _model_in_url(models[0], u):
                continue                       # không có mã model trong URL → không phải trang SP
            if not _series_ok(it["title"], u):
                continue                       # cùng chip nhưng khác DÒNG → khác SP
            if len(seen) >= 3:                 # thử tối đa 3 trang/SP, đủ rồi
                break
            seen.append(u)
            try:
                rows = sr.clean_rows(sr.extract_spec_rows(_fetch(u)))
                rows, _drop = sr.drop_title_conflicts(it["title"], rows)
            except Exception:  # noqa: BLE001
                continue
            if len(rows) < 5 or _looks_like_menu(rows):
                continue
            lan = sr.wrong_kind(it["type"], it["title"], rows)
            if lan:
                continue
            # phải nhắc tới mã model, tránh vớ trang danh mục của hãng
            blob = sr.norm(" ".join(f"{a} {b}" for a, b in rows) + " " + u).replace(" ", "")
            if sr.norm(models[0]).replace(" ", "") not in blob:
                continue
            return {"ok": True, "rows": rows, "url": u, "model": models[0]}
        if seen:
            break
    return {"ok": False, "reason": "không thấy trang hãng có bảng thông số"}


def save(hid: int, url: str, rows: list, brand: str):
    conn = db.get_conn()
    conn.execute("""UPDATE spec_research_source SET status='bo_qua',
        reason=COALESCE(reason,'')||' | hạ cờ: đã có nguồn TRANG HÃNG'
        WHERE haravan_id=? AND status='dung'""", (hid,))
    conn.execute("""INSERT INTO spec_research_source
        (haravan_id,url,page_title,n_rows,rows_json,status,reason,created_at)
        VALUES (?,?,?,?,?,'dung',?,datetime('now','localtime'))""",
                 (hid, url, f"{brand} — trang hãng", len(rows),
                  json.dumps(rows, ensure_ascii=False),
                  "TRANG HÃNG (brand_research)"))
    conn.commit()
    conn.close()


def status():
    conn = db.get_conn()
    tot = conn.execute("""SELECT COUNT(*) FROM product_spec_index WHERE condition_kind='new'
        AND COALESCE(is_service,0)=0 AND COALESCE(skipped,0)=0
        AND COALESCE(published,1)=1""").fetchone()[0]
    hang = conn.execute("""SELECT COUNT(DISTINCT haravan_id) FROM spec_research_source
        WHERE status='dung' AND COALESCE(reason,'') LIKE '%TRANG HÃNG%'""").fetchone()[0]
    conn.close()
    t = targets()
    print(f"phạm vi {tot} SP · đã có nguồn TRANG HÃNG: {hang} · "
          f"còn tra được (có bản đồ hãng): {len(t)}")
    from collections import Counter
    for b, n in Counter(x["brand"] for x in t).most_common(18):
        print(f"   {n:>4}  {b}")
    return t


if __name__ == "__main__":
    if "--status" in sys.argv:
        status()
        sys.exit()
    brand = sys.argv[sys.argv.index("--brand") + 1] if "--brand" in sys.argv else ""
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 100
    items = targets(brand, mx)
    print(f"BẮT ĐẦU {datetime.now():%H:%M:%S} · {len(items)} SP"
          f"{' · hãng ' + brand if brand else ''}")
    ok = fail = 0
    t0 = time.time()
    # Hãng nào trượt liên tiếp N lần đầu → gần như chắc chắn không có trang SP riêng
    # (1ST PLAYER chỉ có trang danh mục). Bỏ qua để dồn thời gian cho hãng có trang.
    MISS_CAP = 8
    miss, skipped_brands = {}, set()
    for i, it in enumerate(items, 1):
        if it["brand"] in skipped_brands:
            continue
        res = research_one(it)
        if res.get("quota"):
            print(f"\n⛔ DỪNG: {res['reason']}")
            break
        if res["ok"]:
            save(it["hid"], res["url"], res["rows"], it["brand"])
            ok += 1
            miss[it["brand"]] = 0
            print(f"  ✅ [{i}/{len(items)}] {it['brand']:<12} {len(res['rows']):>2} dòng "
                  f"| {it['title'][:44]}")
            print(f"       {res['url'][:96]}")
        else:
            fail += 1
            miss[it["brand"]] = miss.get(it["brand"], 0) + 1
            if miss[it["brand"]] >= MISS_CAP:
                skipped_brands.add(it["brand"])
                print(f"  ⏭ BỎ HÃNG {it['brand']} — trượt {MISS_CAP} lần liên tiếp, "
                      f"hãng không có trang SP riêng")
            elif i % 10 == 0 or fail <= 5:
                print(f"  ·  [{i}/{len(items)}] {it['brand']:<12} {res['reason'][:44]} "
                      f"| {it['title'][:40]}")
        time.sleep(0.25)
    print(f"\nXONG sau {round((time.time()-t0)/60,1)} phút · lấy được {ok} · "
          f"không ra {fail}")
    status()
