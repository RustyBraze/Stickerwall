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
    import base64

    from io import BytesIO
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
WEBSOCKET_API_KEY:str = ""

banned_users:dict = {}

# Bot variables
bot: Bot = None # Updated later
dp = Dispatcher()

# ######################################################################


# ------------------------------------------------------------------------------
# Connect to WebSocket server
async def send_sticker_to_ws(message_data):
    try:
        async with connect(
                WEBSOCKET_SERVER_URI,
                additional_headers={"x-api-key": WEBSOCKET_API_KEY}
        ) as websocket:
            await websocket.send(message_data)
    except Exception as e:
        logger.error(f"Error sending sticker to WebSocket server: {e}")

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
            async with connect(
                    WEBSOCKET_SERVER_URI,
                    additional_headers={"x-api-key": WEBSOCKET_API_KEY}
            ) as websocket:

                bot_info = await bot.get_me()
                bot_name = bot_info.username
                # print(f"WebSocket connected, starting heartbeat for bot: {bot_name}")
                logger.info(f"WebSocket connected, starting heartbeat for bot: {bot_name}")

                # Start the heartbeat task
                heartbeat_task = asyncio.create_task(heartbeat(websocket, bot_info))

                # Lets send the bot info
                sticker_message = {
                    "type": "bot_info",
                    "username": bot_info.username,
                    "full_name": bot_info.full_name
                }

                # Send to WebSocket server
                await send_sticker_to_ws(json.dumps(sticker_message))

                # Keep the connection alive and handle other messages
                while True:
                    try:
                        # Wait for any incoming messages
                        message = await websocket.recv()
                        # print(f"Received message from server: {message}")
                        # logger.debug("********************************************************")
                        # logger.debug(f"Received message from server: {message}")
                        # logger.debug("********************************************************")

                        try:
                            data = json.loads(message)
                            if data.get("type") == "user_message":
                                # Send message to user
                                await bot.send_message(
                                    chat_id=data["user_id"],
                                    text=data["message"]
                                )
                        except json.JSONDecodeError:
                            logger.error(f"Invalid JSON received from server: {message}")

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
    message_str: str = f"Hello, {html.bold(message.from_user.full_name)}!\n"
    message_str += f"Send me your sticker and I will show in the digital wall.\n\n"
    message_str += f"You can send up to 3 stickers at a time."

    await message.answer(message_str, parse_mode=ParseMode.HTML)
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
@dp.message(F.content_type.in_('sticker'))
async def handle_sticker(message: types.Message):
    telegram_user_id = message.from_user.id
    telegram_username = message.from_user.username or "No username"
    telegram_full_username = message.from_user.full_name or "No name"

    # Get the sticker file
    sticker: File = await bot.get_file(message.sticker.file_id)
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{sticker.file_path}"

    # Download sticker and convert to base64
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as resp:
            if resp.status == 200:
                sticker_data = await resp.read()
                # Convert to base64
                base64_sticker = base64.b64encode(sticker_data).decode('utf-8')

                # Create message with sticker data
                sticker_message = {
                    "type": "sticker",
                    "telegram_username": telegram_username,
                    "telegram_full_username": telegram_full_username,
                    "telegram_user_id": telegram_user_id,
                    "sticker_id": message.sticker.file_id,
                    "sticker_data": base64_sticker,
                    "file_extension": "webp"  # Telegram stickers are always webp
                }

                # Send to WebSocket server
                await send_sticker_to_ws(json.dumps(sticker_message))
                logger.info(f"Sticker sent to server from user: {telegram_username}")
            else:
                logger.error(f"Failed to download sticker: {resp.status}")
# ------------------------------------------------------------------------------


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
    WEBSOCKET_API_KEY = str(os.getenv("BOT_SERVER_WEBSOCKET_API_KEY"))

    # Sanity check
    if not all([TELEGRAM_TOKEN, WEBSOCKET_SERVER_URI, WEBSOCKET_API_KEY]):
        message_tmp = "Not found or defined: BOT_SERVER_TELEGRAM_BOT_TOKEN / BOT_SERVER_WEBSOCKET_SERVER_URI / BOT_SERVER_WEBSOCKET_API_KEY"
        logger.error(message_tmp)
        print(message_tmp)
        sys.exit(1)

    if "" in [TELEGRAM_TOKEN, WEBSOCKET_SERVER_URI, WEBSOCKET_API_KEY]:
        message_tmp = "Variables cannot be empty: BOT_SERVER_TELEGRAM_BOT_TOKEN / BOT_SERVER_WEBSOCKET_SERVER_URI / BOT_SERVER_WEBSOCKET_API_KEY"
        logger.error(message_tmp)
        print(message_tmp)
        sys.exit(1)

    # Init BOT
    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # Create the dispatcher
    # dp = Dispatcher()

    # executor.start_polling(dp, skip_updates=True)
    # logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
