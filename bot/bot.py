# ######################################################################
# Application: TELEGRAM BOT
# Description: This application connects to Telegram, get the stickers sent
# by the user and forward to the main backend server.
# This application works (for the moment) pulling data
#
# TODO: Implement webhook integration to avoid pooling
# ######################################################################

# ######################################################################
# Import Modules
# ######################################################################
try:
    import os
    import aiohttp
    import aiogram
    import asyncio
    import logging
    import sys
    import json
    import logging
    from dotenv import load_dotenv

    from websockets.asyncio.client import connect

    from aiogram import Bot, Dispatcher, html, types, F
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.filters import CommandStart
    from aiogram.types import Message, File

except Exception as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)
# ######################################################################

# ######################################################################
# DEBUG MODE CHECK
# ######################################################################
if __debug__:
    LOGGING_LEVEL = logging.DEBUG # Enable DEBUG by default
    print(f"({__name__}) - WARNING: Running in DEBUG Mode. For Production, run with -O - Example: python -O potato_file.py")
else:
    LOGGING_LEVEL = logging.INFO # Enable INFO by default
# ######################################################################

# ######################################################################
# Global variables - Some are populated in the MAIN() function
# ######################################################################
TELEGRAM_TOKEN:str = ""
WEBSOCKET_SERVER_URI:str = ""

# Bot variables
bot: Bot = None # Updated later
dp = Dispatcher()

# ######################################################################


# ------------------------------------------------------------------------------
# Connect to WebSocket server
async def send_sticker_to_ws(sticker_path, telegram_user:str, telegram_userid:int):
    # try:
    #     async with connect(WEBSOCKET_SERVER_URI) as websocket:
    #         await websocket.send(sticker_path)
    # except Exception as e:
    #     print(f"Error sending sticker to WebSocket server: {e}")
    try:
        async with connect(WEBSOCKET_SERVER_URI) as websocket:
            message = {
                "type": "sticker",
                "bot_user": telegram_user,
                "bot_name": telegram_userid,
                "path": sticker_path
            }
            await websocket.send(json.dumps(message))

    except Exception as e:
        print(f"Error sending sticker to WebSocket server: {e}")
# ------------------------------------------------------------------------------





# ------------------------------------------------------------------------------
async def heartbeat(websocket, bot_info:aiogram.types.User):
    while True:
        try:
            heartbeat_message = {
                "type": "heartbeat",
                "bot_username": bot_info.username,
                "bot_name": bot_info.full_name,
                "status": "alive"
            }
            await websocket.send(json.dumps(heartbeat_message))
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds

        except Exception as e:
            print(f"Heartbeat error: {e}")
            break


async def create_ws_connection():
    while True:
        try:
            async with connect(WEBSOCKET_SERVER_URI) as websocket:
                bot_info = await bot.get_me()
                bot_name = bot_info.username
                # print(f"WebSocket connected, starting heartbeat for bot: {bot_name}")
                logger.info(f"WebSocket connected, starting heartbeat for bot: {bot_name}")

                # Start the heartbeat task
                heartbeat_task = asyncio.create_task(heartbeat(websocket, bot_info))

                # Keep the connection alive and handle other messages
                while True:
                    try:
                        # Wait for any incoming messages
                        message = await websocket.recv()
                        # print(f"Received message from server: {message}")
                        logger.debug(f"Received message from server: {message}")

                    except Exception as e:
                        # print(f"Error receiving message: {e}")
                        logger.error(f"Error receiving message: {e}")
                        break

                # Cancel heartbeat when connection is lost
                heartbeat_task.cancel()

        except Exception as e:
            # print(f"WebSocket connection error: {e}")
            logger.error(f"WebSocket connection error: {e}")
            await asyncio.sleep(5)  # Wait before reconnecting
# ------------------------------------------------------------------------------



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
    logger.info(f"Received command /start from {message.from_user.username}")
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!\nSend me your sticker and I will show in the digital wall.")
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
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
    await send_sticker_to_ws(sticker_url, message.from_user.username, message.from_user.id)


# ------------------------------------------------------------------------------
async def main() -> None:
    bot_info = await bot.get_me()
    # print(f"Bot info: {bot_info}")

    logger.info(f"Starting bot: {bot_info.username}")

    # Create tasks for both the WebSocket connection and the bot polling
    ws_task = asyncio.create_task(create_ws_connection())
    polling_task = asyncio.create_task(dp.start_polling(bot))

    # And the run events dispatching
    # await dp.start_polling(bot)
    await asyncio.gather(ws_task, polling_task)




# ##################################################################################
if __name__ == "__main__":
    # ------------------------------------------------------------------------------
    # Logger options and settings
    # ------------------------------------------------------------------------------
    logging.basicConfig(
        level=LOGGING_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )
    logger = logging.getLogger(__name__)
    # ------------------------------------------------------------------------------

    # Load the .env file (if exist)
    load_dotenv()

    # Get the infos needed
    TELEGRAM_TOKEN = str(os.getenv("BOT_SERVER_TELEGRAM_BOT_TOKEN"))
    WEBSOCKET_SERVER_URI = str(os.getenv("BOT_SERVER_WEBSOCKET_SERVER_URI"))

    # Sanity check
    if TELEGRAM_TOKEN is None or WEBSOCKET_SERVER_URI is None:
        print("BOT_SERVER_TELEGRAM_BOT_TOKEN/BOT_SERVER_WEBSOCKET_SERVER_URI NOT FOUND or DEFINED")
        sys.exit(1)

    if TELEGRAM_TOKEN == "" or WEBSOCKET_SERVER_URI == "":
        print("BOT_SERVER_TELEGRAM_BOT_TOKEN/BOT_SERVER_WEBSOCKET_SERVER_URI is empty - please define it in .env file or set it as env variable")
        sys.exit(1)

    # Init BOT
    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Create the dispatcher
    # dp = Dispatcher()

    # executor.start_polling(dp, skip_updates=True)
    # logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
