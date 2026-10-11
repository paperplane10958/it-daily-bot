# Деплой IT Daily Bot на VPS

Целевой сервер: 1 CPU / 1 GB RAM, рядом уже работает AmneziaWG. Роль бота —
только выдача уроков; генерация остаётся на рабочей машине.

## 0. Что идёт на сервер

| Что | Как |
|---|---|
| Код | `git clone` / `git pull` с GitHub (ветка `main`) |
| Уроки | `data/lessons.db` через `scp` с рабочей машины (в .gitignore) |
| Секреты | `.env` через `scp` (токен бота, ключ OpenRouter) |
| Зависимости | `uv` (без sudo-пакетов), venv внутри репо |
| Сервис | `deploy/it-daily-bot.service` |

Важно: в `data/lessons.db` лежит и прогресс пользователей (таблица `progress`),
и настройки напоминаний. Перезапись базы на сервере затирает прогресс —
сделать бэкап перед каждым обновлением (шаг 6).

## 1. Код на сервере

```bash
ssh <server>
git clone git@github.com:paperplane10958/it-daily-bot.git ~/it-daily-bot
# или, если уже клонирован: cd ~/it-daily-bot && git pull
```

Если на сервере нет ssh-ключа для GitHub — использовать HTTPS-clone (публичный
репо читается без аутентификации):

```bash
git clone https://github.com/paperplane10958/it-daily-bot.git ~/it-daily-bot
```

## 2. Python и зависимости (uv, без sudo)

Код требует Python ≥ 3.10 (aiogram 3.31, синтаксис 3.10+). На старых дистрибутивах
(Debian 11 = 3.9) системный Python не трогаем — uv ставит собственный:

```bash
cd ~/it-daily-bot
if [ ! -x ~/.local/bin/uv ]; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.13
rm -rf .venv
uv venv .venv --python 3.13
uv pip install -r requirements.txt --python .venv/bin/python
```

## 3. База уроков и .env (с рабочей машины, не с сервера)

```bash
# локально, в корне репо:
scp data/lessons.db <server>:~/it-daily-bot/data/lessons.db
scp .env <server>:~/it-daily-bot/.env
```

На сервере проверить, что бот доступен напрямую (у него своя сеть, не твоя):

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://api.telegram.org
# 200/404 — прямой доступ есть, BOT_PROXY в .env на сервере НЕ нужен:
#   закомментировать строку BOT_PROXY=... (aiogram сам ходит напрямую)
# 000/таймаут — оставить BOT_PROXY как есть
```

## 4. Проверка вручную перед сервисом

```bash
cd ~/it-daily-bot
.venv/bin/python -m pytest tests/ -q     # 129 passed
.venv/bin/python -m src.bot.__main__     # запустить в фоне/в tmux
# в Telegram: /lesson, /progress, /remind
# затем Ctrl+C
```

Внимание: пока локальный бот тоже запущен, два long-polling конфликляют
(токен один) — перед проверкой на сервере локальный остановить.

## 5. systemd-сервис

```bash
sed "s/CHANGE_ME/$USER/" deploy/it-daily-bot.service | sudo tee /etc/systemd/system/it-daily-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now it-daily-bot
journalctl -u it-daily-bot -f          # логи; выйти Ctrl+C, сервис продолжит
systemctl status it-daily-bot          # должно быть active (running)
```

## 6. Обновление бота/уроков (обычный цикл)

```bash
# на сервере:
cd ~/it-daily-bot
sudo systemctl stop it-daily-bot
cp data/lessons.db data/lessons.db.bak   # прогресс пользователей
git pull
# если менялись уроки: перезалить базу с рабочей машины
#   (локально: scp data/lessons.db <server>:~/it-daily-bot/data/lessons.db)
# если менялись зависимости: export PATH="$HOME/.local/bin:$PATH"
#   && uv pip install -r requirements.txt --python .venv/bin/python
sudo systemctl start it-daily-bot
```

Бэкапы копить не бездумно: `ls -lh data/*.bak` и удалять старые руками.

## 7. Если что-то пошло не так

- `systemctl status it-daily-bot` и `journalctl -u it-daily-bot -n 50` — первые зацепки.
- «BOT_TOKEN не задан» — .env не на месте (должен быть `~/it-daily-bot/.env`).
- Сеть: `curl -s https://api.telegram.org` с сервера.
- Свап (рекомендация, если ещё нет): `sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` + строка в `/etc/fstab`.
