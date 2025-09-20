import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.handlers import router
from app.db import init_db

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

# ✅ Default parse_mode ishlatamiz
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)


async def main():
    init_db()
    logging.info("🤖 Bot ishga tushyapti...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
