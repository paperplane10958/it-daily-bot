"""CLI контент-агента: пайплайн roadmap.sh -> OpenRouter -> SQLite.

Команды:
  topics   — скачать/обновить список тем roadmap (data/roadmaps/<id>/topics.json)
  generate — сгенерировать N уроков по темам, положить в SQLite (data/lessons.db)

Примеры:
  .venv/bin/python -m src.agent.cli topics --roadmap backend-beginner
  .venv/bin/python -m src.agent.cli generate --roadmap backend-beginner --limit 3
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from src.agent.generator import generate_lesson
from src.agent.openrouter import OpenRouterClient
from src.agent.roadmap import fetch_roadmap, save_topics
from src.agent.store import LessonStore

DATA_DIR = Path("data")

# Контент тем в GitHub-репо roadmap.sh (описание + ресурсы по теме)
CONTENT_URL = (
    "https://api.github.com/repos/kamranahmedse/developer-roadmap"
    "/contents/roadmaps/{roadmap_id}/content/{slug}@{node_id}.md"
)


def slugify(label: str) -> str:
    """'Pick a Language' -> 'pick-a-language' (для имени файла контента)."""
    return "".join(c.lower() if c.isalnum() else "-" for c in label).strip("-")


def lesson_id(roadmap_id: str, label: str) -> str:
    """Канонический id урока '<roadmap>-<slug>' — назначает пайплайн, не LLM.

    Стабильный ключ дедупа: LLM каждый раз выдумывает свой slug, поэтому id
    от LLM нельзя использовать для проверки «урок уже есть» (иначе перезапуск
    generate плодит дубликаты).
    """
    return f"{roadmap_id}-{slugify(label)}"


def fetch_topic_content(roadmap_id: str, topic: dict, timeout: int = 30) -> str:
    """Скачать markdown ноды темы из репо developer-roadmap (может не существовать)."""
    url = CONTENT_URL.format(roadmap_id=roadmap_id, slug=slugify(topic["label"]), node_id=topic["node_id"])
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return base64.b64decode(data["content"]).decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, KeyError):
        return ""  # контента нет — генерим без опоры


def cmd_topics(args) -> int:
    rm = fetch_roadmap(args.roadmap)
    out = save_topics(rm, DATA_DIR)
    topics = json.loads(out.read_text(encoding="utf-8"))["topics"]
    print(f"{args.roadmap}: {len(topics)} тем -> {out}")
    for t in topics[:10]:
        print(f"  - {t['label']}")
    if len(topics) > 10:
        print(f"  ... и ещё {len(topics) - 10}")
    return 0


def _load_llm_config() -> tuple[str, str]:
    """(api_key, model) из .env. api_key пуст -> нет ключа."""
    load_dotenv()
    return os.getenv("OPENROUTER_API_KEY", ""), os.getenv("LLM_MODEL", "anthropic/claude-3.5-haiku")


def cmd_generate(args) -> int:
    api_key, model = _load_llm_config()
    if not api_key:
        print("OPENROUTER_API_KEY не задан (в .env)", file=sys.stderr)
        return 1

    topics_path = DATA_DIR / "roadmaps" / args.roadmap / "topics.json"
    if not topics_path.exists():
        print(f"нет {topics_path}: сначала `topics --roadmap {args.roadmap}`", file=sys.stderr)
        return 1

    topics = json.loads(topics_path.read_text(encoding="utf-8"))["topics"]
    store = LessonStore(DATA_DIR / "lessons.db")

    ok = skipped = failed = 0
    budget = args.limit
    for t in topics:
        if budget <= 0:
            break
        # пропускаем темы, по которым урок уже есть (по каноническому id)
        lid = lesson_id(args.roadmap, t["label"])
        if store.get_lesson(lid):
            skipped += 1
            continue

        source_md = "" if args.no_sources else fetch_topic_content(args.roadmap, t)
        client = OpenRouterClient(api_key=api_key, model=model)
        lesson, meta = generate_lesson(
            client, topic=t["label"], roadmap_id=args.roadmap, source_md=source_md
        )

        if meta["valid"]:
            # канонический id назначаем сами — id от LLM нестабилен между запусками
            lesson["id"] = lid
            lesson["roadmap"]["order"] = topics.index(t) + 1
            store.upsert_lesson(lesson)
            ok += 1
            print(f"  ✓ {t['label']} -> {lesson['id']} ({meta['attempts']} попыт.)")
        else:
            failed += 1
            print(f"  ✗ {t['label']}: {meta['errors'][:2]}", file=sys.stderr)
        budget -= 1

    print(f"итог: {ok} сгенерировано, {skipped} пропущено (уже есть), {failed} брак")
    store.close()
    return 0 if ok > 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="content-agent", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_topics = sub.add_parser("topics", help="скачать темы roadmap")
    p_topics.add_argument("--roadmap", required=True, help="slug: backend-beginner, linux, ...")
    p_topics.set_defaults(func=cmd_topics)

    p_gen = sub.add_parser("generate", help="сгенерировать уроки в SQLite")
    p_gen.add_argument("--roadmap", required=True)
    p_gen.add_argument("--limit", type=int, default=5, help="сколько тем обработать за запуск")
    p_gen.add_argument("--no-sources", action="store_true", help="не тянуть markdown из GitHub")
    p_gen.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()