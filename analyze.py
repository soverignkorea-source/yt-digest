# -*- coding: utf-8 -*-
"""
analyze.py — 수집된 영상을 Claude API로 분석
1단계: 영상별 구조화 요약 (시황 판단 / 종목 의견 / 핵심 논리)
2단계: 채널 전체 종합 분석 (컨센서스 / 상충 의견 / 섹터 / 인사이트)
결과: data/analysis_latest.json
"""
import json
import os
import sys
import time

import requests

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not API_KEY:
    sys.exit("오류: 환경변수 ANTHROPIC_API_KEY 가 설정되지 않았습니다.")

MODEL = "claude-sonnet-4-6"
API_URL = "https://api.anthropic.com/v1/messages"
HEADERS = {
    "content-type": "application/json",
    "x-api-key": API_KEY,
    "anthropic-version": "2023-06-01",
}

VIDEO_PROMPT = """당신은 한국 주식시장 전문 리서치 어시스턴트입니다.
아래는 유튜브 투자 채널 영상의 자막(또는 설명란)입니다.
자동 생성 자막이라 종목명·숫자에 오탈자가 있을 수 있으니 문맥으로 보정하세요.

채널: {channel}
제목: {title}
게시일: {published}
본문 출처: {source}

<본문>
{body}
</본문>

아래 JSON 스키마로만 응답하세요. 마크다운 코드펜스 없이 순수 JSON만 출력하세요.
{{
  "핵심요약": "2~3문장 요약",
  "시황판단": "강세/약세/중립/해당없음 중 하나 + 근거 한 문장",
  "종목의견": [
    {{"종목": "종목명(또는 티커/섹터)", "방향": "긍정/부정/중립", "논리": "한 문장"}}
  ],
  "매크로포인트": ["언급된 매크로/금리/환율/정책 포인트, 없으면 빈 배열"],
  "리스크경고": ["언급된 리스크, 없으면 빈 배열"],
  "주목도": 1
}}
주목도는 1~5 정수: 정보 밀도와 투자 판단 기여도 기준.
본문이 광고·잡담 위주면 종목의견은 빈 배열로, 주목도 1로 처리하세요."""

SYNTHESIS_PROMPT = """당신은 한국 개인투자자를 위한 수석 애널리스트입니다.
아래는 지난 1주일간 {n_channels}개 투자 유튜브 채널 {n_videos}개 영상의 구조화 요약입니다.

<영상분석목록>
{video_summaries}
</영상분석목록>

이번 주 투자 다이제스트의 종합 분석을 작성하세요.
아래 JSON 스키마로만 응답하세요. 마크다운 코드펜스 없이 순수 JSON만 출력하세요.
{{
  "주간한줄평": "이번 주 시장 분위기 한 문장",
  "시장컨센서스": {{
    "전반적방향": "강세우위/약세우위/혼조 중 하나",
    "설명": "여러 채널에서 공통적으로 나타난 시각 3~5문장",
    "강세채널수": 0, "약세채널수": 0, "중립채널수": 0
  }},
  "공통테마": [
    {{"테마": "테마명", "언급채널": ["채널명"], "내용": "2~3문장"}}
  ],
  "상충의견": [
    {{"쟁점": "쟁점명", "강세측": "채널명: 논리", "약세측": "채널명: 논리"}}
  ],
  "종목별언급": [
    {{"종목": "종목명", "언급횟수": 0, "방향성": "긍정/부정/엇갈림",
      "핵심논리": "종합 논리 1~2문장", "언급채널": ["채널명"]}}
  ],
  "매크로체크": ["이번 주 채널들이 주목한 매크로 변수 정리, 3~6개"],
  "리스크레이더": ["여러 채널이 경고한 리스크, 2~5개"],
  "이번주인사이트": "위 내용을 종합한 투자자 관점의 심층 인사이트 5~8문장. 컨센서스가 쏠린 곳의 역발상 관점, 소수의견 중 주목할 것, 다음 주 확인할 이벤트를 포함",
  "다음주체크포인트": ["다음 주 확인해야 할 이벤트/지표 3~5개"]
}}
종목별언급은 2개 이상 채널에서 언급됐거나 논리가 구체적인 종목 위주로 최대 15개.
특정 채널의 의견을 사실처럼 단정하지 말고 출처 채널을 명시하세요."""


def call_claude(prompt, max_tokens=2000, retries=3):
    body = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    for attempt in range(retries):
        try:
            r = requests.post(API_URL, headers=HEADERS,
                              json=body, timeout=600)
            if r.status_code == 429 or r.status_code >= 500:
                wait = 15 * (attempt + 1)
                print(f"    재시도 대기 {wait}s (HTTP {r.status_code})",
                      flush=True)
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                print(f"    API 오류 {r.status_code}: {r.text[:300]}",
                      flush=True)
                return None
            data = r.json()
            if data.get("stop_reason") == "max_tokens":
                print("    ! 경고: 출력이 토큰 한도에서 잘림", flush=True)
            return "".join(b.get("text", "") for b in data["content"]
                           if b.get("type") == "text")
        except requests.RequestException as e:
            print(f"    API 오류: {e}", flush=True)
            time.sleep(10 * (attempt + 1))
    return None


def parse_json(text):
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        t = t[4:] if t.startswith("json") else t
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # 첫 { 부터 마지막 } 까지 재시도
        s, e = t.find("{"), t.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(t[s:e + 1])
            except json.JSONDecodeError:
                return None
    return None


def main():
    with open("data/videos_latest.json", encoding="utf-8") as f:
        collected = json.load(f)

    analysis = {
        "generated_at": collected["generated_at"],
        "period": collected["period"],
        "channels": [],
    }

    # ---------- 1단계: 영상별 분석 ----------
    all_video_rows = []
    for ch in collected["channels"]:
        ch_out = {"name": ch["name"], "videos": []}
        for v in ch["videos"]:
            body = v.get("transcript") or v.get("description") or ""
            if len(body) < 100:
                continue
            print(f"[분석] {ch['name']} | {v['title'][:40]}")
            raw = call_claude(VIDEO_PROMPT.format(
                channel=ch["name"], title=v["title"],
                published=v["published_at"][:10],
                source="자막" if v["source"] == "transcript" else "설명란",
                body=body))
            parsed = parse_json(raw)
            if not parsed:
                print("    ! 파싱 실패, 건너뜀")
                continue
            row = {
                "video_id": v["video_id"], "title": v["title"],
                "published_at": v["published_at"],
                "url": f"https://www.youtube.com/watch?v={v['video_id']}",
                "view_count": v.get("view_count", 0),
                "source": v["source"], **parsed,
            }
            ch_out["videos"].append(row)
            all_video_rows.append({"채널": ch["name"], **{
                k: parsed.get(k) for k in
                ("핵심요약", "시황판단", "종목의견",
                 "매크로포인트", "리스크경고", "주목도")},
                "제목": v["title"]})
            time.sleep(1)
        analysis["channels"].append(ch_out)

    n_videos = len(all_video_rows)
    if n_videos == 0:
        sys.exit("분석할 영상이 없습니다.")

    # ---------- 2단계: 종합 분석 ----------
    print(f"\n[종합 분석] 영상 {n_videos}개", flush=True)
    synthesis_raw = call_claude(
        SYNTHESIS_PROMPT.format(
            n_channels=len(analysis["channels"]),
            n_videos=n_videos,
            video_summaries=json.dumps(all_video_rows,
                                       ensure_ascii=False)),
        max_tokens=16000)
    synthesis = parse_json(synthesis_raw)

    if not synthesis:
        # 실패 시 디버깅 정보 출력 후 축약 입력으로 1회 재시도
        if synthesis_raw:
            print("--- 응답 앞부분 ---", flush=True)
            print(synthesis_raw[:500], flush=True)
            print("--- 응답 끝부분 ---", flush=True)
            print(synthesis_raw[-500:], flush=True)
        print("[재시도] 주목도 상위 영상으로 축약", flush=True)
        trimmed = sorted(all_video_rows,
                         key=lambda r: r.get("주목도") or 1,
                         reverse=True)[:40]
        synthesis_raw = call_claude(
            SYNTHESIS_PROMPT.format(
                n_channels=len(analysis["channels"]),
                n_videos=len(trimmed),
                video_summaries=json.dumps(trimmed,
                                           ensure_ascii=False)),
            max_tokens=16000)
        synthesis = parse_json(synthesis_raw)

    if not synthesis:
        sys.exit("종합 분석 파싱 실패")
    analysis["synthesis"] = synthesis

    with open("data/analysis_latest.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print("완료 → data/analysis_latest.json")


if __name__ == "__main__":
    main()
