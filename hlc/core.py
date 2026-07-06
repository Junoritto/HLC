"""순수 로직 — 외부 IO 없음. 전부 단위 테스트 대상."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .config import DEADLINE_HOUR, KST, PENALTY, TASK_HEADING


def challenge_day(created_utc: datetime) -> date:
    """카드 생성 시각(UTC aware) -> 그 카드가 속한 challenge day.

    규칙: 업로드는 해당 날짜 08:00 KST까지 유효. 08:00 정각까지는 그날로,
    08:00를 지나면 다음날로 집계한다("8시 이후 업로드는 다음날").
    """
    kst = created_utc.astimezone(KST)
    deadline = kst.replace(hour=DEADLINE_HOUR, minute=0, second=0, microsecond=0)
    return kst.date() if kst <= deadline else kst.date() + timedelta(days=1)


def _block_text(block: dict) -> str:
    t = block.get("type", "")
    rich = block.get(t, {}).get("rich_text", [])
    return "".join(r.get("plain_text", "") for r in rich).strip()


def task_items(blocks: list[dict]) -> list[tuple[str, bool]]:
    """'할 일 체크리스트' 헤딩 아래의 (할 일 텍스트, 체크여부) 목록.

    - 다음 heading을 만나면 섹션 종료.
    - 텍스트가 빈 to_do(템플릿 빈칸)는 제외.
    - '✅ 인증 체크' 등 다른 섹션의 체크박스는 포함하지 않는다.
    """
    result: list[tuple[str, bool]] = []
    in_section = False
    for b in blocks:
        btype = b.get("type", "")
        if btype.startswith("heading"):
            in_section = TASK_HEADING in _block_text(b)
            continue
        if in_section and btype == "to_do":
            txt = _block_text(b)
            if txt:  # 빈칸 무시
                result.append((txt, bool(b["to_do"].get("checked"))))
    return result


def task_todos(blocks: list[dict]) -> list[bool]:
    return [checked for _, checked in task_items(blocks)]


def is_card_complete(blocks: list[dict]) -> bool:
    """할 일 체크리스트에 실제 항목이 있고, 전부 체크되면 True."""
    todos = task_todos(blocks)
    return len(todos) > 0 and all(todos)


def penalty_won(fail_count: int) -> int:
    return fail_count * PENALTY
