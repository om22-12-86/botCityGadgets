from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query import (
    orm_change_banner_image,
    orm_get_categories,
    orm_add_product,
    orm_delete_product,
    orm_get_info_pages,
    orm_get_product,
    orm_get_products,
    orm_update_product,
)

from filters.chat_types import ChatTypeFilter, IsAdmin
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard

admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())

ADMIN_KB = get_keyboard(
    "Добавить товар",
    "Ассортимент",
    "Добавить/Изменить баннер",
    placeholder="Выберите действие",
    sizes=(2,),
)


@admin_router.message(Command("admin"))
async def admin_features(message: types.Message):
    await message.answer("Что хотите сделать?", reply_markup=ADMIN_KB)


@admin_router.message(F.text == 'Ассортимент')
async def show_products(message: types.Message, session: AsyncSession):
    categories = await orm_get_categories(session)
    btns = {category.name: f'category_{category.id}' for category in categories}
    await message.answer("Выберите категорию", reply_markup=get_callback_btns(btns=btns))


# Отображение товаров в категории с указанием количества на складе
@admin_router.callback_query(F.data.startswith('category_'))
async def show_category_products(callback: types.CallbackQuery, session: AsyncSession):
    category_id = callback.data.split('_')[-1]
    products = await orm_get_products(session, int(category_id))
    for product in products:
        # Добавляем отображение количества товара на складе
        await callback.message.answer_photo(
            product.image,
            caption=f"<b>{product.name}</b>\n"
                    f"{product.description}\n"
                    f"Стоимость: {round(product.price, 2)}\n"
                    f"В наличии: {product.stock} шт.",  # Количество товара на складе
            parse_mode='HTML',
            reply_markup=get_callback_btns(
                btns={
                    "Удалить": f"delete_{product.id}",
                    "Изменить": f"change_{product.id}",
                },
                sizes=(2,)
            ),
        )
    await callback.answer()
    await callback.message.answer("ОК, вот список товаров ⏫")


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
    for_page = message.caption.strip()
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
    description = State()
    category = State()
    price = State()
    image = State()
    stock = State()  # изменено с quantity на stock

    product_for_change = None

    texts = {
        "AddProduct:name": "Введите название заново:",
        "AddProduct:description": "Введите описание заново:",
        "AddProduct:category": "Выберите категорию заново ⬆️",
        "AddProduct:price": "Введите стоимость заново:",
        "AddProduct:image": "Этот стейт последний, поэтому...",
        "AddProduct:stock": "Введите количество товара:",  # изменено с quantity на stock
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

