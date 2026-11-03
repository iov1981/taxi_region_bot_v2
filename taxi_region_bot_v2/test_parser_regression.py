import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.ai_parser import parse_request


async def main():
    text = """
Откуда: Пенза, улица Ленина, 25.
Куда: Пенза, улица Московская, 10.
Пассажиров: 2.
Время: как можно скорее.
"""

    result = await parse_request(text)

    print("\nРЕЗУЛЬТАТ РАЗБОРА:")
    for key, value in result.items():
        print(f"{key}: {value}")

    assert result.get("from_place") == "Пенза", result
    assert result.get("to_place") == "Пенза", result
    assert "Ленина" in str(result.get("from_address", "")), result
    assert "25" in str(result.get("from_address", "")), result
    assert "Московская" in str(result.get("to_address", "")), result
    assert "10" in str(result.get("to_address", "")), result
    assert str(result.get("passengers")) == "2", result
    assert result.get("time") == "как можно скорее", result

    print("\nOK: проверка пройдена")


if __name__ == "__main__":
    asyncio.run(main())
