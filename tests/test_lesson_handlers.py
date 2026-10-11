"""Тесты выдачи урока в боте: /lesson, /progress и квиз по callback-кнопкам.

Хендлеры зависимостью принимают stores (LessonStore / ProgressStore) —
в тестах подставляются фейки, сеть и реальная база не дёргаются.
"""

import json
from pathlib import Path

import pytest

from src.bot.handlers import (
    QUIZ_SELECT_ALL,
    QUIZ_SUBMIT,
    QUIZ_TOGGLE,
    answer_callback,
    cmd_lesson,
    cmd_progress,
    render_progress,
)

DOCS = Path(__file__).resolve().parents[1] / "docs"
EXAMPLE = json.loads(
    (DOCS / "examples" / "lesson-what-is-the-internet.json").read_text(encoding="utf-8")
)


class FakeLessonStore:
    def __init__(self, lessons: list[dict]):
        self.lessons = {l["id"]: l for l in lessons}

    def next_published_lesson(self, seen_ids=None):
        for l in self.lessons.values():
            if l["id"] not in (seen_ids or []):
                return l
        return None

    def get_lesson(self, lesson_id):
        return self.lessons.get(lesson_id)

    def all_published_count(self):
        return len(self.lessons)


class FakeProgressStore:
    def __init__(self):
        self.data: dict[tuple[int, str], dict] = {}

    def seen_lesson_ids(self, user_id):
        return [lid for (uid, lid) in self.data if uid == user_id]

    def total_xp(self, user_id):
        return sum(r["xp"] for (uid, _), r in self.data.items() if uid == user_id)

    def completed_count(self, user_id):
        return sum(1 for (uid, _) in self.data if uid == user_id)

    def mark_completed(self, user_id, lesson_id, correct, total, xp):
        self.data[(user_id, lesson_id)] = {"correct": correct, "total": total, "xp": xp}

    def get_result(self, user_id, lesson_id):
        return self.data.get((user_id, lesson_id))


class FakeMessage:
    def __init__(self, chat_id: int = 42):
        self.chat = type("Chat", (), {"id": chat_id})()
        self.sent: list = []

    async def answer(self, text, **kwargs):
        self.sent.append(("text", text, kwargs))

    async def edit_text(self, text, **kwargs):
        self.sent.append(("edit", text, kwargs))


class FakeCallback:
    def __init__(self, data: str, chat_id: int = 42):
        self.data = data
        self.message = FakeMessage(chat_id)
        self.from_user = type("User", (), {"id": chat_id})()

    async def answer(self):
        pass


def stores():
    return FakeLessonStore([EXAMPLE]), FakeProgressStore()


# --- /lesson ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lesson_sends_messages_and_first_quiz_question():
    lessons, progress = stores()
    msg = FakeMessage()
    await cmd_lesson(msg, lessons, progress)
    texts = [t for _, t, _ in msg.sent]
    assert any(EXAMPLE["title"] in t for t in texts), "интро с заголовком урока"
    assert texts[-1].startswith("❓"), "последнее сообщение — вопрос квиза"
    kb = msg.sent[-1][2]["reply_markup"]
    assert kb is not None, "квиз приходит с кнопками вариантов"


@pytest.mark.asyncio
async def test_lesson_without_lessons_says_nothing_available():
    lessons, progress = FakeLessonStore([]), FakeProgressStore()
    msg = FakeMessage()
    await cmd_lesson(msg, lessons, progress)
    texts = [t for _, t, _ in msg.sent]
    assert any("нет" in t.lower() for t in texts)


@pytest.mark.asyncio
async def test_lesson_skips_seen_lessons():
    lessons, progress = stores()
    progress.mark_completed(42, EXAMPLE["id"], correct=4, total=4, xp=20)
    msg = FakeMessage()
    await cmd_lesson(msg, lessons, progress)
    texts = [t for _, t, _ in msg.sent]
    assert any("прошёл" in t.lower() for t in texts), "все уроки пройдены -> поздравляем"


# --- квиз: выбор и отправка --------------------------------------------------------


@pytest.mark.asyncio
async def test_toggle_marks_option_selected():
    lessons, progress = stores()
    lesson = json.loads(json.dumps(EXAMPLE, ensure_ascii=False))
    lesson["quiz"][0]["kind"] = "multi"  # toggle бывает только у multi
    store = FakeLessonStore([lesson])
    # формат: q:<lid>:<qidx>:<mask>:<optidx>:<ok>
    cb = FakeCallback(f"{QUIZ_TOGGLE}:{lesson['id']}:0:0:1:0")
    await answer_callback(cb, store, progress)
    kb = cb.message.sent[-1][2]["reply_markup"]
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("✓" in l for l in labels), "выбранный вариант отмечается"


@pytest.mark.asyncio
async def test_multi_toggle_then_submit_button_appears():
    lessons, progress = stores()
    lesson = json.loads(json.dumps(EXAMPLE, ensure_ascii=False))
    lesson["quiz"][0]["kind"] = "multi"
    store = FakeLessonStore([lesson])
    # после выбора одного варианта появляется кнопка «Ответить»
    cb = FakeCallback(f"{QUIZ_TOGGLE}:{lesson['id']}:0:0:0:0")
    await answer_callback(cb, store, progress)
    kb = cb.message.sent[-1][2]["reply_markup"]
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Ответить" in l for l in labels), "есть кнопка Ответить"


@pytest.mark.asyncio
async def test_submit_scores_correct_answer():
    lessons, progress = stores()
    lesson_id = EXAMPLE["id"]
    q = EXAMPLE["quiz"][0]
    correct_idx = q["correct"][0]
    # формат submit: s:<lid>:<qidx>:<mask>:<ok>; маска = бит выбранного варианта
    cb = FakeCallback(f"{QUIZ_SUBMIT}:{lesson_id}:0:{1 << correct_idx}:0")
    await answer_callback(cb, lessons, progress)
    texts = [t for _, t, _ in cb.message.sent]
    assert any("Верно!" in t for t in texts), "должен похвалить и показать explanation"
    assert any(q["explanation"][:40] in t for t in texts)


@pytest.mark.asyncio
async def test_submit_scores_wrong_answer():
    lessons, progress = stores()
    lesson_id = EXAMPLE["id"]
    q = EXAMPLE["quiz"][0]
    wrong_idx = next(i for i in range(len(q["options"])) if i not in q["correct"])
    cb = FakeCallback(f"{QUIZ_SUBMIT}:{lesson_id}:0:{1 << wrong_idx}:0")
    await answer_callback(cb, lessons, progress)
    texts = [t for _, t, _ in cb.message.sent]
    assert any("Неверно" in t for t in texts)
    assert any(q["explanation"][:40] in t for t in texts)


@pytest.mark.asyncio
async def test_submit_last_question_records_progress_and_xp():
    lessons, progress = stores()
    lesson_id = EXAMPLE["id"]
    ok_counter = [0]  # ok путешествует через колбэки: каждый верный ответ +1
    n = len(EXAMPLE["quiz"])
    # отвечаем правильно на все вопросы: submit с полным набором
    for i in range(n):
        q = EXAMPLE["quiz"][i]
        mask = sum(1 << c for c in q["correct"])
        cb = FakeCallback(f"{QUIZ_SUBMIT}:{lesson_id}:{i}:{mask}:{ok_counter[0]}")
        ok_counter[0] += 1
        await answer_callback(cb, lessons, progress)
    result = progress.get_result(42, EXAMPLE["id"])
    assert result is not None, "прогресс должен записаться"
    assert result["correct"] == n
    assert result["xp"] == EXAMPLE["xp"], "идеальный квиз = полный XP"
    # после последнего вопроса — итоговое сообщение
    last = cb.message.sent[-1][1]
    assert "Квиз завершён" in last


@pytest.mark.asyncio
async def test_after_submit_next_question_shown():
    lessons, progress = stores()
    lesson_id = EXAMPLE["id"]
    cb = FakeCallback(f"{QUIZ_SUBMIT}:{lesson_id}:0:{1 << 0}:0")
    await answer_callback(cb, lessons, progress)
    texts = [t for _, t, _ in cb.message.sent]
    assert any("Квиз 2/5" in t for t in texts), "после ответа показывается следующий вопрос (в эталоне 5 вопросов)"


@pytest.mark.asyncio
async def test_explanation_is_escaped():
    """Explanation от LLM уходит в edit_text при parse_mode='HTML' — сырой '<' недопустим."""
    lessons, progress = stores()
    lesson = json.loads(json.dumps(EXAMPLE, ensure_ascii=False))
    lesson["quiz"][0]["explanation"] = "x < y и a&b"
    store = FakeLessonStore([lesson])
    cb = FakeCallback(f"{QUIZ_SUBMIT}:{lesson['id']}:0:{1 << 0}:0")
    await answer_callback(cb, store, progress)
    texts = [t for _, t, _ in cb.message.sent]
    assert any("x &lt; y и a&amp;b" in t for t in texts), "explanation должен экранироваться"


@pytest.mark.asyncio
async def test_garbage_callback_does_not_crash():
    lessons, progress = stores()
    cb = FakeCallback("quiz:bad:data")
    await answer_callback(cb, lessons, progress)  # не должно бросить


@pytest.mark.asyncio
async def test_select_all_marks_all_selected_for_multi():
    lessons, progress = stores()
    lesson = json.loads(json.dumps(EXAMPLE, ensure_ascii=False))
    lesson["quiz"][0]["kind"] = "multi"
    store = FakeLessonStore([lesson])
    # формат select_all: a:<lid>:<qidx>:<ok>
    cb = FakeCallback(f"{QUIZ_SELECT_ALL}:{lesson['id']}:0:0")
    await answer_callback(cb, store, progress)
    kb = cb.message.sent[-1][2]["reply_markup"]
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert sum("✓" in l for l in labels) == len(lesson["quiz"][0]["options"])


# --- /progress -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_progress_shows_zero_state():
    lessons, progress = stores()
    msg = FakeMessage()
    await cmd_progress(msg, lessons, progress)
    text = msg.sent[0][1]
    assert "0" in text and "урок" in text


@pytest.mark.asyncio
async def test_progress_shows_stats():
    lessons, progress = stores()
    progress.mark_completed(42, "l1", correct=4, total=4, xp=20)
    progress.mark_completed(42, "l2", correct=2, total=4, xp=8)
    msg = FakeMessage()
    await cmd_progress(msg, lessons, progress)
    text = msg.sent[0][1]
    assert "2" in text, "завершено уроков"
    assert "28" in text, "суммарный XP"


def test_render_progress_format():
    text = render_progress(completed=3, xp=45, total_published=26)
    assert "3" in text and "45" in text and "26" in text
