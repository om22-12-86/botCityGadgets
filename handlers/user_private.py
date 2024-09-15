from aiogram import F, types, Router
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database.orm_query import orm_add_to_cart, orm_add_user, orm_get_products, orm_get_products_by_keywords
from filters.chat_types import ChatTypeFilter
from handlers.menu_processing import get_menu_content, carts  # Импортируем функции
from kbds.inline import MenuCallBack, get_product_buttons

# Создаем новый роутер для частных сообщений (личных сообщений пользователей)
user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))  # Ограничиваем роутер для частных чатов


# Обработчик команды /start
@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    """
    Обработчик команды /start. Отправляет пользователю главное меню.
    :param message: Сообщение, содержащее команду /start
    :param session: Асинхронная сессия для взаимодействия с базой данных
    """
    # Получаем основное меню из функции get_menu_content
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main")

    # Отправляем пользователю изображение с кнопками главного меню
    await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)


# Обработчик для выбора категории
@user_private_router.callback_query(F.data.startswith('category_'))
async def show_products_by_category(callback: types.CallbackQuery, session: AsyncSession):
    category_id = int(callback.data.split('_')[-1])
    products = await orm_get_products(session, category_id)

    if not products:
        await callback.message.answer("В этой категории товары не найдены.")
        return

    for product in products:
        await callback.message.answer_photo(
            product.image,
            caption=f"<b>{product.name}</b>\nЦена: {product.price}\n{product.description}",
            parse_mode="HTML",
            reply_markup=get_product_buttons(category_id, product.id)
        )
    await callback.answer()






# Функция для добавления товара в корзину
async def add_to_cart(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession):
    """
    Добавляет товар в корзину для пользователя.
    :param callback: Объект CallbackQuery от нажатия кнопки пользователем
    :param callback_data: Данные callback (в т.ч. ID продукта)
    :param session: Асинхронная сессия для взаимодействия с базой данных
    """
    user = callback.from_user  # Получаем данные пользователя из callback
    # Добавляем пользователя в базу данных, если его нет
    await orm_add_user(
        session,
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=None,
    )
    # Добавляем товар в корзину пользователя
    await orm_add_to_cart(session, user_id=user.id, product_id=callback_data.product_id)
    # Отправляем уведомление пользователю
    await callback.answer("Товар добавлен в корзину.")


# Основной обработчик callback-запросов
@user_private_router.callback_query(MenuCallBack.filter())
async def user_menu(callback: types.CallbackQuery, callback_data: MenuCallBack, session: AsyncSession, state: FSMContext):
    """
    Основной обработчик для всех callback-запросов, связанных с меню.
    Обрабатывает добавление товаров в корзину, навигацию по меню и поиск.
    """
    # Проверка для кнопки "Поиск"
    if callback_data.menu_name == "search_products":
        await callback.message.answer("Введите ключевые слова для поиска:")
        await state.set_state(UserSearchProduct.keywords)  # Устанавливаем состояние для поиска по ключевым словам
        await callback.answer()
        return  # Завершаем обработчик, так как кнопка поиска не требует дальнейшей обработки меню

    # Если пользователь нажал кнопку для добавления товара в корзину
    if callback_data.menu_name == "add_to_cart":
        await add_to_cart(callback, callback_data, session)  # Вызываем функцию добавления товара в корзину
        return  # Выходим из обработчика, так как действие выполнено

    # Получаем текущее содержимое меню для данного уровня, категории и страницы
    media, reply_markup = await get_menu_content(
        session,
        level=callback_data.level,
        menu_name=callback_data.menu_name,
        category=callback_data.category,
        page=callback_data.page,
        product_id=callback_data.product_id,
        user_id=callback.from_user.id,
    )

    # Логика редактирования контента
    if isinstance(media, types.InputMediaPhoto):
        await callback.message.edit_media(media=media, reply_markup=reply_markup)
    else:
        await callback.message.edit_text(text=media, reply_markup=reply_markup)

    await callback.answer()




# Обработчик команды /start
@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message, session: AsyncSession):
    # Получаем основное меню из функции get_menu_content
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main")
    await message.answer_photo(media.media, caption=media.caption, reply_markup=reply_markup)



# FSM для поиска товаров
class UserSearchProduct(StatesGroup):
    keywords = State()


# Обработка команды для начала поиска
@user_private_router.message(F.text == "Поиск")
async def start_search(message: types.Message, state: FSMContext):
    await message.answer("Введите ключевые слова для поиска:")
    await state.set_state(UserSearchProduct.keywords)


# Обработка ввода ключевых слов для поиска
@user_private_router.message(UserSearchProduct.keywords, F.text)
async def search_products(message: types.Message, session: AsyncSession, state: FSMContext):
    """
    Обработчик ввода ключевых слов для поиска товаров.
    :param message: Сообщение пользователя с ключевыми словами
    :param session: Асинхронная сессия для взаимодействия с базой данных
    :param state: FSMContext для управления состояниями
    """
    search_query = message.text.strip()

    # Выполняем поиск товаров по ключевым словам
    products = await orm_get_products_by_keywords(session, search_query)

    # Если товары не найдены
    if not products:
        await message.answer("Товары не найдены.")
        await state.clear()  # Очищаем состояние
        return

    # Отображаем найденные товары
    for product in products:
        # Отправляем пользователю информацию о товаре
        await message.answer_photo(
            product.image,  # Фотография товара
            caption=f"<b>{product.name}</b>\n"
                    f"Описание: {product.description}\n"
                    f"Стоимость: {round(product.price, 2)}\n"
                    f"В наличии: {product.stock} шт.",
            parse_mode='HTML',
            reply_markup=get_product_buttons(product.category_id, product.id)  # Кнопки для взаимодействия
        )

    await state.clear()  # Очищаем состояние после завершения поиска




# Обработчик кнопки "Назад"
@user_private_router.callback_query(F.data == 'go_back')
async def go_back(callback: types.CallbackQuery):
    await callback.message.edit_text("Вы вернулись назад.")
    await callback.answer()


# Обработчик кнопки "Корзина"
@user_private_router.callback_query(F.data == 'cart_view')
async def view_cart(callback: types.CallbackQuery, session: AsyncSession):
    media, reply_markup = await carts(session, level=3, menu_name='cart', page=1, user_id=callback.from_user.id,
                                      product_id=None)
    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer()



# Обработчик кнопки "Купить"
@user_private_router.callback_query(F.data.startswith('buy_'))
async def buy_product(callback: types.CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split('_')[1])
    await orm_add_to_cart(session, user_id=callback.from_user.id, product_id=product_id)
    await callback.answer("Товар добавлен в корзину.")


@user_private_router.callback_query(F.data == 'main_menu')
async def return_to_main_menu(callback: types.CallbackQuery, session: AsyncSession):
    """
    Обработчик для возврата в главное меню.
    """
    # Получаем главное меню из функции get_menu_content
    media, reply_markup = await get_menu_content(session, level=0, menu_name="main")

    # Отправляем изображение с главным меню
    await callback.message.edit_media(media=media, reply_markup=reply_markup)
    await callback.answer()




