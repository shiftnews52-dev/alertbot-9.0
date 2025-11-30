"""
main.py - Точка входа для бота CryptoMicky Alerts
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import BOT_TOKEN, TIMEFRAME, CANDLE_SECONDS, CHECK_INTERVAL, SIGNAL_COOLDOWN, MIN_CONFIDENCE_SCORE, MIN_VOLUME_MULTIPLIER, MIN_VOLATILITY
from handlers import setup_handlers
from tasks import price_collector, signal_analyzer
from database import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("=" * 60)
print("📊 НАСТРОЙКИ БОТА")
print("=" * 60)
print(f"⏰ Таймфрейм: {TIMEFRAME} (фиксированный)")
print(f"🕐 Секунд в свече: {CANDLE_SECONDS}")
print(f"🔄 Интервал проверки: {CHECK_INTERVAL}s")
print(f"⏳ Cooldown: {SIGNAL_COOLDOWN}s ({SIGNAL_COOLDOWN/3600:.1f}ч)")
print(f"📊 Минимальный score: {MIN_CONFIDENCE_SCORE}")
print(f"📈 Мин. объём: {MIN_VOLUME_MULTIPLIER}x")
print(f"💹 Мин. волатильность: {MIN_VOLATILITY}%")
print("=" * 60)

async def main():
    """Основная функция запуска бота"""
    # Инициализируем базу данных
    await init_db()
    
    bot = Bot(token=BOT_TOKEN, parse_mode='HTML')
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
    
    # Регистрируем handlers
    setup_handlers(dp)
    
    logger.info("🤖 CryptoMicky Alerts Bot started")
    
    # Запускаем фоновые задачи
    asyncio.create_task(price_collector(bot))
    asyncio.create_task(signal_analyzer(bot))
    
    # Запускаем бота
    try:
        await dp.start_polling()
    finally:
        await bot.close()

if __name__ == '__main__':
    asyncio.run(main())
