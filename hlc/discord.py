"""Discord — 리치 리포트(임베드) 발송 + ✅ 반응 읽어 정정 대상 추출.

리포트 발송: 웹훅(발신). 반응 읽기/이모지 달기: 봇 토큰(REST).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import requests

from .config import (CORRECT_EMOJI, CORRECTION_DAYS, DISCORD_CHANNEL_ID,
                     DISCORD_TO_NOTION, KST)
from .judge import Report

API = "https://discord.com/api/v10"
BLURPLE, GREEN, RED, AMBER = 0x5865F2, 0x23A55A, 0xF23F42, 0xE0A53A
EMOJI_ENC = requests.utils.quote(CORRECT_EMOJI)


def _md(d) -> str:
    return f"{d.month}/{d.day}"


def _won(n: int) -> str:
    return f"{n:,}"


def _fmt_items(items: list[tuple[str, bool]]) -> str:
    if not items:
        return "—"
    return "\n".join(("☑ " if ch else "☐ ") + t for t, ch in items)


# ---------- 리포트 임베드 구성 (순수) ----------

def format_payload(report: Report, settlement=None):
    """(content, embeds, photo_refs) 반환. photo_refs=[(embed_index, url, 장수)]."""
    r = report
    _P = {"ok": "✅", "pending": "⏳", "fail": "❌", "noplan": "⛔"}

    def line(results):
        if not results:
            return "(가동 전 — 판정 없음)"
        return "   ".join(
            f"{_P[x.state]} {x.name}" + (f"({x.note})" if x.note else "") for x in results
        )

    fields = [{"name": f"어제({_md(r.pending_day)}) — 잠정", "value": line(r.pending_results), "inline": False}]
    # 그저께 확정: 실패가 있을 때만 강조
    conf_fail = [x for x in r.confirm_results if x.state == "fail"]
    if conf_fail:
        fields.append({"name": f"🔒 {_md(r.confirm_day)} 확정 실패",
                       "value": "   ".join(f"❌ {x.name}" for x in conf_fail), "inline": False})
    today = "   ".join(
        f"✅ {x.name}" if x.submitted else f"⛔ {x.name}(미제출)" for x in r.today_status
    )
    fields.append({"name": f"오늘({_md(r.run_day)}) 계획 제출", "value": today, "inline": False})
    pen = " · ".join(f"{p.name} {_won(p.won)}" for p in r.penalties)
    if settlement is not None:
        fields.append({"name": "💰 발생 벌금(누적)", "value": pen, "inline": False})
        unpaid = " · ".join(f"{m.name} {_won(m.unpaid)}" for m in settlement.members)
        fields.append({"name": "🧾 정산 현황",
                       "value": f"미납  {unpaid}\n🏦 창고 잔액 **{_won(settlement.balance)}원** "
                                f"(입금 {_won(settlement.total_paid)} − 지출 {_won(settlement.spent)})",
                       "inline": False})
    else:
        fields.append({"name": "💰 누적 벌금",
                       "value": f"{pen}\n🏦 회식비 창고 **{_won(r.pot)}원**", "inline": False})
    if r.pending_prompt_names:
        who = ", ".join(r.pending_prompt_names)
        fields.append({"name": "⏳ 미인증 정정",
                       "value": f"**{who}** — 진짜 했으면 이 메시지에 {CORRECT_EMOJI} 눌러줘 "
                                f"(내일까지 정정, 안 하면 실패 확정)", "inline": False})

    embeds = [{"title": f"📅 {_md(r.run_day)} HLC 리포트", "color": BLURPLE, "fields": fields}]

    photo_refs = []
    for d in r.members_detail:
        color = {"ok": GREEN, "pending": AMBER}.get(d.yday_state, BLURPLE if not d.yday_judged else RED)
        head = {"ok": "  ·  어제 ✅", "pending": "  ·  어제 ⏳ 미인증",
                "noplan": "  ·  어제 ⛔"}.get(d.yday_state, "") if d.yday_judged else ""
        f = [{"name": "📋 오늘 계획",
              "value": _fmt_items(d.plan_items) if d.today_submitted else "— (미제출)", "inline": False}]
        if d.yday_judged:
            f.append({"name": "✅ 어제 이행", "value": _fmt_items(d.yday_items), "inline": False})
        embed = {"title": f"{d.name}{head}", "color": color, "fields": f}
        if d.photo_urls:
            embed["footer"] = {"text": f"📷 인증 사진 {len(d.photo_urls)}장"}
        embeds.append(embed)
        if d.photo_urls:
            photo_refs.append((len(embeds) - 1, d.photo_urls[0], len(d.photo_urls)))

    content = f"📅 {_md(r.run_day)} HLC 리포트 · 창고 {_won(r.pot)}원"
    return content, embeds, photo_refs


# ---------- 발송 (웹훅) + ✅ 미리 달기 (봇) ----------

def send_report(report: Report, webhook_url: str | None = None, bot_token: str | None = None,
                settlement=None) -> None:
    url = webhook_url or os.environ["DISCORD_WEBHOOK_URL"]
    content, embeds, photo_refs = format_payload(report, settlement)

    files = []
    for i, (idx, src, _n) in enumerate(photo_refs):
        try:
            resp = requests.get(src, timeout=20); resp.raise_for_status()
            fn = f"proof_{i}.png"
            files.append((f"files[{i}]", (fn, resp.content)))
            embeds[idx]["image"] = {"url": f"attachment://{fn}"}
        except requests.RequestException:
            pass

    payload = {"content": content, "embeds": embeds}
    # wait=true -> 메시지 객체(id) 회수
    post_url = url + ("&" if "?" in url else "?") + "wait=true"
    if files:
        r = requests.post(post_url, data={"payload_json": json.dumps(payload)}, files=files, timeout=40)
    else:
        r = requests.post(post_url, json=payload, timeout=40)
    r.raise_for_status()

    # ⏳ 미인증이 있으면 봇이 ✅ 미리 달아 원터치 정정 유도
    if report.pending_prompt_names:
        token = bot_token or os.environ.get("DISCORD_BOT_TOKEN")
        msg = r.json()
        if token and msg.get("id"):
            try:
                requests.put(f"{API}/channels/{msg['channel_id']}/messages/{msg['id']}"
                             f"/reactions/{EMOJI_ENC}/@me",
                             headers={"Authorization": f"Bot {token}"}, timeout=15)
            except requests.RequestException:
                pass


def send_correction_notice(corrected: list[tuple[str, object]], pot: int,
                           webhook_url: str | None = None) -> None:
    """정정된 건을 채널에 투명하게 공지."""
    url = webhook_url or os.environ["DISCORD_WEBHOOK_URL"]
    lines = [f"🔧 {name} {_md(cday)} 정정 인증 완료 (벌금 취소)" for name, cday in corrected]
    lines.append(f"🏦 회식비 창고 **{_won(pot)}원**")
    requests.post(url, json={"content": "\n".join(lines)}, timeout=20).raise_for_status()


# ---------- 반응 읽어 정정 대상 추출 (봇) ----------

def fetch_corrections(today, bot_token: str | None = None, channel_id: str | None = None):
    """최근 리포트 메시지의 ✅ 반응을 읽어, 정정 대상 (notion_id, cday) 목록 반환.

    - 리포트가 다루는 날 = 메시지 게시일(KST) - 1 (= 그 리포트의 '어제').
    - 정정 가능: cday >= today - CORRECTION_DAYS.
    - 본인 반응만 본인 정정 (매핑된 유저만).
    """
    token = bot_token or os.environ["DISCORD_BOT_TOKEN"]
    cid = channel_id or DISCORD_CHANNEL_ID
    h = {"Authorization": f"Bot {token}"}
    msgs = requests.get(f"{API}/channels/{cid}/messages?limit=25", headers=h, timeout=20)
    msgs.raise_for_status()

    out = []
    for m in msgs.json():
        # 봇은 남의 메시지 본문(content)을 못 읽음(특권 인텐트) → 웹훅 게시물로 식별
        if not m.get("webhook_id"):
            continue
        if not any(rx["emoji"].get("name") == CORRECT_EMOJI for rx in m.get("reactions", [])):
            continue
        ts = datetime.fromisoformat(m["timestamp"]).astimezone(KST)
        cday = ts.date() - timedelta(days=1)
        if cday < today - timedelta(days=CORRECTION_DAYS):
            continue                        # 정정 기간 지남
        users = requests.get(f"{API}/channels/{cid}/messages/{m['id']}/reactions/{EMOJI_ENC}",
                             headers=h, timeout=20)
        if users.status_code != 200:
            continue
        for u in users.json():
            notion_id = DISCORD_TO_NOTION.get(u["id"])
            if notion_id:
                out.append((notion_id, cday))
    return out
