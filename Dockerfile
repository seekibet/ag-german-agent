FROM python:3.11-slim

WORKDIR /app

# deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app
COPY . .

# host injects PORT; default 8000 for local `docker run`
ENV PORT=8000
EXPOSE 8000

# NOTE: no --reload in production
CMD ["sh", "-c", "uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
