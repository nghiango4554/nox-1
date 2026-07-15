# -*- coding: utf-8 -*-
"""Reformat body_html SP về CHUẨN bài mẫu ThinkBook 16 G9 (vợ chốt 23/6/2026).

Style nhẹ: h2 18px / h3 16px (px-based), link đỏ #dc2626, ảnh max-width 500px,
p/ul/li để theme lo (KHÔNG inline Arial nặng). Bảng GIỮ nhưng style nhẹ (chỉ
viền ngang, không header xám đậm).

AN TOÀN (guard 2026-06-26):
- MẶC ĐỊNH = DRY-RUN (offline, đọc body từ DB local haravan_products, KHÔNG gọi Haravan).
- LIVE sync (PUT Haravan) CHỈ khi ĐỦ 2 điều kiện: `--apply` (hoặc `--sync`) VÀ
  `--confirm LIVE_HARAVAN`. Thiếu 1 trong 2 → từ chối, không PUT.

Dùng:
    py -3.12 reformat_product_desc.py 123 456            # DRY (offline DB), in tóm tắt
    py -3.12 reformat_product_desc.py 123 --out docs/x   # DRY + xuất preview HTML
    py -3.12 reformat_product_desc.py 123 --apply --confirm LIVE_HARAVAN   # LIVE PUT (gated)
Backup body cũ khi LIVE -> nox-outputs/_reformat_backup_<id>.html
"""
import sys
import argparse
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
BK = ROOT.parent.parent / "nox-outputs"

H2 = ("font-size: 18px; font-weight: 700; color: #dc2626; "
      "border-left: 4px solid #dc2626; padding-left: 10px; margin: 26px 0 12px; line-height: 1.35;")
H3 = "font-size: 16px; font-weight: 600; margin: 12px 0 6px; line-height: 1.4;"
BOX = ("background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; "
       "padding: 10px 16px 4px; margin: 12px 0;")
A_ = "color:#dc2626;"
IMG = "max-width: 500px; width: 100%; height: auto; display: block; margin: 0 auto;"
IMGP = "text-align: center; margin: 16px 0;"
TABLE = "border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 14px; line-height: 1.55; border: 1px solid #d1d5db;"
TH = "border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; font-weight: 600; background: #f9fafb;"
TD = "border: 1px solid #e5e7eb; padding: 8px 10px; vertical-align: top;"


def reformat(body: str) -> str:
    soup = BeautifulSoup(body or "", "html.parser")
    for h in soup.find_all("h2"):
        h["style"] = H2
    for h in soup.find_all("h3"):
        h["style"] = H3
    for a in soup.find_all("a"):
        a["style"] = A_
    for t in soup.find_all("table"):
        t["style"] = TABLE
    for th in soup.find_all("th"):
        th["style"] = TH
    for td in soup.find_all("td"):
        td["style"] = TD
    for img in soup.find_all("img"):
        img["style"] = IMG
    # hàng đầu mỗi bảng = header (nền + đậm) khi bảng toàn <td>
    for table in soup.find_all("table"):
        fr = table.find("tr")
        if fr and not fr.find("th"):
            for cell in fr.find_all("td"):
                cell["style"] = ("border: 1px solid #d1d5db; padding: 8px 10px; "
                                 "text-align: left; font-weight: 600; background: #f9fafb;")
    # p: bọc ảnh -> center; còn lại bỏ style (theme lo)
    for p in soup.find_all("p"):
        if p.find("img"):
            p["style"] = IMGP
        elif p.has_attr("style"):
            del p["style"]
    # bỏ inline style rác trên list/inline tag -> theme lo
    for tag in soup.find_all(["ul", "ol", "li", "strong", "em", "span"]):
        if tag.has_attr("style"):
            del tag["style"]
    # đóng khung <ul> tóm tắt đầu bài (ul đầu tiên) cho dễ nhìn như khuôn combo PC
    first_ul = soup.find("ul")
    if first_ul is not None and first_ul.parent.name != "div":
        wrapper = soup.new_tag("div")
        wrapper["style"] = BOX
        first_ul.wrap(wrapper)
    html = str(soup)
    # in đậm nhãn trước dấu ':' đầu mỗi <li> (vd "Chuẩn kết nối: ...")
    import re as _re
    html = _re.sub(r"<li>([^:<>]{1,28}):", r"<li><strong>\1:</strong>", html)
    return html


def _stats(body: str, new: str) -> dict:
    return {
        "old_len": len(body), "new_len": len(new),
        "h2": new.count("<h2"), "h3": new.count("<h3"),
        "table": new.count("<table"), "img": new.count("<img"),
        "style_attrs_old": body.count("style="), "style_attrs_new": new.count("style="),
    }


def _get_body_local(pid: int):
    """Đọc title + body_html từ DB local (haravan_products) — OFFLINE, KHÔNG gọi Haravan."""
    import db
    conn = db.get_conn()
    row = conn.execute(
        "SELECT title, body_html FROM haravan_products WHERE haravan_id=?", (pid,)
    ).fetchone()
    conn.close()
    if not row:
        return None, None
    return (row["title"] or ""), (row["body_html"] or "")


def dry_one(pid: int, out_dir: Path = None) -> dict:
    """DRY-RUN offline: lấy body từ DB local, reformat, (tùy chọn) xuất preview. KHÔNG Haravan."""
    title, body = _get_body_local(pid)
    if body is None:
        return {"id": pid, "synced": "DRY", "error": "không có trong DB local haravan_products"}
    new = reformat(body)
    info = {"id": pid, "title": title, **_stats(body, new), "synced": "DRY"}
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        prev = (
            f"<!doctype html><meta charset=utf-8><title>{title}</title>"
            f"<h1 style='font:14px system-ui'>DRY PREVIEW · {pid} · {title}</h1>"
            f"<p style='font:12px system-ui;color:#666'>old_len={info['old_len']} → new_len={info['new_len']} · "
            f"h2={info['h2']} h3={info['h3']} table={info['table']} img={info['img']}</p><hr>"
            f"<div style='max-width:760px;margin:auto'>{new}</div>"
        )
        (out_dir / f"{pid}.html").write_text(prev, encoding="utf-8")
        info["preview"] = str(out_dir / f"{pid}.html")
    return info


def apply_one_live(pid: int) -> dict:
    """LIVE: fetch Haravan + PUT body mới. CHỈ gọi khi đã qua guard 2 điều kiện."""
    import haravan_client as hc
    p = hc.get_product(pid)
    title = p.get("title", "")
    body = p.get("body_html") or ""
    BK.mkdir(parents=True, exist_ok=True)
    (BK / f"_reformat_backup_{pid}.html").write_text(body, encoding="utf-8")
    new = reformat(body)
    info = {"id": pid, "title": title, **_stats(body, new)}
    r = hc._request("PUT", f"/products/{pid}.json", payload={"product": {"id": pid, "body_html": new}})
    info["synced"] = "OK" if r.get("product", {}).get("id") == pid else f"ERR {r}"
    return info


def main():
    ap = argparse.ArgumentParser(description="Reformat body_html SP (DRY mặc định).")
    ap.add_argument("ids", nargs="*", type=int, help="Haravan product id")
    ap.add_argument("--apply", action="store_true", help="yêu cầu LIVE sync (cần kèm --confirm)")
    ap.add_argument("--sync", action="store_true", help="alias của --apply")
    ap.add_argument("--confirm", default="", help="phải = LIVE_HARAVAN để LIVE thật")
    ap.add_argument("--out", default="", help="thư mục xuất preview HTML (DRY)")
    # giữ tương thích cờ cũ --dry (no-op vì DRY là mặc định)
    ap.add_argument("--dry", action="store_true", help="(no-op) DRY là mặc định")
    args = ap.parse_args()

    if not args.ids:
        print("Cần ít nhất 1 product id. (DRY mặc định; LIVE cần --apply --confirm LIVE_HARAVAN)")
        sys.exit(1)

    live_requested = args.apply or args.sync
    if live_requested and args.confirm != "LIVE_HARAVAN":
        print("❌ TỪ CHỐI LIVE: thiếu '--confirm LIVE_HARAVAN'. KHÔNG PUT Haravan. "
              "(Bỏ --apply/--sync để chạy DRY offline.)")
        sys.exit(2)

    live = live_requested and args.confirm == "LIVE_HARAVAN"
    out_dir = Path(args.out) if args.out else None
    mode = "LIVE (PUT Haravan)" if live else "DRY (offline DB)"
    print(f"── reformat_product_desc · mode={mode} · {len(args.ids)} SP ──")
    for pid in args.ids:
        try:
            print(apply_one_live(pid) if live else dry_one(pid, out_dir))
        except Exception as e:
            print({"id": pid, "error": str(e)[:160]})


if __name__ == "__main__":
    main()
