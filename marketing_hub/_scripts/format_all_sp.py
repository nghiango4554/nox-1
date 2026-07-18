# -*- coding: utf-8 -*-
"""Format ALL SP live: reformat() moi SP tru COMBO PC + SP an. Backup + guard + retry."""
import sys, os, re, json, time
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import haravan_client as hc
import reformat_product_desc as rf

OUT = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs")
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
BK = open(OUT / f"_format_all_backup_{stamp}.jsonl", "w", encoding="utf-8")
LOG = open(OUT / f"_format_all_log_{stamp}.txt", "w", encoding="utf-8")
def log(m):
    print(m, flush=True); LOG.write(m + "\n"); LOG.flush()

def excluded(p):
    t = (p.get("product_type") or "").upper()
    if "COMBO" in t: return "combo_pc"
    if not p.get("published_at"): return "an"
    return None

def txt(h): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()

log(f"=== FORMAT ALL SP · start {stamp} ===")
ok = skip_combo = skip_an = skip_short = skip_suspect = skip_nochange = fail = 0
page = 1
while True:
    try:
        prods = hc.list_products(page=page, limit=250,
                                 fields="id,title,product_type,published_at,body_html")
    except Exception as e:
        log(f"  list page {page} ERR {str(e)[:80]} — nghi 5s"); time.sleep(5); continue
    if not prods: break
    for p in prods:
        ex = excluded(p)
        if ex == "combo_pc": skip_combo += 1; continue
        if ex == "an": skip_an += 1; continue
        old = p.get("body_html") or ""
        if len(old) < 200: skip_short += 1; continue
        try: new = rf.reformat(old)
        except Exception as e: fail += 1; log(f"  #{p['id']} reformat ERR {str(e)[:60]}"); continue
        if new == old: skip_nochange += 1; continue
        ot, nt = txt(old), txt(new)
        if ot and len(nt) < 0.95 * len(ot):
            skip_suspect += 1
            log(f"  ⚠️ SKIP mat noi dung #{p['id']} text {len(ot)}->{len(nt)} · {p.get('title','')[:40]}")
            continue
        BK.write(json.dumps({"id": p["id"], "old": old}, ensure_ascii=False) + "\n"); BK.flush()
        pid = p["id"]; done = False
        for attempt in range(5):
            try:
                r = hc._request("PUT", f"/products/{pid}.json",
                                payload={"product": {"id": pid, "body_html": new}})
                if r.get("product", {}).get("id") == pid: ok += 1; done = True; break
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    time.sleep(8 + attempt * 5); continue
                log(f"  #{pid} PUT ERR {str(e)[:60]}"); break
        if not done and attempt == 4: log(f"  #{pid} PUT fail sau 5 lan")
        if not done: fail += 1
        time.sleep(0.35)
        if ok % 50 == 0 and ok: log(f"  ...da format {ok} SP (page {page})")
    page += 1
log(f"\n=== XONG ===")
log(f"OK format+push: {ok}")
log(f"SKIP combo PC: {skip_combo} | SP an: {skip_an} | body ngan: {skip_short} | khong doi: {skip_nochange} | nghi mat noi dung: {skip_suspect}")
log(f"FAIL: {fail}")
log(f"Backup: _format_all_backup_{stamp}.jsonl")
BK.close(); LOG.close()
