"""낮 시간대 주기 실행: 오늘 카드의 할 일 체크리스트가 전부 체크되면 '인증 완료'로 자동 변경."""
from __future__ import annotations

from datetime import datetime

from dotenv import load_dotenv

from hlc.config import KST, STATUS_DONE, STATUS_PLAN
from hlc.notion import Notion, load_cards


def main() -> None:
    load_dotenv()
    client = Notion()

    today = datetime.now(tz=KST).date()
    cards = load_cards(client, {today})
    flipped = 0
    for c in cards:
        if c.cday == today and not c.is_stub and c.status == STATUS_PLAN and c.complete:
            client.set_status(c.page_id, STATUS_DONE)
            flipped += 1
    print(f"[sync] {today} 완료: {flipped}건 인증완료 반영")


if __name__ == "__main__":
    main()
