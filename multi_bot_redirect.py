import json
import logging
import random
import subprocess
import threading
import time
from pathlib import Path

import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


REDIRECT_URL = "youurl.com"  # Замените на ваш URL для перенаправления
STATS_FILE = Path("button_stats.json")
TOKENS_FILE = Path("bot_tokens.json")
SERVICE_NAME = "botvpnredirect"

# Add your Telegram user IDs here to allow stats access.
ADMIN_IDS = {
    552181926,
}

BUTTON_TEXT_VARIANTS = [
    "VPN 🚀 БЕСПЛАТНО 48 ЧАСОВ",
    "ЗАБРАТЬ VPN 🚀 48 ЧАСОВ БЕСПЛАТНО",
    "ПОЛУЧИТЬ БЕСПЛАТНЫЙ VPN 🎁",
    "ОТКРЫТЬ VPN БЕЗ ОПЛАТЫ 🔥",
    "АКТИВИРОВАТЬ 48 ЧАСОВ VPN 🚀",
    "ЗАПУСТИТЬ VPN СЕЙЧАС ⚡",
    "ПОЛУЧИТЬ ДОСТУП К VPN 🔐",
    "ВКЛЮЧИТЬ VPN БЕСПЛАТНО ✅",
    "ЗАБРАТЬ ПРОБНЫЙ VPN 🎯",
    "ПЕРЕЙТИ И ПОЛУЧИТЬ VPN 🚀",
]

MENU_BUTTONS = [
    "Оплата",
    "Настройки",
    "Техподдержка",
    "Мои ключи",
]

BOT_TOKENS = [

]


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
)

stats_lock = threading.Lock()
tokens_lock = threading.Lock()


def load_stats() -> dict:
    if not STATS_FILE.exists():
        return {"bots": {}}

    try:
        return json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logging.exception("Failed to load stats from %s", STATS_FILE)
        return {"bots": {}}


def save_stats(stats: dict) -> None:
    STATS_FILE.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_bot_tokens() -> list[str]:
    if TOKENS_FILE.exists():
        try:
            data = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                tokens = [str(token).strip() for token in data if str(token).strip()]
                if tokens:
                    return tokens
        except (json.JSONDecodeError, OSError):
            logging.exception("Failed to load bot tokens from %s", TOKENS_FILE)

    save_bot_tokens(BOT_TOKENS)
    return BOT_TOKENS.copy()


def save_bot_tokens(tokens: list[str]) -> None:
    TOKENS_FILE.write_text(
        json.dumps(tokens, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_bot_token(token: str) -> tuple[bool, str]:
    clean_token = token.strip()
    if ":" not in clean_token:
        return False, "Неверный формат токена."

    with tokens_lock:
        tokens = load_bot_tokens()
        if clean_token in tokens:
            return False, "Этот токен уже есть в списке."

        try:
            bot_info = telebot.TeleBot(clean_token).get_me()
        except Exception:
            logging.exception("Failed to validate new bot token")
            return False, "Не удалось проверить токен. Проверьте, что он корректный."

        tokens.append(clean_token)
        save_bot_tokens(tokens)
        bot_username = bot_info.username or f"bot_{clean_token[-6:]}"
        return True, bot_username


def restart_service_after_delay(delay_seconds: float = 2.0) -> None:
    def worker() -> None:
        time.sleep(delay_seconds)
        try:
            subprocess.run(
                ["systemctl", "restart", SERVICE_NAME],
                check=True,
            )
        except Exception:
            logging.exception("Failed to restart service %s", SERVICE_NAME)

    threading.Thread(target=worker, daemon=True, name="service-restarter").start()


def get_bot_stats(stats: dict, bot_username: str) -> dict:
    bots = stats.setdefault("bots", {})
    return bots.setdefault(
        bot_username,
        {
            "total_clicks": 0,
            "variants": {},
            "users": {},
        },
    )


def build_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    variant_index = random.randrange(len(BUTTON_TEXT_VARIANTS))
    markup.add(
        InlineKeyboardButton(
            BUTTON_TEXT_VARIANTS[variant_index],
            url=REDIRECT_URL,
        )
    )
    for button_text in MENU_BUTTONS:
        markup.add(InlineKeyboardButton(button_text, url=REDIRECT_URL))
    return markup


def build_welcome_text(first_name: str | None) -> str:
    user_name = (first_name or "друг").strip() or "друг"
    return (
        f"Привет, <b>{user_name}</b>!\n\n"
        "Меня зовут RAKETA 👨‍💻 и мы создали свой VPN, чтобы вам было комфортно пользоваться VPN:\n\n"
        "✅ Приватные сервера с защитой от блокировок\n"
        "🚀 Скорость до 10Gb/сек\n"
        "🌱 Без рекламы и без вылетов\n"
        "📋 Белый список для мобильного интернета\n\n"
        "Нажмите кнопку ниже, чтобы получить пробный доступ на 48 часов."
    )


def format_stats(bot_username: str) -> str:
    stats = load_stats()
    bot_stats = get_bot_stats(stats, bot_username)
    lines = [
        f"Бот: @{bot_username}",
        f"Всего кликов: {bot_stats['total_clicks']}",
        "",
        "По кнопкам:",
    ]

    variants = bot_stats["variants"]
    if variants:
        for index in sorted(variants, key=lambda value: int(value)):
            item = variants[index]
            lines.append(f"{int(index) + 1}. {item['text']} — {item['clicks']}")
    else:
        lines.append("Нет данных")

    lines.append("")
    lines.append("Топ пользователей:")
    users = bot_stats["users"]
    if users:
        sorted_users = sorted(
            users.items(),
            key=lambda item: item[1].get("clicks", 0),
            reverse=True,
        )[:10]
        for user_id, item in sorted_users:
            username = item.get("username") or "без username"
            lines.append(f"{user_id} (@{username}) — {item['clicks']}")
    else:
        lines.append("Нет данных")

    return "\n".join(lines)


def send_redirect_message(bot: telebot.TeleBot, chat_id: int, first_name: str | None) -> None:
    bot.send_message(
        chat_id,
        build_welcome_text(first_name),
        reply_markup=build_markup(),
    )


def build_welcome_text(first_name: str | None, bot_username: str | None = None) -> str:
    user_name = (first_name or "друг").strip() or "друг"
    bot_name = f"@{bot_username}" if bot_username else "HAPP VPN"
    return (
        f"Привет, <b>{user_name}</b>!\n\n"
        f"Я {bot_name} 👨‍💻\n\n"
        "Это быстрый VPN на базе HAPP VLESS для стабильного обхода блокировок без сложной настройки.\n\n"
        "✅ Работает там, где обычный VPN уже не справляется\n"
        "✅ Высокая скорость для YouTube, Instagram, TikTok и сайтов\n"
        "✅ Стабильное подключение без рекламы и лишних действий\n"
        "✅ Бесплатный доступ на 48 часов для тестирования\n\n"
        "Заходи и проверь сам. Нажми кнопку ниже и получи тестовый доступ прямо сейчас."
    )


def send_redirect_message(bot: telebot.TeleBot, chat_id: int, first_name: str | None) -> None:
    bot_info = bot.get_me()
    bot_username = bot_info.username if bot_info else None
    bot.send_message(
        chat_id,
        build_welcome_text(first_name, bot_username),
        reply_markup=build_markup(),
    )


def run_bot(token: str) -> None:
    bot = telebot.TeleBot(token, parse_mode="HTML")
    bot_info = bot.get_me()
    bot_username = bot_info.username or f"bot_{token[-6:]}"

    @bot.message_handler(commands=["start"])
    def start_handler(message):
        send_redirect_message(bot, message.chat.id, message.from_user.first_name)

    @bot.message_handler(commands=["stats"])
    def stats_handler(message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "Нет доступа.")
            return

        bot.send_message(message.chat.id, format_stats(bot_username))

    @bot.message_handler(commands=["add"])
    def add_handler(message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "Нет доступа.")
            return

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(message, "Использование: /add <token>")
            return

        ok, result = add_bot_token(parts[1])
        if not ok:
            bot.reply_to(message, result)
            return

        bot.send_message(
            message.chat.id,
            (
                f"Бот @{result} добавлен.\n"
                f"Скрипт перезапущен через systemctl restart {SERVICE_NAME}.\n"
                "Проверяйте нового бота через несколько секунд."
            ),
        )
        restart_service_after_delay()

    @bot.message_handler(func=lambda message: True)
    def fallback_handler(message):
        send_redirect_message(bot, message.chat.id, message.from_user.first_name)

    logging.info("Started bot @%s", bot_username)

    while True:
        try:
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=30,
                skip_pending=True,
            )
        except Exception as exc:
            logging.exception(
                "Bot polling failed for token ending with %s: %s",
                token[-6:],
                exc,
            )
            time.sleep(5)


def main() -> None:
    threads = []

    for token in load_bot_tokens():
        thread = threading.Thread(target=run_bot, args=(token,), daemon=True)
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
