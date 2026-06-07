/* GSC API source & data health — chỉ chạy ở /seo/gsc. Đọc /api/gsc/status, KHÔNG gọi GSC từ browser. */
(function () {
  "use strict";
  var root = document.getElementById("gsc-health");
  if (!root) return;

  // CSS inj, dùng CSS var của theme
  var css = document.createElement("style");
  css.textContent =
    ".gh-card{background:var(--surface,#1a1a1a);border:1px solid var(--border,rgba(255,255,255,.1));border-radius:12px;padding:16px 18px;margin-bottom:16px}" +
    ".gh-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}" +
    ".gh-pill{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600}" +
    ".b-ok{background:rgba(34,197,94,.15);color:#4ade80}.b-warn{background:rgba(245,158,11,.15);color:#fbbf24}" +
    ".b-err{background:rgba(239,68,68,.15);color:#f87171}.b-gray{background:rgba(148,163,184,.15);color:#94a3b8}" +
    ".b-info{background:rgba(59,130,246,.15);color:#60a5fa}" +
    ".gh-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:12px}" +
    ".gh-kpi{background:rgba(255,255,255,.03);border:1px solid var(--border,rgba(255,255,255,.08));border-radius:9px;padding:10px 12px}" +
    ".gh-kpi .v{font-size:15px;font-weight:700;line-height:1.2}.gh-kpi .l{font-size:10.5px;color:var(--text-muted,#94a3b8);text-transform:uppercase;letter-spacing:.3px;margin-top:4px}" +
    ".gh-cov{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}@media(max-width:640px){.gh-cov{grid-template-columns:1fr}}" +
    ".gh-bar-bg{height:12px;background:rgba(59,130,246,.18);border-radius:5px;overflow:hidden}.gh-bar-fill{height:100%;background:#3b82f6}" +
    ".gh-note{font-size:11.5px;color:var(--text-muted,#94a3b8);margin-top:10px;line-height:1.5}" +
    ".gh-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}" +
    ".gh-btn{border:1px solid var(--border,rgba(255,255,255,.15));border-radius:8px;padding:8px 14px;font-size:13px;cursor:pointer;background:var(--surface,#111);color:inherit}" +
    ".gh-btn.primary{background:var(--accent,#7c3aed);color:#fff;border-color:transparent;font-weight:600}" +
    ".gh-btn:disabled{opacity:.5;cursor:default}.gh-sub{font-size:11px;color:var(--text-muted,#94a3b8);width:100%}";
  document.head.appendChild(css);

  function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function pill(cls,t){return '<span class="gh-pill '+cls+'">'+esc(t)+"</span>";}
  function kpi(l,v){return '<div class="gh-kpi"><div class="v">'+esc(v==null?"—":v)+'</div><div class="l">'+esc(l)+"</div></div>";}
  function covBar(l,pct){var raw=(pct==null?"—":pct+"%");var w=Math.min(100,Math.max(0,pct||0));
    return '<div style="margin-bottom:8px"><div style="font-size:11px;color:var(--text-muted,#94a3b8)">'+l+': <b>'+raw+'</b></div>'
      +'<div class="gh-bar-bg" title="raw '+raw+'"><div class="gh-bar-fill" style="width:'+w+'%"></div></div></div>';}

  function get(u){return fetch(u).then(function(r){return r.json();});}

  var POLL=null, syncing=false;
  function render(st){
    // ── state badge ──
    var apiBadge, stateMsg="";
    var a=st.api_status, ec=st.error_code;
    if(a==="ok"){apiBadge=pill("b-ok","API sẵn sàng");}
    else if(a==="ready"){apiBadge=pill("b-info","API ready (chưa probe)");}
    else if(a==="not_configured"){apiBadge=pill("b-gray","Chưa cấu hình");stateMsg="Chưa cấu hình OAuth GSC API. Chạy: <code>py -3.12 marketing_hub/_scripts/gsc_api_auth.py</code>";}
    else if(a==="token_missing"){apiBadge=pill("b-gray","Thiếu token");stateMsg="Chưa cấu hình OAuth GSC API — chạy auth script để đăng nhập.";}
    else if(a==="error"){
      apiBadge=pill("b-err","API lỗi: "+esc(ec||""));
      var m={token_expired:"Token GSC API hết hạn hoặc bị thu hồi — chạy lại OAuth interactive.",
             reconnect_required:"Token GSC API cần reconnect — chạy lại OAuth interactive.",
             permission_denied:"Tài khoản Google chưa có quyền đọc property GSC.",
             wrong_property:"Sai Search Console property hoặc tài khoản chưa thấy property.",
             quota_exceeded:"Vượt quota Search Console API — thử lại sau (cache cũ vẫn còn).",
             temporary_network:"Lỗi tạm thời phía Google — fallback Google Sheet vẫn còn."};
      stateMsg=m[ec]||esc(st.last_error_message_safe||"Lỗi API.");
    } else {apiBadge=pill("b-gray",esc(a));}

    var oauthMap={connected:["b-ok","OAuth kết nối"],expired:["b-err","OAuth hết hạn"],missing:["b-gray","OAuth thiếu"],
                  no_permission:["b-err","Không có quyền"],wrong_property:["b-err","Sai property"],
                  quota_exceeded:["b-warn","Quota"],not_configured:["b-gray","Chưa cấu hình"],error:["b-err","OAuth lỗi"]};
    var ob=oauthMap[st.oauth_status]||["b-gray",st.oauth_status||"—"];

    // data lag warning
    var lagPill = (st.data_age_days!=null && st.data_age_days>3) ? " "+pill("b-warn","Độ trễ "+st.data_age_days+" ngày") : "";

    var html='<div class="gh-card">'
      +'<div class="gh-row" style="margin-bottom:6px"><b style="font-size:14px">🔵 Nguồn dữ liệu &amp; Data Health</b>'
      +' '+apiBadge+' '+pill(ob[0],ob[1])+lagPill+'</div>'
      +'<div class="gh-row" style="font-size:12px;color:var(--text-muted,#94a3b8)">'
      +pill("b-info","Nguồn chính: Search Console API")
      +pill(st.fallback_available?"b-gray":"b-gray","Fallback: Google Sheet snapshot"+(st.fallback_available?"":" (chưa có)"))
      +pill("b-gray","Coverage mode: API top rows")
      +pill("b-warn","Coverage complete: Không")
      +pill("b-gray","Search type: "+((st.search_types||["web"]).join(",")))
      +'</div>';

    if(stateMsg){html+='<div class="gh-note" style="color:#fbbf24">⚠ '+stateMsg+'</div>';}

    // ── KPI health ──
    var ls=st.last_sync||{};
    html+='<div class="gh-kpis">'
      +kpi("API status",st.api_status)
      +kpi("OAuth",st.oauth_status)
      +kpi("Latest available",st.latest_available_date)
      +kpi("Data age",st.data_age_days!=null?st.data_age_days+" ngày":"—")
      +kpi("Cache age",st.cache_age_days!=null?st.cache_age_days+" ngày":"—")
      +kpi("Last success",st.last_success_at||"—")
      +kpi("Last failure",st.last_failure_at||"—")
      +kpi("Rows written",st.rows_written!=null?Number(st.rows_written).toLocaleString("vi-VN"):"—")
      +kpi("Coverage mode",st.coverage_mode)
      +'</div>';

    // ── coverage ──
    html+='<div class="gh-cov"><div>'
      +covBar("Page clicks coverage",st.page_click_coverage_percent)
      +covBar("Page impressions coverage",st.page_impression_coverage_percent)+'</div><div>'
      +covBar("Query clicks coverage",st.query_click_coverage_percent)
      +covBar("Query impressions coverage",st.query_impression_coverage_percent)+'</div></div>'
      +'<div class="gh-note">Detail page/query được tính từ top rows Search Analytics API. Một phần long-tail có thể chưa xuất hiện. Summary property-level đáng tin hơn detail.</div>';

    // ── timezone note ──
    html+='<div class="gh-note">🕒 Search Console dùng ngày theo PT. GA4 hệ thống dùng Asia/Ho_Chi_Minh. Khi ghép theo ngày, số liệu có thể lệch nhẹ ở ranh giới ngày. (Chưa ghép daily trong batch này.)</div>';

    // ── actions ──
    var running=st.sync_running;
    html+='<div class="gh-actions">'
      +'<button class="gh-btn primary" id="gh-api-refresh"'+(running?" disabled":"")+'>'+(running?"⏳ Đang đồng bộ…":"🔄 Đồng bộ từ Search Console API")+'</button>'
      +'<button class="gh-btn" id="gh-sheet-refresh">📁 Làm mới từ Google Sheet fallback</button>'
      +'<span class="gh-sub">Sheet fallback chỉ dùng khi API lỗi hoặc cần đọc lại snapshot Sheet.</span>'
      +'</div></div>';

    root.innerHTML=html;
    var ab=document.getElementById("gh-api-refresh");
    if(ab) ab.addEventListener("click",apiRefresh);
    var sb=document.getElementById("gh-sheet-refresh");
    if(sb) sb.addEventListener("click",sheetRefresh);

    if(running && !POLL){ startPoll(); }
    if(!running && POLL){ stopPoll(); }
  }

  function load(probe){ get("/api/gsc/status"+(probe?"?probe=1":"")).then(render).catch(function(){ root.innerHTML='<div class="gh-card" style="color:#f87171">Không tải được trạng thái GSC API.</div>'; }); }

  function apiRefresh(){
    var b=document.getElementById("gh-api-refresh");
    b.disabled=true; b.textContent="⏳ Đang đồng bộ…"; syncing=true;
    fetch("/api/gsc/refresh",{method:"POST"}).then(function(r){return r.json().then(function(j){j._http=r.status;return j;});})
      .then(function(){ startPoll(); }).catch(function(){ b.disabled=false; b.textContent="🔄 Đồng bộ từ Search Console API"; });
  }
  function sheetRefresh(){
    var b=document.getElementById("gh-sheet-refresh");
    b.disabled=true; b.textContent="⏳ Đang đọc Sheet…";
    fetch("/seo/gsc/refresh",{method:"POST"}).then(function(){ setTimeout(function(){location.reload();},1500); })
      .catch(function(){ b.disabled=false; b.textContent="📁 Làm mới từ Google Sheet fallback"; });
  }

  function startPoll(){
    if(POLL) return;
    POLL=setInterval(function(){
      if(document.hidden) return;             // dừng poll khi tab ẩn
      get("/api/gsc/status").then(function(st){
        if(!st.sync_running){ stopPoll(); syncing=false; render(st); }
        else { render(st); }
      });
    },7000);
  }
  function stopPoll(){ if(POLL){clearInterval(POLL);POLL=null;} }

  // initial load (probe 1 lần để lấy api/oauth status thật)
  load(true);
})();
