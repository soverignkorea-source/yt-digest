# -*- coding: utf-8 -*-
"""
build_html.py — 분석 결과를 다크 테마 HTML 다이제스트로 변환
출력: docs/index.html + docs/archive/YYYY-MM-DD.html
"""
import html
import json
from datetime import datetime

E = html.escape


def badge(direction):
    color = {"긍정": "#2ea043", "부정": "#f85149", "중립": "#8b949e",
             "엇갈림": "#d29922", "강세우위": "#2ea043",
             "약세우위": "#f85149", "혼조": "#d29922"}.get(direction, "#8b949e")
    return (f'<span style="background:{color}22;color:{color};'
            f'border:1px solid {color}55;border-radius:12px;'
            f'padding:2px 10px;font-size:12px;font-weight:600;">'
            f'{E(direction)}</span>')


def li_list(items):
    if not items:
        return "<p class='muted'>해당 없음</p>"
    return "<ul>" + "".join(f"<li>{E(str(x))}</li>" for x in items) + "</ul>"


def build(analysis):
    syn = analysis["synthesis"]
    period = analysis["period"]
    since = period["since"][:10]
    until = period["until"][:10]
    gen = datetime.fromisoformat(analysis["generated_at"])

    n_videos = sum(len(c["videos"]) for c in analysis["channels"])
    n_channels = sum(1 for c in analysis["channels"] if c["videos"])

    cons = syn.get("시장컨센서스", {})

    # ----- 공통 테마 -----
    themes = "".join(
        f"""<div class="card">
          <div class="card-title">{E(t.get('테마',''))}</div>
          <div class="tags">{' '.join(f"<span class='tag'>{E(c)}</span>"
                                      for c in t.get('언급채널', []))}</div>
          <p>{E(t.get('내용',''))}</p>
        </div>"""
        for t in syn.get("공통테마", []))

    # ----- 상충 의견 -----
    conflicts = "".join(
        f"""<div class="card">
          <div class="card-title">⚔️ {E(c.get('쟁점',''))}</div>
          <p><b style="color:#2ea043">강세측</b> — {E(c.get('강세측',''))}</p>
          <p><b style="color:#f85149">약세측</b> — {E(c.get('약세측',''))}</p>
        </div>"""
        for c in syn.get("상충의견", [])) or "<p class='muted'>뚜렷한 상충 의견 없음</p>"

    # ----- 종목 테이블 -----
    stock_rows = "".join(
        f"""<tr>
          <td><b>{E(s.get('종목',''))}</b></td>
          <td style="text-align:center">{s.get('언급횟수','')}</td>
          <td style="text-align:center">{badge(s.get('방향성',''))}</td>
          <td>{E(s.get('핵심논리',''))}</td>
          <td class="muted small">{E(', '.join(s.get('언급채널', [])))}</td>
        </tr>"""
        for s in syn.get("종목별언급", []))

    # ----- 채널별 섹션 -----
    channel_sections = []
    for ch in analysis["channels"]:
        if not ch["videos"]:
            continue
        vids = sorted(ch["videos"],
                      key=lambda v: v.get("주목도", 1), reverse=True)
        vid_html = []
        for v in vids:
            stocks = "".join(
                f"<li><b>{E(s.get('종목',''))}</b> {badge(s.get('방향',''))} "
                f"— {E(s.get('논리',''))}</li>"
                for s in v.get("종목의견", []))
            stars = "★" * int(v.get("주목도", 1)) + \
                    "☆" * (5 - int(v.get("주목도", 1)))
            vid_html.append(f"""
            <details {'open' if v.get('주목도',1)>=4 else ''}>
              <summary>
                <span class="stars">{stars}</span>
                <a href="{E(v['url'])}" target="_blank">{E(v['title'])}</a>
                <span class="muted small">({v['published_at'][:10]}
                 · {'자막' if v['source']=='transcript' else '설명란'})</span>
              </summary>
              <div class="detail-body">
                <p>{E(v.get('핵심요약',''))}</p>
                <p class="muted small">시황: {E(v.get('시황판단',''))}</p>
                {'<ul>'+stocks+'</ul>' if stocks else ''}
              </div>
            </details>""")
        channel_sections.append(f"""
        <div class="channel">
          <h3>{E(ch['name'])}
            <span class="muted small">영상 {len(vids)}개</span></h3>
          {''.join(vid_html)}
        </div>""")

    page = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>주간 투자 유튜브 다이제스트 {until}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0d1117; color:#e6edf3;
         font-family:'Pretendard','Apple SD Gothic Neo','Malgun Gothic',
         sans-serif; line-height:1.65; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:32px 20px 80px; }}
  h1 {{ font-size:26px; margin:0 0 4px; }}
  h2 {{ font-size:20px; margin:40px 0 16px; padding-bottom:8px;
       border-bottom:1px solid #21262d; }}
  h3 {{ font-size:16px; margin:24px 0 10px; color:#79c0ff; }}
  a {{ color:#79c0ff; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .muted {{ color:#8b949e; }}
  .small {{ font-size:12px; }}
  .hero {{ background:linear-gradient(135deg,#161b22,#1c2333);
          border:1px solid #30363d; border-radius:14px;
          padding:24px; margin:24px 0; }}
  .hero .oneliner {{ font-size:18px; font-weight:700; margin-bottom:12px; }}
  .stat-row {{ display:flex; gap:14px; flex-wrap:wrap; margin-top:14px; }}
  .stat {{ background:#0d1117; border:1px solid #30363d;
          border-radius:10px; padding:10px 16px; font-size:13px; }}
  .stat b {{ font-size:18px; display:block; }}
  .card {{ background:#161b22; border:1px solid #30363d;
          border-radius:12px; padding:16px 18px; margin:12px 0; }}
  .card-title {{ font-weight:700; margin-bottom:6px; }}
  .tags {{ margin:4px 0 8px; }}
  .tag {{ display:inline-block; background:#21262d; color:#8b949e;
         border-radius:10px; padding:1px 9px; font-size:11px;
         margin:2px 3px 2px 0; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th,td {{ padding:9px 10px; border-bottom:1px solid #21262d;
          text-align:left; vertical-align:top; }}
  th {{ color:#8b949e; font-size:12px; }}
  .insight {{ background:#1c2333; border-left:4px solid #d29922;
             border-radius:0 12px 12px 0; padding:18px 20px;
             white-space:pre-wrap; }}
  details {{ background:#161b22; border:1px solid #21262d;
            border-radius:10px; padding:10px 14px; margin:8px 0; }}
  summary {{ cursor:pointer; }}
  .detail-body {{ margin-top:10px; padding-top:10px;
                 border-top:1px solid #21262d; font-size:14px; }}
  .stars {{ color:#d29922; font-size:12px; margin-right:6px; }}
  ul {{ margin:8px 0; padding-left:20px; }}
  li {{ margin:4px 0; }}
  .channel {{ margin-bottom:28px; }}
  footer {{ margin-top:60px; color:#484f58; font-size:12px;
           border-top:1px solid #21262d; padding-top:16px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>📺 주간 투자 유튜브 다이제스트</h1>
  <p class="muted">{since} ~ {until} · 생성 {gen:%Y-%m-%d %H:%M} KST</p>

  <div class="hero">
    <div class="oneliner">{E(syn.get('주간한줄평',''))}</div>
    <div>{badge(cons.get('전반적방향',''))}</div>
    <p>{E(cons.get('설명',''))}</p>
    <div class="stat-row">
      <div class="stat"><b>{n_channels}</b>채널</div>
      <div class="stat"><b>{n_videos}</b>영상</div>
      <div class="stat"><b style="color:#2ea043">{cons.get('강세채널수',0)}</b>강세 시각</div>
      <div class="stat"><b style="color:#f85149">{cons.get('약세채널수',0)}</b>약세 시각</div>
      <div class="stat"><b style="color:#8b949e">{cons.get('중립채널수',0)}</b>중립</div>
    </div>
  </div>

  <h2>🔥 이번 주 공통 테마</h2>
  {themes or "<p class='muted'>공통 테마 없음</p>"}

  <h2>⚖️ 상충 의견</h2>
  {conflicts}

  <h2>📊 종목별 언급 현황</h2>
  <table>
    <tr><th>종목</th><th>언급</th><th>방향</th><th>핵심 논리</th><th>채널</th></tr>
    {stock_rows}
  </table>

  <h2>🌐 매크로 체크</h2>
  {li_list(syn.get('매크로체크', []))}

  <h2>🚨 리스크 레이더</h2>
  {li_list(syn.get('리스크레이더', []))}

  <h2>💡 이번 주 인사이트</h2>
  <div class="insight">{E(syn.get('이번주인사이트',''))}</div>

  <h2>📅 다음 주 체크포인트</h2>
  {li_list(syn.get('다음주체크포인트', []))}

  <h2>📚 채널별 상세</h2>
  {''.join(channel_sections)}

  <footer>
    본 다이제스트는 유튜브 자막 기반 자동 요약으로, 원 영상 발화자의 의견이며
    투자 권유가 아닙니다. 자동 생성 자막 특성상 종목명·수치 오류가 있을 수 있으니
    반드시 원 영상을 확인하세요. · <a href="archive/">지난 다이제스트</a>
  </footer>
</div>
</body>
</html>"""
    return page, until


def main():
    with open("data/analysis_latest.json", encoding="utf-8") as f:
        analysis = json.load(f)
    page, until = build(analysis)

    import os
    os.makedirs("docs/archive", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(page)
    with open(f"docs/archive/{until}.html", "w", encoding="utf-8") as f:
        f.write(page)

    # 아카이브 목록 페이지
    files = sorted((x for x in os.listdir("docs/archive")
                    if x.endswith(".html") and x != "index.html"),
                   reverse=True)
    links = "".join(f'<li><a href="{x}">{x[:-5]}</a></li>' for x in files)
    with open("docs/archive/index.html", "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html><html lang="ko"><head>
<meta charset="utf-8"><title>다이제스트 아카이브</title>
<style>body{{background:#0d1117;color:#e6edf3;font-family:sans-serif;
max-width:600px;margin:40px auto;padding:0 20px}}
a{{color:#79c0ff}}</style></head>
<body><h1>지난 다이제스트</h1><ul>{links}</ul>
<p><a href="../index.html">← 최신 다이제스트</a></p></body></html>""")

    print(f"완료 → docs/index.html, docs/archive/{until}.html")


if __name__ == "__main__":
    main()
