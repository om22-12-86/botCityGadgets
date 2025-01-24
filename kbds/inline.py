from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types
from utils.paginator import Paginator


class MenuCallBack(CallbackData, prefix="menu"):
    level: int
    menu_name: str
    category: int | None = None
    page: int = 1
    product_id: int | None = None




def get_product_buttons(category_id, product_id, pagination_btns, current_page):
    # Кнопки для удаления и изменения товара (для админа)
    inline_keyboard = [
        [
            InlineKeyboardButton(text="Удалить", callback_data=f"admin_delete_{product_id}"),
            InlineKeyboardButton(text="Изменить", callback_data=f"admin_change_{product_id}")
        ]
    ]

    # Добавляем кнопки пагинации
    pagination_buttons = [
        InlineKeyboardButton(
            text=text,
            callback_data=(
                f"category_{category_id}_{current_page - 1}" if text == "◀ Пред." else
                f"category_{category_id}_{current_page + 1}" if text == "След. ▶" else callback_data
            )
        )
        for text, callback_data in pagination_btns.items()
    ]

    # Если есть кнопки пагинации, добавляем их в клавиатуру
    if pagination_buttons:
        inline_keyboard.append(pagination_buttons)

    # Создаем и возвращаем клавиатуру
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard, row_width=2)












def get_user_main_btns(*, level: int, sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()
    btns = {
        "Товары 📦": "catalog",
        "Корзина 🛒": "cart",
        "О нас ℹ️": "about",
        "Оплата 💵": "payment",
        "Доставка 🚚": "shipping",
        "Заказы 📝": "orders"  # Новая кнопка для отображения заказов
    }
    for text, menu_name in btns.items():
        if menu_name == 'catalog':
            keyboard.add(InlineKeyboardButton(text=text,
                                              callback_data=MenuCallBack(level=level + 1, menu_name=menu_name).pack()))
        elif menu_name == 'cart':
            keyboard.add(InlineKeyboardButton(text=text,
                                              callback_data=MenuCallBack(level=3, menu_name=menu_name).pack()))
        else:
            keyboard.add(InlineKeyboardButton(text=text,
                                              callback_data=MenuCallBack(level=level, menu_name=menu_name).pack()))

    return keyboard.adjust(*sizes).as_markup()



def get_user_catalog_btns(*, level: int, categories: list, sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()

    # Цикл для добавления кнопок с категориями товаров
    for c in categories:
        keyboard.add(InlineKeyboardButton(
            text=c.name,
            callback_data=MenuCallBack(level=level + 1, menu_name=c.name,
                                       category=c.id).pack()))  # Здесь c.id должно быть корректным


    # Кнопки назад и корзина
    keyboard.add(InlineKeyboardButton(text='Назад',
                                      callback_data=MenuCallBack(level=level - 1, menu_name='main').pack()))
    keyboard.add(InlineKeyboardButton(text='Корзина 🛒',
                                      callback_data=MenuCallBack(level=3, menu_name='cart').pack()))
    # Кнопка поиска товаров
    keyboard.add(InlineKeyboardButton(text='Поиск 🔍',
                                      callback_data=MenuCallBack(level=level + 1, menu_name='search_products').pack()))


    return keyboard.adjust(*sizes).as_markup()



# Функция для создания кнопок для найденных товаров с пагинацией
def get_user_products_btns(
        product_id, category_id, paginator=None, page=1, level=2, sizes=(2, 1)
):
    # Инициализируем объект клавиатуры
    keyboard = InlineKeyboardBuilder()

    # Добавляем кнопку "Назад", которая переводит пользователя в каталог
    keyboard.add(InlineKeyboardButton(
        text="Назад",
        callback_data=MenuCallBack(level=level - 1, menu_name='catalog', category=category_id).pack()
    ))

    # Добавляем кнопку для перехода в корзину
    keyboard.add(InlineKeyboardButton(
        text="Корзина 🛒",
        callback_data=MenuCallBack(level=3, menu_name='cart').pack()
    ))

    # Добавляем кнопку "Купить"
    keyboard.add(InlineKeyboardButton(
        text="Купить 💵",
        callback_data=MenuCallBack(level=level, menu_name='add_to_cart', product_id=product_id).pack()
    ))

    # Разделение строк для кнопок
    keyboard.adjust(*sizes)

    # Если paginator не None, добавляем кнопки пагинации
    if paginator:
        row = []
        if paginator.has_previous():
            row.append(InlineKeyboardButton(
                text="◀ Пред. Стр.",
                callback_data=f"search_{category_id}_{paginator.page - 1}"  # Передаем текущий запрос и номер страницы
            ))
        if paginator.has_next():
            row.append(InlineKeyboardButton(
                text="След. Стр. ▶",
                callback_data=f"search_{category_id}_{paginator.page + 1}"  # Передаем текущий запрос и номер страницы
            ))

        # Добавляем кнопки пагинации в клавиатуру
        if row:
            keyboard.row(*row)

    return keyboard.as_markup()








def get_products_btns(
        *,
        level: int,
        category: int,
        page: int,
        pagination_btns: dict,
        product_id: int,
        sizes: tuple[int] = (2, 1)
):
    keyboard = InlineKeyboardBuilder()

    keyboard.add(InlineKeyboardButton(text='Назад',
                                      callback_data=MenuCallBack(level=level - 1, menu_name='catalog').pack()))
    keyboard.add(InlineKeyboardButton(text='Корзина 🛒',
                                      callback_data=MenuCallBack(level=3, menu_name='cart').pack()))
    keyboard.add(InlineKeyboardButton(text='Купить 💵',
                                      callback_data=MenuCallBack(level=level, menu_name='add_to_cart',
                                                                 product_id=product_id).pack()))

    keyboard.adjust(*sizes)

    row = []
    for text, menu_name in pagination_btns.items():
        if menu_name == "next":
            row.append(InlineKeyboardButton(text=text,
                                            callback_data=MenuCallBack(
                                                level=level,
                                                menu_name=menu_name,
                                                category=category,
                                                page=page + 1).pack()))

        elif menu_name == "previous":
            row.append(InlineKeyboardButton(text=text,
                                            callback_data=MenuCallBack(
                                                level=level,
                                                menu_name=menu_name,
                                                category=category,
                                                page=page - 1).pack()))

    return keyboard.row(*row).as_markup()


def get_user_cart(
        *,
        level: int,
        page: int | None,
        pagination_btns: dict | None,
        product_id: int | None,
        sizes: tuple[int] = (3,)
):
    keyboard = InlineKeyboardBuilder()
    if page:
        keyboard.add(InlineKeyboardButton(text='Удалить',
                                          callback_data=MenuCallBack(level=level, menu_name='delete',
                                                                     product_id=product_id, page=page).pack()))
        keyboard.add(InlineKeyboardButton(text='-1',
                                          callback_data=MenuCallBack(level=level, menu_name='decrement',
                                                                     product_id=product_id, page=page).pack()))
        keyboard.add(InlineKeyboardButton(text='+1',
                                          callback_data=MenuCallBack(level=level, menu_name='increment',
                                                                     product_id=product_id, page=page).pack()))

        keyboard.adjust(*sizes)

        row = []
        for text, menu_name in pagination_btns.items():
            if menu_name == "next":
                row.append(InlineKeyboardButton(text=text,
                                                callback_data=MenuCallBack(level=level, menu_name=menu_name,
                                                                           page=page + 1).pack()))
            elif menu_name == "previous":
                row.append(InlineKeyboardButton(text=text,
                                                callback_data=MenuCallBack(level=level, menu_name=menu_name,
                                                                           page=page - 1).pack()))

        keyboard.row(*row)

        row2 = [
            InlineKeyboardButton(text='На главную 🏠',
                                 callback_data=MenuCallBack(level=0, menu_name='main').pack()),
            InlineKeyboardButton(text='Заказать☝🏻',
                                 callback_data="order"),
        ]
        return keyboard.row(*row2).as_markup()
    else:
        keyboard.add(
            InlineKeyboardButton(text='На главную 🏠',
                                 callback_data=MenuCallBack(level=0, menu_name='main').pack()))

        return keyboard.adjust(*sizes).as_markup()


# Генерация кнопок для каждого заказа
async def generate_order_buttons(order_id: int) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text="На главную 🏠", callback_data="main_menu"),
        InlineKeyboardButton(text="Удалить", callback_data=f"delete_order_{order_id}")
    ]
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(*buttons)
    return keyboard



def create_status_buttons():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="Выданные", callback_data="view_delivered_orders"),
        InlineKeyboardButton(text="В обработке", callback_data="view_processing_orders"),
        InlineKeyboardButton(text="Готовы к получению", callback_data="view_ready_orders"),
    )
    return keyboard



def get_callback_btns(*, btns: dict[str, str], sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()

    for text, data in btns.items():
        keyboard.add(InlineKeyboardButton(text=text, callback_data=data))

    return keyboard.adjust(*sizes).as_markup()
