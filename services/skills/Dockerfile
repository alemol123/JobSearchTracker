FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PORT=8000

# Dependencies first, so this layer is reused when only .py files change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only what the service needs to run (no COPY . .): no tests, .venv or local files.
COPY app.py db.py migrate.py ./
COPY skills/ skills/
COPY migrations/ migrations/

RUN useradd --create-home app
USER app

EXPOSE 8000
# Migrate first, then serve. One worker, and max 1 replica on Azure, so migrations never run twice at once.
CMD ["sh", "-c", "python migrate.py && exec gunicorn -w 1 -b 0.0.0.0:${PORT} 'app:create_app()'"]
