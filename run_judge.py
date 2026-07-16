"""매일 08:00 KST: 어제=잠정(⏳) / 그저께=확정 판정 + 오늘 미제출 처리 + Discord 리포트."""
from __future__ import annotations

from datetime import datetime, timedelta

from dotenv import load_dotenv

from hlc import discord, judge, ledger
from hlc import penalty_ledger as pl
from hlc.config import KST, MEMBERS, PENALTY
from hlc.judge import Penalty
from hlc.notion import Notion, load_cards


def main() -> None:
    load_dotenv()
    client = Notion()

    today = datetime.now(tz=KST).date()
    focus = {today, today - timedelta(days=1), today - timedelta(days=2)}
    cards = load_cards(client, focus)
    plan = judge.build_plan(cards, today, MEMBERS)

    # 1) 상태 변경 (승격 인증완료 / 확정 실패)
    for page_id, status in plan.finalize:
        client.set_status(page_id, status)

    # 2) 오늘 계획 미제출 -> 실패 stub (중복 방지)
    existing_stub = {(c.assignee_id, c.cday) for c in cards if c.is_stub}
    for member_id in plan.missing:
        if (member_id, today) not in existing_stub:
            client.create_stub(member_id, today)

    # 3) 목표일 자동 기입 — 비어 있을 때만 (사용자가 찍은 목표일은 절대 덮어쓰지 않음)
    for c in cards:
        if not c.is_stub and c.cday in focus and c.date_field is None:
            client.set_date(c.page_id, c.cday)

    # 4) 벌금 장부: 확정된 실패 중 아직 기록 안 된 건만 추가 (중복 방지)
    led = pl.read_penalties(client)
    new_rows = pl.pending_rows(plan.report.fail_days, led, plan.report.fail_reasons)
    pl.write_rows(client, new_rows)
    if new_rows:
        led = pl.read_penalties(client)      # 기록 후 재조회

    # 5) 누적 벌금 = 장부 합계 (봇 기록 + 사람이 넣은 '조정')
    plan.report.penalties = [
        Penalty(name, led.totals.get(mid, 0) // PENALTY, led.totals.get(mid, 0))
        for mid, name in MEMBERS.items()
    ]
    plan.report.pot = sum(led.totals.values())

    # 6) 리포트 발송 (장부 현황 + 그날 확정분 + 정산/사진/✅ 프롬프트)
    settlement = ledger.build_settlement(plan.report.penalties, MEMBERS, ledger.read_ledger(client))
    newly = [(MEMBERS.get(m, "?"), d, r) for m, d, r in new_rows]
    discord.send_report(plan.report, settlement=settlement, new_penalties=newly)
    print(f"[judge] {today} 완료: finalize={len(plan.finalize)} stub={len(plan.missing)} "
          f"장부기록={len(new_rows)}건 누적={plan.report.pot:,}원")


if __name__ == "__main__":
    main()
