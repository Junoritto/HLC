from datetime import date

from hlc.discord import GREEN, RED, format_payload
from hlc.judge import MemberDetail, Penalty, Report, TodayStatus, YdayResult


def _report(**over):
    base = dict(
        run_day=date(2026, 7, 6),
        yesterday=date(2026, 7, 5),
        yesterday_results=[YdayResult("준호", True, ""), YdayResult("종서", False, "인증 미이행")],
        today_status=[TodayStatus("준호", True), TodayStatus("종서", False)],
        penalties=[Penalty("준호", 0, 0), Penalty("종서", 2, 6000)],
        pot=6000,
        members_detail=[
            MemberDetail("준호", True, [("듀오링고", True), ("운동", True)],
                         True, True, "", [("듀오링고", True)], ["https://x/p.png"], 0),
            MemberDetail("종서", False, [], True, False, "인증 미이행", [("영어", False)], [], 6000),
        ],
    )
    base.update(over)
    return Report(**base)


def test_summary_and_member_embeds_built():
    content, embeds, refs = format_payload(_report())
    assert "7/6 HLC 리포트" in content and "6,000원" in content
    # 요약 1 + 멤버 2
    assert len(embeds) == 3
    # 요약 필드
    joined = str(embeds[0])
    assert "인증 미이행" in joined and "회식비 창고" in joined


def test_member_embed_color_by_result():
    _, embeds, _ = format_payload(_report())
    assert embeds[1]["color"] == GREEN   # 준호 성공
    assert embeds[2]["color"] == RED     # 종서 실패


def test_plan_and_execution_rendered_with_checkboxes():
    _, embeds, _ = format_payload(_report())
    junho = embeds[1]
    plan = next(f["value"] for f in junho["fields"] if "오늘 계획" in f["name"])
    assert "☑ 듀오링고" in plan and "☑ 운동" in plan
    yday = next(f["value"] for f in junho["fields"] if "어제 이행" in f["name"])
    assert "☑ 듀오링고" in yday


def test_photo_ref_points_to_member_embed():
    _, embeds, refs = format_payload(_report())
    # 준호(사진 1장) -> embed index 1 참조
    assert refs == [(1, "https://x/p.png", 1)]
    assert embeds[1]["footer"]["text"] == "📷 인증 사진 1장"


def test_missing_today_shows_dash():
    _, embeds, _ = format_payload(_report())
    jongseo = embeds[2]
    plan = next(f["value"] for f in jongseo["fields"] if "오늘 계획" in f["name"])
    assert "미제출" in plan


def test_pre_go_live_member_neutral_no_yday_field():
    from hlc.discord import BLURPLE
    rep = _report(
        yesterday_results=[],
        members_detail=[MemberDetail("준호", True, [("듀오링고", False)],
                                     False, False, "", [], [], 0)],
    )
    _, embeds, _ = format_payload(rep)
    assert embeds[1]["color"] == BLURPLE
    assert all("어제 이행" not in f["name"] for f in embeds[1]["fields"])
