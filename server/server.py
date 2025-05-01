# ######################################################################
# Application: Backend - Sticker wall
# Description: Backend that manages the interface between the BOT and the
# webpage that shows the stickers
#
# ######################################################################
import fastapi

# ######################################################################
# Import Modules
# ######################################################################
try:
    import os
    import sys
    import logging
    import uuid
    import uvicorn
    import json
    # from xmlrpc.client import boolean

    from fastapi import FastAPI, WebSocket, HTTPException, Security
    from fastapi.security.api_key import APIKeyHeader
    from fastapi.staticfiles import StaticFiles
    from dotenv import load_dotenv, dotenv_values
    from starlette.websockets import WebSocketDisconnect
    from starlette.status import HTTP_403_FORBIDDEN
    from typing import List, Annotated
    from sqlmodel import Field, Session, SQLModel, create_engine, select

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


# ------------------------------------------------------------------------------
# Logging Stuff
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=LOGGING_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)
# ------------------------------------------------------------------------------


# ######################################################################
# Global variables - Some are populated in the MAIN() function
# ######################################################################
API_KEY:str = ""
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

BASE_PATH:str = os.getcwd() # Return a string representing the current working directory. Example: E:\\ or /VAR/DEV/

# Websocket clients
connected_telegram_clients = []
connected_wall_clients = []

# SQLITE Stuff
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{os.path.join(BASE_PATH, sqlite_file_name)}" # The file should be saved on the same directory as the application
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

# Default user policy
defaultUserStickerPolicy = {
    "stickerCountMax" : 3
}
# ######################################################################


# ######################################################################
# FastAPI main
# ######################################################################
app = FastAPI(
    title="Sticker Wall",
    description="A simple sticker wall server",
    version="0.1.2",
    docs_url=None,
    redoc_url=None,
    # docs_url="/docs",
    # redoc_url="/redoc",
)
# ######################################################################


# ######################################################################
# Database Models
# ######################################################################
# class Hero(SQLModel, table=True):
#     id: int | None = Field(default=None, primary_key=True)
#     name: str = Field(index=True)
#     age: int | None = Field(default=None, index=True)
#     secret_name: str

# Uploaded stickers
# class StickerbyUser(SQLModel, table=True, extend_existing=True):
#     id: int | None = Field(default=None, primary_key=True)
#     telegram_user: str | None = Field(default=None)
#     telegram_id: str = Field(index=True, unique=True)
#     sticker: str
#     sticker_options: str | None= Field(nullable=True)
#     enabled: bool = True
#
# # Stickers that are banned
# class StickerBan(SQLModel, table=True, extend_existing=True):
#     id: int | None = Field(default=None, primary_key=True)
#     sticker: str = Field(index=True, unique=True)
#
# # Stickers that are banned
# class UserBan(SQLModel, table=True, extend_existing=True):
#     id: int | None = Field(default=None, primary_key=True)
#     user_name: str
#     user_id: str = Field(index=True, unique=True)
# ######################################################################




# ######################################################################
# Functions / Modules
# ######################################################################
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


# ------------------------------------------------------------------------------
def get_session():
    with Session(engine) as session:
        yield session






# Yes... the code may be a mess... but you can't start perfect when you start from scratch something :)



















# ------------------------------------------------------------------------------
@app.websocket("/ws/telegram")
async def websocket_telegram_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_telegram_clients.append(websocket)

    logging.debug(f"Connected telegram bots: {len(connected_telegram_clients)}")

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # logging.info(f"Received message: {data}")
                # logging.info(f"Received message: {message}")

                if message.get("type") == "heartbeat":
                    # Log or handle heartbeat
                    logging.info(f"Heartbeat received from bot: {message.get('bot_name')}")
                    continue


                if message.get("type") == "sticker":
                    # Log or handle heartbeat
                    logging.info(f"Sticker received: {message.get('bot_name')}")
                    # Handle other message types
                    # logging.info(f"Received message: {data}")
                    # Broadcast to all connected clients
                    for client in connected_wall_clients:
                        if client != websocket:
                            await client.send_text(data)
                    continue

            except json.JSONDecodeError:
                logging.error(f"Invalid JSON received: {data}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        connected_telegram_clients.remove(websocket)

# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
@app.websocket("/ws/wall")
async def websocket_wall_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_wall_clients.append(websocket)
    logging.info(f"Connected clients: {len(connected_wall_clients)}")

    try:
        while True:
            data = await websocket.receive_text()
            logging.info(f"Received message: {data}")
            # Broadcast to all connected clients
            for client in connected_wall_clients:
                if client != websocket:
                    await client.send_text(data)

    except WebSocketDisconnect:
        # logging.info("Client disconnected")
        pass

    except Exception as e:
        print(f"WebSocket error: {e}")

    finally:
        connected_wall_clients.remove(websocket)
# ------------------------------------------------------------------------------






# ------------------------------------------------------------------------------
@app.get("/api/stickers", response_model=List[str])
async def list_stickers(apikey: str = Security(api_key_header)):

    # print(f"API_KEY expected/received: {API_KEY}/{apikey}")

    if not apikey:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate API key"
        )
    if apikey != API_KEY:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Nope... Could not validate API key"
        )

    try:
        # Get list of .webp files from stickers directory
        sticker_files = [f for f in os.listdir("static/stickers") if f.endswith('.webp')]

        # Broadcast the entire list to all connected clients
        for client in connected_wall_clients:
            for sticker in sticker_files:
                sticker_path = f"stickers/{sticker}"
                await client.send_text(sticker_path)

        # Return the list of sticker paths
        return [f"stickers/{sticker}" for sticker in sticker_files]

    except Exception as e:
        logging.error(f"Error listing stickers: {e}")
        raise HTTPException(status_code=500, detail="Error listing stickers")





@app.on_event("startup")
def on_startup():
    create_db_and_tables()





# ------------------------------------------------------------------------------
# Static mounts to serve stuff - They need to be the last declared to avoid issues or errors due the '/'
# app.mount("/static", StaticFiles(directory="public"), name="static")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
# ------------------------------------------------------------------------------


if __name__ == "__main__":
    # Load the .env file (if exist)
    load_dotenv()

    # ------------------------------------------------------------------------------
    # Configurations
    # ------------------------------------------------------------------------------
    API_KEY = os.getenv("BACKEND_API_KEY")
    TELEGRAM_WEBSOCK_API_KEY = os.getenv("BOT_SERVER_WEBSOCKET_API_KEY")
    # api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
    # ------------------------------------------------------------------------------


    logging.info("Starting server...")
    logging.info(f"Database: {sqlite_url}")

    if not API_KEY or API_KEY == "":
        # If it is missing or fail, fallback to a random value
        API_KEY = str(uuid.uuid4())
    logger.info(f"API_KEY: {API_KEY}")

    # uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
    if LOGGING_LEVEL == logging.DEBUG:
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True, log_level="debug", proxy_headers=True)
    elif LOGGING_LEVEL == logging.INFO:
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True, log_level="info", proxy_headers=True)
    else:
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True, proxy_headers=True)

