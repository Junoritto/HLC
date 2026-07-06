from datetime import date

from hlc.discord import format_report
from hlc.judge import Penalty, Report, TodayStatus, YdayResult


def test_format_report_contains_key_parts():
    r = Report(
        run_day=date(2026, 7, 6),
        yesterday=date(2026, 7, 5),
        yesterday_results=[
            YdayResult("준호", True, ""),
            YdayResult("종서", False, "인증 미이행"),
        ],
        today_status=[TodayStatus("준호", True), TodayStatus("종서", False)],
        penalties=[Penalty("준호", 0, 0), Penalty("종서", 2, 6000)],
        pot=6000,
    )
    text = format_report(r)
    assert "7/6 HLC 리포트" in text
    assert "✅ 준호" in text
    assert "❌ 종서(인증 미이행)" in text
    assert "⛔ 종서(미제출)" in text
    assert "종서 6,000" in text
    assert "회식비 창고: **6,000원**" in text
