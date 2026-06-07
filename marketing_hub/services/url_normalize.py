# -*- coding: utf-8 -*-
"""URL normalization — khóa join GSC × GA4 = date + normalized_path.

v1: bỏ TOÀN BỘ query string. Whitelist query param mặc định rỗng (mở rộng sau).
Rule:
  - bỏ scheme, host, fragment, toàn bộ query string
  - giữ "/" cho homepage
  - giữ slug tiếng Việt hợp lệ (decode %xx → UTF-8)
  - trailing slash thống nhất (bỏ trailing trừ root)
  - "(not set)" → sentinel không join
"""
from urllib.parse import urlsplit, unquote

NOT_SET = "(not set)"

# v1 rỗng — khi cần giữ query đặc biệt thì thêm tên param vào đây (hoặc qua config sau)
DEFAULT_QUERY_WHITELIST: tuple = ()


def normalize_landing_path(value, query_whitelist: tuple = DEFAULT_QUERY_WHITELIST) -> str:
    if value is None:
        return NOT_SET
    s = str(value).strip()
    if not s or s.lower() == NOT_SET:
        return NOT_SET

    parts = urlsplit(s)
    if parts.scheme or parts.netloc:
        path = parts.path or "/"
    else:
        # giá trị không có scheme/host (vd "/blogs/x?a=1#h" hoặc "abc")
        path = s.split("#", 1)[0].split("?", 1)[0]

    path = unquote(path)                 # giữ slug tiếng Việt
    if not path:
        path = "/"
    if not path.startswith("/"):
        path = "/" + path

    # trailing slash thống nhất: bỏ trailing trừ root
    if len(path) > 1:
        path = path.rstrip("/") or "/"

    # query whitelist (v1 rỗng → không giữ gì). Để mở rộng sau:
    if query_whitelist and parts.query:
        from urllib.parse import parse_qsl, urlencode
        kept = [(k, v) for k, v in parse_qsl(parts.query) if k in query_whitelist]
        if kept:
            path = path + "?" + urlencode(sorted(kept))

    return path


if __name__ == "__main__":
    tests = [
        ("https://sintech.vn/blogs/huong-dan/abc?utm_source=fb&fbclid=1", "/blogs/huong-dan/abc"),
        ("https://sintech.vn/", "/"),
        ("https://sintech.vn", "/"),
        ("/collections/pc-gaming/", "/collections/pc-gaming"),
        ("/tìm-kiếm/màn-hình", "/tìm-kiếm/màn-hình"),
        ("/t%C3%ACm/m%C3%A0n-h%C3%ACnh", "/tìm/màn-hình"),
        ("/page?gclid=xyz#section", "/page"),
        ("(not set)", "(not set)"),
        ("", "(not set)"),
        (None, "(not set)"),
    ]
    ok = 0
    for inp, exp in tests:
        got = normalize_landing_path(inp)
        flag = "OK " if got == exp else "FAIL"
        if got == exp:
            ok += 1
        print(f"{flag} {inp!r} -> {got!r} (exp {exp!r})")
    print(f"\n{ok}/{len(tests)} passed")
