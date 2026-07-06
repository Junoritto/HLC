"""Discord 리치 리포트 — 임베드 구성(순수) + 사진 재업로드 발송(IO)."""
from __future__ import annotations

import json
import os

import requests

from .judge import Report

BLURPLE = 0x5865F2
GREEN = 0x23A55A
RED = 0xF23F42


def _md(d) -> str:
    return f"{d.month}/{d.day}"


def _won(n: int) -> str:
    return f"{n:,}"


def _fmt_items(items: list[tuple[str, bool]]) -> str:
    if not items:
        return "—"
    return "\n".join(("☑ " if ch else "☐ ") + t for t, ch in items)


def format_payload(report: Report):
    """(content, embeds, photo_refs) 반환. photo_refs = [(embed_index, url, 사진수)]. 순수."""
    r = report

    # --- 요약 임베드 ---
    if r.yesterday_results:
        yday = "   ".join(
            f"✅ {x.name}" if x.ok else f"❌ {x.name}({x.note})" for x in r.yesterday_results
        )
    else:
        yday = "(가동 전 — 판정 없음)"
    today = "   ".join(
        f"✅ {x.name}" if x.submitted else f"⛔ {x.name}(미제출)" for x in r.today_status
    )
    pen = " · ".join(f"{p.name} {_won(p.won)}" for p in r.penalties)

    embeds = [{
        "title": f"📅 {_md(r.run_day)} HLC 리포트",
        "color": BLURPLE,
        "fields": [
            {"name": f"어제({_md(r.yesterday)}) 결과", "value": yday, "inline": False},
            {"name": f"오늘({_md(r.run_day)}) 계획 제출", "value": today, "inline": False},
            {"name": "💰 누적 벌금",
             "value": f"{pen}\n🏦 회식비 창고 **{_won(r.pot)}원**", "inline": False},
        ],
    }]

    # --- 멤버별 임베드 ---
    photo_refs = []
    for d in r.members_detail:
        if not d.yday_judged:
            color, head = BLURPLE, ""
        elif d.yday_ok:
            color, head = GREEN, "  ·  어제 ✅ 성공"
        else:
            color, head = RED, f"  ·  어제 ❌ {d.yday_note}"

        fields = [{"name": "📋 오늘 계획",
                   "value": _fmt_items(d.plan_items) if d.today_submitted else "— (미제출)",
                   "inline": False}]
        if d.yday_judged:
            fields.append({"name": "✅ 어제 이행",
                           "value": _fmt_items(d.yday_items), "inline": False})

        embed = {"title": f"{d.name}{head}", "color": color, "fields": fields}
        if d.photo_urls:
            embed["footer"] = {"text": f"📷 인증 사진 {len(d.photo_urls)}장"}
        embeds.append(embed)
        if d.photo_urls:
            photo_refs.append((len(embeds) - 1, d.photo_urls[0], len(d.photo_urls)))

    content = f"📅 {_md(r.run_day)} HLC 리포트 · 창고 {_won(r.pot)}원"
    return content, embeds, photo_refs


def send_report(report: Report, webhook_url: str | None = None) -> None:
    url = webhook_url or os.environ["DISCORD_WEBHOOK_URL"]
    content, embeds, photo_refs = format_payload(report)

    files = []
    for i, (idx, src, _cnt) in enumerate(photo_refs):
        try:
            resp = requests.get(src, timeout=20)
            resp.raise_for_status()
            fn = f"proof_{i}.png"
            files.append((f"files[{i}]", (fn, resp.content)))
            embeds[idx]["image"] = {"url": f"attachment://{fn}"}
        except requests.RequestException:
            pass  # 사진 실패해도 리포트 본문은 보냄

    payload = {"content": content, "embeds": embeds}
    if files:
        r = requests.post(url, data={"payload_json": json.dumps(payload)}, files=files, timeout=40)
    else:
        r = requests.post(url, json=payload, timeout=40)
    r.raise_for_status()
