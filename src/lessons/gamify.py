"""Геймификация: стрик по датам активности и уровни по XP.

Чистые функции без I/O — даты и XP подают хендлеры, беря их из progress.
Стрик = дни подряд с пройденными уроками до сегодня (или вчера — ещё жив,
сегодняшний день в запасе). Уровень = 1 + 100 XP за уровень.
"""

import datetime as dt

XP_PER_LEVEL = 100


def streak_from_dates(dates: list[dt.date], today: dt.date) -> int:
    """Длина цепочки дней активности, заканчивающейся сегодня или вчера.

    Дедуплицирует вход, игнорирует будущие даты. Пропущенный день рвёт цепочку.
    """
    unique = sorted({d for d in dates if d <= today}, reverse=True)
    if not unique:
        return 0
    if unique[0] not in (today, today - dt.timedelta(days=1)):
        return 0
    streak = 1
    for prev, cur in zip(unique, unique[1:]):
        if (prev - cur).days == 1:
            streak += 1
        else:
            break
    return streak


def level_for_xp(xp: int) -> int:
    """Уровень: 1 + xp // XP_PER_LEVEL."""
    return 1 + xp // XP_PER_LEVEL


def level_progress(xp: int) -> tuple[int, int, int]:
    """(уровень, XP внутри текущего уровня, порог следующего уровня)."""
    level = level_for_xp(xp)
    return level, xp % XP_PER_LEVEL, XP_PER_LEVEL
