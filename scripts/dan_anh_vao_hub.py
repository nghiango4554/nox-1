# -*- coding: utf-8 -*-
"""Dan 1 anh tu dia vao DAU danh sach anh cua SP tren hub /thumbs.

    python dan_anh_vao_hub.py <handle> <duong_dan_anh>

Goi POST /thumbs/paste — hub tu chuan hoa 1000x1000 roi chen len vi tri 1.
CHI ghi vao hub LOCAL, KHONG day live (day live la nut rieng tren trang).
Anh cu KHONG bi xoa, no tut xuong vi tri 2.
"""
import base64, io, json, os, sys, urllib.request

HUB = "http://127.0.0.1:5055"


def dan(handle, path):
    raw = open(path, "rb").read()
    body = json.dumps({"handle": handle,
                       "image": "data:image/png;base64," + base64.b64encode(raw).decode()})
    req = urllib.request.Request(HUB + "/thumbs/paste", data=body.encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    r = json.load(urllib.request.urlopen(req, timeout=120))
    return r


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    h, p = sys.argv[1], sys.argv[2]
    print("dan %s (%d byte) -> %s" % (os.path.basename(p), os.path.getsize(p), h))
    print(json.dumps(dan(h, p), ensure_ascii=False)[:300])
