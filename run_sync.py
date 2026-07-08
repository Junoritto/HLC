"""낮 주기 실행: ① 오늘 상태를 증거 기준으로 교정 ② ✅ 반응 정정 반영."""
from __future__ import annotations

from datetime import datetime, timedelta

from dotenv import load_dotenv

from hlc import discord, judge
from hlc.config import KST, MEMBERS, STATUS_DONE
from hlc.notion import Notion, load_cards
from hlc.sync import reconcile_targets


def main() -> None:
    load_dotenv()
    client = Notion()
    today = datetime.now(tz=KST).date()
    yday = today - timedelta(days=1)
    cards = load_cards(client, {today, yday})

    # 1) 오늘 카드 상태 교정 (증거 기준)
    targets = reconcile_targets(cards, today)
    for page_id, status in targets:
        client.set_status(page_id, status)

    # 2) ✅ 반응 정정 (본인 반응 -> 본인 어제 카드 인증완료)
    corrected = []
    try:
        for notion_id, cday in discord.fetch_corrections(today):
            for c in cards:
                if (c.assignee_id == notion_id and c.cday == cday
                        and not c.is_stub and c.status != STATUS_DONE):
                    client.set_status(c.page_id, STATUS_DONE)
                    corrected.append((MEMBERS.get(notion_id, "?"), cday))
                    break
    except Exception as e:  # 반응 정정 실패해도 교정은 유지
        print("[sync] 반응 정정 스킵:", e)

    if corrected:
        fresh = load_cards(client, {today, yday, today - timedelta(days=2)})
        pot = judge.build_plan(fresh, today, MEMBERS).report.pot
        discord.send_correction_notice(corrected, pot)

    print(f"[sync] {today} 완료: 상태교정 {len(targets)}건 · 반응정정 {len(corrected)}건")


if __name__ == "__main__":
    main()
