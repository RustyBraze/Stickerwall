# ######################################################################
# Application: Backend - Sticker wall
# Description: Backend that manages the interface between the BOT and the
# webpage that shows the stickers
#
# ######################################################################

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
    import base64
    # import datetime as _datetime
    # from xmlrpc.client import boolean

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, WebSocket, HTTPException, Security
    from fastapi.security.api_key import APIKeyHeader
    from fastapi.staticfiles import StaticFiles
    from dotenv import load_dotenv, dotenv_values
    from starlette.websockets import WebSocketDisconnect
    from starlette.status import HTTP_403_FORBIDDEN
    from typing import List, Annotated, Optional, Dict
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import Column, JSON, Index
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
TELEGRAM_WEBSOCK_API_KEY:str = ""

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

BASE_PATH:str = os.getcwd() # Return a string representing the current working directory. Example: E:\\ or /VAR/DEV/

# Websocket clients
connected_telegram_clients = []
connected_wall_clients = []

# SQLITE Stuff
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{os.path.join(BASE_PATH, sqlite_file_name)}" # The file should be saved on the same directory as the application
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args, echo=False)

# Default user policy
defaultUserStickerPolicy = {
    "stickerCountMax" : 3
}
# ######################################################################


# ######################################################################
# FastAPI new Startup/Shutdown
# ######################################################################
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs at startup
    global API_KEY
    global TELEGRAM_WEBSOCK_API_KEY

    # Load the .env file (if exist)
    load_dotenv()

    # ------------------------------------------------------------------------------
    # Configurations
    # ------------------------------------------------------------------------------
    API_KEY = os.getenv("BACKEND_API_KEY")
    TELEGRAM_WEBSOCK_API_KEY = os.getenv("BOT_SERVER_WEBSOCKET_API_KEY")
    # api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
    # ------------------------------------------------------------------------------
    print(TELEGRAM_WEBSOCK_API_KEY)
    # sys.exit(0)

    # Sanity check
    if not all([API_KEY, TELEGRAM_WEBSOCK_API_KEY]):
        print("Missing required environment variables")
        sys.exit(1)

    if "" in [API_KEY, TELEGRAM_WEBSOCK_API_KEY]:
        print("Empty required environment variables")
        sys.exit(1)



    logging.info("Starting server...")
    logging.info(f"Database: {sqlite_url}")

    # create_db_and_tables()
    yield
    # Runs at shutdown
    pass



# ######################################################################
# FastAPI main
# ######################################################################
app = FastAPI(
    title="Sticker Wall",
    description="A simple sticker wall server",
    version="0.1.2",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
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
class StickerByUser(SQLModel, table=True):
    __tablename__ = "stickerbyuser"
    __table_args__ = (
        Index('ix_sticker_user_telegram_user', 'telegram_user'),
        Index('ix_sticker_user_telegram_id', 'telegram_id'),
        Index('ix_sticker_user_sticker_id', 'sticker_id'),
        {'extend_existing': True}
    )

    id: int | None = Field(default=None, primary_key=True)
    telegram_user: str | None = Field(default=None)
    telegram_id: int = Field(default=0)
    sticker_id: str | None = Field(default=None) # Telegram sticker ID
    file_path: str | None = Field(default=None)  # Path to stored sticker
    created_at: datetime = Field(default_factory=datetime.now)
    enabled: bool = Field(default=True)
    options: dict | None = Field(default=None, sa_column=Column(JSON))  # For future customization


class StickerBan(SQLModel, table=True):
    __tablename__ = "stickerban"
    __table_args__ = (
        Index('ix_sticker_ban_sticker_id', 'sticker_id', unique=True),
        {'extend_existing': True}
    )

    id: int | None = Field(default=None, primary_key=True)
    sticker_id: str | None = Field(default=None)
    reason: str | None = Field(default=None)
    banned_at: datetime = Field(default_factory=datetime.now)

class UserBan(SQLModel, table=True):
    __tablename__ = "userban"
    __table_args__ = (
        Index('ix_user_ban_telegram_user', 'telegram_user'),
        Index('ix_user_ban_telegram_id', 'telegram_id', unique=True),
        {'extend_existing': True}
    )

    id: int | None = Field(default=None, primary_key=True)
    telegram_user: str | None = Field(default=None)
    telegram_id: int = Field(default=0)
    reason: str | None = Field(default=None)
    banned_at: datetime = Field(default_factory=datetime.now)

# ######################################################################




# ######################################################################
# Functions / Modules
# ######################################################################
def create_db_and_tables():
    SQLModel.metadata.create_all(engine, checkfirst=True)

# ------------------------------------------------------------------------------
def get_session():
    with Session(engine) as session:
        yield session
# ------------------------------------------------------------------------------






# Yes... the code may be a mess... but you can't start perfect when you start from scratch something :)



















# ------------------------------------------------------------------------------
@app.websocket("/ws/telegram")
async def websocket_telegram_endpoint(websocket: WebSocket):
    global TELEGRAM_WEBSOCK_API_KEY
    global connected_telegram_clients

    # Get the API key from headers
    headers = dict(websocket.headers)
    client_api_key = headers.get("x-api-key")

    if not client_api_key or client_api_key != TELEGRAM_WEBSOCK_API_KEY:
        logging.warning(f"Token: {client_api_key} / {TELEGRAM_WEBSOCK_API_KEY}")
        logging.warning("Unauthorized WebSocket connection attempt")
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    connected_telegram_clients.append(websocket)

    # logging.debug(f"Connected telegram bots: {len(connected_telegram_clients)}")

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

                    with Session(engine) as session:
                        user_ban = session.exec(
                            select(UserBan)
                            .where(UserBan.telegram_id == int(message["bot_id"]))
                        ).first()

                        if user_ban:
                            logging.warning(f"Banned user {message['bot_user']} attempted to send sticker")
                            continue

                        # Check if sticker is banned
                        sticker_ban = session.exec(
                            select(StickerBan)
                            .where(StickerBan.sticker_id == message["sticker_id"])
                        ).first()

                        if sticker_ban:
                            logging.warning(f"Banned sticker {message['sticker_id']} attempted by user {message['bot_user']}")
                            continue

                        # Check user's sticker count in the last hour
                        one_hour_ago = datetime.now() - timedelta(hours=1)
                        recent_stickers = session.exec(
                            select(StickerByUser)
                            .where(StickerByUser.telegram_id == int(message["bot_id"]))
                            .where(StickerByUser.created_at > one_hour_ago)
                        ).all()

                        if len(recent_stickers) >= defaultUserStickerPolicy["stickerCountMax"]:
                            logging.warning(f"User {message['bot_user']} exceeded sticker limit")
                            continue



                    # Get the base64 data and save it
                    sticker_data = base64.b64decode(message["sticker_data"])
                    file_name = f"{message['sticker_id']}.{message['file_extension']}"
                    file_path = os.path.join("static/stickers", file_name)

                    # Ensure directory exists
                    os.makedirs("static/stickers", exist_ok=True)

                    # Save the file
                    with open(file_path, "wb") as f:
                        f.write(sticker_data)

                    # Save to database
                    with Session(engine) as session:
                        sticker = StickerByUser(
                            telegram_user=message["bot_user"],
                            telegram_id=int(message["bot_id"]),
                            sticker_id=message["sticker_id"],
                            file_path=f"stickers/{file_name}"
                        )
                        session.add(sticker)
                        session.commit()

                    # Create the URL path for clients
                    sticker_url = f"stickers/{file_name}"

                    # Modify message for clients
                    client_message = {
                        "type": "sticker",
                        "bot_user": message["bot_user"],
                        "bot_id": message["bot_id"],
                        "path": sticker_url
                    }

                    # Broadcast to wall clients
                    for client in connected_wall_clients:
                        await client.send_text(json.dumps(client_message))

                    logging.info(f"Sticker saved and broadcast: {file_name}")
                    continue



            except json.JSONDecodeError:
                logging.error(f"Invalid JSON received: {data}")

            except Exception as e:
                logging.error(f"Error processing message: {e}")

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





@app.post("/api/ban/user")
async def ban_user(
        telegram_id: str,
        reason: str | None = None,
        apikey: str = Security(api_key_header)
):
    if not apikey or apikey != API_KEY:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")

    with Session(engine) as session:
        user_ban = UserBan(
            telegram_id=telegram_id,
            reason=reason
        )
        session.add(user_ban)
        session.commit()
        return {"status": "success", "message": f"User {telegram_id} banned"}

@app.post("/api/ban/sticker")
async def ban_sticker(
        sticker_id: str,
        reason: str | None = None,
        apikey: str = Security(api_key_header)
):
    if not apikey or apikey != API_KEY:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")

    with Session(engine) as session:
        sticker_ban = StickerBan(
            sticker_id=sticker_id,
            reason=reason
        )
        session.add(sticker_ban)
        session.commit()
        return {"status": "success", "message": f"Sticker {sticker_id} banned"}
























# ------------------------------------------------------------------------------
# Static mounts to serve stuff - They need to be the last declared to avoid issues or errors due the '/'
# app.mount("/static", StaticFiles(directory="public"), name="static")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
# ------------------------------------------------------------------------------


if __name__ == "__main__":
    # if not API_KEY or API_KEY == "":
    #     # If it is missing or fail, fallback to a random value
    #     API_KEY = str(uuid.uuid4())
    # logger.info(f"API_KEY: {API_KEY}")

    create_db_and_tables()

    # uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
    if LOGGING_LEVEL == logging.DEBUG:
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True, log_level="debug", proxy_headers=True)
    elif LOGGING_LEVEL == logging.INFO:
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True, log_level="info", proxy_headers=True)
    else:
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True, proxy_headers=True)

