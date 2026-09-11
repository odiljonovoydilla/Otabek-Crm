import os

import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(title="CRM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Mini App qaysi domendan ochilsa ham ruxsat
    allow_methods=["*"],
    allow_headers=["*"],
)

pool: asyncpg.Pool | None = None


@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)


@app.on_event("shutdown")
async def shutdown():
    await pool.close()


# ---------- Sxemalar ----------

class OrderCreate(BaseModel):
    customer_telegram_id: int
    device_type: str
    order_type: str          # tamirlash / ornatish / profilaktika
    problem_description: str
    address: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None


# ---------- Endpointlar ----------

@app.get("/services")
async def get_services():
    """Mini App bosh sahifasida ko'rsatiladigan xizmatlar ro'yxati."""
    rows = await pool.fetch(
        "SELECT id, device_type, service_name, service_kind, standard_price "
        "FROM services_catalog WHERE is_active = TRUE"
    )
    return [dict(r) for r in rows]


@app.post("/orders")
async def create_order(data: OrderCreate):
    """Mijoz Mini App orqali zayavka qoldirganda chaqiriladi."""
    async with pool.acquire() as conn:
        customer = await conn.fetchrow(
            "SELECT id FROM customers WHERE telegram_id = $1",
            data.customer_telegram_id,
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Mijoz topilmadi")

        if data.address or data.location_lat:
            await conn.execute(
                """
                UPDATE customers
                SET address = COALESCE($1, address),
                    location_lat = COALESCE($2, location_lat),
                    location_lng = COALESCE($3, location_lng)
                WHERE id = $4
                """,
                data.address,
                data.location_lat,
                data.location_lng,
                customer["id"],
            )

        order = await conn.fetchrow(
            """
            INSERT INTO orders (
                customer_id, order_type, problem_description, status, source
            )
            VALUES ($1, $2, $3, 'yangi', 'direct')
            RETURNING id, status, created_at
            """,
            customer["id"],
            data.order_type,
            data.problem_description,
        )
        return dict(order)


@app.get("/orders/{telegram_id}")
async def get_customer_orders(telegram_id: int):
    """Mijozning 'Mening buyurtmalarim' sahifasi uchun."""
    rows = await pool.fetch(
        """
        SELECT o.id, o.order_type, o.status, o.final_price, o.created_at
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE c.telegram_id = $1
        ORDER BY o.created_at DESC
        """,
        telegram_id,
    )
    return [dict(r) for r in rows]
