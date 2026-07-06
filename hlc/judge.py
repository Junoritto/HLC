"""8시 심판 로직 — 순수 함수. IO 없이 '무엇을 바꿀지' 계획(JudgePlan)만 만든다.

판정 단위는 (멤버 × challenge day). 하루에 카드를 여러 장 올려도 하나라도 완료면 성공,
벌금도 멤버·날짜당 1회만. START_DATE 이전(가동 전)은 판정·벌금에서 제외한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .config import PENALTY, START_DATE, STATUS_DONE, STATUS_FAIL
from .models import Card


@dataclass
class YdayResult:
    name: str
    ok: bool
    note: str


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
    plan_items: list[tuple[str, bool]]     # 오늘 계획 (텍스트, 체크)
    yday_judged: bool                       # 어제가 가동 이후라 판정됨
    yday_ok: bool
    yday_note: str
    yday_items: list[tuple[str, bool]]     # 어제 이행 (텍스트, 체크)
    photo_urls: list[str]                   # 어제 인증 사진
    penalty_won: int


@dataclass
class Report:
    run_day: date
    yesterday: date
    yesterday_results: list[YdayResult]   # 비어 있으면 '가동 전'
    today_status: list[TodayStatus]
    penalties: list[Penalty]
    pot: int
    members_detail: list[MemberDetail]


def _pick_latest(cards: list[Card]) -> Card | None:
    return max(cards, key=lambda c: c.created_utc) if cards else None


def _pick_best_yday(cards: list[Card]) -> Card | None:
    """완료한 카드 우선, 없으면 최신."""
    done = [c for c in cards if c.complete]
    return _pick_latest(done or cards)


@dataclass
class JudgePlan:
    finalize: list[tuple[str, str]] = field(default_factory=list)  # (page_id, new_status)
    missing: list[str] = field(default_factory=list)               # 오늘 계획 미제출 멤버 id
    report: Report | None = None


def _is_fail_day(group: list[Card], day: date, yesterday: date) -> bool:
    """(멤버, day) 하루가 최종적으로 '실패'인가."""
    if any(c.complete for c in group if not c.is_stub):
        return False
    if any(c.status == STATUS_DONE for c in group):
        return False
    if any(c.is_stub or c.status == STATUS_FAIL for c in group):
        return True
    if day == yesterday:          # 오늘 마감되는데 미완료 -> 실패
        return True
    return False                  # 오늘/미래의 진행중(계획 완료)은 아직 보류


def build_plan(cards: list[Card], run_day: date, members: dict[str, str]) -> JudgePlan:
    yesterday = run_day - timedelta(days=1)
    by_member: dict[str, list[Card]] = {m: [] for m in members}
    for c in cards:
        if c.assignee_id in by_member:
            by_member[c.assignee_id].append(c)

    plan = JudgePlan()

    # 1) 어제 카드 마감 (가동 시작 이후에만) — 멤버 단위 성공/실패
    if yesterday >= START_DATE:
        for mid in members:
            yc = [c for c in by_member[mid] if c.cday == yesterday and not c.is_stub]
            if not yc:
                continue
            target = STATUS_DONE if any(c.complete for c in yc) else STATUS_FAIL
            for c in yc:
                if c.status != target:
                    plan.finalize.append((c.page_id, target))

    # 2) 오늘 계획 미제출 검출
    if run_day >= START_DATE:
        for mid in members:
            submitted = any(c.cday == run_day and not c.is_stub for c in by_member[mid])
            if not submitted:
                plan.missing.append(mid)

    plan.report = _report(by_member, members, run_day, yesterday, plan.missing)
    return plan


def _report(by_member, members, run_day, yesterday, missing) -> Report:
    pre_go_live = yesterday < START_DATE
    yday_results, today_status, penalties, pot = [], [], [], 0
    details = []

    for mid, name in members.items():
        mine = by_member[mid]

        # 어제 결과
        yday_ok, yday_note = False, ""
        if not pre_go_live:
            yc = [c for c in mine if c.cday == yesterday]
            if any(c.complete for c in yc if not c.is_stub) or any(c.status == STATUS_DONE for c in yc):
                yday_ok, yday_note = True, ""
            elif any(c.is_stub for c in yc):
                yday_note = "계획 미제출"
            elif yc:
                yday_note = "인증 미이행"
            else:
                yday_note = "미제출"
            yday_results.append(YdayResult(name, yday_ok, yday_note))

        # 오늘 제출 여부
        submitted = any(c.cday == run_day and not c.is_stub for c in mine)
        today_status.append(TodayStatus(name, submitted))

        # 상세 카드(계획/이행/사진)
        today_card = _pick_latest([c for c in mine if c.cday == run_day and not c.is_stub])
        yday_card = _pick_best_yday([c for c in mine if c.cday == yesterday and not c.is_stub])

        # 벌금: (멤버 × 날짜) 실패 수.
        #  - START_DATE 이후: 증거 기반 판정(_is_fail_day)
        #  - 과거: 소급 판정하지 않고, 사람이 이미 매긴 '실패'만 인정 (옵션 A)
        days: dict[date, list[Card]] = {}
        for c in mine:
            days.setdefault(c.cday, []).append(c)
        fails = 0
        for d, g in days.items():
            if d >= START_DATE:
                if _is_fail_day(g, d, yesterday):
                    fails += 1
            elif any(c.status == STATUS_FAIL for c in g) and not any(c.status == STATUS_DONE for c in g):
                fails += 1
        if mid in missing:                 # 오늘 미제출(신규 stub 예정)
            fails += 1
        won = fails * PENALTY
        pot += won
        penalties.append(Penalty(name, fails, won))

        details.append(MemberDetail(
            name=name,
            today_submitted=submitted,
            plan_items=today_card.items if today_card else [],
            yday_judged=not pre_go_live,
            yday_ok=yday_ok,
            yday_note=yday_note,
            yday_items=(yday_card.items if yday_card and not pre_go_live else []),
            photo_urls=(yday_card.photo_urls if yday_card and not pre_go_live else []),
            penalty_won=won,
        ))

    return Report(run_day, yesterday, yday_results, today_status, penalties, pot, details)
