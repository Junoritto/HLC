from datetime import date, datetime, timezone

from hlc import judge
from hlc.config import STATUS_DONE, STATUS_FAIL, STATUS_PLAN
from hlc.models import Card

MEMBERS = {"A": "준호", "B": "종서", "C": "명근"}

D = date(2026, 7, 10)          # run day
PEND = date(2026, 7, 9)        # 어제 (잠정)
CONF = date(2026, 7, 8)        # 그저께 (확정)


def card(member, cday, complete=False, status=STATUS_PLAN, stub=False, pid=None, photos=None):
    dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Card(pid or f"{member}-{cday}-{status}", member, status, cday, complete,
                dt, dt, is_stub=stub, photo_urls=photos or [])


def _today_all():
    return [card(m, D) for m in MEMBERS]   # 전원 오늘 제출(미제출 벌금 격리)


def _pen(plan):
    return {p.name: p.won for p in plan.report.penalties}


def _pending(plan):
    return {r.name: r.state for r in plan.report.pending_results}


def _confirm(plan):
    return {r.name: r.state for r in plan.report.confirm_results}


# ---------- 어제(잠정) ----------

def test_pending_evidence_ok_and_promoted():
    plan = judge.build_plan([card("A", PEND, complete=True)] + _today_all(), D, MEMBERS)
    assert _pending(plan)["준호"] == "ok"
    assert (f"A-{PEND}-{STATUS_PLAN}", STATUS_DONE) in plan.finalize


def test_pending_no_evidence_is_pending_no_penalty():
    plan = judge.build_plan([card("A", PEND, complete=False)] + _today_all(), D, MEMBERS)
    assert _pending(plan)["준호"] == "pending"
    assert _pen(plan)["준호"] == 0                      # 잠정은 벌금 X
    assert "준호" in plan.report.pending_prompt_names
    assert all(st != STATUS_FAIL for _, st in plan.finalize)


def test_pending_photo_alone_is_pending():
    # 사진만 있고 체크 안 하면 미인증 (올체크가 유일한 성공 조건)
    plan = judge.build_plan([card("A", PEND, complete=False, photos=["x"])] + _today_all(), D, MEMBERS)
    assert _pending(plan)["준호"] == "pending"


# ---------- 그저께(확정) ----------

def test_confirm_no_evidence_fails_and_penalized():
    plan = judge.build_plan([card("A", CONF, complete=False)] + _today_all(), D, MEMBERS)
    assert _confirm(plan)["준호"] == "fail"
    assert (f"A-{CONF}-{STATUS_PLAN}", STATUS_FAIL) in plan.finalize
    assert _pen(plan)["준호"] == 3000


def test_confirm_checkbox_ok():
    plan = judge.build_plan([card("A", CONF, complete=True)] + _today_all(), D, MEMBERS)
    assert _confirm(plan)["준호"] == "ok"
    assert _pen(plan)["준호"] == 0
    assert (f"A-{CONF}-{STATUS_PLAN}", STATUS_DONE) in plan.finalize


def test_confirm_reaction_corrected_not_refailed():
    # 반응으로 인증완료 됐지만 증거는 없음 -> 확정 때 다시 실패 안 됨, 벌금 X
    plan = judge.build_plan(
        [card("A", CONF, complete=False, status=STATUS_DONE)] + _today_all(), D, MEMBERS)
    assert _pen(plan)["준호"] == 0
    assert all(st != STATUS_FAIL for pid, st in plan.finalize if pid.startswith("A-"))


# ---------- 오늘 미제출 / 과거 ----------

def test_missing_today_stub_and_penalty():
    plan = judge.build_plan([card("A", D)], D, MEMBERS)   # B,C 미제출
    assert set(plan.missing) == {"B", "C"}
    assert _pen(plan)["종서"] == 3000 and _pen(plan)["명근"] == 3000


def test_past_manual_fail_counted():
    cards = [card("A", date(2026, 7, 3), status=STATUS_FAIL)] + _today_all()
    plan = judge.build_plan(cards, D, MEMBERS)
    assert _pen(plan)["준호"] == 3000


def test_future_fail_status_not_counted():
    # 미래 날짜 카드가 실패 status여도 벌금 집계 안 됨 (확정 전)
    future = date(2026, 7, 12)
    plan = judge.build_plan([card("A", future, status=STATUS_FAIL)] + _today_all(), D, MEMBERS)
    assert _pen(plan)["준호"] == 0


def test_pending_fail_status_not_counted():
    # 어제(잠정) 카드가 실패 status여도 아직 집계 안 됨
    plan = judge.build_plan([card("A", PEND, status=STATUS_FAIL)] + _today_all(), D, MEMBERS)
    assert _pen(plan)["준호"] == 0


def test_stub_and_missing_not_double_counted():
    # A는 오늘 stub만(미제출) -> missing + stub 이중집계 방지 = 1건
    stub = card("A", D, stub=True, status=STATUS_FAIL)
    plan = judge.build_plan([stub, card("B", D), card("C", D)], D, MEMBERS)
    assert "A" in plan.missing
    assert _pen(plan)["준호"] == 3000


def test_past_stub_counts_immediately():
    # 지난 미제출 stub은 확정 구간 여부와 무관하게 즉시 실패로 유지
    stub = card("A", CONF, stub=True, status=STATUS_FAIL)
    plan = judge.build_plan([stub] + _today_all(), D, MEMBERS)
    assert _pen(plan)["준호"] == 3000


def test_today_submission_status():
    plan = judge.build_plan([card("A", D)], D, MEMBERS)
    ts = {t.name: t.submitted for t in plan.report.today_status}
    assert ts == {"준호": True, "종서": False, "명근": False}


def test_pre_go_live_confirm_skipped():
    run_day = date(2026, 7, 7)          # confirm=7/5 < START, pending=7/6
    plan = judge.build_plan([card(m, run_day) for m in MEMBERS], run_day, MEMBERS)
    assert plan.report.confirm_results == []
    assert plan.report.pot == 0
