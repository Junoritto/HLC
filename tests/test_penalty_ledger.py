from datetime import date

from hlc.config import REASON_NOPLAN, REASON_NOPROOF
from hlc.penalty_ledger import PenaltyLedger, pending_rows

D1, D2 = date(2026, 7, 9), date(2026, 7, 12)


def test_records_only_unrecorded_days():
    led = PenaltyLedger(totals={"A": 3000}, recorded={("A", D1)})
    rows = pending_rows({"A": {D1, D2}}, led, {("A", D1): REASON_NOPLAN, ("A", D2): REASON_NOPROOF})
    assert rows == [("A", D2, REASON_NOPROOF)]     # D1은 이미 기록됨 -> 스킵


def test_no_duplicate_on_rerun():
    # 봇이 두 번 돌아도 이미 기록된 건 다시 안 넣음
    led = PenaltyLedger(totals={"A": 6000}, recorded={("A", D1), ("A", D2)})
    assert pending_rows({"A": {D1, D2}}, led, {}) == []


def test_adjust_rows_do_not_block_bot_records():
    # '조정' 줄은 recorded에 안 들어가므로 봇 기록을 막지 않음
    led = PenaltyLedger(totals={"A": 9000}, recorded=set())
    rows = pending_rows({"A": {D1}}, led, {("A", D1): REASON_NOPLAN})
    assert rows == [("A", D1, REASON_NOPLAN)]


def test_empty_when_no_fails():
    assert pending_rows({}, PenaltyLedger({}, set()), {}) == []
