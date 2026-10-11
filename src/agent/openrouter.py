"""Минимальный клиент OpenRouter (OpenAI-совместимый chat/completions).

httpx вместо urllib: OpenRouter блокирует TLS-отпечаток python-urllib (403
"Access denied by security policy"), httpx с тем же ключом проходит.
Прокси берётся из окружения (ALL_PROXY/HTTPS_PROXY) автоматически.
"""

import json

import httpx

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient:
    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-haiku", timeout: int = 300):
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

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        try:
            resp = httpx.post(
                API_URL,
                json=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/paperplane10958/it-daily-bot",
                    "X-Title": "IT Daily Bot",
                },
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            raise RuntimeError(f"OpenRouter недоступен: {e}") from e

        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter вернул {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"неожиданный ответ OpenRouter: {json.dumps(data)[:300]}") from e