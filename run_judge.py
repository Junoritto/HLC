"""매일 08:00 KST 실행: 어제 카드 마감 + 오늘 계획 미제출 처리 + Discord 리포트."""
from __future__ import annotations

from datetime import datetime, timedelta

from dotenv import load_dotenv

from hlc import discord, judge
from hlc.config import KST, MEMBERS
from hlc.notion import Notion, load_cards


def main() -> None:
    load_dotenv()  # 로컬 실행용(.env). GH Actions에선 env가 이미 주입됨 → no-op
    client = Notion()

    today = datetime.now(tz=KST).date()          # challenge day D (08:00 KST 실행)
    yesterday = today - timedelta(days=1)
    cards = load_cards(client, {today, yesterday})
    plan = judge.build_plan(cards, today, MEMBERS)

    # 1) 어제 카드 마감 (인증완료/실패)
    for page_id, status in plan.finalize:
        client.set_status(page_id, status)

    # 2) 오늘 계획 미제출 -> 실패 stub (중복 생성 방지)
    existing_stub = {(c.assignee_id, c.cday) for c in cards if c.is_stub}
    for member_id in plan.missing:
        if (member_id, today) not in existing_stub:
            client.create_stub(member_id, today)

    # 3) 날짜 필드 자동 기입 (기존 결함 보정) — 어제/오늘 실카드
    for c in cards:
        if not c.is_stub and c.cday in {today, yesterday}:
            client.set_date(c.page_id, c.cday)

    # 4) 리포트 발송 (임베드 + 인증사진 첨부)
    discord.send_report(plan.report)
    print(f"[judge] {today} 완료: finalize={len(plan.finalize)} stub={len(plan.missing)}")


if __name__ == "__main__":
    main()
