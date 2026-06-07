/* Task Center — /tasks. Đọc /api/tasks. */
(function () {
  "use strict";
  var app = document.getElementById("tc-app");
  if (!app) return;
  function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function get(u){return fetch(u).then(function(r){return r.json();});}
  function pill(c,t){return '<span class="tc-pill '+c+'">'+esc(t)+"</span>";}
  function prio(p){var c={P0:"b-err",P1:"b-warn",P2:"b-info",P3:"b-gray"}[p]||"b-gray";return pill(c,p||"—");}
  function sev(p){var c={P0:"b-err",P1:"b-warn",P2:"b-info",P3:"b-gray"}[p]||"b-gray";return pill(c,"mức "+(p||"—"));}
  var TST = {open:["b-warn","Đang mở"],resolved:["b-ok","Đã xử lý"],snoozed:["b-gray","Tạm hoãn"]};
  function tStatus(s){var m=TST[s]||["b-gray",s];return pill(m[0],m[1]);}

  var FILTER = {status:"open"};
  var TABS = [["open","Đang mở"],["all","Tất cả"],["snoozed","Tạm hoãn"],["resolved","Đã xử lý"],
    ["P0","P0"],["P1","P1"],["P2","P2"],["P3","P3"],["tracking","Tracking"],["sync","Đồng bộ"]];

  function qstr() {
    var p = [];
    if (FILTER.status && ["open","snoozed","resolved"].indexOf(FILTER.status)>=0) p.push("status="+FILTER.status);
    if (FILTER.priority) p.push("priority="+FILTER.priority);
    if (FILTER.type) p.push("type="+FILTER.type);
    return p.length?"?"+p.join("&"):"";
  }
  function setTab(key) {
    FILTER = {};
    if (["open","all","snoozed","resolved"].indexOf(key)>=0) { if(key!=="all") FILTER.status=key; }
    else if (/^P[0-3]$/.test(key)) { FILTER.status="open"; FILTER.priority=key; }
    else { FILTER.status="open"; FILTER.type=key; }
    FILTER._active = key;
    load();
  }

  function render(res) {
    var c = res.counts || {};
    var active = FILTER._active || "open";
    var tabs = '<div class="tc-tabs">' + TABS.map(function(t){
      var n = c[t[0]]; var lbl = t[1] + (n!=null?" ("+n+")":"");
      return '<button class="tc-tab'+(active===t[0]?" on":"")+'" data-tab="'+t[0]+'">'+esc(lbl)+"</button>";
    }).join("") + "</div>";
    var rows = res.data || [];
    var body = rows.length ? rows.map(function(t){
      var snap = ""; try { snap = JSON.stringify(JSON.parse(t.metric_snapshot_json||"{}")); } catch(e){}
      return '<div class="tc-task"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
        + prio(t.implementation_priority) + sev(t.severity)
        + pill("b-gray", t.task_type || t.source || "—")
        + '<b style="font-size:13px">'+esc(t.title)+"</b>"
        + '<span style="margin-left:auto">'+tStatus(t.status)+"</span></div>"
        + '<div style="font-size:12px;color:var(--text-muted,#94a3b8);margin:6px 0">'+esc(t.description||"")+"</div>"
        + '<div style="display:flex;gap:6px">'
        + (t.status==="open"
            ? '<button class="tc-btn" data-res="'+t.id+'">Xử lý xong</button><button class="tc-btn" data-snz="'+t.id+'">Tạm hoãn</button>'
            : '<button class="tc-btn" data-rop="'+t.id+'">Mở lại</button>')
        + '<span style="margin-left:auto;font-size:10.5px;color:var(--text-muted,#94a3b8)">'+esc(t.updated_at||"")+"</span></div></div>";
    }).join("") : '<div class="tc-card" style="color:var(--text-muted,#94a3b8);font-size:12px">Chưa có việc nào — bấm Tạo task.</div>';
    app.innerHTML = tabs + '<div class="tc-card">' + body + "</div>";
    Array.prototype.forEach.call(app.querySelectorAll("[data-tab]"), function(b){ b.addEventListener("click", function(){ setTab(b.getAttribute("data-tab")); }); });
    [["data-res","/resolve"],["data-rop","/reopen"],["data-snz","/snooze"]].forEach(function(p){
      Array.prototype.forEach.call(app.querySelectorAll("["+p[0]+"]"), function(b){
        b.addEventListener("click", function(){ fetch("/api/tasks/"+b.getAttribute(p[0])+p[1],{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}).then(load); });
      });
    });
  }

  function load() { get("/api/tasks"+qstr()).then(render).catch(function(){ app.innerHTML='<div class="tc-card" style="color:#f87171">Không tải được Task Center.</div>'; }); }

  var POLL=null;
  var gb=document.getElementById("tc-gen");
  if(gb) gb.addEventListener("click", function(){
    gb.disabled=true; gb.textContent="⏳ Đang tạo…";
    fetch("/api/tasks/generate",{method:"POST"}).then(function(r){return r.json();}).then(function(){
      if(POLL) return;
      POLL=setInterval(function(){ if(document.hidden)return; get("/api/tasks?status=open").then(function(s){ if(!s.is_running){clearInterval(POLL);POLL=null;gb.disabled=false;gb.textContent="⚙️ Tạo task";load();} }); },3000);
    }).catch(function(){ gb.disabled=false; gb.textContent="⚙️ Tạo task"; });
  });
  load();
})();
