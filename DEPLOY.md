# Деплой IELTS Bot на DigitalOcean Droplet

---

## ПОЛНЫЙ СБРОС (если уже что-то стоит и надо начать заново)

Выполняй от `root`:

```bash
# Остановить и удалить сервис
systemctl stop ielts-bot
systemctl disable ielts-bot
rm -f /etc/systemd/system/ielts-bot.service
systemctl daemon-reload

# Удалить всё приложение
rm -rf /opt/ielts-bot

# Удалить пользователя
userdel -r ieltsbot 2>/dev/null || true

# Удалить cron-задачу если была
crontab -u ieltsbot -r 2>/dev/null || true
```

После этого можно начинать установку с нуля с Части 3.

---

## Часть 1 — Создание Droplet

1. Зайди на [digitalocean.com](https://digitalocean.com) → **Create** → **Droplets**
2. Выбери:
   - **Region:** ближайший к аудитории (Frankfurt или Amsterdam)
   - **Image:** Ubuntu 22.04 LTS x64
   - **Plan:** Basic → Regular → **$6/mo** (1 vCPU / 1 GB RAM / 25 GB SSD)
   - **Authentication:** SSH Key или Password
3. Нажми **Create Droplet**, скопируй IP-адрес

---

## Часть 2 — Подключение к серверу

```bash
ssh root@<IP-адрес>

# Обновить систему
apt update && apt upgrade -y
```

---

## Часть 3 — Установка системных зависимостей

```bash
apt install -y python3 python3-pip python3-venv python3-full ffmpeg git

# Проверка
python3 --version    # 3.11+
ffmpeg -version
git --version
```

---

## Часть 4 — Создание пользователя и директории

```bash
adduser --disabled-password --gecos "" ieltsbot
mkdir -p /opt/ielts-bot
chown -R ieltsbot:ieltsbot /opt/ielts-bot
```

> Папка `savings` для аудиофайлов создаётся ботом автоматически при запуске.

---

## Часть 5 — Загрузка кода

```bash
su - ieltsbot
cd /opt/ielts-bot

git clone -b claude/fix-telegram-whisper-bugs-tze0T <ссылка-на-репозиторий> .

exit
```

> Замени `<ссылка-на-репозиторий>` на реальный URL репозитория.

---

## Часть 6 — Python-окружение

```bash
su - ieltsbot
cd /opt/ielts-bot

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

exit
```

---

## Часть 7 — Файл .env с секретами

```bash
nano /opt/ielts-bot/.env
```

Вставь и заполни своими значениями:

```env
BOT_TOKEN=токен_от_BotFather
OPENAI_API_KEY=sk-...
VIDEO_SAVING_PATH=/opt/ielts-bot/savings
GROUP_ID=-1001234567890
GROUP_IDS=-1001234567890,-1002345678901,-1003456789012
```

`GROUP_ID` оставлен для совместимости с одной группой. Для нескольких групп заполни `GROUP_IDS` ID групп через запятую. Если указаны оба параметра, бот разрешит доступ по всем группам.

**Как узнать GROUP_ID / GROUP_IDS:**
1. Добавь бота `@userinfobot` в свою группу
2. Напиши в группе `/start`
3. Он ответит ID группы — скопируй (число со знаком минус, например `-1009876543210`)
4. Удали `@userinfobot` из группы

Сохрани файл: `Ctrl+O` → `Enter` → `Ctrl+X`

```bash
# Закрыть доступ к .env для посторонних
chown ieltsbot:ieltsbot /opt/ielts-bot/.env
chmod 600 /opt/ielts-bot/.env
```

---

## Часть 8 — Systemd сервис

```bash
cp /opt/ielts-bot/ielts-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable ielts-bot
systemctl start ielts-bot

# Проверить статус
systemctl status ielts-bot
```

Должно быть:
```
Active: active (running)
```

```bash
# Смотреть логи в реальном времени
journalctl -u ielts-bot -f
```

В логах должно появиться:
```
INFO:aiogram.dispatcher:Start polling
```

---

## Часть 9 — Бот в Telegram

1. Добавь бота в свою группу
2. Назначь бота **администратором** с правом **«Удаление сообщений»**
3. Напиши боту в личку `/start`

**Ожидаемое поведение:**
- Если ты **администратор группы** → приветствие учителя с расширенным анализом
- Если ты **участник группы** → приветствие ученика с базовой оценкой IELTS
- Если тебя **нет в группе** → «Доступ закрыт»

---

## Часть 10 — Автоочистка аудиофайлов

Бот удаляет файлы сам после каждого запроса, но для подстраховки — ночная очистка через cron:

```bash
chmod +x /opt/ielts-bot/cleanup_audio.sh
crontab -u ieltsbot -e
```

Добавь строку (22:00 UTC = 03:00 по Ташкенту):

```
0 22 * * * VIDEO_SAVING_PATH=/opt/ielts-bot/savings /opt/ielts-bot/cleanup_audio.sh
```

Сохрани: `Ctrl+O` → `Enter` → `Ctrl+X`

```bash
# Проверить что добавилось
crontab -u ieltsbot -l
```

---

## Часть 11 — Файрвол

```bash
ufw allow OpenSSH
ufw enable
ufw status
```

Бот работает через исходящий HTTPS к Telegram и OpenAI — входящие порты не нужны.

---

## Обновление кода

```bash
systemctl stop ielts-bot

su - ieltsbot
cd /opt/ielts-bot
git pull origin claude/fix-telegram-whisper-bugs-tze0T

# Если добавились новые зависимости
source venv/bin/activate
pip install -r requirements.txt
deactivate

exit

systemctl start ielts-bot
journalctl -u ielts-bot -f
```

---

## Управление ботом

```bash
systemctl stop ielts-bot       # остановить
systemctl start ielts-bot      # запустить
systemctl restart ielts-bot    # перезапустить

journalctl -u ielts-bot -f           # логи в реальном времени
journalctl -u ielts-bot -n 50        # последние 50 строк
journalctl -u ielts-bot --since today  # логи за сегодня
```

---

## Возможные проблемы

### Бот не запускается
```bash
journalctl -u ielts-bot -n 100 --no-pager
```
Частые причины:
- Неверный `BOT_TOKEN` или `OPENAI_API_KEY` в `.env`
- Не установлены зависимости → повтори Часть 6
- Неверный `GROUP_ID` → должен быть со знаком минус

### FFmpeg не найден
```bash
which ffmpeg        # должен вернуть /usr/bin/ffmpeg
apt install -y ffmpeg
```

### Бот не реагирует на голосовые
Убедись что `BOT_TOKEN` правильный, бот добавлен в группу и назначен администратором.

---

## Итоговая структура на сервере

```
/opt/ielts-bot/
├── bot/
│   ├── __init__.py
│   ├── bot.py           ← роутинг: приватный чат и группа
│   ├── cache.py         ← TTL-кэш в памяти + отложенное удаление файлов
│   ├── config.py        ← читает .env
│   ├── locks.py         ← per-user очередь запросов
│   ├── roles.py         ← определение роли пользователя
│   └── handlers/
│       ├── group.py     ← модерация группы
│       ├── student.py   ← IELTS-оценка для учеников
│       └── teacher.py   ← расширенный анализ для учителей
├── chatgpt_api/
│   ├── __init__.py
│   └── gpt.py           ← Whisper + GPT-4o, два промпта
├── venv/                ← Python-окружение (не в git)
├── .env                 ← СЕКРЕТЫ (не в git!)
├── requirements.txt
├── ielts-bot.service    ← systemd
└── cleanup_audio.sh     ← cron-очистка в 03:00 Ташкент
```
