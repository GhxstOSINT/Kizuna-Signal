# Build context is the repository root:  docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KIZUNA_ROOT=/srv

WORKDIR /srv

COPY backend/pyproject.toml backend/README.md ./backend/
COPY backend/app ./backend/app
COPY data/tables ./data/tables
COPY models ./models
COPY data/synthetic/synthetic_viewing_affinity.csv ./data/synthetic/synthetic_viewing_affinity.csv

RUN pip install --no-cache-dir "./backend[postgres,ml]"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
