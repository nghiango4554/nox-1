/* Tracking Audit dashboard — chỉ ở /seo/tracking. Đọc /api/tracking/*. KHÔNG gọi GA4 từ browser. */
(function () {
  "use strict";
  var app = document.getElementById("trk-app");
  if (!app) return;
  function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function nf(n){return n==null?"—":Number(n).toLocaleString("vi-VN");}
  function pill(c,t,tip){return '<span class="trk-pill '+c+'"'+(tip?' title="'+esc(tip)+'"':'')+'>'+esc(t)+"</span>";}
  function kpi(l,v){return '<div class="trk-kpi"><div class="v">'+esc(v==null?"—":v)+'</div><div class="l">'+esc(l)+"</div></div>";}
  function get(u){return fetch(u).then(function(r){return r.json();});}
  function hpct(h){return h&&h.percent!=null?h.percent+"%":"—";}
  function hpill(h){var p=h&&h.percent;var c=p==null?"b-gray":(p>=80?"b-ok":(p>=1?"b-warn":"b-err"));return pill(c,hpct(h));}

  var SRC = {gtm:["b-info","GTM"],theme:["b-info","Theme"],backend:["b-info","Backend"],ads_import:["b-gray","Ads import"],auto:["b-gray","Tự động"],unknown:["b-warn","Chưa rõ"]};
  var CAT = {ecommerce:"Ecommerce",lead:"Lead",support_contact:"Liên hệ",build_pc:"Build PC",custom_unknown:"Tùy chỉnh?",automatic:"Tự động"};
  var FST = {open:["b-warn","Đang mở"],resolved:["b-ok","Đã xử lý"],snoozed:["b-gray","Tạm hoãn"]};
  function srcBadge(s){var m=SRC[s]||["b-gray",s];return pill(m[0],m[1]);}
  function fStatus(s){var m=FST[s]||["b-gray",s];return pill(m[0],m[1]);}
  function statusBadge(s){return s==="detected"?pill("b-ok","Có data"):pill("b-warn","Chưa thấy");}
  function prioBadge(p){var c={P0:"b-err",P1:"b-warn",P2:"b-info",P3:"b-gray"}[p]||"b-gray";return pill(c,p);}
  function sevBadge(p){var c={P0:"b-err",P1:"b-warn",P2:"b-info",P3:"b-gray"}[p]||"b-gray";return pill(c,"mức "+p);}

  function render(st, ev, fnd, fn) {
    var pc = st.priority_counts || {};
    var html = '<div class="trk-card"><div class="trk-kpis">'
      + kpi("Đang đo", st.detected_events) + kpi("Kỳ vọng", st.expected_events) + kpi("Thiếu", st.missing_events)
      + kpi("Vấn đề đang mở", st.open_findings)
      + kpi("Sức khỏe Ecommerce", hpct(st.ecommerce_health)) + kpi("Sức khỏe Lead", hpct(st.lead_health))
      + kpi("Sức khỏe Liên hệ", hpct(st.contact_health)) + kpi("Sức khỏe Build PC", hpct(st.build_pc_health))
      + '</div><div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">'
      + prioBadge("P0")+" "+nf(pc.P0)+" &nbsp; "+prioBadge("P1")+" "+nf(pc.P1)+" &nbsp; "+prioBadge("P2")+" "+nf(pc.P2)+" &nbsp; "+prioBadge("P3")+" "+nf(pc.P3)
      + '<span style="margin-left:auto;font-size:11px;color:var(--text-muted,#94a3b8)">Dữ liệu sự kiện mới nhất: '+esc(st.event_data_latest_date||"—")
      + (st.last_audit?(" · audit "+esc(st.last_audit.status||"")+" "+esc(st.last_audit.finished_at||"")):" · chưa chạy audit")+"</span></div>"
      + (st.warning||[]).map(function(w){return '<div style="font-size:11px;color:#fbbf24;margin-top:5px">⚠ '+esc(w)+"</div>";}).join("")
      + "</div>";

    // funnel
    var steps = (fn && fn.steps) || [];
    var maxc = Math.max.apply(null, steps.map(function(s){return s.count||0;}).concat([1]));
    html += '<div class="trk-sec">🛒 Phễu chuyển đổi Ecommerce (28 ngày · tương đối)</div><div class="trk-card">'
      + steps.map(function(s){
          var w = s.count?Math.max(2,Math.round(s.count/maxc*100)):0;
          return '<div style="margin-bottom:7px"><div style="display:flex;justify-content:space-between;font-size:12px"><span>'+esc(s.event)+(s.present?"":" "+pill("b-warn","chưa thấy"))+'</span><span>'+nf(s.count)+'</span></div>'
            +'<div class="trk-funnel-bar"><div class="trk-funnel-fill" style="width:'+w+'%"></div></div></div>';
        }).join("") + "</div>";

    // findings
    var fr = (fnd && fnd.data) || [];
    html += '<div class="trk-sec">🚩 Vấn đề phát hiện ('+fr.length+')</div><div class="trk-card trk-tblwrap">'
      + (fr.length? '<table class="trk-tbl"><thead><tr><th>Ưu tiên làm</th><th>Mức độ</th><th>Vấn đề</th><th>Nhóm</th><th>Trạng thái</th><th>Lần cuối</th><th>Thao tác</th></tr></thead><tbody>'
        + fr.map(function(f){
            return "<tr><td>"+prioBadge(f.implementation_priority)+"</td><td>"+sevBadge(f.severity)+"</td><td><b>"+esc(f.title)+"</b><div style='font-size:11px;color:var(--text-muted,#94a3b8);white-space:normal;max-width:380px'>"+esc(f.description)+"</div></td>"
              +"<td>"+esc(CAT[f.category]||f.category)+"</td><td>"+fStatus(f.status)+"</td><td>"+esc(f.last_seen_at||"—")+"</td>"
              +"<td>"+(f.status==="open"
                ? '<button class="trk-btn" data-fres="'+f.id+'">Xử lý xong</button> <button class="trk-btn" data-fsnz="'+f.id+'">Tạm hoãn</button>'
                : '<button class="trk-btn" data-frop="'+f.id+'">Mở lại</button>')+"</td></tr>";
          }).join("")+"</tbody></table>"
        : '<div style="color:var(--text-muted,#94a3b8);font-size:12px">Chưa có vấn đề nào — bấm Chạy audit.</div>') + "</div>";

    // catalog
    var er = (ev && ev.data) || [];
    html += '<div class="trk-sec">📋 Danh mục sự kiện · Event Catalog ('+er.length+')</div><div class="trk-card trk-tblwrap">'
      + '<table class="trk-tbl"><thead><tr><th>Event</th><th>Nhóm</th><th class="num">Số lần 28 ngày</th><th class="num">Người dùng</th><th>Lần cuối</th><th>Nguồn</th><th>Kỳ vọng</th><th>Key event</th><th>Trạng thái</th><th>Ghi chú</th></tr></thead><tbody>'
      + er.map(function(r){
          return "<tr><td><code>"+esc(r.event_name)+"</code></td><td>"+esc(CAT[r.category]||r.category)+"</td>"
            +'<td class="num">'+nf(r.count_28d)+'</td><td class="num">'+nf(r.users_28d)+"</td><td>"+esc(r.last_seen||"—")+"</td>"
            +"<td>"+srcBadge(r.source_type)+"</td><td>"+(r.expected?"✓":"—")+"</td><td>"+(r.key_event_recommended?pill("b-info","nên mark"):"—")+"</td>"
            +"<td>"+statusBadge(r.source_status)+"</td><td style='white-space:normal;max-width:200px;font-size:11px;color:var(--text-muted,#94a3b8)'>"+esc(r.note||"")+"</td></tr>";
        }).join("")+"</tbody></table></div>";

    app.innerHTML = html;
    bindFindings();
  }

  function act(url, id) {
    fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"}).then(function(){ load(); });
  }
  function bindFindings() {
    [["data-fres","/resolve"],["data-frop","/reopen"],["data-fsnz","/snooze"]].forEach(function(p){
      Array.prototype.forEach.call(app.querySelectorAll("["+p[0]+"]"), function(b){
        b.addEventListener("click", function(){ act("/api/tracking/findings/"+b.getAttribute(p[0])+p[1]); });
      });
    });
  }

  function load() {
    Promise.all([get("/api/tracking/status"), get("/api/tracking/events"), get("/api/tracking/findings"), get("/api/tracking/funnel")])
      .then(function(r){ render(r[0],r[1],r[2],r[3]); })
      .catch(function(){ app.innerHTML='<div class="trk-card" style="color:#f87171">Không tải được Tracking Audit.</div>'; });
  }

  var POLL=null;
  function runAudit() {
    var b=document.getElementById("trk-audit"); if(b){b.disabled=true;b.textContent="⏳ Đang audit…";}
    fetch("/api/tracking/audit",{method:"POST"}).then(function(r){return r.json();}).then(function(){
      if(POLL) return;
      POLL=setInterval(function(){ if(document.hidden)return; get("/api/tracking/status").then(function(s){ if(!s.is_running){clearInterval(POLL);POLL=null;if(b){b.disabled=false;b.textContent="🔄 Chạy audit";}load();} }); },4000);
    }).catch(function(){ if(b){b.disabled=false;b.textContent="🔄 Chạy audit";} });
  }
  var ab=document.getElementById("trk-audit"); if(ab) ab.addEventListener("click", runAudit);
  load();
})();
