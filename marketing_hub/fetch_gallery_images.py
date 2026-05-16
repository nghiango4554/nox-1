"""Tải gallery 4 ảnh/post từ sintech.vn cho 14 bài.
Dedupe size variants (_1024x1024, _medium, _large, ...).
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import db

UPLOAD = ROOT / "uploads"
UPLOAD.mkdir(parents=True, exist_ok=True)

# Đã crawl từ WebFetch sintech.vn product pages
URLS_BY_CODE = {
    "FB0003": [
        "https://cdn.hstatic.net/products/200000860097/cpu_amd_ryzen_9_9800x3d__4.7ghz_boost_5.2ghz_8_nh_n_16_lu_ng__e4b0f1e919454125b6b80cfd31facada.png",
        "https://cdn.hstatic.net/products/200000860097/cpu_amd_ryzen_9_9800x3d__4.7ghz_boost_5.2ghz__8_nh_n_16_lu_ng_1_99381d8b11e243ffae01e040545422ef.png",
    ],
    "FB0004": [
        "https://product.hstatic.net/200000860097/product/image-hastech-7_8c250b9c4498493daa4a4dece29b3805.jpg",
        "https://product.hstatic.net/200000860097/product/image-hastech-3-3_253b85b8992f438b9d270d83f52b2e71.jpg",
        "https://product.hstatic.net/200000860097/product/image-hastech-1-3_2086c2358de54d54804fee353e7e29cb.jpg",
        "https://product.hstatic.net/200000860097/product/image-hastech-4-3_24b3eb91dcf342d688c58265bc74c34b.jpg",
        "https://product.hstatic.net/200000860097/product/image-hastech-2-3_21f9626406bb4ce29806bda8db62be16.jpg",
    ],
    "FB0005": [
        "https://cdn.hstatic.net/products/200000860097/52008_1_e609140c7b7244f8bbea001149cb554a.jpg",
        "https://cdn.hstatic.net/products/200000860097/52008_vga_asus_prime_rtx_5060_ti_16gb_gddr7_oc__3__6ed619167edc41308a61ad38f9be5db7.jpg",
        "https://cdn.hstatic.net/products/200000860097/52008_vga_asus_prime_rtx_5060_ti_16gb_gddr7_oc__4__d210a04c59244670bf6937c2b3ded473.jpg",
        "https://cdn.hstatic.net/products/200000860097/52008_vga_asus_prime_rtx_5060_ti_16gb_gddr7_oc__1__80940a78fef4440fb7c65b9127421518.jpg",
    ],
    "FB0006": [
        "https://cdn.hstatic.net/products/200000860097/ram-pc-ddr5-kingston-fury-beast-32gb-6000mhz-kf560c40bb-32-hinh-1_e0385f7035bb44b5b1a88cfb83082485.jpg",
        "https://cdn.hstatic.net/products/200000860097/ram-pc-ddr5-kingston-fury-beast-32gb-6000mhz-kf560c40bb-32-hinh-2_1acf1f6f495e49c2b80a2710edc21d8d.jpg",
        "https://cdn.hstatic.net/products/200000860097/ram-pc-ddr5-kingston-fury-beast-32gb-6000mhz-kf560c40bb-32-hinh-3_80ce0a4b9cfc4da991d24ffed5186567.jpg",
    ],
    "FB0007": [
        "https://cdn.hstatic.net/products/200000860097/text_ng_n_14__9_139_db3b23d278434c7ba6b013727158a621.png",
        "https://cdn.hstatic.net/products/200000860097/text_ng_n_12__8_156_699d001c68794fe58ef1bcd18a6792d9.jpg",
        "https://cdn.hstatic.net/products/200000860097/text_ng_n_13__8_130_b1645a77886043919125a97d5a4062bc.jpg",
        "https://cdn.hstatic.net/products/200000860097/text_ng_n_11__7_171_bef9bef9871c4cc5ba9a2590614e0f06.jpg",
        "https://cdn.hstatic.net/products/200000860097/text_ng_n_10__5_247_683be762bed9413eaf10815bae9bfd66.png",
    ],
    "FB0008": [
        "https://product.hstatic.net/200000860097/product/deepcool-ag500-digital-argb-4_c8e194e6439644a88ee1de269b083f47_master_6e058cc89a0641658bb638abc98f69fb.png",
        "https://product.hstatic.net/200000860097/product/deepcool-ag500-digital-argb_ed9529f62bbd4e15a02130adf71c1efa_master_0f02e80ebfaa461184b2f4d8f3aa42fd.png",
    ],
    "FB0009": [
        "https://cdn.hstatic.net/products/200000860097/22982-asus-prime-ap201-case-mesh-white_99fece236fdb4d359ed53c20bbb05690.jpg",
        "https://cdn.hstatic.net/products/200000860097/12894_asus_prime_ap201_white__5__c350c6b3c0594320b59b94f089d703cf.jpg",
        "https://cdn.hstatic.net/products/200000860097/12894_asus_prime_ap201_white__3__97ad6741025b4c3b8c66df6a45be2784.jpg",
        "https://cdn.hstatic.net/products/200000860097/12894_asus_prime_ap201_white__4__5ddece37b5f84e3cad26284a30948f96.jpg",
    ],
    "FB0010": [
        "https://product.hstatic.net/200000860097/product/p-cs-rm850e-v3_471fd3b68d7748809932602dbf0f030a_master_62feaafb2a284d93927617657c729a3d.png",
        "https://file.hstatic.net/200000420363/file/p-cs-rm850e-v3-6_61be8664f9fb44158f9282834e3c72b1.jpg",
    ],
    "FB0011": [
        "https://cdn.hstatic.net/products/200000860097/image_-_2025-02-04t111024.698_6e883d39c9b9404da29204194cccae2a_0acb6ff1b23245128416abc0d2da4ca2.png",
        "https://cdn.hstatic.net/products/200000860097/image_-_2025-02-04t111034.189_cf661c29956a47249415eea959b3b8c9_35b66c9b7744483f8bc8e5303e14877b.png",
        "https://cdn.hstatic.net/products/200000860097/image_-_2025-02-04t111038.717_c2e48d0940ca416bb7417398a61fde2f_f7be2af8f049403e9f6638c196ee334d.png",
    ],
    "FB0012": [
        "https://product.hstatic.net/200000860097/product/battle-ax-z890m-plus-v20-1_f7bc042183f745a194a6ea7edeae989e.png",
        "https://product.hstatic.net/200000860097/product/battle-ax-z890m-plus-v20-7_3b79111bc9c74d81bec38b30d8ea33d9.png",
        "https://product.hstatic.net/200000860097/product/battle-ax-z890m-plus-v20-5_b5b0fef943e94b79bc5b5f248bece186.png",
        "https://product.hstatic.net/200000860097/product/battle-ax-z890m-plus-v20-6_50f3c91811a84682a8c27accf75cd9ea.png",
    ],
    "FB0013": [
        "https://product.hstatic.net/200000860097/product/z6137856845542_e9bcd7e1089cfabef1359ea32fc992ab_5dc93e9bb6424288880711e0b2477826.jpg",
    ],
    "FB0014": [
        "https://product.hstatic.net/200000860097/product/22627-tuf-vg279q1a-01_41fb179248ab497e911f2584e9569006.jpg",
        "https://product.hstatic.net/200000860097/product/22627-tuf-vg279q1a-02_ae50c9574ec34ca19d0f80e6d7f65bff.jpg",
        "https://product.hstatic.net/200000860097/product/22627-tuf-vg279q1a-03_e71a7e9ebd0c4ab5a305becd994f2b83.jpg",
        "https://product.hstatic.net/200000860097/product/22627-tuf-vg279q1a-04_563c91ce00d74fcf8ee3af2ea1e1ba48.jpg",
    ],
    "FB0015": [
        "https://cdn.hstatic.net/products/200000860097/f75__2__ef931bf74c0e4d96b8c9dd6266b87ab6.png",
        "https://cdn.hstatic.net/products/200000860097/f75__4__471eb60486b44ba2831d85d93db0d6c4.png",
        "https://cdn.hstatic.net/products/200000860097/f75__3__8e0ac31794034fad819b310e9746f4f7.png",
        "https://cdn.hstatic.net/products/200000860097/f75__1__012777a9137c4b7c805af712e5ddb2a7.png",
    ],
    "FB0016": [
        "https://cdn.hstatic.net/products/200000860097/sc506__1__5c908e1eab114eaf99c3571511b48d8d.png",
        "https://cdn.hstatic.net/products/200000860097/sc506__12__e1aca78f536144ab9d99cdedad8eb2a6.jpg",
        "https://cdn.hstatic.net/products/200000860097/sc506__9__29a31996f804440f95382d8b178adf81.jpg",
        "https://cdn.hstatic.net/products/200000860097/sc506__7__97e5d82a05fd4549988e3406c1f0cddd.png",
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Referer": "https://sintech.vn/",
}


def dedupe_variants(urls):
    """Strip size suffixes (_NNNxNNN, _medium, _large, _grande, _compact, _small) → keep first."""
    seen = set()
    result = []
    for u in urls:
        # remove query string
        clean = u.split("?")[0]
        # base = strip size suffix before extension
        base = re.sub(
            r"_(\d+x\d+|small|medium|large|grande|compact|master)(\.[a-zA-Z]+)$",
            r"\2",
            clean,
        )
        if base not in seen:
            seen.add(base)
            result.append(u)
    return result


def download(url: str, dest: Path) -> bool:
    if url.startswith("//"):
        url = "https:" + url
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) < 1000:
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"   ✗ download fail: {e}")
        return False


# remove old single-image files
for code in URLS_BY_CODE.keys():
    for ext in ("jpg", "jpeg", "png", "webp"):
        old = UPLOAD / f"{code.lower()}-product.{ext}"
        if old.exists():
            old.unlink()

results = {}
for code, urls in URLS_BY_CODE.items():
    urls = dedupe_variants(urls)[:4]
    saved = []
    for i, url in enumerate(urls, 1):
        ext = url.rsplit(".", 1)[-1].split("?")[0].split("&")[0].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            ext = "jpg"
        fname = f"{code.lower()}-product-{i}.{ext}"
        dest = UPLOAD / fname
        if download(url, dest):
            saved.append(fname)
            kb = dest.stat().st_size // 1024
            print(f"  ✓ {fname} ({kb} KB)")
        else:
            print(f"  ✗ {fname}")
    results[code] = saved

    if saved:
        conn = db.get_conn()
        conn.execute(
            "UPDATE posts SET image_path=?, images=?, updated_at=datetime('now') WHERE code=?",
            (saved[0], json.dumps(saved), code),
        )
        conn.commit()
        conn.close()

print("\n=== TỔNG KẾT ===")
need_more = []
for code, saved in results.items():
    flag = "✅" if len(saved) >= 4 else "⚠️ "
    print(f"  {flag} {code}: {len(saved)}/4 ảnh")
    if len(saved) < 4:
        need_more.append((code, len(saved)))

if need_more:
    print("\nSP cần fallback thêm:")
    for code, n in need_more:
        print(f"  • {code}: thiếu {4 - n} ảnh")
