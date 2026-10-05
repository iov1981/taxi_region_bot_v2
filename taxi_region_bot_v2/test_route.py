import asyncio

from app.services.route_service import get_route_distance


async def check_route(from_place, to_place):
    print()
    print("=" * 60)
    print(f"ОТКУДА: {from_place}")
    print(f"КУДА:   {to_place}")
    print("=" * 60)

    distance = await get_route_distance(
        from_place,
        to_place
    )

    if distance is None:
        print("❌ Маршрут не найден.")
    else:
        print(f"✅ Расстояние: {distance} км")


async def main():

    print("Проверка маршрутов")
    print()

    # Проверяем уже рабочий маршрут
    await check_route(
        "Пенза, Россия",
        "Воробьевка, Пензенская область, Россия"
    )

    # Проверяем адреса с улицей и домом
    await check_route(
        "Пенза, улица Ленина, 25",
        "Воробьевка, Советская, 10"
    )


if __name__ == "__main__":
    asyncio.run(main())