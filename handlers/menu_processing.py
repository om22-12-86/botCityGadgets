from aiogram.types import InputMediaPhoto
from sqlalchemy.ext.asyncio import AsyncSession
import requests

# Импортируем необходимые функции для работы с базой данных из orm_query
from database.orm_query import (
    orm_add_to_cart,
    orm_delete_from_cart,
    orm_get_banner,
    orm_get_categories,
    orm_get_products,
    orm_get_user_carts,
    orm_reduce_product_in_cart,
)

# Импортируем функции для создания inline-клавиатур
from kbds.inline import (
    get_products_btns,
    get_user_cart,
    get_user_catalog_btns,
    get_user_main_btns,
)

# Импортируем класс для работы с пагинацией (разбиение на страницы)
from utils.paginator import Paginator


# Функция отображения главного меню
async def main_menu(session: AsyncSession, level: int, menu_name: str):
    banner = await orm_get_banner(session, menu_name)
    image = InputMediaPhoto(media=banner.image, caption=banner.description)
    kbds = get_user_main_btns(level=level)
    return image, kbds


# Функция для отображения каталога категорий товаров
async def catalog(session: AsyncSession, level: int, menu_name: str):
    banner = await orm_get_banner(session, menu_name)
    image = InputMediaPhoto(media=banner.image, caption=banner.description)

    categories = await orm_get_categories(session)

    if not categories:
        print(f"No categories found for menu: {menu_name}")
        # Если нет категорий, отправьте сообщение пользователю
        return image, InlineKeyboardMarkup().add(
            InlineKeyboardButton(text="Категории отсутствуют", callback_data="no_categories"))

    # Если категории есть, создаём кнопки
    kbds = get_user_catalog_btns(level=level, categories=categories)
    return image, kbds



# Функция для создания кнопок пагинации
def pages(paginator: Paginator):
    btns = dict()
    if paginator.has_previous():  # Если есть предыдущая страница
        btns["◀ Пред."] = "previous"
    if paginator.has_next():  # Если есть следующая страница
        btns["След. ▶"] = "next"
    return btns


# Функция для отображения списка товаров в категории
async def products(session: AsyncSession, level: int, category: int, page: int):
    products = await orm_get_products(session, category_id=category)
    paginator = Paginator(products, page=page)
    product = paginator.get_page()[0]

    image = InputMediaPhoto(
        media=product.image,
        caption=f"<b>{product.name}</b>\n"
                f"{product.description}\n"
                f"Стоимость: {round(product.price, 2)} ₽\n"
                f"В наличии: {product.stock} шт.\n"  # Отображаем количество товара на складе
                f"<b>Товар {paginator.page} из {paginator.pages}</b>",
        parse_mode='HTML'
    )

    pagination_btns = pages(paginator)
    kbds = get_products_btns(
        level=level,
        category=category,
        page=page,
        pagination_btns=pagination_btns,
        product_id=product.id,
    )
    return image, kbds




# Функция для работы с корзиной товаров
# admin_private.py

async def carts(session: AsyncSession, level: int, menu_name: str, page: int, user_id: int, product_id: int | None):
    # Действия при удалении товара из корзины
    if menu_name == "delete":
        await orm_delete_from_cart(session, user_id, product_id)
        if page > 1:
            page -= 1
    # Действия при уменьшении количества товара
    elif menu_name == "decrement":
        await orm_reduce_product_in_cart(session, user_id, product_id)
        if page > 1:
            page -= 1
    # Действия при увеличении количества товара
    elif menu_name == "increment":
        added = await orm_add_to_cart(session, user_id, product_id)
        if not added:
            # Отправить сообщение о том, что товара недостаточно
            print(f"Недостаточно товара на складе для продукта ID: {product_id}")

    # Получаем корзину пользователя
    carts = await orm_get_user_carts(session, user_id)

    if not carts:
        banner = await orm_get_banner(session, "cart")
        image = InputMediaPhoto(
            media=banner.image, caption=f"<b>{banner.description}</b>", parse_mode='HTML'
        )
        kbds = get_user_cart(level=level, page=None, pagination_btns=None, product_id=None)
    else:
        paginator = Paginator(carts, page=page)
        cart = paginator.get_page()[0]

        cart_price = round(cart.stock * cart.product.price, 2)
        total_price = round(
            sum(cart.stock * cart.product.price for cart in carts), 2
        )

        image = InputMediaPhoto(
            media=cart.product.image,
            caption=f"<b>{cart.product.name}</b>\n"
                    f"{cart.product.price}₽ x {cart.stock} = {cart_price}₽\n"
                    f"Товар {paginator.page} из {paginator.pages} в корзине.\n"
                    f"Общая стоимость товаров в корзине {total_price}₽",
            parse_mode='HTML'
        )

        pagination_btns = pages(paginator)
        kbds = get_user_cart(
            level=level,
            page=page,
            pagination_btns=pagination_btns,
            product_id=cart.product.id,
        )
    return image, kbds





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
        # Проверка, что категория не None
        if category is None:
            print(f"category_id is None in get_menu_content for level {level}")
            raise ValueError("category_id не может быть None")
        return await products(session, level, category, page)
    elif level == 3:
        return await carts(session, level, menu_name, page, user_id, product_id)
