"""Anh Nox-1 tự tay gen lại 3 title + 3 meta cho 30 job đầu sai độ dài.
Pattern:
  - Title: 45-58c (<=61), bắt đầu Type SP, KHÔNG dùng Sintech.
  - Meta : 140-160c, M1 SPEC + XEM NGAY, M2 SETUP + THAM KHẢO NGAY, M3 GIẢI PHÁP + CHỌN NGAY.
Không filler 'bền bỉ' / 'đẹp mắt'. Đếm ký tự bằng len() (NFC).
"""
import json, sqlite3, sys, unicodedata
sys.stdout.reconfigure(encoding="utf-8")

def L(s): return len(unicodedata.normalize("NFC", s))

DATA = [
{
 "id": 69,
 "T": [
   "Chuột không dây AULA AM207 Wireless 2.4G 1600 DPI nhẹ",
   "Chuột AULA AM207 không dây 2.4G, nhẹ 55g, dễ dùng",
   "Chuột AULA AM207 không dây 5 màu cho bàn làm việc gọn",
 ],
 "M": [
   "Chuột không dây AULA AM207 Wireless 2.4G, DPI 800-1200-1600, thân nhẹ 55g cho bàn học và văn phòng gọn gàng. XEM NGAY tại Sintech với giá tốt.",
   "Setup bàn học, bàn văn phòng gọn cùng chuột AULA AM207 không dây 2.4G, 5 màu trẻ trung dễ phối phụ kiện. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Chuột AULA AM207 - giải pháp cho người cần chuột không dây 2.4G nhỏ gọn 55g, 5 màu lựa chọn dễ phối. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 70,
 "T": [
   "Máy bộ Dell Vostro 3020 SFF, Core i5-13400, 8GB, 512GB",
   "PC bộ Dell Vostro 3020 SFF i5-13400 cho doanh nghiệp",
   "Máy bộ Dell Vostro 3020 SFF i5-13400 cho văn phòng nhỏ",
 ],
 "M": [
   "Máy bộ Dell Vostro 3020 SFF chip Core i5-13400, RAM 8GB, SSD 512GB cho văn phòng, học tập và doanh nghiệp nhỏ. XEM NGAY tại Sintech với giá tốt.",
   "Setup văn phòng gọn cùng máy bộ Dell Vostro 3020 SFF, i5-13400, 8GB, 512GB SSD, mượt cho công việc đa nhiệm. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Dell Vostro 3020 SFF - giải pháp PC văn phòng cho doanh nghiệp, cấu hình i5-13400, 8GB, 512GB SSD. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 71,
 "T": [
   "Bàn Gaming chữ K màu đen mặt HDF cho góc PC gọn đẹp",
   "Bàn Gaming chữ K màu đen 1200x600mm cho setup PC",
   "Bàn Gaming chữ K màu đen, chân sắt sơn tĩnh điện",
 ],
 "M": [
   "Bàn Gaming chữ K màu đen, mặt HDF 120x60cm, chân sắt sơn tĩnh điện và lỗ đi dây sẵn cho góc PC gọn gàng tại nhà. XEM NGAY tại Sintech với giá tốt.",
   "Setup PC tại nhà cùng bàn Gaming chữ K Sintech màu đen, mặt HDF rộng, dễ bố trí gear gaming hoặc văn phòng. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Bàn Gaming chữ K Sintech - giải pháp cho game thủ và nhân viên cần bàn gọn 120x60cm, đi dây tiện. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 72,
 "T": [
   "Fan Case Ocypus Industrial Gamma F12 ARGB Đen Sync Main",
   "Fan Case Ocypus Gamma F12 ARGB Đen, PWM, Sync Main",
   "Fan Case Ocypus Gamma F12 ARGB Đen cho thùng PC gaming",
 ],
 "M": [
   "Fan Case Ocypus Industrial Gamma F12 ARGB Đen, kết nối PWM, Sync Main, thiết kế Interlocking đi dây gọn cho thùng PC gaming. XEM NGAY tại Sintech với giá tốt.",
   "Setup thùng PC gaming tông đen ARGB cùng fan Ocypus Gamma F12, hỗ trợ PWM mượt và đồng bộ LED main. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Fan Case Ocypus Gamma F12 ARGB Đen - giải pháp làm mát cho thùng máy gaming cần PWM, Sync Main. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 73,
 "T": [
   "Tản nhiệt khí Leopard KF400 RGB Đen, PWM 4PIN, đa socket",
   "Tản nhiệt khí Leopard KF400 RGB Đen cho CPU Intel/AMD",
   "Tản nhiệt khí Leopard KF400 RGB Đen cho PC gaming",
 ],
 "M": [
   "Tản nhiệt khí Leopard KF400 RGB Đen, quạt PWM 4PIN, dải tốc độ 900-2300RPM, hỗ trợ nhiều socket Intel cho PC gaming. XEM NGAY tại Sintech với giá tốt.",
   "Setup PC gaming tông đen cùng tản khí Leopard KF400 RGB - quạt PWM, LED RGB nổi bật, lắp gọn cho dàn build mới. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Leopard KF400 RGB Đen - giải pháp tản nhiệt CPU cho game thủ cần fan PWM 4PIN, RGB phối case dễ. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 74,
 "T": [
   "Tản nhiệt khí Leopard KF400 RGB Trắng, PWM 4PIN, đa socket",
   "Tản nhiệt khí Leopard KF400 RGB Trắng cho PC sáng màu",
   "Tản nhiệt khí Leopard KF400 RGB Trắng cho CPU Intel/AMD",
 ],
 "M": [
   "Tản nhiệt khí Leopard KF400 RGB Trắng, quạt PWM 4PIN, tốc độ 900-2300RPM, hỗ trợ nhiều socket Intel/AMD cho PC sáng màu. XEM NGAY tại Sintech với giá tốt.",
   "Setup PC tông trắng cùng tản nhiệt khí Leopard KF400 RGB - quạt PWM, RGB hợp setup sáng và dễ lắp đặt. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Leopard KF400 RGB Trắng - giải pháp tản CPU cho game thủ build PC sáng màu cần PWM 4PIN, RGB nổi bật. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 76,
 "T": [
   "Sạc Laptop Asus 19V 3.42A 65W đầu 5.5x2.5mm hình chữ nhật",
   "Sạc Laptop Asus 19V 3.42A 65W chính hãng cho máy Asus",
   "Adapter Asus 65W 19V 3.42A đầu tròn lớn cho laptop Asus",
 ],
 "M": [
   "Sạc Laptop Asus 19V 3.42A 65W hình chữ nhật, đầu 5.5x2.5mm, mới fullbox cho laptop Asus thay sạc cũ ổn định. XEM NGAY tại Sintech với giá tốt.",
   "Adapter Asus 65W đầu tròn lớn 5.5x2.5mm thay sạc laptop hỏng cho học sinh, dân văn phòng dùng máy Asus. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Sạc Asus 19V 3.42A 65W chữ nhật - giải pháp thay sạc laptop Asus cho học tập và làm việc hằng ngày. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 77,
 "T": [
   "Nguồn Xigmatek X-POWER III X650 600W cho PC gaming",
   "Nguồn Xigmatek X-POWER III X650 600W, +12V 540W, quạt 12cm",
   "Nguồn Xigmatek X-POWER III X650 600W cho dàn PC nâng cấp",
 ],
 "M": [
   "Nguồn Xigmatek X-POWER III X650 600W, đường +12V 540W, quạt 12cm êm, đa đầu cắm cho main, CPU, VGA, ổ lưu trữ. XEM NGAY tại Sintech với giá tốt.",
   "Build PC gaming phổ thông, nâng cấp VGA rời ổn định cùng PSU Xigmatek X-POWER III X650 600W, đầu cắm đa dạng. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Xigmatek X-POWER III X650 600W - giải pháp nguồn cho game thủ build dàn PC mới hoặc nâng VGA. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 78,
 "T": [
   "Đầu chuyển USB sang Type-C 10Gbps, sạc 120W, vỏ nhôm",
   "Đầu chuyển USB-A sang Type-C, hỗ trợ sạc 120W 20V6A",
   "Đầu chuyển USB sang Type-C, vỏ nhôm, dữ liệu 10Gbps",
 ],
 "M": [
   "Đầu chuyển USB sang Type-C, vỏ nhôm gọn, hỗ trợ sạc nhanh 120W 20V6A và dữ liệu 10Gbps cho điện thoại, máy tính bảng. XEM NGAY tại Sintech với giá tốt.",
   "Setup laptop và PC gọn gàng cùng đầu chuyển USB-A sang Type-C, sạc 120W, dữ liệu 10Gbps cho thiết bị cá nhân. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Đầu chuyển USB sang Type-C - giải pháp tận dụng cổng USB-A để sạc nhanh và truyền dữ liệu tốc độ cao. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 80,
 "T": [
   "Router Wifi 6 Mesh Ruijie RG-EW3200GX PRO, 8 anten, 3200Mbps",
   "Bộ phát Ruijie RG-EW3200GX PRO Wifi 6 Mesh cho nhà rộng",
   "Router Wifi 6 Mesh Ruijie RG-EW3200GX PRO, 2 băng tần",
 ],
 "M": [
   "Router Wifi 6 Mesh Ruijie RG-EW3200GX PRO tốc độ 3200Mbps, 8 anten, 2 băng tần, hợp nhà nhiều phòng và văn phòng đông thiết bị. XEM NGAY tại Sintech với giá tốt.",
   "Setup mạng nhà rộng, văn phòng nhiều thiết bị cùng Ruijie RG-EW3200GX PRO Wifi 6 Mesh, cổng Gigabit ổn định. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Ruijie RG-EW3200GX PRO Wifi 6 Mesh - giải pháp mạng cho gia đình, văn phòng cần phủ sóng và chịu tải. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 81,
 "T": [
   "Box SSD M.2 NVMe RAINBOWGEAR R320 USB 3.1, vỏ nhôm 4TB",
   "Box SSD M.2 PCIe/NVMe RAINBOWGEAR R320 USB 3.1 vỏ nhôm",
   "Box SSD RAINBOWGEAR R320 USB 3.1 cho M.2 NVMe tới 4TB",
 ],
 "M": [
   "Box SSD M.2 PCIe/NVMe RAINBOWGEAR R320 USB 3.1, vỏ kim loại tản nhiệt, hỗ trợ tối đa 4TB, kèm cáp Type-C - USB. XEM NGAY tại Sintech với giá tốt.",
   "Setup laptop, PC gọn gàng cùng box RAINBOWGEAR R320 - tận dụng SSD M.2 NVMe cũ thành ổ lưu trữ rời di động. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Box SSD RAINBOWGEAR R320 - giải pháp cho dân kỹ thuật cần sao lưu, chuyển dữ liệu nhanh qua chuẩn USB 3.1. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 82,
 "T": [
   "Bàn phím cơ Mechanics Darkflash G87, 98 phím, Blue Switch",
   "Bàn phím cơ Darkflash G87 có dây USB cho học tập, gaming",
   "Bàn phím cơ Mechanics Darkflash G87 cho PC, keycap ABS",
 ],
 "M": [
   "Bàn phím cơ Mechanics Darkflash G87, 98 phím, Blue Switch, keycap ABS, kết nối USB có dây cho học tập, văn phòng và chơi game. XEM NGAY tại Sintech với giá tốt.",
   "Setup PC gọn cùng bàn phím cơ Darkflash G87 - 98 phím, Blue Switch gõ rõ tay, keycap ABS dùng hằng ngày. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Mechanics Darkflash G87 - giải pháp bàn phím cơ giá tốt cho học sinh, sinh viên và game thủ phổ thông. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 84,
 "T": [
   "Chuột Gaming Lecoo MS106 có dây, 7 phím chức năng cho PC",
   "Chuột Gaming có dây Lecoo MS106 cho setup học và game",
   "Chuột quang Gaming Lecoo MS106 chống ẩm bụi, 7 phím",
 ],
 "M": [
   "Chuột Gaming có dây Lecoo MS106, 7 phím chức năng, thiết kế chống ẩm bụi cho thao tác game nhanh và bàn làm việc gọn. XEM NGAY tại Sintech với giá tốt.",
   "Setup gaming và học tập gọn cùng chuột Lecoo MS106 - thiết kế tinh tế, 7 phím lập trình, chống bụi tốt. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Chuột Lecoo MS106 - giải pháp cho học sinh, dân văn phòng và game thủ cần chuột có dây 7 phím tiện. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 86,
 "T": [
   "Tai nghe E-DRA EH416PRO có dây USB, mic đa hướng, 50mm",
   "Tai nghe chơi game E-DRA EH416PRO USB cho PC gaming",
   "Tai nghe Gaming E-DRA EH416PRO USB, mic đa hướng tiện",
 ],
 "M": [
   "Tai nghe chơi game E-DRA EH416PRO có dây USB, mic đa hướng, củ loa lớn cho game, voice chat và học online rõ tiếng. XEM NGAY tại Sintech với giá tốt.",
   "Setup PC chơi game, học online cùng tai nghe E-DRA EH416PRO - kết nối USB, mic đa hướng, dây gọn dễ dùng. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "E-DRA EH416PRO - giải pháp tai nghe gaming có dây cho game thủ, học sinh cần nghe game và đàm thoại rõ. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 87,
 "T": [
   "Tai nghe E-DRA EH416PRO Hồng có dây USB cho gaming",
   "Tai nghe chơi game E-DRA EH416PRO Hồng, mic đa hướng",
   "Tai nghe E-DRA EH416PRO Hồng USB, củ loa 50mm dễ dùng",
 ],
 "M": [
   "Tai nghe chơi game E-DRA EH416PRO Hồng, kết nối USB, mic đa hướng, củ loa 50mm cho game thủ nữ, học online và voice chat. XEM NGAY tại Sintech với giá tốt.",
   "Setup gaming sáng màu cùng E-DRA EH416PRO Hồng - dây 1.6m, USB, mic đa hướng dùng cho PC chơi game hằng ngày. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "E-DRA EH416PRO Hồng - giải pháp tai nghe gaming dễ phối setup hồng pastel, hợp game thủ nữ và bàn học. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 88,
 "T": [
   "Cáp HDMI 3m dây dẹp Full HD cho PC, Tivi, Projector",
   "Cáp HDMI 3m dây dẹp Full HD, mềm mỏng, đi dây gọn",
   "Cáp HDMI 3m dây dẹp Full HD cho bàn làm việc, giải trí",
 ],
 "M": [
   "Cáp HDMI 3m dây dẹp Full HD kết nối PC, Tivi, Projector trực tiếp, dễ đi dây gọn cho bàn làm việc và phòng giải trí. XEM NGAY tại Sintech với giá tốt.",
   "Setup phòng làm việc, phòng họp gọn gàng cùng cáp HDMI 3m dây dẹp Full HD, kết nối nhiều thiết bị tiện lợi. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Cáp HDMI 3m dây dẹp Full HD - giải pháp đi dây phẳng cho PC, Tivi, Projector trong nhà và văn phòng. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 89,
 "T": [
   "Tản nhiệt nước AIO LeoPard TK1 240mm RGB Fixed Đen",
   "AIO LeoPard TK1 240mm RGB Fixed Đen cho PC gaming",
   "Tản nước LeoPard TK1 240mm RGB Đen, fan 1700RPM",
 ],
 "M": [
   "Tản nhiệt nước AIO LeoPard TK1 240mm RGB Fixed Đen, fan 1700RPM, hỗ trợ nhiều socket cho PC gaming gọn và mát. XEM NGAY tại Sintech với giá tốt.",
   "Build PC gaming tông đen cùng AIO LeoPard TK1 240mm RGB Fixed - kiểm soát nhiệt CPU và LED đồng bộ thẩm mỹ. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "LeoPard TK1 240mm RGB Đen - giải pháp tản nước cho game thủ build PC tông đen cần làm mát ổn định. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 90,
 "T": [
   "Chuột Gaming Aula S12 PRO Đen có dây, RGB, 8 nút, DPI cao",
   "Chuột Gaming Aula S12 PRO Đen có dây cho PC chơi game",
   "Chuột Aula S12 PRO Đen có dây USB, LED RGB cho gaming",
 ],
 "M": [
   "Chuột Gaming Aula S12 PRO Đen có dây USB 2.0, DPI nhiều mức tới 12800, LED RGB và 8 nút cho thao tác game gọn. XEM NGAY tại Sintech với giá tốt.",
   "Setup PC gaming tông đen cùng chuột Aula S12 PRO - phản hồi 1000Hz, 8 nút lập trình, ôm tay khi chơi lâu. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Aula S12 PRO Đen - giải pháp chuột gaming có dây cho game thủ cần DPI cao, RGB và 8 nút linh hoạt. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 91,
 "T": [
   "Chuột Gaming Aula S12 PRO Trắng Xám có dây, RGB, 8 nút",
   "Chuột Aula S12 PRO Trắng Xám có dây USB cho setup sáng",
   "Chuột Gaming Aula S12 PRO Trắng Xám DPI cao, dây 1.5m",
 ],
 "M": [
   "Chuột Gaming Aula S12 PRO Trắng Xám có dây USB 2.0, DPI cao tới 12800, LED RGB và 8 nút cho setup gaming sáng màu. XEM NGAY tại Sintech với giá tốt.",
   "Setup PC tông trắng cùng chuột Aula S12 PRO Trắng Xám - phản hồi 1000Hz, 8 nút, dây 1.5m, ôm tay khi chơi. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Aula S12 PRO Trắng Xám - giải pháp chuột gaming có dây cho game thủ build PC sáng cần DPI cao và RGB. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 93,
 "T": [
   "Chuột Gaming Lecoo MS108 có dây, 7 phím chức năng, gọn",
   "Chuột quang Gaming Lecoo MS108 chống tia nước, bụi bẩn",
   "Chuột Gaming Lecoo MS108 cho học tập, văn phòng, gaming",
 ],
 "M": [
   "Chuột Gaming có dây Lecoo MS108 thiết kế gọn, chống tia nước và bụi bẩn, 7 phím chức năng cho thao tác game và làm việc. XEM NGAY tại Sintech với giá tốt.",
   "Setup học tập, gaming gọn cùng chuột Lecoo MS108 - cảm biến quang, 7 phím, dây USB phù hợp dùng hằng ngày. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Lecoo MS108 - giải pháp chuột Gaming có dây cho học sinh, sinh viên và game thủ cần 7 phím chức năng. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 95,
 "T": [
   "Tản nhiệt nước AIO ID Cooling DashFlow 240, TDP 220W",
   "AIO ID Cooling DashFlow 240 cho CPU Intel Gen 12/13, AM5",
   "Tản nước ID Cooling DashFlow 240 cho PC gaming gọn",
 ],
 "M": [
   "Tản nhiệt nước AIO ID Cooling DashFlow 240, TDP 220W, pump mặt đồng lớn, LED trắng, hỗ trợ Intel Gen 12/13 và AM5. XEM NGAY tại Sintech với giá tốt.",
   "Build PC gaming hiệu năng cùng AIO ID Cooling DashFlow 240 - kiểm soát nhiệt CPU và bơm trắng tinh tế. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "ID Cooling DashFlow 240 - giải pháp tản nước AIO cho game thủ và dân kỹ thuật build PC mới. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 96,
 "T": [
   "AIO Ocypus Delta L24 BK ARGB V2 Đen, fan 120mm, đa socket",
   "Tản nhiệt nước Ocypus Delta L24 BK ARGB V2 Đen 240mm",
   "Ocypus Delta L24 BK ARGB V2 Đen cho PC gaming tông đen",
 ],
 "M": [
   "Tản nhiệt nước AIO Ocypus Delta L24 BK ARGB V2 Đen, fan 120mm, LED ARGB, hỗ trợ AM4/AM5, LGA 1700/1851 cho PC gaming. XEM NGAY tại Sintech với giá tốt.",
   "Build PC gaming tông đen ARGB cùng AIO Ocypus Delta L24 BK V2 - bơm êm, fan mạnh, LED đồng bộ thẩm mỹ. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Ocypus Delta L24 BK ARGB V2 Đen - giải pháp tản nước cho game thủ build PC đen cần làm mát ổn. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 97,
 "T": [
   "AIO Ocypus Delta L24 BK ARGB V2 Trắng, fan 120mm, đa socket",
   "Tản nhiệt nước Ocypus Delta L24 BK ARGB V2 Trắng 240mm",
   "Ocypus Delta L24 BK ARGB V2 Trắng cho PC gaming sáng màu",
 ],
 "M": [
   "Tản nhiệt nước AIO Ocypus Delta L24 BK ARGB V2 Trắng, fan 120mm, LED ARGB, hỗ trợ AM4/AM5, LGA 1700/1851 cho PC sáng. XEM NGAY tại Sintech với giá tốt.",
   "Build PC gaming tông trắng ARGB cùng AIO Ocypus Delta L24 BK V2 - bơm êm, fan mạnh, LED đồng bộ thẩm mỹ. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Ocypus Delta L24 BK ARGB V2 Trắng - giải pháp tản nước cho game thủ build PC tông sáng cần mát ổn. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 98,
 "T": [
   "Ghế Gaming E-DRA DIGNITY EGC234 da cao cấp, kê tay 1D",
   "Ghế Gaming E-DRA DIGNITY EGC234 cho góc PC gaming",
   "Ghế chơi game E-DRA DIGNITY EGC234 đệm mút khung kim loại",
 ],
 "M": [
   "Ghế Gaming E-DRA DIGNITY EGC234 da cao cấp, kê tay 1D, đệm mút và bệ bướm linh hoạt cho góc chơi game tại nhà. XEM NGAY tại Sintech với giá tốt.",
   "Setup góc chơi game gọn cùng ghế E-DRA DIGNITY EGC234 - khung kim loại, bánh xe êm, ngồi thoải mái. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "E-DRA DIGNITY EGC234 - giải pháp ghế Gaming giá tốt cho game thủ cần ngồi lâu và bàn làm việc. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 99,
 "T": [
   "Tay cầm Machenike G3S Dual-mode Trắng/Đen, RGB, 600mAh",
   "Tay cầm Machenike G3S Dual-mode cho PC, Android, Switch",
   "Tay cầm Machenike G3S Dual-mode 2.4G và có dây tiện dụng",
 ],
 "M": [
   "Tay cầm Machenike G3S Dual-mode Trắng/Đen hỗ trợ có dây và 2.4G Wireless, RGB, pin 600mAh cho PC, Android, Switch. XEM NGAY tại Sintech với giá tốt.",
   "Setup giải trí gia đình cùng tay cầm Machenike G3S Dual-mode - 2.4G, có dây, dùng cho nhiều thiết bị chơi game. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Machenike G3S Dual-mode - giải pháp tay cầm game cho học sinh, sinh viên dùng PC, Android và Switch. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 100,
 "T": [
   "Tay cầm Machenike G5 Pro Tri-mode, pin 600mAh, RGB",
   "Tay cầm Machenike G5 Pro Tri-mode cho PC, Android, Switch",
   "Tay cầm Machenike G5 Pro Tri-mode kết nối linh hoạt",
 ],
 "M": [
   "Tay cầm Machenike G5 Pro Tri-mode hỗ trợ có dây, 2.4G Wireless, pin 600mAh, RGB cho PC, laptop, Android và Nintendo Switch. XEM NGAY tại Sintech với giá tốt.",
   "Setup giải trí đa thiết bị cùng tay cầm Machenike G5 Pro Tri-mode - thân gọn 236g, RGB nổi bật, mang theo tiện. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Machenike G5 Pro Tri-mode - giải pháp tay cầm game cho game thủ cần kết nối linh hoạt nhiều thiết bị. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 101,
 "T": [
   "Combo phím chuột Simetech KM-120 LED RGB cho văn phòng",
   "Combo phím chuột có dây Simetech KM-120 LED RGB gọn đẹp",
   "Phím chuột văn phòng Simetech KM-120 LED RGB cho PC",
 ],
 "M": [
   "Combo phím chuột Simetech KM-120 LED RGB có dây, gọn dễ dùng cho bàn làm việc, học tập và PC văn phòng hằng ngày. XEM NGAY tại Sintech với giá tốt.",
   "Setup bàn làm việc, học tập gọn cùng combo Simetech KM-120 LED RGB - phím chuột có dây, thao tác ổn định. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Simetech KM-120 LED RGB - giải pháp combo phím chuột giá tốt cho học sinh, dân văn phòng dùng Windows, macOS. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 102,
 "T": [
   "Tản nhiệt khí Ocypus Delta A40 BK ARGB Trắng, TDP 220W",
   "Tản nhiệt khí Ocypus Delta A40 BK ARGB Trắng cho PC sáng",
   "Tản khí Ocypus Delta A40 BK ARGB Trắng, ARGB, đa socket",
 ],
 "M": [
   "Tản nhiệt khí Ocypus Delta A40 BK ARGB Trắng, quạt 120mm, TDP 220W, LED ARGB, hỗ trợ Intel/AMD cho PC gaming sáng màu. XEM NGAY tại Sintech với giá tốt.",
   "Build PC gaming tông trắng cùng tản khí Ocypus Delta A40 BK ARGB - quạt mạnh, ARGB và lắp gọn cho dàn mới. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Ocypus Delta A40 BK ARGB Trắng - giải pháp tản khí cho game thủ build PC sáng màu cần TDP 220W. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 103,
 "T": [
   "Tản nhiệt khí Ocypus Delta A40 BK ARGB Đen, TDP 220W",
   "Tản nhiệt khí Ocypus Delta A40 BK ARGB Đen cho PC gaming",
   "Tản khí Ocypus Delta A40 BK ARGB Đen, ARGB, đa socket",
 ],
 "M": [
   "Tản nhiệt khí Ocypus Delta A40 BK ARGB Đen, quạt 120mm, TDP 220W, LED ARGB, hỗ trợ Intel/AMD cho PC gaming tông đen. XEM NGAY tại Sintech với giá tốt.",
   "Build PC gaming tông đen cùng tản khí Ocypus Delta A40 BK ARGB - quạt mạnh, ARGB và lắp gọn cho dàn mới. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "Ocypus Delta A40 BK ARGB Đen - giải pháp tản khí cho game thủ build PC đen cần TDP 220W và ARGB. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
{
 "id": 105,
 "T": [
   "Chuột có dây E-DRA EM606 USB LED, 1000 DPI cho văn phòng",
   "Chuột E-DRA EM606 có dây USB LED cho học tập, văn phòng",
   "Chuột văn phòng E-DRA EM606 USB LED, 1000 DPI gọn nhẹ",
 ],
 "M": [
   "Chuột có dây E-DRA EM606 USB LED, độ phân giải 1000 DPI cho văn phòng, học tập và PC làm việc gọn gàng hằng ngày. XEM NGAY tại Sintech với giá tốt.",
   "Setup bàn học, bàn văn phòng gọn cùng chuột E-DRA EM606 - dây USB 2.0, 1000 DPI, thao tác ổn định mỗi ngày. THAM KHẢO NGAY tại Sintech với giá ưu đãi.",
   "E-DRA EM606 - giải pháp chuột văn phòng có dây giá tốt cho học sinh, sinh viên và nhân viên văn phòng. CHỌN NGAY mẫu phù hợp tại Sintech với giá tốt.",
 ],
},
]

# Validate
def validate(data):
    errs = []
    for item in data:
        for i, t in enumerate(item["T"]):
            l = L(t)
            if l < 45 or l > 61:
                errs.append((item["id"], "T", i+1, l, t))
            if "Sintech" in t:
                errs.append((item["id"], "T-has-Sintech", i+1, l, t))
        for i, m in enumerate(item["M"]):
            l = L(m)
            if l < 140 or l > 160:
                errs.append((item["id"], "M", i+1, l, m))
        # filler check
        for src in item["T"] + item["M"]:
            low = src.lower()
            if "bền bỉ" in low or "đẹp mắt" in low:
                errs.append((item["id"], "filler", "?", L(src), src))
    return errs

errs = validate(DATA)
print(f"Items: {len(DATA)} | Errors: {len(errs)}")
for e in errs:
    print(f"  #{e[0]} {e[1]}{e[2]} len={e[3]} | {e[4][:80]}")

if errs:
    sys.exit(1)

# Apply nếu pass + có flag --apply
if "--apply" in sys.argv:
    DB = r"C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub\data\posts.db"
    con = sqlite3.connect(DB)
    cur = con.cursor()
    n = 0
    from datetime import datetime
    now = datetime.now().isoformat(timespec="seconds")
    for item in DATA:
        cur.execute(
            "UPDATE content_jobs SET ai_titles_json=?, ai_metas_json=?, updated_at=? WHERE id=? AND status='draft'",
            (json.dumps(item["T"], ensure_ascii=False), json.dumps(item["M"], ensure_ascii=False), now, item["id"])
        )
        if cur.rowcount:
            n += 1
            print(f"  ✓ #{item['id']} updated")
        else:
            print(f"  ✗ #{item['id']} skip (no match draft)")
    con.commit()
    con.close()
    print(f"\nApplied: {n}/{len(DATA)} jobs.")
else:
    print("\n✓ All passed validation. Run with --apply to UPDATE DB.")
