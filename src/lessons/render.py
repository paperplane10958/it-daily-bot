"""Рендер урока (docs/lesson.schema.json) в HTML-сообщения Telegram.

Чистые функции без aiogram — тестируются без сети. Длины полей гарантированы
валидатором (validate_lesson), но материалы всё равно пакуются жадно: 3 примера
по 2000 символов сами по себе не влезают в один лимит Telegram.
"""

import html

TG_MESSAGE_LIMIT = 4000  # тот же запас, что в валидаторе


def _esc(text) -> str:
    return html.escape(str(text), quote=False)


def _bulleted(items: list[str], mark: str = "•") -> str:
    return "\n".join(f"{mark} {_esc(i)}" for i in items)


def _pack(blocks: list[str], limit: int = TG_MESSAGE_LIMIT) -> list[str]:
    """Жадно склеить блоки в сообщения <= limit; слишком длинный блок — разрезать."""
    msgs: list[str] = []
    cur = ""
    for block in blocks:
        candidate = f"{cur}\n\n{block}" if cur else block
        if len(candidate) <= limit:
            cur = candidate
            continue
        if cur:
            msgs.append(cur)
        while len(block) > limit:  # валидатор не допускает, но не падаем
            msgs.append(block[:limit])
            block = block[limit:]
        cur = block
    if cur:
        msgs.append(cur)
    return msgs


def _render_intro(lesson: dict) -> str:
    parts = [
        f"🎓 <b>{_esc(lesson['title'])}</b>  (≈{lesson['est_minutes']} мин, +{lesson['xp']} XP)",
        _esc(lesson["hook"]),
    ]
    if lesson.get("objectives"):
        parts.append("После урока ты сможешь:\n" + _bulleted(lesson["objectives"], "✅"))
    return "\n\n".join(parts)


def _render_theory(section: dict) -> str:
    return f"<b>{_esc(section['heading'])}</b>\n\n{section['body']}"


def _render_materials(lesson: dict) -> list[str]:
    """Термины, примеры, практика, подводные камни, источники — упакованные сообщения."""
    blocks: list[str] = []
    if lesson.get("key_terms"):
        lines = [f"<b>{_esc(t['term'])}</b> — {_esc(t['definition'])}" for t in lesson["key_terms"]]
        blocks.append("📚 Ключевые термины:\n" + "\n".join(lines))
    for ex in lesson.get("examples", []):
        block = f"💡 <b>{_esc(ex['title'])}</b>\n{_esc(ex['body'])}"
        if ex.get("code"):
            block += f"\n\n<pre>{_esc(ex['code'])}</pre>"
        blocks.append(block)
    if lesson.get("practice"):
        pr = lesson["practice"]
        block = f"✍️ Попробуй сам: {_esc(pr['prompt'])}"
        if pr.get("hint"):
            block += f"\n\nПодсказка: {_esc(pr['hint'])}"
        blocks.append(block)
    if lesson.get("pitfalls"):
        blocks.append("⚠️ Частые ошибки:\n" + _bulleted(lesson["pitfalls"]))
    if lesson.get("sources"):
        lines = [f"🔗 <a href=\"{_esc(s['url'])}\">{_esc(s['title'])}</a>" for s in lesson["sources"]]
        blocks.append("Где копнуть глубже:\n" + "\n".join(lines))
    return _pack(blocks)


def lesson_messages(lesson: dict) -> list[str]:
    """Урок -> список HTML-сообщений: интро, theory-секции, материалы."""
    msgs = [_render_intro(lesson)]
    msgs += [_render_theory(s) for s in lesson.get("theory", [])]
    msgs += _render_materials(lesson)
    return msgs


def render_quiz_question(lesson: dict, index: int) -> str:
    """Вопрос квиза: номер, вопрос, варианты A-D, пометка про multi."""
    quiz = lesson["quiz"]
    q = quiz[index]
    kind = "несколько вариантов" if q["kind"] == "multi" else "один вариант"
    head = f"❓ Квиз {index + 1}/{len(quiz)} ({kind}):"
    options = "\n".join(f"{chr(ord('A') + j)}) {_esc(o)}" for j, o in enumerate(q["options"]))
    note = "\n\nМожно выбрать несколько вариантов." if q["kind"] == "multi" else ""
    return f"{head}\n{_esc(q['question'])}\n\n{options}{note}"


def render_result(lesson: dict, correct: int, total: int, xp: int) -> str:
    """Итог квиза: счёт, XP, оценочная фраза в стиле Duolingo."""
    lines = ["🏁 Квиз завершён!", f"Результат: {correct}/{total}", f"Награда: +{xp} XP"]
    if correct == total:
        lines.append("Идеально! Так держать 🔥")
    elif correct * 2 >= total:
        lines.append("Хорошо! Загляни ещё раз в термины и примеры.")
    else:
        lines.append("Не страшно — попробуй пройти урок ещё раз.")
    return "\n".join(lines)
