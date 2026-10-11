"""Тесты прогресса пользователя (SQLite, та же база, что уроки)."""

import pytest

from src.bot.progress import ProgressStore


@pytest.fixture
def store(tmp_path):
    s = ProgressStore(tmp_path / "lessons.db")
    yield s
    s.close()


def test_new_user_has_no_seen_and_zero_xp(store):
    assert store.seen_lesson_ids(42) == []
    assert store.total_xp(42) == 0
    assert store.completed_count(42) == 0


def test_mark_completed_makes_lesson_seen(store):
    store.mark_completed(42, "backend-beginner-git", correct=3, total=4, xp=10)
    assert store.seen_lesson_ids(42) == ["backend-beginner-git"]
    assert store.completed_count(42) == 1
    assert store.total_xp(42) == 10


def test_progress_is_per_user(store):
    store.mark_completed(42, "backend-beginner-git", correct=3, total=4, xp=10)
    assert store.seen_lesson_ids(7) == []
    assert store.total_xp(7) == 0


def test_retake_overwrites_result_not_duplicates(store):
    store.mark_completed(42, "backend-beginner-git", correct=3, total=4, xp=10)
    store.mark_completed(42, "backend-beginner-git", correct=4, total=4, xp=15)
    assert store.completed_count(42) == 1
    assert store.total_xp(42) == 15, "повторное прохождение перезаписывает результат"


def test_total_xp_sums_across_lessons(store):
    store.mark_completed(42, "l1", correct=4, total=4, xp=10)
    store.mark_completed(42, "l2", correct=2, total=4, xp=5)
    assert store.total_xp(42) == 15


def test_seen_lesson_ids_for_skip_query(store):
    store.mark_completed(42, "l1", correct=4, total=4, xp=10)
    store.mark_completed(42, "l2", correct=2, total=4, xp=5)
    assert set(store.seen_lesson_ids(42)) == {"l1", "l2"}


def test_last_answer_details_are_stored(store):
    store.mark_completed(42, "l1", correct=3, total=4, xp=10)
    row = store.get_result(42, "l1")
    assert row == {"correct": 3, "total": 4, "xp": 10}
    assert store.get_result(42, "nope") is None
