"""Тесты рендера урока в HTML-сообщения Telegram (без aiogram, чистые функции)."""

import json
from pathlib import Path

from src.lessons.render import lesson_messages, render_quiz_question, render_result

DOCS = Path(__file__).resolve().parents[1] / "docs"
EXAMPLE = json.loads((DOCS / "examples" / "lesson-what-is-the-internet.json").read_text(encoding="utf-8"))


def test_lesson_messages_returns_nonempty_messages():
    msgs = lesson_messages(EXAMPLE)
    assert msgs, "должно быть хотя бы одно сообщение"
    assert all(m.strip() for m in msgs)
    assert all(len(m) <= 4000 for m in msgs), "каждое сообщение <= лимит Telegram"


def test_intro_contains_title_hook_objectives():
    intro = lesson_messages(EXAMPLE)[0]
    assert EXAMPLE["title"] in intro
    assert EXAMPLE["hook"] in intro
    for obj in EXAMPLE["objectives"]:
        assert obj in intro


def test_theory_sections_rendered_with_headings():
    msgs = lesson_messages(EXAMPLE)
    joined = "\n".join(msgs)
    for section in EXAMPLE["theory"]:
        assert section["heading"] in joined
        assert section["body"] in joined


def test_html_is_escaped():
    lesson = json.loads(json.dumps(EXAMPLE, ensure_ascii=False))
    lesson["theory"][0]["body"] = "Тег <b>жирный</b> и 5 > 3"
    joined = "\n".join(lesson_messages(lesson))
    # тело theory не экранируется (markdown от LLM), но заголовки и хук — да:
    assert "5 &gt; 3" in joined or "5 > 3" in joined
    lesson2 = json.loads(json.dumps(EXAMPLE, ensure_ascii=False))
    lesson2["title"] = "<script>alert(1)</script>"
    lesson2["hook"] = "a < b"
    intro = lesson_messages(lesson2)[0]
    assert "<script>" not in intro and "&lt;script&gt;" in intro
    assert "a &lt; b" in intro


def test_materials_contains_terms_examples_pitfalls_sources():
    joined = "\n".join(lesson_messages(EXAMPLE))
    for t in EXAMPLE["key_terms"]:
        assert t["term"] in joined
    for ex in EXAMPLE["examples"]:
        assert ex["title"] in joined
    if EXAMPLE.get("code"):
        pass  # code рендерится в <pre> — проверяется отдельным тестом
    for p in EXAMPLE["pitfalls"]:
        assert p in joined
    for s in EXAMPLE["sources"]:
        assert s["url"] in joined


def test_code_example_rendered_in_pre_block():
    lesson = json.loads(json.dumps(EXAMPLE, ensure_ascii=False))
    lesson["examples"][0]["code"] = "print('hello')"
    joined = "\n".join(lesson_messages(lesson))
    assert "<pre>" in joined and "print('hello')" in joined


def test_quiz_question_renders_question_and_number():
    q = render_quiz_question(EXAMPLE, 0)
    assert "1/" in q and str(len(EXAMPLE["quiz"])) in q
    assert EXAMPLE["quiz"][0]["question"] in q


def test_result_renders_score_and_xp():
    text = render_result(EXAMPLE, correct=3, total=4, xp=12)
    assert "3/4" in text
    assert "12" in text


def test_empty_optional_blocks_dont_crash():
    lesson = json.loads(json.dumps(EXAMPLE, ensure_ascii=False))
    for key in ("key_terms", "examples", "pitfalls", "practice"):
        lesson.pop(key, None)
    msgs = lesson_messages(lesson)
    assert msgs and all(m.strip() for m in msgs)
