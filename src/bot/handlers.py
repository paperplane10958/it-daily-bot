"""Обработчики бота: приветствие, /lesson с квизом-кнопками, /progress, эхо.

Квиз: состояние прохождения (текущий вопрос, выбор multi-вопроса, счёт верных)
хранится на сервере — таблица quiz_state в SQLite. Раньше выбор кодировался
в callback_data — два быстрых тапа приходили от одной и той же старой клавиатуры,
второй перезаписывал первый (вариант «отваливался», submit шёл с неполной маской).
Бюджет callback_data — 64 байта: канонический id урока ограничен (~45 симв.),
поля короткие. Если урок из callback не найден в базе — просим вызвать /lesson заново.
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

import datetime as dt

from src.lessons.gamify import level_for_xp, level_progress, streak_from_dates
from src.lessons.render import lesson_messages, render_quiz_question, render_result
from src.lessons.xp import award_xp

router = Router(name="messages")

# Префиксы callback_data: q=toggle варианта, a=выбрать все, s=ответить,
# c=карточки (show/next), rh/roff/ron=напоминания (час/выкл/вкл)
QUIZ_TOGGLE = "q"
QUIZ_SELECT_ALL = "a"
QUIZ_SUBMIT = "s"
CARDS_SHOW = "c"
REMIND_HOUR = "rh"
REMIND_OFF = "roff"
REMIND_ON = "ron"
NOOP = "noop"

# stores подставляет __main__.py при старте; в тестах хендлеры получают фейки напрямую
runtime: dict = {"lessons": None, "progress": None, "reminders": None}

GREETING = (
    "Привет! Я IT Daily Bot 🤖🎓\n"
    "Буду учить тебя IT каждый день по 5–15 минут — короткие уроки, "
    "квизы, стрики и XP, как в Duolingo.\n\n"
    "Команды: /lesson — урок, /progress — прогресс, /help — справка"
)

HELP = (
    "Команды:\n"
    "/lesson — следующий урок: теория секциями + квиз-кнопки, XP за прохождение\n"
    "/progress — пройдено уроков, XP, уровень и стрик 🔥\n"
    "/cards — карточки терминов из пройденных уроков\n"
    "/remind — ежедневное напоминание об уроке (выбор времени)\n"
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


def quiz_kb(lesson: dict, index: int, mask: int = 0) -> InlineKeyboardMarkup:
    """Кнопки вопроса квиза.

    mask — битовая маска выбранных вариантов (отметки ✓ и кнопка «Ответить»);
    выбор и счёт живут в серверном состоянии (quiz_state), в callback_data не ездят.
    """
    lid = lesson["id"]
    q = lesson["quiz"][index]
    rows: list[list[InlineKeyboardButton]] = []
    for j, opt in enumerate(q["options"]):
        mark = "✓ " if mask & (1 << j) else ""
        label = f"{mark}{chr(ord('A') + j)}) {opt}"
        if q["kind"] == "single":
            # одиночный выбор: тап по варианту сразу отправляет ответ,
            # индекс варианта едет в callback_data (маска не нужна)
            cb = f"{QUIZ_SUBMIT}:{lid}:{index}:{j}"
        else:
            # multi: маска не в callback_data — живёт в серверном состоянии quiz_choice
            cb = f"{QUIZ_TOGGLE}:{lid}:{index}:{j}"
        rows.append([InlineKeyboardButton(text=label[:64], callback_data=cb)])
    if q["kind"] == "multi":
        if mask != (1 << len(q["options"])) - 1:
            rows.append([InlineKeyboardButton(text="Выбрать все", callback_data=f"{QUIZ_SELECT_ALL}:{lid}:{index}")])
        if mask:
            rows.append(
                [InlineKeyboardButton(text="Ответить", callback_data=f"{QUIZ_SUBMIT}:{lid}:{index}:m")]
            )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_quiz_cb(data: str) -> dict | None:
    """Разобрать callback_data квиза. Форматы:
    q:<lid>:<qidx>:<optidx> | a:<lid>:<qidx> | s:<lid>:<qidx>:<флаг>
    """
    p = data.split(":")
    try:
        op = p[0]
        if op == CARDS_SHOW:
            # формат карточек: c:<idx>:<show|next>
            return {"op": op, "idx": int(p[1]), "action": p[2]}
        if op == REMIND_HOUR:
            # формат: rh:<час 0..23>
            return {"op": op, "hour": int(p[1])}
        if op in (REMIND_OFF, REMIND_ON):
            return {"op": op}
        if op == QUIZ_TOGGLE:  # q:<lid>:<qidx>:<optidx>; 6 полей — формат до фикса
            if len(p) != 4:
                return {"op": op, "stale": True}
            return {"op": op, "lid": p[1], "qidx": int(p[2]), "optidx": int(p[3])}
        if op in (QUIZ_SELECT_ALL, QUIZ_SUBMIT):
            # a:<lid>:<qidx> (3) | s:<lid>:<qidx>[:<optidx>|"m"] (4); больше полей —
            # формат до фикса (маска/ok в callback_data) -> просим перезапустить урок
            if (op == QUIZ_SELECT_ALL and len(p) != 3) or (op == QUIZ_SUBMIT and len(p) not in (3, 4)):
                return {"op": op, "stale": True}
            optidx = None
            if len(p) > 3 and p[3] != "m":
                optidx = int(p[3])
            return {"op": op, "lid": p[1], "qidx": int(p[2]), "optidx": optidx}
    except (IndexError, ValueError):
        return None
    return None


async def _edit_quiz(cb, lesson: dict, index: int, mask: int, prefix: str = "") -> None:
    text = f"{prefix}{render_quiz_question(lesson, index)}"
    await cb.message.edit_text(
        text, reply_markup=quiz_kb(lesson, index, mask), link_preview_options=NO_LINK_PREVIEW
    )


async def answer_callback(cb, lessons, progress, reminders=None) -> None:
    """Обработчик кнопок: квиз, карточки, напоминания."""
    parsed = parse_quiz_cb(cb.data)
    if parsed is None:
        await cb.answer()
        return
    if parsed["op"] == CARDS_SHOW:
        await _handle_cards_cb(cb, parsed, progress)
        return
    if parsed["op"] in (REMIND_HOUR, REMIND_OFF, REMIND_ON):
        await _handle_remind_cb(cb, parsed, reminders)
        return
    if parsed.get("stale"):
        # колбэк клавиатуры до фикса (маска в callback_data): lid/qidx не парсятся
        # надёжно — не грейдим по нему, просим перезапустить урок
        await cb.answer("Квиз обновился — отправь /lesson заново", show_alert=True)
        return
    lesson = lessons.get_lesson(parsed["lid"])
    if lesson is None or parsed["qidx"] >= len(lesson.get("quiz", [])):
        await cb.answer("Урок обновился — отправь /lesson заново", show_alert=True)
        return

    uid = cb.from_user.id
    state = progress.get_quiz_state(uid, lesson["id"]) or {"qidx": parsed["qidx"], "mask": 0, "ok": 0}
    # колбэк по устаревшей клавиатуре (вопрос уже отвечен) — тихо игнорируем:
    # иначе двойной submit засчитал бы вопрос дважды
    if state["qidx"] != parsed["qidx"]:
        await cb.answer()
        return

    if parsed["op"] == QUIZ_TOGGLE:
        optidx = parsed["optidx"]
        if not 0 <= optidx < len(lesson["quiz"][parsed["qidx"]]["options"]):
            await cb.answer()
            return
        new_mask = state["mask"] ^ (1 << optidx)
        progress.set_quiz_state(uid, lesson["id"], parsed["qidx"], new_mask, state["ok"])
        await _edit_quiz(cb, lesson, parsed["qidx"], new_mask)
        await cb.answer()
        return

    if parsed["op"] == QUIZ_SELECT_ALL:
        all_mask = (1 << len(lesson["quiz"][parsed["qidx"]]["options"])) - 1
        progress.set_quiz_state(uid, lesson["id"], parsed["qidx"], all_mask, state["ok"])
        await _edit_quiz(cb, lesson, parsed["qidx"], all_mask)
        await cb.answer()
        return

    # QUIZ_SUBMIT: выбор пользователя — из серверного состояния (multi)
    # или из колбэка (single: тап по варианту сразу отправляет ответ)
    q = lesson["quiz"][parsed["qidx"]]
    if q["kind"] == "single":
        optidx = parsed["optidx"]
        # index вне диапазона (мусур в callback_data) — не грейдим вопрос
        if optidx is None or not 0 <= optidx < len(q["options"]):
            await cb.answer("Ответ устарел — отправь /lesson заново", show_alert=True)
            return
        chosen = {optidx}
    else:
        chosen = {j for j in range(len(q["options"])) if state["mask"] & (1 << j)}
    is_correct = chosen == set(q["correct"])
    ok_new = state["ok"] + (1 if is_correct else 0)
    verdict = "✅ Верно!" if is_correct else "❌ Неверно."
    # explanation — текст от LLM: экранируем (parse_mode=HTML дефолтный)
    explanation = f"\n💬 {html.escape(q['explanation'], quote=False)}"

    nxt = parsed["qidx"] + 1
    if nxt < len(lesson["quiz"]):
        # маска нового вопроса чистая, счёт едет дальше
        progress.set_quiz_state(uid, lesson["id"], nxt, 0, ok_new)
        await cb.message.edit_text(
            f"{verdict}{explanation}\n\n{render_quiz_question(lesson, nxt)}",
            reply_markup=quiz_kb(lesson, nxt),
            link_preview_options=NO_LINK_PREVIEW,
        )
        await cb.answer()
        return

    # последний вопрос: итог + запись прогресса
    progress.delete_quiz_state(uid, lesson["id"])
    total = len(lesson["quiz"])
    xp = award_xp(ok_new, total, lesson["xp"])
    progress.mark_completed(uid, lesson["id"], correct=ok_new, total=total, xp=xp)
    await cb.message.edit_text(
        f"{verdict}{explanation}\n\n{render_result(lesson, ok_new, total, xp)}",
        link_preview_options=NO_LINK_PREVIEW,
    )
    await cb.answer()


def render_progress(completed: int, xp: int, total_published: int, streak: int) -> str:
    """Текст /progress: пройдено уроков, XP, уровень и стрик."""
    level, in_level, to_next = level_progress(xp)
    return (
        f"📊 Твой прогресс:\n"
        f"Пройдено уроков: {completed} из {total_published}\n"
        f"XP: {xp} (уровень {level}: {in_level}/{to_next} до следующего)\n"
        f"Стрик: {streak} 🔥"
    )


async def cmd_lesson(msg: Message, lessons, progress) -> None:
    """Выдать следующий непройденный урок: контент + первый вопрос квиза."""
    seen = progress.seen_lesson_ids(msg.chat.id)
    lesson = lessons.next_published_lesson(seen)
    if lesson is None:
        # всё пройдено: повторное прохождение задумано (mark_completed — upsert),
        # выдаём последний завершённый урок заново; это же сбрасывает застрявший
        # quiz_state брошенной попытки
        last_id = progress.last_completed_lesson_id(msg.chat.id)
        lesson = lessons.get_lesson(last_id) if last_id else None
        if lesson is None:
            await msg.answer(ALL_DONE if lessons.all_published_count() else NO_LESSONS)
            return

    # сбросить застрявшее состояние предыдущей попытки (урок бросили посреди квиза),
    # иначе guard «устаревший колбэк» молча глотал бы тапы по новому вопросу
    progress.delete_quiz_state(msg.chat.id, lesson["id"])
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
            streak=streak_from_dates(progress.activity_dates(msg.chat.id), dt.date.today()),
        )
    )


def cards_kb(index: int, total: int, revealed: bool) -> InlineKeyboardMarkup:
    """Кнопки карточки: 'Показать определение' -> 'Дальше' (и навигация 1..N)."""
    rows = []
    if not revealed:
        rows.append([InlineKeyboardButton(text="Показать определение", callback_data=f"{CARDS_SHOW}:{index}:show")])
    else:
        rows.append([InlineKeyboardButton(text=f"Дальше ({index + 2}/{total})", callback_data=f"{CARDS_SHOW}:{index}:next")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_card(terms: list[tuple[str, str, str, str]], index: int, revealed: bool) -> str:
    """Карточка: термин (+ определение после 'Показать'), источник — урок."""
    term, definition, _lid, lesson_title = terms[index]
    lines = [f"🃏 Карточка {index + 1}/{len(terms)}", f"<b>{html.escape(term, quote=False)}</b>"]
    if revealed:
        lines.append(html.escape(definition, quote=False))
    lines.append(f"<i>из урока «{html.escape(lesson_title, quote=False)}»</i>")
    return "\n\n".join(lines)


async def cmd_cards(msg: Message, progress) -> None:
    """Карточки терминов из пройденных уроков (пока без SRS — простой просмотр)."""
    terms = progress.terms(msg.chat.id)
    if not terms:
        await msg.answer("Пока нет карточек — пройди первый урок (/lesson), и термины появятся здесь 🃏")
        return
    await msg.answer(
        render_card(terms, 0, revealed=False),
        reply_markup=cards_kb(0, len(terms), revealed=False),
        link_preview_options=NO_LINK_PREVIEW,
    )


async def handle_cards(message: Message) -> None:
    progress = runtime["progress"]
    if progress is None:
        await message.answer("База недоступна — загляни позже 👷")
        return
    await cmd_cards(message, progress)


async def _handle_cards_cb(cb, parsed: dict, progress) -> None:
    """Кнопки карточек: показать определение / следующая карточка.

    Термины перечитываются из базы по тому же ORDER BY, что при /cards, —
    состояние только в callback_data (индекс).
    """
    terms = progress.terms(cb.from_user.id)
    idx = parsed["idx"]
    if not terms or idx >= len(terms):
        await cb.answer("Карточки обновились — отправь /cards заново", show_alert=True)
        return
    if parsed["action"] == "show":
        await cb.message.edit_text(
            render_card(terms, idx, revealed=True),
            reply_markup=cards_kb(idx, len(terms), revealed=True),
            link_preview_options=NO_LINK_PREVIEW,
        )
        await cb.answer()
        return
    # next
    nxt = idx + 1
    if nxt >= len(terms):
        await cb.message.edit_text("🃏 Карточки закончились! Возвращайся после нового урока (/lesson).")
        await cb.answer()
        return
    await cb.message.edit_text(
        render_card(terms, nxt, revealed=False),
        reply_markup=cards_kb(nxt, len(terms), revealed=False),
        link_preview_options=NO_LINK_PREVIEW,
    )
    await cb.answer()


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
    reminders = runtime["reminders"]
    if lessons is None or progress is None:
        await cb.answer("Бот перезапускается — отправь /lesson заново", show_alert=True)
        return
    await answer_callback(cb, lessons, progress, reminders)


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


@router.message(Command("cards"))
async def cards_command(message: Message) -> None:
    await handle_cards(message)


# --- напоминания (/remind) ----------------------------------------------------------

REMIND_HOURS = [(7, "Утро 7:00"), (12, "День 12:00"), (19, "Вечер 19:00"), (22, "Ночь 22:00")]


def remind_kb(enabled: bool, hour: int | None) -> InlineKeyboardMarkup:
    """Кнопки /remind: пресеты часов, вкл (предыдущий час) / выкл."""
    rows = [[InlineKeyboardButton(text=label, callback_data=f"{REMIND_HOUR}:{h}") for h, label in REMIND_HOURS]]
    if enabled and hour is not None:
        rows.append([InlineKeyboardButton(text="Выключить", callback_data=REMIND_OFF)])
    else:
        rows.append([InlineKeyboardButton(text="Включить снова", callback_data=REMIND_ON)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_remind(setting: dict | None) -> str:
    """Текст /remind: текущее состояние + как работает."""
    if setting and setting["enabled"]:
        status = f"Напоминание включено: каждый день в {setting['hour']}:00 ⏰"
    elif setting:
        status = "Напоминание выключено."
    else:
        status = "Напоминание пока не настроено."
    return (
        f"{status}\n\n"
        "Пришлю сообщение в выбранный час, если в этот день ты ещё не прошёл урок. "
        "Время местное (как на твоих часах).\n\n"
        "Работает, пока бот запущен."
    )


async def cmd_remind(msg: Message, reminders) -> None:
    setting = reminders.get(msg.chat.id)
    await msg.answer(
        render_remind(setting),
        reply_markup=remind_kb(enabled=bool(setting and setting["enabled"]), hour=setting["hour"] if setting else None),
    )


async def handle_remind(message: Message) -> None:
    reminders = runtime["reminders"]
    if reminders is None:
        await message.answer("База недоступна — загляни позже 👷")
        return
    await cmd_remind(message, reminders)


async def _handle_remind_cb(cb, parsed: dict, reminders) -> None:
    """Кнопки напоминаний: выбор часа, вкл/выкл."""
    if reminders is None:
        await cb.answer("База недоступна — загляни позже", show_alert=True)
        return
    user_id = cb.from_user.id
    if parsed["op"] == REMIND_HOUR:
        reminders.set(user_id, parsed["hour"])
        text = f"Готово! Буду напоминать каждый день в {parsed['hour']}:00 ⏰"
    elif parsed["op"] == REMIND_OFF:
        reminders.disable(user_id)
        text = "Напоминание выключено. Включить снова — /remind."
    else:  # REMIND_ON: включить с прежним часом
        setting = reminders.get(user_id)
        if not setting:
            await cb.answer("Сначала выбери время — /remind", show_alert=True)
            return
        reminders.set(user_id, setting["hour"])
        text = f"Снова включено: каждый день в {setting['hour']}:00 ⏰"
    setting = reminders.get(user_id)
    await cb.message.edit_text(
        text,
        reply_markup=remind_kb(enabled=bool(setting and setting["enabled"]), hour=setting["hour"] if setting else None),
    )
    await cb.answer()


@router.message(Command("remind"))
async def remind_command(message: Message) -> None:
    await handle_remind(message)


@router.message()
async def handle_echo(message: Message) -> None:
    if message.text:
        # parse_mode=HTML включён дефолтно: пользовательский текст экранируем,
        # иначе «1<2» уронит отправку с 400 can't parse entities
        await message.answer(html.escape(message.text, quote=False))
