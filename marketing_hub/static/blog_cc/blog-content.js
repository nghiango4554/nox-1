/* ============================================================
   Blog SEO Command Center — vanilla render + interactions
   No framework. Renders from window.SH (nav) + window.SHB (roadmap).
   Icons hydrate from window.SintechIcons (lib/).
   ------------------------------------------------------------
   Sections: icon hydrate · sidebar · topbar · KPI header ·
   quick filters · tabs · Queue · Kanban · Calendar ·
   KPI Monitor · Import/Settings · detail Drawer.
   ============================================================ */
(function () {
  "use strict";
  var SH = window.SH, SHB = window.SHB, ICONS = window.SintechIcons || {};

  /* ---------- helpers ---------- */
  function ic(name, cls, st) {
    var p = ICONS[name] || "";
    return '<span class="ic' + (cls ? " " + cls : "") + '"' + (st ? ' style="' + st + '"' : "") + ' aria-hidden="true">' +
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + p + "</svg></span>";
  }
  var esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  var band = (s) => s >= 80 ? "good" : s >= 65 ? "ok" : "bad";
  var bandColor = (s) => s >= 80 ? "#1ab394" : s >= 65 ? "#f59e0b" : "#ef4444";

  /* ---------- state ---------- */
  var state = { tab: "queue", filters: new Set(), sel: null };

  /* ---------- sidebar (from SH.nav) ---------- */
  function navFlat(g) {
    return '<div><div class="sb-group-label">' + g.group + "</div>" + g.items.map(function (it) {
      var active = !!it.active;
      return '<a href="' + (it.url || "#") + '" class="nav-item' + (active ? " active" : "") + '" data-tone="' + (it.tone || "slate") + '">' +
        ic(it.icon) + "<span>" + it.label + "</span>" + (it.badge ? '<span class="nav-badge">' + it.badge + "</span>" : "") + "</a>";
    }).join("") + "</div>";
  }
  function navCollapsible(g) {
    var subs = g.subgroups.map(function (sg) {
      var items = sg.items.map(function (it) {
        return '<button class="nav-sub" data-tone="' + (it.tone || "slate") + '"><span>' + it.label + "</span>" + (it.badge ? '<span class="nb">' + it.badge + "</span>" : "") + "</button>";
      }).join("");
      return '<div><button class="nav-item" style="padding:8px 10px" data-collapse>' + ic(sg.icon, "", "font-size:16px") +
        '<span style="font-size:13px">' + sg.label + "</span>" + ic("chevron-right", "nav-chevron") + "</button>" +
        '<div class="nav-children"><div class="nav-children-in">' + items + "</div></div></div>";
    }).join("");
    return '<div><button class="nav-item" data-collapse>' + ic("boxes") + "<span>" + g.group + "</span>" + ic("chevron-right", "nav-chevron") + "</button>" +
      '<div class="nav-children"><div class="nav-children-in">' + subs + "</div></div></div>";
  }
  function sidebar() {
    var groups = SH.nav.map(function (g) { return g.collapsible ? navCollapsible(g) : navFlat(g); }).join("");
    return '<aside class="sidebar"><div class="brand"><div class="brand-logo">' + ic("hexagon") + "</div>" +
      '<div><div class="brand-name">Sintech Hub</div><div class="brand-sub">by Nox-1</div></div></div>' +
      '<div class="sb-search">' + ic("search") + "<span>Tìm bài / SP / URL…</span><kbd>⌘K</kbd></div>" +
      '<nav class="sb-scroll">' + groups + "</nav>" +
      '<div class="sb-foot"><div class="avatar">NX</div><div style="min-width:0"><div style="font-size:13px;font-weight:700">Nox Admin</div>' +
      '<div style="font-size:11.5px;color:var(--ink-3);font-weight:600">Gói Pro · 1 seat</div></div>' +
      ic("chevrons-up-down", "", "margin-left:auto;color:var(--ink-3);font-size:16px") + "</div></aside>";
  }
  function topbar() {
    return '<header class="topbar"><div class="crumb">' + ic("newspaper", "", "color:var(--accent-ink)") +
      "<span>Nội dung</span>" + ic("chevron-right") + "<b>Blog SEO Command Center</b></div>" +
      '<div class="top-actions"><button class="icon-btn" aria-label="Thông báo">' + ic("bell") + '<span class="dot"></span></button>' +
      '<button class="btn-primary">' + ic("plus") + "Bài mới</button></div></header>";
  }
  function chatFab() { return '<button class="nox-fab" aria-label="Trợ lý Nox-1">' + ic("message-circle-heart") + '<span class="ping">2</span></button>'; }

  /* ---------- filtering ---------- */
  function inWeek(r) { var p = r.dDraft.split("/"), v = p[1] * 31 + (+p[0]); return v >= 6 * 31 + 16 && v <= 6 * 31 + 23; }
  function filtered() {
    var f = state.filters;
    var pri = ["A1", "A2", "A3"].filter((p) => f.has(p));
    var clu = SHB.clusters.filter((c) => f.has(c));
    return SHB.items.filter((r) =>
      (pri.length === 0 || pri.includes(r.pri)) &&
      (clu.length === 0 || clu.includes(r.cluster)) &&
      (!f.has("overdue") || r.overdue) &&
      (!f.has("noowner") || !r.owner) &&
      (!f.has("thisweek") || inWeek(r)));
  }

  /* ---------- KPI header ---------- */
  function kpiHeader() {
    var I = SHB.items, n = (fn) => I.filter(fn).length;
    var tiles = [
      ["all", I.length, "Tổng roadmap", "coral", "list-checks"],
      ["A1", n((x) => x.pri === "A1"), "Ưu tiên A1", "rose", "flame"],
      ["A2", n((x) => x.pri === "A2"), "Ưu tiên A2", "amber", "chevrons-up"],
      ["writing", n((x) => x.status === "writing"), "Đang viết", "violet", "pen-line"],
      ["seo_review", n((x) => x.status === "seo_review"), "Đang review", "indigo", "search-check"],
      ["ready_publish", n((x) => x.status === "ready_publish"), "Sẵn sàng đăng", "teal", "rocket"],
      ["published", n((x) => x.status.indexOf("publish") === 0 || x.status.indexOf("monitor") === 0), "Đã đăng", "teal", "circle-check-big"],
      ["overdue", n((x) => x.overdue), "Quá hạn", "rose", "alarm-clock"],
    ];
    return '<div class="bc-kpis">' + tiles.map((t) =>
      '<div class="bc-kpi" data-tone="' + t[3] + '" data-kpi="' + t[0] + '"><span class="ico">' + ic(t[4]) + "</span>" +
      '<div class="v">' + t[1] + '</div><div class="l">' + t[2] + "</div></div>").join("") + "</div>";
  }

  /* ---------- quick filters ---------- */
  function quickFilters() {
    var I = SHB.items;
    var c = { A1: I.filter((x) => x.pri === "A1").length, A2: I.filter((x) => x.pri === "A2").length,
      overdue: I.filter((x) => x.overdue).length, noowner: I.filter((x) => !x.owner).length, thisweek: I.filter(inWeek).length };
    var clusterIcons = { "Build PC": "cpu", "Linh kiện cũ": "memory-stick", "Phần mềm bản quyền": "code",
      "Dịch vụ Quận 7": "map-pin", "Kỹ thuật/Gaming hỗ trợ": "gamepad-2" };
    var chips = [["A1", "A1", "flame"], ["A2", "A2", "chevrons-up"]];
    (SHB.clusters || []).forEach(function (cl) { c[cl] = I.filter((x) => x.cluster === cl).length; chips.push([cl, cl, clusterIcons[cl] || "tag"]); });
    chips.push(["overdue", "Quá hạn", "alarm-clock"], ["noowner", "Chưa giao", "user-x"], ["thisweek", "Tuần này", "calendar-clock"]);
    return '<div class="qfilters"><span class="qf-label">Lọc nhanh</span>' + chips.map((c2) =>
      '<button class="qf' + (state.filters.has(c2[0]) ? " on" : "") + '" data-filter="' + c2[0] + '">' + ic(c2[2]) + c2[1] +
      (c[c2[0]] != null ? '<span class="qn">' + c[c2[0]] + "</span>" : "") + "</button>").join("") + "</div>";
  }

  /* ---------- tabs ---------- */
  function tabsBar(rows) {
    var tabs = [["queue", "Queue", "table-2", rows.length], ["kanban", "Kanban", "columns-3"], ["calendar", "Calendar", "calendar-days"],
      ["kpi", "KPI Monitor", "line-chart"], ["import", "Import / Settings", "settings-2"]];
    return '<div class="bc-tabs">' + tabs.map((t) =>
      '<button class="bc-tab' + (state.tab === t[0] ? " on" : "") + '" data-tab="' + t[0] + '">' + ic(t[2]) + t[1] +
      (t[3] != null ? '<span class="tc">' + t[3] + "</span>" : "") + "</button>").join("") + "</div>";
  }

  /* ---------- SEO ring ---------- */
  function seoRing(score) {
    var r = 11, c = 2 * Math.PI * r, off = c * (1 - score / 100);
    return '<span class="seo-mini"><svg class="ring" viewBox="0 0 30 30">' +
      '<circle cx="15" cy="15" r="' + r + '" fill="none" stroke="var(--line)" stroke-width="3.5"></circle>' +
      '<circle cx="15" cy="15" r="' + r + '" fill="none" stroke="' + bandColor(score) + '" stroke-width="3.5" stroke-linecap="round" stroke-dasharray="' + c + '" stroke-dashoffset="' + off + '" transform="rotate(-90 15 15)"></circle>' +
      '</svg><b style="color:' + bandColor(score) + '">' + score + "</b></span>";
  }
  function ownerCell(o) {
    if (!o) return '<span class="owner-none">' + ic("circle-help") + "Chưa giao</span>";
    return '<span class="owner-chip"><span class="owner-av">' + o.slice(0, 2).toUpperCase() + "</span>" + o + "</span>";
  }

  /* ---------- Queue ---------- */
  function queueTab(rows) {
    var SM = SHB.statusMeta;
    var body = rows.map(function (r) {
      return '<tr class="clickable" data-row="' + SHB.priTone[r.pri] + '" data-id="' + r.id + '">' +
        '<td><span class="t-num">' + r.id.replace("BLOG-", "#") + "</span></td>" +
        '<td><span class="pill" data-tone="' + SHB.priTone[r.pri] + '">' + r.pri + "</span></td>" +
        '<td><span class="t-num">W' + r.week + "</span></td><td><span class=\"t-num\">P" + r.phase + "</span></td>" +
        '<td><span class="pill" data-tone="' + SHB.clusterTone[r.cluster] + '">' + r.cluster + "</span></td>" +
        '<td class="cell-title"><div class="ct">' + esc(r.title) + '</div><div class="ck">⌕ ' + r.kw + "</div></td>" +
        '<td><span style="font-size:11.5px;font-weight:700;color:var(--ink-2)">' + r.intent + "</span></td>" +
        '<td><span class="pill" data-tone="' + SHB.funnelTone[r.funnel] + '">' + r.funnel + "</span></td>" +
        "<td>" + seoRing(r.seo) + "</td>" +
        '<td><span class="impact-pip ' + r.impact + '"><i></i>' + r.impact + "</span></td>" +
        '<td><span class="pill dotty' + (r.status === "writing" || r.status.indexOf("monitor") === 0 ? " pulse" : "") + '" data-tone="' + SM[r.status].tone + '">' + SM[r.status].label + "</span></td>" +
        "<td>" + ownerCell(r.owner) + "</td>" +
        '<td><span class="dl' + (r.overdue ? " over" : "") + '">' + r.dDraft + "</span></td>" +
        '<td><span class="dl">' + r.dPub + "</span></td>" +
        '<td><span class="next-act" title="' + esc(r.next) + '">' + esc(r.next) + "</span></td></tr>";
    }).join("");
    return '<div class="dtable-wrap"><div class="dtable-top"><h3>' + ic("table-2") + "Hàng đợi công việc</h3>" +
      '<div class="sec-meta" style="margin-left:auto">' + ic("list") + rows.length + " bài · click 1 dòng để mở chi tiết</div></div>" +
      '<div class="dtable-scroll"><table class="dtable" style="min-width:1240px"><thead><tr>' +
      "<th>ID</th><th>Ưu tiên</th><th>Tuần</th><th>Phase</th><th>Cluster</th><th>Tiêu đề</th><th>Intent</th><th>Funnel</th><th>SEO</th><th>Impact</th><th>Trạng thái</th><th>Owner</th><th>DL draft</th><th>DL publish</th><th>Next action</th>" +
      "</tr></thead><tbody>" + (body || '<tr><td colspan="15" style="text-align:center;padding:30px;color:var(--ink-3);font-weight:600">Không có bài nào khớp bộ lọc.</td></tr>') + "</tbody></table></div></div>";
  }

  /* ---------- Kanban ---------- */
  function kanbanTab(rows) {
    var SM = SHB.statusMeta, cols = SHB.kanbanCols, byCol = {};
    cols.forEach((c) => (byCol[c] = []));
    rows.forEach((r) => { var c = SM[r.status].col; if (byCol[c]) byCol[c].push(r); });
    var wip = { Writing: 5, "SEO Review": 5 };
    var tone = { Backlog: "slate", "Brief Ready": "sky", Writing: "violet", "Image Needed": "amber", "SEO Review": "indigo", "Ready Publish": "teal", Published: "teal", Monitor: "sky", "Refresh Needed": "rose" };
    return '<div class="kanban">' + cols.map(function (c) {
      var list = byCol[c], warn = wip[c] && list.length > wip[c];
      return '<div class="kcol' + (warn ? " wip-warn" : "") + '" data-tone="' + tone[c] + '"><div class="kcol-head"><span class="kcol-dot"></span><h4>' + c + '</h4><span class="kc">' + list.length + "</span></div>" +
        (warn ? '<div class="wip-flag">' + ic("triangle-alert") + "WIP vượt " + wip[c] + " — cần giải phóng</div>" : "") +
        '<div class="kcards">' + list.map(function (r) {
          return '<div class="kcard" data-tone="' + SHB.priTone[r.pri] + '" data-id="' + r.id + '"><div class="kcard-top">' +
            '<span class="kid">' + r.id.replace("BLOG-", "#") + '</span><span class="pill" data-tone="' + SHB.priTone[r.pri] + '" style="font-size:10px">' + r.pri + "</span>" +
            '<span class="pill" data-tone="' + SHB.clusterTone[r.cluster] + '" style="font-size:10px;margin-left:auto">' + r.cluster + "</span></div>" +
            '<div class="ktitle">' + esc(r.title) + '</div><div class="kcard-foot"><span class="dl' + (r.overdue ? " over" : "") + '">' + r.dPub + "</span>" +
            (r.owner ? '<span class="owner-av" title="' + r.owner + '">' + r.owner.slice(0, 2).toUpperCase() + "</span>" : ic("circle-help", "", "margin-left:auto;color:#be123c;font-size:15px")) + "</div></div>";
        }).join("") + "</div></div>";
    }).join("") + "</div>";
  }

  /* ---------- Calendar ---------- */
  function calendarTab(rows) {
    var weeks = {};
    rows.forEach((r) => { (weeks[r.week] = weeks[r.week] || []).push(r); });
    var wk = Object.keys(weeks).map(Number).sort((a, b) => a - b);
    var phase = { 1: "Phase 1 · Nền tảng", 2: "Phase 2 · Mở rộng", 3: "Phase 3 · Chiều sâu", 4: "Phase 4 · Phủ & refresh" };
    return '<div class="cal-grid">' + wk.map(function (w) {
      var list = weeks[w].slice().sort((a, b) => a.dPub.localeCompare(b.dPub)), ph = list[0].phase;
      return '<div class="cal-week"><div class="cal-wlabel"><span class="wn">W' + w + '</span><span class="wp">' + phase[ph] + "</span></div><div class=\"cal-lane\">" +
        list.map(function (r) {
          var fl = r.overdue ? ["over", "Quá hạn"] : !r.owner ? ["noowner", "Chưa giao"] : r.status === "backlog" ? ["draft", "Chưa có brief"] :
            (r.status.indexOf("publish") === 0 || r.status.indexOf("monitor") === 0) ? ["pub", "Đã đăng"] : ["draft", "Lên kế hoạch"];
          return '<div class="cal-event" data-tone="' + SHB.clusterTone[r.cluster] + '" data-id="' + r.id + '"><span class="ce-bar"></span><div style="min-width:0">' +
            '<div class="ce-t">' + esc(r.title) + '</div><div class="ce-m"><span>' + r.id.replace("BLOG-", "#") + "</span>·<span>đăng " + r.dPub + '</span><span class="ce-flag ' + fl[0] + '">' + fl[1] + "</span></div></div></div>";
        }).join("") + "</div></div>";
    }).join("") + "</div>";
  }

  /* ---------- KPI Monitor ---------- */
  function kpiTab(rows) {
    var pub = rows.filter((r) => r.kpi.d14);
    var cell = (k) => k ? '<div class="kw-cell"><span class="kv">' + k.clicks.toLocaleString("vi-VN") + '</span><span class="kl">clicks · CTR ' + k.ctr + "%</span></div>" : '<span class="nodata">' + ic("clock") + "chưa có</span>";
    var body = pub.map(function (r) {
      return '<tr data-row="teal" class="clickable" data-id="' + r.id + '"><td><span class="t-num">' + r.id.replace("BLOG-", "#") + "</span></td>" +
        '<td class="cell-title"><div class="ct">' + esc(r.title) + "</div></td><td><span class=\"dl\">" + r.dPub + "</span></td>" +
        "<td>" + cell(r.kpi.d14) + "</td><td>" + cell(r.kpi.d28) + "</td><td>" + cell(r.kpi.d60) + "</td>" +
        '<td><span class="scoreband good" style="background:' + bandColor(r.seo) + '">' + r.kpi.d14.pos + '</span></td><td><span class="win-query">' + r.kw + "</span></td>" +
        '<td><span class="next-act" title="' + esc(r.next) + '">' + esc(r.next) + "</span></td></tr>";
    }).join("");
    return '<div class="dtable-wrap"><div class="dtable-top"><h3>' + ic("line-chart") + "KPI Monitor — sau đăng 14 / 28 / 60 ngày</h3>" +
      '<div class="sec-meta" style="margin-left:auto">' + ic("database") + "nguồn: GSC DB (cache) · " + pub.length + " bài đã đăng</div></div>" +
      '<div class="dtable-scroll"><table class="dtable" style="min-width:1100px"><thead><tr><th>ID</th><th>Tiêu đề</th><th>Đăng</th><th>14 ngày</th><th>28 ngày</th><th>60 ngày</th><th>Vị trí TB</th><th>Winning query</th><th>Next action</th></tr></thead><tbody>' +
      (body || '<tr><td colspan="9" style="text-align:center;padding:30px;color:var(--ink-3);font-weight:600">Chưa có bài nào được đăng trong bộ lọc này.</td></tr>') + "</tbody></table></div></div>";
  }

  /* ---------- Import / Settings ---------- */
  function importTab() {
    var sets = [
      ["git-branch", "violet", "Lọc nguồn dữ liệu", "Chỉ hiển thị bài có source = 'roadmap'", true],
      ["repeat", "sky", "Import idempotent", "Chạy lại không tạo bản trùng (key: roadmap_id)", true],
      ["shield-alert", "rose", "Chặn auto-publish Haravan", "Sync chỉ chạy khi bấm tay + confirm phrase", true],
      ["calendar-off", "amber", "Scheduler nền", "Không tự chạy job theo lịch", false],
    ];
    return '<div class="imp-grid"><div class="panel" style="gap:18px"><div class="panel-head">' + ic("upload", "lead") + "<h3>Import roadmap từ Excel</h3></div>" +
      '<div class="imp-drop"><div class="di">' + ic("file-spreadsheet") + "</div><h3>Kéo thả file Excel kế hoạch SEO</h3>" +
      "<p>Nguồn: <code>ke_hoach_blog_seo_sintech_gsc_16m_3m.xlsx</code><br>Chỉ import 40 bài roadmap · idempotent · update theo roadmap_id.</p>" +
      '<div style="display:flex;gap:10px"><button class="btn-soft">' + ic("upload") + "Chọn file &amp; import</button><button class=\"btn-line\">" + ic("download") + "Tải import report (CSV)</button></div></div>" +
      '<div style="display:flex;gap:12px;flex-wrap:wrap"><span class="fl-chip" data-tone="teal">' + ic("circle-check") + "Lần import gần nhất: 40 bài</span>" +
      '<span class="fl-chip" data-tone="sky">' + ic("clock") + "02/05/2026 09:14</span><span class=\"fl-chip\" data-tone=\"slate\">" + ic("copy-check") + "0 trùng lặp</span></div></div>" +
      '<div class="panel" style="gap:6px"><div class="panel-head">' + ic("settings-2", "lead") + "<h3>Cài đặt an toàn</h3></div>" +
      sets.map((s) => '<div class="set-row"><div class="si" data-tone="' + s[1] + '">' + ic(s[0]) + '</div><div style="min-width:0"><div class="st">' + s[2] + '</div><div class="sd">' + s[3] + "</div></div>" +
        '<div class="sw"><span class="fl-toggle' + (s[4] ? " on" : "") + '" style="pointer-events:none"><span class="fl-switch"><i></i></span></span></div></div>').join("") + "</div></div>";
  }

  /* ---------- Drawer ---------- */
  function drawer() {
    var r = state.sel, SM = SHB.statusMeta, openCls = r ? " open" : "";
    var inner = "";
    if (r) {
      var kbox = (k, w) => k ? '<div class="dw-kpibox"><div class="win">' + w + '</div><div class="num">' + k.clicks.toLocaleString("vi-VN") + '</div><div class="sub">clicks · CTR ' + k.ctr + "%</div></div>" :
        '<div class="dw-kpibox empty"><span class="nodata">' + ic("clock") + "chưa có data</span></div>";
      inner =
        '<div class="dw-head"><div class="dw-top"><div style="min-width:0;flex:1"><span class="dw-id">' + r.id + " · Tuần " + r.week + " · Phase " + r.phase + '</span><h2 class="dw-title">' + esc(r.title) + "</h2></div>" +
        '<button class="dw-close" aria-label="Đóng">' + ic("x") + "</button></div>" +
        '<div class="dw-chips"><span class="pill" data-tone="' + SHB.priTone[r.pri] + '">' + r.pri + '</span><span class="pill" data-tone="' + SHB.clusterTone[r.cluster] + '">' + r.cluster + "</span>" +
        '<span class="pill" data-tone="' + SHB.funnelTone[r.funnel] + '">' + r.funnel + '</span><span class="pill dotty" data-tone="' + SM[r.status].tone + '">' + SM[r.status].label + "</span>" +
        '<span class="pill" data-tone="' + (band(r.seo) === "good" ? "teal" : band(r.seo) === "ok" ? "amber" : "rose") + '">SEO ' + r.seo + "</span></div></div>" +
        '<div class="dw-body">' +
        '<div class="dw-sec"><h4>' + ic("heading") + "SEO meta</h4>" +
        '<div class="dw-field"><div class="fl">Title SEO</div><div class="fv">' + esc(r.titleSeo) + '</div></div>' +
        '<div class="dw-field"><div class="fl">Meta description</div><div class="fv">' + esc(r.meta) + '</div></div>' +
        '<div class="dw-2"><div class="dw-field"><div class="fl">H1</div><div class="fv">' + esc(r.h1) + '</div></div><div class="dw-field"><div class="fl">Slug</div><div class="fv mono">/' + r.slug + "</div></div></div></div>" +
        '<div class="dw-sec"><h4>' + ic("hash") + "Keywords</h4><div class=\"dw-field\"><div class=\"fl\">Main keyword</div><div class=\"fv mono\">" + r.kw + "</div></div>" +
        '<div class="dw-kw">' + r.secondary.map((k) => '<span data-tone="sky">' + esc(k) + "</span>").join("") + "</div></div>" +
        '<div class="dw-2"><div class="dw-field"><div class="fl">Target URL</div><div class="fv mono">' + r.target + '</div></div><div class="dw-field"><div class="fl">CTA</div><div class="fv">' + esc(r.cta) + "</div></div></div>" +
        '<div class="dw-sec"><h4>' + ic("list-tree") + "Outline H2 / H3</h4><div class=\"dw-outline\">" + r.outline.map((o, i) => '<div class="dw-ol"><span class="on">' + (i + 1) + "</span>" + esc(o) + "</div>").join("") + "</div></div>" +
        '<div class="dw-2"><div class="dw-field"><div class="fl">EEAT / assets</div><div class="fv">' + r.eeat.join(" · ") + '</div></div><div class="dw-field"><div class="fl">Schema</div><div class="fv">' + r.schema + "</div></div></div>" +
        '<div class="dw-sec"><h4>' + ic("link-2") + "Internal links</h4><div class=\"dw-links\">" + r.internal.map((l) => '<div class="dw-link">' + ic("link") + l + "</div>").join("") + "</div></div>" +
        '<div class="dw-sec"><h4>' + ic("image") + "Image search keywords</h4><div class=\"dw-kw\">" + r.images.map((k) => '<span data-tone="violet">' + esc(k) + "</span>").join("") + "</div></div>" +
        '<div class="dw-sec"><h4>' + ic("line-chart") + "KPI sau đăng</h4><div class=\"dw-kpi3\">" + kbox(r.kpi.d14, "14 ngày") + kbox(r.kpi.d28, "28 ngày") + kbox(r.kpi.d60, "60 ngày") + "</div></div>" +
        '<div class="dw-sec"><h4>' + ic("shield-alert") + "Risk note</h4><div class=\"dw-risk\">" + ic("triangle-alert") + esc(r.risk) + "</div></div>" +
        '<div class="dw-sec"><h4>' + ic("history") + "Audit log</h4><div class=\"dw-log\">" + r.audit.map((a) => '<div class="dw-logrow"><span class="lt">' + a.t + '</span><span class="la">' + esc(a.a) + '</span><span class="lw">' + a.who + "</span></div>").join("") + "</div></div>" +
        "</div>" +
        '<div class="dw-foot"><a class="btn-soft violet" href="/blog-content/' + r.dbid + '/edit">' + ic("pencil") + "Edit / Soạn bài</a>" +
        '<a class="btn-line" href="/api/blog-content/export">' + ic("download") + "Export CSV</a>" +
        '<span class="grow"></span><button class="btn-danger" data-sync>' + ic("cloud-upload") + "Sync Haravan</button></div>";
    }
    return '<div class="drawer-scrim' + openCls + '" data-scrim></div><aside class="drawer' + openCls + '" aria-hidden="' + (!r) + '">' + inner + "</aside>";
  }

  /* ---------- mount + render ---------- */
  function pageInner() {
    var rows = filtered();
    var tabBody = state.tab === "queue" ? queueTab(rows) : state.tab === "kanban" ? kanbanTab(rows) :
      state.tab === "calendar" ? calendarTab(rows) : state.tab === "kpi" ? kpiTab(rows) : importTab();
    return '<div class="content">' +
      '<div class="page-head"><div class="page-title">' + ic("newspaper") + '<span class="crumb-up">Nội dung /</span> Blog SEO Command Center</div>' +
      '<div class="spacer"></div><button class="btn-ghost" data-tab="import">' + ic("upload") + "Import roadmap</button><button class=\"btn-line\">" + ic("download") + "Export CSV</button></div>" +
      kpiHeader() + quickFilters() + tabsBar(rows) + tabBody + drawer() + "</div>";
  }
  function render() {
    document.getElementById("root").innerHTML = '<div class="app">' + sidebar() + '<div class="main">' + topbar() + pageInner() + "</div>" + chatFab() + "</div>";
  }
  function rerenderPage() {
    var main = document.querySelector(".main");
    main.querySelector(".content").outerHTML = pageInner();
  }

  /* ---------- copy prompt cho ChatGPT ---------- */
  function buildPrompt(r) {
    var sec = (r.secondary || []).join(", ");
    var links = (r.internal || []).map(function (l) { return l; }).join("\n");
    var lines = [
      "Viết 1 bài blog chuẩn SEO bằng tiếng Việt theo brief dưới đây. Văn phong rõ ràng, hữu ích, đúng sự thật — KHÔNG bịa thông số, KHÔNG hướng dẫn crack/kích hoạt phần mềm lậu. Các thông số dữ liệu đều phải lấy data mới nhất, thực tế, hiện tại và có logic.",
      "• H1: " + (r.h1 || ""),
      "• Slug: " + (r.slug || ""),
      "• Keyword chính: " + (r.kw || ""),
      "• Keyword phụ: " + sec,
      "• CTA (đưa vào cuối bài): " + (r.cta || ""),
      "• Internal links (chèn tự nhiên, đúng ngữ cảnh trong bài):",
      links,
    ];
    return lines.join("\n");
  }
  function fallbackCopy(txt) {
    var ta = document.createElement("textarea");
    ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.focus(); ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta);
  }
  function copyPrompt(btn, r) {
    var txt = buildPrompt(r);
    var done = function () {
      var old = btn.innerHTML; btn.innerHTML = ic("copy-check") + "Đã copy!";
      setTimeout(function () { btn.innerHTML = old; }, 1700);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(done, function () { fallbackCopy(txt); done(); });
    } else { fallbackCopy(txt); done(); }
  }

  /* ---------- gọi API thật (generate brief/draft, sync) ---------- */
  function ccAction(btn, url, body, okMsg) {
    var old = btn.innerHTML; btn.innerHTML = "⏳ Đang xử lý…"; btn.style.pointerEvents = "none";
    fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        btn.innerHTML = (d && d.ok === false) ? (ic("triangle-alert") + (d.error || "lỗi").slice(0, 40)) : (ic("circle-check") + okMsg);
        setTimeout(function () { btn.innerHTML = old; btn.style.pointerEvents = ""; }, 2400);
      })
      .catch(function () { btn.innerHTML = ic("triangle-alert") + "lỗi mạng"; setTimeout(function () { btn.innerHTML = old; btn.style.pointerEvents = ""; }, 2400); });
  }

  /* ---------- interactions ---------- */
  document.addEventListener("click", function (e) {
    var t = e.target;
    var cp = t.closest("[data-copyprompt]");
    if (cp && state.sel) { copyPrompt(cp, state.sel); return; }
    var gb = t.closest("[data-genbrief]");
    if (gb && state.sel) { ccAction(gb, "/api/blog-content/items/" + state.sel.dbid + "/generate-brief", {}, "Đã tạo brief"); return; }
    var gd = t.closest("[data-gendraft]");
    if (gd && state.sel) { ccAction(gd, "/api/blog-content/items/" + state.sel.dbid + "/generate-draft", {}, "Đã gen draft"); return; }
    var sy = t.closest("[data-sync]");
    if (sy && state.sel) {
      if (!confirm("Sync bài này lên Haravan (tạo bản nháp ẩn, không tự đăng)?")) return;
      var phrase = prompt("Gõ xác nhận để sync:\nPUBLISH BLOG ITEM");
      if (phrase === null) return;
      ccAction(sy, "/api/blog-content/items/" + state.sel.dbid + "/sync", { confirm: phrase, publish: false }, "Đã sync");
      return;
    }
    var tabBtn = t.closest("[data-tab]");
    if (tabBtn) { state.tab = tabBtn.getAttribute("data-tab"); rerenderPage(); return; }
    var f = t.closest("[data-filter]");
    if (f) { var k = f.getAttribute("data-filter"); state.filters.has(k) ? state.filters.delete(k) : state.filters.add(k); rerenderPage(); return; }
    var kpi = t.closest("[data-kpi]");
    if (kpi) { var kk = kpi.getAttribute("data-kpi"); if (["A1", "A2", "overdue"].includes(kk)) { state.filters.has(kk) ? state.filters.delete(kk) : state.filters.add(kk); state.tab = "queue"; } else if (["writing", "seo_review", "ready_publish", "published"].includes(kk)) state.tab = "kanban"; rerenderPage(); return; }
    var row = t.closest("[data-id]");
    if (row) { var it = SHB.items.find((x) => x.id === row.getAttribute("data-id")); if (it) { state.sel = it; document.querySelector(".content").outerHTML = pageInner(); } return; }
    if (t.closest("[data-scrim]") || t.closest(".dw-close")) { state.sel = null; document.querySelector(".content").outerHTML = pageInner(); return; }
    var col = t.closest("[data-collapse]");
    if (col) { col.classList.toggle("open"); var kids = col.nextElementSibling; if (kids && kids.classList.contains("nav-children")) kids.classList.toggle("open"); return; }
    if (t.closest(".nox-fab")) { var fab = t.closest(".nox-fab"); fab.classList.toggle("on"); return; }
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render);
  else render();
})();
