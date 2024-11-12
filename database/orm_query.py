from sqlalchemy import or_
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




# database/orm_query.py
async def get_orders(session: AsyncSession):
    query = select(Order)  # или другой запрос, если нужно
    result = await session.execute(query)
    return result.scalars().all()


async def create_order_from_cart(session: AsyncSession, user_id: int):
    # Перемещение импорта внутрь функции для предотвращения циклического импорта
    from database.orm_query import orm_get_user_carts, orm_clear_user_cart

    try:
        # Получение корзины пользователя
        carts = await orm_get_user_carts(session, user_id)
        if not carts:
            raise ValueError("Корзина пользователя пуста.")

        # Создание нового заказа
        order_number = ''.join(random.choices('0123456789', k=7))
        order = Order(
            user_id=user_id,
            order_number=order_number,
            status="В обработке",
            total_cost=Decimal(0),
            created=datetime.now(),
            updated=datetime.now()
        )
        session.add(order)
        await session.flush()  # Присваиваем ID заказу и отправляем изменения в БД
        logging.info(f"Создан заказ с ID: {order.id}")

        # Проверка ID заказа перед коммитом
        if not order.id:
            raise ValueError("Не удалось создать заказ. ID заказа отсутствует.")

        # Перенос элементов корзины в заказ
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
        await session.commit()  # Коммит всех изменений

        # Очистка корзины пользователя
        await orm_clear_user_cart(session, user_id)
        logging.info(f"Заказ с номером {order_number} успешно создан для пользователя {user_id}")

        return order

    except (IntegrityError, ValueError) as e:
        logging.error(f"Ошибка при создании заказа: {e}")
        await session.rollback()  # Откат транзакции при ошибке
        raise e






async def orm_clear_user_cart(session: AsyncSession, user_id: int):
    query = delete(Cart).where(Cart.user_id == user_id)
    await session.execute(query)
    await session.commit()





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

async def update_order_status(session: AsyncSession, order_id: int, status: str):
    """Обновление статуса заказа."""
    query = update(Order).where(Order.id == order_id).values(status=status, updated=datetime.now())
    await session.execute(query)
    await session.commit()
    return status


async def get_user_orders(session: AsyncSession, user_id: int):
    query = select(Order).filter(Order.user_id == user_id).order_by(Order.created.desc())
    result = await session.execute(query)
    orders = result.scalars().all()

    if not orders:
        return "У вас нет заказов.", None

    # Формирование текста для вывода информации о заказах
    order_texts = []
    for order in orders:
        order_texts.append(
            f"Заказ #{order.order_number}, статус: {order.status}, сумма: {order.total_cost} ₽, создан: {order.created}"
        )

    return "\n\n".join(order_texts), None







