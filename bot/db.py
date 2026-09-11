import os

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


async def get_or_create_customer(telegram_id: int, full_name: str) -> int:
    """
    Telegram ID bo'yicha mijozni topadi, topilmasa yangi yozuv yaratadi.
    Mijozning customers.id qiymatini qaytaradi.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM customers WHERE telegram_id = $1", telegram_id
        )
        if row:
            return row["id"]

        row = await conn.fetchrow(
            """
            INSERT INTO customers (telegram_id, full_name, phone)
            VALUES ($1, $2, '')
            RETURNING id
            """,
            telegram_id,
            full_name,
        )
        return row["id"]
