from datetime import date, datetime, timezone

from hlc.config import STATUS_DONE, STATUS_FAIL, STATUS_PLAN
from hlc.models import Card
from hlc.sync import reconcile_targets

TODAY = date(2026, 7, 10)


def card(cday, complete, status, stub=False, pid="p"):
    dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Card(pid, "A", status, cday, complete, dt, dt, is_stub=stub)


def test_complete_plan_becomes_done():
    t = reconcile_targets([card(TODAY, True, STATUS_PLAN)], TODAY)
    assert t == [("p", STATUS_DONE)]


def test_fake_done_reverts_to_plan():
    # 체크 안 했는데 수동으로 인증완료 -> 되돌림 (가짜 인증 차단)
    t = reconcile_targets([card(TODAY, False, STATUS_DONE)], TODAY)
    assert t == [("p", STATUS_PLAN)]


def test_manual_fail_reverts_to_plan():
    t = reconcile_targets([card(TODAY, False, STATUS_FAIL)], TODAY)
    assert t == [("p", STATUS_PLAN)]


def test_no_change_when_already_correct():
    assert reconcile_targets([card(TODAY, True, STATUS_DONE)], TODAY) == []
    assert reconcile_targets([card(TODAY, False, STATUS_PLAN)], TODAY) == []


def test_stub_and_past_days_untouched():
    yday = date(2026, 7, 9)
    cards = [
        card(TODAY, False, STATUS_FAIL, stub=True, pid="stub"),   # stub 유지
        card(yday, False, STATUS_FAIL, pid="past"),               # 지난 실패 유지
    ]
    assert reconcile_targets(cards, TODAY) == []
