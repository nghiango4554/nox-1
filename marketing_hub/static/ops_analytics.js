/* Analytics Ops — /ops/analytics. Đọc /api/ops/analytics-daily/status. */
(function () {
  "use strict";
  var app = document.getElementById("ops-app");
  if (!app) return;
  function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function get(u){return fetch(u).then(function(r){return r.json();});}
  function pill(c,t){return '<span class="ops-pill '+c+'">'+esc(t)+"</span>";}
  function stStep(s){return {ok:["b-ok","✓ xong"],error:["b-err","✗ lỗi"],skipped:["b-gray","— bỏ qua"]}[s]||["b-gray",s];}

  function render(st) {
    var last = st.last_run || {};
    var steps = last.steps || [];
    var pmap = {ga4_incremental_sync:"GA4 sync (incremental)",gsc_api_incremental_sync:"GSC API sync (incremental)",
      gsc_ga4_daily_join:"Ghép GSC × GA4 (daily)",tracking_audit:"Tracking audit",task_generate:"Tạo task",alert:"Telegram alert"};
    var html = '<div class="ops-card"><div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">'
      + pill(st.enabled?"b-ok":"b-gray", st.enabled?"Scheduler bật":"Scheduler tắt")
      + pill("b-info", "Lịch: "+esc(st.schedule))
      + pill(st.telegram_alert_enabled?"b-ok":"b-gray", "Telegram alert "+(st.telegram_alert_enabled?"bật":"tắt"))
      + (st.is_running?pill("b-warn","⏳ Đang chạy"):"")
      + '</div><div style="font-size:11px;color:var(--text-muted,#94a3b8);margin-top:8px">Pipeline tuần tự: GA4 → GSC API → daily join → Tracking audit → Task generate → Alert P0/P1 (im lặng khi OK). Fallback Sheet KHÔNG trộn vào daily join.</div></div>';

    html += '<div class="ops-card"><div style="font-size:13px;font-weight:700;margin-bottom:9px">Lần chạy gần nhất '
      + (last.status?pill(last.status==="success"?"b-ok":"b-err", last.status):pill("b-gray","chưa chạy"))
      + (last.duration_seconds!=null?' <span style="font-size:11px;color:var(--text-muted,#94a3b8)">'+last.duration_seconds+'s · '+esc(last.finished_at||"")+'</span>':'')
      + (last.alert_sent?" "+pill("b-info","alert đã gửi"):"") + "</div>";
    var pipe = st.pipeline || [];
    if (steps.length) {
      html += pipe.map(function(name){
        var s = steps.filter(function(x){return x.step===name;})[0];
        var b = s?stStep(s.status):["b-gray","—"];
        return '<div class="ops-step"><span class="nm">'+esc(pmap[name]||name)+'</span>'
          + (s&&s.error?'<span style="font-size:11px;color:#f87171">'+esc(s.error)+'</span>':'')
          + '<span class="dur">'+(s&&s.duration_seconds!=null?s.duration_seconds+"s":"")+'</span>'+pill(b[0],b[1])+"</div>";
      }).join("");
      html += '<div style="font-size:12px;color:var(--text-muted,#94a3b8);margin-top:8px">P0 mới: <b>'+(last.new_p0||0)+'</b> · P1 mới: <b>'+(last.new_p1||0)+'</b> · step lỗi: <b>'+(last.failed_steps||0)+"</b></div>";
    } else {
      html += '<div style="color:var(--text-muted,#94a3b8);font-size:12px">Chưa có lần chạy nào — bấm Chạy pipeline.</div>';
    }
    html += "</div>";
    app.innerHTML = html;
  }

  function load(){ get("/api/ops/analytics-daily/status").then(render).catch(function(){ app.innerHTML='<div class="ops-card" style="color:#f87171">Không tải được Analytics Ops.</div>'; }); }

  var POLL=null;
  var rb=document.getElementById("ops-run");
  if(rb) rb.addEventListener("click", function(){
    rb.disabled=true; rb.textContent="⏳ Đang chạy…";
    fetch("/api/ops/analytics-daily/run",{method:"POST"}).then(function(r){return r.json();}).then(function(){
      if(POLL) return;
      POLL=setInterval(function(){ if(document.hidden)return; get("/api/ops/analytics-daily/status").then(function(s){ if(!s.is_running){clearInterval(POLL);POLL=null;rb.disabled=false;rb.textContent="▶️ Chạy pipeline";render(s);} }); },5000);
    }).catch(function(){ rb.disabled=false; rb.textContent="▶️ Chạy pipeline"; });
  });
  load();
})();
