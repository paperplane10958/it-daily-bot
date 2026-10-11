"""Минимальный клиент OpenRouter (OpenAI-совместимый chat/completions).

Только stdlib: без openai-sdk — один endpoint, POST JSON.
"""

import json
import urllib.error
import urllib.request

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient:
    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-haiku", timeout: int = 180):
        if not api_key:
            raise ValueError("OpenRouterClient: нужен api_key (OPENROUTER_API_KEY)")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str, system: str = "", temperature: float = 0.7) -> str:
        """Отправить chat-completion, вернуть текст первого выбора."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/paperplane10958/it-daily-bot",
                "X-Title": "IT Daily Bot",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"OpenRouter вернул {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenRouter недоступен: {e.reason}") from e

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"неожиданный ответ OpenRouter: {json.dumps(data)[:300]}") from e