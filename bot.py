import os
import aiohttp
import asyncio
import logging
import sys
from dotenv import load_dotenv, dotenv_values

from websockets.asyncio.client import connect

from aiogram import Bot, Dispatcher, html, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, File

load_dotenv()

# ------------------------------------------------------------------------------
TELEGRAM_TOKEN = str(os.getenv("BOT_TOKEN"))
WEBSOCKET_SERVER_URI = str(os.getenv("WEBSOCKET_SERVER_URI"))
# ------------------------------------------------------------------------------
# print(f"TELEGRAM_TOKEN: {TELEGRAM_TOKEN}")
# sys.exit(0)

if TELEGRAM_TOKEN is None or WEBSOCKET_SERVER_URI is None:
    print("BOT_TOKEN/WEBSOCKET_SERVER_URI env NOT FOUND or defined")
    sys.exit(1)

if TELEGRAM_TOKEN == "" or WEBSOCKET_SERVER_URI == "":
    print("BOT_TOKEN/WEBSOCKET_SERVER_URI is empty - please define it in .env file or set it as env variable")
    sys.exit(1)

# Initialize Bot instance with default bot properties which will be passed to all API calls
# bot = Bot(token=TELEGRAM_TOKEN)
bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher()

# ------------------------------------------------------------------------------
# Connect to WebSocket server
async def send_sticker_to_ws(sticker_path):
    try:
        async with connect(WEBSOCKET_SERVER_URI) as websocket:
            await websocket.send(sticker_path)
    except Exception as e:
        print(f"Error sending sticker to WebSocket server: {e}")


# ------------------------------------------------------------------------------
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    # Most event objects have aliases for API methods that can be called in events' context
    # For example if you want to answer to incoming message you can use `message.answer(...)` alias
    # and the target chat will be passed to :ref:`aiogram.methods.send_message.SendMessage`
    # method automatically or call API method directly via
    # Bot instance: `bot.send_message(chat_id=message.chat.id, ...)`
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}! Send me your sticker and I will show in the digital wall.")

# ------------------------------------------------------------------------------
# @dp.message_handler(content_types=types.ContentType.STICKER)
# @dp.message.handler(lambda message: message.sticker)
# @dp.message.handlers(content_types=types.ContentType.STICKER)
# @dp.message(F.is_('sticker') | F.sticker.is_type('sticker'))
@dp.message(F.content_type.in_('sticker'))
async def handle_sticker(message: types.Message):
    sticker: File = await bot.get_file(message.sticker.file_id)
    sticker_path = f"public/stickers/{message.sticker.file_id}.webp"
    sticker_url = f"stickers/{message.sticker.file_id}.webp"

    os.makedirs("public/stickers", exist_ok=True)

    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{sticker.file_path}"
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as resp:
            if resp.status == 200:
                with open(sticker_path, 'wb') as f:
                    f.write(await resp.read())

    print(f"Sticker saved at {sticker_path}")

    # Notify WebSocket clients
    await send_sticker_to_ws(sticker_url)


# ------------------------------------------------------------------------------
async def main() -> None:
    # And the run events dispatching
    await dp.start_polling(bot)



# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # executor.start_polling(dp, skip_updates=True)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
