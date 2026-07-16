"""매일 08:00 KST: 어제=잠정(⏳) / 그저께=확정 판정 + 오늘 미제출 처리 + Discord 리포트."""
from __future__ import annotations

from datetime import datetime, timedelta

from dotenv import load_dotenv

from hlc import discord, judge, ledger
from hlc.config import KST, MEMBERS
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

    # 4) 리포트 발송 (임베드 + 사진 + 정산 현황 + ⏳면 봇이 ✅ 미리 달기)
    settlement = ledger.build_settlement(plan.report.penalties, MEMBERS, ledger.read_ledger(client))
    discord.send_report(plan.report, settlement=settlement)
    print(f"[judge] {today} 완료: finalize={len(plan.finalize)} stub={len(plan.missing)}")


if __name__ == "__main__":
    main()
