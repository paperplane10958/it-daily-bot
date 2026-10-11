"""Правило начисления XP за квиз: полный XP — за идеальный результат, иначе половина."""

import math


def award_xp(correct: int, total: int, base_xp: int) -> int:
    """XP за прохождение квиза: 100% верных -> base_xp, иначе половина (округление вверх)."""
    if correct >= total:
        return base_xp
    if correct == 0:
        return 0
    return math.ceil(base_xp / 2)
