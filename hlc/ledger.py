"""정산 장부 — Notion '정산 장부' DB(입금/지출)를 읽어 미납·창고 잔액 계산.

발생 벌금(카드 계산)은 judge가, 실제 돈 흐름(입금/지출)은 이 장부가 담당한다.
  미납 = 발생 벌금 − 입금
  창고 잔액 = 입금 합 − 지출 합
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .config import LEDGER_DB_ID


@dataclass
class Ledger:
    paid: dict[str, int]     # notion_id -> 입금 합
    spent: int               # 지출 합


@dataclass
class MemberSettle:
    name: str
    accrued: int             # 발생 벌금
    paid: int                # 입금
    unpaid: int              # 미납 = accrued - paid


@dataclass
class Settlement:
    members: list[MemberSettle]
    total_paid: int
    spent: int
    balance: int             # 창고 잔액 = total_paid - spent
    accrued_total: int


def read_ledger(client) -> Ledger:
    """정산 장부 DB의 모든 행을 읽어 입금(담당자별)·지출 합계."""
    paid: dict[str, int] = defaultdict(int)
    spent = 0
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = client._post(f"/databases/{LEDGER_DB_ID}/query", body)
        for row in data["results"]:
            p = row["properties"]
            typ = (p.get("유형", {}).get("select") or {}).get("name")
            amt = p.get("금액", {}).get("number") or 0
            if typ == "입금":
                ppl = p.get("담당자", {}).get("people", [])
                if ppl:
                    paid[ppl[0]["id"]] += amt
            elif typ == "지출":
                spent += amt
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return Ledger(dict(paid), spent)


def build_settlement(penalties, members: dict[str, str], ledger: Ledger) -> Settlement:
    """발생 벌금(penalties) + 장부(ledger) -> 미납/잔액. 순수."""
    id_by_name = {name: nid for nid, name in members.items()}
    rows = []
    for p in penalties:
        nid = id_by_name.get(p.name)
        paid = ledger.paid.get(nid, 0)
        rows.append(MemberSettle(p.name, p.won, paid, p.won - paid))
    total_paid = sum(ledger.paid.values())
    accrued_total = sum(p.won for p in penalties)
    return Settlement(rows, total_paid, ledger.spent, total_paid - ledger.spent, accrued_total)
