from sqlalchemy import or_
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import random
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
    existing_user = await session.execute(select(User).where(User.user_id == user_id))
    if not existing_user.scalar():
        user = User(user_id=user_id, first_name=first_name, last_name=last_name, phone=phone)
        session.add(user)
        await session.commit()


# Работа с корзинами
async def orm_add_to_cart(session: AsyncSession, user_id: int, product_id: int):
    user_query = select(User).where(User.user_id == user_id)
    user = (await session.execute(user_query)).scalar()
    if not user:
        session.add(User(user_id=user_id))
        await session.commit()

    product_query = select(Product).where(Product.id == product_id)
    product = (await session.execute(product_query)).scalar()
    if not product or product.stock <= 0:
        return None

    cart_query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    cart_item = (await session.execute(cart_query)).scalar()

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
    except IntegrityError as e:
        await session.rollback()
        logging.error(f"Error adding to cart: {e}")
        return None
    return cart_item






async def orm_get_user_carts(session: AsyncSession, user_id):
    query = select(Cart).filter(Cart.user_id == user_id).options(joinedload(Cart.product))
    result = await session.execute(query)
    return result.scalars().all()

async def orm_delete_from_cart(session: AsyncSession, user_id: int, product_id: int):
    query = delete(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    await session.execute(query)
    await session.commit()

# Ваша функция orm_reduce_product_in_cart
async def orm_reduce_product_in_cart(session: AsyncSession, user_id: int, product_id: int):
    # Получаем элемент корзины
    cart_query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    cart_result = await session.execute(cart_query)
    cart = cart_result.scalar()
    if not cart:
        return  # Выходим, если элемента в корзине нет

    # Уменьшаем количество товара в корзине
    if cart.stock > 1:
        cart.stock -= 1
        await session.commit()  # Фиксируем изменения
    else:
        await orm_delete_from_cart(session, user_id, product_id)  # Удаляем товар из корзины, если он был последний

    # Обновляем количество товара на складе
    product_query = select(Product).where(Product.id == product_id)
    product_result = await session.execute(product_query)
    product = product_result.scalar()
    if product:
        product.stock += 1  # Возвращаем товар на склад
        await session.commit()  # Фиксируем изменения в базе данных


async def orm_get_products_by_keywords(session: AsyncSession, keywords: str):
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
    # Генерация номера заказа
    order_number = ''.join(random.choices('0123456789', k=7))
    timestamp = datetime.now()

    # Создаем новый заказ
    new_order = Order(
        user_id=user_id,
        order_number=order_number,
        status="В обработке",
        created=timestamp,
        updated=timestamp
    )
    session.add(new_order)
    await session.flush()  # Необходим для получения `new_order.id`

    # Подгружаем корзину пользователя с продуктами
    cart_query = (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(selectinload(Cart.product))
    )
    cart_items = (await session.execute(cart_query)).scalars().all()

    if not cart_items:
        return None  # Пустая корзина, возвращаем None

    # Перенос товаров из корзины в заказ
    for item in cart_items:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item.product_id,
            stock=item.stock,
            price=item.product.price
        )
        session.add(order_item)
        await session.delete(item)  # Удаляем товар из корзины

    await session.commit()
    return new_order


async def get_user_orders(session: AsyncSession, user_id: int):
    query = select(Order).filter(Order.user_id == user_id).order_by(Order.created.desc())
    result = await session.execute(query)
    return result.scalars().all()


async def update_order_status(session: AsyncSession, order_id: int, status: str):
    query = update(Order).where(Order.id == order_id).values(status=status, updated=datetime.now())
    await session.execute(query)
    await session.commit()
    return status




