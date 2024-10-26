from sqlalchemy import or_
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from database.models import Banner, Cart, Category, Product, User

# Работа с баннерами (информационными страницами)
async def orm_add_banner_description(session: AsyncSession, data: dict):
    query = select(Banner)
    result = await session.execute(query)
    if result.first():  # Если данные уже существуют, обновите их вместо завершения
        return  # Либо обновите существующий баннер, если это необходимо
    session.add_all([Banner(name=name, description=description) for name, description in data.items()])
    await session.commit()



async def orm_change_banner_image(session: AsyncSession, name: str, image: str):
    query = update(Banner).where(Banner.name == name).values(image=image)
    await session.execute(query)
    await session.commit()


async def orm_get_banner(session: AsyncSession, page: str):
    query = select(Banner).where(Banner.name == page)
    result = await session.execute(query)
    return result.scalar()


async def orm_get_info_pages(session: AsyncSession):
    query = select(Banner)
    result = await session.execute(query)
    return result.scalars().all()

# Работа с категориями
async def orm_get_categories(session: AsyncSession):
    query = select(Category)
    result = await session.execute(query)
    categories = result.scalars().all()

    # Убедитесь, что функция возвращает пустой список, а не None
    return categories if categories else []


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
            description=data["description"],
            price=float(data["price"]),
            image=data["image"],
            category_id=int(data["category"]),
            stock=int(data["stock"])
        )
        session.add(obj)
        await session.commit()
    except Exception as e:
        await session.rollback()
        print(f"Ошибка при добавлении продукта: {e}")
        raise



async def orm_get_products(session: AsyncSession, category_id: int):
    if category_id is None:
        return []  # Вернуть пустой список
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
    # Проверка существования пользователя
    existing_user = await session.execute(select(User).where(User.user_id == user_id))
    if not existing_user.scalar():
        # Добавляем пользователя, если его еще нет
        user = User(user_id=user_id, first_name=first_name, last_name=last_name, phone=phone)
        session.add(user)
        await session.commit()



# Работа с корзинами
async def orm_add_to_cart(session: AsyncSession, user_id: int, product_id: int):
    # Проверяем, существует ли пользователь в базе данных
    user_query = select(User).where(User.user_id == user_id)
    user = (await session.execute(user_query)).scalar()

    # Если пользователя нет, добавляем его
    if not user:
        session.add(User(user_id=user_id))
        try:
            await session.commit()  # Сохраняем изменения для пользователя
            print("Пользователь успешно добавлен.")
            user = (await session.execute(user_query)).scalar()  # Повторная проверка
        except IntegrityError as e:
            await session.rollback()
            print(f"Ошибка при добавлении пользователя: {e}")
            return None

    if not user:
        print("Ошибка: пользователь не добавлен в базу данных.")
        return None

    # Проверка наличия продукта на складе
    product_query = select(Product).where(Product.id == product_id)
    product = (await session.execute(product_query)).scalar()

    if not product:
        print("Товар не найден.")
        return None
    elif product.stock <= 0:
        print("Товар недоступен для добавления в корзину.")
        return None

    # Проверяем, есть ли товар в корзине пользователя
    cart_query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    cart_item = (await session.execute(cart_query)).scalar()

    # Если товар уже есть в корзине, увеличиваем количество, иначе добавляем новый товар в корзину
    if cart_item:
        if cart_item.stock < product.stock:
            cart_item.stock += 1
        else:
            print("Недостаточно товара на складе.")
            return None
    else:
        # Добавляем новый товар в корзину
        new_cart_item = Cart(user_id=user_id, product_id=product_id, stock=1)
        session.add(new_cart_item)

    # Уменьшаем количество товара на складе
    product.stock -= 1
    try:
        await session.commit()
        print("Товар успешно добавлен в корзину.")
    except IntegrityError as e:
        await session.rollback()
        print(f"Ошибка при добавлении товара в корзину: {e}")
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


async def orm_reduce_product_in_cart(session: AsyncSession, user_id: int, product_id: int):
    query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    cart = await session.execute(query)
    cart = cart.scalar()

    if not cart:
        return

    if cart.stock > 1:
        cart.stock -= 1
        await session.commit()

        # Увеличиваем количество товара на складе
        product_query = select(Product).where(Product.id == product_id)
        product = await session.execute(product_query)
        product = product.scalar()
        if product:
            product.stock += 1
            await session.commit()

        return True
    else:
        await orm_delete_from_cart(session, user_id, product_id)
        await session.commit()

        # Увеличиваем количество товара на складе при удалении из корзины
        product_query = select(Product).where(Product.id == product_id)
        product = await session.execute(product_query)
        product = product.scalar()
        if product:
            product.stock += 1
            await session.commit()

        return False


async def orm_get_products_by_keywords(session: AsyncSession, keywords: str):
    """
    Функция для поиска товаров по ключевым словам.
    :param session: Асинхронная сессия для взаимодействия с базой данных
    :param keywords: Ключевые слова для поиска
    :return: Список товаров, соответствующих ключевым словам
    """
    keyword_list = keywords.split()  # Разбиваем ключевые слова на список
    query = select(Product).where(
        or_(
            *[Product.name.ilike(f"%{keyword}%") for keyword in keyword_list],
            *[Product.description.ilike(f"%{keyword}%") for keyword in keyword_list]
        )
    )
    result = await session.execute(query)
    return result.scalars().all()
