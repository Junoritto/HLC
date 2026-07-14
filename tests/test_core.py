from datetime import date, datetime, timezone

from hlc import core
from hlc.config import KST


def _utc(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


# ---------- challenge_day: createdTime -> 다음 08:00 KST 경계 ----------

def test_challenge_day_evening_before_maps_to_next_day():
    # 7/5 21:00 KST 업로드 = 7/5 12:00 UTC -> 7/6 챌린지
    assert core.challenge_day(_utc(2026, 7, 5, 12, 0)) == date(2026, 7, 6)


def test_challenge_day_early_morning_before_8_maps_to_same_day():
    # 7/6 07:00 KST = 7/5 22:00 UTC -> 7/6 챌린지 (마감 전)
    assert core.challenge_day(_utc(2026, 7, 5, 22, 0)) == date(2026, 7, 6)


def test_challenge_day_after_8_maps_to_next_day():
    # 7/6 10:14 KST = 7/6 01:14 UTC -> 7/7 챌린지 (마감 후 = 다음날 집계)
    assert core.challenge_day(_utc(2026, 7, 6, 1, 14)) == date(2026, 7, 7)


def test_challenge_day_exactly_8am_counts_as_on_time():
    # 정확히 08:00 KST = 전날 23:00 UTC. 마감 포함(<=)이므로 그날(7/6) 인정
    assert core.challenge_day(_utc(2026, 7, 5, 23, 0)) == date(2026, 7, 6)


def test_challenge_day_one_second_after_8am_is_next_day():
    # 08:00:01 KST = 전날 23:00:01 UTC -> 다음날(7/7)
    assert core.challenge_day(datetime(2026, 7, 5, 23, 0, 1, tzinfo=timezone.utc)) == date(2026, 7, 7)


# ---------- 카드 본문 파싱: '할 일 체크리스트' 아래 to_do만 ----------

def _todo(text, checked):
    return {"type": "to_do", "to_do": {
        "rich_text": [{"plain_text": text}] if text else [],
        "checked": checked,
    }}


def _h3(text):
    return {"type": "heading_3", "heading_3": {"rich_text": [{"plain_text": text}]}}


def _h2(text):
    return {"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": text}]}}


# 실제 템플릿 구조 재현
SAMPLE_BLOCKS = [
    _h2("오늘의 계획 (8시 이전 작성)"),
    _h3("할 일 체크리스트"),
    _todo("듀오링고", False),
    _todo("", False),          # 빈 칸 (무시 대상)
    _todo("", False),
    _h3("예상 소요 / 시간 블록"),
    _h2("내일 인증 (다음날 8시 이전)"),
    _h3("✅ 인증 체크"),
    _todo("할 일 체크박스 채우기", True),   # 메타 체크박스 (무시 대상)
    _todo("📷 인증 사진 첨부", True),
]


def test_task_todos_only_under_task_heading_and_nonempty():
    todos = core.task_todos(SAMPLE_BLOCKS)
    assert todos == [False]  # '듀오링고'만, 빈칸/메타 제외


def test_is_complete_false_when_task_unchecked():
    assert core.is_card_complete(SAMPLE_BLOCKS) is False


def test_is_complete_true_when_all_tasks_checked():
    blocks = [
        _h3("할 일 체크리스트"),
        _todo("듀오링고", True),
        _todo("운동", True),
        _h3("예상 소요"),
        _h3("✅ 인증 체크"),
        _todo("사진 첨부", False),   # 메타는 미체크여도 무관
    ]
    assert core.is_card_complete(blocks) is True


def test_is_complete_false_when_no_tasks():
    # 할 일에 실제 항목이 없으면(빈칸만) 완료로 보지 않음
    blocks = [_h3("할 일 체크리스트"), _todo("", False)]
    assert core.is_card_complete(blocks) is False


# ---------- 벌금 집계 ----------

def test_penalty_won():
    assert core.penalty_won(0) == 0
    assert core.penalty_won(2) == 6000


# ---------- resolve_cday: 여러 날 미리 계획 + 백데이팅 차단 ----------

def _created(y, mo, d, h):  # KST 기준 시각을 UTC로
    return datetime(y, mo, d, h, tzinfo=KST).astimezone(timezone.utc)


def test_resolve_cday_no_date_uses_createdtime():
    # 7/14 07:00 생성, 날짜 없음 -> 7/14
    assert core.resolve_cday(_created(2026, 7, 14, 7), None) == date(2026, 7, 14)


def test_resolve_cday_future_date_used():
    # 7/14 생성인데 날짜=7/17 (미래) -> 7/17 (미리 계획 허용)
    assert core.resolve_cday(_created(2026, 7, 14, 7), date(2026, 7, 17)) == date(2026, 7, 17)


def test_resolve_cday_backdate_blocked():
    # 7/14 10:00 생성(마감 후, 최소유효 7/15)인데 날짜=7/14 로 백데이팅 -> 무시, 7/15
    assert core.resolve_cday(_created(2026, 7, 14, 10), date(2026, 7, 14)) == date(2026, 7, 15)


def test_resolve_cday_stub_uses_date_field():
    # stub은 날짜(실제 미제출일) 그대로 (백데이팅 가드 미적용)
    assert core.resolve_cday(_created(2026, 7, 14, 10), date(2026, 7, 14), is_stub=True) == date(2026, 7, 14)
