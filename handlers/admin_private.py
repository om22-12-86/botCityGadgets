from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.paginator import Paginator
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


from database.orm_query import (
    get_user_by_id,
    update_order_status,
    get_orders,
    orm_change_banner_image,
    orm_get_categories,
    orm_add_product,
    orm_delete_product,
    orm_get_info_pages,
    orm_get_product,
    orm_get_products,
    orm_update_product,
    orm_get_products_by_keywords,
    get_all_orders,
)

from filters.chat_types import ChatTypeFilter, IsAdmin
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard

admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())

# Клавиатура для меню администратора
ADMIN_KB = get_keyboard(
    "Добавить товар",
    "Ассортимент",
    "Добавить/Изменить баннер",
    "Заказы",               # Новая кнопка для работы с заказами
    "Загрузить файл Excel",  # Новая кнопка для загрузки файла Excel
    placeholder="Выберите действие",
    sizes=(2,),
)

# FSM для поиска товаров
class AdminSearchProduct(StatesGroup):
    keywords = State()

@admin_router.message(Command("admin"))
async def admin_features(message: types.Message):
    await message.answer("Что хотите сделать?", reply_markup=ADMIN_KB)


@admin_router.message(F.text == 'Ассортимент')
async def show_products(message: types.Message, session: AsyncSession):
    categories = await orm_get_categories(session)
    btns = {category.name: f'category_{category.id}' for category in categories}
    # Добавляем кнопку "Поиск"
    btns["Поиск"] = 'admin_search'
    await message.answer("Выберите категорию или выполните поиск", reply_markup=get_callback_btns(btns=btns))




# Обработчик для показа товаров в категории
@admin_router.callback_query(F.data.startswith('category_'))
async def show_category_products(callback: types.CallbackQuery, session: AsyncSession):
    data = callback.data.split('_')
    category_id = int(data[1])
    page = int(data[2]) if len(data) > 2 else 1  # Устанавливаем текущую страницу

    products = await orm_get_products(session, category_id)
    paginator = Paginator(products, page=page, per_page=3)
    page_products = paginator.get_page()

    # Определяем кнопки пагинации
    pagination_btns = {}
    if paginator.has_previous():
        pagination_btns["◀ Пред."] = f"category_{category_id}_{paginator.page - 1}"
    if paginator.has_next():
        pagination_btns["След. ▶"] = f"category_{category_id}_{paginator.page + 1}"

    # Проверка значений pagination_btns и current_page для отладки
    print("pagination_btns:", pagination_btns)
    print("current_page:", paginator.page)

    # Отправка товаров с кнопками пагинации
    for product in page_products:
        await callback.message.answer_photo(
            product.image,
            caption=(
                f"<b>{product.name}</b>\n"
                f"Артикул: {product.sku}\n"
                f"{product.description}\n"
                f"Стоимость: {round(product.price, 2)} ₽\n"
                f"В наличии: {product.stock} шт.\n"
                f"<b>Товар {paginator.page} из {paginator.pages}</b>"
            ),
            parse_mode='HTML',
            reply_markup=get_product_buttons(category_id, product.id, pagination_btns, paginator.page)
        )

    await callback.answer("ОК, вот список товаров ⏫")





@admin_router.callback_query(F.data.startswith("delete_"))
async def delete_product_callback(callback: types.CallbackQuery, session: AsyncSession):
    product_id = callback.data.split("_")[-1]
    await orm_delete_product(session, int(product_id))

    await callback.answer("Товар удален")
    await callback.message.answer("Товар удален!")


################# Микро FSM для загрузки/изменения баннеров ############################

class AddBanner(StatesGroup):
    image = State()

@admin_router.message(StateFilter(None), F.text == 'Добавить/Изменить баннер')
async def add_image(message: types.Message, state: FSMContext, session: AsyncSession):
    pages_names = [page.name for page in await orm_get_info_pages(session)]
    await message.answer(f"Отправьте фото баннера.\nВ описании укажите для какой страницы:\n{', '.join(pages_names)}")
    await state.set_state(AddBanner.image)


@admin_router.message(AddBanner.image, F.photo)
async def save_banner_image(message: types.Message, state: FSMContext, session: AsyncSession):
    image_id = message.photo[-1].file_id
    for_page = message.caption.strip() if message.caption else None

    if not for_page:
        await message.answer("Пожалуйста, укажите название страницы в описании к фото.")
        return

    pages_names = [page.name for page in await orm_get_info_pages(session)]
    if for_page not in pages_names:
        await message.answer(f"Введите правильное название страницы, например:\n{', '.join(pages_names)}")
        return

    await orm_change_banner_image(session, for_page, image_id)
    await message.answer("Баннер добавлен/изменен.")
    await state.clear()


@admin_router.message(AddBanner.image)
async def prompt_for_banner_image(message: types.Message, state: FSMContext):
    await message.answer("Отправьте фото баннера или напишите 'отмена'")


#########################################################################################


######################### FSM для добавления/изменения товаров админом ###################

from aiogram.fsm.state import State, StatesGroup

class AddProduct(StatesGroup):
    name = State()
    sku = State()  # Новый стейт для SKU
    description = State()
    category = State()
    price = State()
    image = State()
    stock = State()

    product_for_change = None

    texts = {
        "AddProduct:name": "Введите название товара заново:",
        "AddProduct:sku": "Введите артикул (SKU) заново:",  # Сообщение для sku
        "AddProduct:description": "Введите описание товара заново:",
        "AddProduct:category": "Выберите категорию товара заново ⬆️",
        "AddProduct:price": "Введите стоимость товара заново:",
        "AddProduct:image": "Отправьте фото товара:",
        "AddProduct:stock": "Введите количество товара заново:",
    }



@admin_router.callback_query(StateFilter(None), F.data.startswith("change_"))
async def change_product_callback(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    product_id = callback.data.split("_")[-1]
    product_for_change = await orm_get_product(session, int(product_id))
    AddProduct.product_for_change = product_for_change
    await callback.answer()
    await callback.message.answer("Введите название товара", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AddProduct.name)


@admin_router.message(StateFilter(None), F.text == "Добавить товар")
async def start_adding_product(message: types.Message, state: FSMContext):
    await message.answer("Введите название товара", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AddProduct.name)


@admin_router.message(StateFilter("*"), Command("отмена"))
@admin_router.message(StateFilter("*"), F.text.casefold() == "отмена")
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    if AddProduct.product_for_change:
        AddProduct.product_for_change = None
    await state.clear()
    await message.answer("Действия отменены", reply_markup=ADMIN_KB)


@admin_router.message(StateFilter("*"), Command("назад"))
@admin_router.message(StateFilter("*"), F.text.casefold() == "назад")
async def back_step_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == AddProduct.name:
        await message.answer('Предыдущего шага нет, или введите название товара или напишите "отмена"')
        return

    previous = None
    for step in AddProduct.__all_states__:
        if step.state == current_state:
            await state.set_state(previous)
            await message.answer(f"Ок, вы вернулись к прошлому шагу\n{AddProduct.texts[previous.state]}")
            return
        previous = step


@admin_router.message(AddProduct.name, F.text)
async def add_name(message: types.Message, state: FSMContext):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(name=AddProduct.product_for_change.name)
    else:
        if not (5 <= len(message.text) <= 150):
            await message.answer("Название товара должно быть от 5 до 150 символов. Введите заново.")
            return
        await state.update_data(name=message.text)
    await message.answer("Введите артикул (SKU) товара")
    await state.set_state(AddProduct.sku)



@admin_router.message(AddProduct.sku, F.text)
async def add_sku(message: types.Message, state: FSMContext):
    await state.update_data(sku=message.text)
    await message.answer("Введите описание товара")
    await state.set_state(AddProduct.description)




@admin_router.message(AddProduct.name)
async def prompt_name(message: types.Message, state: FSMContext):
    await message.answer("Введите текст названия товара")


@admin_router.message(AddProduct.description, F.text)
async def add_description(message: types.Message, state: FSMContext, session: AsyncSession):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(description=AddProduct.product_for_change.description)
    else:
        if len(message.text) < 5:
            await message.answer("Слишком короткое описание. Введите заново.")
            return
        await state.update_data(description=message.text)

    categories = await orm_get_categories(session)
    btns = {category.name: str(category.id) for category in categories}
    await message.answer("Выберите категорию", reply_markup=get_callback_btns(btns=btns))
    await state.set_state(AddProduct.category)


@admin_router.message(AddProduct.description)
async def prompt_description(message: types.Message, state: FSMContext):
    await message.answer("Введите текст описания товара")


@admin_router.callback_query(AddProduct.category)
async def category_choice(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    # Получаем id выбранной категории
    category_id = int(callback.data)

    # Получаем список допустимых категорий
    valid_categories = [category.id for category in await orm_get_categories(session)]

    # Проверяем, является ли выбранная категория допустимой
    if category_id in valid_categories:
        # Обновляем данные состояния
        await state.update_data(category=category_id)

        # Проверяем, отличается ли сообщение от текущего
        current_message_text = callback.message.text

        # Новый текст сообщения
        new_message_text = "Введите стоимость товара"

        if current_message_text != new_message_text:
            await callback.message.answer(new_message_text)

        # Устанавливаем следующее состояние
        await state.set_state(AddProduct.price)

        # Закрываем callback уведомление
        await callback.answer()
    else:
        # Если категория недействительна, отправляем уведомление
        await callback.answer("Выберите корректную категорию", show_alert=True)


@admin_router.message(AddProduct.price, F.text)
async def add_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer("Стоимость товара должна быть положительным числом. Введите заново.")
            return
        await state.update_data(price=price)
    except ValueError:
        await message.answer("Введите корректное числовое значение стоимости.")
        return

    await message.answer("Отправьте фото товара")
    await state.set_state(AddProduct.image)


@admin_router.message(AddProduct.image, F.photo)
async def add_image(message: types.Message, state: FSMContext):
    image_id = message.photo[-1].file_id
    await state.update_data(image=image_id)
    await message.answer("Введите количество товара")
    await state.set_state(AddProduct.stock)


@admin_router.message(AddProduct.stock, F.text)
async def add_stock(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        stock = int(message.text)
        if stock < 0:
            await message.answer("Количество товара не может быть отрицательным. Введите заново.")
            return
        data = await state.get_data()
        data['stock'] = stock  # Добавляем количество товара в данные

        if AddProduct.product_for_change:
            # Update existing product
            await orm_update_product(session, AddProduct.product_for_change.id, data)
            AddProduct.product_for_change = None
            await message.answer("Товар изменен.")
        else:
            # Add new product
            await orm_add_product(session, data)
            await message.answer("Товар добавлен.")

        await state.clear()
        await message.answer("Возвращаемся в меню", reply_markup=ADMIN_KB)
    except ValueError:
        await message.answer("Введите корректное числовое значение количества.")


# Обработка нажатия кнопки "Поиск" в ассортименте
@admin_router.callback_query(F.data == 'admin_search')
async def admin_start_search(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ключевые слова для поиска:")
    await state.set_state(AdminSearchProduct.keywords)

# Обработка ввода ключевых слов для поиска
@admin_router.message(AdminSearchProduct.keywords, F.text)
async def admin_search_products(message: types.Message, session: AsyncSession, state: FSMContext):
    search_query = message.text.strip()
    products = await orm_get_products_by_keywords(session, search_query)
    if not products:
        await message.answer("Товары не найдены.")
        return

    for product in products:
        await message.answer_photo(
            product.image,
            caption=f"<b>{product.name}</b>\n"
                    f"<b>{product.sku}</b>\n"
                    f"{product.description}\n"
                    f"Стоимость: {round(product.price, 2)} ₽\n"
                    f"В наличии: {product.stock} шт.",
            parse_mode='HTML',
            reply_markup=get_callback_btns(
                btns={
                    "Удалить": f"delete_{product.id}",
                    "Изменить": f"change_{product.id}",
                },
                sizes=(2,)
            )
        )

    await state.clear()  # Очищаем состояние после завершения поиска



# Обработчик кнопки "Заказы"
@admin_router.message(F.text == 'Заказы')
async def show_orders(message: types.Message, session: AsyncSession):
    # Получаем список всех заказов
    orders = await get_orders(session)

    if not orders:
        await message.answer("Нет заказов.")
        return

    # Отображаем информацию о заказах
    for order in orders:
        # Получаем данные о пользователе (предполагается, что метод get_user_by_id существует)
        user = await get_user_by_id(session, order.user_id)
        user_info = f"Пользователь: {user.first_name} {user.last_name} (ID: {user.user_id})" if user else "Пользователь: Неизвестен"

        status_text = f"Статус: {order.status}"

        # Кнопки для изменения статуса
        buttons = [
            InlineKeyboardButton(text="Отмена", callback_data=f"order_{order.id}_cancel"),
            InlineKeyboardButton(text="Готов", callback_data=f"order_{order.id}_ready"),
            InlineKeyboardButton(text="Выдан", callback_data=f"order_{order.id}_delivered")
        ]

        # Создаем клавиатуру только если есть кнопки
        if buttons:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[button] for button in buttons])
            await message.answer(
                f"Заказ № {order.order_number}\n"
                f"{user_info}\n"
                f"{status_text}",
                reply_markup=keyboard
            )
        else:
            await message.answer(
                f"Заказ № {order.order_number}\n"
                f"{user_info}\n"
                f"{status_text}\n(Нет доступных действий)"
            )


# Добавьте команду или callback для обработки отображения всех заказов
@admin_router.message(Command("orders"))
async def show_all_orders(message: types.Message, session: AsyncSession):
    """Показ всех заказов для администратора."""
    orders_text, keyboard = await get_all_orders(session)
    if not orders_text:
        await message.answer("Нет доступных заказов.")
    else:
        await message.answer(orders_text, reply_markup=keyboard)



# Обработчики изменения статуса заказа
@admin_router.callback_query(F.data.startswith("order_"))
async def handle_order_action(callback: types.CallbackQuery, session: AsyncSession):
    # Разбираем callback_data в формате "order_<id>_<action>"
    parts = callback.data.split('_')

    if len(parts) < 3:
        await callback.answer("Некорректный формат данных.")
        return

    order_id = parts[1]
    action = parts[2]

    try:
        order_id = int(order_id)  # Преобразуем идентификатор заказа в число
    except ValueError:
        await callback.answer("Некорректный идентификатор заказа.")
        return

    # Проверяем действие и обновляем статус заказа
    status_map = {
        "cancel": "Отменен",
        "ready": "Готов к получению",
        "delivered": "Выдан"
    }

    if action in status_map:
        new_status = status_map[action]
        await update_order_status(session, order_id, new_status)
        await callback.answer(f"Статус заказа обновлен на '{new_status}'.")
    else:
        await callback.answer("Неизвестное действие.")


@admin_router.message(Command("orders"))
async def handle_orders(message: types.Message, session: AsyncSession):
    # Получаем все заказы из базы данных
    orders = await get_orders(session)

    if not orders:
        await message.answer("Нет заказов.")
        return

    # Для каждого заказа создаем кнопки
    for order in orders:
        # Кнопка для изменения статуса заказа
        buttons = [
            InlineKeyboardButton("Изменить статус", callback_data=f"change_status_{order.id}")
        ]
        keyboard = InlineKeyboardMarkup(row_width=1).add(*buttons)

        # Отправляем информацию о заказе с клавиатурой
        await message.answer(f"Заказ #{order.id} от пользователя {order.user_id}\nСтатус: {order.status}",
                             reply_markup=keyboard)




@admin_router.callback_query(F.data == "view_orders")
async def view_orders(callback: types.CallbackQuery, session: AsyncSession):
    orders = await get_orders(session)
    if not orders:
        await callback.message.answer("Нет текущих заказов.")
        return

    for order in orders:
        order_text = "\n".join([f"{item.product.name} - {item.stock} шт." for item in order.items])
        total = sum([item.stoc * item.price for item in order.items])
        await callback.message.answer(
            f"Заказ #{order.order_number}\n"
            f"Пользователь: {order.user_id}\n"
            f"Товары:\n{order_text}\n"
            f"Сумма: {total} ₽",
            reply_markup=get_order_admin_buttons(order.id)
        )




# Обработчик изменения статуса заказа
@admin_router.callback_query(F.data.startswith('order_cancel_'))
async def cancel_order(callback: types.CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split('_')[2])
    await update_order_status(session, order_id, "Отменен")
    await callback.answer("Статус заказа обновлен на 'Отменен'")

@admin_router.callback_query(F.data.startswith('order_ready_'))
async def ready_order(callback: types.CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split('_')[2])
    await update_order_status(session, order_id, "Готов")
    await callback.answer("Статус заказа обновлен на 'Готов'")

@admin_router.callback_query(F.data.startswith('order_delivered_'))
async def delivered_order(callback: types.CallbackQuery, session: AsyncSession):
    order_id = int(callback.data.split('_')[2])
    await update_order_status(session, order_id, "Выдан")
    await callback.answer("Статус заказа обновлен на 'Выдан'")


@admin_router.callback_query(lambda c: c.data and c.data.startswith("change_status_"))
async def handle_status_change(callback_query: types.CallbackQuery, session: AsyncSession):
    # Извлекаем ID заказа из callback_data
    order_id = int(callback_query.data.split("_")[2])

    # Получаем заказ из базы данных
    order = await get_order_by_id(session, order_id)

    if not order:
        await callback_query.answer("Этот заказ не найден.")
        return

    # Предлагаем изменить статус
    new_status = "Выполнен" if order.status != "Выполнен" else "Отменен"
    await update_order_status(session, order_id, new_status)

    await callback_query.answer(f"Статус заказа #{order_id} изменен на {new_status}.")




# Обработчик для загрузки файла Excel
@admin_router.message(F.text == "Загрузить файл Excel")
async def prompt_for_excel_upload(message: types.Message):
    await message.answer("Пожалуйста, отправьте файл Excel для загрузки.")

@admin_router.message(F.document.file_name.endswith(".xls") | F.document.file_name.endswith(".xlsx"))
async def handle_excel_upload(message: types.Message):
    file_id = message.document.file_id
    file = await bot.get_file(file_id)

    # Загрузка файла на сервер
    await file.download(destination=f"/path/to/upload/{message.document.file_name}")
    await message.answer("Файл Excel успешно загружен и обработан.")
