from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.paginator import Paginator
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import CallbackQuery
from sqlalchemy.future import select
from database.engine import SessionLocal
from database.models import Order, User, OrderHistory, Category
import logging
from urllib.parse import quote, unquote
import pandas as pd
import os


logging.basicConfig(level=logging.INFO)


from database.orm_query import (
upload_local_image_to_telegram,
send_default_image,
get_and_store_default_image_id,
delete_old_products_in_category,
send_product_image,
get_product_image,
upload_default_image,
    get_deleted_orders,
    move_order_to_history,
    display_orders_to_user,
    delete_order,
    get_order_items,
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
from kbds.inline import get_callback_btns, create_status_buttons, get_product_buttons
from kbds.reply import get_keyboard

admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())

# Клавиатура для меню администратора

ADMIN_KB = get_keyboard(
"Добавить Категорию",
    "Добавить товар",
    "Ассортимент",
    "Добавить/Изменить баннер",
    "Заказы",
    "Загрузить файл Excel",

    placeholder="Выберите действие",
    sizes=(3,),
)






# FSM для поиска товаров
class AdminSearchProduct(StatesGroup):
    keywords = State()

@admin_router.message(Command("admin"))
async def admin_features(message: types.Message):
    await message.answer("Что хотите сделать?", reply_markup=ADMIN_KB)


class AddCategory(StatesGroup):
    name = State()  # Для ввода названия категории
    description = State()  # Для ввода описания категории




@admin_router.message(F.text == "Добавить Категорию")
async def add_category_prompt(message: types.Message, state: FSMContext):
    await message.answer("Введите название новой категории:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AddCategory.name)  # Переходим в состояние для ввода категории



@admin_router.message(AddCategory.name, F.text)
async def add_category_name(message: types.Message, state: FSMContext, session: AsyncSession):
    category_name = message.text.strip()

    if len(category_name) < 3:
        await message.answer("Название категории должно быть хотя бы из 3 символов. Попробуйте снова.")
        return

    # Проверяем, существует ли категория с таким названием
    existing_category = await orm_get_categories(session)
    if any(category.name.lower() == category_name.lower() for category in existing_category):
        await message.answer(f"Категория с названием '{category_name}' уже существует.")
        return

    # Сохраняем название категории в состоянии
    await state.update_data(name=category_name)

    # Переходим ко второму шагу — запросим описание категории
    await message.answer("Введите описание категории (можно пропустить):")
    await state.set_state(AddCategory.description)


@admin_router.message(AddCategory.description, F.text)
async def add_category_description(message: types.Message, state: FSMContext, session: AsyncSession):
    category_description = message.text.strip() if message.text != "." else None

    # Получаем данные из состояния
    data = await state.get_data()
    category_name = data.get("name")

    # Создаем новый объект категории
    new_category = Category(
        name=category_name,
        description=category_description
    )

    # Сохраняем категорию в базе данных
    session.add(new_category)
    await session.commit()

    # Завершаем создание категории
    await message.answer(f"Категория '{category_name}' успешно добавлена!", reply_markup=ADMIN_KB)
    await state.clear()  # Очистим состояние



@admin_router.message(F.text == 'Ассортимент')
async def show_products(message: types.Message, session: AsyncSession):
    categories = await orm_get_categories(session)
    btns = {category.name: f'category_{category.id}' for category in categories}
    # Добавляем кнопку "Поиск"
    btns["Поиск"] = 'admin_search'
    await message.answer("Выберите категорию или выполните поиск", reply_markup=get_callback_btns(btns=btns))


@admin_router.callback_query(F.data.startswith('category_'))
async def show_category_products(callback: types.CallbackQuery, session: AsyncSession):
    try:
        # Логируем полученные данные callback
        print(f"Получен callback: {callback.data}")

        # Извлекаем данные из callback
        data = callback.data.split('_')

        # Проверка, что данные корректны (минимум 2 элемента: category_id и page)
        if len(data) < 3:
            raise ValueError("Неверный формат данных callback")

        category_id = int(data[1])  # Идентификатор категории
        page = int(data[2]) if len(data) > 2 else 1  # Текущая страница (по умолчанию 1)

        # Получаем список товаров в категории
        products = await orm_get_products(session, category_id)

        if not products:
            await callback.message.answer("В этой категории товары не найдены.")
            return

        # Пагинация: создаем объект Paginator и получаем товары на текущей странице
        paginator = Paginator(products, page=page, per_page=5)  # Показываем 5 товаров на странице
        page_products = paginator.get_page()

        # Если на текущей странице нет товаров
        if not page_products:
            await callback.message.answer("На этой странице товаров нет.")
            return

        # Логируем текущую страницу и общее количество страниц
        print(f"Текущая страница: {paginator.page}, Всего страниц: {paginator.pages}")

        # Определяем кнопки пагинации
        pagination_btns = {}
        if paginator.has_previous():
            pagination_btns["◀ Пред."] = f"category_{category_id}_{paginator.page - 1}"
        if paginator.has_next():
            pagination_btns["След. ▶"] = f"category_{category_id}_{paginator.page + 1}"

        # Отправка товаров с кнопками пагинации
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
                    reply_markup=get_product_buttons(category_id, product.id, pagination_btns, paginator.page)
                )
            else:
                # Если изображения нет, отправляем только текстовую информацию
                await callback.message.answer(
                    text=caption,
                    parse_mode='HTML',
                    reply_markup=get_product_buttons(category_id, product.id, pagination_btns, paginator.page)
                )

        # Завершаем обработку
        await callback.answer("ОК, вот список товаров ⏫")

    except Exception as e:
        # Логируем ошибку
        print(f"Ошибка при загрузке товаров: {e}")
        # Отправляем сообщение о проблеме
        await callback.message.answer("Произошла ошибка при загрузке товаров.")






@admin_router.callback_query(F.data.startswith('admin_delete_'))
async def admin_delete_product(callback: types.CallbackQuery, session: AsyncSession):
    try:
        product_id = int(callback.data.split('_')[-1])
        logging.info(f"Удаление товара с ID: {product_id}")
        await orm_delete_product(session, product_id)
        await callback.answer("Товар удален!")
        await callback.message.delete()  # Удаление сообщения с товаром
    except Exception as e:
        logging.error(f"Ошибка при удалении товара: {e}")
        await callback.answer("Произошла ошибка при удалении товара.")




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


# Обработка кнопки изменения товара
@admin_router.callback_query(F.data.startswith('admin_change_'))
async def change_product_callback(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    product_id = int(callback.data.split('_')[-1])

    # Получаем товар по ID
    product = await orm_get_product(session, product_id)

    if product:
        await state.update_data(product=product)  # Сохраняем товар в состоянии
        AddProduct.product_for_change = product  # Устанавливаем товар для изменения
        await callback.message.answer("Введите новое название товара:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(AddProduct.name)
    else:
        await callback.message.answer("Товар не найден.")



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


@admin_router.message(StateFilter("*"), F.text.casefold() == ".")
async def leave_without_changes(message: types.Message, state: FSMContext):
    current_state = await state.get_state()

    if AddProduct.product_for_change:  # Проверяем, выбран ли товар для изменения
        # Если товар для изменения найден, сохраняем старые значения без изменений
        if current_state == AddProduct.name:
            await state.update_data(name=AddProduct.product_for_change.name)
        elif current_state == AddProduct.sku:
            await state.update_data(sku=AddProduct.product_for_change.sku)
        elif current_state == AddProduct.description:
            await state.update_data(description=AddProduct.product_for_change.description)
        elif current_state == AddProduct.category:
            await state.update_data(category=AddProduct.product_for_change.category_id)
        elif current_state == AddProduct.price:
            await state.update_data(price=AddProduct.product_for_change.price)
        elif current_state == AddProduct.image:
            await state.update_data(image=AddProduct.product_for_change.image)
        elif current_state == AddProduct.stock:
            await state.update_data(stock=AddProduct.product_for_change.stock)

        await message.answer("Параметр оставлен без изменений. Продолжаем редактирование.")
    else:
        await message.answer("Ошибка: не выбран товар для изменения.")

    # Переход к следующему шагу в зависимости от текущего состояния
    if current_state == AddProduct.name:
        await message.answer("Введите артикул (SKU) товара")
        await state.set_state(AddProduct.sku)
    elif current_state == AddProduct.sku:
        await message.answer("Введите описание товара")
        await state.set_state(AddProduct.description)
    elif current_state == AddProduct.description:
        await message.answer("Выберите категорию товара")
        await state.set_state(AddProduct.category)
    elif current_state == AddProduct.category:
        await message.answer("Введите стоимость товара")
        await state.set_state(AddProduct.price)
    elif current_state == AddProduct.price:
        await message.answer("Отправьте фото товара")
        await state.set_state(AddProduct.image)
    elif current_state == AddProduct.image:
        await message.answer("Введите количество товара")
        await state.set_state(AddProduct.stock)





@admin_router.message(AddProduct.name, F.text)
async def add_name(message: types.Message, state: FSMContext):
    if message.text == "." and AddProduct.product_for_change:
        await state.update_data(name=AddProduct.product_for_change.name)
    else:
        if not (5 <= len(message.text) <= 250):
            await message.answer("Название товара должно быть от 5 до 250 символов. Введите заново.")
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

        # Отправка найденных товаров
        for product in products:
            caption = (
                f"<b>{product.name}</b>\n"
                f"<b>{product.sku}</b>\n"
                f"{product.description}\n"
                f"Стоимость: {round(product.price, 2)} ₽\n"
                f"В наличии: {product.stock} шт."
            )

            # Если есть изображение
            if product.image:
                try:
                    await message.answer_photo(
                        product.image,  # Отправляем изображение товара
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=get_callback_btns(
                            btns={
                                "Удалить": f"delete_{product.id}",
                                "Изменить": f"change_{product.id}",
                            },
                            sizes=(2,)
                        )
                    )
                except Exception as e:
                    print(f"Ошибка при отправке изображения: {e}")
                    # Если ошибка при отправке фото, отправляем только описание
                    await message.answer(
                        text=caption,
                        parse_mode='HTML',
                        reply_markup=get_callback_btns(
                            btns={
                                "Удалить": f"admin_delete_{product.id}",
                                "Изменить": f"admin_change_{product.id}",
                            },
                            sizes=(2,)
                        )
                    )
            else:
                # Если изображения нет, отправляем только описание товара
                await message.answer(
                    text=caption,
                    parse_mode='HTML',
                    reply_markup=get_callback_btns(
                        btns={
                            "Удалить": f"admin_delete_{product.id}",
                            "Изменить": f"admin_change_{product.id}",
                        },
                        sizes=(2,)
                    )
                )

        # Кнопки пагинации
        pagination_btns = {}
        if page > 1:
            pagination_btns["◀ Пред."] = f"admin_search_{search_query}_{page - 1}"
        if page < total_pages:
            pagination_btns["След. ▶"] = f"admin_search_{search_query}_{page + 1}"

        if pagination_btns:
            await message.answer(
                text=pagination_info,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=text, callback_data=callback_data) for text, callback_data in pagination_btns.items()]
                ])
            )

        await state.clear()

    except Exception as e:
        print(f"Ошибка при выполнении запроса: {e}")
        await message.answer("Произошла ошибка при загрузке товаров.")




@admin_router.callback_query(F.data.startswith('admin_search_'))
async def admin_pagination(callback: types.CallbackQuery, session: AsyncSession):
    try:
        # Разбор callback_data
        data = callback.data.split('_')
        search_query = unquote('_'.join(data[2:-1]))  # Извлекаем и декодируем поисковый запрос
        page = int(data[-1])  # Текущая страница
        per_page = 5  # Количество товаров на странице

        # Получаем товары и общее количество
        products, total_count = await orm_get_products_by_keywords(session, search_query, page, per_page)

        if not products:
            await callback.message.edit_text("Товары не найдены.")
            return

        # Пагинация
        total_pages = (total_count + per_page - 1) // per_page
        pagination_info = f"Найдено {total_count} товаров. Страница {page} из {total_pages}."

        # Отправка товаров (как в основном хендлере)
        for product in products:
            caption = (
                f"<b>{product.name}</b>\n"
                f"<b>{product.sku}</b>\n"
                f"{product.description}\n"
                f"Стоимость: {round(product.price, 2)} ₽\n"
                f"В наличии: {product.stock} шт."
            )
            if product.image:
                try:
                    await callback.message.answer_photo(
                        product.image,
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=get_callback_btns(
                            btns={
                                "Удалить": f"admin_delete_{product.id}",
                                "Изменить": f"admin_change_{product.id}",
                            },
                            sizes=(2,)
                        )
                    )
                except Exception as e:
                    print(f"Ошибка при отправке изображения: {e}")
                    await callback.message.answer(
                        text=caption,
                        parse_mode='HTML',
                        reply_markup=get_callback_btns(
                            btns={
                                "Удалить": f"admin_delete_{product.id}",
                                "Изменить": f"admin_change_{product.id}",
                            },
                            sizes=(2,)
                        )
                    )
            else:
                await callback.message.answer(
                    text=caption,
                    parse_mode='HTML',
                    reply_markup=get_callback_btns(
                        btns={
                            "Удалить": f"admin_delete_{product.id}",
                            "Изменить": f"admin_change_{product.id}",
                        },
                        sizes=(2,)
                    )
                )

        # Кнопки пагинации
        pagination_btns = {}
        if page > 1:
            pagination_btns["◀ Пред."] = f"admin_search_{quote(search_query)}_{page - 1}"
        if page < total_pages:
            pagination_btns["След. ▶"] = f"admin_search_{quote(search_query)}_{page + 1}"

        if pagination_btns:
            await callback.message.answer(
                text=pagination_info,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=text, callback_data=callback_data) for text, callback_data in pagination_btns.items()]
                ])
            )

    except Exception as e:
        print(f"Ошибка при обработке пагинации: {e}")
        await callback.message.answer("Произошла ошибка при загрузке данных.")





# Обработчик для команды "Заказы"
@admin_router.message(F.text == 'Заказы')
async def show_orders_menu(message: types.Message):
    """
    Отображение меню для выбора действия с заказами.
    """
    # Кнопки для выбора фильтра по статусу заказов
    buttons = [
        InlineKeyboardButton(text="Все", callback_data="view_all_orders"),
        InlineKeyboardButton(text="История заказа", callback_data="view_order_history"),
        InlineKeyboardButton(text="Поиск", callback_data="search_orders")  # Оставляем кнопку для поиска
    ]

    # Создаем клавиатуру с кнопками для выбора, в два столбика
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [buttons[0], buttons[1]],  # В два столбика
            [buttons[2]]               # Поиск в отдельной строке
        ],
        resize_keyboard=True,  # Делаем клавиатуру компактной
        one_time_keyboard=True  # Клавиатура скрывается после выбора
    )

    # Отправка сообщения с предложением выбрать действие
    await message.answer("Выберите действие для просмотра заказов:", reply_markup=keyboard)



@admin_router.callback_query(F.data == "view_order_history")
async def view_order_history(callback: CallbackQuery, session: AsyncSession):
    """
    Обработчик для отображения истории удаленных заказов.
    """
    logging.info("Обработчик 'История заказов' вызван.")  # Лог вызова обработчика

    # Запрос к таблице `order_history` для получения всех записей
    query = select(OrderHistory).order_by(OrderHistory.deleted_at.desc())
    result = await session.execute(query)
    orders = result.scalars().all()

    # Проверка наличия записей в `order_history`
    if not orders:
        await callback.message.answer("История заказов пуста.")
        return

    logging.info(f"Найдено {len(orders)} записей в истории.")  # Лог количества записей

    # Перебираем удаленные заказы и отправляем администратору
    for order in orders:
        deleted_time = order.deleted_at.strftime("%d.%m.%Y %H:%M") if order.deleted_at else "Не указано"
        created_time = order.created.strftime("%d.%m.%Y %H:%M")
        updated_time = order.updated.strftime("%d.%m.%Y %H:%M")

        # Формируем текст сообщения для каждого заказа
        message_text = (
            f"Заказ № {order.order_number}\n"
            f"Пользователь ID: {order.user_id}\n"
            f"Дата создания: {created_time}\n"
            f"Дата обновления: {updated_time}\n"
            f"Дата удаления: {deleted_time}\n"
            f"Статус: {order.status}\n"
            f"Общая стоимость: {order.total_cost:.2f} ₽"
        )

        await callback.message.answer(message_text)

    # Подтверждаем пользователю, что все данные отображены
    await callback.answer("История заказов успешно отображена.")






# Обработчик callback для фильтрации заказов по статусу
@admin_router.callback_query(F.data.startswith("view_"))
async def filter_orders_by_status(callback: types.CallbackQuery, session: AsyncSession):
    """
    Фильтрация заказов по выбранному статусу.
    """
    # Маппинг статусов
    status_map = {
        "all_orders": None,  # Все заказы
        "delivered_orders": "Выдан",  # Заказы с статусом "Выдан"
        "processing_orders": "В обработке",  # Заказы в процессе
        "cancelled_orders": "Отменен",  # Заказы с отмененным статусом
        "ready_orders": "Готов к получению"  # Заказы готовые к получению
    }

    # Получаем статус из callback_data
    status_key = callback.data.split("_")[1]
    status = status_map.get(status_key)  # Если статус найден, применяем его

    # Получаем список заказов с учетом фильтрации
    orders = await get_orders_by_status(session, status) if status else await get_orders(session)

    if not orders:
        await callback.message.answer(f"Нет заказов со статусом '{status or 'все'}'.")
        return

    # Сортируем заказы по дате создания (от новых к старым)
    orders = sorted(orders, key=lambda x: x.created, reverse=True)

    # Отправка заказов
    for order in orders:
        user = await get_user_by_id(session, order.user_id)
        user_info = f"Пользователь: {user.first_name} {user.last_name} (ID: {user.user_id})" if user else "Пользователь: Неизвестен"
        order_items = await get_order_items(session, order.id)
        items_info = "\n".join([f"{item.product.name} — {item.product.sku}\nКоличество: {item.stock}, Цена: {item.price} ₽" for item in order_items])
        total_sum = sum(item.stock * item.price for item in order_items)
        created_time = order.created.strftime("%d.%m.%Y %H:%M")

        # Кнопки для изменения статуса заказа
        buttons = [
            InlineKeyboardButton(text="Отмена", callback_data=f"order_{order.id}_cancel"),
            InlineKeyboardButton(text="Готов", callback_data=f"order_{order.id}_ready"),
            InlineKeyboardButton(text="Выдан", callback_data=f"order_{order.id}_delivered"),
            InlineKeyboardButton(text="Удалить", callback_data=f"order_{order.id}_delete")  # Кнопка для удаления
        ]

        # Создаем клавиатуру с компактными кнопками
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [buttons[0], buttons[1]],  # В два столбика
                [buttons[2], buttons[3]]   # В два столбика
            ],
            resize_keyboard=True,  # Делаем клавиатуру компактной
            one_time_keyboard=True  # Клавиатура скрывается после выбора
        )

        # Отправляем информацию о заказе
        await callback.message.answer(
            f"Заказ № {order.order_number}\n"
            f"{user_info}\n"
            f"Дата и время заказа: {created_time}\n"
            f"Статус: {order.status}\n"
            f"Товары:\n{items_info}\n"
            f"Общая сумма заказа: {total_sum:.2f} ₽",
            reply_markup=keyboard
        )








# Обработчик для поиска заказов
@admin_router.callback_query(F.data == "search_orders")
async def search_orders_prompt(callback: types.CallbackQuery, state: FSMContext):
    """
    Запрос пользователя на ввод номера заказа или имени пользователя для поиска.
    """
    await callback.message.answer("Введите номер заказа:")
    await state.set_state("search_order")



@admin_router.message(StateFilter("search_order"), F.text)
async def handle_search_order(message: types.Message, session: AsyncSession, state: FSMContext):
    """
    Обработка запроса на поиск заказов.
    """
    search_query = message.text.strip()

    # Используем SessionLocal для создания сессии
    async with SessionLocal() as session:
        # Ищем заказы по номеру
        result = await session.execute(select(Order).where(Order.order_number.like(f"%{search_query}%")))

        # Получаем все заказы
        orders = result.scalars().all()

        # Дополнительно ищем заказы по имени пользователя (предполагается, что есть связь с моделью User)
        matching_orders = []
        for order in orders:
            # Ищем по номеру заказа или по имени пользователя
            if search_query in str(order.order_number):
                matching_orders.append(order)
            elif order.user and search_query.lower() in f"{order.user.first_name} {order.user.last_name}".lower():
                matching_orders.append(order)

        # Проверяем, есть ли совпадения
        if not matching_orders:
            await message.answer("Заказы не найдены.")
        else:
            await display_orders_to_user(session, message, matching_orders)

    await state.clear()






# Обработчики изменения статуса заказа
@admin_router.callback_query(F.data.startswith("order_"))
async def handle_order_action(callback: types.CallbackQuery, session: AsyncSession):
    """
    Обработка изменения статуса заказа или удаления заказа.
    """
    parts = callback.data.split('_')

    if len(parts) < 3:
        await callback.answer("Некорректный формат данных.")
        return

    order_id = parts[1]
    action = parts[2]

    try:
        order_id = int(order_id)
    except ValueError:
        await callback.answer("Некорректный идентификатор заказа.")
        return

    status_map = {
        "cancel": "Отменен",
        "ready": "Готов к получению",
        "delivered": "Выдан"
    }

    if action in status_map:
        new_status = status_map[action]
        await update_order_status(session, order_id, new_status)
        await callback.answer(f"Статус заказа обновлен на '{new_status}'.")
    elif action == "delete":
        # Логика удаления заказа
        await delete_order(callback, session)  # Передаем callback, а не order_id
        await callback.answer(f"Заказ №{order_id} был удален.")
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
        # Кнопки для изменения статуса заказа
        buttons = [
            InlineKeyboardButton("Изменить статус", callback_data=f"change_status_{order.id}")
        ]

        # Если заказ неоплачен, добавляем кнопку "Оплатить онлайн"
        if not order.is_paid:
            buttons.append(InlineKeyboardButton("Оплатить онлайн 💳", callback_data=f"pay_order_{order.id}"))

        # Создаем клавиатуру
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








@admin_router.callback_query(F.data == "view_all_orders")
async def view_all_orders(callback: types.CallbackQuery, session: AsyncSession):
    """
    Display all active orders.
    """
    query = select(Order).filter(Order.status != "Удален").order_by(Order.created.desc())
    result = await session.execute(query)
    orders = result.scalars().all()

    if not orders:
        await callback.message.answer("Нет доступных заказов.")
        return

    for order in orders:
        user = await get_user_by_id(session, order.user_id)
        user_info = f"Пользователь: {user.first_name} {user.last_name} (ID: {user.user_id})" if user else "Пользователь: Неизвестен"
        created_time = order.created.strftime("%d.%m.%Y %H:%M")

        await callback.message.answer(
            f"Заказ № {order.order_number}\n"
            f"{user_info}\n"
            f"Дата и время заказа: {created_time}\n"
            f"Статус: {order.status}\n"
            f"Общая стоимость: {order.total_cost:.2f} ₽"
        )


@admin_router.callback_query(F.data.startswith("order_") and F.data.endswith("_delete"))
async def delete_order(callback: CallbackQuery, session: AsyncSession):
    """
    Обработчик для удаления заказа.
    """
    # Извлекаем ID заказа из callback_data
    order_id = int(callback.data.split("_")[1])

    # Перемещаем заказ в `order_history`
    success = await move_order_to_history(session, order_id)

    if success:
        await callback.answer(f"Заказ № {order_id} успешно удален и добавлен в историю.")
    else:
        await callback.answer(f"Не удалось найти заказ с ID {order_id}.")




# Обработчики для callback-данных
@admin_router.callback_query(F.data == 'view_all_orders')
async def callback_view_all_orders(callback_query: types.CallbackQuery, session: AsyncSession):
    orders = await get_orders_by_status(session, 'Все')
    await display_orders(callback_query.message, orders)

@admin_router.callback_query(F.data == 'view_delivered_orders')
async def callback_view_delivered_orders(callback_query: types.CallbackQuery, session: AsyncSession):
    orders = await get_orders_by_status(session, 'Выдан')
    await display_orders(callback_query.message, orders)

@admin_router.callback_query(F.data == 'view_processing_orders')
async def callback_view_processing_orders(callback_query: types.CallbackQuery, session: AsyncSession):
    orders = await get_orders_by_status(session, 'В обработке')
    await display_orders(callback_query.message, orders)

@admin_router.callback_query(F.data == 'view_ready_orders')
async def callback_view_ready_orders(callback_query: types.CallbackQuery, session: AsyncSession):
    orders = await get_orders_by_status(session, 'Готов к получению')
    await display_orders(callback_query.message, orders)




# Отправка сообщений с заказами через статус
@admin_router.message(F.text == 'Выданные')
async def view_delivered_orders(message: types.Message, session: AsyncSession):
    orders = await get_orders_by_status(session, 'Выдан')
    await display_orders(message, orders)



@admin_router.message(F.text == 'В обработке')
async def view_processing_orders(message: types.Message, session: AsyncSession):
    orders = await get_orders_by_status(session, 'В обработке')
    await display_orders(message, orders)



@admin_router.message(F.text == 'Готовы к получению')
async def view_ready_orders(message: types.Message, session: AsyncSession):
    orders = await get_orders_by_status(session, 'Готов к получению')
    await display_orders(message, orders)



# Дополнительный обработчик для "Показать статусы"
@admin_router.message(F.text == 'Показать статусы')
async def show_statuses(message: types.Message, session: AsyncSession):
    statuses = await get_statuses(session)  # Здесь предполагается, что функция get_statuses возвращает список статусов
    await message.answer(f"Доступные статусы: {', '.join(statuses)}")



@admin_router.message(F.text == 'Выданные')
async def view_delivered_orders(message: types.Message, session: AsyncSession):
    orders = await get_orders_by_status(session, 'Выдан')
    if orders:
        await message.answer("Заказы со статусом 'Выдан':")
        for order in orders:
            await message.answer(f"Заказ #{order.id} - {order.status}")
    else:
        await message.answer("Нет заказов со статусом 'Выдан'.")

@admin_router.message(F.text == 'В обработке')
async def view_processing_orders(message: types.Message, session: AsyncSession):
    orders = await get_orders_by_status(session, 'В обработке')
    if orders:
        await message.answer("Заказы со статусом 'В обработке':")
        for order in orders:
            await message.answer(f"Заказ #{order.id} - {order.status}")
    else:
        await message.answer("Нет заказов со статусом 'В обработке'.")

@admin_router.message(F.text == 'Готовы к получению')
async def view_ready_orders(message: types.Message, session: AsyncSession):
    orders = await get_orders_by_status(session, 'Готов к получению')
    if orders:
        await message.answer("Заказы со статусом 'Готов к получению':")
        for order in orders:
            await message.answer(f"Заказ #{order.id} - {order.status}")
    else:
        await message.answer("Нет заказов со статусом 'Готов к получению'.")



@admin_router.callback_query(F.data == "view_cancelled_orders")
async def view_cancelled_orders(callback: types.CallbackQuery, session: AsyncSession):
    orders = await get_orders_by_status(session, 'Отменен')
    if orders:
        await callback.message.answer("Заказы со статусом 'Отменен':")
        for order in orders:
            await callback.message.answer(f"Заказ #{order.id} - {order.status}")
    else:
        await callback.message.answer("Нет заказов со статусом 'Отменен'.")




@admin_router.message(F.text == 'Загрузить файл Excel')
async def handle_excel_upload(message: types.Message, state: FSMContext):
    # Получаем список категорий из базы
    async with SessionLocal() as session:
        result = await session.execute(select(Category))
        categories = result.scalars().all()
        btns = {category.name: str(category.id) for category in categories}
        btns["Отмена"] = "cancel"

        # Запрашиваем у пользователя категорию для загрузки
        await message.answer("Выберите категорию для загрузки товаров из Excel",
                             reply_markup=get_callback_btns(btns=btns))
        await state.set_state('choose_category')



@admin_router.callback_query(StateFilter('choose_category'))
async def choose_category_callback(callback: types.CallbackQuery, state: FSMContext):
    category_id = int(callback.data)
    await state.update_data(category=category_id)
    await callback.message.answer("Загрузите файл Excel")
    await state.set_state('upload_excel')





@admin_router.message(StateFilter('upload_excel'), F.document)
async def handle_file_upload(message: types.Message, state: FSMContext, session: AsyncSession):
    temp_file_path = None
    try:
        # Получаем ID категории
        category_id = (await state.get_data()).get('category')
        if not category_id:
            await message.answer("Категория не выбрана.")
            return

        # Загрузка файла
        file_id = message.document.file_id
        file_info = await message.bot.get_file(file_id)
        file_path = file_info.file_path
        file = await message.bot.download_file(file_path)

        temp_file_path = f"temp_{file_id}.xlsx"
        with open(temp_file_path, 'wb') as f:
            f.write(file.getvalue())

        # Чтение Excel
        try:
            df = pd.read_excel(temp_file_path)
        except Exception as e:
            raise ValueError(f"Ошибка чтения Excel-файла: {e}")

        # Проверка колонок
        required_columns = {'name', 'sku', 'category', 'price', 'stock'}
        if not required_columns.issubset(df.columns):
            raise ValueError("Excel-файл не содержит всех необходимых колонок.")

        # Заменяем NaN значения на дефолтные
        df['name'] = df['name'].fillna('Без названия')  # Пример дефолтного значения для имени
        df['sku'] = df['sku'].fillna('Неизвестно')  # Пример дефолтного значения для SKU
        df['description'] = df['description'].fillna('Нет описания')  # Пример для описания
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
        df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0)
        df['category'] = pd.to_numeric(df['category'], errors='coerce').fillna(category_id)  # Используем выбранную категорию, если значение NaN

        # Удаление старых товаров
        await delete_old_products_in_category(session, category_id)

        # Добавление товаров
        for _, row in df.iterrows():
            product_data = {
                "name": row['name'],
                "sku": row['sku'],
                "description": row['description'],
                "price": row['price'],
                "image": None,  # Не указываем изображение, если его нет
                "stock": row['stock'],
                "category": category_id,
            }
            await orm_add_product(session, product_data)

        await message.answer("Товары успешно добавлены.")

    except Exception as e:
        await message.answer(f"Ошибка при обработке файла: {e}")

    finally:
        if temp_file_path:
            os.remove(temp_file_path)









@admin_router.message(StateFilter('change_product_image'), F.photo)
async def update_product_image(message: types.Message, state: FSMContext, session: AsyncSession):
    product_id = (await state.get_data())['product_id']
    new_image_id = message.photo[-1].file_id  # Получаем file_id изображения

    # Обновляем изображение в базе
    await orm_update_product(session, product_id, {"image": new_image_id})

    await message.answer("Изображение успешно обновлено.")
    await state.clear()




