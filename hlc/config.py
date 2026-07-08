"""HLC 자동화 설정값. 비밀값은 여기 두지 않고 환경변수(.env)로만 읽는다."""
from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

# --- 챌린지 규칙 ---
KST = ZoneInfo("Asia/Seoul")
DEADLINE_HOUR = 8          # 매일 08:00 KST 마감
PENALTY = 3000             # 실패 1건당 벌금(원)

# 자동 판정/벌금은 이 날짜(challenge day) 이후부터만 적용. 과거는 소급하지 않는다.
START_DATE = date(2026, 7, 6)

# --- Notion ---
DATABASE_ID = "386379967a7c804580c0ea318d5cad6c"  # HLC 인증 Board

# status 속성 이름 (Notion에서 '🤖 판정'으로 명시 — 봇 소유 배지)
STATUS_PROP = "🤖 판정"

# 진행 상태 값 (Notion status 옵션 이름과 정확히 일치해야 함)
STATUS_PLAN = "계획 완료"
STATUS_DONE = "인증 완료"
STATUS_FAIL = "실패"

# 판정 대상 체크리스트가 들어있는 헤딩 텍스트
TASK_HEADING = "할 일 체크리스트"

# --- 멤버 (Notion user id -> 표시 이름) ---
MEMBERS: dict[str, str] = {
    "2cf2c36d-a314-403f-a10f-a76af6a989ac": "준호",
    "88de5147-a7bd-4039-8a02-9aa89b8a22c5": "종서",
    "baf68de0-a010-4f34-8c70-8ffe51ca6564": "명근",
}
