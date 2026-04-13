FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# cspell:words adduser gecos appuser
WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

USER appuser

CMD ["python", "main.py"]
