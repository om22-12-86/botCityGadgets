from aiogram import F, types, Router
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select
from database.models import Banner, Cart, Category, Product, User
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_add_to_cart, orm_add_user, orm_get_products_by_keywords, orm_get_products, orm_get_user_carts, create_order_from_cart, get_user_orders
from filters.chat_types import ChatTypeFilter
from handlers.menu_processing import get_menu_content, carts# Импортируем функции
from kbds.inline import MenuCallBack, get_product_buttons, get_user_products_btns
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from utils.paginator import Paginator




user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))  # Ограничиваем роутер для частных чатов


# Обработчик команды /start
@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main")
    await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)

# Обработчик для выбора категории
@user_private_router.callback_query(F.data.startswith('category_'))
async def show_products_by_category(callback: types.CallbackQuery, session: AsyncSession):
    category_id = int(callback.data.split('_')[-1])
    products = await orm_get_products(session, category_id)

    if not products:
        await callback.message.answer("В этой категории товары не найдены.")
        return

    # Создаем объект Paginator с начальной страницей
    paginator = Paginator(products, page=1, per_page=3)  # Настройте начальную страницу и товары на странице
    page_products = paginator.get_page()  # Получаем товары для текущей страницы

    # Определяем кнопки для пагинации
    pagination_btns = {}
    if paginator.has_previous():
        pagination_btns["◀ Пред."] = f"category_{category_id}_{paginator.page - 1}"
    if paginator.has_next():
        pagination_btns["След. ▶"] = f"category_{category_id}_{paginator.page + 1}"

    # Перебираем товары на текущей странице и отправляем их пользователю
    for product in page_products:
        await callback.message.answer_photo(
            product.image,
            caption=f"<b>{product.name}</b>\n"
                    f"<b>{product.sku}</b>\n"
                    f"{product.description}\n"
                    f"Стоимость: {round(product.price, 2)} ₽\n"
                    f"В наличии: {product.stock} шт.\n"
                    f"<b>Товар {paginator.page} из {paginator.pages}</b>",
            parse_mode='HTML',
            # Теперь передаем `pagination_btns` и `current_page` в `get_product_buttons`
            reply_markup=get_product_buttons(category_id, product.id, pagination_btns, paginator.page)
        )

    await callback.answer()







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

    # Добавляем товар в корзину пользователя
    await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id)
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

    # Проверка на изменение содержимого
    if isinstance(media, types.InputMediaPhoto):
        if callback.message.photo and callback.message.caption == media.caption and callback.message.reply_markup == reply_markup:
            await callback.answer("Контент не изменился.")
            return
        # Обновляем фото, если есть изменения
        await callback.message.edit_media(media=media, reply_markup=reply_markup)

    elif isinstance(media, str):
        if callback.message.text == media and callback.message.reply_markup == reply_markup:
            await callback.answer("Контент не изменился.")
            return
        await callback.message.edit_text(text=media, reply_markup=reply_markup)

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
    search_query = message.text.strip()
    products = await orm_get_products_by_keywords(session, search_query)

    if not products:
        await message.answer("Товары не найдены.")
        await state.clear()
        return

    for product in products:
        await message.answer_photo(
            product.image,
            caption=(
                f"<b>{product.name}</b>\n"
                f"Артикул: {product.sku}\n"
                f"{product.description}\n"
                f"Цена: {product.price} ₽\n"
                f"В наличии: {product.stock} шт.\n"
            ),
            parse_mode='HTML',
            reply_markup=get_user_products_btns(product_id=product.id)
        )
    await state.clear()




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


@user_private_router.callback_query(F.data == 'main_menu')
async def go_to_main_menu(callback: types.CallbackQuery, session: AsyncSession):
    # Здесь функция для возврата к главному меню
    media, reply_markup = await get_menu_content(session, level=0, menu_name='main')
    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer("Вы вернулись в главное меню.")




@user_private_router.callback_query(F.data == "order")
async def handle_create_order(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    order = await create_order_from_cart(session, user_id)

    if order:
        await callback.message.answer(
            f"Ваш заказ #{order.order_number} успешно создан и находится в обработке.",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("На главную 🏠", callback_data="main_menu"))
        )
    else:
        await callback.message.answer("Ваша корзина пуста.")
    await callback.answer()

@user_private_router.callback_query(F.data == "view_orders")
async def handle_view_orders(callback: CallbackQuery, session: AsyncSession):
    orders_text, keyboard = await user_orders(session, callback.from_user.id)
    await callback.message.answer(orders_text, reply_markup=keyboard)
    await callback.answer()