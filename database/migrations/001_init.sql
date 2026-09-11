-- ============================================================
-- MAISHIY TEXNIKA TA'MIRLASH/O'RNATISH CRM — DATABASE SXEMASI
-- PostgreSQL 14+
-- ============================================================

-- ------------------------------------------------------------
-- 1. XODIMLAR (usta, admin — kelajakda bir nechta usta bo'lsa ham ishlaydi)
-- ------------------------------------------------------------
CREATE TABLE staff (
    id              SERIAL PRIMARY KEY,
    full_name       VARCHAR(150) NOT NULL,
    phone           VARCHAR(20) NOT NULL UNIQUE,
    telegram_id     BIGINT UNIQUE,              -- bot orqali aniqlash uchun
    role            VARCHAR(20) NOT NULL DEFAULT 'usta',  -- usta / admin
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 2. MIJOZLAR
-- ------------------------------------------------------------
CREATE TABLE customers (
    id              SERIAL PRIMARY KEY,
    full_name       VARCHAR(150),
    phone           VARCHAR(20) NOT NULL,
    telegram_id     BIGINT UNIQUE,              -- bot orqali yozgan mijoz
    address         TEXT,
    location_lat    DOUBLE PRECISION,           -- Telegram location
    location_lng    DOUBLE PRECISION,
    customer_type   VARCHAR(20) NOT NULL DEFAULT 'jismoniy', -- jismoniy / yuridik
    notes           TEXT,                       -- "kechqurun bo'sh" kabi izohlar
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_customers_phone ON customers(phone);

-- ------------------------------------------------------------
-- 3. MIJOZLARGA TEGISHLI QURILMALAR
-- ------------------------------------------------------------
CREATE TABLE devices (
    id                  SERIAL PRIMARY KEY,
    customer_id         INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    device_type         VARCHAR(50) NOT NULL,   -- konditsioner / kirmoshina / plita / muzlatgich
    brand               VARCHAR(50),
    model               VARCHAR(100),
    serial_number       VARCHAR(100),
    purchase_date       DATE,
    warranty_until      DATE,                   -- kafolat muddati — eslatma yuborish uchun
    last_service_date   DATE,                   -- oxirgi texxizmat sanasi
    next_service_due     DATE,                   -- keyingi tozalash/texxizmat sanasi (avtomatik eslatma uchun)
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_devices_customer ON devices(customer_id);
CREATE INDEX idx_devices_next_service ON devices(next_service_due);

-- ------------------------------------------------------------
-- 4. HAMKOR DO'KONLAR / SAVDO MARKAZLARI
-- ------------------------------------------------------------
CREATE TABLE partners (
    id                  SERIAL PRIMARY KEY,
    shop_name           VARCHAR(150) NOT NULL,
    contact_person      VARCHAR(150),
    phone               VARCHAR(20),
    address             TEXT,
    default_service_fee NUMERIC(12,2),          -- standart kelishilgan narx (agar fixed bo'lsa)
    fee_type            VARCHAR(20) DEFAULT 'fixed', -- fixed / percent
    fee_percent         NUMERIC(5,2),            -- agar foiz bo'lsa
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 5. XIZMATLAR NARXNOMASI (katalog)
-- ------------------------------------------------------------
CREATE TABLE services_catalog (
    id              SERIAL PRIMARY KEY,
    device_type     VARCHAR(50) NOT NULL,       -- qaysi qurilma turiga tegishli
    service_name    VARCHAR(150) NOT NULL,      -- masalan: "Konditsioner o'rnatish"
    service_kind    VARCHAR(20) NOT NULL,       -- tamirlash / ornatish / profilaktika
    standard_price  NUMERIC(12,2) NOT NULL,
    estimated_hours NUMERIC(4,1),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- ------------------------------------------------------------
-- 6. EHTIYOT QISMLAR OMBORI
-- ------------------------------------------------------------
CREATE TABLE parts_inventory (
    id              SERIAL PRIMARY KEY,
    part_name       VARCHAR(150) NOT NULL,
    part_code       VARCHAR(50),
    device_type     VARCHAR(50),                -- qaysi qurilma turiga mos
    quantity        INTEGER NOT NULL DEFAULT 0,
    cost_price      NUMERIC(12,2),               -- tan narxi
    sell_price      NUMERIC(12,2),               -- mijozga sotish narxi
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 7. BUYURTMALAR / ZAYAVKALAR — TIZIMNING YURAGI
-- ------------------------------------------------------------
CREATE TABLE orders (
    id                      SERIAL PRIMARY KEY,
    customer_id             INTEGER NOT NULL REFERENCES customers(id),
    device_id               INTEGER REFERENCES devices(id),
    assigned_staff_id       INTEGER REFERENCES staff(id),

    -- manba: to'g'ridan-to'g'ri mijozmi, hamkor do'kon orqalimi
    source                  VARCHAR(20) NOT NULL DEFAULT 'direct',  -- direct / partner
    partner_id              INTEGER REFERENCES partners(id),

    order_type              VARCHAR(20) NOT NULL,   -- tamirlash / ornatish / profilaktika
    problem_description     TEXT,                   -- mijoz aytgan muammo
    diagnosis               TEXT,                   -- usta aniqlagan haqiqiy sabab

    status                  VARCHAR(30) NOT NULL DEFAULT 'yangi',
    -- yangi -> tasdiqlangan -> jarayonda -> ehtiyot_qism_kutilmoqda -> bajarilgan -> bekor_qilingan

    scheduled_at            TIMESTAMP,              -- rejalashtirilgan tashrif vaqti
    completed_at            TIMESTAMP,              -- bajarilgan vaqt

    estimated_price         NUMERIC(12,2),          -- dastlabki taxmin
    final_price              NUMERIC(12,2),          -- yakuniy narx

    -- kim to'laydi: mijozmi yoki hamkor do'konmi
    payment_responsibility  VARCHAR(20) NOT NULL DEFAULT 'customer', -- customer / partner
    partner_agreed_price    NUMERIC(12,2),          -- do'kon bilan kelishilgan narx

    cancellation_reason     TEXT,                   -- bekor qilingan bo'lsa, sababi
    lead_source              VARCHAR(50),            -- instagram / tanish / qayta_murojaat / boshqa

    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_source ON orders(source);
CREATE INDEX idx_orders_scheduled ON orders(scheduled_at);

-- ------------------------------------------------------------
-- 8. BUYURTMADA ISHLATILGAN EHTIYOT QISMLAR (many-to-many)
-- ------------------------------------------------------------
CREATE TABLE order_parts (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    part_id         INTEGER NOT NULL REFERENCES parts_inventory(id),
    quantity        INTEGER NOT NULL DEFAULT 1,
    price_at_time   NUMERIC(12,2) NOT NULL         -- narx o'zgarib qolsa ham tarix saqlanadi
);

-- ------------------------------------------------------------
-- 9. TO'LOVLAR (faqat to'g'ridan-to'g'ri mijozlardan)
-- ------------------------------------------------------------
CREATE TABLE payments (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(id),
    amount          NUMERIC(12,2) NOT NULL,
    payment_method  VARCHAR(20) NOT NULL,       -- naqd / karta / click / payme
    status          VARCHAR(20) NOT NULL DEFAULT 'tolandi', -- tolandi / qarz
    paid_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 10. HAMKOR DO'KONLAR BILAN HISOB-KITOB (davriy)
-- ------------------------------------------------------------
CREATE TABLE partner_settlements (
    id              SERIAL PRIMARY KEY,
    partner_id      INTEGER NOT NULL REFERENCES partners(id),
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    total_amount    NUMERIC(12,2) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'kutilmoqda', -- kutilmoqda / tolandi
    paid_at         TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- qaysi orderlar shu hisob-kitobga kirgani (many-to-many)
CREATE TABLE settlement_orders (
    settlement_id   INTEGER NOT NULL REFERENCES partner_settlements(id) ON DELETE CASCADE,
    order_id        INTEGER NOT NULL REFERENCES orders(id),
    PRIMARY KEY (settlement_id, order_id)
);

-- ------------------------------------------------------------
-- 11. USTANING JADVALI (band vaqtlar — orders bilan avtomatik bog'lanadi)
-- ------------------------------------------------------------
CREATE TABLE schedule_blocks (
    id              SERIAL PRIMARY KEY,
    staff_id        INTEGER NOT NULL REFERENCES staff(id),
    order_id        INTEGER REFERENCES orders(id),
    start_time      TIMESTAMP NOT NULL,
    end_time        TIMESTAMP NOT NULL,
    note            VARCHAR(200)                -- masalan: "shaxsiy ish", "dam olish"
);

CREATE INDEX idx_schedule_staff_time ON schedule_blocks(staff_id, start_time);

-- ------------------------------------------------------------
-- 12. BUYURTMA HOLATI TARIXI (audit log — kim qachon o'zgartirgan)
-- ------------------------------------------------------------
CREATE TABLE order_status_history (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    old_status      VARCHAR(30),
    new_status      VARCHAR(30) NOT NULL,
    changed_by      INTEGER REFERENCES staff(id),
    changed_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    comment         TEXT
);

CREATE INDEX idx_status_history_order ON order_status_history(order_id);

-- ------------------------------------------------------------
-- 13. BUYURTMAGA BIRIKTIRILGAN RASM/VIDEO
-- ------------------------------------------------------------
CREATE TABLE order_attachments (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    file_url        TEXT NOT NULL,              -- Telegram file_id yoki storage link
    attachment_type VARCHAR(20) NOT NULL DEFAULT 'photo', -- photo / video
    uploaded_by     VARCHAR(20) NOT NULL,       -- customer / staff
    stage           VARCHAR(20),                -- muammo / natija (oldin/keyin)
    uploaded_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 14. MIJOZ BAHOSI (ish sifatini kuzatish)
-- ------------------------------------------------------------
CREATE TABLE order_reviews (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
    rating          SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 15. YUBORILGAN BILDIRISHNOMALAR JURNALI (takroriy spam bo'lmasligi uchun)
-- ------------------------------------------------------------
CREATE TABLE notifications_log (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER REFERENCES customers(id),
    order_id        INTEGER REFERENCES orders(id),
    notif_type      VARCHAR(30) NOT NULL,       -- service_reminder / status_update / promo
    message         TEXT,
    sent_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_customer ON notifications_log(customer_id);

-- ------------------------------------------------------------
-- 16. ISHGA KAFOLAT (usta o'zi qilgan ta'mirga)
-- ------------------------------------------------------------
CREATE TABLE service_warranties (
    id                  SERIAL PRIMARY KEY,
    order_id            INTEGER NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
    warranty_days       INTEGER NOT NULL DEFAULT 30,
    warranty_expires_at DATE NOT NULL,
    claimed             BOOLEAN NOT NULL DEFAULT FALSE, -- kafolat asosida qayta chaqirilganmi
    claim_order_id      INTEGER REFERENCES orders(id)   -- kafolat bo'yicha ochilgan yangi order
);

-- ------------------------------------------------------------
-- 17. XARAJATLAR (benzin, transport, mayda xarid — haqiqiy foyda uchun)
-- ------------------------------------------------------------
CREATE TABLE expenses (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER REFERENCES orders(id),  -- agar aynan shu buyurtmaga tegishli bo'lsa
    category        VARCHAR(30) NOT NULL,       -- transport / ehtiyot_qism / boshqa
    amount          NUMERIC(12,2) NOT NULL,
    note            TEXT,
    spent_at        TIMESTAMP NOT NULL DEFAULT NOW()
);
