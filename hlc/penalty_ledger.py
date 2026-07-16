"""벌금 장부 — 발생 벌금의 저장된 기록(진실).

봇은 매 실행마다 카드로 '확정된 실패'를 판정하고, 장부에 없는 건만 한 줄씩 추가한다.
누적 벌금 = 장부 합계 (봇 기록 + 사람이 넣은 '조정' 줄).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from .config import (MEMBERS, PENALTY, PENALTY_DB_ID, REASON_ADJUST,
                     REASON_NOPLAN, REASON_NOPROOF)


@dataclass
class PenaltyLedger:
    totals: dict[str, int]              # notion_id -> 벌금 합
    recorded: set[tuple[str, date]]     # 봇이 이미 기록한 (담당자, 날짜)


def read_penalties(client) -> PenaltyLedger:
    totals: dict[str, int] = defaultdict(int)
    recorded: set[tuple[str, date]] = set()
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = client._post(f"/databases/{PENALTY_DB_ID}/query", body)
        for row in data["results"]:
            p = row["properties"]
            ppl = p.get("담당자", {}).get("people", [])
            if not ppl:
                continue
            mid = ppl[0]["id"]
            totals[mid] += p.get("금액", {}).get("number") or 0
            reason = (p.get("사유", {}).get("select") or {}).get("name")
            dp = (p.get("날짜", {}) or {}).get("date") or {}
            if reason != REASON_ADJUST and dp.get("start"):
                recorded.add((mid, date.fromisoformat(dp["start"][:10])))
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return PenaltyLedger(dict(totals), recorded)


def pending_rows(fail_days: dict[str, set[date]], led: PenaltyLedger,
                 reasons: dict[tuple[str, date], str]) -> list[tuple[str, date, str]]:
    """장부에 아직 없는 확정 실패 -> 기록할 (담당자, 날짜, 사유) 목록. 순수."""
    out = []
    for mid, days in fail_days.items():
        for d in sorted(days):
            if (mid, d) not in led.recorded:
                out.append((mid, d, reasons.get((mid, d), REASON_NOPROOF)))
    return out


def write_rows(client, rows: list[tuple[str, date, str]]) -> None:
    for mid, d, reason in rows:
        name = MEMBERS.get(mid, "?")
        client._post("/pages", {
            "parent": {"database_id": PENALTY_DB_ID},
            "properties": {
                "이름": {"title": [{"text": {"content": f"{name} {d.month}/{d.day} {reason}"}}]},
                "날짜": {"date": {"start": d.isoformat()}},
                "담당자": {"people": [{"id": mid}]},
                "금액": {"number": PENALTY},
                "사유": {"select": {"name": reason}},
                "메모": {"rich_text": [{"text": {"content": "봇 자동 기록"}}]},
            },
        })
