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
    import secrets

    from contextlib import asynccontextmanager

    from fastapi import FastAPI, WebSocket, HTTPException, Security, Response
    from fastapi.security.api_key import APIKeyHeader
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware

    from dotenv import load_dotenv, dotenv_values

    from starlette.websockets import WebSocketDisconnect
    from starlette.status import HTTP_403_FORBIDDEN

    from typing import List, Annotated, Optional, Dict

    from datetime import datetime, timezone, timedelta

    from sqlalchemy import Column, JSON, Index
    from sqlmodel import Field, Session, SQLModel, create_engine, select, distinct

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
# Make sure we load the .env file
load_dotenv()

API_KEY:str = ""
TELEGRAM_WEBSOCK_API_KEY:str = ""

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

BASE_PATH:str = os.getcwd() # Return a string representing the current working directory. Example: E:\\ or /VAR/DEV/

# Global token storage
active_tokens = {}

# Websocket clients
connected_telegram_clients = []
connected_wall_clients = []

# ------------------------------------------------------------------------------
# SQLITE Stuff
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{os.path.join(BASE_PATH, sqlite_file_name)}" # The file should be saved on the same directory as the application
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args, echo=False)
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
wallSettingsDefault = {
    "debugEnableBoxes": 1,                  # Enable lines around boxes
    "debugEnableMessages": 1,               # Enable Debug messages

    "botUsername": "",
    "botFullName": "",

    "stickerMaxCount": 150,                 # Maximum stickers to be displayed
    "stickerSizeMax": 200,                  # Size in px
    "stickerSizeMin": 100,                  # Size in px
    "stickerResizeFactor": 0,               # Used to calculate the factor between Max/Min
    "stickerRestitution": 0.5,              #
    "stickerFrictionAir": 0.01,             #
    "stickerFriction": 0.01,                #
    "stickerInertia": 0,                    # 0 = Infinite
    "stickerInverseInertia": 0,             #

    "WorldGravityStartValueX": 0,           # Initial World Gravity value X
    "WorldGravityStartValueY": 0,           # Initial World Gravity value Y
    "WorldGravityShiftEnable": 1,           # 1 = Enables periodic Gravity Shift
    "WorldGravityShiftTime": 30,            # For how long in seconds the gravity shall be applied
    "WorldGravityStopTime": 10,             # When to stop the gravity shift
    "WorldgravityShiftFactor": 0.001,       #
    "stickerDriftForceEnable": 1,           # Enable Drift Force
    "stickerDriftForce": 0.0005,            # Force factor
    "stickerDriftForceInterval": 10,        # When to apply the force in seconds
    "StickerlifeSpanMinutes": 0             # How long the sticker should stay
}
wallSettingsActual = wallSettingsDefault.copy()









# ------------------------------------------------------------------------------
# ######################################################################


# ######################################################################
# FastAPI new Startup/Shutdown
# ######################################################################
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs at startup
    global API_KEY
    global TELEGRAM_WEBSOCK_API_KEY

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
    version="0.1.3",
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
    telegram_fullname: str | None = Field(default=None)
    telegram_id: int = Field(default=0)
    sticker_id: str | None = Field(default=None) # Telegram sticker ID
    file_path: str | None = Field(default=None)  # Path to stored sticker
    created_at: datetime = Field(default_factory=datetime.now)
    enabled: bool = Field(default=True)
    options: dict | None = Field(default=None, sa_column=Column(JSON))  # For future customization
# ------------------------------------------------------------------------------
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
# ------------------------------------------------------------------------------
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
# ------------------------------------------------------------------------------
class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        Index('ix_users_username', 'username', unique=True),
        {'extend_existing': True}
    )

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
# ------------------------------------------------------------------------------
# ######################################################################

# ------------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str
# ------------------------------------------------------------------------------
class WallMessageType:
    CLEAR = "wall_clear"
    RELOAD = "wall_reload"
    STICKER_ADD = "sticker_add"
    STICKER_REMOVE = "sticker_remove"
# ------------------------------------------------------------------------------



# ######################################################################
# Functions / Modules
# ######################################################################
# ------------------------------------------------------------------------------
def create_db_and_tables():
    SQLModel.metadata.create_all(engine, checkfirst=True)
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
def get_session():
    with Session(engine) as session:
        yield session
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
def create_access_token() -> str:
    return secrets.token_urlsafe(32)
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
def create_initial_admin(session: Session, admin_password: str) -> None:
    if not admin_password:
        logger.warning("No INITIAL_ADMIN_PASSWORD set, skipping admin creation")
        sys.exit(1)

    # Check if admin user exists
    admin = session.exec(select(User).where(User.username == "admin")).first()
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
def verify_token(token: str) -> bool:
    if token not in active_tokens:
        return False

    token_data = active_tokens[token]
    if datetime.now() > token_data["expires"]:
        del active_tokens[token]
        return False

    return True
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
def check_auth(apikey: str = Security(api_key_header)) -> bool:
    if not apikey:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="No API key provided"
        )
    if apikey == API_KEY or verify_token(apikey):
        return True
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN, detail="Invalid API key"
    )
# ------------------------------------------------------------------------------




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


                if message.get("type") == "sticker":

                    with Session(engine) as session:
                        user_ban = session.exec(
                            select(UserBan)
                            .where(UserBan.telegram_id == int(message["telegram_user_id"]))
                        ).first()

                        if user_ban:
                            logging.warning(f"Banned user {message['telegram_username']} attempted to send sticker")
                            continue

                        # Check if sticker is banned
                        sticker_ban = session.exec(
                            select(StickerBan)
                            .where(StickerBan.sticker_id == message["sticker_id"])
                        ).first()

                        if sticker_ban:
                            logging.warning(f"Banned sticker {message['sticker_id']} attempted by user {message['telegram_username']}")
                            continue

                        # Check user's sticker count in the last hour
                        one_hour_ago = datetime.now() - timedelta(hours=1)
                        recent_stickers = session.exec(
                            select(StickerByUser)
                            .where(StickerByUser.telegram_id == int(message["telegram_user_id"]))
                            .where(StickerByUser.created_at > one_hour_ago)
                        ).all()

                        if len(recent_stickers) >= defaultUserStickerPolicy["stickerCountMax"]:
                            logging.warning(f"User {message['telegram_username']} exceeded sticker limit")
                            error_message = {
                                "type": "user_message",
                                "user_id": message["telegram_user_id"],
                                "message": f"You've reached the limit of {defaultUserStickerPolicy['stickerCountMax']} stickers per hour. Please try again later. !!POLICY NOT BEEN ENFORCED!!"
                            }
                            # Broadcast to Bot servers - yup, the only way to work
                            # TODO: Fix this to return to the only connected client (not an issue because it is only 1 bot connected usually)
                            await ws_broadcast_to_telegram_clients(error_message)
                            # for client in connected_telegram_clients:
                            #     await client.send_text(json.dumps(error_message))
                            # continue

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
                            telegram_user=message["telegram_username"],
                            telegram_fullname=message["telegram_full_username"],
                            telegram_id=int(message["telegram_user_id"]),
                            sticker_id=message["sticker_id"],
                            file_path=f"stickers/{file_name}"
                        )
                        session.add(sticker)
                        session.commit()

                    # Create the URL path for clients
                    sticker_url = f"stickers/{file_name}"

                    # Modify message for clients
                    client_message = {
                        "type": WallMessageType.STICKER_ADD,
                        "data": {
                            "sticker_id": message["sticker_id"],
                            "path": sticker_url
                        # "action": "new",
                        # "telegram_user": message["bot_user"],
                        # "telegram_userid": message["bot_id"],
                        }
                    }

                    # Broadcast to wall clients
                    await ws_broadcast_to_wall_clients(client_message)
                    # for client in connected_wall_clients:
                    #     await client.send_text(json.dumps(client_message))

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
# ##############################################################################
# END WEBSOCKET Endpoints
# ##############################################################################



# /api/wall/clear - remove all stickers
# /api/wall/reload - reload all stickers from database
# /api/wall/config - set/load wall configuration
# /api/wall/sticker - add/remove individual sticker






@app.post("/api/wall/clear")
async def clear_wall(apikey: str = Security(api_key_header)):
    """Clear all stickers from the wall"""
    # TODO: Fix the authentication
    # if check_auth(apikey):
    message = {
        "type": WallMessageType.CLEAR,
        "data": None
    }
    await ws_broadcast_to_wall_clients(message)
    return {"status": "success", "message": "Wall cleared"}

@app.post("/api/wall/reload")
async def reload_wall(apikey: str = Security(api_key_header)):
    """Reload all enabled stickers from database"""
    # TODO: Fix the authentication
    # if check_auth(apikey):
    with (Session(engine) as session):
        # Get all enabled stickers
        # stickers = session.exec(
        #     select(StickerByUser)
        #     .where(StickerByUser.enabled == True)
        #     .distinct(StickerByUser.sticker_id)
        # ).all()

        base_query = select(
            StickerByUser.sticker_id,
            StickerByUser.file_path,
            StickerByUser.enabled
        ).where(
            StickerByUser.enabled == True
        ).distinct(StickerByUser.sticker_id)

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
                    "sticker_id": sticker.sticker_id,
                    "path": sticker.file_path
                }
            }
            await ws_broadcast_to_wall_clients(add_message)

        return {"status": "success", "message": f"Reloaded {len(stickers)} stickers"}

@app.put("/api/wall/sticker/{sticker_id}")
async def enable_sticker(sticker_id: str, apikey: str = Security(api_key_header)):
    """Enable and show a sticker on the wall"""
    # TODO: Fix the authentication
    # if check_auth(apikey):
    with Session(engine) as session:
        sticker = session.exec(
            select(StickerByUser)
            .where(StickerByUser.sticker_id == sticker_id)
        ).first()

        if not sticker:
            raise HTTPException(status_code=404, detail="Sticker not found")

        sticker.enabled = True
        session.commit()

        message = {
            "type": WallMessageType.STICKER_ADD,
            "data": {
                "sticker_id": sticker.sticker_id,
                "path": sticker.file_path
            }
        }
        await ws_broadcast_to_wall_clients(message)
        return {"status": "success", "message": "Sticker enabled"}

@app.delete("/api/wall/sticker/{sticker_id}")
async def disable_sticker(sticker_id: str, apikey: str = Security(api_key_header)):
    """Disable and remove a sticker from the wall"""
    # TODO: Fix the authentication
    # if check_auth(apikey):
    with Session(engine) as session:
        sticker = session.exec(
            select(StickerByUser)
            .where(StickerByUser.sticker_id == sticker_id)
        ).first()

        if not sticker:
            raise HTTPException(status_code=404, detail="Sticker not found")

        sticker.enabled = False
        session.commit()

        message = {
            "type": WallMessageType.STICKER_REMOVE,
            "data": {
                "sticker_id": sticker.sticker_id
            }
        }
        await ws_broadcast_to_wall_clients(message)
        return {"status": "success", "message": "Sticker disabled"}
















# ------------------------------------------------------------------------------
@app.get("/api/wall/config")
async def get_wall_config(apikey: str = Security(api_key_header)) -> Response:

    # if not apikey:
    #     raise HTTPException(
    #         status_code=HTTP_403_FORBIDDEN, detail="Could not validate API key"
    #     )
    # if apikey != API_KEY:
    #     raise HTTPException(
    #         status_code=HTTP_403_FORBIDDEN, detail="Nope... Could not validate API key"
    #     )

    return Response(content=json.dumps(wallSettingsActual), media_type="application/json")
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# @app.post("/api/wall/config")
# async def post_wall_config(apikey: str = Security(api_key_header), item: Body):
#
#     # if not apikey:
#     #     raise HTTPException(
#     #         status_code=HTTP_403_FORBIDDEN, detail="Could not validate API key"
#     #     )
#     # if apikey != API_KEY:
#     #     raise HTTPException(
#     #         status_code=HTTP_403_FORBIDDEN, detail="Nope... Could not validate API key"
#     #     )
#
#     return Response(content=json.dumps(wallSettingsActual), media_type="application/json")


# ------------------------------------------------------------------------------
@app.get("/api/stickers", response_model=List[str])
async def list_stickers(apikey: str = Security(api_key_header)):
    # Gets a list of stickers from the system

    # print(f"API_KEY expected/received: {API_KEY}/{apikey}")

    # if not apikey:
    #     raise HTTPException(
    #         status_code=HTTP_403_FORBIDDEN, detail="Could not validate API key"
    #     )
    # if apikey != API_KEY:
    #     raise HTTPException(
    #         status_code=HTTP_403_FORBIDDEN, detail="Nope... Could not validate API key"
    #     )
    try:
        with Session(engine) as session:
            # First, get unique sticker IDs with their basic info
            base_query = select(
                StickerByUser.sticker_id,
                StickerByUser.file_path,
                StickerByUser.enabled
            ).distinct()

            unique_stickers = session.exec(base_query).all()
            result = []

            # For each unique sticker, get all users who sent it
            for sticker in unique_stickers:
                users_query = select(
                    StickerByUser.telegram_user,
                    StickerByUser.telegram_fullname,
                    StickerByUser.telegram_id
                ).where(
                    StickerByUser.sticker_id == sticker.sticker_id
                ).distinct()

                users = session.exec(users_query).all()

                sticker_entry = {
                    "sticker_id": sticker.sticker_id,
                    "file_path": sticker.file_path,
                    "enabled": sticker.enabled,
                    "telegram": [
                        {
                            "user": user.telegram_fullname,
                            "id": f"@{user.telegram_user}"
                            # "id": str(user.telegram_id)
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

# ------------------------------------------------------------------------------
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
        token = create_access_token()
        active_tokens[token] = {
            "user_id": user.id,
            "expires": datetime.now() + timedelta(hours=24)
        }

        return {"access_token": token, "token_type": "bearer"}
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
@app.post("/api/auth/logout")
async def logout(apikey: str = Security(api_key_header)):
    if apikey in active_tokens:
        del active_tokens[apikey]
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



if __name__ == "__main__":
    # if not API_KEY or API_KEY == "":
    #     # If it is missing or fail, fallback to a random value
    #     API_KEY = str(uuid.uuid4())
    # logger.info(f"API_KEY: {API_KEY}")

    create_db_and_tables()
    with Session(engine) as session:
        create_initial_admin(session, os.getenv("INITIAL_ADMIN_PASSWORD"))


# uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
    if LOGGING_LEVEL == logging.DEBUG:
        uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True, log_level="debug", proxy_headers=True)
    elif LOGGING_LEVEL == logging.INFO:
        uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True, log_level="info", proxy_headers=True)
    else:
        uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True, proxy_headers=True)

