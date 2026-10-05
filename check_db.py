import sqlite3

DB = r"G:\taxi_region_bot_v2\taxi_region_bot_v2\taxi.db"

conn = sqlite3.connect(DB)

for table in ["requests", "driver_requests"]:

    print("\n" + "=" * 60)
    print(f"ТАБЛИЦА: {table}")
    print("=" * 60)

    row = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type='table' AND name=?",
        (table,)
    ).fetchone()

    if row:
        print(row[0])
    else:
        print("Таблица не найдена")

conn.close()