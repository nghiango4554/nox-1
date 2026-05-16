"""Facebook Graph API wrapper. Reads token from ../state/fb_token.json."""

import json
from pathlib import Path
import requests

TOKEN_PATH = Path(__file__).parent.parent / "state" / "fb_token.json"
GRAPH_VERSION = "v21.0"


def load_config():
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def post_multi_to_page(message, image_paths, scheduled_publish_time=None, published=True):
    """Post 2+ photos as carousel/album.

    Step 1: upload each photo with published=false → get media id.
    Step 2: POST /feed with attached_media=[{media_fbid: id}, ...]
    """
    cfg = load_config()
    page_id = cfg["page_id"]
    token = cfg["page_access_token"]

    media_ids = []
    for ip in image_paths:
        url = f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/photos"
        with open(ip, "rb") as fh:
            r = requests.post(
                url,
                data={"access_token": token, "published": "false"},
                files={"source": fh},
                timeout=60,
            )
        j = r.json()
        if "error" in j:
            raise RuntimeError(f"FB upload error: {j['error']}")
        media_ids.append(j["id"])

    feed_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/feed"
    data = {"message": message, "access_token": token}
    for i, mid in enumerate(media_ids):
        data[f"attached_media[{i}]"] = json.dumps({"media_fbid": mid})
    if scheduled_publish_time:
        data["published"] = "false"
        data["scheduled_publish_time"] = str(int(scheduled_publish_time))
    elif not published:
        data["published"] = "false"
    r = requests.post(feed_url, data=data, timeout=30)
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"FB feed error: {j['error']}")
    return j


def post_to_page(message, image_path=None, scheduled_publish_time=None, published=True):
    """Post text (and optional image) to Sintech Page.

    scheduled_publish_time: unix timestamp (seconds). If set, FB will schedule.
        Must be 10 minutes - 6 months in the future. Also forces published=False.
    Returns: {"id": "PAGE_ID_POST_ID"} on success, raises on failure.
    """
    cfg = load_config()
    page_id = cfg["page_id"]
    token = cfg["page_access_token"]

    if image_path:
        # Upload photo + caption
        url = f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/photos"
        files = {"source": open(image_path, "rb")}
        data = {
            "message": message,
            "access_token": token,
        }
        if scheduled_publish_time:
            data["published"] = "false"
            data["scheduled_publish_time"] = str(int(scheduled_publish_time))
        elif not published:
            data["published"] = "false"
        r = requests.post(url, data=data, files=files, timeout=60)
        files["source"].close()
    else:
        url = f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/feed"
        data = {
            "message": message,
            "access_token": token,
        }
        if scheduled_publish_time:
            data["published"] = "false"
            data["scheduled_publish_time"] = str(int(scheduled_publish_time))
        elif not published:
            data["published"] = "false"
        r = requests.post(url, data=data, timeout=30)

    j = r.json()
    if "error" in j:
        raise RuntimeError(f"FB error: {j['error']}")
    return j


def delete_post(fb_post_id):
    cfg = load_config()
    token = cfg["page_access_token"]
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{fb_post_id}"
    r = requests.delete(url, params={"access_token": token}, timeout=30)
    j = r.json()
    if j.get("error"):
        raise RuntimeError(f"FB error: {j['error']}")
    return j


def page_info():
    cfg = load_config()
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{cfg['page_id']}"
    r = requests.get(
        url,
        params={
            "fields": "id,name,fan_count,followers_count",
            "access_token": cfg["page_access_token"],
        },
        timeout=15,
    )
    return r.json()


def post_url(fb_post_id, page_id=None):
    if not page_id:
        page_id = load_config()["page_id"]
    parts = fb_post_id.split("_")
    post_only = parts[1] if len(parts) > 1 else fb_post_id
    return f"https://www.facebook.com/{page_id}/posts/{post_only}"
