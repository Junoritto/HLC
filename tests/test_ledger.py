from hlc.judge import Penalty
from hlc.ledger import Ledger, build_settlement

MEMBERS = {"idA": "준호", "idB": "종서", "idC": "명근"}


def test_unpaid_and_balance():
    penalties = [Penalty("준호", 2, 6000), Penalty("종서", 2, 6000), Penalty("명근", 1, 3000)]
    ledger = Ledger(paid={"idA": 6000, "idB": 3000}, spent=9000)
    s = build_settlement(penalties, MEMBERS, ledger)
    m = {x.name: x for x in s.members}
    assert m["준호"].unpaid == 0          # 6000 발생 - 6000 입금
    assert m["종서"].unpaid == 3000        # 6000 - 3000
    assert m["명근"].unpaid == 3000        # 3000 - 0
    assert s.total_paid == 9000
    assert s.spent == 9000
    assert s.balance == 0                  # 입금 9000 - 지출 9000
    assert s.accrued_total == 15000


def test_no_ledger_all_unpaid():
    s = build_settlement([Penalty("준호", 2, 6000)], MEMBERS, Ledger(paid={}, spent=0))
    assert s.members[0].unpaid == 6000
    assert s.balance == 0


def test_overpay_and_spend():
    # 입금이 발생보다 많고 지출 있음
    ledger = Ledger(paid={"idA": 10000}, spent=4000)
    s = build_settlement([Penalty("준호", 1, 3000)], MEMBERS, ledger)
    assert s.members[0].unpaid == -7000    # 초과 납부
    assert s.balance == 6000               # 10000 - 4000
