# 주간 투자 유튜브 다이제스트

매주 토요일 06:00 KST에 지난 7일간 투자 유튜브 채널 영상을 수집·분석하여
다크 테마 HTML 다이제스트를 GitHub Pages로 발행합니다.

## 파이프라인
```
channels.json → collect.py → analyze.py → build_html.py → docs/ (Pages)
```

## 설정 절차

### 1. API 키 발급
1. console.cloud.google.com 접속
2. 새 프로젝트 생성
3. "YouTube Data API v3" 검색 → 사용 설정
4. 사용자 인증 정보 → API 키 생성 → 복사

### 2. 저장소 준비
1. 이 폴더 전체를 새 GitHub 저장소로 푸시
2. Settings → Pages → Source: `main` 브랜치 `/docs` 폴더
3. Settings → Secrets and variables → Actions → New repository secret
   - `YT_API_KEY` : 유튜브 API 키
   - `ANTHROPIC_API_KEY` : Anthropic API 키 (console.anthropic.com)

### 3. 첫 실행 테스트
1. Actions 탭 → weekly-youtube-digest → Run workflow (수동 실행)
2. 완료 후 `https://<계정명>.github.io/<저장소명>/` 접속 확인

## 채널 추가/삭제
`channels.json`에서 한 줄 추가/삭제 후 커밋하면 끝.
```json
{ "name": "채널이름", "handle": "@핸들" }
```
채널 ID는 자동 조회되어 `channel_ids_cache.json`에 캐시됩니다.

## 조정 가능한 값 (collect.py 상단)
- `MIN_DURATION_SEC` : 쇼츠 제외 기준 (기본 180초)
- `MAX_VIDEOS_PER_CHANNEL` : 채널당 최대 영상 수 (기본 10)
- `TRANSCRIPT_MAX_CHARS` : 자막 최대 길이 (기본 18,000자)

## 발행 시각 변경
`.github/workflows/weekly-digest.yml`의 cron 수정.
UTC 기준이므로 KST에서 9시간을 빼야 합니다.
예) 일요일 19:30 KST → `30 10 * * 0`

## 주의사항
- 자동 생성 자막 특성상 종목명·수치 오류 가능 → 원 영상 확인 필수
- 자막을 끈 채널은 설명란 기반으로만 요약됨
- GitHub Actions 환경에서 간혹 자막 요청이 차단될 수 있음 (재실행으로 해결)
