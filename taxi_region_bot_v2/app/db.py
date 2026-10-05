
import aiosqlite


DB_NAME = "taxi.db"


# ============================================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ
# ============================================================

async def init_db():

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                raw_text TEXT NOT NULL,
                ai_summary TEXT,
                phone TEXT,
                distance_km REAL,
                price REAL,
                yandex_price TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                driver_id INTEGER,
                driver_username TEXT,
                driver_first_name TEXT,
                admin_message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS driver_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                driver_id INTEGER NOT NULL,
                driver_username TEXT,
                driver_first_name TEXT,
                status TEXT DEFAULT 'waiting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ----------------------------------------------------
        # Таблица настроек тарифов
        # ----------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tariff_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                city_enabled INTEGER NOT NULL DEFAULT 1,
                intercity_enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )

        await db.execute(
            """
            INSERT OR IGNORE INTO tariff_settings
            (
                id,
                city_enabled,
                intercity_enabled
            )
            VALUES (1, 1, 1)
            """
        )

        # ----------------------------------------------------
        # Миграция существующей таблицы requests
        # ----------------------------------------------------

        cur = await db.execute(
            "PRAGMA table_info(requests)"
        )

        columns = await cur.fetchall()

        column_names = [
            column[1]
            for column in columns
        ]

        if "phone" not in column_names:

            await db.execute(
                """
                ALTER TABLE requests
                ADD COLUMN phone TEXT
                """
            )

        if "distance_km" not in column_names:

            await db.execute(
                """
                ALTER TABLE requests
                ADD COLUMN distance_km REAL
                """
            )

        if "price" not in column_names:

            await db.execute(
                """
                ALTER TABLE requests
                ADD COLUMN price REAL
                """
            )

        if "yandex_price" not in column_names:

            await db.execute(
                """
                ALTER TABLE requests
                ADD COLUMN yandex_price TEXT
                """
            )

        if "status" not in column_names:

            await db.execute(
                """
                ALTER TABLE requests
                ADD COLUMN status TEXT NOT NULL DEFAULT 'new'
                """
            )

        if "driver_id" not in column_names:

            await db.execute(
                """
                ALTER TABLE requests
                ADD COLUMN driver_id INTEGER
                """
            )

        if "driver_username" not in column_names:

            await db.execute(
                """
                ALTER TABLE requests
                ADD COLUMN driver_username TEXT
                """
            )

        if "driver_first_name" not in column_names:

            await db.execute(
                """
                ALTER TABLE requests
                ADD COLUMN driver_first_name TEXT
                """
            )

        if "admin_message_id" not in column_names:

            await db.execute(
                """
                ALTER TABLE requests
                ADD COLUMN admin_message_id INTEGER
                """
            )

        await db.commit()


# ============================================================
# НАСТРОЙКИ ТАРИФОВ
# ============================================================

async def get_tariff_settings():

    async with aiosqlite.connect(DB_NAME) as db:

        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            """
            SELECT
                city_enabled,
                intercity_enabled
            FROM tariff_settings
            WHERE id = 1
            """
        )

        row = await cur.fetchone()

        if not row:

            return {
                "city_enabled": True,
                "intercity_enabled": True
            }

        return {
            "city_enabled": bool(
                row["city_enabled"]
            ),
            "intercity_enabled": bool(
                row["intercity_enabled"]
            )
        }


async def set_city_enabled(enabled):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            UPDATE tariff_settings
            SET city_enabled = ?
            WHERE id = 1
            """,
            (
                1 if enabled else 0,
            )
        )

        await db.commit()


async def set_intercity_enabled(enabled):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            UPDATE tariff_settings
            SET intercity_enabled = ?
            WHERE id = 1
            """,
            (
                1 if enabled else 0,
            )
        )

        await db.commit()


# ============================================================
# СОЗДАНИЕ ЗАЯВКИ
# ============================================================

async def create_request(
        telegram_id,
        username,
        first_name,
        raw_text,
        ai_summary,
        distance_km=None,
        price=None
):

    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute(
            """
            INSERT INTO requests
            (
                telegram_id,
                username,
                first_name,
                raw_text,
                ai_summary,
                distance_km,
                price,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'new')
            """,
            (
                telegram_id,
                username,
                first_name,
                raw_text,
                ai_summary,
                distance_km,
                price
            )
        )

        await db.commit()

        return cur.lastrowid


# ============================================================
# СОХРАНИТЬ ID СООБЩЕНИЯ АДМИНА
# ============================================================

async def save_admin_message_id(
        request_id,
        admin_message_id
):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            UPDATE requests
            SET admin_message_id = ?
            WHERE id = ?
            """,
            (
                admin_message_id,
                request_id
            )
        )

        await db.commit()


# ============================================================
# СОХРАНЕНИЕ ТЕЛЕФОНА
# ============================================================

async def save_phone(
        telegram_id,
        phone
):

    async with aiosqlite.connect(DB_NAME) as db:

        db.row_factory = aiosqlite.Row

        # Берём самую свежую активную заявку
        # именно этого клиента.
        cur = await db.execute(
            """
            SELECT *
            FROM requests
            WHERE telegram_id = ?
            AND status = 'new'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                telegram_id,
            )
        )

        request = await cur.fetchone()

        if not request:
            return None

        await db.execute(
            """
            UPDATE requests
            SET phone = ?
            WHERE id = ?
            """,
            (
                phone,
                request["id"]
            )
        )

        await db.commit()

        # Получаем обновлённую заявку.
        cur = await db.execute(
            """
            SELECT *
            FROM requests
            WHERE id = ?
            """,
            (
                request["id"],
            )
        )

        return await cur.fetchone()


# ============================================================
# ПОЛУЧИТЬ ЗАКАЗ
# ============================================================

async def get_request(request_id):

    async with aiosqlite.connect(DB_NAME) as db:

        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            """
            SELECT *
            FROM requests
            WHERE id = ?
            """,
            (
                request_id,
            )
        )

        return await cur.fetchone()


# ============================================================
# ПОСЛЕДНЯЯ ЗАЯВКА
# ============================================================

async def get_last_request():

    async with aiosqlite.connect(DB_NAME) as db:

        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            """
            SELECT *
            FROM requests
            ORDER BY id DESC
            LIMIT 1
            """
        )

        return await cur.fetchone()


# ============================================================
# АКТИВНЫЕ ЗАКАЗЫ
# ============================================================

async def get_active_requests():

    async with aiosqlite.connect(DB_NAME) as db:

        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            """
            SELECT *
            FROM requests
            WHERE status IN ('new', 'taken')
            ORDER BY id DESC
            """
        )

        return await cur.fetchall()


# ============================================================
# ЗАЯВКИ ВОДИТЕЛЕЙ
# ============================================================

async def add_driver_request(
        request_id,
        driver_id,
        driver_username,
        driver_first_name
):

    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute(
            """
            SELECT status
            FROM requests
            WHERE id = ?
            """,
            (
                request_id,
            )
        )

        request = await cur.fetchone()

        if not request:
            return False, "not_found"

        if request[0] != "new":
            return False, "taken"

        cur = await db.execute(
            """
            SELECT id
            FROM driver_requests
            WHERE request_id = ?
            AND driver_id = ?
            AND status = 'waiting'
            """,
            (
                request_id,
                driver_id
            )
        )

        existing = await cur.fetchone()

        if existing:
            return False, "already_waiting"

        await db.execute(
            """
            INSERT INTO driver_requests
            (
                request_id,
                driver_id,
                driver_username,
                driver_first_name,
                status
            )
            VALUES (?, ?, ?, ?, 'waiting')
            """,
            (
                request_id,
                driver_id,
                driver_username,
                driver_first_name
            )
        )

        await db.commit()

        return True, "added"


async def get_driver_requests(request_id):

    async with aiosqlite.connect(DB_NAME) as db:

        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            """
            SELECT *
            FROM driver_requests
            WHERE request_id = ?
            AND status = 'waiting'
            ORDER BY id ASC
            """,
            (
                request_id,
            )
        )

        return await cur.fetchall()


async def assign_driver(
        request_id,
        driver_id,
        driver_username,
        driver_first_name
):

    async with aiosqlite.connect(DB_NAME) as db:

        cur = await db.execute(
            """
            UPDATE requests
            SET
                status = 'taken',
                driver_id = ?,
                driver_username = ?,
                driver_first_name = ?
            WHERE id = ?
            AND status = 'new'
            """,
            (
                driver_id,
                driver_username,
                driver_first_name,
                request_id
            )
        )

        if cur.rowcount == 0:

            await db.rollback()

            return False

        await db.execute(
            """
            UPDATE driver_requests
            SET status = 'assigned'
            WHERE request_id = ?
            AND driver_id = ?
            AND status = 'waiting'
            """,
            (
                request_id,
                driver_id
            )
        )

        await db.execute(
            """
            UPDATE driver_requests
            SET status = 'rejected'
            WHERE request_id = ?
            AND driver_id != ?
            AND status = 'waiting'
            """,
            (
                request_id,
                driver_id
            )
        )

        await db.commit()

        return True


# ============================================================
# СОВМЕСТИМОСТЬ СО СТАРОЙ ФУНКЦИЕЙ
# ============================================================

async def take_request(
        request_id,
        driver_id,
        driver_username,
        driver_first_name
):

    return await assign_driver(
        request_id,
        driver_id,
        driver_username,
        driver_first_name
    )


# ============================================================
# ЗАВЕРШИТЬ ЗАКАЗ
# ============================================================

async def complete_request(request_id):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            UPDATE requests
            SET status = 'done'
            WHERE id = ?
            """,
            (
                request_id,
            )
        )

        await db.commit()


# ============================================================
# ОТМЕНИТЬ ЗАКАЗ
# ============================================================

async def cancel_request(request_id):

    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute(
            """
            UPDATE requests
            SET status = 'cancelled'
            WHERE id = ?
            """,
            (
                request_id,
            )
        )

        await db.commit()


# ============================================================
# ИСТОРИЯ ЗАКАЗОВ
# ============================================================

async def get_order_history(limit=20):

    async with aiosqlite.connect(DB_NAME) as db:

        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            """
            SELECT *
            FROM requests
            WHERE status IN ('done', 'cancelled')
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (
                limit,
            )
        )

        return await cur.fetchall()

