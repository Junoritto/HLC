"""8시 심판 로직 — 순수 함수. IO 없이 '무엇을 바꿀지' 계획(JudgePlan)만 만든다.

2단계 판정 (정정 유예 = CORRECTION_DAYS일):
- 어제(pending_day): 잠정. 증거 있으면 인증완료, 없으면 ⏳ 미인증(벌금 X, 정정 가능).
- 그저께(confirm_day = 어제 - 유예일): 확정. 증거/정정 없으면 실패 + 벌금 lock.
성공 = 증거(사진 or 올체크). 판정 단위는 (멤버 × challenge day).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .config import CORRECTION_DAYS, PENALTY, START_DATE, STATUS_DONE, STATUS_FAIL
from .models import Card, succeeded


@dataclass
class DayResult:
    name: str
    state: str   # 'ok' | 'pending' | 'fail' | 'noplan'
    note: str = ""


@dataclass
class TodayStatus:
    name: str
    submitted: bool


@dataclass
class Penalty:
    name: str
    fail_count: int
    won: int


@dataclass
class MemberDetail:
    name: str
    today_submitted: bool
    plan_items: list[tuple[str, bool]]
    yday_judged: bool
    yday_state: str                         # ok / pending / noplan
    yday_items: list[tuple[str, bool]]
    photo_urls: list[str]
    penalty_won: int


@dataclass
class Report:
    run_day: date
    pending_day: date                       # 어제
    confirm_day: date                       # 그저께
    pending_results: list[DayResult]        # 어제 (⏳ 포함) — 비면 '가동 전'
    confirm_results: list[DayResult]        # 그저께 확정 (신규 실패)
    today_status: list[TodayStatus]
    penalties: list[Penalty]
    pot: int
    members_detail: list[MemberDetail]
    pending_prompt_names: list[str]         # ⏳ 미인증 → ✅ 정정 대상


@dataclass
class JudgePlan:
    finalize: list[tuple[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    report: Report | None = None


def _pick_latest(cards: list[Card]) -> Card | None:
    return max(cards, key=lambda c: c.created_utc) if cards else None


def _pick_best(cards: list[Card]) -> Card | None:
    good = [c for c in cards if c.complete or c.photo_urls]
    return _pick_latest(good or cards)


def _is_fail_day(group: list[Card], day: date, confirm_day: date) -> bool:
    """(멤버, day)가 확정 '실패'인가. 확정일(그저께) 이후는 벌금 보류.

    어제(잠정)·오늘·미래 날짜는 status가 실패여도 집계하지 않는다
    (오늘 계획 미제출은 tally의 missing에서 별도 처리).
    """
    if any(succeeded(c) for c in group):
        return False                        # 올체크 = 성공
    if any(c.status == STATUS_DONE for c in group):
        return False                        # 이미 인증완료(과거 확정/정정)
    if any(c.is_stub for c in group):
        return True                         # 계획 미제출 stub = 즉시 확정 (유예 없음)
    if day > confirm_day:
        return False                        # 어제(잠정)·오늘·미래 -> 확정 전, 보류
    return True                             # 확정 구간인데 성공/인증 없음 -> 실패


def build_plan(cards: list[Card], run_day: date, members: dict[str, str]) -> JudgePlan:
    pending_day = run_day - timedelta(days=1)               # 어제
    confirm_day = pending_day - timedelta(days=CORRECTION_DAYS)  # 그저께(유예 후 확정)

    by_member: dict[str, list[Card]] = {m: [] for m in members}
    for c in cards:
        if c.assignee_id in by_member:
            by_member[c.assignee_id].append(c)

    plan = JudgePlan()

    for mid in members:
        mine = by_member[mid]
        # 어제/그저께 성공 카드는 인증완료로 승격 (증거 뒤늦게 추가/정정 반영)
        for day in (pending_day, confirm_day):
            if day < START_DATE:
                continue
            for c in mine:
                if c.cday == day and not c.is_stub and succeeded(c) and c.status != STATUS_DONE:
                    plan.finalize.append((c.page_id, STATUS_DONE))
        # 그저께 확정: 증거도 정정(인증완료)도 없으면 실패 lock
        if confirm_day >= START_DATE:
            cc = [c for c in mine if c.cday == confirm_day and not c.is_stub]
            if cc and not any(succeeded(c) or c.status == STATUS_DONE for c in cc):
                for c in cc:
                    if c.status != STATUS_FAIL:
                        plan.finalize.append((c.page_id, STATUS_FAIL))

    # 오늘 계획 미제출 -> 실패 stub (즉시)
    if run_day >= START_DATE:
        for mid in members:
            if not any(c.cday == run_day and not c.is_stub for c in by_member[mid]):
                plan.missing.append(mid)

    plan.report = _report(by_member, members, run_day, pending_day, confirm_day, plan.missing)
    return plan


def _day_state(cards_for_day: list[Card], is_pending: bool) -> DayResult:
    """어제/그저께 한 날의 멤버 상태."""
    ns = [c for c in cards_for_day if not c.is_stub]
    if any(succeeded(c) for c in ns) or any(c.status == STATUS_DONE for c in cards_for_day):
        return DayResult("", "ok")
    if any(c.is_stub for c in cards_for_day):
        return DayResult("", "noplan", "계획 미제출")
    if not ns:
        return DayResult("", "noplan", "미제출")
    return DayResult("", "pending" if is_pending else "fail",
                     "미인증" if is_pending else "인증 미이행")


def _report(by_member, members, run_day, pending_day, confirm_day, missing) -> Report:
    pre_pending = pending_day < START_DATE
    pre_confirm = confirm_day < START_DATE
    pending_results, confirm_results, today_status = [], [], []
    penalties, pot, details, prompt = [], 0, [], []

    for mid, name in members.items():
        mine = by_member[mid]
        p_cards = [c for c in mine if c.cday == pending_day]
        c_cards = [c for c in mine if c.cday == confirm_day]

        # 어제(잠정)
        p_res = _day_state(p_cards, is_pending=True)
        p_res.name = name
        if not pre_pending:
            pending_results.append(p_res)
            if p_res.state == "pending":
                prompt.append(name)

        # 그저께(확정) — 실패만 눈에 띄게, ok도 포함
        c_res = _day_state(c_cards, is_pending=False)
        c_res.name = name
        if not pre_confirm:
            confirm_results.append(c_res)

        # 오늘 제출
        submitted = any(c.cday == run_day and not c.is_stub for c in mine)
        today_status.append(TodayStatus(name, submitted))

        # 상세(계획/어제 이행/사진)
        today_card = _pick_latest([c for c in mine if c.cday == run_day and not c.is_stub])
        yday_card = _pick_best([c for c in p_cards if not c.is_stub])

        # 벌금: 확정 실패만 (어제 잠정은 제외)
        days: dict[date, list[Card]] = {}
        for c in mine:
            days.setdefault(c.cday, []).append(c)
        fail_days = set()                    # (멤버 × 날짜) 중복 제거
        for d, g in days.items():
            if d >= START_DATE:
                if _is_fail_day(g, d, confirm_day):
                    fail_days.add(d)
            elif any(c.status == STATUS_FAIL for c in g) and not any(c.status == STATUS_DONE for c in g):
                fail_days.add(d)
        if mid in missing:                   # 오늘 미제출 (stub은 아직 생성 전)
            fail_days.add(run_day)
        won = len(fail_days) * PENALTY
        pot += won
        penalties.append(Penalty(name, len(fail_days), won))

        details.append(MemberDetail(
            name=name,
            today_submitted=submitted,
            plan_items=today_card.items if today_card else [],
            yday_judged=not pre_pending,
            yday_state=p_res.state,
            yday_items=(yday_card.items if yday_card and not pre_pending else []),
            photo_urls=(yday_card.photo_urls if yday_card and not pre_pending else []),
            penalty_won=won,
        ))

    return Report(run_day, pending_day, confirm_day, pending_results, confirm_results,
                  today_status, penalties, pot, details, prompt)
