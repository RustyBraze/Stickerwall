# Sticker Wall - Interactive Telegram Sticker Display

An interactive web application that creates a dynamic sticker wall where users can send stickers via Telegram, which then appear and move around with physics-based animations on a shared web display.

The system is divided in 2 images:
- `rustybraze/stickerbot` - Bot program that talks with Telegram Servers
- `rustybraze/stickerwall` - Frontend and Backend of the system

## Quick Start

The easiest way to get started is using docker-compose:

```yaml
services:
  stickerwall:
    image: rustybraze/stickerwall:latest
    restart: unless-stopped

    environment:
      # Key for the websock communication - BOT Server + Backend Server use this to authenticate
      BOT_SERVER_WEBSOCKET_API_KEY: ""
      # Initial password for the user admin (access via admin.html page)
      INITIAL_ADMIN_PASSWORD: ""

    volumes:
      - ./data/stickers:/app/static/stickers
      - ./data/data:/app/data

    ports:
      - 8000:8000

    networks:
      - sticker_net

  # ------------------------------------------------------------------------------

  stickerbot:
    image: rustybraze/stickerbot:latest
    restart: unless-stopped

    environment:
      PYTHONUNBUFFERED: 1
      # Key for the websock communication - BOT Server + Backend Server use this to authenticate
      BOT_SERVER_WEBSOCKET_API_KEY: ""
      # Telegram NOT TOKEN (From @Botfather)
      BOT_SERVER_TELEGRAM_BOT_TOKEN: ""
      # Internal websock to exchange communication (set the IP of the server or the image name)
      BOT_SERVER_WEBSOCKET_SERVER_URI: "ws://stickerwall:8000/ws/telegram"

    depends_on:
      - stickerwall

    networks:
      - sticker_net

networks:
  sticker_net:
    driver: bridge
``` 

## Configuration

### Required Environment Variables

#### Sticker Wall Server (stickerwall)
- `BOT_SERVER_WEBSOCKET_API_KEY`:  API key for WebSocket authentication
- `INITIAL_ADMIN_PASSWORD`:  Initial password for the admin interface

#### Telegram Bot (stickerbot)
- `BOT_SERVER_WEBSOCKET_API_KEY`:  Same API key as the server
- `BOT_SERVER_TELEGRAM_BOT_TOKEN`:  Your Telegram bot token from @BotFather
- `BOT_SERVER_WEBSOCKET_SERVER_URI`:  WebSocket URI for bot-server communication

### Volumes

#### Sticker Wall Server
- `/app/static/stickers`:  Directory for storing sticker files
- `/app/data`:  Directory for SQLite database and other persistent data

## Usage

1. Create a new bot using Telegram's [@BotFather](https://t.me/botfather)
2. Copy the bot token
3. Create a docker-compose.yml file with the configuration above
4. Replace the placeholder values with your actual configuration
5. Run the containers:
  ```bash
  docker compose up -d
  ``` 

## Accessing the Interface

- Landing page: `http://your-server:8000`
- Main wall: `http://your-server:8000/wall.html`
- Admin interface: `http://your-server:8000/admin.html`
    - Default username: `admin`
    - Password: Value of `INITIAL_ADMIN_PASSWORD`

## Features

- Real-time sticker display with physics animations
- Telegram bot integration
- Admin interface for moderation
- Sticker management (show/hide/ban)
- User management
- Configurable display options

## Security Notes

- Change the default admin password after first login
- Use a strong, random WebSocket API key
- Keep your Telegram bot token secure
- Consider using HTTPS reverse proxy in production

## Monitoring

The application logs are available through Docker:

```bash
# View server logs
docker logs -f stickerwall
# View bot logs
docker logs -f stickerbot
``` 

## Updating

To update to the latest version:

```bash
# Pull the latest image
docker compose pull
# Start container
docker compose up -d
```

## Support

For issues and feature requests, please visit our [GitHub repository](https://github.com/RustyBraze/Stickerwall).

## License

MIT License
