/* GA4 Analytics dashboard — chỉ chạy ở /seo/ga4. Đọc endpoint cache, không gọi GA4 trực tiếp. */
(function () {
  "use strict";
  var app = document.getElementById("ga4-app");
  if (!app) return;

  var ACC = {
    exact_period_cache: "Số user duy nhất trong toàn khoảng ngày, lấy từ GA4 period-level cache",
    exact_additive: "Có thể cộng chính xác theo ngày",
    exact_recomputed: "Tính lại từ metric gốc (engaged/sessions)",
    weighted_recomputed: "Tính theo trọng số sessions",
    approximate_daily_sum: "Ước tính từ dữ liệu ngày, có thể đếm trùng user giữa các ngày"
  };
  var ACC_SHORT = { exact_period_cache: "exact", exact_additive: "exact", exact_recomputed: "exact",
                    weighted_recomputed: "~wt", approximate_daily_sum: "≈" };

  var S = { range: "28", from: "", to: "", compare: true, channel: "", device: "",
            ptype: "", search: "", tab: "overview", loaded: {}, rtTimer: null, syncing: false };

  function $(s, r) { return (r || document).querySelector(s); }
  function $all(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function nf(n) { if (n == null) return "—"; return Number(n).toLocaleString("vi-VN"); }
  function money(n) { if (n == null) return "—"; return Number(n).toLocaleString("vi-VN") + "₫"; }
  function pctv(n) { return (n == null) ? "—" : (Number(n) * 100).toFixed(1) + "%"; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  // qs() CHỈ chứa filter GLOBAL thật: khoảng ngày + so sánh kỳ trước.
  // Filter tab-specific (channel/page_type/search) do từng tab tự append.
  function qs(extra) {
    var p = ["compare_previous=" + (S.compare ? "true" : "false")];
    if (S.range === "custom" && S.from && S.to) { p.push("date_from=" + S.from, "date_to=" + S.to); }
    else { p.push("range=" + S.range); }
    if (extra) p.push(extra);
    return "?" + p.join("&");
  }
  function appliedLine(txt) {
    return '<div class="g4-muted" style="margin:2px 0 8px;font-size:11.5px">🔎 Bộ lọc đang áp dụng: ' + esc(txt) + "</div>";
  }
  var TOTAL_NOTE = "Tab này đang hiển thị tổng dữ liệu theo khoảng ngày.";
  function get(url) { return fetch(url).then(function (r) { return r.json().then(function (j) { j._http = r.status; return j; }); }); }

  /* ---------- delta + kpi ---------- */
  function deltaHtml(d) {
    if (!d || d.delta_percent == null) return '<div class="dl g4-muted">—</div>';
    var up = d.delta >= 0, cls = up ? "up" : "down";
    return '<div class="dl ' + cls + '">' + (up ? "▲" : "▼") + " " + Math.abs(d.delta_percent) + "% "
      + '<span class="g4-muted">vs ' + nf(d.previous) + "</span></div>";
  }
  function accBadge(code) {
    if (!code) return "";
    return '<span class="g4-acc" title="' + esc(ACC[code] || code) + '">' + (ACC_SHORT[code] || code) + "</span>";
  }
  function kpi(label, d, fmt, accCode, tip) {
    var val = d && typeof d === "object" ? d.current : d;
    var shown = fmt === "money" ? money(val) : fmt === "pct" ? pctv(val) : nf(val);
    return '<div class="g4-kpi"><div class="num">' + shown + "</div>"
      + '<div class="lbl">' + esc(label) + (accCode ? " " + accBadge(accCode) : "")
      + (tip ? ' <span class="g4-help" title="' + esc(tip) + '">ⓘ</span>' : "") + "</div>"
      + (d && typeof d === "object" ? deltaHtml(d) : "") + "</div>";
  }
  function barChart(title, series, key, fmtFn) {
    if (!series || !series.length) return '<div class="g4-chart"><h4>' + esc(title) + '</h4><div class="g4-muted">Không có dữ liệu</div></div>';
    var max = Math.max.apply(null, series.map(function (x) { return x[key] || 0; })) || 1;
    var bars = series.map(function (x) {
      var h = Math.max(2, (x[key] || 0) / max * 100);
      return '<div class="g4-bar" style="height:' + h + '%" title="' + x.date + ": " + (fmtFn ? fmtFn(x[key]) : nf(x[key])) + '"></div>';
    }).join("");
    return '<div class="g4-chart"><h4>' + esc(title) + '</h4><div class="g4-bars">' + bars + "</div></div>";
  }

  function panel(t) { return $('.g4-panel[data-tab="' + t + '"]'); }
  function skel(t) { panel(t).innerHTML = '<div class="g4-skel"></div>'; }
  function emptyBox(msg) { return '<div class="g4-empty">' + esc(msg) + "</div>"; }
  function errBox(env) {
    if (env && env.error === "not_configured") return emptyBox("Chưa cấu hình tracking.");
    return '<div class="g4-empty" style="color:#f87171">Lỗi tải dữ liệu' + (env && env.error ? ": " + esc(env.error) : "") + "</div>";
  }

  /* ---------- META LINE + status ---------- */
  function pill(cls, txt, title) { return '<span class="g4-pill ' + cls + '"' + (title ? ' title="' + esc(title) + '"' : "") + ">" + esc(txt) + "</span>"; }
  function renderMeta(st) {
    var apiMap = { ok: ["b-ok", "API ok"], ready: ["b-warn", "API ready"], error: ["b-err", "API " + (st.error_code || "lỗi")],
                   token_missing: ["b-err", "thiếu token"], not_configured: ["b-gray", "chưa cấu hình"] };
    var a = apiMap[st.api_status] || ["b-gray", st.api_status];
    var ls = st.last_sync || {};
    var out = [];
    out.push(pill("b-info", "Property " + (window.GA4_CFG ? window.GA4_CFG.propertyMasked : "***")));
    out.push(pill("b-gray", (window.GA4_CFG ? window.GA4_CFG.authMode : "")));
    out.push(pill(a[0], a[1], st.error_message));
    if (ls.latest_data_date) out.push(pill("b-gray", "Data đến " + ls.latest_data_date));
    if (ls.finished_at) out.push(pill("b-gray", "Sync " + ls.finished_at));
    if (st.is_running) out.push(pill("b-warn", "⏳ đang đồng bộ"));
    $("#g4-meta").innerHTML = out.join(" ");
    var btn = $("#g4-refresh");
    if (st.is_running) { btn.disabled = true; btn.textContent = "⏳ Đang đồng bộ…"; S.syncing = true; }
    else if (!S.syncing) { btn.disabled = false; btn.textContent = "🔄 Refresh cache"; }
  }
  function loadStatus() { return get("/api/ga4/status?probe=0").then(renderMeta).catch(function () {}); }

  function staleBadge(env) {
    if (env && env.stale) return ' <span class="g4-pill b-warn" title="Cache cũ hơn TTL">⚠ cache stale</span>';
    return "";
  }

  /* ---------- OVERVIEW ---------- */
  function loadOverview() {
    skel("overview");
    Promise.all([get("/api/ga4/overview" + qs()), get("/api/ga4/timeseries" + qs()),
                 get("/api/ga4/realtime")]).then(function (res) {
      var ov = res[0], ts = res[1], rt = res[2];
      if (!ov.ok) { panel("overview").innerHTML = errBox(ov); return; }
      if (ov.tracking_state === "not_configured" && (!ov.data || !ov.data.sessions || !ov.data.sessions.current)) {
        panel("overview").innerHTML = emptyBox("Chưa có dữ liệu — bấm Refresh cache để đồng bộ lần đầu."); return;
      }
      var acc = (ov.meta && ov.meta.metric_accuracy) || {}, d = ov.data;
      var cards = [
        kpi("Active users", d.active_users, "n", acc.active_users),
        kpi("New users", d.new_users, "n", acc.new_users),
        kpi("Sessions", d.sessions, "n", acc.sessions),
        kpi("Organic Search sessions", d.organic_search_sessions, "n", acc.organic_search_sessions),
        kpi("Engagement rate", d.engagement_rate, "pct", acc.engagement_rate),
        kpi("Key events", d.key_events, "n", acc.key_events),
        kpi("Ecommerce purchases", d.ecommerce_purchases, "n", acc.ecommerce_purchases),
        kpi("Purchase revenue", d.purchase_revenue, "money", acc.purchase_revenue),
        kpi("Khách hoạt động 30 phút gần nhất", rt && rt.active_users_30m, "n", null, "Realtime, cửa sổ 30 phút"),
        kpi("Khách hoạt động 5 phút gần nhất", rt && (rt.active_users_5m == null ? "—" : rt.active_users_5m), "n", null,
            (rt && rt.five_minute_state === "ok") ? "Realtime, cửa sổ 5 phút" : "Chưa khả dụng")
      ].join("");
      var s = ts.data || [];
      var charts = [
        barChart("Sessions theo ngày", s, "sessions"),
        barChart("Organic sessions theo ngày", s, "organic_search_sessions"),
        barChart("Engagement rate theo ngày", s, "engagement_rate", pctv),
        barChart("Key events theo ngày", s, "key_events"),
        (d.purchase_revenue && d.purchase_revenue.current ? barChart("Revenue theo ngày", s, "purchase_revenue", money) : "")
      ].join("");
      panel("overview").innerHTML =
        '<p class="g4-muted" style="margin:2px 0 10px">Kỳ ' + ov.period.date_from + " → " + ov.period.date_to
        + (ov.previous_period ? " (so với " + ov.previous_period.date_from + " → " + ov.previous_period.date_to + ")" : "")
        + staleBadge(ov) + "</p>" + appliedLine(TOTAL_NOTE)
        + '<div class="g4-kpis">' + cards + "</div>"
        + '<div class="g4-charts">' + charts + "</div>";
    }).catch(function () { panel("overview").innerHTML = errBox(); });
  }

  /* ---------- REALTIME ---------- */
  function renderRealtime(rt) {
    var p = panel("realtime");
    if (!rt.ok && rt.realtime_source === "error") {
      p.innerHTML = '<div class="g4-card">' + emptyBox("Realtime tạm không khả dụng (" + esc(rt.error || "lỗi") + ").") + "</div>"; return;
    }
    var d = rt.data || {};
    var src = { cache: ["b-gray", "cache"], live: ["b-ok", "live"], cache_fallback: ["b-warn", "cache fallback"], error: ["b-err", "error"] }[rt.realtime_source] || ["b-gray", rt.realtime_source];
    var head = pill(src[0], "nguồn: " + src[1]) + " " + (rt.stale ? pill("b-warn", "stale") : "")
      + " " + pill("b-gray", "cập nhật " + (rt.fetched_at || "—")) + ' <button class="btn" id="g4-rt-refresh" type="button" style="padding:3px 10px;font-size:12px">↻ làm mới</button>';
    var body;
    if (rt.empty || (d.active_users_30m === 0 && (!d.top_pages || !d.top_pages.length))) {
      body = emptyBox("Chưa ghi nhận hoạt động trong 30 phút gần nhất.");
    } else {
      var fiveTxt = (d.active_users_5m == null) ? '<span class="g4-muted">chưa khả dụng</span>' : nf(d.active_users_5m);
      function rows(arr, k1, k2) { return (arr && arr.length) ? arr.map(function (x) {
        return "<tr><td>" + esc(x[k1]) + '</td><td class="num">' + nf(x[k2]) + "</td></tr>"; }).join("") : '<tr><td class="g4-muted" colspan="2">—</td></tr>'; }
      body = '<div class="g4-kpis" style="margin-bottom:12px">'
        + kpi("Khách hoạt động 30 phút gần nhất", d.active_users_30m, "n")
        + '<div class="g4-kpi"><div class="num">' + fiveTxt + '</div><div class="lbl">Khách hoạt động 5 phút gần nhất</div></div></div>'
        + '<div class="g4-charts">'
        + '<div class="g4-chart"><h4>Top page</h4><table class="g4-tbl" style="min-width:auto"><tbody>' + rows(d.top_pages, "page", "active_users") + "</tbody></table></div>"
        + '<div class="g4-chart"><h4>Thiết bị</h4><table class="g4-tbl" style="min-width:auto"><tbody>' + rows(d.devices, "device", "active_users") + "</tbody></table></div>"
        + '<div class="g4-chart"><h4>Top event</h4><table class="g4-tbl" style="min-width:auto"><tbody>' + rows(d.top_events, "event", "count") + "</tbody></table></div>"
        + "</div>";
    }
    p.innerHTML = '<div style="margin-bottom:10px">' + head + "</div>" + body;
    var rb = $("#g4-rt-refresh"); if (rb) rb.addEventListener("click", function () { loadRealtime(true); });
  }
  function loadRealtime(force) {
    if (!force) skel("realtime");
    get("/api/ga4/realtime" + (force ? "?force=1" : "")).then(renderRealtime).catch(function () { panel("realtime").innerHTML = errBox(); });
  }

  /* ---------- generic table tabs ---------- */
  function sortableHead(cols, cur) {
    return cols.map(function (c) {
      var cls = c.num ? "num" : "";
      var arrow = (cur && cur === c.key) ? " ▾" : "";
      return '<th class="' + cls + '"' + (c.key ? ' data-sort="' + c.key + '"' : "") + ">" + esc(c.label) + arrow + "</th>";
    }).join("");
  }
  var PG = {};
  function tableTab(tab, url, cols, rowFn, opts) {
    opts = opts || {};
    skel(tab);
    var head = (opts.toolbar || "") + (opts.applied ? appliedLine(opts.applied) : "");
    get(url).then(function (env) {
      if (!env.ok) { panel(tab).innerHTML = head + errBox(env); if (opts.afterRender) opts.afterRender(panel(tab)); return; }
      var rows = env.data || [];
      if (!rows.length) {
        panel(tab).innerHTML = head + '<div class="g4-card">' + emptyBox("Không có dữ liệu trong kỳ.") + "</div>";
        if (opts.afterRender) opts.afterRender(panel(tab)); return;
      }
      var body = rows.map(rowFn).join("");
      var note = opts.note ? '<p class="g4-muted" style="margin:4px 0 8px">' + opts.note + staleBadge(env) + "</p>" : "";
      var pag = "";
      if (env.total_rows != null) {
        var off = env.offset || 0, lim = env.limit || rows.length, to = Math.min(off + lim, env.total_rows);
        pag = '<div class="g4-paginate"><span class="g4-muted">' + (off + 1) + "–" + to + " / " + env.total_rows + "</span>"
          + '<button data-pg="prev"' + (off <= 0 ? " disabled" : "") + ">←</button>"
          + '<button data-pg="next"' + (to >= env.total_rows ? " disabled" : "") + ">→</button></div>";
      }
      panel(tab).innerHTML = head + note + '<div class="g4-card g4-tblwrap"><table class="g4-tbl"><thead><tr>'
        + sortableHead(cols, S["sort_" + tab]) + "</tr></thead><tbody>" + body + "</tbody></table>" + pag + "</div>";
      $all("th[data-sort]", panel(tab)).forEach(function (th) {
        th.addEventListener("click", function () {
          var k = th.getAttribute("data-sort");
          S["order_" + tab] = (S["sort_" + tab] === k && S["order_" + tab] === "desc") ? "asc" : "desc";
          S["sort_" + tab] = k; PG[tab] = 0; reloadTab(tab);
        });
      });
      $all("[data-pg]", panel(tab)).forEach(function (b) {
        b.addEventListener("click", function () {
          PG[tab] = Math.max(0, (PG[tab] || 0) + (b.getAttribute("data-pg") === "next" ? 1 : -1)); reloadTab(tab);
        });
      });
      if (opts.afterRender) opts.afterRender(panel(tab));
    }).catch(function () { panel(tab).innerHTML = head + errBox(); if (opts.afterRender) opts.afterRender(panel(tab)); });
  }
  function pageExtra(tab, perPage) {
    var off = (PG[tab] || 0) * perPage;
    var e = "limit=" + perPage + "&offset=" + off;
    if (S["sort_" + tab]) e += "&sort=" + S["sort_" + tab] + "&order=" + (S["order_" + tab] || "desc");
    return e;
  }

  var CHANNEL_LIST = [];
  function loadChannels() {
    var cols = [{ label: "Channel" }, { label: "Source/medium" }, { label: "Active*", num: 1, key: "active_users" },
      { label: "Sessions", num: 1, key: "sessions" }, { label: "Engaged", num: 1, key: "engaged_sessions" },
      { label: "Eng.rate", num: 1, key: "engagement_rate" }, { label: "Key ev", num: 1, key: "key_events" },
      { label: "Purchases", num: 1, key: "ecommerce_purchases" }, { label: "Revenue", num: 1, key: "purchase_revenue" },
      { label: "Δ sessions", num: 1 }, { label: "Δ revenue", num: 1 }];
    var optHtml = CHANNEL_LIST.map(function (c) {
      return '<option value="' + esc(c) + '"' + (S.channel === c ? " selected" : "") + ">" + esc(c) + "</option>"; }).join("");
    var toolbar = '<div class="g4-quick"><span style="font-size:12px;color:var(--text-muted,#94a3b8)">Kênh:&nbsp;</span>'
      + '<select id="g4-ch-sel" style="background:var(--surface,#111);color:inherit;border:1px solid var(--border,rgba(255,255,255,.12));border-radius:8px;padding:5px 9px;font-size:12px">'
      + '<option value="">Tất cả kênh</option>' + optHtml + "</select></div>";
    var extra = pageExtra("channels", 50);
    if (S.channel) extra += "&channel=" + encodeURIComponent(S.channel);
    tableTab("channels", "/api/ga4/channels" + qs(extra), cols, function (r) {
      return "<tr><td>" + chBadge(r.channel) + '</td><td class="g4-key">' + esc(r.source_medium) + '</td><td class="num">' + nf(r.active_users)
        + '</td><td class="num">' + nf(r.sessions) + '</td><td class="num">' + nf(r.engaged_sessions) + '</td><td class="num">' + pctv(r.engagement_rate)
        + '</td><td class="num">' + nf(r.key_events) + '</td><td class="num">' + nf(r.ecommerce_purchases) + '</td><td class="num">' + money(r.purchase_revenue)
        + '</td><td class="num ' + (r.delta_sessions >= 0 ? "up" : "down") + '">' + (r.delta_sessions >= 0 ? "+" : "") + nf(r.delta_sessions)
        + '</td><td class="num ' + (r.delta_revenue >= 0 ? "up" : "down") + '">' + (r.delta_revenue >= 0 ? "+" : "") + money(r.delta_revenue) + "</td></tr>";
    }, {
      toolbar: toolbar,
      applied: S.channel ? ("Kênh = " + S.channel) : "Tất cả kênh (theo khoảng ngày)",
      note: "* Active users theo kênh là ước tính (cộng daily). Sessions & revenue exact additive.",
      afterRender: function (p) {
        var sel = $("#g4-ch-sel", p);
        if (sel) sel.addEventListener("change", function (e) { S.channel = e.target.value; PG.channels = 0; loadChannels(); });
      }
    });
  }
  function chBadge(c) {
    var m = { "Organic Search": "b-ok", "Direct": "b-gray", "Organic Social": "b-info", "Paid Social": "b-warn",
      "Referral": "b-info", "Paid Search": "b-warn", "Email": "b-info", "Unassigned": "b-gray" };
    return '<span class="g4-pill ' + (m[c] || "b-gray") + '">' + esc(c || "Other") + "</span>";
  }

  var LP_QUICK = [["", "Tất cả"], ["traffic", "Traffic cao"], ["lowering", "Engagement thấp"], ["keyev", "Có key event"],
    ["rev", "Có revenue"], ["product", "Product"], ["collection", "Collection"], ["blog", "Blog"], ["build_pc", "Build PC"], ["homepage", "Homepage"], ["other", "Other"]];
  var LP_TYPES = ["product", "collection", "blog", "build_pc", "homepage", "other"];
  var lpQuick = "";
  function loadLanding() {
    var q = LP_QUICK.map(function (x) {
      return '<button data-q="' + x[0] + '"' + (lpQuick === x[0] ? ' class="on"' : "") + ">" + x[1] + "</button>"; }).join("");
    var toolbar = '<div class="g4-quick" style="margin-bottom:6px"><input type="search" id="g4-lp-search" placeholder="Tìm landing path…" '
      + 'value="' + esc(S.search) + '" style="background:var(--surface,#111);color:inherit;border:1px solid var(--border,rgba(255,255,255,.12));border-radius:8px;padding:5px 10px;font-size:12px;width:190px"></div>'
      + '<div class="g4-quick" id="g4-lpq">' + q + "</div>";
    var cols = [{ label: "Landing page" }, { label: "Type" }, { label: "Active*", num: 1, key: "active_users" },
      { label: "New*", num: 1, key: "new_users" }, { label: "Sessions", num: 1, key: "sessions" },
      { label: "Eng.rate", num: 1, key: "engagement_rate" }, { label: "Views", num: 1, key: "screen_page_views" },
      { label: "Key ev", num: 1, key: "key_events" }, { label: "Purch", num: 1, key: "ecommerce_purchases" },
      { label: "Revenue", num: 1, key: "purchase_revenue" }, { label: "Δ sess", num: 1 }, { label: "Track" }];
    var extra = pageExtra("landing", 50);
    if (LP_TYPES.indexOf(lpQuick) >= 0) extra += "&page_type=" + lpQuick;
    if (S.search) extra += "&search=" + encodeURIComponent(S.search);
    var qlabel = (function () { for (var i = 0; i < LP_QUICK.length; i++) if (LP_QUICK[i][0] === lpQuick) return LP_QUICK[i][1]; return "Tất cả"; })();
    var applied = "Quick: " + qlabel + (S.search ? (" · Tìm: “" + S.search + "”") : "");
    tableTab("landing", "/api/ga4/landing-pages" + qs(extra), cols, function (r) {
      return '<tr><td class="g4-key" title="' + esc(r.landing_page_raw || r.normalized_path) + '">' + esc(r.normalized_path)
        + "</td><td>" + ptypeBadge(r.page_type) + '</td><td class="num">' + nf(r.active_users) + '</td><td class="num">' + nf(r.new_users)
        + '</td><td class="num">' + nf(r.sessions) + '</td><td class="num">' + pctv(r.engagement_rate) + '</td><td class="num">' + nf(r.screen_page_views)
        + '</td><td class="num">' + nf(r.key_events) + '</td><td class="num">' + nf(r.ecommerce_purchases) + '</td><td class="num">' + money(r.purchase_revenue)
        + '</td><td class="num ' + (r.delta_sessions >= 0 ? "up" : "down") + '">' + (r.delta_sessions >= 0 ? "+" : "") + nf(r.delta_sessions)
        + '</td><td>' + pill("b-ok", r.tracking_state) + "</td></tr>";
    }, {
      toolbar: toolbar, applied: applied,
      note: "normalized_path dùng cho join SEO sau. * Active/New users theo landing là ước tính (cộng daily).",
      afterRender: function (p) {
        $all("#g4-lpq button", p).forEach(function (b) {
          b.addEventListener("click", function () {
            lpQuick = b.getAttribute("data-q");
            if (lpQuick === "traffic") { S.sort_landing = "sessions"; S.order_landing = "desc"; }
            else if (lpQuick === "lowering") { S.sort_landing = "engagement_rate"; S.order_landing = "asc"; }
            else if (lpQuick === "keyev") { S.sort_landing = "key_events"; S.order_landing = "desc"; }
            else if (lpQuick === "rev") { S.sort_landing = "purchase_revenue"; S.order_landing = "desc"; }
            PG.landing = 0; loadLanding();
          });
        });
        var si = $("#g4-lp-search", p), t;
        if (si) si.addEventListener("input", function (e) {
          clearTimeout(t); t = setTimeout(function () { S.search = e.target.value.trim(); PG.landing = 0; loadLanding(); }, 400);
        });
      }
    });
  }
  function ptypeBadge(t) {
    var m = { product: "b-info", collection: "b-info", blog: "b-ok", build_pc: "b-warn", homepage: "b-gray", page: "b-gray", other: "b-gray" };
    return '<span class="g4-pill ' + (m[t] || "b-gray") + '">' + esc(t) + "</span>";
  }

  function loadDevices() {
    var cols = [{ label: "Device" }, { label: "Active*", num: 1, key: "active_users" }, { label: "Sessions", num: 1, key: "sessions" },
      { label: "Engaged", num: 1, key: "engaged_sessions" }, { label: "Eng.rate", num: 1, key: "engagement_rate" },
      { label: "Key ev", num: 1, key: "key_events" }, { label: "Revenue", num: 1, key: "purchase_revenue" }];
    tableTab("devices", "/api/ga4/devices" + qs("limit=50"), cols, function (r) {
      return "<tr><td>" + esc(r.device_category) + '</td><td class="num">' + nf(r.active_users) + '</td><td class="num">' + nf(r.sessions)
        + '</td><td class="num">' + nf(r.engaged_sessions) + '</td><td class="num">' + pctv(r.engagement_rate) + '</td><td class="num">' + nf(r.key_events)
        + '</td><td class="num">' + money(r.purchase_revenue) + "</td></tr>";
    }, { applied: "Tất cả thiết bị theo khoảng ngày (chưa hỗ trợ lọc chéo theo thiết bị)",
         note: "* Active users theo thiết bị là ước tính (cộng daily)." });
  }

  function loadEvents() {
    var cols = [{ label: "Event name" }, { label: "Count", num: 1, key: "event_count" }, { label: "Users", num: 1, key: "total_users" },
      { label: "Key ev", num: 1, key: "key_events" }, { label: "Value", num: 1, key: "event_value" }, { label: "Last seen" }];
    tableTab("events", "/api/ga4/events" + qs(pageExtra("events", 100)), cols, function (r) {
      return "<tr><td>" + esc(r.event_name) + '</td><td class="num">' + nf(r.event_count) + '</td><td class="num">' + nf(r.total_users)
        + '</td><td class="num">' + nf(r.key_events) + '</td><td class="num">' + nf(r.event_value) + "</td><td>" + esc(r.last_seen_date) + "</td></tr>";
    }, { applied: TOTAL_NOTE,
         note: "Chỉ render event đã ghi nhận. Event không có trong bảng = chưa thấy / chưa cấu hình." });
  }

  function loadEcommerce() {
    skel("ecommerce");
    get("/api/ga4/ecommerce" + qs()).then(function (env) {
      if (!env.ok) { panel("ecommerce").innerHTML = errBox(env); return; }
      var d = env.data || {};
      if (env.tracking_state === "not_configured") {
        panel("ecommerce").innerHTML = '<div class="g4-card" style="opacity:.7"><h3 style="margin:0 0 6px">🛒 Ecommerce</h3>'
          + '<p class="g4-muted">Chưa cấu hình tracking ecommerce. (Không hiển thị số 0 như dữ liệu thật.)</p></div>'; return;
      }
      var funnel = [["Items viewed", d.items_viewed], ["Items added to cart", d.items_added_to_cart],
        ["Items checked out", d.items_checked_out], ["Items purchased", d.items_purchased]];
      var fmax = Math.max.apply(null, funnel.map(function (x) { return x[1] || 0; })) || 1;
      var funHtml = funnel.map(function (x) {
        return '<div style="margin-bottom:6px"><div class="g4-muted" style="font-size:11px">' + x[0] + ": <b>" + nf(x[1]) + '</b></div>'
          + '<div style="height:14px;background:rgba(59,130,246,.18);border-radius:4px;overflow:hidden"><div style="height:100%;width:'
          + ((x[1] || 0) / fmax * 100) + '%;background:#3b82f6"></div></div></div>'; }).join("");
      panel("ecommerce").innerHTML = appliedLine(TOTAL_NOTE) + '<div class="g4-kpis">'
        + kpi("Checkouts", d.checkouts, "n") + kpi("Ecommerce purchases", d.ecommerce_purchases, "n")
        + kpi("Purchase revenue", d.purchase_revenue, "money") + kpi("Total revenue", d.total_revenue, "money")
        + "</div><div class=\"g4-card\" style=\"margin-top:12px\"><h4 style=\"margin:0 0 10px;font-size:12px\">Funnel theo số lượng item</h4>"
        + funHtml + '<p class="g4-muted" style="margin-top:6px">items_* là số lượng item, KHÔNG phải số user.</p></div>';
    }).catch(function () { panel("ecommerce").innerHTML = errBox(); });
  }

  function loadHealth() {
    skel("health");
    Promise.all([get("/api/ga4/status?probe=1"), get("/api/ga4/ecommerce" + qs())]).then(function (r) {
      var st = r[0], ec = r[1], ls = st.last_sync || {};
      var q = "—";
      if (ls.quota_snapshot_json) { try { var qj = JSON.parse(ls.quota_snapshot_json);
        var t = qj.tokensPerDay || {}, h = qj.tokensPerHour || {};
        q = "ngày " + (t.remaining != null ? t.remaining : "?") + " còn / giờ " + (h.remaining != null ? h.remaining : "?") + " còn"; } catch (e) { q = "có"; } }
      function row(k, v, cls) { return '<tr><td class="g4-muted">' + esc(k) + "</td><td>" + (cls ? pill(cls, v) : esc(v)) + "</td></tr>"; }
      var apiCls = st.api_status === "ok" ? "b-ok" : st.api_status === "error" ? "b-err" : "b-warn";
      var syncCls = ls.status === "success" ? "b-ok" : ls.status === "running" ? "b-warn" : ls.status ? "b-err" : "b-gray";
      panel("health").innerHTML = '<div class="g4-card g4-tblwrap"><table class="g4-tbl" style="min-width:auto"><tbody>'
        + row("GA4 API status", st.api_status + (st.error_code ? " (" + st.error_code + ")" : ""), apiCls)
        + row("Property ID", window.GA4_CFG.propertyMasked) + row("Credential mode", st.auth_mode)
        + row("Latest data date", ls.latest_data_date || "—") + row("Fetched at", ls.finished_at || "—")
        + row("Last sync status", ls.status || "—", syncCls) + row("Sync rows written", ls.rows_written != null ? nf(ls.rows_written) : "—")
        + row("Sync range", (ls.date_from || "—") + " → " + (ls.date_to || "—"))
        + row("Sync running", st.is_running ? "có" : "không", st.is_running ? "b-warn" : "b-gray")
        + row("Quota snapshot", q) + row("Ecommerce tracking", ec.tracking_state, ec.tracking_state === "ok" ? "b-ok" : "b-gray")
        + (st.metadata ? row("Metadata", st.metadata.dimensions + " dims / " + st.metadata.metrics + " metrics") : "")
        + "</tbody></table></div>";
    }).catch(function () { panel("health").innerHTML = errBox(); });
  }

  var LOADERS = { overview: loadOverview, realtime: loadRealtime, channels: loadChannels, landing: loadLanding,
    devices: loadDevices, events: loadEvents, ecommerce: loadEcommerce, health: loadHealth };
  function reloadTab(t) { if (LOADERS[t]) LOADERS[t](); }

  /* ---------- tab nav ---------- */
  function showTab(t) {
    S.tab = t;
    $all("#g4-tabnav button").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-t") === t); });
    $all(".g4-panel").forEach(function (p) { p.hidden = p.getAttribute("data-tab") !== t; });
    if (!S.loaded[t]) { S.loaded[t] = true; reloadTab(t); }
    // realtime polling only on realtime tab
    if (S.rtTimer) { clearInterval(S.rtTimer); S.rtTimer = null; }
    if (t === "realtime") {
      S.rtTimer = setInterval(function () {
        if (document.hidden || S.tab !== "realtime") return; loadRealtime();
      }, 60000);
    }
  }

  /* ---------- filter changes ---------- */
  function reloadAll() {
    S.loaded = {}; S.loaded[S.tab] = true; reloadTab(S.tab); loadStatus();
  }
  function bindFilters() {
    $all("#g4-range button").forEach(function (b) {
      b.addEventListener("click", function () {
        $all("#g4-range button").forEach(function (x) { x.classList.remove("on"); });
        b.classList.add("on"); S.range = b.getAttribute("data-r");
        $("#g4-custom").style.display = S.range === "custom" ? "" : "none";
        if (S.range !== "custom") reloadAll();
      });
    });
    $("#g4-from").addEventListener("change", function (e) { S.from = e.target.value; if (S.to) reloadAll(); });
    $("#g4-to").addEventListener("change", function (e) { S.to = e.target.value; if (S.from) reloadAll(); });
    $("#g4-compare").addEventListener("change", function (e) { S.compare = e.target.checked; reloadAll(); });
    // channel/page_type/search là tab-specific → bind trong loadChannels/loadLanding (không ở global bar)
    $("#g4-refresh").addEventListener("click", doRefresh);
    $all("#g4-tabnav button").forEach(function (b) {
      b.addEventListener("click", function () { showTab(b.getAttribute("data-t")); });
    });
  }

  /* ---------- refresh cache (handle 409) ---------- */
  function doRefresh() {
    var btn = $("#g4-refresh");
    btn.disabled = true; btn.textContent = "⏳ Đang đồng bộ…"; S.syncing = true;
    fetch("/api/ga4/refresh", { method: "POST" }).then(function (r) { return r.json().then(function (j) { j._http = r.status; return j; }); })
      .then(function (j) {
        if (j._http === 409) { /* đang chạy — không báo lỗi đỏ */ }
        pollSync();
      }).catch(function () { S.syncing = false; btn.disabled = false; btn.textContent = "🔄 Refresh cache"; });
  }
  function pollSync() {
    var tries = 0;
    var iv = setInterval(function () {
      tries++;
      get("/api/ga4/status?probe=0").then(function (st) {
        renderMeta(st);
        if (!st.is_running || tries > 40) {
          clearInterval(iv); S.syncing = false;
          var btn = $("#g4-refresh"); btn.disabled = false; btn.textContent = "🔄 Refresh cache";
          reloadAll();
        }
      });
    }, 3000);
  }

  /* ---------- channel list cho select trong tab Channels ---------- */
  function loadChannelList() {
    get("/api/ga4/channels?range=90&limit=500").then(function (env) {
      if (!env.ok) return; var seen = {};
      (env.data || []).forEach(function (r) { if (r.channel && !seen[r.channel]) { seen[r.channel] = 1; CHANNEL_LIST.push(r.channel); } });
    });
  }

  /* ---------- init ---------- */
  bindFilters();
  loadStatus();
  loadChannelList();
  S.loaded.overview = true;
  loadOverview();
})();
