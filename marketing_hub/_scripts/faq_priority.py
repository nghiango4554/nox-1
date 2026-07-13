"""Dung danh sach bai UU TIEN lam FAQ (thay cho kieu bom hang loat).

Boi canh 13/7/2026: Google DA GO FAQ rich result (7/5/2026). Schema khong con la KPI.
Gia tri con lai = noi dung FAQ hien thi bam truy van THAT + co hoi duoc trich trong AI Overview.
=> Chi lam bai CO impression that. Bai 0 imp thi khong gan FAQ (lo ROI + dau vet noi dung hang loat).

Phan nhom:
  A_EVERGREEN — co imp, noi dung con dung theo thoi gian  -> lam ngay
  B_TIN_CU    — co imp NHUNG la tin ra mat/ro ri/du kien  -> phai gan moc thoi gian hoac bo
  C_BO_QUA    — 0 impression                              -> khong gan FAQ, cho vo quyet giu/gop/redirect

Output: nox-outputs/faq_preview/faq_priority.json (kem key chinh + top query GSC moi bai)
Chay:  py -3.12 _scripts/faq_priority.py
"""
import datetime
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import faq_schema
import haravan_blog as hb

BLOGS = {1000906526: "news", 1000960873: "huong-dan"}
OUT = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_preview\faq_priority.json")
GSC_TOKEN = r"C:\Users\NGHIANGO\.openclaw\workspace\gsc\token.json"

# tin ra mat / ro ri / du kien -> het han theo thoi gian
RUMOR = re.compile(r"rò rỉ|đồn|lộ diện|dự kiến|sắp ra mắt|ra mắt|công bố|trình làng|"
                   r"úp mở|hé lộ|leak|xác nhận sẽ", re.I)


def gsc_pages():
    creds = Credentials.from_authorized_user_file(
        GSC_TOKEN, ["https://www.googleapis.com/auth/webmasters.readonly"])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    end = datetime.date.today() - datetime.timedelta(days=2)
    start = end - datetime.timedelta(days=89)
    rows = svc.searchanalytics().query(siteUrl="sc-domain:sintech.vn", body={
        "startDate": start.isoformat(), "endDate": end.isoformat(),
        "dimensions": ["page", "query"], "rowLimit": 25000,
    }).execute().get("rows", [])
    kw = defaultdict(list)
    for r in rows:
        p = r["keys"][0].rstrip("/")
        if "/blogs/" in p:
            kw[p].append({"kw": r["keys"][1], "clk": r["clicks"],
                          "imp": r["impressions"], "pos": round(r["position"], 1)})
    for p in kw:
        kw[p].sort(key=lambda k: -k["imp"])
    print(f"GSC {start} -> {end}: {len(kw)} URL blog co hien thi")
    return kw


def main():
    kw = gsc_pages()
    rows = []
    for bid, slug in BLOGS.items():
        page = 1
        while True:
            arts = hb.list_articles(bid, limit=50, page=page)
            if not arts:
                break
            for a in arts:
                body = a.get("body_html") or ""
                url = f"https://sintech.vn/blogs/{slug}/{a.get('handle')}"
                keys = kw.get(url, [])
                imp = sum(k["imp"] for k in keys)
                title = a.get("title") or ""
                has_faq = len(faq_schema.extract_faq(body))

                if imp <= 0:
                    grp = "C_BO_QUA"
                elif RUMOR.search(title):
                    grp = "B_TIN_CU"
                else:
                    grp = "A_EVERGREEN"

                rows.append({
                    "group": grp, "blog_id": bid, "id": a["id"], "handle": a.get("handle"),
                    "title": title, "url": url, "imp": imp,
                    "clk": sum(k["clk"] for k in keys),
                    "n_faq_hien_tai": has_faq,
                    "da_day": has_faq >= 2,
                    "key_chinh": keys[0]["kw"] if keys else "",
                    "top_keys": keys[:8],
                    "published": (a.get("published_at") or "")[:10],
                    "body": body,
                })
            page += 1

    rows.sort(key=lambda r: -r["imp"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    for g in ("A_EVERGREEN", "B_TIN_CU", "C_BO_QUA"):
        sel = [r for r in rows if r["group"] == g]
        day = sum(1 for r in sel if r["da_day"])
        print(f"\n=== {g}: {len(sel)} bai (da co FAQ: {day})")
        for r in sel[:12] if g != "C_BO_QUA" else []:
            mark = "✔" if r["da_day"] else " "
            print(f"  {mark} {r['imp']:>6} imp · {r['title'][:42]:44s} | key: {r['key_chinh'][:34]}")
    print(f"\n[XONG] {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
