#!/bin/bash
# Удаляет все аудиофайлы старше 1 часа из папки savings
# Запускается ежедневно в 03:00 по Ташкенту (22:00 UTC) через cron

SAVINGS_DIR="${VIDEO_SAVING_PATH:-/opt/ielts-bot/savings}"
LOG_TAG="ielts-bot-cleanup"

deleted=$(find "$SAVINGS_DIR" -maxdepth 1 -type f \( -name "*.mp3" -o -name "*.ogg" \) -mmin +60 -print -delete 2>&1)

if [ -n "$deleted" ]; then
    echo "$deleted" | while read -r f; do
        logger -t "$LOG_TAG" "Удалён файл: $f"
    done
else
    logger -t "$LOG_TAG" "Нечего удалять."
fi
