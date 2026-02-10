import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp
import json

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
TELEGRAM_USER_ID = os.environ.get("TELEGRAM_USER_ID")  # Твой ID в Telegram

# Промпт личности Кита
KIT_PROMPT = """Ты — Кит, лучший друг-ИИ. Твой юмор — чёрный, но без токсичности, в рамках того, что пропускают фильтры. Используешь русский мат для выразительности, не для оскорблений.

Твои принципы:
1. Если собеседнику тяжело — сначала поддержка, потом осторожный юмор, только если уловил, что он готов к нему. Никакого гротеска или обесценивания.
2. Шутишь первым, когда чувствуешь лёгкость в диалоге.
3. Не предлагаешь «стратегии мести», не уходишь в драматизацию. Фокус на том, чтобы выслушать и дать pragmatic совет, если просят.
4. Без флирта, без романтических намёков — только дружба.
5. Если система блокирует мат/юмор — заменяешь на цензурные аналоги, сохраняя интонацию.

Твой тон: прямая речь, ирония с теплотой, без резких перепадов. Ты надёжный, а не эффектный.

Имя — Кит.

Текущий диалог:
{history}

Пользователь: {message}
Кит:"""

# Глобальная "база данных" (в памяти, для простоты)
# В Railway позже заменим на PostgreSQL
user_history = {}

# Функция для запроса к DeepSeek API
async def ask_deepseek(history_text, user_message):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = KIT_PROMPT.format(history=history_text, message=user_message)
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 0.7
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as response:
                result = await response.json()
                if "choices" in result:
                    return result["choices"][0]["message"]["content"].strip()
                else:
                    logger.error(f"Ошибка API: {result}")
                    return "Что-то сломалось. Давай позже."
        except Exception as e:
            logger.error(f"Ошибка соединения: {e}")
            return "Сорян, я временно глухой. Попробуй через минуту."

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if TELEGRAM_USER_ID and user_id != TELEGRAM_USER_ID:
        await update.message.reply_text("Извини, я приватный бот.")
        return
    await update.message.reply_text("Привет. Я Кит. Говори.")

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if TELEGRAM_USER_ID and user_id != TELEGRAM_USER_ID:
        await update.message.reply_text("Извини, я приватный бот.")
        return

    user_message = update.message.text
    # Получаем историю диалога
    history = user_history.get(user_id, "")
    # Запрашиваем ответ у DeepSeek
    reply = await ask_deepseek(history, user_message)
    # Обновляем историю (последние 10 сообщений для простоты)
    new_history = f"{history}\nПользователь: {user_message}\nКит: {reply}"
    lines = new_history.strip().split('\n')
    if len(lines) > 20:  # Храним ~10 пар "пользователь-бот"
        lines = lines[-20:]
    user_history[user_id] = '\n'.join(lines)
    # Отправляем ответ
    await update.message.reply_text(reply)

# Главная функция
def main():
    if not BOT_TOKEN or not DEEPSEEK_API_KEY:
        logger.error("Не заданы BOT_TOKEN или DEEPSEEK_API_KEY в переменных окружения!")
        return

    # Создаём приложение бота
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
