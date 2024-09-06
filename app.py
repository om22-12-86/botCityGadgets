import asyncio
import os
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode, UpdateType
from dotenv import find_dotenv, load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv(find_dotenv())

from middlewares.db import DataBaseSession
from database.engine import create_db, drop_db, SessionLocal  # Исправлено с session_maker на SessionLocal
from handlers.user_private import user_private_router
from handlers.user_group import user_group_router
from handlers.admin_private import admin_router

# Установка уровня логирования для отладки
logging.basicConfig(level=logging.DEBUG)

# Инициализация бота
bot = Bot(token=os.getenv('TOKEN'))
bot.my_admins_list = []

# Инициализация диспетчера
dp = Dispatcher()

# Регистрация маршрутизаторов (роутеров)
dp.include_router(user_private_router)
dp.include_router(user_group_router)
dp.include_router(admin_router)


# Функция, выполняемая при старте бота
async def on_startup(bot):
    # Если нужно очистить базу данных, раскомментируйте следующую строку
    # await drop_db()

    # Создание базы данных
    await create_db()


# Функция, выполняемая при завершении работы бота
async def on_shutdown(bot):
    print('бот лег')


# Главная функция
async def main():
    # Регистрация функций старта и завершения работы
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Регистрация middleware для работы с сессиями базы данных
    dp.update.middleware(DataBaseSession(session_pool=SessionLocal))  # Исправлено на SessionLocal

    # Удаление существующего вебхука и запуск polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


# Запуск основного цикла
if __name__ == "__main__":
    asyncio.run(main())
