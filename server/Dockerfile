FROM python:3.13-slim

WORKDIR /app

COPY . .

#COPY ../requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
