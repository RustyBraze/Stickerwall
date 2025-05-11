# ######################################################################
# Application: Backend - Sticker wall
# Description: Backend that manages the interface between the BOT and the
# webpage that shows the stickers
#
# ######################################################################
from json import JSONDecodeError

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
    import secrets
    import time

    from enum import Enum

    from contextlib import asynccontextmanager

    from fastapi import FastAPI, WebSocket, HTTPException, Security, Response, Depends
    from fastapi.security.api_key import APIKeyHeader
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware

    from dotenv import load_dotenv, dotenv_values

    from starlette.websockets import WebSocketDisconnect
    from starlette.status import HTTP_403_FORBIDDEN

    from typing import List, Annotated, Optional, Dict

    from datetime import datetime, timezone, timedelta

    from sqlalchemy import Column, JSON, Index, inspect
    from sqlmodel import Field, Session, SQLModel, create_engine, select, distinct, func, desc, and_

    from passlib.context import CryptContext

    from pydantic import BaseModel

except Exception as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)
# ######################################################################

# ######################################################################
# DEBUG MODE CHECK
# ######################################################################
if __debug__:
    LOGGING_LEVEL = logging.DEBUG # Enable DEBUG by default
    # print(f"({__name__}) - WARNING: Running in DEBUG Mode. For Production, run with -O - Example: python -O potato_file.py")
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
# Make sure we load the .env file
load_dotenv()

TELEGRAM_WEBSOCK_API_KEY:str = ""

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

BASE_PATH:str = os.getcwd() # Return a string representing the current working directory. Example: E:\\ or /VAR/DEV/

# Websocket clients
connected_telegram_clients = []
connected_wall_clients = []

# ------------------------------------------------------------------------------
# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ------------------------------------------------------------------------------
# Default user policy
defaultUserStickerPolicy = {
    "stickerCountMax" : 3,
    "policyType" : "",               # xxxxxxxxxxxxxxxxxx
    "stickerPeriod" : 3600,
    "stickerPeriodUnit" : "seconds"
}

bot_information = {
    "username": "",  # Default value
    "full_name": ""  # Default value
}

# ######################################################################
# SQLITE Stuff
# ######################################################################
# ------------------------------------------------------------------------------
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{os.path.join(BASE_PATH, 'data' ,sqlite_file_name)}" # The file should be saved on the same directory as the application
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args, echo=False)
# engine = create_engine(sqlite_url, echo=True)
# ------------------------------------------------------------------------------
# ######################################################################
# END SQLITE Stuff
# ######################################################################









# ######################################################################
# FastAPI new Startup/Shutdown
# ######################################################################
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs at startup
    # global API_KEY
    global TELEGRAM_WEBSOCK_API_KEY
    global engine

    # ------------------------------------------------------------------------------
    # Configurations
    # ------------------------------------------------------------------------------
    # API_KEY = os.getenv("BACKEND_API_KEY")
    TELEGRAM_WEBSOCK_API_KEY = os.getenv("BOT_SERVER_WEBSOCKET_API_KEY")
    # api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
    # ------------------------------------------------------------------------------
    # print(TELEGRAM_WEBSOCK_API_KEY)
    # sys.exit(0)

    # Sanity check
    if not all([TELEGRAM_WEBSOCK_API_KEY]):
        print("Missing required environment variables")
        sys.exit(1)

    if "" in [TELEGRAM_WEBSOCK_API_KEY]:
        print("Empty required environment variables")
        sys.exit(1)

    # logging.info('*' * 20)
    logging.info(f"Starting server...")
    # logging.info('*' * 20)

    # logging.info("Starting server...")
    logging.info(f"Database: {sqlite_url}")

    # SQLModel.metadata.create_all(engine, checkfirst=False)
    # with Session(engine) as session:
    #     create_initial_admin(session, os.getenv("INITIAL_ADMIN_PASSWORD"))
    create_db_and_tables()

    yield
    # Runs at shutdown
    pass



# ######################################################################
# FastAPI main
# ######################################################################
app = FastAPI(
    title="Sticker Wall",
    description="A simple sticker wall server",
    version="0.2.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
    # docs_url="/docs",
    # redoc_url="/redoc",
)

# Allow CORS (optional but useful for frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ######################################################################



# ######################################################################
# Database Models
# ######################################################################
class Sticker(SQLModel, table=True):
    __tablename__ = "stickers"
    __table_args__ = (
        Index('ix_stickers_sticker_id', 'sticker_id', unique=True),
        {'extend_existing': True}
    )

    id: int | None = Field(default=None, primary_key=True)
    sticker_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sticker_id: str | None = Field(default=None)  # sticker id from telegram bot
    sticker_path: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    visible: bool = Field(default=True)
    banned: bool = Field(default=False)
    reason: str | None = Field(default=None)
    boost_factor: int = Field(default=0)
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
class TelegramUser(SQLModel, table=True):
    __tablename__ = "telegram_users"
    __table_args__ = (
        Index('ix_telegram_users_userid', 'userid', unique=True),
        {'extend_existing': True}
    )

    id: int | None = Field(default=None, primary_key=True)
    userid: int = Field(unique=True)  # telegram user ID
    username: str | None = Field(default=None)
    fullusername: str | None = Field(default=None)
    last_chatid: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    last_message: datetime | None = Field(default=None)
    banned: bool = Field(default=False)
    reason: str | None = Field(default=None)
    admin: bool = Field(default=False)
    policy: dict | None = Field(default=None, sa_column=Column(JSON))
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
class TelegramUserSticker(SQLModel, table=True):
    __tablename__ = "telegram_user_stickers"
    __table_args__ = (
        Index('ix_telegram_user_stickers_user_id', 'user_id'),
        Index('ix_telegram_user_stickers_sticker_id', 'sticker_id'),
        {'extend_existing': True}
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="telegram_users.id")
    sticker_id: int = Field(foreign_key="stickers.id")
    sent_at: datetime = Field(default_factory=datetime.now)
    blocked_by_policy: bool = Field(default=False)
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        {'extend_existing': True}
    )

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    name: str = Field(default="Default Key")
    created_at: datetime = Field(default_factory=datetime.now)
    last_used: datetime | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)
    is_active: bool = Field(default=True)
    description: Optional[str] = Field(default=None)
# ------------------------------------------------------------------------------
# ######################################################################
# END Database Models
# ######################################################################

# ------------------------------------------------------------------------------
# ######################################################################
def create_db_and_tables():
    """Create tables if they don't exist"""

    # global engine

    # inspector = inspect(engine)
    # existing_tables = inspector.get_table_names()
    #
    # tables_to_check = [
    #     (Sticker, "stickers"),
    #     (TelegramUser, "telegram_users"),
    #     (TelegramUserSticker, "telegram_user_stickers"),
    #     (User, "users"),
    #     (APIKey, "api_keys")
    # ]
    #
    # for model, table_name in tables_to_check:
    #     if table_name not in existing_tables:
    #         model.__table__.create(engine)
    #         logger.info(f"Created table: {table_name}")
    #     else:
    #         logger.info(f"Table already exists: {table_name}")

    SQLModel.metadata.create_all(engine, checkfirst=True)
    # SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        create_initial_admin(session, os.getenv("INITIAL_ADMIN_PASSWORD"))
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
class APIKeyCreate(BaseModel):
    name: str
    description: Optional[str] = None
# ------------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str
# ------------------------------------------------------------------------------
class WallMessageType(str, Enum):
    CLEAR = "wall_clear"
    RELOAD = "wall_reload"
    RESTART = "wall_restart"
    STICKER_ADD = "sticker_add"
    STICKER_REMOVE = "sticker_remove"
    BOT_INFO = "bot_info"
# ------------------------------------------------------------------------------
class StickerActionType(str, Enum):
    BAN = "ban"
    UNBAN = "unban"
    HIDE = "hide"
    SHOW = "show"
# ------------------------------------------------------------------------------
class StickerActionRequest(BaseModel):
    type: StickerActionType
    reason: Optional[str] = None
# ------------------------------------------------------------------------------



# ######################################################################
# Functions / Modules
# ######################################################################
# ------------------------------------------------------------------------------
# def get_session():
#     with Session(engine) as session:
#         yield session
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# API-KEY management
# ------------------------------------------------------------------------------
def create_api_key(session, name: str, description: str | None = None) -> APIKey:
    """Create a new API key"""
    api_key = APIKey(
        key=secrets.token_urlsafe(32),
        name=name,
        description=description,
        expires_at=datetime.now() + timedelta(hours=1)  # Set initial expiration
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key
# ------------------------------------------------------------------------------
def validate_api_key(session, key: str) -> bool:
    """Validate an API key and update last used timestamp and expiration"""
    current_time = datetime.now()

    api_key = session.exec(
        select(APIKey)
        .where(APIKey.key == key)
        .where(APIKey.is_active == True)
        .where((APIKey.expires_at > current_time) | (APIKey.expires_at.is_(None)))
    ).first()

    if api_key:
        # Update last used time and extend expiration
        api_key.last_used = current_time
        api_key.expires_at = current_time + timedelta(hours=1)  # Reset timeout on use
        session.commit()
        return True
    return False
# ------------------------------------------------------------------------------
def invalidate_api_key(session, key: str) -> bool:
    """Invalidate an API key"""
    api_key = session.exec(
        select(APIKey)
        .where(APIKey.key == key)
        .where(APIKey.is_active == True)
    ).first()

    if api_key:
        APIKey.is_active = False
        session.commit()
        return True
    return False
# ------------------------------------------------------------------------------
async def verify_api_key(api_key: str = Security(api_key_header)) -> bool:
    """Verify API key and return boolean"""
    with Session(engine) as session:
        if validate_api_key(session, api_key):
            return True
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
# ------------------------------------------------------------------------------
async def cancel_api_key(api_key: str = Security(api_key_header)) -> bool:
    """Cancel the API key and return boolean"""
    with Session(engine) as session:
        if invalidate_api_key(session, api_key):
            return True
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
# ------------------------------------------------------------------------------
# END API-KEY management
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
def create_initial_admin(session: Session, admin_password: str) -> None:
    if not admin_password:
        logger.warning("No INITIAL_ADMIN_PASSWORD set, skipping admin creation")
        sys.exit(1)

    # Check if admin user exists
    admin = session.exec(
        select(User)
        .where(User.username == "admin")
    ).first()

    if not admin:
        admin = User(
            username="admin",
            hashed_password=get_password_hash(admin_password),
            is_admin=True
        )
        session.add(admin)
        session.commit()
        logger.info("Created initial admin user")
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
def update_bot_info(username: str, full_name: str):
    """Update the bot information globally"""
    global bot_information
    bot_information["username"] = username
    bot_information["full_name"] = full_name


# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------



# ######################################################################
# Websocket broadcast section
# ######################################################################
# ------------------------------------------------------------------------------
async def ws_broadcast_to_wall_clients(message: dict):
    for client in connected_wall_clients:
        await client.send_text(json.dumps(message))
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
async def ws_broadcast_to_telegram_clients(message: dict):
    for client in connected_telegram_clients:
        await client.send_text(json.dumps(message))
# ------------------------------------------------------------------------------
# ######################################################################
# END Websocket broadcast section
# ######################################################################


# Yes... the code may be a mess... but you can't start perfect when you start from scratch something :)

















# ##############################################################################
# WEBSOCKET Endpoints
# ##############################################################################
# ------------------------------------------------------------------------------
@app.websocket("/ws/telegram")
async def websocket_telegram_endpoint(websocket: WebSocket):
    """
    Handles WebSocket connections for Telegram-related communications.

    This endpoint authenticates WebSocket connections based on API keys, manages connected Telegram clients,
    and processes incoming data. The endpoint validates user activity against specific bans, rate limits the
    sticker uploads, and ensures the secure handling of stickers via base64 encoding and storage. It also
    broadcasts updates to other WebSocket clients.

    The implementation includes input validation, real-time data processing, storage operations,
    and error handling for smooth communication between the bot servers and wall clients.

    Arguments:
        websocket (WebSocket): Represents the active WebSocket connection being handled.

    Raises:
        None

    Returns:
        None
    """
    global TELEGRAM_WEBSOCK_API_KEY
    global connected_telegram_clients
    global bot_information

    # Get the API key from headers
    headers = dict(websocket.headers)
    client_api_key = headers.get("x-api-key")

    if not client_api_key or client_api_key != TELEGRAM_WEBSOCK_API_KEY:
        # logging.warning(f"Token: {client_api_key} / {TELEGRAM_WEBSOCK_API_KEY}")
        logging.warning("Unauthorized WebSocket connection attempt - Invalid API KEY")
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

                if message.get("type") == "bot_info":
                    # print('*' * 20)
                    # print(message)
                    # print('*' * 20)
                    print(message.get("username"), message.get("full_name"))
                    update_bot_info(
                        username=message.get("username", "..."),
                        full_name=message.get("full_name", "Sticker Wall Bot")
                    )
                    send_message = {
                        "type": "bot_info",
                        "data": bot_information
                    }
                    # Broadcast to wall clients
                    await ws_broadcast_to_wall_clients(send_message)
                    continue


                if message.get("type") == "sticker":
                    with Session(engine) as session:
                        # Check if user exists or create new
                        user = session.exec(
                            select(TelegramUser)
                            .where(TelegramUser.userid == int(message["telegram_user_id"]))
                        ).first()

                        logging.info(f"Check: User Ban")

                        if user and user.banned:
                            logging.warning(f"Banned user {message['telegram_username']} attempted to send sticker")
                            continue

                        if not user:
                            user = TelegramUser(
                                userid=int(message["telegram_user_id"]),
                                username=message["telegram_username"],
                                fullusername=message["telegram_full_username"],
                                last_chatid=message.get("chat_id"),
                                last_message=datetime.now()
                            )
                            session.add(user)
                            session.flush()  # Get the user ID
                        else:
                            user.last_message = datetime.now()
                            user.last_chatid = message.get("chat_id")

                        logging.info(f"Check: Sticker Ban")

                        # Check if sticker exists or create new
                        sticker = session.exec(
                            select(Sticker)
                            .where(Sticker.sticker_id == message["sticker_id"])
                        ).first()

                        if sticker and sticker.banned:
                            logging.warning(f"Banned sticker {message['sticker_id']} attempted by user {message['telegram_username']}")
                            continue

                        # logging.info(f"Check: User Policy")
                        #
                        # # Check user's sticker policy
                        # policy = user.policy or defaultUserStickerPolicy
                        # period_start = datetime.now() - timedelta(seconds=policy["stickerPeriod"])
                        # recent_stickers = session.exec(
                        #     select(TelegramUserSticker)
                        #     .where(TelegramUserSticker.user_id == user.id)
                        #     .where(TelegramUserSticker.sent_at > period_start)
                        # ).all()
                        #
                        # if len(recent_stickers) >= policy["stickerCountMax"]:
                        #     error_message = {
                        #         "type": "user_message",
                        #         "user_id": message["telegram_user_id"],
                        #         "message": f"You've reached the limit of {policy['stickerCountMax']} stickers per period."
                        #     }
                        #     logging.info(f"Broadcasting to user")
                        #     await ws_broadcast_to_telegram_clients(error_message)
                        #
                        #     # Record the blocked attempt
                        #     if sticker:
                        #         logging.info(f"Recording blocked attempt")
                        #
                        #         user_sticker = TelegramUserSticker(
                        #             user_id=user.id,
                        #             sticker_id=sticker.id,
                        #             blocked_by_policy=True
                        #         )
                        #         session.add(user_sticker)
                        #         session.flush()  # Get the user ID
                        #
                        #     # continue

                        logging.info(f"Processing sticker")

                        # Process sticker file
                        sticker_data = base64.b64decode(message["sticker_data"])
                        file_name = f"{message['sticker_id']}.{message['file_extension']}"
                        file_path = os.path.join("static/stickers", file_name)

                        # Ensure directory exists
                        os.makedirs("static/stickers", exist_ok=True)

                        # Save the file
                        with open(file_path, "wb") as f:
                            f.write(sticker_data)

                        if not sticker:
                            sticker = Sticker(
                                sticker_id=message["sticker_id"],
                                sticker_path=f"stickers/{file_name}"
                            )
                            session.add(sticker)
                            session.flush()
                        else:
                            sticker.boost_factor += 1

                        # Record user-sticker relationship
                        user_sticker = TelegramUserSticker(
                            user_id=user.id,
                            sticker_id=sticker.id
                        )
                        session.add(user_sticker)
                        session.flush()
                        session.commit()

                        # Create the wall message
                        client_message = {
                            "type": WallMessageType.STICKER_ADD,
                            "data": {
                                "sticker_id": sticker.sticker_uuid,  # Use UUID instead of telegram sticker_id
                                "path": sticker.sticker_path
                            }
                        }

                        # Broadcast to wall clients
                        await ws_broadcast_to_wall_clients(client_message)
                        logging.info(f"Sticker saved and broadcast: {file_name}")

            except json.JSONDecodeError:
                logging.error(f"Invalid JSON received: {data}")

            except Exception as e:
                logging.error(f"Error processing message: {e}")
                # logging.error(f"Data received: {data}")

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
    """
    Asynchronous function to handle WebSocket connections for the wall endpoint. This
    function manages a list of connected WebSocket clients, facilitates broadcasting
    messages to all clients except the sender, and handles client disconnections.

    Arguments:
        websocket (WebSocket): The WebSocket connection object representing the client
            connected to the `/ws/wall` endpoint.

    Raises:
        Exception: Any unexpected exceptions occurring during the WebSocket communication.
    """
    global bot_information

    await websocket.accept()
    connected_wall_clients.append(websocket)
    logging.info(f"Connected clients: {len(connected_wall_clients)}")

    try:

        # Send initial bot info when client connects
        await websocket.send_json({
            "type": "bot_info",
            "data": bot_information
        })

        # while True:
        #     data = await websocket.receive_text()
        #     logging.info(f"Received message: {data}")
        #     # Broadcast to all connected clients
        #     for client in connected_wall_clients:
        #         if client != websocket:
        #             await client.send_text(data)
        while True:
            try:
                data = await websocket.receive_json()

                # Handle get_bot_info request
                if data.get("type") == "get_bot_info":
                    await websocket.send_json({
                        "type": "bot_info",
                        "data": bot_information
                    })

            except WebSocketDisconnect:
                break
            except JSONDecodeError:
                logger.warning("Invalid JSON received from wall client")
                continue
            except Exception as e:
                logger.error(f"Error in wall websocket: {e}")
                break

    except WebSocketDisconnect:
        # logging.info("Client disconnected")
        pass

    except Exception as e:
        print(f"WebSocket error: {e}")

    finally:
        connected_wall_clients.remove(websocket)
# ------------------------------------------------------------------------------
# ##############################################################################
# END WEBSOCKET Endpoints
# ##############################################################################






# ##############################################################################
# API Endpoints
# ##############################################################################


# ------------------------------------------------------------------------------
# Endpoint: /API/ADMIN/*
# ------------------------------------------------------------------------------
@app.post("/api/admin/apikeys")
async def create_new_api_key(
        key_data: APIKeyCreate,
        authenticated: bool = Depends(verify_api_key)
):
    """Create a new API key"""
    with Session(engine) as session:
        api_key = create_api_key(session, key_data.name, key_data.description)
        return {
            "status": "success",
            "message": "API key created successfully",
            "key": api_key.key  # Only shown once at creation
        }
# ------------------------------------------------------------------------------
@app.get("/api/admin/apikeys")
async def list_api_keys(authenticated: bool = Depends(verify_api_key)):
    """List all API keys (without showing the actual keys)"""
    with Session(engine) as session:
        keys = session.exec(select(APIKey)).all()
        current_time = datetime.now()

        return [{
            "id": key.id,
            "name": key.name,
            "created_at": key.created_at,
            "last_used": key.last_used,
            "expires_at": key.expires_at,
            "is_active": key.is_active,
            "is_expired": key.expires_at < current_time if key.expires_at else False,
            "description": key.description
        } for key in keys]
# ------------------------------------------------------------------------------
@app.delete("/api/admin/apikeys/{key_id}")
async def deactivate_api_key(
        key_id: int,
        authenticated: bool = Depends(verify_api_key)
):
    """Deactivate an API key"""
    with Session(engine) as session:
        key = session.get(APIKey, key_id)
        if not key:
            raise HTTPException(status_code=404, detail="API key not found")
        key.is_active = False
        session.commit()
        return {"status": "success", "message": "API key deactivated"}
# ------------------------------------------------------------------------------




# ------------------------------------------------------------------------------
# Endpoint: /API/WALL/*
# ------------------------------------------------------------------------------
@app.post("/api/wall/clear")
async def clear_wall(authenticated: bool = Depends(verify_api_key)):
    """Clear all stickers from the wall"""

    message = {
        "type": WallMessageType.CLEAR,
        "data": None
    }
    await ws_broadcast_to_wall_clients(message)
    return {"status": "success", "message": "Wall cleared"}
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
@app.post("/api/wall/execute")
async def wall_execute(authenticated: bool = Depends(verify_api_key)):
    """Send a command to the wall
    Commands:
    - Reload
    - Clear
    - Restart
    - Config Update
    """

    return {"status": "success", "message": "Wall reloaded"}
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
@app.post("/api/wall/reload")
async def reload_wall(authenticated: bool = Depends(verify_api_key)):
    """Reload all enabled stickers from database"""

    with (Session(engine) as session):
        # Get all enabled stickers
        # stickers = session.exec(
        #     select(StickerByUser)
        #     .where(StickerByUser.enabled == True)
        #     .distinct(StickerByUser.sticker_id)
        # ).all()

        # base_query = select(
        #     StickerByUser.sticker_id,
        #     StickerByUser.file_path,
        #     StickerByUser.enabled
        # ).where(
        #     StickerByUser.enabled == True
        # ).distinct(StickerByUser.sticker_id)

        base_query = select(
            Sticker.sticker_uuid,
            Sticker.sticker_path,
            Sticker.visible,
            Sticker.boost_factor
        ).where(
            and_(
                Sticker.visible == True,
                Sticker.banned == False
            )
        ).order_by(desc(Sticker.boost_factor)).limit(limit=10)  # Show popular stickers first

        stickers = session.exec(base_query).all()

        # First clear the wall
        clear_message = {
            "type": WallMessageType.CLEAR,
            "data": None
        }
        await ws_broadcast_to_wall_clients(clear_message)

        # Then add each sticker
        for sticker in stickers:
            add_message = {
                "type": WallMessageType.STICKER_ADD,
                "data": {
                    "sticker_id": sticker.sticker_uuid,
                    "path": sticker.sticker_path,
                    "boost_factor": sticker.boost_factor
                }
            }
            await ws_broadcast_to_wall_clients(add_message)
            time.sleep(0.1)

        return {"status": "success", "message": f"Reloaded {len(stickers)} stickers"}
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
@app.get("/api/wall/config")
async def get_wall_config(authenticated: bool = Depends(verify_api_key)) -> Response:

    # return Response(content=json.dumps(wallSettingsActual), media_type="application/json")
    return Response(content={"status":"Not implemented"}, media_type="application/json")
# ------------------------------------------------------------------------------




# ------------------------------------------------------------------------------
# Endpoint: /API/STICKERS
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
@app.get("/api/stickers", response_model=List[str])
async def list_stickers(authenticated: bool = Depends(verify_api_key)):
    # Gets a list of stickers from the system
    try:
        with Session(engine) as session:
            # Get stickers with their usage count and users
            stickers_query = (
                select(
                    Sticker,
                    func.count(distinct(TelegramUserSticker.user_id)).label("unique_users"),
                    func.count(TelegramUserSticker.id).label("total_uses")
                )
                .outerjoin(TelegramUserSticker)
                .group_by(Sticker.id)
                .order_by(desc("total_uses"))
            )

            stickers_result = session.exec(stickers_query).all()
            result = []

            for sticker, unique_users, total_uses in stickers_result:
                # Get users who used this sticker
                users_query = (
                    select(TelegramUser)
                    .join(TelegramUserSticker)
                    .where(TelegramUserSticker.sticker_id == sticker.id)
                    .distinct()
                )
                users = session.exec(users_query).all()

                sticker_entry = {
                    "sticker_id": sticker.sticker_id,
                    "sticker_uuid": sticker.sticker_uuid,
                    "file_path": sticker.sticker_path,
                    "visible": sticker.visible,
                    "banned": sticker.banned,
                    "boost_factor": sticker.boost_factor,
                    "stats": {
                        "unique_users": unique_users,
                        "total_uses": total_uses
                    },
                    "telegram": [
                        {
                            "user": user.fullusername,
                            "id": f"@{user.username}"
                        }
                        for user in users
                    ]
                }
                result.append(sticker_entry)

            return Response(content=json.dumps(result), media_type="application/json")

    except Exception as e:
        logging.error(f"Error listing stickers: {e}")
        raise HTTPException(status_code=500, detail="Error listing stickers")
# ------------------------------------------------------------------------------



# ------------------------------------------------------------------------------
@app.post("/api/users/{user_uuid}/ban")
async def ban_user(
        user_uuid: int,
        reason: str | None = None,
        authenticated: bool = Depends(verify_api_key)
):

    with Session(engine) as session:
        user = session.exec(
            select(TelegramUser)
            .where(TelegramUser.userid == user_uuid)
        ).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.banned = True
        user.reason = reason
        session.commit()

        return {"status": "success", "message": f"User {user_uuid} banned"}
# ------------------------------------------------------------------------------







































# ##############################################################################
# /api/stickers
# ##############################################################################





# ------------------------------------------------------------------------------
# @app.post("/api/stickers/{sticker_uuid}/show")
# async def show_sticker(sticker_uuid: str, apikey: str = Security(api_key_header)):
#     """Hide the sticker from the wall"""
#     if not apikey or apikey != API_KEY:
#         raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")
#
#     if not sticker_uuid:
#         raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid StickerID")
#
#     with Session(engine) as session:
#         sticker = session.exec(
#             select(Sticker)
#             .where(Sticker.sticker_uuid == sticker_uuid)
#         ).first()
#
#         if not sticker:
#             raise HTTPException(status_code=404, detail="Sticker not found")
#
#         # Update sticker visibility
#         sticker.visible = True
#         session.commit()
#
#         # Notify wall clients to remove the sticker
#         message = {
#             "type": WallMessageType.STICKER_ADD,
#             "data": {
#                 "sticker_id": sticker.sticker_uuid,
#                 "path": sticker.sticker_path,
#                 "boost_factor": sticker.boost_factor
#             }
#         }
#         await ws_broadcast_to_wall_clients(message)
#
#         return {
#             "status": "success",
#             "message": f"Sticker {sticker_uuid} shown"
#         }
# # ------------------------------------------------------------------------------
#
# # ------------------------------------------------------------------------------
# @app.post("/api/stickers/{sticker_uuid}/hide")
# async def hide_sticker(sticker_uuid: str, apikey: str = Security(api_key_header)):
#     """Hide the sticker from the wall"""
#     if not apikey or apikey != API_KEY:
#         raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")
#
#     if not sticker_uuid:
#         raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid StickerID")
#
#     with Session(engine) as session:
#         sticker = session.exec(
#             select(Sticker)
#             .where(Sticker.sticker_uuid == sticker_uuid)
#         ).first()
#
#         if not sticker:
#             raise HTTPException(status_code=404, detail="Sticker not found")
#
#         # Update sticker visibility
#         sticker.visible = False
#         session.commit()
#
#         # Notify wall clients to remove the sticker
#         message = {
#             "type": WallMessageType.STICKER_REMOVE,
#             "data": {
#                 "sticker_id": sticker.sticker_uuid  # Using UUID for wall communication
#             }
#         }
#         await ws_broadcast_to_wall_clients(message)
#
#         return {
#             "status": "success",
#             "message": f"Sticker {sticker_uuid} hidden"
#         }
# # ------------------------------------------------------------------------------
#
#
#
# # ------------------------------------------------------------------------------
# @app.post("/api/stickers/{sticker_uuid}/unban")
# async def unban_sticker(
#         sticker_uuid: str,
#         reason: str | None = None,
#         apikey: str = Security(api_key_header)
# ):
#     if not apikey or apikey != API_KEY:
#         raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")
#
#     with Session(engine) as session:
#         sticker = session.exec(
#             select(Sticker)
#             .where(Sticker.sticker_uuid == sticker_uuid)
#         ).first()
#
#         if not sticker:
#             raise HTTPException(status_code=404, detail="Sticker not found")
#
#         sticker.banned = False
#         # sticker.reason = reason
#         sticker.visible = False
#         session.commit()
#
#         # # Notify wall clients to remove the sticker
#         # message = {
#         #     "type": WallMessageType.STICKER_REMOVE,
#         #     "data": {
#         #         "sticker_id": sticker.sticker_uuid
#         #     }
#         # }
#         # await ws_broadcast_to_wall_clients(message)
#
#         return {"status": "success", "message": f"Sticker {sticker_uuid} unbanned"}
# # ------------------------------------------------------------------------------
#
# # ------------------------------------------------------------------------------
# @app.post("/api/stickers/{sticker_uuid}/ban")
# async def ban_sticker(
#         sticker_uuid: str,
#         reason: str | None = None,
#         apikey: str = Security(api_key_header)
# ):
#     if not apikey or apikey != API_KEY:
#         raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")
#
#     with Session(engine) as session:
#         sticker = session.exec(
#             select(Sticker)
#             .where(Sticker.sticker_uuid == sticker_uuid)
#         ).first()
#
#         if not sticker:
#             raise HTTPException(status_code=404, detail="Sticker not found")
#
#         sticker.banned = True
#         sticker.reason = reason
#         sticker.visible = False
#         session.commit()
#
#         # Notify wall clients to remove the sticker
#         message = {
#             "type": WallMessageType.STICKER_REMOVE,
#             "data": {
#                 "sticker_id": sticker.sticker_uuid
#             }
#         }
#         await ws_broadcast_to_wall_clients(message)
#
#         return {"status": "success", "message": f"Sticker {sticker_uuid} banned"}

@app.post("/api/stickers/{sticker_uuid}")
async def handle_sticker_action(
        sticker_uuid: str,
        action: StickerActionRequest,
        authenticated: bool = Depends(verify_api_key)
):
    """Handle different sticker actions: ban, unban, hide, show"""
    with Session(engine) as session:
        sticker = session.exec(
            select(Sticker)
            .where(Sticker.sticker_uuid == sticker_uuid)
        ).first()

        if not sticker:
            raise HTTPException(status_code=404, detail="Sticker not found")

        # Handle different action types
        if action.type == StickerActionType.BAN:
            sticker.banned = True
            sticker.visible = False
            sticker.reason = action.reason
            wall_message_type = WallMessageType.STICKER_REMOVE
            message = "Sticker banned successfully"

        elif action.type == StickerActionType.UNBAN:
            sticker.visible = False
            sticker.banned = False
            sticker.reason = None
            wall_message_type = WallMessageType.STICKER_REMOVE
            message = "Sticker unbanned successfully"

        elif action.type == StickerActionType.HIDE:
            sticker.visible = False
            wall_message_type = WallMessageType.STICKER_REMOVE
            message = "Sticker hidden successfully"

        elif action.type == StickerActionType.SHOW:
            if sticker.banned:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot show banned sticker"
                )
            sticker.visible = True
            wall_message_type = WallMessageType.STICKER_ADD
            message = "Sticker shown successfully"

        session.commit()

        # Notify wall clients about the change
        wall_message = {
            "type": wall_message_type,
            "data": {
                "sticker_id": sticker.sticker_uuid,
                "path": sticker.sticker_path
            }
        }
        await ws_broadcast_to_wall_clients(wall_message)

        return {
            "status": "success",
            "message": message,
            "sticker": {
                "uuid": sticker.sticker_uuid,
                "visible": sticker.visible,
                "banned": sticker.banned,
                "reason": sticker.reason,
                "path": sticker.sticker_path
            }
        }
# ------------------------------------------------------------------------------
























# ------------------------------------------------------------------------------
@app.post("/api/users/{user_uuid}/unban")
async def unban_user(
        user_uuid: int,
        reason: str | None = None,
        authenticated: bool = Depends(verify_api_key)
):

    with Session(engine) as session:
        user = session.exec(
            select(TelegramUser)
            .where(TelegramUser.userid == user_uuid)
        ).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.banned = True
        user.reason = reason
        session.commit()

        return {"status": "success", "message": f"User {user_uuid} banned"}
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
@app.get("/api/users")
async def unban_user(authenticated: bool = Depends(verify_api_key)):

    return {"status": "success", "message": f"User potato"}
# ------------------------------------------------------------------------------







# ##############################################################################
# LOGIN / LOGOUT Endpoints
# ##############################################################################
# ------------------------------------------------------------------------------
@app.post("/api/auth/login")
async def login(request: LoginRequest):
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.username == request.username)
        ).first()

        if not user or not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password"
            )

        # Generate token
        token = create_api_key(session=session, name=user.username)
        # active_tokens[token] = {
        #     "user_id": user.id,
        #     "expires": datetime.now() + timedelta(hours=24)
        # }

        return {"access_token": token.key, "token_type": "x-api-key"}
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
@app.post("/api/auth/logout")
async def logout(authenticated: bool = Depends(verify_api_key)):
    return {"message": "Successfully logged out"}
# ------------------------------------------------------------------------------
# ##############################################################################
# END LOGIN / LOGOUT Endpoints
# ##############################################################################


















# ------------------------------------------------------------------------------
# Static mounts to serve stuff - They need to be the last declared to avoid issues or errors due the '/'
# app.mount("/static", StaticFiles(directory="public"), name="static")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
# ------------------------------------------------------------------------------




# if __name__ == "__main__":
#     # if not API_KEY or API_KEY == "":
#     #     # If it is missing or fail, fallback to a random value
#     #     API_KEY = str(uuid.uuid4())
#     # logger.info(f"API_KEY: {API_KEY}")
#
#
#
# # uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
#     if LOGGING_LEVEL == logging.DEBUG:
#         uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True, log_level="debug", proxy_headers=True)
#     elif LOGGING_LEVEL == logging.INFO:
#         uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True, log_level="info", proxy_headers=True)
#     else:
#         uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True, proxy_headers=True)
#
