"""낮 시간대 주기 실행: 오늘 카드의 할 일 체크리스트가 전부 체크되면 '인증 완료'로 자동 변경."""
from __future__ import annotations

from datetime import datetime

from dotenv import load_dotenv

from hlc.config import KST
from hlc.notion import Notion, load_cards
from hlc.sync import reconcile_targets


def main() -> None:
    load_dotenv()
    client = Notion()

    today = datetime.now(tz=KST).date()
    cards = load_cards(client, {today})
    targets = reconcile_targets(cards, today)
    for page_id, status in targets:
        client.set_status(page_id, status)
    print(f"[sync] {today} 완료: {len(targets)}건 상태 교정 (체크박스 기준)")


if __name__ == "__main__":
    main()
