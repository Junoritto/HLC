from datetime import date, datetime, timezone

from hlc import judge
from hlc.config import STATUS_DONE, STATUS_FAIL, STATUS_PLAN
from hlc.models import Card

MEMBERS = {"A": "준호", "B": "종서", "C": "명근"}

D = date(2026, 7, 10)         # run day (START_DATE=7/6 이후)
YDAY = date(2026, 7, 9)


def card(member, cday, complete, status=STATUS_PLAN, stub=False, pid=None):
    dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Card(
        page_id=pid or f"{member}-{cday}-{status}",
        assignee_id=member,
        status=status,
        cday=cday,
        complete=complete,
        created_utc=dt,
        last_edited_utc=dt,
        is_stub=stub,
    )


def test_finalize_marks_complete_yesterday_card_done():
    plan = judge.build_plan([card("A", YDAY, complete=True)], D, MEMBERS)
    assert (f"A-{YDAY}-{STATUS_PLAN}", STATUS_DONE) in plan.finalize


def test_finalize_marks_incomplete_yesterday_card_fail():
    plan = judge.build_plan([card("B", YDAY, complete=False)], D, MEMBERS)
    assert (f"B-{YDAY}-{STATUS_PLAN}", STATUS_FAIL) in plan.finalize


def test_finalize_skips_when_status_already_correct():
    plan = judge.build_plan([card("A", YDAY, complete=True, status=STATUS_DONE)], D, MEMBERS)
    assert plan.finalize == []


def test_duplicate_cards_success_wins_no_false_fail():
    # 하루에 2장: 완료 1 + 빈 계획 1 -> 둘 다 실패 아님(빈 카드는 DONE으로)
    cards = [
        card("A", YDAY, complete=True, status=STATUS_DONE, pid="done"),
        card("A", YDAY, complete=False, status=STATUS_PLAN, pid="empty"),
    ]
    plan = judge.build_plan(cards, D, MEMBERS)
    # 빈 카드는 DONE으로 정정, 어제 FAIL은 없음 (벌금 격리 검증은 아래 테스트)
    assert ("empty", STATUS_DONE) in plan.finalize
    assert all(status != STATUS_FAIL for _, status in plan.finalize)


def test_duplicate_cards_penalty_counts_once():
    cards = [
        card("A", YDAY, complete=True, status=STATUS_DONE, pid="d"),
        card("A", YDAY, complete=False, status=STATUS_PLAN, pid="e"),
        card("A", D, complete=False),           # 오늘은 제출 -> 미제출 벌금 없음
    ]
    plan = judge.build_plan(cards, D, MEMBERS)
    pen = {p.name: p.fail_count for p in plan.report.penalties}
    assert pen["준호"] == 0


def test_missing_today_plan_flagged_for_stub():
    plan = judge.build_plan([card("A", D, complete=False)], D, MEMBERS)
    assert set(plan.missing) == {"B", "C"}


def test_no_missing_when_all_submitted_today():
    cards = [card(m, D, complete=False) for m in MEMBERS]
    plan = judge.build_plan(cards, D, MEMBERS)
    assert plan.missing == []


def test_penalty_counts_member_day_fails():
    cards = [
        card("A", date(2026, 7, 7), complete=False, status=STATUS_FAIL),  # 실패 1
        card("A", YDAY, complete=False),   # 어제 미이행 -> 실패 예정
        # 오늘 A 미제출 -> stub 실패 예정
        card("B", D, complete=False),      # 종서/명근 오늘 제출
        card("C", D, complete=False),
    ]
    plan = judge.build_plan(cards, D, MEMBERS)
    pen = {p.name: p.won for p in plan.report.penalties}
    assert pen["준호"] == 3 * 3000
    assert pen["종서"] == 0
    assert plan.report.pot == 3 * 3000


def test_pre_go_live_day_not_finalized_or_penalized():
    # yesterday가 START_DATE 이전이면 판정/벌금 없음
    run_day = date(2026, 7, 6)         # yesterday=7/5 < START_DATE
    cards = [
        card("A", date(2026, 7, 5), complete=False),   # 가동 전
        card("A", run_day, complete=False),            # 오늘 제출
        card("B", run_day, complete=False),
        card("C", run_day, complete=False),
    ]
    plan = judge.build_plan(cards, run_day, MEMBERS)
    assert plan.finalize == []                 # 어제(7/5) 마감 안 함
    assert plan.report.yesterday_results == [] # '가동 전'
    assert plan.report.pot == 0                # 벌금 없음


def test_past_manual_fail_counts_in_penalty():
    # START_DATE 이전이라도 사람이 매긴 '실패'는 누적 벌금에 반영 (옵션 A)
    cards = [
        card("A", date(2026, 7, 3), complete=False, status=STATUS_FAIL),  # 과거 수동 실패
        card("A", D, complete=False),   # 오늘 제출(미제출 벌금 격리)
        card("B", D, complete=False),
        card("C", D, complete=False),
    ]
    plan = judge.build_plan(cards, D, MEMBERS)
    pen = {p.name: p.won for p in plan.report.penalties}
    assert pen["준호"] == 3000
    assert pen["종서"] == 0


def test_past_done_not_counted():
    cards = [
        card("A", date(2026, 7, 3), complete=False, status=STATUS_DONE),  # 과거 인증완료
        card("A", D, complete=False),
        card("B", D, complete=False),
        card("C", D, complete=False),
    ]
    plan = judge.build_plan(cards, D, MEMBERS)
    pen = {p.name: p.won for p in plan.report.penalties}
    assert pen["준호"] == 0


def test_manual_done_without_checkboxes_is_fail():
    # 체크박스 미완료인데 status만 인증완료 -> 리포트·벌금·finalize 모두 '실패'
    cards = [
        card("A", YDAY, complete=False, status=STATUS_DONE),  # 가짜 인증완료
        card("A", D, complete=False),   # 오늘 제출(미제출 벌금 격리)
        card("B", D, complete=False), card("C", D, complete=False),
    ]
    plan = judge.build_plan(cards, D, MEMBERS)
    yr = {y.name: (y.ok, y.note) for y in plan.report.yesterday_results}
    assert yr["준호"] == (False, "인증 미이행")
    assert {p.name: p.won for p in plan.report.penalties}["준호"] == 3000
    assert (f"A-{YDAY}-{STATUS_DONE}", STATUS_FAIL) in plan.finalize


def test_report_today_submission_status():
    plan = judge.build_plan([card("A", D, complete=False)], D, MEMBERS)
    today = {t.name: t.submitted for t in plan.report.today_status}
    assert today == {"준호": True, "종서": False, "명근": False}
