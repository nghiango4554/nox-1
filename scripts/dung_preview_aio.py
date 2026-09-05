# -*- coding: utf-8 -*-
"""Dung trang preview AIO: moi SP 2 hang — hang tren 1 anh LON (ban moi),
hang duoi cac anh CU nho, bam vao phong to.

    python dung_preview_aio.py
"""
import io, json, os, glob, datetime, html as H

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
SC = (r"C:\Users\NGHIANGO\AppData\Local\Temp\claude\C--Users-NGHIANGO--openclaw-workspace"
      r"\88692c79-cb21-48e4-8955-050078970802\scratchpad")
STD = r"C:/Users/NGHIANGO/Desktop/Sintech-img/thumb_chuan/std"
OUT = os.path.join(WS, "nox-outputs", "preview_aio.html")

o = {x["stt"]: x for x in json.load(io.open(os.path.join(SC, "aio_data.json"), encoding="utf-8"))}
xong = sorted(int(os.path.basename(p).split("_")[2].split(".")[0])
              for p in glob.glob(os.path.join(WS, "nox-outputs", "aio_moi_*.png")))

khoi = []
for n in xong:
    x = o[n]
    d = os.path.join(STD, x["h"])
    man = json.load(io.open(os.path.join(d, "manifest.json"), encoding="utf-8"))
    cu = []
    for it in man:
        f = os.path.join(d, "%d.jpg" % it["idx"])
        if os.path.exists(f):
            cu.append('<img class="nho" loading="lazy" src="/thumbs/img/std/%s/%d.jpg?v=%d" '
                      'data-to="/thumbs/img/std/%s/%d.jpg?v=%d" title="idx %d — bấm để phóng to">'
                      % (x["h"], it["idx"], int(os.path.getmtime(f)),
                         x["h"], it["idx"], int(os.path.getmtime(f)), it["idx"]))
    moi_f = os.path.join(WS, "nox-outputs", "aio_moi_%02d.png" % n)
    v = int(os.path.getmtime(moi_f))
    khoi.append(
        '<section class="sp">'
        '<div class="dau"><span class="stt">%d</span><b>%s</b>'
        '<a href="https://sintech.vn/products/%s" target="_blank">live ↗</a></div>'
        '<div class="tren"><img class="lon" src="/preview/file/outputs/aio_moi_%02d.png?v=%d" '
        'data-to="/preview/file/outputs/aio_moi_%02d.png?v=%d" title="ảnh MỚI — bấm để phóng to"></div>'
        '<div class="nhan-cu">%d ảnh cũ trong kho — bấm để phóng to</div>'
        '<div class="duoi">%s</div>'
        '</section>'
        % (n, H.escape(x["ten"]), x["h"], n, v, n, v, len(cu), "".join(cu)))

CSS = """
body{background:#0f1319;color:#e6e9ef;font:14px/1.5 system-ui,Segoe UI,sans-serif;margin:0;padding:22px}
h1{font-size:21px;margin:0 0 4px}.sub{color:#8b98ab;font-size:13px;margin-bottom:18px}
.sp{background:#171c24;border-radius:12px;padding:14px 16px 18px;margin-bottom:18px;border:1px solid #232b36}
.dau{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap}
.stt{background:#111;color:#ffd400;font-weight:700;font-size:14px;padding:2px 9px;border-radius:6px}
.dau b{font-size:14.5px;font-weight:600}
.dau a{color:#3b82f6;text-decoration:none;font-size:12px}
.tren{background:#fff;border-radius:9px;padding:6px;display:flex;justify-content:center}
.lon{max-width:100%;max-height:460px;object-fit:contain;cursor:zoom-in;display:block}
.nhan-cu{color:#7f8b9c;font-size:12px;margin:12px 0 7px}
.duoi{display:flex;gap:9px;flex-wrap:wrap}
.nho{width:120px;height:120px;object-fit:contain;background:#fff;border-radius:7px;padding:4px;
     cursor:zoom-in;border:2px solid #2a3341}
.nho:hover{border-color:#3b82f6}
#phu{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;align-items:center;
     justify-content:center;z-index:99;cursor:zoom-out;padding:24px}
#phu img{max-width:96vw;max-height:94vh;object-fit:contain;background:#fff;border-radius:9px}
#dong{position:fixed;top:14px;right:20px;color:#fff;font-size:30px;font-weight:700;cursor:pointer;z-index:100}
"""
JS = """
const phu=document.getElementById('phu'), pimg=phu.querySelector('img');
document.addEventListener('click',e=>{
  const t=e.target;
  if(t.dataset && t.dataset.to){ pimg.src=t.dataset.to; phu.style.display='flex'; return; }
  if(t===phu||t.id==='dong'||t===pimg){ phu.style.display='none'; }
});
document.addEventListener('keydown',e=>{ if(e.key==='Escape') phu.style.display='none'; });
"""
doc = ('<!doctype html><meta charset="utf-8"><title>Preview tản AIO</title>'
       '<style>%s</style>'
       '<h1>Preview ảnh tản nước AIO — %d sản phẩm</h1>'
       '<div class="sub">Hàng trên: ảnh MỚI (to). Hàng dưới: ảnh CŨ trong kho. '
       'Bấm bất kỳ ảnh nào để phóng to, bấm nền hoặc Esc để đóng. Cập nhật %s.</div>'
       '%s'
       '<div id="phu"><img></div><div id="dong" style="display:none">×</div>'
       '<script>%s</script>'
       % (CSS, len(xong), datetime.datetime.now().strftime("%H:%M %d/%m"), "".join(khoi), JS))
io.open(OUT, "w", encoding="utf-8").write(doc)
print("da dung %d SP -> %s (%d byte)" % (len(xong), OUT, len(doc.encode())))
