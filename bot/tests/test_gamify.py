"""Тесты геймификации: стрик по датам активности и уровни по XP."""

from datetime import date

from src.lessons.gamify import level_for_xp, level_progress, streak_from_dates


def test_streak_today_only():
    today = date(2026, 10, 11)
    assert streak_from_dates([today], today) == 1


def test_streak_three_days_in_row():
    today = date(2026, 10, 11)
    dates = [today, date(2026, 10, 10), date(2026, 10, 9)]
    assert streak_from_dates(dates, today) == 3


def test_streak_gap_breaks_chain():
    today = date(2026, 10, 11)
    # 9-е пропущено: цепочка 10-11 = 2
    dates = [today, date(2026, 10, 10), date(2026, 10, 8)]
    assert streak_from_dates(dates, today) == 2


def test_streak_alive_if_last_activity_yesterday():
    today = date(2026, 10, 11)
    dates = [date(2026, 10, 10), date(2026, 10, 9)]
    assert streak_from_dates(dates, today) == 2, "стрик жив, пока не пропущен день"


def test_streak_dead_after_idle_day():
    today = date(2026, 10, 11)
    dates = [date(2026, 10, 9), date(2026, 10, 8)]
    assert streak_from_dates(dates, today) == 0, "пропущен день 10-го — стрик сгорел"


def test_streak_empty_is_zero():
    assert streak_from_dates([], date(2026, 10, 11)) == 0


def test_streak_dedupes_and_ignores_future():
    today = date(2026, 10, 11)
    dates = [today, today, date(2026, 10, 12)]  # будущее не считается
    assert streak_from_dates(dates, today) == 1


def test_level_starts_at_1():
    assert level_for_xp(0) == 1


def test_level_grows_every_100_xp():
    assert level_for_xp(99) == 1
    assert level_for_xp(100) == 2
    assert level_for_xp(250) == 3


def test_level_progress_shows_way_to_next_level():
    assert level_progress(250) == (3, 50, 100), "(уровень, XP внутри уровня, порог)"
