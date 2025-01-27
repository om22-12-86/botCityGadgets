from aiogram.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote, unquote


# Импортируем необходимые функции для работы с базой данных из orm_query
from database.orm_query import (
    create_order_from_cart,
    get_user_orders,
    orm_add_to_cart,
    orm_delete_from_cart,
    orm_get_banner,
    orm_get_categories,
    orm_get_products,
    orm_get_user_carts,
    orm_reduce_product_in_cart
)

# Импортируем функции для создания inline-клавиатур
from kbds.inline import (
get_user_products_btns,
    get_products_btns,
    get_user_cart,
    get_user_catalog_btns,
    get_user_main_btns
)

# Импортируем класс для работы с пагинацией (разбиение на страницы)
from utils.paginator import Paginator


# Функция отображения главного меню
async def main_menu(session: AsyncSession, level: int, menu_name: str):
    banner = await orm_get_banner(session, menu_name)

    if not banner.image or not banner.description:
        print(f"Баннер для '{menu_name}' не содержит изображение или описание. Используются стандартные значения.")
        banner.image = "DEFAULT_IMAGE_URL"
        banner.description = "Стандартное описание"

    image = InputMediaPhoto(media=banner.image, caption=banner.description)
    kbds = get_user_main_btns(level=level)
    return image, kbds


# Функция для отображения каталога категорий товаров
async def catalog(session: AsyncSession, level: int, menu_name: str):
    banner = await orm_get_banner(session, menu_name)
    image = InputMediaPhoto(media=banner.image, caption=banner.description)

    categories = await orm_get_categories(session)

    # Проверяем, есть ли категории
    if not categories:
        print(f"No categories found for menu: {menu_name}")
        return image, InlineKeyboardMarkup().add(
            InlineKeyboardButton(text="Категории отсутствуют", callback_data="no_categories")
        )

    # Создаем inline-клавиатуру с категориями
    kbds = get_user_catalog_btns(level=level, categories=categories)
    return image, kbds


# Функция для создания кнопок пагинации
def pages(paginator: Paginator):
    btns = {}
    if paginator.has_previous():
        btns["◀ Пред."] = "previous"
    if paginator.has_next():
        btns["След. ▶"] = "next"
    return btns


# Функция для отображения списка товаров в категории
async def products(session: AsyncSession, level: int, category: int, page: int):
    products = await orm_get_products(session, category_id=category)
    print(f"Товары в категории {category}: {products}")  # Добавьте лог
    if not products:
        print(f"Нет товаров в категории {category}")

    paginator = Paginator(products, page=page)

    # Получаем товары на текущей странице
    page_products = paginator.get_page()

    # Проверяем, если нет товаров, отправляем соответствующее сообщение
    if not page_products:
        print(f"Товары в категории {category} не найдены.")
        return None, None  # Возвращаем None, если товаров нет

    # Получаем первый товар на странице
    product = page_products[0]

    # Проверяем, есть ли изображение
    if product.image:
        # Если изображение есть, используем InputMediaPhoto
        image = InputMediaPhoto(
            media=product.image,
            caption=(
                f"<b>{product.name}</b>\n"
                f"Артикул: {product.sku}\n"
                f"{product.description}\n"
                f"Стоимость: {round(product.price, 2)} ₽\n"
                f"В наличии: {product.stock} шт.\n"
                f"<b>Товар {paginator.page} из {paginator.pages}</b>"
            ),
            parse_mode='HTML'
        )
    else:
        # Если изображения нет, отправляем только описание товара
        image = (
            f"<b>{product.name}</b>\n"
            f"Артикул: {product.sku}\n"
            f"{product.description}\n"
            f"Стоимость: {round(product.price, 2)} ₽\n"
            f"В наличии: {product.stock} шт.\n"
            f"<b>Товар {paginator.page} из {paginator.pages}</b>"
        )

    pagination_btns = pages(paginator)
    kbds = get_user_products_btns(
        product_id=product.id,
        category_id=category,  # Меняем category на category_id
        paginator=paginator,
        page=page,
        level=level,
        sizes=(2, 1)
    )

    return image, kbds





## Функция для работы с корзиной товаров
async def carts(session: AsyncSession, level: int, menu_name: str, page: int, user_id: int, product_id: int | None):
    if menu_name == "delete":
        await orm_delete_from_cart(session, user_id, product_id)
        if page > 1:
            page -= 1
    elif menu_name == "decrement":
        await orm_reduce_product_in_cart(session, user_id, product_id)
        if page > 1:
            page -= 1
    elif menu_name == "increment":
        added = await orm_add_to_cart(session, user_id, product_id)
        if not added:
            print(f"Недостаточно товара на складе для продукта ID: {product_id}")

    carts = await orm_get_user_carts(session, user_id)

    # Проверяем, есть ли товары в корзине
    if not carts:
        banner = await orm_get_banner(session, "cart")
        image = InputMediaPhoto(
            media=banner.image, caption=f"<b>{banner.description}</b>", parse_mode='HTML'
        )
        kbds = get_user_cart(level=level, page=None, pagination_btns=None, product_id=None)
    else:
        paginator = Paginator(carts, page=page)
        cart = paginator.get_page()[0]

        # Получаем продукт из объекта корзины
        product = cart.product  # Здесь cart.product используется для доступа к продукту

        cart_price = round(cart.stock * product.price, 2)
        total_price = round(sum(item.stock * item.product.price for item in carts), 2)

        # Проверка на наличие изображения
        if product.image:
            # Если есть изображение, используем InputMediaPhoto
            image = InputMediaPhoto(
                media=product.image,
                caption=(
                    f"<b>{product.name}</b>\n"
                    f"Артикул: {product.sku}\n"
                    f"{product.description}\n"
                    f"Цена: {product.price}₽ x {cart.stock} = {cart_price}₽\n"
                    f"Товар {paginator.page} из {paginator.pages} в корзине.\n"
                    f"Общая стоимость товаров в корзине {total_price}₽"
                ),
                parse_mode='HTML'
            )
        else:
            # Если изображения нет, создаем только текстовое описание
            caption = (
                f"<b>{product.name}</b>\n"
                f"Артикул: {product.sku}\n"
                f"{product.description}\n"
                f"Цена: {product.price}₽ x {cart.stock} = {cart_price}₽\n"
                f"Товар {paginator.page} из {paginator.pages} в корзине.\n"
                f"Общая стоимость товаров в корзине {total_price}₽"
            )
            image = caption  # Просто текст без изображения

        pagination_btns = pages(paginator)
        kbds = get_user_cart(
            level=level,
            page=page,
            pagination_btns=pagination_btns,
            product_id=product.id,
        )

    return image, kbds






async def get_banner(session: AsyncSession, banner_name: str):
    from database.models import Banner  # Обратите внимание, что этот импорт должен быть корректным

    # Получаем баннер по имени
    query = select(Banner).where(Banner.name == banner_name)
    result = await session.execute(query)
    banner = result.scalar_one_or_none()

    if not banner:
        print(f"Баннер с именем {banner_name} не найден.")

    return banner





async def user_orders(session, user_id, message):
    # Получаем заказы пользователя
    orders = await get_user_orders(session, user_id)
    if not orders:
        await message.answer("У вас пока нет заказов.")
        return

    orders_text = "Ваши заказы:\n"
    for order in orders:
        created_time = order.created.strftime("%d.%m.%Y %H:%M")  # Форматируем дату и время
        orders_text += (
            f"Номер: {order.order_number}\n"
            f"Дата и время заказа: {created_time}\n"
            f"Товары:\n"
        )
        for item in order.items:
            orders_text += f"{item.product.name} - {item.stock} шт.\n"
        orders_text += f"Сумма: {sum([item.stock * item.price for item in order.items]):.2f} ₽\nСтатус: {order.status}\n\n"

        # Кнопки для взаимодействия с заказом
        buttons = [
            InlineKeyboardButton(text="На главную 🏠", callback_data="main_menu"),
            InlineKeyboardButton(text="Удалить", callback_data=f"delete_order_{order.id}")
        ]

        # Создаем клавиатуру с кнопками под каждым заказом
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [buttons[0], buttons[1]],  # Два столбика
            ],
            resize_keyboard=True,  # Уменьшаем размер кнопок
            one_time_keyboard=True  # Скрываем клавиатуру после выбора
        )

        # Отправляем информацию о заказе с клавиатурой
        await message.answer(orders_text, reply_markup=keyboard)





# Основная функция для обработки меню
async def get_menu_content(
        session: AsyncSession,
        level: int,
        menu_name: str,
        category: int | None = None,
        page: int | None = None,
        product_id: int | None = None,
        user_id: int | None = None,
):
    if level == 0:
        return await main_menu(session, level, menu_name)
    elif level == 1:
        return await catalog(session, level, menu_name)
    elif level == 2:
        if category is None:
            print(f"category_id is None in get_menu_content for level {level}")
            raise ValueError("category_id не может быть None")
        return await products(session, level, category, page)
    elif level == 3:
        return await carts(session, level, menu_name, page, user_id, product_id)
    elif level == 4 and menu_name == "orders":
        # Обрабатываем запрос на просмотр заказов для уровня 4
        orders_text, keyboard = await user_orders(session, user_id)
        return orders_text, keyboard
    else:
        raise ValueError(f"Unsupported menu level: {level}")
