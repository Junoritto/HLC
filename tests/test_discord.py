from datetime import date

from hlc.discord import AMBER, GREEN, format_payload
from hlc.judge import DayResult, MemberDetail, Penalty, Report, TodayStatus


def _report(**over):
    base = dict(
        run_day=date(2026, 7, 10),
        pending_day=date(2026, 7, 9),
        confirm_day=date(2026, 7, 8),
        pending_results=[DayResult("준호", "ok"), DayResult("종서", "pending", "미인증")],
        confirm_results=[DayResult("준호", "ok"), DayResult("종서", "fail", "인증 미이행")],
        today_status=[TodayStatus("준호", True), TodayStatus("종서", False)],
        penalties=[Penalty("준호", 0, 0), Penalty("종서", 1, 3000)],
        pot=3000,
        members_detail=[
            MemberDetail("준호", True, [("듀오링고", True)], True, "ok", [("듀오링고", True)],
                         ["https://x/p.png"], 0),
            MemberDetail("종서", True, [("영어", False)], True, "pending", [], [], 0),
        ],
        pending_prompt_names=["종서"],
    )
    base.update(over)
    return Report(**base)


def test_summary_shows_pending_and_confirm_and_prompt():
    content, embeds, refs = format_payload(_report())
    s = str(embeds[0])
    assert "⏳ 종서(미인증)" in s          # 어제 잠정
    assert "🔒" in s and "❌ 종서" in s     # 그저께 확정 실패
    assert "✅ 눌러" in s                    # 정정 프롬프트
    assert "3,000원" in content


def test_member_embed_color_by_state():
    _, embeds, _ = format_payload(_report())
    assert embeds[1]["color"] == GREEN      # 준호 ok
    assert embeds[2]["color"] == AMBER      # 종서 pending


def test_photo_ref_and_footer():
    _, embeds, refs = format_payload(_report())
    assert refs == [(1, "https://x/p.png", 1)]
    assert embeds[1]["footer"]["text"] == "📷 인증 사진 1장"


def test_no_prompt_when_none_pending():
    _, embeds, _ = format_payload(_report(pending_prompt_names=[]))
    assert all("✅ 눌러" not in str(e) for e in embeds)
