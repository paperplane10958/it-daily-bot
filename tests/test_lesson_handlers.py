"""Тесты выдачи урока в боте: /lesson, /progress и квиз по callback-кнопкам.

Хендлеры зависимостью принимают stores (LessonStore / ProgressStore) —
в тестах подставляются фейки, сеть и реальная база не дёргаются.
"""

import json
from pathlib import Path

import pytest

from datetime import date, timedelta

from src.bot.handlers import (
    CARDS_SHOW,
    QUIZ_SELECT_ALL,
    QUIZ_SUBMIT,
    QUIZ_TOGGLE,
    REMIND_OFF,
    REMIND_HOUR,
    REMIND_ON,
    answer_callback,
    cmd_cards,
    cmd_lesson,
    cmd_progress,
    cmd_remind,
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


class FakeReminderStore:
    def __init__(self):
        self.settings: dict[int, dict] = {}

    def set(self, user_id, hour):
        self.settings[user_id] = {"hour": hour, "enabled": True}

    def disable(self, user_id):
        if user_id in self.settings:
            self.settings[user_id]["enabled"] = False

    def get(self, user_id):
        return self.settings.get(user_id)


class FakeProgressStore:
    def __init__(self):
        self.data: dict[tuple[int, str], dict] = {}
        self.terms_data: list[tuple[str, str, str, str]] = []
        self.dates_data: list = []

    def seen_lesson_ids(self, user_id):
        return [lid for (uid, lid) in self.data if uid == user_id]

    def terms(self, user_id):
        return self.terms_data

    def activity_dates(self, user_id):
        return self.dates_data

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
    text = render_progress(completed=3, xp=145, total_published=26, streak=2)
    assert "3" in text and "145" in text and "26" in text
    assert "уровень 2: 45/100" in text, "145 XP = уровень 2, 45 XP до следующего"
    assert "Стрик: 2" in text


@pytest.mark.asyncio
async def test_progress_shows_streak_from_activity_dates():
    lessons, progress = stores()
    today = date.today()
    progress.mark_completed(42, "l1", correct=4, total=4, xp=20)
    progress.dates_data = [today, today - timedelta(days=1), today - timedelta(days=2)]
    msg = FakeMessage()
    await cmd_progress(msg, lessons, progress)
    assert "Стрик: 3" in msg.sent[0][1]


# --- /cards: карточки терминов ----------------------------------------------------


@pytest.mark.asyncio
async def test_cards_without_terms_prompts_lesson():
    lessons, progress = stores()
    msg = FakeMessage()
    await cmd_cards(msg, progress)
    assert any("/lesson" in t for _, t, _ in msg.sent)


@pytest.mark.asyncio
async def test_cards_shows_first_term_without_definition():
    lessons, progress = stores()
    progress.terms_data = [("Сервер", "Мощный компьютер в дата-центре", "l1", "Тест")]
    msg = FakeMessage()
    await cmd_cards(msg, progress)
    text = msg.sent[-1][1]
    assert "Сервер" in text
    assert "Мощный" not in text, "определение скрыто до нажатия кнопки"
    labels = [b.text for row in msg.sent[-1][2]["reply_markup"].inline_keyboard for b in row]
    assert any("Показать" in l for l in labels)


@pytest.mark.asyncio
async def test_cards_show_reveals_definition():
    lessons, progress = stores()
    progress.terms_data = [("Сервер", "Мощный компьютер в дата-центре", "l1", "Тест")]
    cb = FakeCallback(f"{CARDS_SHOW}:0:show")
    await answer_callback(cb, lessons, progress)
    texts = [t for _, t, _ in cb.message.sent]
    assert any("Мощный компьютер в дата-центре" in t for t in texts)
    labels = [b.text for row in cb.message.sent[-1][2]["reply_markup"].inline_keyboard for b in row]
    assert any("Дальше" in l for l in labels)


@pytest.mark.asyncio
async def test_cards_next_moves_to_next_term():
    lessons, progress = stores()
    progress.terms_data = [
        ("Сервер", "Определение 1", "l1", "Т1"),
        ("DNS", "Определение 2", "l2", "Т2"),
    ]
    cb = FakeCallback(f"{CARDS_SHOW}:0:next")
    await answer_callback(cb, lessons, progress)
    text = cb.message.sent[-1][1]
    assert "DNS" in text
    assert "Определение 2" not in text, "следующая карточка снова без определения"
    assert "2/2" in text


@pytest.mark.asyncio
async def test_cards_next_after_last_says_done():
    lessons, progress = stores()
    progress.terms_data = [("Сервер", "Определение 1", "l1", "Т1")]
    cb = FakeCallback(f"{CARDS_SHOW}:0:next")
    await answer_callback(cb, lessons, progress)
    assert any("закончил" in t.lower() for _, t, _ in cb.message.sent)


# --- /remind: ежедневные напоминания ------------------------------------------------


def test_remind_kb_has_hour_buttons_and_off():
    from src.bot.handlers import remind_kb

    kb_off = remind_kb(enabled=False, hour=None)
    labels_off = [b.text for row in kb_off.inline_keyboard for b in row]
    assert any("Утро" in l for l in labels_off) and any("Вечер" in l for l in labels_off)
    assert any("Включить снова" in l for l in labels_off), "в выключенном состоянии — кнопка включения"

    kb_on = remind_kb(enabled=True, hour=19)
    labels_on = [b.text for row in kb_on.inline_keyboard for b in row]
    assert any("Выключить" in l for l in labels_on), "во включённом состоянии — кнопка выключения"


@pytest.mark.asyncio
async def test_remind_shows_current_setting():
    lessons, progress = stores()
    reminders = FakeReminderStore()
    reminders.set(42, 19)
    msg = FakeMessage()
    await cmd_remind(msg, reminders)
    text = msg.sent[-1][1]
    assert "19" in text and "вкл" in text.lower()


@pytest.mark.asyncio
async def test_remind_unset_shows_hint():
    lessons, progress = stores()
    msg = FakeMessage()
    await cmd_remind(msg, FakeReminderStore())
    assert any("не" in t.lower() for _, t, _ in msg.sent)


@pytest.mark.asyncio
async def test_remind_hour_saves_setting():
    lessons, progress = stores()
    reminders = FakeReminderStore()
    cb = FakeCallback(f"{REMIND_HOUR}:20")
    await answer_callback(cb, lessons, progress, reminders)
    assert reminders.get(42) == {"hour": 20, "enabled": True}
    text = cb.message.sent[-1][1]
    assert "20" in text, "подтверждение с выбранным часом"


@pytest.mark.asyncio
async def test_remind_off_disables():
    lessons, progress = stores()
    reminders = FakeReminderStore()
    reminders.set(42, 9)
    cb = FakeCallback(REMIND_OFF)
    await answer_callback(cb, lessons, progress, reminders)
    assert reminders.get(42) == {"hour": 9, "enabled": False}


@pytest.mark.asyncio
async def test_remind_on_reenables_previous_hour():
    lessons, progress = stores()
    reminders = FakeReminderStore()
    reminders.set(42, 9)
    reminders.disable(42)
    cb = FakeCallback(REMIND_ON)
    await answer_callback(cb, lessons, progress, reminders)
    assert reminders.get(42) == {"hour": 9, "enabled": True}
