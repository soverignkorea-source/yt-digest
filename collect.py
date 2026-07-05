# -*- coding: utf-8 -*-
"""
collect.py — 유튜브 투자 채널 주간 영상 수집
1) channels.json의 @핸들을 채널 ID로 변환(캐시: channel_ids_cache.json)
2) 각 채널 업로드 재생목록에서 최근 7일 영상 수집
3) 자막(한국어 우선) 추출, 실패 시 설명란 사용
4) data/videos_latest.json 저장
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

API_KEY = os.environ.get("YT_API_KEY", "")
if not API_KEY:
    sys.exit("오류: 환경변수 YT_API_KEY 가 설정되지 않았습니다.")

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
SINCE = NOW - timedelta(days=7)

BASE = "https://www.googleapis.com/youtube/v3"
CACHE_FILE = "channel_ids_cache.json"
MIN_DURATION_SEC = 180          # 3분 미만(쇼츠) 제외
MAX_VIDEOS_PER_CHANNEL = 10     # 채널당 최대 수집 영상 수
TRANSCRIPT_MAX_CHARS = 18000    # 자막 최대 길이(분석 비용 관리)


def yt_get(endpoint, **params):
    params["key"] = API_KEY
    r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------
# 1. 핸들 → 채널 ID (캐시)
# ---------------------------------------------------------------
def resolve_channels():
    cfg = load_json("channels.json", {})
    cache = load_json(CACHE_FILE, {})
    resolved = []
    cache_updated = False

    for ch in cfg.get("channels", []):
        handle = ch["handle"]
        if handle in cache:
            entry = cache[handle]
        else:
            print(f"[ID 조회] {ch['name']} ({handle})")
            data = yt_get("channels", part="id,contentDetails",
                          forHandle=handle.lstrip("@"))
            items = data.get("items", [])
            if not items:
                print(f"  ! 채널을 찾지 못함: {handle} — 건너뜀")
                continue
            entry = {
                "channel_id": items[0]["id"],
                "uploads_playlist": items[0]["contentDetails"]
                                            ["relatedPlaylists"]["uploads"],
            }
            cache[handle] = entry
            cache_updated = True
            time.sleep(0.2)
        resolved.append({**ch, **entry})

    if cache_updated:
        save_json(CACHE_FILE, cache)
    return resolved


# ---------------------------------------------------------------
# 2. 최근 7일 영상 목록
# ---------------------------------------------------------------
def recent_videos(channel):
    """업로드 재생목록에서 최근 7일 영상 (playlistItems: 1 unit/page)"""
    vids, page_token = [], None
    while True:
        data = yt_get("playlistItems",
                      part="snippet,contentDetails",
                      playlistId=channel["uploads_playlist"],
                      maxResults=50,
                      **({"pageToken": page_token} if page_token else {}))
        stop = False
        for item in data.get("items", []):
            pub = datetime.fromisoformat(
                item["contentDetails"]["videoPublishedAt"]
                .replace("Z", "+00:00")).astimezone(KST)
            if pub < SINCE:
                stop = True
                break
            if pub > NOW:
                continue
            sn = item["snippet"]
            vids.append({
                "video_id": item["contentDetails"]["videoId"],
                "title": sn["title"],
                "description": (sn.get("description") or "")[:3000],
                "published_at": pub.isoformat(),
            })
        page_token = data.get("nextPageToken")
        if stop or not page_token or len(vids) >= MAX_VIDEOS_PER_CHANNEL * 2:
            break
    return vids[:MAX_VIDEOS_PER_CHANNEL * 2]


def parse_duration(iso):
    """ISO8601 PT#H#M#S → 초"""
    import re
    m = re.fullmatch(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def enrich_and_filter(videos):
    """videos.list로 길이/라이브 여부 확인, 쇼츠·예정 라이브 제외"""
    result = []
    for i in range(0, len(videos), 50):
        batch = videos[i:i + 50]
        ids = ",".join(v["video_id"] for v in batch)
        data = yt_get("videos", part="contentDetails,snippet,statistics",
                      id=ids)
        meta = {it["id"]: it for it in data.get("items", [])}
        for v in batch:
            it = meta.get(v["video_id"])
            if not it:
                continue
            dur = parse_duration(it["contentDetails"].get("duration"))
            live = it["snippet"].get("liveBroadcastContent", "none")
            if live in ("live", "upcoming"):   # 진행 중/예정 라이브 제외
                continue
            if dur < MIN_DURATION_SEC:         # 쇼츠 제외
                continue
            v["duration_sec"] = dur
            v["view_count"] = int(it.get("statistics", {})
                                    .get("viewCount", 0))
            result.append(v)
    return result


# ---------------------------------------------------------------
# 3. 자막 추출
# ---------------------------------------------------------------
def fetch_transcript(video_id):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt = YouTubeTranscriptApi()
        fetched = ytt.fetch(video_id, languages=["ko", "en"])
        text = " ".join(seg.text for seg in fetched).strip()
        return text[:TRANSCRIPT_MAX_CHARS] if text else None
    except Exception as e:
        print(f"    자막 없음({video_id}): {type(e).__name__}")
        return None


# ---------------------------------------------------------------
# main
# ---------------------------------------------------------------
def main():
    channels = resolve_channels()
    print(f"수집 기간: {SINCE:%Y-%m-%d %H:%M} ~ {NOW:%Y-%m-%d %H:%M} KST")
    print(f"채널 수: {len(channels)}\n")

    out = {
        "generated_at": NOW.isoformat(),
        "period": {"since": SINCE.isoformat(), "until": NOW.isoformat()},
        "channels": [],
    }
    total = 0
    for ch in channels:
        print(f"[수집] {ch['name']}")
        try:
            vids = enrich_and_filter(recent_videos(ch))
        except Exception as e:
            print(f"  ! 실패: {e}")
            continue
        vids = vids[:MAX_VIDEOS_PER_CHANNEL]
        for v in vids:
            tr = fetch_transcript(v["video_id"])
            v["transcript"] = tr
            v["source"] = "transcript" if tr else "description"
            time.sleep(0.3)
        print(f"  영상 {len(vids)}개")
        total += len(vids)
        out["channels"].append({
            "name": ch["name"], "handle": ch["handle"],
            "channel_id": ch["channel_id"], "videos": vids,
        })

    save_json("data/videos_latest.json", out)
    print(f"\n완료: 총 {total}개 영상 → data/videos_latest.json")


if __name__ == "__main__":
    main()
