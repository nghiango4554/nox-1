# -*- coding: utf-8 -*-
"""Gỡ dòng phân cách toàn dấu gạch '—-----' (separator artifact) cuối bài. Body-only PUT."""
import re, time
from bs4 import BeautifulSoup
import haravan_client as hc
import blog_rewrite_apply as ap

PROD = [1068255170, 1074653556, 1074564335, 1062537121, 1053655520]
BLOG = [(1000906526, 1002411453), (1000906526, 1002404456), (1000906526, 1002420376),
        (1000906526, 1002717797), (1000906526, 1002402249)]
DASH = re.compile(r'^[\s—–\-_=•·.*]{3,}$')


def clean(body):
    soup = BeautifulSoup(body, "lxml")
    cont = soup.body or soup
    removed = 0
    for el in cont.find_all(["p", "div"]):
        t = el.get_text().strip()
        if t and DASH.fullmatch(t):
            el.decompose(); removed += 1
    new = "".join(str(x) for x in (soup.body.contents if soup.body else soup.contents)).strip()
    return new, removed


for pid in PROD:
    b = hc._request("GET", "/products/%d.json" % pid)["product"].get("body_html") or ""
    new, r = clean(b)
    if r:
        hc._request("PUT", "/products/%d.json" % pid, payload={"product": {"id": pid, "body_html": new}})
        time.sleep(0.6)
    print("prod %d | gỡ %d dòng gạch" % (pid, r))
for bid, aid in BLOG:
    b = ap._fetch_live_article(bid, aid)[1].get("body_html") or ""
    new, r = clean(b)
    if r:
        ap._put_article(bid, aid, {"id": aid, "body_html": new})
        time.sleep(0.6)
    print("blog %d | gỡ %d dòng gạch" % (aid, r))
