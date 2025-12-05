from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    # База данных (локально)
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    DB_HOST: str | None = None
    DB_PORT: str | None = None
    DB_NAME: str | None = None

    # Безопасность
    SECRET_KEY: str = "dev_secret_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # URL базы (для продакшена)
    DATABASE_URL: str | None = None

    OPENAI_API_KEY: str | None = None  
    OPENAI_MODEL: str = "gpt-4o"       

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode='after')
    def assemble_db_connection(self):
        # Railway предоставляет DATABASE_URL
        if self.DATABASE_URL:
            # Конвертируем postgres:// в postgresql+asyncpg://
            if self.DATABASE_URL.startswith("postgres://"):
                self.DATABASE_URL = self.DATABASE_URL.replace(
                    "postgres://", "postgresql+asyncpg://", 1
                )
            elif self.DATABASE_URL.startswith("postgresql://"):
                self.DATABASE_URL = self.DATABASE_URL.replace(
                    "postgresql://", "postgresql+asyncpg://", 1
                )
            
            print(f"✅ Используется DATABASE_URL из окружения")
            return self

        # Локальная разработка
        if self.DB_USER and self.DB_HOST and self.DB_NAME:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@"
                f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
            print(f"✅ Собран DATABASE_URL из компонентов")
        else:
            self.DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/dbname"
            print("⚠️ WARNING: Database config not found. Using dummy URL.")

        return self


settings = Settings()