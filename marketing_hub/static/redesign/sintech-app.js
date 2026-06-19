/* ============================================================
   Sintech Hub — interactions (vanilla JS, no framework)
   • Hydrates inline icons from window.SintechIcons
   • KPI style toggle · sidebar collapse · table filter
   • tier select · alert dismiss · Nox-1 chat · page nav
   Load AFTER the icon files + this page's markup.
   ============================================================ */
(function () {
  "use strict";
  var ICONS = window.SintechIcons || {};

  /* ---- inline icon hydration ---- */
  function hydrate(root) {
    (root || document).querySelectorAll(".ic[data-icon]:not([data-ic-done])").forEach(function (el) {
      var p = ICONS[el.getAttribute("data-icon")];
      if (p) el.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + p + "</svg>";
      el.setAttribute("data-ic-done", "1");
    });
  }

  /* ---- page navigation map (sidebar → file) ---- */
  var NAV = {
    "Dashboard": "dashboard.html",
    "Title & Meta": "title-meta.html",
    "Collection Content": "editor.html",
    "Coverage": "audit.html",
  };

  /* ---- KPI style swap ---- */
  function setKpi(mode, btn) {
    var cls = mode === "soft" ? "is-soft" : mode === "mono" ? "is-grad is-mono" : "is-grad";
    document.querySelectorAll(".stat").forEach(function (s) {
      s.classList.remove("is-grad", "is-soft", "is-mono");
      cls.split(" ").forEach(function (c) { s.classList.add(c); });
    });
    if (btn) btn.parentNode.querySelectorAll("button").forEach(function (b) { b.classList.toggle("on", b === btn); });
  }

  /* ---- queue/list table filter (by status text) ---- */
  function filterRows(scope, val) {
    var norm = val.toLowerCase();
    scope.querySelectorAll("tbody tr").forEach(function (tr) {
      var pill = tr.querySelector(".pill.dotty");
      var st = pill ? pill.textContent.trim().toLowerCase() : "";
      var show = norm === "tất cả" || st.indexOf(norm) !== -1 ||
        (norm === "cần fix" && st.indexOf("cần fix") !== -1);
      tr.style.display = show ? "" : "none";
    });
  }

  /* ---- Nox-1 chat ---- */
  function chatPanel() {
    var chips = ["Duyệt 16 bài blog", "Fix Telegram 401", "Gen mô tả SP thiếu", "Báo cáo CWV"];
    var p = document.createElement("div");
    p.className = "nox-panel"; p.setAttribute("role", "dialog");
    p.innerHTML =
      '<div class="nox-head"><div class="nox-ava"><i class="ic" data-icon="sparkles"></i></div>' +
      '<div style="min-width:0"><h4>Nox-1 <i class="ic heart" data-icon="heart"></i></h4>' +
      '<p><i></i>Trợ lý vận hành · trực tuyến</p></div>' +
      '<button class="nox-close" aria-label="Đóng"><i class="ic" data-icon="x"></i></button></div>' +
      '<div class="nox-body" id="nox-body"><div class="nox-msg bot">Chào chị 👋 Em là Nox-1. Sáng nay có 17 bài chờ duyệt và Telegram bot đang lỗi 401 — em xử lý phần nào trước ạ?</div>' +
      '<div class="nox-chips">' + chips.map(function (c) { return '<button class="nox-chip">' + c + "</button>"; }).join("") + "</div></div>" +
      '<div class="nox-foot"><input class="nox-input" placeholder="Nhắn cho Nox-1…"/>' +
      '<button class="nox-send" aria-label="Gửi"><i class="ic" data-icon="arrow-up"></i></button></div>';
    return p;
  }
  function send(panel, v) {
    var input = panel.querySelector(".nox-input"), val = (v || input.value).trim(); if (!val) return;
    var body = panel.querySelector("#nox-body"), c = body.querySelector(".nox-chips"); if (c) c.remove();
    var me = document.createElement("div"); me.className = "nox-msg me"; me.textContent = val; body.appendChild(me);
    input.value = ""; body.scrollTop = body.scrollHeight;
    setTimeout(function () {
      var b = document.createElement("div"); b.className = "nox-msg bot";
      b.textContent = "Đã ghi nhận ✓ Em mở luồng xử lý cho “" + val + "” và cập nhật tiến độ ở Job Center nhé.";
      body.appendChild(b); body.scrollTop = body.scrollHeight;
    }, 600);
  }
  function toggleChat() {
    var fab = document.querySelector(".nox-fab"); if (!fab) return;
    var open = document.querySelector(".nox-panel");
    if (open) { open.remove(); fab.querySelector(".ic").setAttribute("data-icon", "message-circle-heart"); fab.querySelector(".ic").removeAttribute("data-ic-done"); hydrate(fab); return; }
    var p = chatPanel(); document.querySelector(".app").appendChild(p); hydrate(p);
    fab.querySelector(".ic").setAttribute("data-icon", "chevron-down"); fab.querySelector(".ic").removeAttribute("data-ic-done"); hydrate(fab);
    var ping = fab.querySelector(".ping"); if (ping) ping.style.display = "none";
    p.querySelector(".nox-send").addEventListener("click", function () { send(p); });
    p.querySelector(".nox-input").addEventListener("keydown", function (e) { if (e.key === "Enter") send(p); });
    p.querySelectorAll(".nox-chip").forEach(function (b) { b.addEventListener("click", function () { send(p, b.textContent); }); });
    p.querySelector(".nox-close").addEventListener("click", toggleChat);
  }

  /* ---- global click delegation ---- */
  function wire() {
    document.addEventListener("click", function (e) {
      var t = e.target;

      // page nav (sidebar)
      var nav = t.closest(".nav-item, .nav-sub");
      if (nav && !nav.querySelector(".nav-chevron")) {
        if (nav.tagName === "A" && nav.getAttribute("href")) return; // link thật → điều hướng tự nhiên
        var label = (nav.querySelector("span") || nav).textContent.trim();
        if (NAV[label]) { location.href = NAV[label]; return; }
      }
      // collapsible group
      var col = t.closest(".nav-item");
      if (col && col.querySelector(".nav-chevron")) {
        col.classList.toggle("open");
        var kids = col.nextElementSibling;
        if (kids && kids.classList.contains("nav-children")) kids.classList.toggle("open");
        return;
      }
      // KPI style
      var seg = t.closest(".seg button");
      if (seg) {
        var m = seg.textContent.trim();
        setKpi(m.indexOf("Dịu") > -1 ? "soft" : m.indexOf("Đơn") > -1 ? "mono" : "gradient", seg);
        return;
      }
      // table filters (dashboard .tbl-filter, list .chipf rows are separate)
      var chip = t.closest(".tbl-filter button, .dtable .tbl-filter button");
      if (chip) {
        chip.parentNode.querySelectorAll("button").forEach(function (b) { b.classList.toggle("on", b === chip); });
        filterRows(chip.closest(".tbl-wrap"), chip.textContent.trim());
        return;
      }
      // tier select
      var tier = t.closest(".tier-card");
      if (tier) { tier.classList.toggle("active"); return; }
      // alert dismiss
      if (t.closest(".alerts .icon-btn")) { var a = t.closest(".alerts"); if (a) a.style.display = "none"; return; }
      // chat
      if (t.closest(".nox-fab")) { toggleChat(); return; }
    });
  }

  function init() { hydrate(); wire(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  window.Sintech = { hydrate: hydrate };
})();
