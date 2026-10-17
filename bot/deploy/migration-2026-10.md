# Миграция сервера на структуру bot/ (2026-10)

Разовое обновление: на сервере уже стоит старая структура (код в корне,
база в `data/lessons.db`). После мерджа `refactor/split-generator` в `main`
сервер переезжает на новую: код бота в `bot/`, база в `bot/data/lessons.db`.
Даунтайм — пара минут (бот на это время остановлен).

Главное правило миграции: **базу не заливаем с рабочей машины** — серверная
`data/lessons.db` главнее (там живой прогресс пользователей). Мы её копируем
внутри сервера в новое место. Старый файл не трогаем — это и есть откат.

## 1. Локально: смержить и запушить

```bash
git checkout main
git merge --no-ff refactor/split-generator -m "merge: inline-меню + разделение bot/generator"
git push origin main
```

## 2. На сервере: остановить, обновить, перенести базу

```bash
ssh <server>
cd ~/it-daily-bot

# 2.1 остановить бот (пока не трогаем юнит — просто стоп)
sudo systemctl stop it-daily-bot

# 2.2 бэкап живой базы (на всякий случай, рядом с оригиналом)
cp data/lessons.db data/lessons.db.migration.bak

# 2.3 новый код (старый src/ исчезнет из репо — сервис до юнита не трогаем!)
git pull

# 2.4 база в новый дом: КОПИЯ, не перенос
mkdir -p bot/data
cp data/lessons.db bot/data/lessons.db

# 2.5 зависимости (состав не менялся, команда идемпотентна)
export PATH="$HOME/.local/bin:$PATH"
uv pip install -r bot/requirements.txt -r generator/requirements.txt --python .venv/bin/python

# 2.6 тесты бота на сервере
cd ~/it-daily-bot/bot
../.venv/bin/python -m pytest tests/ -q     # ожидание: 118 passed
```

## 3. Юнит и ручная проверка

```bash
# 3.1 новый юнит: WorkingDirectory теперь ~/it-daily-bot/bot
# (пути — от корня репо: после §2.6 ты в bot/, вернись командой cd ~/it-daily-bot)
cd ~/it-daily-bot
sed "s/CHANGE_ME/$USER/" bot/deploy/it-daily-bot.service | sudo tee /etc/systemd/system/it-daily-bot.service
sudo systemctl daemon-reload
grep -E "WorkingDirectory|ExecStart" /etc/systemd/system/it-daily-bot.service

# 3.2 проверка руками перед сервисом (локальный бот на рабочей машине — выключить!)
cd ~/it-daily-bot/bot
../.venv/bin/python -m src.bot.__main__
#   в Telegram: /start (меню со статистикой), /lesson, /progress — затем Ctrl+C
```

## 4. Запуск и живая проверка

```bash
sudo systemctl start it-daily-bot
systemctl status it-daily-bot        # active (running)
journalctl -u it-daily-bot -f        # логи; Ctrl+C выйти
```

В Telegram: `/start` → шапка с прогрессом/XP/стриком + 4 кнопки; синяя
меню-кнопка у поля ввода; `/lesson` отдаёт следующий непройденный урок.

## 5. Откат (если что-то не так до/ после старта)

Старая структура осталась нетронутой: база так же лежит в `data/lessons.db`
(мы делали копию), юнит можно вернуть:

```bash
cd ~/it-daily-bot
git checkout c7097b5                        # старый код (коммит до мерджа)
# если юнит уже перезаписан — вернуть старый вид (WorkingDirectory=%h/it-daily-bot,
# ExecStart=%h/it-daily-bot/.venv/bin/python -m src.bot.__main__) и daemon-reload
sudo systemctl start it-daily-bot
```

Прогресс при откате не теряется: новая копия в `bot/data/` — копия, оригинал
в `data/lessons.db.migration.bak` не перезаписан.

## 6. После миграции

- Обычный цикл обновлений — §6 `bot/deploy/README.md` (git pull + restart;
  базу трогать, только если менялись уроки).
- `data/` на сервере больше не используется рабочим ботом: `data/lessons.db.migration.bak`
  можно держать как бэкап до первой успешной недели, потом удалить.
- Новые уроки: генерация локально в `generator/data/lessons.db` → перенос
  уроков в `bot/data/lessons.db` → scp на сервер (с бэкапом серверной базы).