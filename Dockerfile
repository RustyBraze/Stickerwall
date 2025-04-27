# Use Python 3.11 base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY server.py .
COPY bot.py .

RUN mkdir public
COPY public ./public

## Create stickers directory
#RUN mkdir stickers

# Expose port for FastAPI server
EXPOSE 8000

# Copy startup script
COPY start.sh .
RUN chmod +x start.sh

# Run both services using the start script
CMD ["./start.sh"]