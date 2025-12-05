import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from app.core.config import settings

# Удаляем passlib, используем bcrypt напрямую

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль с хешем (Python 3.12 совместимый)"""
    # bcrypt требует байты, поэтому кодируем строки
    # Если хеш из БД пришел как str, кодируем его в bytes
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Хеширует пароль (Python 3.12 совместимый)"""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    # Возвращаем строку (decode), чтобы сохранить в БД как текст
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создаёт JWT токен"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt