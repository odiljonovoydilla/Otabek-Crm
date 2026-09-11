import os

import asyncpg
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_KEY = os.getenv("API_SECRET_KEY")  # admin panelga kirish uchun umumiy kalit

app = FastAPI(title="CRM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Mini App qaysi domendan ochilsa ham ruxsat
    allow_methods=["*"],
    allow_headers=["*"],
)

pool: asyncpg.Pool | None = None

VALID_STATUSES = {
    "yangi",
    "tasdiqlangan",
    "jarayonda",
    "ehtiyot_qism_kutilmoqda",
    "bajarilgan",
    "bekor_qilingan",
}


@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)


@app.on_event("shutdown")
async def shutdown():
    await pool.close()


async def require_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    """Admin panel endpointlarini himoya qiladi — X-Admin-Key header API_SECRET_KEY'ga mos bo'lishi kerak."""
    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Ruxsat yo'q: admin kaliti noto'g'ri")


# ---------- Sxemalar (mijoz tomoni) ----------

class OrderCreate(BaseModel):
    customer_telegram_id: int
    device_type: str
    order_type: str          # tamirlash / ornatish / profilaktika
    problem_description: str
    address: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None


# ---------- Sxemalar (admin tomoni) ----------

class OrderUpdate(BaseModel):
    status: str | None = None
    diagnosis: str | None = None
    estimated_price: float | None = None
    final_price: float | None = None
    scheduled_at: str | None = None       # ISO format datetime
    assigned_staff_id: int | None = None
    cancellation_reason: str | None = None
    comment: str | None = None            # holat tarixiga yoziladigan izoh


class SettlementCreate(BaseModel):
    partner_id: int
    period_start: str   # ISO format date
    period_end: str      # ISO format date


# ---------- Endpointlar (mijoz tomoni) ----------

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


# ---------- Admin panel endpointlari ----------

admin_router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


@admin_router.get("/orders")
async def admin_list_orders(status: str | None = None, source: str | None = None, partner_id: int | None = None):
    """Buyurtmalar ro'yxati — status, source (direct/partner) va hamkor bo'yicha filtrlash mumkin."""
    rows = await pool.fetch(
        """
        SELECT
            o.id, o.order_type, o.status, o.source, o.problem_description,
            o.estimated_price, o.final_price, o.payment_responsibility,
            o.partner_agreed_price, o.created_at, o.scheduled_at, o.completed_at,
            c.full_name AS customer_name, c.phone AS customer_phone,
            p.shop_name AS partner_name
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        LEFT JOIN partners p ON p.id = o.partner_id
        WHERE ($1::varchar IS NULL OR o.status = $1)
          AND ($2::varchar IS NULL OR o.source = $2)
          AND ($3::int IS NULL OR o.partner_id = $3)
        ORDER BY o.created_at DESC
        """,
        status,
        source,
        partner_id,
    )
    return [dict(r) for r in rows]


@admin_router.get("/orders/{order_id}")
async def admin_get_order(order_id: int):
    """Buyurtma tafsiloti — mijoz, hamkor va holat tarixi bilan birga."""
    order = await pool.fetchrow(
        """
        SELECT
            o.*, c.full_name AS customer_name, c.phone AS customer_phone,
            c.address AS customer_address, p.shop_name AS partner_name
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        LEFT JOIN partners p ON p.id = o.partner_id
        WHERE o.id = $1
        """,
        order_id,
    )
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    history = await pool.fetch(
        """
        SELECT id, old_status, new_status, changed_by, changed_at, comment
        FROM order_status_history
        WHERE order_id = $1
        ORDER BY changed_at DESC
        """,
        order_id,
    )
    return {"order": dict(order), "history": [dict(h) for h in history]}


@admin_router.patch("/orders/{order_id}/status")
async def admin_update_order(order_id: int, data: OrderUpdate):
    """Buyurtma holati va boshqa maydonlarini o'zgartiradi, holat o'zgarsa order_status_history'ga yozadi."""
    async with pool.acquire() as conn:
        current = await conn.fetchrow("SELECT status FROM orders WHERE id = $1", order_id)
        if not current:
            raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

        if data.status is not None and data.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Noto'g'ri holat qiymati")

        completed_at_clause = ""
        if data.status == "bajarilgan":
            completed_at_clause = ", completed_at = COALESCE(completed_at, NOW())"

        updated = await conn.fetchrow(
            f"""
            UPDATE orders
            SET status = COALESCE($1, status),
                diagnosis = COALESCE($2, diagnosis),
                estimated_price = COALESCE($3, estimated_price),
                final_price = COALESCE($4, final_price),
                scheduled_at = COALESCE($5::timestamp, scheduled_at),
                assigned_staff_id = COALESCE($6, assigned_staff_id),
                cancellation_reason = COALESCE($7, cancellation_reason),
                updated_at = NOW()
                {completed_at_clause}
            WHERE id = $8
            RETURNING *
            """,
            data.status,
            data.diagnosis,
            data.estimated_price,
            data.final_price,
            data.scheduled_at,
            data.assigned_staff_id,
            data.cancellation_reason,
            order_id,
        )

        if data.status is not None and data.status != current["status"]:
            await conn.execute(
                """
                INSERT INTO order_status_history (order_id, old_status, new_status, comment)
                VALUES ($1, $2, $3, $4)
                """,
                order_id,
                current["status"],
                data.status,
                data.comment,
            )

        return dict(updated)


@admin_router.get("/partners")
async def admin_list_partners():
    """Do'konlar ro'yxati — har biri uchun hisob-kitob qilinmagan buyurtmalar soni va summasi bilan."""
    rows = await pool.fetch(
        """
        SELECT
            p.*,
            (
                SELECT COUNT(*) FROM orders o
                WHERE o.partner_id = p.id
                  AND o.payment_responsibility = 'partner'
                  AND o.status = 'bajarilgan'
                  AND NOT EXISTS (SELECT 1 FROM settlement_orders so WHERE so.order_id = o.id)
            ) AS unsettled_orders_count,
            (
                SELECT COALESCE(SUM(COALESCE(o.partner_agreed_price, o.final_price, 0)), 0)
                FROM orders o
                WHERE o.partner_id = p.id
                  AND o.payment_responsibility = 'partner'
                  AND o.status = 'bajarilgan'
                  AND NOT EXISTS (SELECT 1 FROM settlement_orders so WHERE so.order_id = o.id)
            ) AS unsettled_total
        FROM partners p
        ORDER BY p.shop_name
        """
    )
    return [dict(r) for r in rows]


@admin_router.get("/partners/{partner_id}/unsettled-orders")
async def admin_partner_unsettled_orders(partner_id: int):
    """Hamkor uchun hali hisob-kitob qilinmagan, bajarilgan buyurtmalar — hisob-kitob yaratishdan oldin ko'rish uchun."""
    rows = await pool.fetch(
        """
        SELECT o.id, o.order_type, o.completed_at,
               COALESCE(o.partner_agreed_price, o.final_price, 0) AS amount,
               c.full_name AS customer_name
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE o.partner_id = $1
          AND o.payment_responsibility = 'partner'
          AND o.status = 'bajarilgan'
          AND NOT EXISTS (SELECT 1 FROM settlement_orders so WHERE so.order_id = o.id)
        ORDER BY o.completed_at
        """,
        partner_id,
    )
    return [dict(r) for r in rows]


@admin_router.get("/settlements")
async def admin_list_settlements(partner_id: int | None = None):
    """Hisob-kitoblar ro'yxati, ixtiyoriy ravishda hamkor bo'yicha filtrlangan."""
    rows = await pool.fetch(
        """
        SELECT s.*, p.shop_name AS partner_name
        FROM partner_settlements s
        JOIN partners p ON p.id = s.partner_id
        WHERE ($1::int IS NULL OR s.partner_id = $1)
        ORDER BY s.created_at DESC
        """,
        partner_id,
    )
    return [dict(r) for r in rows]


@admin_router.post("/settlements")
async def admin_create_settlement(data: SettlementCreate):
    """
    Berilgan davr uchun hamkorning hali hisob-kitob qilinmagan buyurtmalarini yig'ib,
    yangi partner_settlements yozuvi yaratadi.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            orders = await conn.fetch(
                """
                SELECT o.id, COALESCE(o.partner_agreed_price, o.final_price, 0) AS amount
                FROM orders o
                WHERE o.partner_id = $1
                  AND o.payment_responsibility = 'partner'
                  AND o.status = 'bajarilgan'
                  AND o.completed_at::date BETWEEN $2::date AND $3::date
                  AND NOT EXISTS (SELECT 1 FROM settlement_orders so WHERE so.order_id = o.id)
                """,
                data.partner_id,
                data.period_start,
                data.period_end,
            )
            if not orders:
                raise HTTPException(
                    status_code=400,
                    detail="Bu davr uchun hisob-kitob qilinmagan buyurtma topilmadi",
                )

            total_amount = sum(o["amount"] for o in orders)

            settlement = await conn.fetchrow(
                """
                INSERT INTO partner_settlements (partner_id, period_start, period_end, total_amount)
                VALUES ($1, $2::date, $3::date, $4)
                RETURNING *
                """,
                data.partner_id,
                data.period_start,
                data.period_end,
                total_amount,
            )

            await conn.executemany(
                "INSERT INTO settlement_orders (settlement_id, order_id) VALUES ($1, $2)",
                [(settlement["id"], o["id"]) for o in orders],
            )

            return dict(settlement)


@admin_router.patch("/settlements/{settlement_id}/pay")
async def admin_mark_settlement_paid(settlement_id: int):
    """Hisob-kitobni 'to'landi' deb belgilaydi."""
    updated = await pool.fetchrow(
        """
        UPDATE partner_settlements
        SET status = 'tolandi', paid_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        settlement_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Hisob-kitob topilmadi")
    return dict(updated)


app.include_router(admin_router)
