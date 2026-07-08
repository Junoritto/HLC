"""Notion 원본 페이지/블록 -> 판정에 쓰는 Card 구조로 정규화."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from . import core
from .config import STATUS_PROP


@dataclass(frozen=True)
class Card:
    page_id: str
    assignee_id: str | None
    status: str
    cday: date                 # challenge_day (createdTime 기준)
    complete: bool             # 할 일 체크리스트 전부 체크됨
    created_utc: datetime
    last_edited_utc: datetime
    is_stub: bool = False                       # 스크립트가 만든 미제출 실패 카드
    items: list[tuple[str, bool]] = field(default_factory=list)  # 할 일 (텍스트, 체크여부)
    photo_urls: list[str] = field(default_factory=list)          # 인증 사진 URL

    @classmethod
    def from_notion(cls, page: dict, blocks: list[dict]) -> "Card":
        props = page["properties"]
        people = props.get("담당자", {}).get("people", [])
        assignee = people[0]["id"] if people else None
        status_obj = props.get(STATUS_PROP, {}).get("status") or {}
        created = datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))
        edited = datetime.fromisoformat(page["last_edited_time"].replace("Z", "+00:00"))
        title = _title(props)
        files = props.get("인증 사진", {}).get("files", [])
        photo_urls = [u for u in
                      ((f.get("file") or f.get("external") or {}).get("url", "") for f in files) if u]
        return cls(
            page_id=page["id"],
            assignee_id=assignee,
            status=status_obj.get("name", ""),
            cday=core.challenge_day(created),
            complete=core.is_card_complete(blocks),
            created_utc=created,
            last_edited_utc=edited,
            is_stub=title.startswith("[HLC] 미제출"),
            items=core.task_items(blocks),
            photo_urls=photo_urls,
        )


def succeeded(c: Card) -> bool:
    """성공 = 할 일 체크리스트 올체크. (사진은 전시·증거용, 판정 기준 아님)

    체크 깜빡 등 억울한 경우는 Discord ✅ 반응 정정으로 구제한다.
    """
    return (not c.is_stub) and c.complete


def _title(props: dict) -> str:
    for p in props.values():
        if p.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in p.get("title", []))
    return ""
