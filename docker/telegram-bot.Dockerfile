FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    python-telegram-bot[all]>=21.0 \
    httpx>=0.28.0

COPY docker/telegram-bot.py /app/bot.py

CMD ["python", "/app/bot.py"]
