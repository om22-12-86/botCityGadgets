FROM python:3.10-slim

# Устанавливаем зависимости для сборки psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    build-essential

# Устанавливаем рабочую директорию
WORKDIR /bot

# Копируем проект в контейнер
COPY . /bot

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Указываем команду для запуска бота
CMD ["python", "app.py"]
