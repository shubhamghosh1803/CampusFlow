
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN apt-get update \
    && apt-get upgrade -y \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ /app/

RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
