# 🔄 Инструкция по миграции и запуску

## Шаг 1: Запуск Docker

```bash
docker-compose up --build -d
```

## Шаг 2: Создание миграции

```bash
# Создать миграцию
docker-compose exec backend alembic revision --autogenerate -m "add extended university schema"

# Применить миграцию
docker-compose exec backend alembic upgrade head
```

## Шаг 3: Загрузка тестовых данных

```bash
# Создать папку scripts
mkdir -p scripts
touch scripts/__init__.py

# Скопировать скрипт seed_data.py в scripts/

# Запустить загрузку данных
docker-compose exec backend python -m scripts.seed_data
```

## Шаг 4: Проверка

Открой http://localhost:8000/docs и проверь:

1. **Регистрация/Вход** через созданного админа:
   - Email: `admin@university.kz`
   - Password: `admin123`

2. **Получение списка университетов**: `GET /universities/`

3. **Детальная информация**: `GET /universities/1`

4. **Поиск программ**: `GET /universities/programs/search?degree=bachelor`

5. **Сравнение вузов**: `POST /universities/compare` 
   ```json
   {
     "university_ids": [1, 2]
   }
   ```

## Альтернатива: Запуск без Docker

```bash
# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt

# Создать базу
createdb university_db

# Применить миграции
alembic upgrade head

# Загрузить данные
python -m scripts.seed_data

# Запустить сервер
uvicorn app.main:app --reload
```

## Полезные команды

```bash
# Остановить контейнеры
docker-compose down

# Удалить базу данных и начать заново
docker-compose down -v
docker-compose up --build

# Просмотр логов
docker-compose logs -f backend

# Подключение к базе данных
docker-compose exec db psql -U postgres -d university_db
```

## Структура API

### Университеты
- `GET /universities/` - Список с фильтрами
- `GET /universities/{id}` - Детальная информация
- `POST /universities/` - Создать (админ)
- `PATCH /universities/{id}` - Обновить (админ)
- `DELETE /universities/{id}` - Удалить (админ)

### Программы
- `POST /universities/{id}/programs` - Добавить программу
- `GET /universities/programs/search` - Поиск программ

### Факультеты
- `POST /universities/{id}/faculties` - Добавить факультет

### Гранты
- `POST /universities/{id}/grants` - Добавить грант
- `GET /universities/{id}/grants` - Список грантов

### Общежития
- `POST /universities/{id}/dormitories` - Добавить общежитие

### Избранное
- `POST /universities/{id}/favorite` - Добавить в избранное
- `DELETE /universities/{id}/favorite` - Удалить из избранного
- `GET /universities/favorites/my` - Мои избранные

### Сравнение
- `POST /universities/compare` - Сравнить университеты

## Примеры запросов

### Поиск университетов с общежитием в Алматы
```bash
curl "http://localhost:8000/universities/?city=Алматы&has_dormitory=true"
```

### Поиск бакалаврских программ до 1.5 млн
```bash
curl "http://localhost:8000/universities/programs/search?degree=bachelor&max_price=1500000"
```

### Сравнение двух университетов
```bash
curl -X POST "http://localhost:8000/universities/compare" \
  -H "Content-Type: application/json" \
  -d '{"university_ids": [1, 2]}'
```
