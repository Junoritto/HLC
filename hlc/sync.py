"""완료 동기화 = status를 체크박스 진실에 맞추는 교정(reconcile) 로직 — 순수.

status를 사용자가 손으로 바꿔도, 오늘 카드는 여기서 체크박스 기준으로 되돌린다.
최종 확정(실패 처리)은 08:00 judge가 담당한다.
"""
from __future__ import annotations

from datetime import date

from .config import STATUS_DONE, STATUS_PLAN
from .models import Card


def reconcile_targets(cards: list[Card], today: date) -> list[tuple[str, str]]:
    """오늘(진행 중) 카드의 목표 상태 목록 [(page_id, target)] — 변경 필요분만.

    - 체크박스 전부 완료 → '인증 완료'
    - 아직 미완료 → '계획 완료' (수동으로 바꾼 인증완료/실패를 되돌림)
    - stub·오늘이 아닌 카드는 건드리지 않음 (지난 실패를 되살리지 않음)
    """
    targets: list[tuple[str, str]] = []
    for c in cards:
        if c.cday != today or c.is_stub:
            continue
        want = STATUS_DONE if c.complete else STATUS_PLAN
        if c.status != want:
            targets.append((c.page_id, want))
    return targets
