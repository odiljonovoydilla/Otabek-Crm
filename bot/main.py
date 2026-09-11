import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo
from dotenv import load_dotenv

from db import get_or_create_customer

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MINIAPP_URL = os.getenv("MINIAPP_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    # Mijozni bazada topamiz yoki yangi yaratamiz (telegram_id orqali)
    await get_or_create_customer(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="Zayavka qoldirish",
                    web_app=WebAppInfo(url=MINIAPP_URL),
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="Mening buyurtmalarim",
                    web_app=WebAppInfo(url=f"{MINIAPP_URL}#orders"),
                )
            ],
        ]
    )

    await message.answer(
        "Assalomu alaykum! Konditsioner, kirmoshina va boshqa "
        "maishiy texnikalarni ta'mirlash yoki o'rnatish uchun "
        "quyidagi tugmalardan foydalaning.",
        reply_markup=keyboard,
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
