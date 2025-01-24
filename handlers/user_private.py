from aiogram import F, types, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select
from database.models import Banner, Cart, Category, Product, User
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_add_to_cart, orm_add_user, orm_get_products_by_keywords, orm_get_products, orm_get_user_carts, create_order_from_cart, get_user_orders, display_orders_to_user
from filters.chat_types import ChatTypeFilter
from handlers.menu_processing import get_menu_content, carts# Импортируем функции
from kbds.inline import MenuCallBack, get_product_buttons, get_user_products_btns
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from utils.paginator import Paginator
from aiogram import Bot



user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))  # Ограничиваем роутер для частных чатов


# Обработчик команды /start
@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main")
    await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)


@user_private_router.callback_query(F.data.startswith('category_'))
async def show_category_products(callback: types.CallbackQuery, session: AsyncSession):
    try:
        # Извлекаем данные из callback
        data = callback.data.split('_')
        category_id = int(data[1])
        page = int(data[2]) if len(data) > 2 else 1  # Устанавливаем текущую страницу

        # Получаем список товаров в категории
        products = await orm_get_products(session, category_id)

        if not products:
            await callback.message.answer("В этой категории товары не найдены.")
            return

        # Пагинация: создаем объект Paginator и получаем товары на текущей странице
        paginator = Paginator(products, page=page, per_page=5)  # Показываем 1 товар на странице
        page_products = paginator.get_page()

        # Если на текущей странице нет товаров
        if not page_products:
            await callback.message.answer("На этой странице товаров нет.")
            return

        # Лог для текущей страницы и общего количества страниц
        print(f"Текущая страница: {paginator.page}, Всего страниц: {paginator.pages}")

        # Перебираем товары на текущей странице
        for product in page_products:
            caption = (
                f"<b>{product.name}</b>\n"
                f"Артикул: {product.sku}\n"
                f"{product.description}\n"
                f"Стоимость: {round(product.price, 2)} ₽\n"
                f"В наличии: {product.stock} шт.\n"
                f"<b>Товар {paginator.page} из {paginator.pages}</b>"
            )

            # Если есть изображение, отправляем его
            if product.image:
                await callback.message.answer_photo(
                    product.image,  # Отправляем изображение товара
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=get_product_buttons(category_id, product.id, {}, paginator.page)
                )
            else:
                # Если изображения нет, отправляем только текстовую информацию
                await callback.message.answer(
                    text=caption,
                    parse_mode='HTML',
                    reply_markup=get_product_buttons(category_id, product.id, {}, paginator.page)
                )

        # Создаем кнопки пагинации (внизу списка)
        pagination_btns = {}
        if paginator.has_previous():
            pagination_btns["◀ Пред."] = f"category_{category_id}_{paginator.page - 1}"
        if paginator.has_next():
            pagination_btns["След. ▶"] = f"category_{category_id}_{paginator.page + 1}"

        # Добавляем кнопки пагинации после всех товаров
        if pagination_btns:
            await callback.message.answer(
                text="Выберите страницу:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data)] for text, data in pagination_btns.items()]
                )
            )

    except Exception as e:
        print(f"Ошибка при загрузке товаров: {e}")
        await callback.message.answer("Произошла ошибка при загрузке товаров.")





# Функция для добавления товара в корзину
async def add_to_cart(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):
    user = callback.from_user

    # Проверяем, существует ли пользователь в базе данных
    query = select(User).where(User.user_id == user.id)
    result = await session.execute(query)
    existing_user = result.scalar()

    # Если пользователя нет, добавляем его
    if not existing_user:
        await orm_add_user(
            session,
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=None
        )
        await session.commit()  # Сохраняем изменения после добавления пользователя

    # Проверка наличия фото у продукта
    result = await session.execute(select(Product).where(Product.id == callback_data.product_id))
    product = result.scalar()
    if not product:
        await callback.answer("Товар не найден.")
        return

    # Проверяем наличие фото у товара
    if not product.image:
        media = types.InputMediaPhoto(media="DEFAULT_IMAGE_URL", caption=product.name)  # Стандартное изображение для товаров без фото
    else:
        media = types.InputMediaPhoto(media=product.image, caption=product.name)

    # Добавляем товар в корзину пользователя
    await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id)
    await callback.message.edit_media(media=media, reply_markup=callback.message.reply_markup)
    await callback.answer("Товар добавлен в корзину.")







# Основной обработчик callback-запросов
@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession, state: FSMContext):
    if callback_data.menu_name == "search_products":
        await callback.message.answer("Введите ключевые слова для поиска:")
        await state.set_state(UserSearchProduct.keywords)
        await callback.answer()
        return
    if callback_data.menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session)
        return
    if callback_data.menu_name == "orders":  # Новая кнопка для заказов
        # Выводим заказы пользователя
        orders_text, keyboard = await get_user_orders(session, callback.from_user.id)
        await callback.message.answer(orders_text, reply_markup=keyboard)
        await callback.answer()
        return

    # Получаем содержимое меню
    media, reply_markup = await get_menu_content(
        session,
        level=callback_data.level,
        menu_name=callback_data.menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_id=callback.from_user.id,
    )

    # Проверка наличия данных для отправки
    if media:  # Проверяем, есть ли текст или медиа для отправки
        text_to_send = media  # Если есть текст, используем его
    else:
        text_to_send = "Нет данных для отображения"  # Если нет текста, отправляем заглушку

    # Проверка на изменение содержимого
    if isinstance(media, types.InputMediaPhoto):
        # Если изображение есть
        if callback.message.photo and callback.message.caption == media.caption and callback.message.reply_markup == reply_markup:
            await callback.answer("Контент не изменился.")
            return
        # Обновляем фото, если есть изменения
        await callback.message.edit_media(media=media, reply_markup=reply_markup)

    elif isinstance(media, str):
        # Если изображения нет, обновляем только текст
        if callback.message.text == media and callback.message.reply_markup == reply_markup:
            await callback.answer("Контент не изменился.")
            return
        # Обновляем только текст, без изображений
        await callback.message.edit_text(text=text_to_send, reply_markup=reply_markup)

    else:
        await callback.message.answer("Произошла ошибка при загрузке контента.")

    await callback.answer()






# FSM для поиска товаров
class UserSearchProduct(StatesGroup):
    keywords = State()


# Обработка кнопки "Поиск"
@user_private_router.callback_query(F.data == 'search')
async def start_search(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ключевые слова для поиска:")
    await state.set_state(UserSearchProduct.keywords)
    await callback.answer()




# Обработчик поиска товаров
@user_private_router.message(UserSearchProduct.keywords, F.text)
async def search_products(message: types.Message, session: AsyncSession, state: FSMContext):
    search_query = message.text.strip()  # Извлекаем текст запроса
    page = 1  # Начальная страница
    per_page = 5  # Количество товаров на странице

    try:
        # Получаем список товаров и общее количество
        products, total_count = await orm_get_products_by_keywords(session, search_query, page, per_page)

        if not products:
            await message.answer("Товары не найдены.")
            await state.clear()
            return

        # Пагинация
        total_pages = (total_count + per_page - 1) // per_page  # Количество страниц
        pagination_info = f"Найдено {total_count} товаров. Страница {page} из {total_pages}."

        # Отправка найденных товаров с кнопками
        for product in products:
            caption = (
                f"<b>{product.name}</b>\n"
                f"Артикул: {product.sku}\n"
                f"{product.description}\n"
                f"Цена: {round(product.price, 2)} ₽\n"
                f"В наличии: {product.stock} шт.\n"
            )

            if product.image:
                await message.answer_photo(
                    product.image,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=get_user_products_btns(
                        product_id=product.id,
                        category_id=product.category_id
                    )
                )
            else:
                await message.answer(
                    text=caption,
                    parse_mode='HTML',
                    reply_markup=get_user_products_btns(
                        product_id=product.id,
                        category_id=product.category_id
                    )
                )

        # Кнопки пагинации
        pagination_btns = []
        if page < total_pages:
            pagination_btns.append(InlineKeyboardButton(
                text="След. ▶",
                callback_data=f"search_{search_query}_{page + 1}"
            ))

        if pagination_btns:
            await message.answer(
                text=pagination_info,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[pagination_btns])
            )

        await state.clear()

    except Exception as e:
        print(f"Ошибка при выполнении запроса: {e}")
        await message.answer("Произошла ошибка при загрузке товаров.")





@user_private_router.callback_query(F.data.startswith('search_'))
async def search_pagination(callback: types.CallbackQuery, session: AsyncSession):
    try:
        # Получаем данные из callback_data
        data = callback.data.split('_')
        search_query = data[1]
        page = int(data[2])  # Извлекаем номер страницы из callback_data

        # Получаем список товаров и общее количество
        products, total_count = await orm_get_products_by_keywords(session, search_query, page=page)

        if not products:
            await callback.message.answer("Товары не найдены.")
            return

        # Отправка найденных товаров
        for product in products:
            if product.image:
                await callback.message.answer_photo(
                    product.image,
                    caption=(
                        f"<b>{product.name}</b>\n"
                        f"Артикул: {product.sku}\n"
                        f"{product.description}\n"
                        f"Цена: {round(product.price, 2)} ₽\n"
                        f"В наличии: {product.stock} шт.\n"
                    ),
                    parse_mode='HTML',
                    reply_markup=get_user_products_btns(
                        product_id=product.id,
                        category_id=product.category_id
                    )
                )
            else:
                await callback.message.answer(
                    text=(
                        f"<b>{product.name}</b>\n"
                        f"Артикул: {product.sku}\n"
                        f"{product.description}\n"
                        f"Цена: {round(product.price, 2)} ₽\n"
                        f"В наличии: {product.stock} шт.\n"
                    ),
                    parse_mode='HTML',
                    reply_markup=get_user_products_btns(
                        product_id=product.id,
                        category_id=product.category_id
                    )
                )

        # Получаем общее количество товаров и страниц
        total_pages = (total_count + 4) // 5  # Общее количество страниц
        pagination_info = f"Найдено {total_count} товаров. Страница {page} из {total_pages}."

        # Создаем кнопки пагинации
        pagination_btns = []
        if page > 1:
            pagination_btns.append(InlineKeyboardButton(
                text="◀ Пред.",
                callback_data=f"search_{search_query}_{page - 1}"
            ))
        if page < total_pages:
            pagination_btns.append(InlineKeyboardButton(
                text="След. ▶",
                callback_data=f"search_{search_query}_{page + 1}"
            ))

        if pagination_btns:
            await callback.message.answer(
                text=pagination_info,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[pagination_btns])
            )

        await callback.answer()

    except Exception as e:
        print(f"Ошибка при пагинации: {e}")
        await callback.answer("Произошла ошибка при загрузке товаров.")





# Функция для добавления товара в корзину по нажатию "Купить"
@user_private_router.callback_query(F.data.startswith('buy_'))
async def buy_product(callback: types.CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split('_')[1])
    user_id = callback.from_user.id

    # Попытка добавить товар в корзину
    result = await orm_add_to_cart(session, user_id=user_id, product_id=product_id)

    # Обработка результата
    if result:
        await callback.answer("Товар добавлен в корзину.")
    else:
        await callback.answer("Не удалось добавить товар. Возможно, товар закончился или пользователь не добавлен.")


# Обработчик для кнопки "На главную 🏠"
@user_private_router.callback_query(F.data == "main_menu")
async def go_to_main_menu(callback: types.CallbackQuery, session: AsyncSession):
    # Возвращаем пользователя в главное меню
    media, reply_markup = await get_menu_content(session, level=0, menu_name='main')
    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer("Вы вернулись в главное меню.")


@user_private_router.message(F.text == "Заказать")
async def create_order(message: types.Message, session: AsyncSession, user_id: int):
    # Создаём заказ на основе данных из корзины
    cart_items = await orm_get_user_carts(session, user_id)
    if not cart_items:
        await message.answer("Ваша корзина пуста!")
        return

    # Создаем заказ
    order_number = random.randint(100000, 999999)  # Генерация номера заказа
    order = await create_order_from_cart(session, user_id, cart_items, order_number)

    # Уведомляем пользователя
    await message.answer(f"Ваш заказ №{order_number} успешно создан! Ожидайте обновления статуса.")

    # Очищаем корзину
    await orm_clear_user_cart(session, user_id)


@user_private_router.message(F.text == "Заказы 📝")
async def show_user_orders(message: types.Message, session: AsyncSession, user_id: int):
    orders = await get_user_orders(session, user_id)  # Получаем все заказы пользователя
    if not orders:
        await message.answer("У вас нет заказов.")
        return

    # Перебираем все заказы
    for order in orders:
        created_time = order.created.strftime("%d.%m.%Y %H:%M")  # Форматируем дату и время
        order_text = (
            f"Заказ №{order.order_number}\n"
            f"Дата и время заказа: {created_time}\n"  # Дата и время заказа
            f"Статус: {order.status}\n"
            f"Общая стоимость: {order.total_cost:.2f} ₽\n"
        )

        # Перечисляем товары в заказе
        for item in order.items:
            product = item.product
            order_text += f"  - {product.name} (Количество: {item.stock}, Цена: {item.price:.2f} ₽)\n"
        order_text += "\n"

        # Кнопки для взаимодействия с заказом
        buttons = [
            InlineKeyboardButton(text="На главную 🏠", callback_data="main_menu"),
            InlineKeyboardButton(text="Удалить", callback_data=f"delete_order_{order.id}")
        ]

        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [buttons[0], buttons[1]],  # Два столбца кнопок
            ],
            resize_keyboard=True,  # Кнопки будут адаптироваться по размеру
            one_time_keyboard=True  # После нажатия скрываются
        )

        # Отправляем сообщение с заказом и клавиатурой
        await message.answer(order_text, reply_markup=keyboard)







@user_private_router.callback_query(F.data == "order")
async def handle_create_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    user_id = callback.from_user.id
    # Передаем bot в функцию create_order_from_cart
    order = await create_order_from_cart(session, user_id, bot)

    if order:
        await callback.message.answer(
            f"Ваш заказ #{order.order_number} успешно создан и находится в обработке.",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("На главную 🏠", callback_data="main_menu"))
        )
    else:
        await callback.message.answer("Ваша корзина пуста.")
    await callback.answer()


@user_private_router.callback_query(F.data == "view_orders")
async def handle_view_orders(callback: types.CallbackQuery, session: AsyncSession):
    orders_text, keyboard = await get_user_orders(session, callback.from_user.id)
    if orders_text:
        await callback.message.answer(orders_text, reply_markup=keyboard)
    else:
        await callback.message.answer("У вас нет активных заказов.")
    await callback.answer()


@user_private_router.message(Command("orders"))
async def handle_user_orders(message: types.Message, session: AsyncSession, user: User):
    # Получаем заказы пользователя из базы данных
    orders = await get_user_orders(session, user.id)

    if not orders:
        await message.answer("У вас нет заказов.")
        return

    for order in orders:
        created_time = order.created.strftime("%d.%m.%Y %H:%M")  # Форматируем дату и время
        order_text = (
            f"Заказ №{order.order_number}\n"
            f"Дата и время заказа: {created_time}\n"  # Добавлено отображение даты и времени
            f"Статус: {order.status}\n"
            f"Общая стоимость: {order.total_cost:.2f} ₽\n"
        )
        for item in order.items:
            product = item.product
            order_text += f"  - {product.name} (Количество: {item.stock}, Цена: {item.price:.2f} ₽)\n"
        order_text += "\n"
        await message.answer(order_text)



# Обработчик для кнопки "Удалить"
@user_private_router.callback_query(F.data.startswith("delete_order_"))
async def handle_delete_order(callback: types.CallbackQuery, session: AsyncSession):
    # Извлекаем ID заказа из callback_data
    order_id = int(callback.data.split("_")[-1])

    # Проверяем, существует ли заказ и принадлежит ли он пользователю
    order = await session.get(Order, order_id)
    if not order or order.user_id != callback.from_user.id:
        await callback.answer("Ошибка: Заказ не найден или недоступен для удаления.", show_alert=True)
        return

    # Удаляем заказ и коммитим изменения
    try:
        await session.delete(order)
        await session.commit()
        await callback.answer("Заказ успешно удален.")
        await callback.message.delete()  # Удаляем сообщение с заказом после удаления
    except Exception as e:
        await session.rollback()
        logging.error(f"Ошибка при удалении заказа {order_id}: {e}")
        await callback.answer("Произошла ошибка при удалении заказа. Попробуйте еще раз.", show_alert=True)
