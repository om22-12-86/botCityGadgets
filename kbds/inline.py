from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types


class MenuCallBack(CallbackData, prefix="menu"):
    level: int
    menu_name: str
    category: int | None = None
    page: int = 1
    product_id: int | None = None




# Функция для создания кнопок с учетом пагинации
def get_product_buttons(category_id, product_id, pagination_btns, current_page):
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="Удалить", callback_data=f"delete_{product_id}"))
    keyboard.add(InlineKeyboardButton(text="Изменить", callback_data=f"change_{product_id}"))

    # Добавляем кнопки пагинации, если они есть
    for text, callback_data in pagination_btns.items():
        keyboard.add(InlineKeyboardButton(text=text, callback_data=callback_data))

    return keyboard.adjust(2).as_markup()








def get_user_main_btns(*, level: int, sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()
    btns = {
        "Товары 📦": "catalog",
        "Корзина 🛒": "cart",
        "О нас ℹ️": "about",
        "Оплата 💵": "payment",
        "Доставка 🚚": "shipping",
        "Заказы 📝": "order"  # Новая кнопка для отображения заказов
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

# Функция для создания кнопок для найденных товаров
def get_user_products_btns(product_id: int, level: int = 2, sizes=(2, 1)):
    keyboard = InlineKeyboardBuilder()

    # Добавляем кнопку "Назад"
    keyboard.add(InlineKeyboardButton(
        text="Назад",
        callback_data=MenuCallBack(level=level - 1, menu_name="catalog").pack()
    ))

    # Добавляем кнопку "Корзина"
    keyboard.add(InlineKeyboardButton(
        text="Корзина 🛒",
        callback_data=MenuCallBack(level=3, menu_name="cart").pack()
    ))

    # Добавляем кнопку "Купить"
    keyboard.add(InlineKeyboardButton(
        text="Купить 💵",
        callback_data=MenuCallBack(level=level, menu_name="add_to_cart", product_id=product_id).pack()
    ))

    # Устанавливаем размеры кнопок
    keyboard.adjust(*sizes)

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





# Функция для создания кнопок "Назад", "Корзина", "Купить"
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
#
# def get_product_buttons(category_id: int, product_id: int):
#     """
#     Функция для создания клавиатуры с кнопками для продукта.
#     :param category_id: ID категории, из которой был выбран товар
#     :param product_id: ID продукта
#     :return: InlineKeyboardMarkup с кнопками
#     """
#     keyboard = []
#
#     # Кнопка "Главное меню"
#     keyboard.append([InlineKeyboardButton(text="Главное меню", callback_data="main_menu")])
#
#     # Добавляем кнопки "Корзина" и "Купить"
#     keyboard.append([InlineKeyboardButton(text="Корзина 🛒", callback_data="cart_view")])
#     keyboard.append([InlineKeyboardButton(text="Купить 💵", callback_data=f"buy_{product_id}")])
#
#     return InlineKeyboardMarkup(inline_keyboard=keyboard)




def get_callback_btns(*, btns: dict[str, str], sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()

    for text, data in btns.items():
        keyboard.add(InlineKeyboardButton(text=text, callback_data=data))

    return keyboard.adjust(*sizes).as_markup()
