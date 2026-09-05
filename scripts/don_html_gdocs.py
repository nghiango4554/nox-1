# -*- coding: utf-8 -*-
"""Don HTML rac do dan tu Google Docs: bo <span> chi mang style, bo style rac
tren p/li/h2, giu nguyen <strong>, <a>, <img>, <table>.

⚠️ DUNG HTMLParser, KHONG dung regex — su co 16/7/2026: regex don <span> an mat
mot the </a> va nuot ca doan 391 ky tu ma "chu van y nguyen" nen khong ai phat hien.

Dung:
    from don_html_gdocs import don
    sach = don(body_html)
"""
from html.parser import HTMLParser
import html as _html
import re

# The tu dong dong, khong co the dong
RONG = {"br", "img", "hr", "input", "meta", "link", "col", "source"}

# The bi go hoan toan (giu noi dung ben trong)
GO = {"span", "font"}

# Thuoc tinh giu lai theo tung the
GIU = {
    "a": ("href", "target", "rel", "title"),
    "img": ("src", "alt", "width", "height"),
    "table": (), "thead": (), "tbody": (), "tr": (), "th": (), "td": (),
    "colgroup": (), "col": (),
}


class Don(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.ra = []
        self.bo_qua = 0          # dang trong <style>/<script> rac
        self.giu_ld = 0          # dang trong <script type="application/ld+json"> — PHAI GIU

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            # 🚨 JSON-LD SONG tren trang live (do 21/08/2026, bai RAM co FAQPage hien ra
            # trong ma nguon). Xoa la mat rich result — giu nguyen ca the lan noi dung.
            loai = dict(attrs).get("type") or ""
            if "ld+json" in loai.lower():
                self.giu_ld += 1
                self.ra.append('<script type="application/ld+json">')
                return
            self.bo_qua += 1
            return
        if tag == "style":
            self.bo_qua += 1
            return
        if tag in GO:
            return               # go the mo, giu noi dung
        d = dict(attrs)
        giu = GIU.get(tag)
        if giu is None:
            # the thuong: bo sach style/class rac, khuon trang tri se dat lai sau
            moi = {k: v for k, v in d.items() if k in ("colspan", "rowspan", "id")}
        else:
            moi = {k: v for k, v in d.items() if k in giu}
        s = "<" + tag
        for k, v in moi.items():
            if v is None:
                s += " " + k
            else:
                s += ' %s="%s"' % (k, _html.escape(v, quote=True))
        s += ">"
        self.ra.append(s)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "script":
            if self.giu_ld:
                self.giu_ld -= 1
                self.ra.append("</script>")
            else:
                self.bo_qua = max(0, self.bo_qua - 1)
            return
        if tag == "style":
            self.bo_qua = max(0, self.bo_qua - 1)
            return
        if tag in GO or tag in RONG:
            return
        self.ra.append("</%s>" % tag)

    def handle_data(self, data):
        if self.bo_qua and not self.giu_ld:
            return
        self.ra.append(data)

    def handle_comment(self, data):
        # 🚨 GIU comment. Theme Sintech nhet FAQ schema vao body duoi dang
        # <!--FAQJSON:{...}--> roi render ra <script type="application/ld+json"> tren trang.
        # Xoa comment la mat FAQPage — da kiem trang live 21/08/2026, schema do CO song.
        if not self.bo_qua:
            self.ra.append("<!--%s-->" % data)

    def handle_entityref(self, name):
        if not self.bo_qua:
            self.ra.append("&%s;" % name)

    def handle_charref(self, name):
        if not self.bo_qua:
            self.ra.append("&#%s;" % name)


def _chu(h):
    t = re.sub(r"<[^>]+>", " ", h or "")
    t = _html.unescape(t).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def don(body):
    """Tra ve HTML da don. Nem loi neu phan chu bi doi — khong bao gio ghi bua."""
    p = Don()
    p.feed(body)
    p.close()
    ra = "".join(p.ra)

    # don khoang trang thua giua cac the, khong dung vao noi dung
    ra = re.sub(r">\s*\n\s*<", "><", ra)
    ra = re.sub(r"<p>\s*(?:&nbsp;|\s)*</p>", "", ra)
    ra = re.sub(r"<li>\s*(?:&nbsp;|\s)*</li>", "", ra)

    truoc, sau = _chu(body), _chu(ra)
    if truoc != sau:
        # tim cho lech dau tien de bao cho de sua
        n = min(len(truoc), len(sau))
        i = next((k for k in range(n) if truoc[k] != sau[k]), n)
        raise ValueError(
            "Don HTML lam DOI phan chu (truoc %d, sau %d). Lech tu vi tri %d:\n"
            "  truoc: ...%s...\n  sau  : ...%s..."
            % (len(truoc), len(sau), i, truoc[max(0, i - 60):i + 60], sau[max(0, i - 60):i + 60]))

    # kiem the doi xung co ban
    for the in ("a", "strong", "table", "ul", "ol", "li", "h2", "h3", "p"):
        mo = len(re.findall(r"<%s\b" % the, ra))
        dong = len(re.findall(r"</%s>" % the, ra))
        if mo != dong:
            raise ValueError("The <%s> khong can: %d mo / %d dong" % (the, mo, dong))
    return ra


if __name__ == "__main__":
    import io, json, os, sys, datetime
    if len(sys.argv) < 3:
        raise SystemExit("dung: python don_html_gdocs.py <blog_id> <article_id> [ghi]")
    blog_id, art_id = int(sys.argv[1]), int(sys.argv[2])
    ghi = len(sys.argv) > 3 and sys.argv[3] == "ghi"

    sys.path.insert(0, r"C:\Users\NGHIANGO\.openclaw\workspace\nox-1")
    sys.path.insert(0, r"C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub")
    import haravan_client as hc

    OUT = r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs"
    a = hc.get_article(blog_id, art_id)
    a = a.get("article", a)
    body = a.get("body_html") or ""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json.dump(a, io.open(os.path.join(OUT, "_BACKUP_don_%s_%s.json" % (art_id, stamp)),
                         "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    sach = don(body)
    print("body: %d -> %d ky tu (bot %.0f%%)" % (len(body), len(sach), 100 * (1 - len(sach) / len(body))))
    print("so <span> con lai:", sach.count("<span"))
    print("chu giu nguyen: DUNG")
    io.open(os.path.join(OUT, "_don_%s.html" % art_id), "w", encoding="utf-8").write(sach)

    if ghi:
        hc.update_article(blog_id, art_id, {"body_html": sach})
        lai = hc.get_article(blog_id, art_id)
        lai = (lai.get("article", lai).get("body_html") or "")
        print("sau khi ghi: %d ky tu | %s" % (len(lai), "DA LUU" if len(lai) < len(body) else "KIEM LAI"))
    else:
        print("[CHAY THU] chua day len.")
