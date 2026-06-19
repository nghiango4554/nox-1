/* Sintech Hub — mock data (mirrors the original dashboard) */
window.SH = (function () {
  const nav = [
    { group: "Tổng quan", items: [
      { icon: "layout-dashboard", label: "Dashboard", active: true },
      { icon: "list-checks", label: "Job Center", badge: "1.5k", tone: "violet" },
    ]},
    { group: "Phân tích & đo lường", items: [
      { icon: "chart-area", label: "GA4 Analytics" },
      { icon: "search", label: "Search Console" },
      { icon: "radar", label: "Tracking Audit" },
      { icon: "square-check-big", label: "Task Center", badge: "17", tone: "amber" },
      { icon: "activity", label: "Analytics Ops" },
    ]},
    { group: "Facebook", items: [
      { icon: "plus-circle", label: "Bài mới" },
      { icon: "send", label: "Bài đã đăng" },
      { icon: "calendar-days", label: "Lịch đăng" },
    ]},
    { group: "Nội dung", items: [
      { icon: "package", label: "Content Jobs" },
      { icon: "folder-tree", label: "Collection Content" },
      { icon: "file-text", label: "Blog Content" },
      { icon: "shopping-bag", label: "SP mới" },
      { icon: "image", label: "ALT ảnh", badge: "9.7k", tone: "rose" },
    ]},
    { group: "Tối ưu & kho", collapsible: true, defaultOpen: true, subgroups: [
      { label: "SEO", icon: "shield-check", items: [
        { label: "Coverage" }, { label: "Title & Meta" }, { label: "H1 trong mô tả" },
        { label: "SP thiếu mô tả", badge: "212", tone: "amber" }, { label: "Trùng lặp" },
        { label: "Link gãy", badge: "8", tone: "rose" }, { label: "Indexability" },
        { label: "Internal links" }, { label: "Lịch sử" },
      ]},
      { label: "Haravan", icon: "shopping-bag", items: [
        { label: "Sản phẩm" }, { label: "Blog & News" }, { label: "Audit log" },
      ]},
    ]},
    { group: "Khác", items: [
      { icon: "images", label: "Thư viện ảnh" },
      { icon: "swords", label: "Đối thủ" },
    ]},
  ];

  const sp = (arr) => arr;

  const stats = [
    { id: "jobs", grad: "coral", tone: "sky", icon: "package", title: "Content jobs", value: "1550",
      status: "synced", statusTone: "sky", sub: "synced 314 · draft 1",
      spark: sp([8,10,9,12,11,14,13,16,15,18]) },
    { id: "seo", grad: "teal", tone: "teal", icon: "search", title: "SEO trang điểm kém", value: "1",
      status: "TB 81.0", statusTone: "teal", sub: "2819 trang · tốt 2751",
      spark: sp([5,4,6,3,5,2,3,2,1,1]) },
    { id: "approve", grad: "violet", tone: "violet", icon: "square-check-big", title: "Bài chờ duyệt", value: "17",
      status: "chờ duyệt", statusTone: "amber", sub: "blog 16 · content 1",
      spark: sp([3,5,4,7,6,9,8,12,14,17]) },
    { id: "haravan", grad: "blue", tone: "indigo", icon: "shopping-bag", title: "SP Haravan", value: "2584",
      status: "audit 51.5", statusTone: "indigo", sub: "điểm audit TB 51.5",
      spark: sp([20,21,20,22,23,22,24,23,25,26]) },
    { id: "alt", grad: "red", tone: "rose", icon: "image", title: "Alt coverage", value: "37.5", unit: "%",
      status: "cần sửa", statusTone: "rose", sub: "0 good · 9730 cần sửa",
      spark: sp([42,40,41,39,40,38,39,38,37,37]) },
    { id: "cwv", grad: "amber", tone: "amber", icon: "gauge", title: "CWV perf kém", value: "201",
      status: "cần fix", statusTone: "rose", sub: "4992 URL · TB 68.9",
      spark: sp([12,14,13,16,15,18,17,19,20,20]) },
  ];

  const alerts = [
    { icon: "wifi-off", tone: "rose", label: "Telegram bot down", sub: "HTTP 401" },
    { icon: "database-backup", tone: "rose", label: "Backup DB quá cũ", sub: "225h" },
    { icon: "gauge", tone: "amber", label: "201 URL CWV kém", sub: "chưa sync GitHub" },
    { icon: "git-branch", tone: "amber", label: "79 chưa commit", sub: "Git master" },
  ];

  // chart series — 7 ngày
  const days = ["T2","T3","T4","T5","T6","T7","CN"];
  const series = {
    traffic: { label: "Lượt truy cập", color: "var(--accent-from)", data: [1820,2110,1980,2460,2390,1740,1610], delta: "+12.4%", up: true },
    cwv:     { label: "Điểm CWV TB",  color: "#0ea5e9", data: [61,63,62,66,68,69,68.9], delta: "+3.1", up: true },
    index:   { label: "URL được index", color: "#8b5cf6", data: [2510,2540,2560,2590,2640,2710,2751], delta: "+9.6%", up: true },
  };

  const health = [
    { icon: "server", name: "Flask web", desc: "ứng dụng chính", tone: "emerald", state: "Up", stateTone: "emerald" },
    { icon: "bot", name: "AI provider", desc: "codex", tone: "emerald", state: "sẵn sàng", stateTone: "emerald" },
    { icon: "send", name: "Telegram bot", desc: "thông báo", tone: "rose", state: "HTTP 401", stateTone: "rose" },
    { icon: "git-branch", name: "Git (master)", desc: "↑23 · 79 chưa commit", tone: "amber", state: "lệch", stateTone: "amber" },
    { icon: "database-backup", name: "Backup DB", desc: "secrets 225h", tone: "rose", state: "225h", stateTone: "rose" },
    { icon: "layers", name: "Pillar gen", desc: "17 / 120 · 103 chờ", tone: "amber", progress: 14, stateTone: "amber" },
  ];

  const queue = [
    { type: "Blog", icon: "file-text", tone: "amber", title: "Top 10 serum cấp ẩm cho da dầu", sub: "pillar · skincare", status: "chờ duyệt", statusTone: "amber", prog: 100, when: "2 phút trước" },
    { type: "Content", icon: "package", tone: "violet", title: "Mô tả SP — Kem chống nắng Anessa", sub: "Haravan · SKU 4821", status: "đang gen", statusTone: "sky", pulse: true, prog: 64, when: "9 phút trước" },
    { type: "Blog", icon: "file-text", tone: "amber", title: "Cách chọn toner theo loại da", sub: "cluster · skincare", status: "chờ duyệt", statusTone: "amber", prog: 100, when: "21 phút trước" },
    { type: "SEO", icon: "search", tone: "emerald", title: "Audit schema FAQ + ItemList", sub: "1 collection còn thiếu", status: "cần fix", statusTone: "rose", prog: 30, when: "34 phút trước" },
    { type: "FB", icon: "send", tone: "sky", title: "Caption — Flash sale cuối tuần", sub: "Facebook · ảnh kèm", status: "đã lên lịch", statusTone: "emerald", prog: 100, when: "1 giờ trước" },
  ];

  const quick = [
    { tag: "SEO & Content", icon: "search", tone: "emerald", items: [
      { icon: "package", t: "Content jobs", s: "Viết mô tả sản phẩm" },
      { icon: "file-text", t: "Blog content", s: "Bài blog + duyệt" },
      { icon: "layers", t: "Pillar plan", s: "Gen pillar–cluster" },
      { icon: "shield-check", t: "Audit SEO", s: "Quét điểm on-page" },
    ]},
    { tag: "Facebook", icon: "thumbs-up", tone: "sky", items: [
      { icon: "plus-circle", t: "Tạo bài FB", s: "Caption + ảnh" },
      { icon: "calendar-days", t: "Lịch tuần", s: "Xem / kéo-thả lịch" },
    ]},
    { tag: "Haravan", icon: "shopping-bag", tone: "indigo", items: [
      { icon: "package", t: "Sản phẩm", s: "Catalog + audit SEO" },
      { icon: "tag", t: "Bộ sưu tập", s: "Gom nhóm + mô tả" },
    ]},
    { tag: "System", icon: "settings", tone: "slate", items: [
      { icon: "braces", t: "Health JSON", s: "Số liệu thô (debug)" },
      { icon: "database-backup", t: "Backup", s: "Chạy snapshot DB" },
    ]},
  ];

  return { nav, stats, alerts, days, series, health, queue, quick };
})();
