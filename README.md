# CRM — maishiy texnika ta'mirlash/o'rnatish

## Tuzilma

```
crm-project/
├── docker-compose.yml     # hammasini birgalikda ishga tushiradi
├── .env.example           # nusxa ko'chirib .env qiling va to'ldiring
├── database/
│   └── migrations/
│       └── 001_init.sql   # barcha jadvallar shu yerda
├── bot/                    # Telegram bot (aiogram)
│   ├── main.py
│   └── db.py
├── api/                    # FastAPI backend (Mini App uchun)
│   └── main.py
└── miniapp/                 # keyingi bosqichda to'ldiriladi
```

## Ishga tushirish (qadam-baqadam)

### 1. BotFather'dan token oling
Telegram'da @BotFather ga yozing, `/newbot` buyrug'i bilan yangi bot yarating, tokenni saqlab qo'ying.

### 2. Muhit faylini sozlang
```bash
cp .env.example .env
```
`.env` faylini oching, `BOT_TOKEN` qatoriga BotFather'dan olgan tokenni qo'ying.

### 3. Docker bilan ishga tushiring
```bash
docker-compose up --build
```
Bu buyruq:
- PostgreSQL'ni ishga tushiradi va `001_init.sql` orqali barcha jadvallarni avtomatik yaratadi
- API serverini ishga tushiradi (`http://localhost:8000`)
- Telegram botni ishga tushiradi

### 4. Tekshirish
- Telegram'da o'z botingizga `/start` yozing — javob kelishi kerak
- Brauzerda `http://localhost:8000/docs` ni oching — FastAPI avtomatik hujjatlarini ko'rasiz

## Keyingi qadamlar
- [ ] Mini App sahifalarini yaratish (`miniapp/` papkasida)
- [ ] Admin/usta paneli uchun API endpointlar
- [ ] Hamkor do'konlar bilan hisob-kitob logikasi
- [ ] Avtomatik eslatma yuborish (kafolat, texxizmat sanasi)
