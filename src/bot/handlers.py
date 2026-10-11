"""Обработчики бота: приветствие, /lesson с квизом-кнопками, /progress, эхо.

Квиз без серверного состояния: выбор пользователя кодируется битовой маской
в callback_data, счёт верных ответов путешествует вместе с кнопками. Бюджет
callback_data — 64 байта: канонический id урока ограничен (~45 симв.), поля
короткие. Если урок из callback не найден в базе — просим вызвать /lesson заново.
"""

import html

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)

from src.lessons.render import lesson_messages, render_quiz_question, render_result
from src.lessons.xp import award_xp

router = Router(name="messages")

# Префиксы callback_data: q=toggle варианта, a=выбрать все, s=ответить
QUIZ_TOGGLE = "q"
QUIZ_SELECT_ALL = "a"
QUIZ_SUBMIT = "s"
NOOP = "noop"

# stores подставляет __main__.py при старте; в тестах хендлеры получают фейки напрямую
runtime: dict = {"lessons": None, "progress": None}

GREETING = (
    "Привет! Я IT Daily Bot 🤖🎓\n"
    "Буду учить тебя IT каждый день по 5–15 минут — короткие уроки, "
    "квизы, стрики и XP, как в Duolingo.\n\n"
    "Команды: /lesson — урок, /progress — прогресс, /help — справка"
)

HELP = (
    "Команды:\n"
    "/lesson — следующий урок: теория секциями + квиз-кнопки, XP за прохождение\n"
    "/progress — сколько уроков пройдено и сколько XP накоплено\n"
    "/start — приветствие"
)

NO_LESSONS = (
    "Пока нет доступных уроков — загляни позже! 👷\n"
    "Новые уроки добавляются в базу автоматически."
)

ALL_DONE = (
    "Поздравляю — ты прошёл все доступные уроки! 🎉\n"
    "Новые уроки добавляются в базу автоматически; загляни позже."
)

NO_LINK_PREVIEW = LinkPreviewOptions(is_disabled=True)


def quiz_kb(lesson: dict, index: int, mask: int = 0, ok: int = 0) -> InlineKeyboardMarkup:
    """Кнопки вопроса квиза.

    mask — битовая маска выбранных вариантов; ok — сколько ответов уже верно
    (путешествует через колбэки до итогового результата).
    """
    lid = lesson["id"]
    q = lesson["quiz"][index]
    rows: list[list[InlineKeyboardButton]] = []
    for j, opt in enumerate(q["options"]):
        mark = "✓ " if mask & (1 << j) else ""
        label = f"{mark}{chr(ord('A') + j)}) {opt}"
        if q["kind"] == "single":
            # одиночный выбор: тап по варианту сразу отправляет ответ
            cb = f"{QUIZ_SUBMIT}:{lid}:{index}:{1 << j}:{ok}"
        else:
            cb = f"{QUIZ_TOGGLE}:{lid}:{index}:{mask}:{1 << j}:{ok}"
        rows.append([InlineKeyboardButton(text=label[:64], callback_data=cb)])
    if q["kind"] == "multi":
        if mask != (1 << len(q["options"])) - 1:
            rows.append([InlineKeyboardButton(text="Выбрать все", callback_data=f"{QUIZ_SELECT_ALL}:{lid}:{index}:{ok}")])
        if mask:
            rows.append(
                [InlineKeyboardButton(text="Ответить", callback_data=f"{QUIZ_SUBMIT}:{lid}:{index}:{mask}:{ok}")]
            )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_quiz_cb(data: str) -> dict | None:
    """Разобрать callback_data квиза. Форматы:
    q:<lid>:<qidx>:<mask>:<optidx>:<ok> | a:<lid>:<qidx>:<ok> | s:<lid>:<qidx>:<mask>:<ok>
    """
    p = data.split(":")
    try:
        op = p[0]
        if op == QUIZ_TOGGLE:
            return {"op": op, "lid": p[1], "qidx": int(p[2]), "mask": int(p[3]), "optidx": int(p[4]), "ok": int(p[5])}
        if op in (QUIZ_SELECT_ALL, QUIZ_SUBMIT):
            out = {"op": op, "lid": p[1], "qidx": int(p[2])}
            if op == QUIZ_SELECT_ALL:
                out["ok"] = int(p[3])
            else:
                out["mask"] = int(p[3])
                out["ok"] = int(p[4])
            return out
    except (IndexError, ValueError):
        return None
    return None


async def _edit_quiz(cb, lesson: dict, index: int, mask: int, ok: int, prefix: str = "") -> None:
    text = f"{prefix}{render_quiz_question(lesson, index)}"
    await cb.message.edit_text(
        text, reply_markup=quiz_kb(lesson, index, mask, ok), link_preview_options=NO_LINK_PREVIEW
    )


async def answer_callback(cb, lessons, progress) -> None:
    """Обработчик кнопок квиза: toggle / выбрать все / ответить."""
    parsed = parse_quiz_cb(cb.data)
    if parsed is None:
        await cb.answer()
        return
    lesson = lessons.get_lesson(parsed["lid"])
    if lesson is None or parsed["qidx"] >= len(lesson.get("quiz", [])):
        await cb.answer("Урок обновился — отправь /lesson заново", show_alert=True)
        return

    if parsed["op"] == QUIZ_TOGGLE:
        new_mask = parsed["mask"] ^ (1 << parsed["optidx"])
        await _edit_quiz(cb, lesson, parsed["qidx"], new_mask, parsed["ok"])
        await cb.answer()
        return

    if parsed["op"] == QUIZ_SELECT_ALL:
        all_mask = (1 << len(lesson["quiz"][parsed["qidx"]]["options"])) - 1
        await _edit_quiz(cb, lesson, parsed["qidx"], all_mask, parsed["ok"])
        await cb.answer()
        return

    # QUIZ_SUBMIT: маска = выбор пользователя, сверяем с correct
    q = lesson["quiz"][parsed["qidx"]]
    chosen = {j for j in range(len(q["options"])) if parsed["mask"] & (1 << j)}
    is_correct = chosen == set(q["correct"])
    ok_new = parsed["ok"] + (1 if is_correct else 0)
    verdict = "✅ Верно!" if is_correct else "❌ Неверно."
    # explanation — текст от LLM: экранируем (parse_mode=HTML дефолтный)
    explanation = f"\n💬 {html.escape(q['explanation'], quote=False)}"

    nxt = parsed["qidx"] + 1
    if nxt < len(lesson["quiz"]):
        await cb.message.edit_text(
            f"{verdict}{explanation}\n\n{render_quiz_question(lesson, nxt)}",
            reply_markup=quiz_kb(lesson, nxt, 0, ok_new),
            link_preview_options=NO_LINK_PREVIEW,
        )
        await cb.answer()
        return

    # последний вопрос: итог + запись прогресса
    total = len(lesson["quiz"])
    xp = award_xp(ok_new, total, lesson["xp"])
    user_id = cb.from_user.id
    progress.mark_completed(user_id, lesson["id"], correct=ok_new, total=total, xp=xp)
    await cb.message.edit_text(
        f"{verdict}{explanation}\n\n{render_result(lesson, ok_new, total, xp)}",
        link_preview_options=NO_LINK_PREVIEW,
    )
    await cb.answer()


def render_progress(completed: int, xp: int, total_published: int) -> str:
    """Текст /progress: пройдено уроков и XP."""
    return f"📊 Твой прогресс:\nПройдено уроков: {completed} из {total_published}\nXP: {xp}"


async def cmd_lesson(msg: Message, lessons, progress) -> None:
    """Выдать следующий непройденный урок: контент + первый вопрос квиза."""
    seen = progress.seen_lesson_ids(msg.chat.id)
    lesson = lessons.next_published_lesson(seen)
    if lesson is None:
        await msg.answer(ALL_DONE if lessons.all_published_count() else NO_LESSONS)
        return

    for text in lesson_messages(lesson):
        await msg.answer(text, link_preview_options=NO_LINK_PREVIEW)
    await msg.answer(
        render_quiz_question(lesson, 0),
        reply_markup=quiz_kb(lesson, 0),
        link_preview_options=NO_LINK_PREVIEW,
    )


async def cmd_progress(msg: Message, lessons, progress) -> None:
    await msg.answer(
        render_progress(
            completed=progress.completed_count(msg.chat.id),
            xp=progress.total_xp(msg.chat.id),
            total_published=lessons.all_published_count(),
        )
    )


async def handle_lesson(message: Message) -> None:
    lessons, progress = runtime["lessons"], runtime["progress"]
    if lessons is None or progress is None:
        await message.answer(NO_LESSONS)
        return
    await cmd_lesson(message, lessons, progress)


async def handle_progress(message: Message) -> None:
    lessons, progress = runtime["lessons"], runtime["progress"]
    if lessons is None or progress is None:
        await message.answer("База уроков недоступна — загляни позже 👷")
        return
    await cmd_progress(message, lessons, progress)


@router.callback_query(F.data)
async def handle_quiz_callback(cb) -> None:
    lessons, progress = runtime["lessons"], runtime["progress"]
    if lessons is None or progress is None:
        await cb.answer("Бот перезапускается — отправь /lesson заново", show_alert=True)
        return
    await answer_callback(cb, lessons, progress)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(GREETING)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("lesson"))
async def lesson_command(message: Message) -> None:
    await handle_lesson(message)


@router.message(Command("progress"))
async def progress_command(message: Message) -> None:
    await handle_progress(message)


@router.message()
async def handle_echo(message: Message) -> None:
    if message.text:
        # parse_mode=HTML включён дефолтно: пользовательский текст экранируем,
        # иначе «1<2» уронит отправку с 400 can't parse entities
        await message.answer(html.escape(message.text, quote=False))
