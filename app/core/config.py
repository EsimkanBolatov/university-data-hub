import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

# 1. Вычисляем путь к корню проекта, чтобы точно найти .env
# Если config.py лежит в /app/core/, то поднимаемся на 2 уровня вверх
current_file_dir = os.path.dirname(os.path.abspath(__file__))
# Поднимаемся из 'core' в 'app', и из 'app' в корень проекта
ROOT_DIR = os.path.dirname(os.path.dirname(current_file_dir))
ENV_PATH = os.path.join(ROOT_DIR, ".env")

print(f"📂 Ищем .env файл по пути: {ENV_PATH}") # Для отладки

class Settings(BaseSettings):
    # Точные названия переменных как в вашем .env файле
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    DB_HOST: str | None = None
    DB_PORT: str | None = None
    DB_NAME: str | None = None

    # Безопасность
    SECRET_KEY: str = "dev_secret_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Если вы используете готовую строку подключения
    DATABASE_URL: str | None = None

    OPENAI_API_KEY: str | None = None  
    OPENAI_MODEL: str = "gpt-4o"       

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,  # Указываем жесткий путь
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode='after')
    def assemble_db_connection(self):
        # 1. Если есть DATABASE_URL (например, Railway/Render)
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgres://"):
                self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
            elif self.DATABASE_URL.startswith("postgresql://") and "asyncpg" not in self.DATABASE_URL:
                self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            print(f"✅ Config: Используется DATABASE_URL из окружения")
            return self

        # 2. Собираем URL из переменных (DB_USER, DB_HOST...)
        if self.DB_USER and self.DB_HOST and self.DB_NAME:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@"
                f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
            print(f"✅ Config: URL базы собран вручную. Хост: {self.DB_HOST}")
            return self

        # 3. Если ничего не сработало
        print("❌ ОШИБКА CONFIG: Переменные окружения не загрузились!")
        print(f"   Проверьте файл: {ENV_PATH}")
        print(f"   Видит ли Python переменные? DB_HOST={self.DB_HOST}, DB_USER={self.DB_USER}")
        
        # Ставим заглушку, чтобы приложение не упало мгновенно, но подключение не пройдет
        self.DATABASE_URL = "postgresql+asyncpg://error:error@localhost/error"
        return self

settings = Settings()