from aiogram.utils.formatting import Bold, as_list, as_marked_section


categories = ['UAG', 'UNIQ', 'SATECHI', 'SAMSUNG', 'PITAKA', 'NOMAD', 'KARL LAGERFELD', 'APPLE', 'APPLE-REMESHOK', 'DYSON', 'ANKER', 'SPIGEN']

description_for_info_pages = {
    "main": "Добро пожаловать!",
    "about": "CITY_GADGETS \nРежим работы - 10:00 - 19:00.",
    "payment": as_marked_section(
        Bold("Варианты оплаты:"),
        "При получении кеш",
        marker="✅ ",
    ).as_html(),
    "shipping": as_list(
        as_marked_section(
            Bold("Варианты доставки/заказа:"),
            "Курьер",
            "Самовынос (сейчас прибегу заберу)",
            marker="✅ ",
        ),
        as_marked_section(Bold("Нельзя:"), "Почта", "Голуби", marker="❌ "),
        sep="\n----------------------\n",
    ).as_html(),
    'catalog': 'Категории:',
    'cart': 'В корзине ничего нет!'
}