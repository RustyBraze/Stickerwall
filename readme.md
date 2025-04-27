# Sticker Party Wall

A fun interactive web application that creates a dynamic sticker wall where users can send stickers via Telegram, which then appear and move around with physics-based animations on a shared web display.

## Features

- Real-time sticker display with physics animations powered by Matter.js
- Telegram bot integration for sticker submissions
- WebSocket server for real-time updates
- Dockerized deployment support
- Static file serving for stickers and web assets

## Prerequisites

- Python 3.11 or higher
- Node.js (for development)
- Docker (optional, for containerized deployment)

## Getting Started

1. Clone the repository

2. Copy the example configuration files:
   ```bash
   cp .env.example .env
   ```

3. Configure the environment variables in `.env`:
    - `BOT_TOKEN`: Your Telegram bot token (get it from @BotFather)
    - `WEBSOCKET_SERVER_URI`: WebSocket server URL (default: ws://127.0.0.1:8000/ws)
    - `API_KEY`: API key for server authentication

4. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Run the server:
   ```bash
   python server.py
   ```

6. Run the Telegram bot:
   ```bash
   python bot.py
   ```

## Docker Deployment

To run the application using Docker:

```bash
bash docker build -t sticker-wall . docker run -p 8000:8000 -e BOT_TOKEN=your_bot_token -e API_KEY=your_api_key sticker-wall
```

## Docker compose

1. Copy the example configuration file:
    ```bash
   cp compose.example.yml compose.yml
    ```
2. Do the necessary configuration
3. Run compose
   ```bash
   docker compose up --build -d
    ```

## Project Structure

- `server.py` - FastAPI server handling WebSocket connections and static files
- `bot.py` - Telegram bot for receiving and processing stickers
- `public/` - Static files directory
- `public/stickers/` - Directory for stored stickers
- `public/index.html` - Main web interface
- `public/js/main.js` - Frontend JavaScript handling physics animations and WebSocket client

## Contributing

Feel free to submit issues and pull requests to help improve the project.

## License

MIT