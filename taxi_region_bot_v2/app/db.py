import aiosqlite
from typing import Optional, List, Dict, Any, Tuple

from app.config import get_commission_percent

DB_NAME = "taxi.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                phone TEXT,
                first_name TEXT,
                username TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS blacklist (
                telegram_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS drivers (
                driver_id INTEGER PRIMARY KEY,
                driver_name TEXT,
                driver_username TEXT,
                car_info TEXT,
                rating REAL DEFAULT 5.0,
                rating_count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                driver_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

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
                commission REAL DEFAULT 0,
                driver_payout REAL DEFAULT 0,
                yandex_price TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                driver_id INTEGER,
                driver_username TEXT,
                driver_first_name TEXT,
                admin_message_id INTEGER,
                rating INTEGER,
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
            INSERT OR IGNORE INTO tariff_settings (id, city_enabled, intercity_enabled)
            VALUES (1, 1, 1)
            """
        )

        cur = await db.execute("PRAGMA table_info(requests)")
        columns = await cur.fetchall()
        column_names = [col[1] for col in columns]

        for col_name, col_type in [
            ("phone", "TEXT"),
            ("distance_km", "REAL"),
            ("price", "REAL"),
            ("commission", "REAL DEFAULT 0"),
            ("driver_payout", "REAL DEFAULT 0"),
            ("yandex_price", "TEXT"),
            ("status", "TEXT NOT NULL DEFAULT 'new'"),
            ("driver_id", "INTEGER"),
            ("driver_username", "TEXT"),
            ("driver_first_name", "TEXT"),
            ("admin_message_id", "INTEGER"),
            ("rating", "INTEGER"),
        ]:
            if col_name not in column_names:
                await db.execute(f"ALTER TABLE requests ADD COLUMN {col_name} {col_type}")

        await db.commit()


# --- ЧЁРНЫЙ СПИСОК ---

async def ban_user(telegram_id: int, reason: str = "Нарушение правил сервиса"):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO blacklist (telegram_id, reason)
            VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                reason = excluded.reason,
                banned_at = CURRENT_TIMESTAMP
            """,
            (telegram_id, reason.strip())
        )
        await db.commit()


async def unban_user(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("DELETE FROM blacklist WHERE telegram_id = ?", (telegram_id,))
        await db.commit()
        return cur.rowcount > 0


async def get_ban_info(telegram_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM blacklist WHERE telegram_id = ?", (telegram_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


# --- КЛИЕНТЫ ---

async def get_user_phone(telegram_id: int) -> Optional[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT phone FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cur.fetchone()
        return str(row["phone"]).strip() if row and row["phone"] else None


async def save_user_phone(telegram_id: int, phone: str, first_name: str = "", username: str = ""):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO users (telegram_id, phone, first_name, username)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                phone = excluded.phone,
                first_name = excluded.first_name,
                username = excluded.username,
                updated_at = CURRENT_TIMESTAMP
            """,
            (telegram_id, phone.strip(), first_name, username)
        )
        await db.commit()


# --- ВОДИТЕЛИ ---

async def set_driver_car(driver_id: int, car_info: str, driver_name: str = "", driver_username: str = ""):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO drivers (driver_id, car_info, driver_name, driver_username)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(driver_id) DO UPDATE SET
                car_info = excluded.car_info,
                driver_name = CASE WHEN excluded.driver_name != '' THEN excluded.driver_name ELSE drivers.driver_name END,
                driver_username = CASE WHEN excluded.driver_username != '' THEN excluded.driver_username ELSE drivers.driver_username END,
                updated_at = CURRENT_TIMESTAMP
            """,
            (driver_id, car_info.strip(), driver_name, driver_username)
        )
        await db.commit()


async def get_driver_profile(driver_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM drivers WHERE driver_id = ?", (driver_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_all_drivers() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM drivers ORDER BY updated_at DESC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def save_order_rating(request_id: int, client_id: int, driver_id: int, rating: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT rating FROM requests WHERE id = ?", (request_id,))
        req = await cur.fetchone()
        if req and req[0] is not None:
            return False

        await db.execute("UPDATE requests SET rating = ? WHERE id = ?", (rating, request_id))
        await db.execute(
            "INSERT INTO reviews (request_id, client_id, driver_id, rating) VALUES (?, ?, ?, ?)",
            (request_id, client_id, driver_id, rating)
        )

        cur_avg = await db.execute(
            "SELECT AVG(rating), COUNT(rating) FROM reviews WHERE driver_id = ?",
            (driver_id,)
        )
        avg_row = await cur_avg.fetchone()
        if avg_row and avg_row[1] > 0:
            avg_score = round(float(avg_row[0]), 2)
            rev_count = int(avg_row[1])
            await db.execute(
                """
                INSERT INTO drivers (driver_id, rating, rating_count)
                VALUES (?, ?, ?)
                ON CONFLICT(driver_id) DO UPDATE SET
                    rating = excluded.rating,
                    rating_count = excluded.rating_count
                """,
                (driver_id, avg_score, rev_count)
            )

        await db.commit()
        return True


# --- ЗАКАЗЫ ---

async def create_request(
    telegram_id: int,
    username: Optional[str],
    first_name: Optional[str],
    raw_text: str,
    ai_summary: str,
    distance_km: Optional[float] = None,
    price: Optional[int] = None,
    phone: Optional[str] = None
) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            INSERT INTO requests (
                telegram_id, username, first_name, raw_text,
                ai_summary, distance_km, price, phone, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
            """,
            (telegram_id, username, first_name, raw_text, ai_summary, distance_km, price, phone)
        )
        await db.commit()
        return cur.lastrowid


async def get_request(request_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_last_request() -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM requests ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_active_requests() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM requests WHERE status IN ('new', 'taken', 'arrived') ORDER BY id DESC"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_order_history(limit: int = 20) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM requests ORDER BY id DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_all_orders_for_export() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT 
                r.id,
                r.created_at,
                r.telegram_id,
                r.first_name,
                r.phone,
                r.raw_text,
                r.distance_km,
                r.price,
                r.commission,
                r.driver_payout,
                r.status,
                r.driver_first_name,
                r.driver_username,
                r.rating,
                d.car_info
            FROM requests r
            LEFT JOIN drivers d ON r.driver_id = d.driver_id
            ORDER BY r.id DESC
            """
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def save_admin_message_id(request_id: int, admin_message_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE requests SET admin_message_id = ? WHERE id = ?", (admin_message_id, request_id))
        await db.commit()


async def save_phone(telegram_id: int, phone: str) -> Optional[Dict[str, Any]]:
    phone_clean = phone.strip()
    await save_user_phone(telegram_id, phone_clean)

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM requests
            WHERE telegram_id = ? AND status IN ('new', 'taken', 'arrived')
            ORDER BY id DESC LIMIT 1
            """,
            (telegram_id,)
        )
        request = await cur.fetchone()
        if not request:
            return None

        req_id = request["id"]
        await db.execute("UPDATE requests SET phone = ? WHERE id = ?", (phone_clean, req_id))
        await db.commit()

        cur_updated = await db.execute("SELECT * FROM requests WHERE id = ?", (req_id,))
        updated_row = await cur_updated.fetchone()
        return dict(updated_row) if updated_row else None


# --- ОЧИСТКА ВСЕХ ЗАКАЗОВ ---

async def clear_all_orders_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM requests")
        await db.execute("DELETE FROM driver_requests")
        await db.execute("DELETE FROM reviews")
        await db.execute("DELETE FROM sqlite_sequence WHERE name IN ('requests', 'driver_requests', 'reviews')")
        await db.commit()


# --- СТАТИСТИКА И ОТКЛИКИ ---

async def get_today_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT 
                COUNT(*) as total_orders,
                TOTAL(price) as total_revenue,
                TOTAL(commission) as total_commission,
                TOTAL(driver_payout) as total_driver_payout,
                TOTAL(distance_km) as total_distance
            FROM requests
            WHERE status = 'done'
              AND DATE(created_at, 'localtime') = DATE('now', 'localtime')
            """
        )
        row = await cur.fetchone()

        cur_all = await db.execute(
            "SELECT COUNT(*) as created_count FROM requests WHERE DATE(created_at, 'localtime') = DATE('now', 'localtime')"
        )
        row_all = await cur_all.fetchone()

        return {
            "done_orders": row["total_orders"] if row else 0,
            "total_revenue": round(row["total_revenue"]) if row else 0,
            "total_commission": round(row["total_commission"]) if row else 0,
            "total_driver_payout": round(row["total_driver_payout"]) if row else 0,
            "total_distance": round(row["total_distance"], 1) if row else 0.0,
            "created_orders": row_all["created_count"] if row_all else 0
        }


async def add_driver_request(
    request_id: int,
    driver_id: int,
    driver_username: Optional[str],
    driver_first_name: Optional[str]
) -> Tuple[bool, str]:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT status FROM requests WHERE id = ?", (request_id,))
        request = await cur.fetchone()

        if not request:
            return False, "not_found"
        if request[0] != "new":
            return False, "taken"

        cur = await db.execute(
            "SELECT id FROM driver_requests WHERE request_id = ? AND driver_id = ? AND status = 'waiting'",
            (request_id, driver_id)
        )
        existing = await cur.fetchone()
        if existing:
            return False, "already_waiting"

        await db.execute(
            """
            INSERT INTO driver_requests (request_id, driver_id, driver_username, driver_first_name, status)
            VALUES (?, ?, ?, ?, 'waiting')
            """,
            (request_id, driver_id, driver_username, driver_first_name)
        )
        await db.commit()
        return True, "added"


async def get_driver_requests(request_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM driver_requests WHERE request_id = ? AND status = 'waiting' ORDER BY id ASC",
            (request_id,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def assign_driver(
    request_id: int,
    driver_id: int,
    driver_username: Optional[str],
    driver_first_name: Optional[str]
) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            UPDATE requests
            SET status = 'taken', driver_id = ?, driver_username = ?, driver_first_name = ?
            WHERE id = ? AND status = 'new'
            """,
            (driver_id, driver_username, driver_first_name, request_id)
        )
        if cur.rowcount == 0:
            await db.rollback()
            return False

        await db.execute(
            "UPDATE driver_requests SET status = 'assigned' WHERE request_id = ? AND driver_id = ? AND status = 'waiting'",
            (request_id, driver_id)
        )
        await db.execute(
            "UPDATE driver_requests SET status = 'rejected' WHERE request_id = ? AND driver_id != ? AND status = 'waiting'",
            (request_id, driver_id)
        )
        await db.commit()
        return True


async def set_order_arrived(request_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "UPDATE requests SET status = 'arrived' WHERE id = ? AND status = 'taken'",
            (request_id,)
        )
        await db.commit()
        return cur.rowcount > 0


async def complete_request(request_id: int) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        req = await cur.fetchone()

        total_price = float(req["price"]) if req and req["price"] else 0.0
        percent = get_commission_percent()

        commission = round(total_price * (percent / 100.0), 2)
        driver_payout = round(total_price - commission, 2)

        await db.execute(
            """
            UPDATE requests 
            SET status = 'done', commission = ?, driver_payout = ?
            WHERE id = ?
            """,
            (commission, driver_payout, request_id)
        )
        await db.commit()

        return {
            "price": int(total_price),
            "commission": commission,
            "driver_payout": driver_payout,
            "percent": percent
        }


async def cancel_request(request_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE requests SET status = 'cancelled' WHERE id = ?", (request_id,))
        await db.commit()


# --- ТАРИФЫ ---

async def get_tariff_settings() -> Dict[str, bool]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT city_enabled, intercity_enabled FROM tariff_settings WHERE id = 1")
        row = await cur.fetchone()
        if not row:
            return {"city_enabled": True, "intercity_enabled": True}
        return {
            "city_enabled": bool(row["city_enabled"]),
            "intercity_enabled": bool(row["intercity_enabled"])
        }


async def set_city_enabled(enabled: bool):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE tariff_settings SET city_enabled = ? WHERE id = 1", (1 if enabled else 0,))
        await db.commit()


async def set_intercity_enabled(enabled: bool):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE tariff_settings SET intercity_enabled = ? WHERE id = 1", (1 if enabled else 0,))
        await db.commit()


# --- БАЛАНС ВОДИТЕЛЯ ---

async def get_driver_finances(driver_id: int) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row

        cur_today = await db.execute(
            """
            SELECT 
                COUNT(*) as orders_count,
                TOTAL(price) as revenue,
                TOTAL(commission) as commission,
                TOTAL(driver_payout) as payout
            FROM requests
            WHERE driver_id = ? 
              AND status = 'done'
              AND DATE(created_at, 'localtime') = DATE('now', 'localtime')
            """,
            (driver_id,)
        )
        row_today = await cur_today.fetchone()

        cur_week = await db.execute(
            """
            SELECT 
                COUNT(*) as orders_count,
                TOTAL(price) as revenue,
                TOTAL(commission) as commission,
                TOTAL(driver_payout) as payout
            FROM requests
            WHERE driver_id = ? 
              AND status = 'done'
              AND created_at >= DATETIME('now', '-7 days', 'localtime')
            """,
            (driver_id,)
        )
        row_week = await cur_week.fetchone()

        cur_total = await db.execute(
            """
            SELECT 
                COUNT(*) as orders_count,
                TOTAL(price) as revenue,
                TOTAL(commission) as commission,
                TOTAL(driver_payout) as payout
            FROM requests
            WHERE driver_id = ? AND status = 'done'
            """,
            (driver_id,)
        )
        row_total = await cur_total.fetchone()

        return {
            "today": {
                "orders": row_today["orders_count"] if row_today else 0,
                "revenue": round(row_today["revenue"]) if row_today else 0,
                "commission": round(row_today["commission"], 1) if row_today else 0.0,
                "payout": round(row_today["payout"], 1) if row_today else 0.0,
            },
            "week": {
                "orders": row_week["orders_count"] if row_week else 0,
                "revenue": round(row_week["revenue"]) if row_week else 0,
                "commission": round(row_week["commission"], 1) if row_week else 0.0,
                "payout": round(row_week["payout"], 1) if row_week else 0.0,
            },
            "total": {
                "orders": row_total["orders_count"] if row_total else 0,
                "revenue": round(row_total["revenue"]) if row_total else 0,
                "commission": round(row_total["commission"], 1) if row_total else 0.0,
                "payout": round(row_total["payout"], 1) if row_total else 0.0,
            }
        }


# --- ВЫБОРКА ID ДЛЯ РАССЫЛКИ ---

async def get_all_client_ids() -> List[int]:
    """Возвращает список ID всех клиентов сервиса."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT telegram_id FROM users")
        rows = await cur.fetchall()
        return [row[0] for row in rows]


async def get_all_driver_ids() -> List[int]:
    """Возвращает список ID всех зарегистрированных водителей."""
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT driver_id FROM drivers")
        rows = await cur.fetchall()
        return [row[0] for row in rows]