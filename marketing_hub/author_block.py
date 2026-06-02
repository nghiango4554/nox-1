"""author_block.py — Hộp tác giả + Person/Author JSON-LD cho bài blog (E-E-A-T EXPERTISE).

Theme Haravan tự inject Article schema nhưng KHÔNG có author → ta chèn thêm:
  1. Hộp tác giả nhìn thấy được (cuối bài) — tên, chức danh, link social.
  2. <script type="application/ld+json"> Person (sameAs Facebook) — Google đọc mọi JSON-LD trên trang.

Idempotent: nhận diện qua attribute data-author-box để KHÔNG chèn 2 lần.
"""
from __future__ import annotations

import json

# Hồ sơ tác giả THẬT (vợ chốt 2/6) — checklist E-E-A-T cấm tác giả ảo.
AUTHOR = {
    "name": "Trọng Nghĩa",
    "job_title": "CTV SEO Website",
    "org": "Sintech",
    "url": "https://www.facebook.com/may.meocan.9/",
    "bio": "",  # chưa cần — để trống
}

_MARKER = "data-author-box"


def has_author_box(html: str) -> bool:
    return bool(html) and _MARKER in html


def build_author_box(author: dict | None = None) -> str:
    a = author or AUTHOR
    name = (a.get("name") or "").strip()
    role = (a.get("job_title") or "").strip()
    org = (a.get("org") or "").strip()
    url = (a.get("url") or "").strip()
    bio = (a.get("bio") or "").strip()
    if not name:
        return ""

    person: dict = {"@context": "https://schema.org", "@type": "Person", "name": name}
    if role:
        person["jobTitle"] = role
    if url:
        person["sameAs"] = [url]
    if org:
        person["worksFor"] = {"@type": "Organization", "name": org}
    schema = json.dumps(person, ensure_ascii=False)

    sub = role + (" · " + org if org else "") if role else org
    fb = (f'<a href="{url}" target="_blank" rel="noopener nofollow" '
          f'style="color:#e74c3c;text-decoration:none">Facebook ↗</a>') if url else ""
    box = (
        f'<div {_MARKER}="1" style="margin:28px 0 6px;padding:14px 16px;border:1px solid #e5e7eb;'
        f'border-left:4px solid #e74c3c;border-radius:8px;background:#fafafa;font-family:Arial,sans-serif">'
        f'<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px;'
        f'margin-bottom:4px">Tác giả</div>'
        f'<div style="font-weight:700;color:#111;font-size:15px">{name}</div>'
        + (f'<div style="color:#555;font-size:13px;margin-top:2px">{sub}</div>' if sub else "")
        + (f'<div style="color:#555;font-size:13px;margin-top:4px">{bio}</div>' if bio else "")
        + (f'<div style="font-size:13px;margin-top:6px">{fb}</div>' if fb else "")
        + f'</div>'
        f'<script type="application/ld+json">{schema}</script>'
    )
    return box


def ensure_author_box(html: str, author: dict | None = None) -> str:
    """Chèn hộp tác giả vào CUỐI body nếu CHƯA có (idempotent). Trả body mới."""
    if not html:
        return html or ""
    if has_author_box(html):
        return html
    box = build_author_box(author)
    return (html.rstrip() + "\n" + box) if box else html
