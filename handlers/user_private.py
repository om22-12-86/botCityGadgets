from aiogram import F, types, Router
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_add_to_cart, orm_add_user
from filters.chat_types import ChatTypeFilter
from handlers.menu_processing import get_menu_content, carts  # Импортируем функции
from kbds.inline import MenuCallBack

# Создаем новый роутер для частных сообщений (личных сообщений пользователей)
user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))  # Ограничиваем роутер для частных чатов


# Обработчик команды /start
@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    """
    Обработчик команды /start. Отправляет пользователю главное меню.
    :param message: Сообщение, содержащее команду /start
    :param session: Асинхронная сессия для взаимодействия с базой данных
    """
    # Получаем основное меню из функции get_menu_content
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main")

    # Отправляем пользователю изображение с кнопками главного меню
    await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)


# Функция для добавления товара в корзину
async def add_to_cart(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):
    """
    Добавляет товар в корзину для пользователя.
    :param callback: Объект CallbackQuery от нажатия кнопки пользователем
    :param callback_data: Данные callback (в т.ч. ID продукта)
    :param session: Асинхронная сессия для взаимодействия с базой данных
    """
    user = callback.from_user  # Получаем данные пользователя из callback
    # Добавляем пользователя в базу данных, если его нет
    await orm_add_user(
        session,
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=None,
    )
    # Добавляем товар в корзину пользователя
    await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id)
    # Отправляем уведомление пользователю
    await callback.answer("Товар добавлен в корзину.")


# Основной обработчик callback-запросов
@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):
    """
    Основной обработчик для всех callback-запросов, связанных с меню.
    Обрабатывает добавление товаров в корзину и навигацию по меню.
    :param callback: Объект CallbackQuery, получаемый при взаимодействии пользователя с интерфейсом
    :param callback_data: Данные callback (навигация по меню, категория, страница и др.)
    :param session: Асинхронная сессия для взаимодействия с базой данных
    """
    # Если пользователь нажал кнопку для добавления товара в корзину
    if callback_data.menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session)  # Вызываем функцию добавления товара в корзину
        return  # Выходим из обработчика, так как действие выполнено

    # Получаем текущее содержимое меню для данного уровня, категории и страницы
    media, reply_markup = await get_menu_content(
        session,
        level=callback_data.level,
        menu_name=callback_data.menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_id=callback.from_user.id,
    )

    # Проверяем, что содержимое представляет собой изображение
    if isinstance(media, types.InputMediaPhoto):
        new_media = media.media  # Если это изображение, сохраняем изображение
    else:
        new_media = media  # Если это текст, сохраняем текст

    current_reply_markup = callback.message.reply_markup  # Текущая разметка кнопок

    # Проверяем, изменилось ли сообщение (контент или кнопки)
    if current_reply_markup != reply_markup or new_media != callback.message.text:
        # Если это изображение, редактируем медиа-сообщение
        if isinstance(media, types.InputMediaPhoto):
            await callback.message.edit_media(media=media, reply_markup=reply_markup)
        else:
            # Если это текст, редактируем текстовое сообщение
            await callback.message.edit_text(text=media, reply_markup=reply_markup)
        # Закрываем уведомление callback
        await callback.answer()
    else:
        # Если содержимое не изменилось, просто уведомляем пользователя
        await callback.answer("Сообщение не изменилось.")
