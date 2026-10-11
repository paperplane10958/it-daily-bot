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


# --- геймификация: даты активности и карточки -------------------------------------


def test_activity_dates_from_updated_at(store):
    from datetime import date

    store.mark_completed(42, "l1", correct=4, total=4, xp=10)
    dates = store.activity_dates(42)
    assert dates == [date.today()], "updated_at пишется UTC; для стрика хватает даты"


def test_terms_without_lessons_rows_is_empty(tmp_path):
    """Пройденный урок, отсутствующий в таблице lessons, карточек не даёт."""
    from src.agent.store import LessonStore

    db = tmp_path / "lessons.db"
    LessonStore(db).close()  # создаёт таблицу lessons (пустую)
    ps = ProgressStore(db)
    ps.mark_completed(42, "ghost-lesson", correct=4, total=4, xp=10)
    assert ps.terms(42) == []
    ps.close()


def test_terms_joined_from_lessons_db(tmp_path):
    """terms() объединяет key_terms завершённых уроков из таблицы lessons."""
    import json
    from pathlib import Path

    from src.agent.store import LessonStore
    from src.bot.progress import ProgressStore

    docs = Path(__file__).resolve().parents[1] / "docs"
    lesson = json.loads((docs / "examples" / "lesson-what-is-the-internet.json").read_text(encoding="utf-8"))
    lesson["id"] = "r1-t1"
    lesson["roadmap"]["order"] = 1
    lesson["key_terms"] = [{"term": "Сервер", "definition": "Мощный компьютер"}]

    lessons_db = tmp_path / "lessons.db"
    ls = LessonStore(lessons_db)
    ls.upsert_lesson(lesson)
    ls.close()

    ps = ProgressStore(lessons_db)
    ps.mark_completed(42, "r1-t1", correct=1, total=1, xp=10)
    terms = ps.terms(42)
    ps.close()
    assert terms == [("Сервер", "Мощный компьютер", "r1-t1", "Что такое интернет")]
