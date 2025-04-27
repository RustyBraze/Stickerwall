import os
import logging
import uuid
# from xmlrpc.client import boolean

import uvicorn
from fastapi import FastAPI, WebSocket, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv, dotenv_values
from starlette.websockets import WebSocketDisconnect
from starlette.status import HTTP_403_FORBIDDEN
from typing import List

# ------------------------------------------------------------------------------
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Just load the env
load_dotenv()

# ------------------------------------------------------------------------------
# API key configuration
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


app = FastAPI(
    title="Sticker Wall",
    description="A simple sticker wall server",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    # docs_url="/docs",
    # redoc_url="/redoc",
)

# Static mounts to serve stuff
app.mount("/static", StaticFiles(directory="public"), name="static")

# Websocket clients
connected_clients = []

# ------------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logging.info(f"Connected clients: {len(connected_clients)}")

    try:
        while True:
            data = await websocket.receive_text()
            logging.info(f"Received message: {data}")
            # Broadcast to all connected clients
            for client in connected_clients:
                if client != websocket:
                    await client.send_text(data)

    except WebSocketDisconnect:
        # logging.info("Client disconnected")
        pass

    except Exception as e:
        print(f"WebSocket error: {e}")

    finally:
        connected_clients.remove(websocket)

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
        sticker_files = [f for f in os.listdir("public/stickers") if f.endswith('.webp')]

        # Broadcast the entire list to all connected clients
        for client in connected_clients:
            for sticker in sticker_files:
                sticker_path = f"stickers/{sticker}"
                await client.send_text(sticker_path)

        # Return the list of sticker paths
        return [f"stickers/{sticker}" for sticker in sticker_files]

    except Exception as e:
        logging.error(f"Error listing stickers: {e}")
        raise HTTPException(status_code=500, detail="Error listing stickers")


if __name__ == "__main__":
    logging.info("Starting server...")

    if not API_KEY or API_KEY == "":
        # If it is missing or fail, fallback to a random value
        API_KEY = str(uuid.uuid4())
    logger.info(f"API_KEY: {API_KEY}")

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
