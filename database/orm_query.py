from sqlalchemy import or_
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import CallbackQuery
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import random
from decimal import Decimal
from datetime import datetime
from database.models import Banner, Cart, Category, Product, User, Order, OrderItem
import logging

logging.basicConfig(level=logging.INFO)



# Работа с баннерами (информационными страницами)
async def orm_add_banner_description(session: AsyncSession, data: dict):
    query = select(Banner)
    result = await session.execute(query)
    if result.first():
        return
    session.add_all([Banner(name=name, description=description) for name, description in data.items()])
    await session.commit()
    return True


async def orm_change_banner_image(session: AsyncSession, name: str, image: str):
    query = update(Banner).where(Banner.name == name).values(image=image)
    await session.execute(query)
    await session.commit()

async def orm_get_banner(session: AsyncSession, page: str):
    query = select(Banner).where(Banner.name == page)
    result = await session.execute(query)
    banner = result.scalar()
    if not banner or not banner.image:
        logging.info(f"Banner '{page}' не содержит корректного изображения или описания. Используются стандартные значения.")
        return Banner(image="DEFAULT_IMAGE_URL", description="Описание по умолчанию")
    return banner




async def orm_get_info_pages(session: AsyncSession):
    query = select(Banner)
    result = await session.execute(query)
    return result.scalars().all()



# Работа с категориями
async def orm_get_categories(session: AsyncSession):
    query = select(Category)
    result = await session.execute(query)
    return result.scalars().all()

async def orm_create_categories(session: AsyncSession, categories: list):
    query = select(Category)
    result = await session.execute(query)
    if result.first():
        return
    session.add_all([Category(name=name) for name in categories])
    await session.commit()




# Добавление и редактирование товаров
async def orm_add_product(session: AsyncSession, data: dict):
    try:
        obj = Product(
            name=data["name"],
            sku=data.get("sku"),
            description=data["description"],
            price=float(data["price"]),
            image=data["image"],
            category_id=int(data["category"]),
            stock=int(data["stock"])
        )
        session.add(obj)
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        logging.error(f"Error adding product: {e}")
        raise



async def orm_get_products(session: AsyncSession, category_id: int):
    query = select(Product).where(Product.category_id == category_id)
    result = await session.execute(query)
    return result.scalars().all()

async def orm_get_product(session: AsyncSession, product_id: int):
    query = select(Product).where(Product.id == product_id)
    result = await session.execute(query)
    return result.scalar()




async def orm_update_product(session: AsyncSession, product_id: int, data: dict):
    query = (
        update(Product)
        .where(Product.id == product_id)
        .values(
            name=data["name"],
            sku=data.get("sku"),
            description=data["description"],
            price=float(data["price"]),
            image=data["image"],
            category_id=int(data["category"]),
            stock=int(data["stock"])
        )
    )
    await session.execute(query)
    await session.commit()




async def orm_delete_product(session: AsyncSession, product_id: int):
    query = delete(Product).where(Product.id == product_id)
    await session.execute(query)
    await session.commit()



# Работа с пользователями
async def orm_add_user(session: AsyncSession, user_id: int, first_name: str = None, last_name: str = None, phone: str = None):
    """Добавление пользователя в базу данных, если он отсутствует."""
    existing_user = await session.execute(select(User).where(User.user_id == user_id))
    if not existing_user.scalar():
        user = User(user_id=user_id, first_name=first_name, last_name=last_name, phone=phone)
        session.add(user)
        await session.commit()


# Работа с корзинами
async def orm_add_to_cart(session: AsyncSession, user_id: int, product_id: int):
    """Добавление товара в корзину пользователя."""
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar()
    if not user:
        session.add(User(user_id=user_id))
        await session.commit()

    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar()
    if not product or product.stock <= 0:
        return None

    result = await session.execute(select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id))
    cart_item = result.scalar()
    if cart_item:
        if cart_item.stock < product.stock:
            cart_item.stock += 1
        else:
            logging.warning("Insufficient stock.")
            return None
    else:
        session.add(Cart(user_id=user_id, product_id=product_id, stock=1))

    product.stock -= 1
    try:
        await session.commit()
        return cart_item
    except IntegrityError as e:
        await session.rollback()
        logging.error(f"Error adding to cart: {e}")
        return None






async def orm_get_user_carts(session: AsyncSession, user_id: int):
    """Получение корзины пользователя с деталями о продуктах."""
    query = select(Cart).filter(Cart.user_id == user_id).options(joinedload(Cart.product))
    result = await session.execute(query)
    return result.scalars().all()

async def orm_delete_from_cart(session: AsyncSession, user_id: int, product_id: int):
    query = delete(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    await session.execute(query)
    await session.commit()  # Убедитесь, что коммит вызывается




# Ваша функция orm_reduce_product_in_cart
async def orm_reduce_product_in_cart(session: AsyncSession, user_id: int, product_id: int):
    """Уменьшение количества товара в корзине пользователя."""
    result = await session.execute(select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id))
    cart = result.scalar()
    if not cart:
        return

    if cart.stock > 1:
        cart.stock -= 1
        await session.commit()
    else:
        await orm_delete_from_cart(session, user_id, product_id)

    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar()
    if product:
        product.stock += 1
        await session.commit()


async def orm_get_products_by_keywords(session: AsyncSession, keywords: str):
    """Поиск продуктов по ключевым словам."""
    keyword_list = keywords.split()
    query = select(Product).where(
        or_(
            *[Product.name.ilike(f"%{keyword}%") for keyword in keyword_list],
            *[Product.description.ilike(f"%{keyword}%") for keyword in keyword_list]
        )
    )
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_user_orders(session: AsyncSession, user_id: int):
    """Получение всех заказов пользователя с их деталями."""
    query = select(Order).filter(Order.user_id == user_id).options(selectinload(Order.items))  # Загрузка элементов заказа
    result = await session.execute(query)
    return result.scalars().all()



# Функция для получения всех заказов
async def get_orders(session: AsyncSession, status: str = None):
    """
    Получение всех заказов, с фильтрацией по статусу (если указано).
    """
    query = select(Order)
    if status:
        query = query.filter(Order.status == status)
    result = await session.execute(query)
    return result.scalars().all()



# Функция для получения заказов по статусу
async def get_orders_by_status(session: AsyncSession, status: str):
    """
    Получение заказов по статусу.
    """
    query = select(Order).filter(Order.status == status)
    result = await session.execute(query)
    return result.scalars().all()






# Оповещение пользователя о создании заказа
async def send_order_notification(bot, user_id, order_number):
    """Отправка уведомления пользователю о создании заказа."""
    message = f"Ваш заказ с номером {order_number} был успешно создан.\n" \
              f"Статус: В обработке."
    await bot.send_message(user_id, message)


# Функция для создания заказа
async def create_order_from_cart(session: AsyncSession, user_id: int, bot):
    try:
        # Получение корзины пользователя
        carts = await orm_get_user_carts(session, user_id)
        if not carts:
            raise ValueError("Корзина пользователя пуста.")

        # Генерация уникального номера заказа
        order_number = ''.join(random.choices('0123456789', k=7))

        # Создание нового заказа
        order = Order(
            user_id=user_id,
            order_number=order_number,
            status="В обработке",  # Статус по умолчанию
            total_cost=Decimal(0),
            created=datetime.now(),
            updated=datetime.now()
        )
        session.add(order)
        await session.flush()  # Получаем ID созданного заказа, не фиксируя транзакцию

        # Перенос элементов из корзины в заказ и расчет общей стоимости
        total_cost = Decimal(0)
        for cart in carts:
            order_item = OrderItem(
                order_id=order.id,  # Используем ID созданного заказа
                product_id=cart.product_id,
                stock=cart.stock,
                price=cart.product.price
            )
            session.add(order_item)
            total_cost += Decimal(cart.stock) * Decimal(cart.product.price)

        # Обновление стоимости заказа
        order.total_cost = total_cost

        # Коммит изменений заказа и добавленных элементов
        await session.commit()

        # Очистка корзины пользователя после фиксации заказа
        await orm_clear_user_cart(session, user_id)
        await session.commit()  # Фиксация очистки корзины

        logging.info(f"Заказ с номером {order_number} успешно создан и корзина очищена для пользователя {user_id}")

        # Отправка уведомления пользователю
        await send_order_notification(bot, user_id, order_number)

        return order

    except (IntegrityError, ValueError) as e:
        logging.error(f"Ошибка при создании заказа: {e}")
        await session.rollback()
        raise e





async def orm_clear_user_cart(session: AsyncSession, user_id: int):
    try:
        query = delete(Cart).where(Cart.user_id == user_id)
        result = await session.execute(query)
        await session.commit()  # Коммит для фиксации изменений
        logging.info(f"Удалено {result.rowcount} строк из корзины пользователя {user_id}")
    except Exception as e:
        logging.error(f"Ошибка при очистке корзины пользователя {user_id}: {e}")
        await session.rollback()
        raise e







async def update_order(session: AsyncSession, order_id: int, new_status: str, total_cost: float = None):
    update_query = (
        update(Order)
        .where(Order.id == order_id)
        .values(
            status=new_status,
            updated=datetime.now()
        )
    )

    if total_cost is not None:
        update_query = update_query.values(total_cost=total_cost)

    await session.execute(update_query)
    await session.commit()

# Функция для обновления статуса заказа
async def update_order_status(session: AsyncSession, order_id: int, status: str):
    """
    Обновление статуса заказа в базе данных.
    """
    try:
        query = update(Order).where(Order.id == order_id).values(status=status, updated=datetime.now())
        result = await session.execute(query)
        await session.commit()
        return status
    except Exception as e:
        logging.error(f"Ошибка обновления статуса заказа #{order_id}: {e}")
        return "Ошибка при обновлении статуса."


# Если заказов нет, выводим сообщение, если есть — список заказов

# Функция для получения заказов пользователя
async def get_user_orders(session: AsyncSession, user_id: int):
    """Функция для получения заказов пользователя"""
    result = await session.execute(
        select(Order).filter_by(user_id=user_id).options(selectinload(Order.items).selectinload(OrderItem.product))
    )
    orders = result.scalars().all()

    if not orders:
        return "У вас нет активных заказов.", None

    # Формируем текст с заказами
    orders_text = "Ваши заказы:\n"
    for order in orders:
        created_time = order.created.strftime("%d.%m.%Y %H:%M")
        orders_text += (
            f"Заказ №{order.order_number}\n"
            f"Дата и время заказа: {created_time}\n"
            f"Статус: {order.status}\n"
            f"Общая стоимость: {order.total_cost:.2f} ₽\n"
        )
        for item in order.items:
            product = item.product
            orders_text += f"{product.name} (Количество: {item.stock}, Цена: {item.price} ₽)\n"
        orders_text += "\n"

    # Кнопка для возврата к главному меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="На главную 🏠", callback_data="main_menu")]
    ])

    return orders_text, keyboard


# Функция для отображения заказов пользователю (предполагается, что она уже есть)
async def display_orders_to_user(session, message, orders):
    """
    Отображает заказы пользователю с возможностью изменять статус и удалять заказы.
    """
    for order in orders:
        # Получаем данные о пользователе
        user = await get_user_by_id(session, order.user_id)
        user_info = f"Пользователь: {user.first_name} {user.last_name} (ID: {user.user_id})" if user else "Пользователь: Неизвестен"

        # Получаем товары заказа
        order_items = await get_order_items(session, order.id)
        items_info = "\n".join(
            [f"{item.product.name} — {item.product.sku}\nКоличество: {item.stock}, Цена: {item.price} ₽" for item in
             order_items])

        # Рассчитываем общую сумму заказа
        total_sum = sum(item.stock * item.price for item in order_items)

        # Время создания заказа
        created_time = order.created.strftime("%d.%m.%Y %H:%M")

        # Формируем сообщение для отправки
        order_details = (
            f"Заказ № {order.order_number}\n"
            f"{user_info}\n"
            f"Дата и время заказа: {created_time}\n"
            f"Статус: {order.status}\n"
            f"Товары:\n{items_info}\n"
            f"Общая сумма заказа: {total_sum:.2f} ₽"
        )

        # Создаем кнопки для управления заказом
        buttons = [
            InlineKeyboardButton(text="Отмена", callback_data=f"order_{order.id}_cancel"),
            InlineKeyboardButton(text="Готов", callback_data=f"order_{order.id}_ready"),
            InlineKeyboardButton(text="Выдан", callback_data=f"order_{order.id}_delivered"),
            InlineKeyboardButton(text="Удалить", callback_data=f"order_{order.id}_delete")  # Кнопка для удаления
        ]

        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons], row_width=2)  # Правильная инициализация

        # Отправляем сообщение с информацией о заказе и кнопками
        await message.answer(order_details, reply_markup=keyboard)




async def get_all_orders(session: AsyncSession):
    from database.models import Order
    query = select(Order).order_by(Order.created.desc())
    result = await session.execute(query)
    orders = result.scalars().all()

    if not orders:
        return "Нет заказов.", None

    orders_text = "Все заказы:\n"
    for order in orders:
        orders_text += f"Заказ №{order.order_number} — Статус: {order.status}, Общая стоимость: {order.total_cost} ₽\n"

    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("Обновить", callback_data="refresh_orders"))
    return orders_text, keyboard



async def get_user_by_id(session: AsyncSession, user_id: int):
    from database.models import User  # Предполагается, что модель User существует
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    return result.scalars().first()


async def get_order_items(session: AsyncSession, order_id: int):
    from database.models import OrderItem, Product  # Предполагается, что есть модель OrderItem и Product
    query = (
        select(OrderItem)
        .options(selectinload(OrderItem.product))  # Используйте selectinload для загрузки связанных данных
        .where(OrderItem.order_id == order_id)
    )
    result = await session.execute(query)
    return result.scalars().all()


# Функция для отображения заказов
async def display_orders(message, orders):
    """
    Отображение заказов с их деталями.
    """
    if not orders:
        await message.answer("Нет заказов с выбранным статусом.")
        return

    for order in orders:
        user_info = f"Пользователь: {order.user.first_name} {order.user.last_name} (ID: {order.user.user_id})" if order.user else "Пользователь: Неизвестен"
        order_items = await get_order_items(message.bot.get('db_session'), order.id)
        items_info = "\n".join([f"{item.product.name} — {item.product.sku}\nКоличество: {item.stock}, Цена: {item.price} ₽" for item in order_items])
        total_sum = sum(item.stock * item.price for item in order_items)

        # Кнопки для изменения статуса заказа и удаления
        buttons = [
            InlineKeyboardButton(text="Отмена", callback_data=f"order_{order.id}_cancel"),
            InlineKeyboardButton(text="Готов", callback_data=f"order_{order.id}_ready"),
            InlineKeyboardButton(text="Выдан", callback_data=f"order_{order.id}_delivered"),
            InlineKeyboardButton(text="Удалить", callback_data=f"order_{order.id}_delete")  # Кнопка для удаления
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button] for button in buttons])

        await message.answer(
            f"Заказ № {order.order_number}\n"
            f"{user_info}\n"
            f"Статус: {order.status}\n"
            f"Товары:\n{items_info}\n"
            f"Общая сумма заказа: {total_sum:.2f} ₽",
            reply_markup=keyboard
        )


# Функция для удаления заказа

async def delete_order(session: AsyncSession, callback_query: CallbackQuery):
    callback_data = callback_query.data
    if not callback_data.startswith("delete_order_"):
        return

    # Извлекаем id заказа
    order_id = int(callback_data.split("_")[-1])

    # Получаем заказ
    query = select(Order).where(Order.id == order_id)
    result = await session.execute(query)
    order = result.scalar_one_or_none()

    if not order:
        await callback_query.answer("Этот заказ не найден.")
        return

    # Удаляем товары из заказа
    await session.execute(select(OrderItem).filter(OrderItem.order_id == order_id).delete())

    # Удаляем сам заказ
    await session.execute(select(Order).filter(Order.id == order_id).delete())
    await session.commit()

    # Подтверждаем удаление
    await callback_query.answer("Заказ успешно удален.")

    # Отправляем обновленное сообщение
    await send_user_orders(session, order.user_id, callback_query.message)



# Получаем все заказы пользователя и отправляем их с кнопками
async def send_user_orders(session: AsyncSession, user_id: int, message: types.Message):
    # Получаем все заказы пользователя
    query = select(Order).where(Order.user_id == user_id)
    result = await session.execute(query)
    orders = result.scalars().all()

    if not orders:
        await message.answer("У вас нет заказов.")
        return

    # Для каждого заказа создаем сообщение с кнопками
    for order in orders:
        order_info = f"Заказ №{order.order_number}\nСтатус: {order.status}\nОбщая стоимость: {order.total_cost} руб."
        keyboard = await generate_order_buttons(order.id)
        await message.answer(order_info, reply_markup=keyboard)
