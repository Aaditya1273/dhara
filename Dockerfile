FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# collectstatic needs a key at build time only; the real SECRET_KEY comes from the runtime environment.
RUN SECRET_KEY=build-only DEBUG=False python manage.py collectstatic --noinput
RUN useradd --create-home dhara && mkdir -p /app/media && chown -R dhara /app/media
USER dhara
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn project_qr.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
