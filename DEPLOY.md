# Деплой IELTS Bot на DigitalOcean Droplet

Пошаговая инструкция по развёртыванию бота на Ubuntu-сервере DigitalOcean.

---

## Часть 1 — Создание Droplet на DigitalOcean

1. Зайди на [digitalocean.com](https://digitalocean.com) → **Create** → **Droplets**
2. Выбери:
   - **Region:** ближайший к аудитории (например, Frankfurt или Amsterdam)
   - **Image:** Ubuntu 22.04 LTS x64
   - **Plan:** Basic — **Regular** — **$6/mo** (1 vCPU / 1 GB RAM / 25 GB SSD)
     > Если будет много пользователей — выбирай $12/mo (2 GB RAM)
   - **Authentication:** SSH Key (рекомендуется) или Password
3. Нажми **Create Droplet**
4. Скопируй IP-адрес дроплета (например, `164.90.xxx.xxx`)

---

## Часть 2 — Первое подключение к серверу

```bash
# Подключись по SSH с локального компьютера
ssh root@164.90.xxx.xxx

# Обнови систему
apt update && apt upgrade -y
```

---

## Часть 3 — Установка зависимостей системы

```bash
# Python 3.11+ и pip
apt install -y python3 python3-pip python3-venv python3-full

# FFmpeg (конвертация аудио OGG → MP3)
apt install -y ffmpeg

# Git
apt install -y git

# Проверка версий
python3 --version   # должно быть 3.11+
ffmpeg -version
git --version
```

---

## Часть 4 — Создание отдельного пользователя (безопасность)

```bash
# Создать пользователя ieltsbot
adduser --disabled-password --gecos "" ieltsbot

# Создать рабочую директорию
mkdir -p /opt/ielts-bot/savings
chown -R ieltsbot:ieltsbot /opt/ielts-bot
```

---

## Часть 5 — Загрузка кода на сервер

### Вариант A: через Git (рекомендуется)

```bash
# Переключись на пользователя ieltsbot
su - ieltsbot

# Клонировать репозиторий
cd /opt/ielts-bot
git clone <ссылка-на-репозиторий> .

# Вернуться к root
exit
```

### Вариант B: через scp (с локального компьютера)

Выполняй эти команды **на своём компьютере**, не на сервере:

```bash
# Упаковать проект
cd /путь/к/проекту
zip -r ielts-bot.zip . \
  --exclude ".git/*" \
  --exclude "bot/savings/*" \
  --exclude "venv/*" \
  --exclude "__pycache__/*" \
  --exclude "*.pyc" \
  --exclude ".env"

# Загрузить на сервер
scp ielts-bot.zip root@164.90.xxx.xxx:/opt/ielts-bot/

# На сервере — распаковать
ssh root@164.90.xxx.xxx
cd /opt/ielts-bot
apt install -y unzip
unzip ielts-bot.zip
chown -R ieltsbot:ieltsbot /opt/ielts-bot
```

---

## Часть 6 — Настройка Python-окружения

```bash
# Переключиться на пользователя бота
su - ieltsbot
cd /opt/ielts-bot

# Создать виртуальное окружение
python3 -m venv venv

# Активировать
source venv/bin/activate

# Установить зависимости
pip install --upgrade pip
pip install -r requirements.txt

# Деактивировать
deactivate
exit
```

---

## Часть 7 — Создание файла .env с секретами

```bash
# Создать .env файл (от root)
nano /opt/ielts-bot/.env
```

Вставь содержимое (замени значения на свои):

```env
BOT_TOKEN=8716627566:AAHetGZWlAt4JModw8xJKtP97twofihhxBE
MY_CHAT_ID=266889430
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
VIDEO_SAVING_PATH=/opt/ielts-bot/savings
```

Сохрани: `Ctrl+O`, `Enter`, `Ctrl+X`

```bash
# Защитить файл — только владелец может читать
chown ieltsbot:ieltsbot /opt/ielts-bot/.env
chmod 600 /opt/ielts-bot/.env
```

---

## Часть 8 — Настройка автозапуска через systemd

```bash
# Скопировать service-файл
cp /opt/ielts-bot/ielts-bot.service /etc/systemd/system/

# Перезагрузить конфиги systemd
systemctl daemon-reload

# Включить автозапуск при старте сервера
systemctl enable ielts-bot

# Запустить бота прямо сейчас
systemctl start ielts-bot

# Проверить статус
systemctl status ielts-bot
```

Если всё ОК, увидишь:
```
● ielts-bot.service - IELTS Telegram Bot
     Active: active (running) since ...
```

---

## Часть 9 — Проверка работы

```bash
# Смотреть логи в реальном времени
journalctl -u ielts-bot -f

# Последние 50 строк логов
journalctl -u ielts-bot -n 50
```

В логах должно появиться:
```
INFO:aiogram.dispatcher:Start polling
```

Отправь боту `/start` в Telegram — должен ответить.
Отправь голосовое сообщение — через 15-30 секунд должна прийти оценка.

---

## Управление ботом

```bash
# Остановить бота
systemctl stop ielts-bot

# Перезапустить (например, после обновления кода)
systemctl restart ielts-bot

# Посмотреть статус
systemctl status ielts-bot

# Логи за сегодня
journalctl -u ielts-bot --since today
```

---

## Обновление кода (если использовался Git)

```bash
su - ieltsbot
cd /opt/ielts-bot
git pull origin main
exit

# Перезапустить бота
systemctl restart ielts-bot
```

---

## Обновление кода (если использовался scp)

```bash
# На локальном компьютере — загрузить новые файлы
scp bot/bot.py root@164.90.xxx.xxx:/opt/ielts-bot/bot/
scp chatgpt_api/gpt.py root@164.90.xxx.xxx:/opt/ielts-bot/chatgpt_api/

# На сервере — перезапустить
ssh root@164.90.xxx.xxx
systemctl restart ielts-bot
```

---

## Часть 10 — Автоочистка аудиофайлов (03:00 по Ташкенту)

Бот удаляет временные файлы сам после каждого запроса, но на случай сбоя —
настроим ночную очистку через cron.

```bash
# Сделать скрипт исполняемым
chmod +x /opt/ielts-bot/cleanup_audio.sh

# Открыть crontab от имени пользователя ieltsbot
crontab -u ieltsbot -e
```

Добавь строку (22:00 UTC = 03:00 Ташкент, UTC+5):

```
0 22 * * * VIDEO_SAVING_PATH=/opt/ielts-bot/savings /opt/ielts-bot/cleanup_audio.sh
```

Сохрани и выйди (`Ctrl+O`, `Enter`, `Ctrl+X` если nano).

```bash
# Проверить что задача добавилась
crontab -u ieltsbot -l

# Проверить логи очистки (появятся после первого запуска)
grep "ielts-bot-cleanup" /var/log/syslog
```

---

## Настройка файрвола (опционально, но рекомендуется)

```bash
# Разрешить только SSH
ufw allow OpenSSH
ufw enable

# Проверить
ufw status
```

Бот работает через исходящие HTTPS-соединения к Telegram и OpenAI —
входящие порты не нужны.

---

## Возможные проблемы

### Бот не запускается
```bash
# Смотри подробные логи
journalctl -u ielts-bot -n 100 --no-pager
```

Частые причины:
- Неправильный `BOT_TOKEN` или `OPENAI_API_KEY` в `.env`
- Не установлены зависимости (повтори Часть 6)
- Ошибка в пути `VIDEO_SAVING_PATH` — убедись, что папка существует

### FFmpeg не найден
```bash
which ffmpeg      # должен вернуть /usr/bin/ffmpeg
ffmpeg -version
# Если не установлен:
apt install -y ffmpeg
```

### Нет прав на папку savings
```bash
ls -la /opt/ielts-bot/
chown -R ieltsbot:ieltsbot /opt/ielts-bot/savings
chmod 755 /opt/ielts-bot/savings
```

---

## Итоговая структура на сервере

```
/opt/ielts-bot/
├── bot/
│   ├── bot.py
│   ├── config.py
│   └── savings/          ← голосовые файлы (создаётся автоматически)
├── chatgpt_api/
│   ├── __init__.py
│   └── gpt.py
├── venv/                  ← Python-окружение
├── .env                   ← СЕКРЕТЫ (не в git!)
├── requirements.txt
├── ielts-bot.service
└── cleanup_audio.sh      ← запускается cron в 03:00 по Ташкенту
```
