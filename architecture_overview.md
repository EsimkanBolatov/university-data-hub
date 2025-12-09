# 🏗️ Архитектура University DataHub v2.0

## 📊 Общая схема

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│                    (React + TypeScript)                      │
└────────────────┬─────────────────────────────────────┬──────┘
                 │                                     │
                 │ REST API                            │
                 │                                     │
┌────────────────▼─────────────────────────────────────▼──────┐
│                      FastAPI Backend                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Routers    │  │   Services   │  │  Dependencies   │   │
│  │              │  │              │  │                 │   │
│  │ • auth       │  │ • AI Service │  │ • JWT Auth      │   │
│  │ • catalog    │  │              │  │ • DB Sessions   │   │
│  │ • favorites  │  │              │  │                 │   │
│  │ • ai         │  │              │  │                 │   │
│  │ • admin      │  │              │  │                 │   │
│  └──────┬───────┘  └──────┬───────┘  └─────────────────┘   │
│         │                 │                                  │
│         │                 │                                  │
└─────────┼─────────────────┼──────────────────────────────────┘
          │                 │
          │                 ├──────────────────┐
          │                 │                  │
┌─────────▼─────────┐  ┌────▼────────┐  ┌─────▼──────────┐
│   PostgreSQL      │  │  ChromaDB   │  │  OpenAI API    │
│                   │  │  (Vectors)  │  │  + Web Search  │
│ • Universities    │  │             │  │                │
│ • Programs        │  │ • Embeddings│  │ • GPT-4        │
│ • Users           │  │ • RAG       │  │ • DuckDuckGo   │
│ • Favorites       │  │ • Search    │  │                │
│ • Grants          │  │             │  │                │
└───────────────────┘  └─────────────┘  └────────────────┘
```

---

## 🎯 Компоненты системы

### 1. Backend (FastAPI)

#### Структура

```
app/
├── core/                    # Ядро приложения
│   ├── config.py           # Конфигурация (env vars)
│   └── security.py         # JWT, password hashing
│
├── db/                     # База данных
│   ├── database.py         # Подключение, сессии
│   └── models.py           # SQLAlchemy модели
│
├── routers/                # API эндпоинты
│   ├── auth.py            # Регистрация, вход
│   ├── catalog.py         # 🆕 Каталог с фильтрами
│   ├── favorites.py       # 🆕 Избранное и сравнение
│   ├── ai.py              # ✨ AI ассистент
│   ├── universities.py    # CRUD университетов
│   └── admin.py           # Админка
│
├── services/               # Бизнес-логика
│   └── ai_service.py      # ✨ AI сервис
│
├── schemas/                # Pydantic схемы
│   ├── user.py
│   └── university.py
│
├── dependencies.py         # Зависимости (auth)
└── main.py                # Точка входа
```

#### Ключевые технологии

- **FastAPI** - Веб-фреймворк
- **SQLAlchemy 2.0** - ORM (async)
- **asyncpg** - PostgreSQL драйвер
- **Alembic** - Миграции
- **JWT** - Авторизация
- **Pydantic** - Валидация

---

### 2. AI Модуль

#### Архитектура AI

```
┌─────────────────────────────────────────────┐
│            AIService (Singleton)            │
├─────────────────────────────────────────────┤
│                                             │
│  Components:                                │
│  ┌─────────────┐  ┌──────────────┐         │
│  │  OpenAI     │  │  ChromaDB    │         │
│  │  Client     │  │  Collection  │         │
│  └──────┬──────┘  └──────┬───────┘         │
│         │                │                  │
│         │                │                  │
│  Methods:                                   │
│  • sync_database_to_vector_db()            │
│  • chat_rag()          ◄───── RAG          │
│  • get_recommendations() ◄─── Smart Match  │
│  • compare_universities() ◄── AI Analysis  │
│  • _web_search()       ◄───── Fallback     │
│                                             │
└─────────────────────────────────────────────┘
```

#### Процесс RAG (Retrieval-Augmented Generation)

```
Вопрос пользователя
      │
      ▼
Векторизация вопроса (OpenAI Embeddings)
      │
      ▼
Поиск похожих в ChromaDB (Top-5)
      │
      ├─── Найдено в БД? ──► Да ──► Формируем контекст
      │                              │
      └─── Нет ──────────────────────┤
                                     ▼
                           Веб-поиск (DuckDuckGo)
                                     │
                                     ▼
                    Объединяем контекст (БД + Web)
                                     │
                                     ▼
                        Отправляем в GPT-4 + промпт
                                     │
                                     ▼
                            Получаем ответ
                                     │
                                     ▼
                        Возвращаем пользователю
                        + sources + used_web_search
```

#### Умные рекомендации

```
Профиль студента:
- Баллы ЕНТ: 110
- Бюджет: 1,500,000 ₸
- Интересы: "программирование"
- Город: "Алматы"
      │
      ▼
SQL фильтрация (базовая)
      │
      ▼
Топ-15 кандидатов
      │
      ▼
Детальный анализ каждого:
- Количество программ
- Цены
- Гранты
- Трудоустройство
      │
      ▼
AI промпт с профилем
      │
      ▼
GPT-4 анализ + match_score
      │
      ▼
Топ-3 рекомендации
с причинами и pros/cons
```

---

### 3. Каталог

#### Система фильтрации

```
Запрос GET /catalog/universities?city=Алматы&min_rating=4.0
      │
      ▼
Парсинг параметров (Pydantic)
      │
      ▼
Построение SQL запроса (SQLAlchemy)
      │
      ├── Фильтры: city, type, rating, price, etc.
      ├── Подзапросы: programs, grants
      ├── Сортировка: rating, price, students, name
      └── Пагинация: page, per_page
      │
      ▼
Выполнение запроса (async)
      │
      ▼
Получение данных + агрегаты (min_price, programs_count)
      │
      ▼
Проверка избранного (для текущего юзера)
      │
      ▼
Формирование ответа:
- universities: [...]
- total: N
- page, per_page, total_pages
- filters_applied: {...}
```

#### Оптимизация запросов

- **Индексы** на часто используемых полях (city, rating)
- **Подзапросы** для фильтрации по связанным таблицам
- **Агрегация** на уровне БД (COUNT, MIN, MAX, AVG)
- **Пагинация** для больших результатов

---

### 4. Избранное и сравнение

#### Структура данных

```
User (id: 1)
  │
  ├─── Favorite (created_at: 2024-12-09)
  │     └─── University (id: 1)
  │
  ├─── Favorite (created_at: 2024-12-08)
  │     └─── University (id: 2)
  │
  └─── Favorite (created_at: 2024-12-07)
        └─── University (id: 3)
```

#### Процесс сравнения

```
Запрос: Сравнить [1, 2, 3]
      │
      ▼
Валидация (2-5 университетов)
      │
      ▼
Загрузка данных из БД
      │
      ├─── Основная информация
      ├─── Программы (count, min/max/avg цены)
      ├─── Гранты (count)
      └─── Другие метрики
      │
      ▼
Определение победителей:
- highest_rating
- most_programs
- lowest_price
- most_grants
- best_employment
      │
      ├── Без AI ──► Возврат данных
      │
      └── С AI ──┐
                 ▼
      Формируем промпт для GPT
                 │
                 ▼
      AI анализ сильных/слабых сторон
                 │
                 ▼
      Добавляем ai_analysis к ответу
```

---

## 🔐 Безопасность

### Авторизация

```
1. Пользователь ──► POST /auth/login
                     username + password
                          │
                          ▼
2. Backend ────────► Проверка в БД
                     bcrypt.verify()
                          │
                          ▼
3. Backend ────────► Генерация JWT
                     payload: {sub: email, exp: ...}
                     secret: SECRET_KEY
                          │
                          ▼
4. Возврат ────────► access_token
                          │
                          ▼
5. Клиент ─────────► Сохранение в localStorage
                          │
                          ▼
6. Запросы ────────► Authorization: Bearer TOKEN
                          │
                          ▼
7. Backend ────────► Валидация JWT
                     jwt.decode()
                          │
                          ▼
8. Извлечение ─────► Current User
                     from DB by email
```

### Ролевая модель

```
┌───────────────────────────────────────┐
│              RoleEnum                 │
├───────────────────────────────────────┤
│                                       │
│  USER                                 │
│  ├── View catalog                     │
│  ├── Add to favorites                 │
│  ├── Compare universities             │
│  ├── Use AI chat                      │
│  └── Get recommendations              │
│                                       │
│  ADMIN (все что USER +)               │
│  ├── Create/Update/Delete unis        │
│  ├── Sync AI database                 │
│  ├── Upload JSON files                │
│  └── Access admin panel               │
│                                       │
└───────────────────────────────────────┘
```

---

## 💾 База данных

### Схема

```
users                          universities
┌─────────────┐              ┌──────────────────┐
│ id (PK)     │              │ id (PK)          │
│ email       │              │ name_ru          │
│ password    │              │ city             │
│ role        │              │ rating           │
└─────┬───────┘              │ type             │
      │                      │ ...              │
      │                      └────┬─────────────┘
      │                           │
      │     favorites             │
      │   ┌────────────┐          │
      └───┤ user_id    ◄──────────┤
          │ uni_id     │          │
          │ created_at │          │
          └────────────┘          │
                                  │
          programs                │
        ┌──────────────┐          │
        │ id (PK)      │          │
        │ uni_id (FK)  ◄──────────┤
        │ name         │          │
        │ degree       │          │
        │ price        │          │
        └──────────────┘          │
                                  │
          grants                  │
        ┌──────────────┐          │
        │ id (PK)      │          │
        │ uni_id (FK)  ◄──────────┤
        │ name         │          │
        │ type         │          │
        └──────────────┘          │
                                  │
          dormitories             │
        ┌──────────────┐          │
        │ id (PK)      │          │
        │ uni_id (FK)  ◄──────────┘
        │ name         │
        │ capacity     │
        └──────────────┘
```

---

## 🚀 Производительность

### Оптимизации

1. **Индексы БД**
   ```sql
   CREATE INDEX idx_uni_city ON universities(city);
   CREATE INDEX idx_uni_rating ON universities(rating);
   CREATE INDEX idx_prog_price ON programs(price);
   ```

2. **Async операции**
   - Все запросы к БД асинхронные
   - Параллельная обработка при возможности

3. **Батчинг эмбеддингов**
   - OpenAI API: 100 текстов за раз
   - Экономия времени и запросов

4. **Пагинация**
   - Ограничение результатов
   - Снижение нагрузки на БД

5. **Кеширование** (опционально)
   - Redis для AI рекомендаций
   - TTL: 1 час

---

## 📈 Масштабирование

### Горизонтальное

```
        Load Balancer
             │
      ┌──────┼──────┐
      │      │      │
   Backend Backend Backend
      │      │      │
      └──────┼──────┘
             │
        PostgreSQL
      (Master-Replica)
```

### Вертикальное

- Увеличение CPU/RAM
- Больше workers для uvicorn
- Оптимизация БД (vacuum, reindex)

---

## 🔄 CI/CD (Будущее)

```
Git Push
   │
   ▼
GitHub Actions
   │
   ├─► Lint (ruff)
   ├─► Tests (pytest)
   └─► Build Docker
         │
         ▼
   Docker Registry
         │
         ▼
   Deploy to Server
         │
         ▼
   Health Check
```

---

## 📊 Мониторинг

### Метрики

- Время ответа API
- Использование памяти
- CPU нагрузка
- Количество запросов
- Ошибки (4xx, 5xx)
- AI токены (OpenAI usage)

### Инструменты

- Docker stats
- PostgreSQL logs
- FastAPI middleware (timing)
- Sentry (опционально)

---

**Версия:** 2.0.0  
**Дата:** Декабрь 2024  
**Статус:** Production Ready