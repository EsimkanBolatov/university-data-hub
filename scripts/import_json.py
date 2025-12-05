"""
ETL скрипт для загрузки университетов из JSON с валидацией через Pydantic.
Исправлена проблема дублирования данных при повторной загрузке.
"""
import json
import re
import asyncio
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.database import AsyncSessionLocal
from app.db.models import University, Profession
from app.schemas.json_import import UniversityImportSchema

# ============ УТИЛИТЫ ============

CODE_PATTERN = re.compile(r'([0-9]+[A-Z]+[0-9]+)')

def normalize_keys(obj):
    """
    Рекурсивно очищает ключи словаря от префиксов вида '1_', '12_'.
    """
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            clean_key = re.sub(r'^\d+_', '', k)
            new_obj[clean_key] = normalize_keys(v)
        return new_obj
    elif isinstance(obj, list):
        return [normalize_keys(i) for i in obj]
    else:
        return obj

def extract_profession_code(text: str):
    if not isinstance(text, str): return None, ""
    match = CODE_PATTERN.search(text)
    if match:
        code = match.group(1)
        name = text.replace(code, '').strip(' .-,')
        return code, name
    return None, text

# ============ ЛОГИКА ИМПОРТА ============

async def import_university_from_json(filepath: Path, db: AsyncSession):
    filename = filepath.name
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ {filename}: Ошибка чтения JSON (битый файл). Строка {e.lineno}, ошибка: {e.msg}")
        return

    # 1. Нормализация и валидация
    clean_data = normalize_keys(raw_data)
    try:
        uni_data = UniversityImportSchema(**clean_data)
    except Exception as e:
        print(f"❌ {filename}: Ошибка валидации структуры: {e}")
        return

    if not uni_data.info or not uni_data.info.name:
        print(f"⚠️ {filename}: Не найдено название университета. Пропуск.")
        return

    # 2. Поиск существующего вуза с подгрузкой профессий
    uni_name = uni_data.info.name
    
    # ВАЖНО: options(selectinload(...)) нужен, чтобы мы могли очистить список профессий
    result = await db.execute(
        select(University)
        .where(University.name_ru == uni_name)
        .options(selectinload(University.professions))
    )
    university = result.scalar_one_or_none()

    if not university:
        university = University()
        print(f"✅ {filename}: Создаем вуз '{uni_name}'")
    else:
        print(f"🔄 {filename}: Обновляем вуз '{uni_name}' (данные перезаписываются)")

    # 3. Обновление полей (перезапись)
    university.name_ru = uni_data.info.name
    university.full_name = uni_data.info.full_name
    university.type = "private" if "частный" in (uni_data.info.type or "").lower() else "public"
    university.founded_year = uni_data.info.founded_year
    
    university.city = uni_data.info.city_parsed
    university.country = uni_data.info.country_parsed
    university.address = uni_data.info.address
    university.latitude = uni_data.info.coords.lat if uni_data.info.coords else None
    university.longitude = uni_data.info.coords.lon if uni_data.info.coords else None

    university.website = uni_data.info.website
    university.logo_url = uni_data.info.logo
    university.achievements = uni_data.info.status
    
    if uni_data.desc:
        university.description = uni_data.desc.short_text
        university.mission = uni_data.desc.mission
    
    university.history_json = uni_data.history
    
    if uni_data.contacts:
        university.phone = uni_data.contacts.phone
        university.email = uni_data.contacts.email
        university.contacts_json = uni_data.contacts.model_dump()
        
        if uni_data.contacts.socials:
            university.telegram = uni_data.contacts.socials.get("Telegram")
            university.instagram = uni_data.contacts.socials.get("Instagram")
            university.youtube = uni_data.contacts.socials.get("YouTube")

    db.add(university)
    
    # 4. Обработка профессий БЕЗ ДУБЛИРОВАНИЯ
    # Сначала очищаем текущий список, чтобы состояние соответствовало файлу
    if university.professions:
        university.professions.clear()
        
    await db.flush() # Сохраняем основные данные, чтобы у вуза был ID

    if uni_data.professions:
        count = 0
        for prof_text in uni_data.professions:
            code, name = extract_profession_code(prof_text)
            if not code: continue
            
            # Ищем профессию в справочнике
            res = await db.execute(select(Profession).where(Profession.code == code))
            profession = res.scalar_one_or_none()
            
            # Если профессии нет в справочнике — создаем
            if not profession:
                degree = "Бакалавриат"
                if code.startswith("7") or code.startswith("M"): degree = "Магистратура"
                if code.startswith("8") or code.startswith("D"): degree = "PhD"
                
                profession = Profession(code=code, name=name, degree=degree)
                db.add(profession)
                await db.flush()
            
            # Добавляем связь (так как мы сделали clear выше, дублей не будет)
            university.professions.append(profession)
            count += 1
    
    await db.commit()

# ============ ЗАПУСК ============

async def import_all_from_folder(folder_path: str = "data_source"):
    folder = Path(folder_path)
    if not folder.exists():
        print(f"❌ Папка {folder_path} не найдена!")
        return
    
    files = list(folder.glob("*.json"))
    print(f"📂 Найдено файлов: {len(files)}")

    async with AsyncSessionLocal() as db:
        for json_file in files:
            try:
                await import_university_from_json(json_file, db)
            except Exception as e:
                print(f"🔥 Ошибка в {json_file.name}: {e}")
                await db.rollback()

if __name__ == "__main__":
    # Фикс для Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(import_all_from_folder())
    except KeyboardInterrupt:
        print("\n⛔ Импорт прерван")