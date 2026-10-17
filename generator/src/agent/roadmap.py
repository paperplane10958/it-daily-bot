"""Загрузчик roadmap.sh: JSON нод -> упорядоченный список тем.

Источник структуры: https://roadmap.sh/<roadmap_id>.json (json-версия карты).
Нас интересуют ноды типов topic/subtopic с непустым label — это темы уроков.
Порядок тем — по позиции на карте (y, затем x): roadmap.sh рисует трек сверху вниз.
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

ROADMAP_URL = "https://roadmap.sh/{roadmap_id}.json"
TOPIC_TYPES = {"topic", "subtopic"}


def fetch_roadmap(roadmap_id: str, timeout: int = 30) -> dict:
    """Скачать JSON карты roadmap.sh по slug (например backend-beginner)."""
    url = ROADMAP_URL.format(roadmap_id=roadmap_id)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"roadmap.sh вернул {e.code} для {url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"не удалось скачать {url}: {e.reason}") from e


def parse_topics(roadmap: dict) -> list[dict]:
    """Извлечь темы (topic/subtopic), отсортировать по позиции на карте."""
    nodes = roadmap.get("nodes") or []
    roadmap_id = roadmap.get("slug") or ""
    if not roadmap_id:
        raise ValueError("в roadmap отсутствует slug")
    if not nodes:
        raise ValueError("в roadmap нет нод")

    topics = []
    for n in nodes:
        if n.get("type") not in TOPIC_TYPES:
            continue
        label = (n.get("data") or {}).get("label") or ""
        if not label.strip():
            continue
        pos = n.get("position") or {}
        topics.append(
            {
                "roadmap_id": roadmap_id,
                "node_id": n.get("id") or "",
                "label": label.strip(),
                "kind": n["type"],
                "x": pos.get("x") or 0,
                "y": pos.get("y") or 0,
            }
        )

    if not topics:
        raise ValueError("в roadmap нет тем (topic/subtopic)")
    topics.sort(key=lambda t: (t["y"], t["x"]))
    return topics


def save_topics(roadmap: dict, out_dir: Path) -> Path:
    """Сохранить упорядоченный список тем в data/roadmaps/<id>/topics.json."""
    roadmap_id = roadmap["slug"]
    topics = parse_topics(roadmap)
    out = Path(out_dir) / "roadmaps" / roadmap_id / "topics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"roadmap_id": roadmap_id, "topics": topics}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return out