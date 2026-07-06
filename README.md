# 🔥 HLC 챌린지 자동화

Notion "HLC 인증 Board"를 자동으로 판정·집계하고 Discord로 리포트하는 봇.
Notion(데이터) + GitHub Actions(두뇌) + Discord(알림) 구조.

자세한 설계는 [DESIGN.md](DESIGN.md) 참고.

## 하는 일

- **매일 08:00 KST 심판** (`run_judge.py`)
  - 어제 카드: 할 일 체크리스트 전부 체크 → `인증 완료`, 아니면 `실패`
  - 오늘 계획 미제출자 → `실패` 카드 자동 생성
  - 멤버·날짜당 벌금(3,000원) 집계 → Discord 리포트 발송
  - 어제/오늘 카드의 빈 `날짜` 필드 자동 기입
- **낮 시간대 30분마다 동기화** (`run_sync.py`)
  - 오늘 카드의 할 일 체크박스가 전부 채워지면 → `인증 완료`로 자동 변경 (수동 클릭 불필요)

> 판정·벌금은 `hlc/config.py`의 `START_DATE`(가동 시작일) 이후 날짜에만 적용된다. 과거는 소급하지 않는다.

## 로컬 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # NOTION_TOKEN, DISCORD_WEBHOOK_URL 채우기
pytest                    # 테스트
python run_judge.py       # 심판 1회 (실제로 Notion/Discord에 반영됨!)
python run_sync.py        # 완료 동기화 1회
```

## GitHub Actions 배포

1. 이 저장소를 GitHub에 push
2. **Settings → Secrets and variables → Actions** 에 시크릿 2개 등록:
   - `NOTION_TOKEN`
   - `DISCORD_WEBHOOK_URL`
3. **Actions** 탭에서 워크플로우 활성화. `Run workflow`로 수동 테스트 가능.
   - `judge.yml` — 매일 08:00 KST
   - `sync.yml` — 30분마다(낮 시간대)

> public 저장소면 Actions 무료 무제한. private면 월 2,000분 내(본 봇은 넉넉히 그 안).

## 설정 (`hlc/config.py`)

| 값 | 의미 |
|----|------|
| `MEMBERS` | Notion user id → 이름 |
| `DATABASE_ID` | HLC 인증 Board |
| `START_DATE` | 자동 판정 시작일 |
| `PENALTY` | 실패 1건 벌금(원) |
| `DEADLINE_HOUR` | 마감 시각(KST) |

## 구조

```
hlc/core.py     순수 로직 (challenge day 계산, 체크박스 판정)
hlc/models.py   Notion 페이지 → Card 정규화
hlc/judge.py    심판 계획(순수) — 멤버·날짜 단위 판정/벌금
hlc/notion.py   Notion API 클라이언트 (IO)
hlc/discord.py  리포트 포맷 + 웹훅 발송
run_judge.py    진입점: 08:00 심판
run_sync.py     진입점: 완료 동기화
```
