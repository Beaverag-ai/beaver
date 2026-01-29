FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    libpq-dev \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY beaver/ beaver/

RUN pip install --no-cache-dir -e .

RUN mkdir -p /app/uploads

EXPOSE 8741

CMD ["python", "-m", "beaver.main", "api"]
