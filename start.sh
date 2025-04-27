#!/bin/bash
# Start the FastAPI server in the background
python server.py &

# Start the Telegram bot
python bot.py