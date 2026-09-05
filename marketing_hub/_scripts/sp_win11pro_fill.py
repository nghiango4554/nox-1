"""Dien mo ta + SEO cho 2 SP ban quyen Windows 11 Pro dang trong ruot.

Bam khuon 13 SP ban quyen Windows anh em: 8 H2, signature TREN spec,
spec trong blockquote o CUOI. Style inline (Haravan xoa the <style>).

--thu   : sinh HTML ra file, khong dung Haravan
--ghi   : PUT body + SEO len san pham
"""
import argparse
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import haravan_client as hc  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OUT = Path(__file__).resolve().parent.parent.parent.parent / "nox-outputs"
DO = "#dc2626"

# Yeu cau he thong: lay tu trang chinh thuc Microsoft windows-11-specifications
YCHT = [
    ("Bộ xử lý", "1 GHz trở lên, từ 2 nhân, trên vi xử lý 64-bit tương thích"),
    ("RAM", "4 GB trở lên"),
    ("Dung lượng lưu trữ", "64 GB trở lên"),
    ("Firmware", "UEFI, có hỗ trợ Secure Boot"),
    ("TPM", "Phiên bản 2.0"),
    ("Đồ họa", "Tương thích DirectX 12 trở lên, driver WDDM 2.0"),
    ("Màn hình", "Độ phân giải HD 720p, kích thước trên 9 inch"),
]

SP = {
    1076071149: dict(
        ten="Phần mềm Microsoft Windows 11 Pro 64Bit Eng Intl 1PK DSP OEI DVD (FQC-10528)",
        ma="FQC-10528",
        dang="1PK DSP OEI DVD",
        ngon_ngu="English International",
        seo_t="Windows 11 Pro 64-bit DSP OEI DVD FQC-10528 chính hãng",
        seo_d=("Phần mềm Windows 11 Pro 64-bit bản DSP OEI DVD mã FQC-10528, đĩa cài kèm hộp, "
               "dùng cho máy build mới. Tư vấn và kiểm hàng tại Sintech, hotline 0911 713 000."),
        mo_ta_1=("Với một bộ máy dùng để làm việc, học tập hay vận hành cửa hàng, hệ điều hành bản quyền "
                 "là thứ nên chuẩn bị ngay từ khi dựng máy. Bản DSP OEI DVD này đi kèm đĩa cài vật lý, "
                 "phù hợp khi hoàn thiện một cấu hình PC cụ thể và muốn giữ lại bộ cài phòng khi cần dựng lại máy."),
        mo_ta_2=("Đây là bản tiếng Anh quốc tế, dạng 1PK DSP OEI DVD, mã hàng FQC-10528. Dạng đóng gói này "
                 "thường được chọn khi lắp máy mới tại cửa hàng vì có mã hàng rõ ràng, thuận tiện khi bàn giao "
                 "và đối chiếu về sau."),
        diem=[("Đầy đủ tính năng bản Pro",
               "Có BitLocker để mã hóa ổ đĩa và Client Hyper-V để chạy máy ảo, hai tính năng chỉ có từ bản Pro trở lên. "
               "Phù hợp với máy chứa dữ liệu công việc hoặc cần môi trường thử nghiệm riêng."),
              ("Kèm đĩa cài vật lý",
               "Bản DVD giúp cài đặt không phụ thuộc đường truyền mạng, và giữ được bộ cài để dùng lại khi cần "
               "cài mới hoặc chuyển ổ cứng."),
              ("Mã hàng rõ ràng",
               "FQC-10528 là mã do Microsoft đặt cho đúng phiên bản này, tiện khi kiểm tra hàng lúc nhận "
               "và khi cần tra cứu về sau.")],
        hop=("Người dựng PC mới muốn có hệ điều hành bản quyền ngay từ đầu, người dùng doanh nghiệp cần "
             "BitLocker hoặc Hyper-V, và những ai muốn giữ đĩa cài vật lý thay vì tải qua mạng."),
        khong_hop=("Người chỉ dùng máy cho tác vụ cơ bản như duyệt web và xem phim thì bản Home đã đủ, "
                   "không cần thêm chi phí cho các tính năng Pro."),
    ),
    1076071312: dict(
        ten="Bản quyền Windows 11 Pro 64-bit COA",
        ma="COA",
        dang="Tem COA",
        ngon_ngu="Đa ngôn ngữ, có tiếng Việt",
        seo_t="Bản quyền Windows 11 Pro 64-bit COA chính hãng tại Sintech",
        seo_d=("Bản quyền Windows 11 Pro 64-bit dạng tem COA, chi phí thấp hơn bản hộp, dùng cho máy build "
               "hoặc nâng từ Home. Tư vấn và kích hoạt tại Sintech, 0911 713 000."),
        mo_ta_1=("Bản quyền dạng tem COA là cách phổ biến để đưa Windows 11 Pro lên một bộ máy mà không phải "
                 "trả chi phí cho hộp và đĩa cài. Phần được cấp là quyền sử dụng gắn với máy, còn bộ cài thì tải "
                 "trực tiếp từ Microsoft."),
        mo_ta_2=("Lựa chọn này hợp với người dựng máy mới hoặc đang chạy bản Home muốn lên Pro để dùng BitLocker "
                 "và Hyper-V. Chi phí thấp hơn đáng kể so với bản đóng hộp, đổi lại không có đĩa cài đi kèm."),
        diem=[("Chi phí thấp hơn bản hộp",
               "Cùng là Windows 11 Pro 64-bit nhưng bỏ phần hộp và đĩa, nên hợp lý khi cần trang bị bản quyền "
               "cho nhiều máy hoặc khi ngân sách dồn cho linh kiện."),
              ("Có đủ tính năng bản Pro",
               "BitLocker mã hóa ổ đĩa và Client Hyper-V chạy máy ảo, đúng như bản Pro đóng hộp. "
               "Khác biệt nằm ở cách đóng gói, không nằm ở tính năng."),
              ("Cài đặt bằng bộ cài tải về",
               "Bộ cài lấy trực tiếp từ Microsoft nên luôn là bản cập nhật mới, không phụ thuộc đĩa cũ.")],
        hop=("Người build PC muốn có bản quyền Pro với chi phí hợp lý, người đang dùng Home cần nâng lên Pro, "
             "và các máy văn phòng cần mã hóa ổ đĩa."),
        khong_hop=("Người bắt buộc phải có hộp và đĩa cài vật lý để lưu trữ hoặc để đưa vào hồ sơ tài sản "
                   "thì nên chọn bản đóng hộp thay vì tem COA."),
    ),
}


def h2(t):
    return (f'<h2 style="font-size: 20px; font-weight: 700; color: {DO}; border-left: 4px solid {DO}; '
            f'padding-left: 10px; margin: 26px 0 12px; line-height: 1.35;"><strong>{t}</strong></h2>')


def h3(t):
    return (f'<h3 style="font-size: 17px; font-weight: 700; color: #111; margin: 18px 0 8px; '
            f'line-height: 1.4;">{t}</h3>')


def p(t):
    return f'<p style="font-size: 16px; line-height: 1.65;">{t}</p>'


def dung(pid):
    s = SP[pid]
    ten = s["ten"]
    h = []
    h.append(h2(ten))
    h.append(p(s["mo_ta_1"]))
    h.append(p(s["mo_ta_2"].replace(
        "Sintech", '<a href="https://sintech.vn" style="color:#dc2626;" title="Sintech">Sintech</a>', 1)
        if "Sintech" in s["mo_ta_2"] else s["mo_ta_2"]))

    h.append(h2(f"Điểm nổi bật của {ten}"))
    for tieu, noi in s["diem"]:
        h.append(h3(tieu)); h.append(p(noi))

    h.append(h2("Trải nghiệm thực tế khi sử dụng"))
    h.append(p("Máy chạy bản quyền nhận đầy đủ bản vá bảo mật hàng tháng từ Microsoft, không hiện thông báo "
               "nhắc kích hoạt và không bị khóa phần cá nhân hóa giao diện. Với máy dùng cho công việc, đây là "
               "khác biệt thấy rõ nhất so với bản chưa kích hoạt."))
    h.append(p("Windows 11 Pro yêu cầu TPM 2.0 và Secure Boot, nên trước khi mua nên kiểm tra bo mạch chủ đã bật "
               "hai mục này trong BIOS hay chưa. Máy lắp tại Sintech được kiểm tra sẵn phần này khi bàn giao."))

    h.append(h2("Sản phẩm này phù hợp với ai"))
    h.append(p(s["hop"]))
    h.append(h3("Khi nào không phù hợp"))
    h.append(p(s["khong_hop"]))

    h.append(h2("Yêu cầu hệ thống cần đáp ứng"))
    h.append(p("Số liệu dưới đây lấy theo yêu cầu tối thiểu Microsoft công bố cho Windows 11."))
    h.append('<ul>' + "".join(
        f'<li style="font-size: 16px; line-height: 1.6;"><strong>{k}:</strong> {v}</li>' for k, v in YCHT) + '</ul>')

    h.append(h2(f"Ưu điểm khi chọn {ten}"))
    h.append(p("Bản quyền rõ ràng giúp máy nhận cập nhật đều, giữ được dữ liệu an toàn hơn nhờ mã hóa ổ đĩa, "
               "và tránh rủi ro dùng phần mềm không có nguồn gốc khi máy phục vụ công việc hoặc kinh doanh."))

    h.append(h2("Vì sao nên mua tại Sintech"))
    h.append(p("Sintech kiểm tra hàng trước khi giao, hỗ trợ cài đặt và kích hoạt nếu mua kèm bộ máy, và tư vấn "
               "chọn đúng phiên bản theo nhu cầu thay vì bán loại đắt nhất. Cần dựng máy trọn bộ thì đội kỹ thuật "
               "kiểm tra luôn phần TPM và Secure Boot khi lắp."))

    h.append(h2(f"Câu hỏi thường gặp về {ten}"))
    faq = [
        ("Bản quyền này dùng được cho mấy máy?",
         "Một bản quyền dùng cho một máy. Cần trang bị cho nhiều máy thì mua theo số lượng máy tương ứng."),
        ("Máy đang dùng Windows 11 Home có nâng lên Pro được không?",
         "Được. Máy vẫn giữ nguyên dữ liệu và ứng dụng, chỉ đổi phiên bản hệ điều hành."),
        ("Windows 11 Pro khác Home ở điểm nào?",
         "Bản Pro có thêm BitLocker để mã hóa ổ đĩa và Client Hyper-V để chạy máy ảo, là hai tính năng "
         "Microsoft ghi rõ chỉ có từ bản Pro trở lên."),
        ("Cần chuẩn bị gì trước khi cài?",
         "Kiểm tra bo mạch chủ có TPM 2.0 và đã bật Secure Boot trong BIOS, vì đây là yêu cầu bắt buộc của Windows 11."),
        ("Mua kèm bộ máy có được hỗ trợ cài không?",
         "Có. Mua kèm cấu hình tại Sintech thì phần cài đặt và kích hoạt được làm sẵn trước khi bàn giao."),
    ]
    for q, a in faq:
        h.append(h3(q)); h.append(p(a))

    # SIGNATURE dat TREN spec (thu tu canonical 2095 SP)
    h.append(f'<p style="font-size: 16px; line-height: 1.7; background: #fef2f2; border-left: 4px solid {DO}; '
             f'padding: 12px 16px; border-radius: 6px; margin: 18px 0; color: #111;"><em>Tư vấn cấu hình bởi '
             f'team kỹ thuật Sintech — Hotline <a href="tel:0911713000" style="display:inline-block;'
             f'background:{DO};color:#fff;padding:3px 12px;border-radius:6px;text-decoration:none;'
             f'font-weight:700;font-style:normal;white-space:nowrap">0911 713 000</a> · '
             f'457 Trần Xuân Soạn, Phường Tân Hưng, Thành phố Hồ Chí Minh.</em></p>')

    # SPEC trong blockquote o CUOI
    h.append('<blockquote>')
    h.append(p('<strong>Thông tin hàng hóa</strong>'))
    h.append('<ul>' + "".join(f'<li style="font-size: 16px; line-height: 1.6;"><strong>{k}:</strong> {v}</li>'
             for k, v in [("Tên sản phẩm", ten), ("Loại sản phẩm", "Bản Quyền Phần Mềm"),
                          ("Hãng", "Microsoft"), ("Mã sản phẩm", s["ma"])]) + '</ul>')
    h.append(p('<strong>Phiên bản phần mềm</strong>'))
    h.append('<ul>' + "".join(f'<li style="font-size: 16px; line-height: 1.6;"><strong>{k}:</strong> {v}</li>'
             for k, v in [("Hệ điều hành", "Windows 11 Pro"), ("Nền tảng", "64-bit"),
                          ("Ngôn ngữ", s["ngon_ngu"]), ("Dạng bản quyền", s["dang"])]) + '</ul>')
    h.append(p('<strong>Yêu cầu hệ thống tối thiểu</strong>'))
    h.append('<ul>' + "".join(f'<li style="font-size: 16px; line-height: 1.6;"><strong>{k}:</strong> {v}</li>'
             for k, v in YCHT) + '</ul>')
    h.append('</blockquote>')
    return "".join(h), s


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--thu", action="store_true")
    g.add_argument("--ghi", action="store_true")
    a = ap.parse_args()

    for pid in SP:
        body, s = dung(pid)
        # dash rule: chi khoi signature duoc phep co em dash
        ngoai_sig = body.replace("Sintech — Hotline", "Sintech Hotline")
        kt = {
            "gach ngang dai ngoai signature": ngoai_sig.count("—") + ngoai_sig.count("–"),
            "H2": body.count("<h2"), "H3": body.count("<h3"),
            "blockquote": body.count("<blockquote"),
            "the <style>/<script>": body.count("<style") + body.count("<script"),
            "signature TREN spec": body.find("Tư vấn cấu hình") < body.find("<blockquote"),
            "dia chi dung mau": "457 Trần Xuân Soạn, Phường Tân Hưng, Thành phố Hồ Chí Minh" in body,
            "SEO title <=61": len(s["seo_t"]) <= 61,
            "SEO meta 140-160": 140 <= len(s["seo_d"]) <= 160,
        }
        print(f"\n=== {pid} · {s['ten'][:52]}")
        print(f"    body {len(body):,} ky tu · SEO title {len(s['seo_t'])}c · meta {len(s['seo_d'])}c")
        for k, v in kt.items():
            print(f"      {k:<32} {v}")
        assert kt["gach ngang dai ngoai signature"] == 0
        assert kt["the <style>/<script>"] == 0 and kt["signature TREN spec"]
        assert kt["dia chi dung mau"] and kt["SEO title <=61"] and kt["SEO meta 140-160"]
        (OUT / f"sp_win11pro_{pid}.html").write_text(
            f'<div style="max-width:820px;margin:0 auto;padding:22px;background:#fff">{body}</div>',
            encoding="utf-8")

        if a.ghi:
            hc._request("PUT", f"/products/{pid}.json", payload={"product": {
                "id": pid, "body_html": body,
                "metafields_global_title_tag": s["seo_t"],
                "metafields_global_description_tag": s["seo_d"]}})
            print("      -> DA GHI len Haravan")
    print(f"\nPreview: {OUT}\\sp_win11pro_<id>.html")


if __name__ == "__main__":
    main()
