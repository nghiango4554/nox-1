# -*- coding: utf-8 -*-
"""Ap khuon trang tri COMBO PC len body_html cua mot bai blog.

Khuon nay vo chot 20/08/2026 cho loat bai The Isle, lay mau THAT tu bai da live
(id 1003086405) chu khong phai suy doan. Dung lai cho moi bai blog can trang tri.

Dung:
    from trang_tri_combo import trang_tri
    body_moi = trang_tri(body_cu)

Hoac chay thang de xu ly mot bai:
    python trang_tri_combo.py <blog_id> <article_id>          # chay thu
    python trang_tri_combo.py <blog_id> <article_id> ghi      # day len Haravan
"""
import io, json, os, re, sys, datetime

WRAP = ("font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:#1a1a1a;"
        "max-width:820px;line-height:1.7;font-size:14.5px")
H2 = ("font-size:18px;color:#dc2626;font-weight:700;border-left:4px solid #dc2626;"
      "padding-left:10px;margin:26px 0 12px")
H3 = ("font-size:16px;color:#1a1a1a;font-weight:700;margin:18px 0 8px;padding-left:9px;"
      "border-left:3px solid #f0a5a5")
P = "margin:10px 0"
A = "color:#1f50bc;text-decoration:none;font-weight:600"
TABLE = ("width:100%;border-collapse:collapse;font-family:inherit;margin:14px 0;"
         "border:1px solid #b9c4d0")
TH = ("padding:11px 12px;font-weight:700;font-size:11.5px;letter-spacing:.4px;"
      "text-transform:uppercase;color:#ffffff;background:#1e40af;border:1px solid #1a3691;"
      "text-align:left")
TD = "padding:10px 12px;border:1px solid #d3dae2;vertical-align:top"
TD_SOC = TD + ";background:#f7f9fb"
UL_BOX = "border:1px solid #e4e8ed;border-radius:8px;background:#fbfcfd;padding:12px 16px;margin:14px 0"
UL_BOX_DO = ("border:1px solid #cbd5e1;border-left:4px solid #dc2626;border-radius:8px;"
             "background:#f8fafc;padding:14px 18px;margin:14px 0")
UL = "margin:0;padding-left:20px"
LI = "margin:7px 0"
IMG = "max-width:600px;width:100%;height:auto;display:block;margin:0 auto;border-radius:8px"


def _dat_style(html_, the, style):
    """Ghi de thuoc tinh style cua tung the mo. Chi dung vao THE MO,
    khong bao gio cham noi dung ben trong (tranh be </a> nhu su co 16/7)."""
    def thay(m):
        mo = m.group(0)
        mo = re.sub(r'\s+style="[^"]*"', "", mo)
        mo = re.sub(r"\s+style='[^']*'", "", mo)
        return mo[:-1].rstrip() + ' style="%s">' % style
    return re.sub(r"<%s\b[^>]*>" % the, thay, html_, flags=re.I)


def _boc_list(html_):
    """Dong khoi moi <ul>/<ol> than bai. Hop dau tien vien do (tom tat),
    cac hop sau trung tinh — dung nhu bai mau."""
    dem = {"n": 0}

    def thay(m):
        khoi = m.group(0)
        if 'class="tom-tat"' in khoi:
            box = UL_BOX_DO
        else:
            dem["n"] += 1
            box = UL_BOX_DO if dem["n"] == 1 else UL_BOX
        return '<div style="%s">%s</div>' % (box, khoi)

    # Bo qua list da nam trong hop roi
    html_ = re.sub(r"<(ul|ol)\b[^>]*>.*?</\1>", thay, html_, flags=re.S | re.I)
    return html_


def _soc_bang(html_):
    """To nen xen ke cho hang chan trong tung bang."""
    def mot_bang(mb):
        bang = mb.group(0)
        hang = list(re.finditer(r"<tr\b[^>]*>.*?</tr>", bang, flags=re.S | re.I))
        if len(hang) < 3:
            return bang
        ra, cuoi, thu = [], 0, 0
        for h in hang:
            noi = h.group(0)
            co_th = re.search(r"<th\b", noi, re.I)
            if not co_th:
                thu += 1
                if thu % 2 == 0:
                    noi = re.sub(r'<td\b[^>]*>',
                                 lambda m: m.group(0)[:-1].rstrip().replace(
                                     'style="%s"' % TD, 'style="%s"' % TD_SOC) + ">",
                                 noi, flags=re.I)
            ra.append(bang[cuoi:h.start()])
            ra.append(noi)
            cuoi = h.end()
        ra.append(bang[cuoi:])
        return "".join(ra)

    return re.sub(r"<table\b[^>]*>.*?</table>", mot_bang, html_, flags=re.S | re.I)


def trang_tri(body):
    """Tra ve body da ap khuon combo. Khong doi mot chu nao cua noi dung."""
    b = body

    # Go wrapper cu neu da boc roi, de chay lai khong bi long nhieu lop
    m = re.match(r'\s*<div style="[^"]*max-width:820px[^"]*">(.*)</div>\s*$', b, re.S)
    if m:
        b = m.group(1)

    for the, style in (("h2", H2), ("h3", H3), ("h4", H3), ("p", P), ("a", A),
                       ("table", TABLE), ("th", TH), ("td", TD),
                       ("ul", UL), ("ol", UL), ("li", LI), ("img", IMG)):
        b = _dat_style(b, the, style)

    b = _boc_list(b)
    b = _soc_bang(b)
    return '<div style="%s">%s</div>' % (WRAP, b)


def main():
    if len(sys.argv) < 3:
        raise SystemExit("dung: python trang_tri_combo.py <blog_id> <article_id> [ghi]")
    blog_id, art_id = int(sys.argv[1]), int(sys.argv[2])
    ghi = len(sys.argv) > 3 and sys.argv[3] == "ghi"

    sys.path.insert(0, r"C:\Users\NGHIANGO\.openclaw\workspace\nox-1")
    sys.path.insert(0, r"C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub")
    import haravan_client as hc

    OUT = r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs"
    art = hc.get_article(blog_id, art_id)
    art = art.get("article", art)
    body = art.get("body_html") or ""

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(OUT, "_BACKUP_trangtri_%s_%s.json" % (art_id, stamp))
    json.dump(art, io.open(bak, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("BACKUP =>", bak)

    moi = trang_tri(body)
    print("body cu :", len(body))
    print("body moi:", len(moi))

    # chu nghia phai y nguyen, chi doi trang tri
    chu_cu = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()
    chu_moi = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", moi)).strip()
    print("chu giu nguyen:", "DUNG" if chu_cu == chu_moi else "SAI (%d vs %d)" % (len(chu_cu), len(chu_moi)))
    if chu_cu != chu_moi:
        raise SystemExit("DUNG LAI: noi dung chu bi doi, khong duoc ghi")

    for ten, dieu in (("wrapper 820px", "max-width:820px" in moi),
                      ("H2 do", "#dc2626" in moi),
                      ("header bang xanh", "#1e40af" in moi),
                      ("hop bullet", "#fbfcfd" in moi or "#f8fafc" in moi)):
        print("  %s %s" % ("OK  " if dieu else "SAI ", ten))

    io.open(os.path.join(OUT, "_trangtri_moi_%s.html" % art_id), "w", encoding="utf-8").write(moi)

    if not ghi:
        print("\n[CHAY THU] chua day len.")
        return

    hc.update_article(blog_id, art_id, {"body_html": moi})
    lai = hc.get_article(blog_id, art_id)
    lai = (lai.get("article", lai).get("body_html") or "")
    print("\nDoi chieu sau khi ghi: %d ky tu | %s" % (
        len(lai), "DA LUU" if "max-width:820px" in lai else "CHUA LUU, PUT LAI"))


if __name__ == "__main__":
    main()
