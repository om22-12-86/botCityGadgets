from sqlalchemy import or_
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

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




async def orm_get_products(session: AsyncSession, category_id: int):    # Проверяем, что category_id не None
    if category_id is None:
        raise ValueError("category_id не может быть None")  # Выбрасываем ошибку, если category_id отсутствует

    # Преобразуем category_id в int только если оно не None
    query = select(Product).where(Product.category_id == int(category_id))
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
async def orm_add_user(session: AsyncSession, user_id: int, first_name: str | None = None, last_name: str | None = None, phone: str | None = None):
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    if result.first() is None:
        session.add(User(user_id=user_id, first_name=first_name, last_name=last_name, phone=phone))
        await session.commit()

# Работа с корзинами
async def orm_add_to_cart(session: AsyncSession, user_id: int, product_id: int):
    product_query = select(Product).where(Product.id == product_id)
    product = await session.execute(product_query)
    product = product.scalar()

    if not product or product.stock <= 0:
        return None  # Товар не доступен для добавления в корзину

    cart_query = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    cart = await session.execute(cart_query)
    cart = cart.scalar()

    if cart:
        if cart.stock < product.stock:
            cart.stock += 1
            await session.commit()
            return cart
        else:
            return None  # Превышено количество товара на складе
    else:
        cart = Cart(user_id=user_id, product_id=product_id, stock=1)  # Создаем новую корзину
        session.add(cart)

    product.stock -= 1  # Уменьшаем количество товара на складе
    await session.commit()
    return cart



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

