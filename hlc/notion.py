"""Notion API 클라이언트 (IO). 순수 판정 로직은 core/judge에 있다."""
from __future__ import annotations

import os
from datetime import date, datetime

import requests

from . import core
from .config import DATABASE_ID, DATE_PROP, STATUS_FAIL, STATUS_PROP
from .models import Card

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"


class Notion:
    def __init__(self, token: str | None = None):
        token = token or os.environ["NOTION_TOKEN"]
        self.h = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        }

    # ---- 저수준 ----
    def _post(self, path, body):
        r = requests.post(f"{API}{path}", headers=self.h, json=body, timeout=20)
        r.raise_for_status()
        return r.json()

    def _patch(self, path, body):
        r = requests.patch(f"{API}{path}", headers=self.h, json=body, timeout=20)
        r.raise_for_status()
        return r.json()

    def _get(self, path):
        r = requests.get(f"{API}{path}", headers=self.h, timeout=20)
        r.raise_for_status()
        return r.json()

    # ---- 조회 ----
    def all_pages(self) -> list[dict]:
        pages, cursor = [], None
        while True:
            body = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            data = self._post(f"/databases/{DATABASE_ID}/query", body)
            pages.extend(data["results"])
            if not data.get("has_more"):
                return pages
            cursor = data["next_cursor"]

    def blocks(self, page_id: str) -> list[dict]:
        out, cursor = [], None
        while True:
            q = f"?start_cursor={cursor}" if cursor else ""
            data = self._get(f"/blocks/{page_id}/children{q}&page_size=100"
                             if cursor else f"/blocks/{page_id}/children?page_size=100")
            out.extend(data["results"])
            if not data.get("has_more"):
                return out
            cursor = data["next_cursor"]

    # ---- 변경 ----
    def set_status(self, page_id: str, name: str) -> None:
        self._patch(f"/pages/{page_id}",
                    {"properties": {STATUS_PROP: {"status": {"name": name}}}})

    def set_date(self, page_id: str, day: date) -> None:
        self._patch(f"/pages/{page_id}",
                    {"properties": {DATE_PROP: {"date": {"start": day.isoformat()}}}})

    def create_stub(self, assignee_id: str, day: date) -> None:
        title = f"[HLC] 미제출 ({day.month}/{day.day})"
        self._post("/pages", {
            "parent": {"database_id": DATABASE_ID},
            "properties": {
                "이름": {"title": [{"text": {"content": title}}]},
                "담당자": {"people": [{"id": assignee_id}]},
                STATUS_PROP: {"status": {"name": STATUS_FAIL}},
                DATE_PROP: {"date": {"start": day.isoformat()}},
            },
        })


def load_cards(client: Notion, focus_days: set[date]) -> list[Card]:
    """모든 페이지를 Card로. focus_days(어제/오늘)에 해당하는 카드만 블록을 받아
    완료 여부를 계산한다(나머지는 status만 사용하므로 블록 조회 생략)."""
    cards = []
    for page in client.all_pages():
        created = datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))
        cday = core.challenge_day(created)
        blocks = client.blocks(page["id"]) if cday in focus_days else []
        cards.append(Card.from_notion(page, blocks))
    return cards
