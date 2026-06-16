# -*- coding: utf-8 -*-
"""Live insights: kéo data Google Search Console + GA4 trực tiếp qua OAuth.

Token nằm ở workspace/gsc/ (token.json = GSC, ga_token.json = GA4).
Cache kết quả vào data/insights_live.json để trang load nhanh; nút Refresh pull lại.
"""
import os
import json
import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent              # marketing_hub/
GSC_DIR = ROOT.parent.parent / "gsc"                # workspace/gsc/
CACHE_FILE = ROOT / "data" / "insights_live.json"

GSC_TOKEN = GSC_DIR / "token.json"
GA_TOKEN = GSC_DIR / "ga_token.json"
GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
GA_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

SITE = "sc-domain:sintech.vn"
GA_PROPERTY = "451866979"   # GA4 property sintech.vn (đang chạy)


# ─────────────────────── auth helpers ───────────────────────
def _creds(token_path: Path, scopes):
    creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _date_range(days=28, lag=2):
    end = datetime.date.today() - datetime.timedelta(days=lag)
    start = end - datetime.timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _prev_range(days=28, lag=2):
    end = datetime.date.today() - datetime.timedelta(days=lag + days)
    start = end - datetime.timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _pct(cur, prev):
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 1)


# ─────────────────────── GSC ───────────────────────
def pull_gsc(days=28):
    creds = _creds(GSC_TOKEN, GSC_SCOPES)
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    sd, ed = _date_range(days)
    psd, ped = _prev_range(days)

    def q(dims=None, limit=10, start=sd, end=ed):
        body = {"startDate": start, "endDate": end, "rowLimit": limit}
        if dims:
            body["dimensions"] = dims
        return svc.searchanalytics().query(siteUrl=SITE, body=body).execute().get("rows", [])

    def totals(start, end):
        rows = q(None, 1, start, end)
        if not rows:
            return {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}
        r = rows[0]
        return {"clicks": int(r["clicks"]), "impressions": int(r["impressions"]),
                "ctr": round(r["ctr"] * 100, 2), "position": round(r["position"], 1)}

    cur = totals(sd, ed)
    prev = totals(psd, ped)
    cur["clicks_delta"] = _pct(cur["clicks"], prev["clicks"])
    cur["impressions_delta"] = _pct(cur["impressions"], prev["impressions"])

    queries = [{"key": r["keys"][0], "clicks": int(r["clicks"]), "impressions": int(r["impressions"]),
                "ctr": round(r["ctr"] * 100, 1), "position": round(r["position"], 1)}
               for r in q(["query"], 25)]
    pages = [{"key": r["keys"][0], "clicks": int(r["clicks"]), "impressions": int(r["impressions"]),
              "ctr": round(r["ctr"] * 100, 1), "position": round(r["position"], 1)}
             for r in q(["page"], 25)]
    devices = [{"key": r["keys"][0], "clicks": int(r["clicks"]), "impressions": int(r["impressions"])}
               for r in q(["device"], 5)]

    return {"range": [sd, ed], "totals": cur, "queries": queries, "pages": pages, "devices": devices}


# ─────────────────────── GA4 ───────────────────────
def pull_ga(days=28):
    creds = _creds(GA_TOKEN, GA_SCOPES)
    data = build("analyticsdata", "v1beta", credentials=creds, cache_discovery=False)
    end = datetime.date.today() - datetime.timedelta(days=1)
    start = end - datetime.timedelta(days=days - 1)
    sd, ed = start.isoformat(), end.isoformat()
    pend = end - datetime.timedelta(days=days)
    pstart = pend - datetime.timedelta(days=days - 1)

    def report(dims, mets, limit=10, start=sd, end=ed, order_metric=None):
        body = {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": d} for d in dims],
            "metrics": [{"name": m} for m in mets],
            "limit": limit,
        }
        if order_metric:
            body["orderBys"] = [{"metric": {"metricName": order_metric}, "desc": True}]
        return data.properties().runReport(property="properties/%s" % GA_PROPERTY, body=body).execute()

    METS = ["sessions", "totalUsers", "screenPageViews", "conversions", "engagementRate"]

    def totals(start, end):
        r = report([], METS, 1, start, end)
        rows = r.get("rows", [])
        if not rows:
            return {m: 0 for m in METS}
        v = rows[0]["metricValues"]
        return {
            "sessions": int(float(v[0]["value"])),
            "totalUsers": int(float(v[1]["value"])),
            "screenPageViews": int(float(v[2]["value"])),
            "conversions": int(float(v[3]["value"])),
            "engagementRate": round(float(v[4]["value"]) * 100, 1),
        }

    cur = totals(sd, ed)
    prev = totals(pstart.isoformat(), pend.isoformat())
    cur["sessions_delta"] = _pct(cur["sessions"], prev["sessions"])
    cur["users_delta"] = _pct(cur["totalUsers"], prev["totalUsers"])

    channels = []
    for row in report(["sessionDefaultChannelGroup"], ["sessions", "totalUsers"], 12,
                       order_metric="sessions").get("rows", []):
        channels.append({"key": row["dimensionValues"][0]["value"],
                         "sessions": int(float(row["metricValues"][0]["value"])),
                         "users": int(float(row["metricValues"][1]["value"]))})

    pages = []
    for row in report(["pagePath"], ["screenPageViews", "totalUsers"], 20,
                      order_metric="screenPageViews").get("rows", []):
        pages.append({"key": row["dimensionValues"][0]["value"],
                      "views": int(float(row["metricValues"][0]["value"])),
                      "users": int(float(row["metricValues"][1]["value"]))})

    # daily trend (sessions) cho sparkline
    daily = []
    for row in report(["date"], ["sessions"], 60).get("rows", []):
        daily.append({"date": row["dimensionValues"][0]["value"],
                      "sessions": int(float(row["metricValues"][0]["value"]))})
    daily.sort(key=lambda x: x["date"])

    return {"range": [sd, ed], "totals": cur, "channels": channels, "pages": pages, "daily": daily}


# ─────────────────────── orchestration + cache ───────────────────────
def pull_live(days=28, now_iso=None):
    out = {"fetched_at": now_iso, "gsc": None, "ga": None, "errors": {}}
    try:
        out["gsc"] = pull_gsc(days)
    except Exception as e:
        out["errors"]["gsc"] = str(e)[:300]
    try:
        out["ga"] = pull_ga(days)
    except Exception as e:
        out["errors"]["ga"] = str(e)[:300]
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


if __name__ == "__main__":
    res = pull_live()
    print("fetched_at:", res.get("fetched_at"))
    print("errors:", res.get("errors"))
    if res.get("gsc"):
        print("GSC totals:", res["gsc"]["totals"])
    if res.get("ga"):
        print("GA totals:", res["ga"]["totals"])
