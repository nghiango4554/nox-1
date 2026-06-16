# -*- coding: utf-8 -*-
"""Gỡ câu intro/outro Nox tự chèn (trùng với intro + footer hotline sẵn có của bài).
Chỉ xóa <p> đầu nếu khớp top-prefix, <p> cuối nếu khớp bot-prefix → an toàn, không đụng nội dung."""
import re, time
from bs4 import BeautifulSoup
import haravan_client as hc
import blog_rewrite_apply as ap

# (kind, id..., top_prefix, bot_prefix)
JOBS = [
    ("product", 1068255170, None, "CPU Intel Core i9-9900K cũ (5GHz", "Liên hệ Sintech để kiểm tra CPU"),
    ("blog", 1000906526, 1002411453, "Sintech tổng hợp bảng mã lỗi", "Nếu main X99 báo lỗi khó xác định"),
    ("blog", 1000906526, 1002404456, "Sintech thu mua PC, máy tính cũ giá cao", "Cần thanh lý PC cũ"),
]


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


for job in JOBS:
    kind = job[0]
    if kind == "product":
        pid = job[1]; top_pre, bot_pre = job[3], job[4]
        body = hc._request("GET", "/products/%d.json" % pid)["product"].get("body_html") or ""
        label = "product %d" % pid
    else:
        blog, art = job[1], job[2]; top_pre, bot_pre = job[3], job[4]
        _, a = ap._fetch_live_article(blog, art)
        body = a.get("body_html") or ""
        label = "blog %d/%d" % (blog, art)

    soup = BeautifulSoup(body, "lxml")
    container = soup.body or soup
    ps = container.find_all("p")
    removed = []
    # top
    if ps and norm(ps[0].get_text()).startswith(norm(top_pre)):
        ps[0].decompose(); removed.append("top")
    # bot (re-find after possible top removal)
    ps2 = container.find_all("p")
    if ps2 and norm(ps2[-1].get_text()).startswith(norm(bot_pre)):
        ps2[-1].decompose(); removed.append("bot")

    new = "".join(str(x) for x in (soup.body.contents if soup.body else soup.contents)).strip()
    new = re.sub(r"^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+", "", new)

    if not removed:
        print("%-22s | KHÔNG khớp prefix nào (bỏ qua)" % label)
        continue
    if kind == "product":
        hc._request("PUT", "/products/%d.json" % pid, payload={"product": {"id": pid, "body_html": new}})
    else:
        ap._put_article(blog, art, {"id": art, "body_html": new})
    time.sleep(1)
    print("%-22s | gỡ %s | hotline còn=%d" % (label, "+".join(removed), new.count("0911 713 000")))
