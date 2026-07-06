"""Discord 리포트 포맷(순수) + 웹훅 발송(IO)."""
from __future__ import annotations

import os

import requests

from .judge import Report


def _md(d) -> str:
    return f"{d.month}/{d.day}"


def _won(n: int) -> str:
    return f"{n:,}"


def format_report(r: Report) -> str:
    lines = [f"📅 **{_md(r.run_day)} HLC 리포트**", "━━━━━━━━━━━━━━"]

    lines.append(f"__어제({_md(r.yesterday)}) 결과__")
    if r.yesterday_results:
        yday = "   ".join(
            f"✅ {x.name}" if x.ok else f"❌ {x.name}({x.note})"
            for x in r.yesterday_results
        )
        lines.append(f"  {yday}")
    else:
        lines.append("  (가동 전 — 판정 없음)")

    lines.append(f"__오늘({_md(r.run_day)}) 계획 제출__")
    today = "   ".join(
        f"✅ {x.name}" if x.submitted else f"⛔ {x.name}(미제출)"
        for x in r.today_status
    )
    lines.append(f"  {today}")

    lines.append("━━━━━━━━━━━━━━")
    lines.append("💰 **누적 벌금**")
    pen = " · ".join(f"{p.name} {_won(p.won)}" for p in r.penalties)
    lines.append(f"  {pen}")
    lines.append(f"  🏦 회식비 창고: **{_won(r.pot)}원**")
    return "\n".join(lines)


def send(text: str, webhook_url: str | None = None) -> None:
    url = webhook_url or os.environ["DISCORD_WEBHOOK_URL"]
    resp = requests.post(url, json={"content": text}, timeout=15)
    resp.raise_for_status()
