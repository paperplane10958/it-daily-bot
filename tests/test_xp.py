"""Правило начисления XP за квиз."""

from src.lessons.xp import award_xp


def test_perfect_quiz_gets_full_xp():
    assert award_xp(4, 4, 15) == 15


def test_partial_quiz_gets_half_xp():
    # половина с округлением ВВЕРХ (награда не должна быть обидной)
    assert award_xp(3, 4, 15) == 8
    assert award_xp(2, 4, 15) == 8


def test_zero_correct_gets_zero_xp():
    assert award_xp(0, 4, 15) == 0
