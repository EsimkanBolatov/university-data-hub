"""
ETL скрипт для загрузки университетов из JSON
Запуск: python -m scripts.import_json
"""
import json
import re
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import University, Profession

# ============ REGEX ДЛЯ ПАРСИНГА КОДОВ ============
CODE_PATTERN = re.compile(r'([0-9]+[A-Z]+[0-9]+)')  # Например: 6B06113


def extract_profession_code(text: str) -> tuple[str, str]:
    """
    Извлекает код и название из строки вида:
    "Программист 6В06113" или "6B06101 Информационные системы"
    """
    match = CODE_PATTERN.search(text)
    if match:
        code = match.group(1)
        # Убираем код из названия
        name = text.replace(code, '').strip()
        return code, name
    return None, text


async def import_university_from_json(filepath: Path, db: AsyncSession):
    """Импортирует один университет из JSON файла"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    basic_info = data.get("1_Основная_информация", {})
    description = data.get("2_Краткое_описание", {})
    history = data.get("3_История", {})
    contacts = data.get("11_Контакты", {})
    
    # ============ СОЗДАЕМ/ОБНОВЛЯЕМ ВУЗ ============
    uni_name = basic_info.get("Название_университета")
    
    # Проверяем существование
    result = await db.execute(select(University).where(University.name_ru == uni_name))
    university = result.scalar_one_or_none()
    
    if not university:
        university = University()
        print(f"✅ Создаем новый: {uni_name}")
    else:
        print(f"🔄 Обновляем существующий: {uni_name}")
    
    # Маппинг полей
    university.name_ru = uni_name
    university.full_name = basic_info.get("Полное_название")
    university.type = basic_info.get("Тип", "public")
    university.founded_year = basic_info.get("Год_основания")
    university.city = basic_info.get("Город_страна", {}).get("город", "Неизвестно")
    university.country = basic_info.get("Город_страна", {}).get("страна", "Казахстан")
    university.address = basic_info.get("Адрес")
    university.website = basic_info.get("Официальный_сайт")
    university.logo_url = basic_info.get("Логотип")
    university.description = description.get("Короткий_текст")
    university.mission = description.get("Миссия")
    university.achievements = basic_info.get("статус")
    university.history_json = history
    university.contacts_json = contacts
    
    # Контакты
    university.phone = contacts.get("Телефон")
    university.email = contacts.get("Email")
    university.telegram = contacts.get("Социальные_сети", {}).get("Telegram")
    university.instagram = contacts.get("Социальные_сети", {}).get("Instagram")
    
    db.add(university)
    await db.flush()  # Получаем ID
    
    # ============ ПРОФЕССИИ ============
    professions_list = data.get("42_Список_всех_профессий_и_специальностей", [])
    
    for prof_text in professions_list:
        code, name = extract_profession_code(prof_text)
        
        if not code:
            print(f"⚠️ Не удалось извлечь код из: {prof_text}")
            continue
        
        # Ищем или создаем профессию
        result = await db.execute(select(Profession).where(Profession.code == code))
        profession = result.scalar_one_or_none()
        
        if not profession:
            profession = Profession(
                code=code,
                name=name,
                degree="Бакалавриат" if code.startswith("6") else "Магистратура" if code.startswith("7") else "PhD"
            )
            db.add(profession)
            await db.flush()
            print(f"  ➕ Добавлена профессия: {code} - {name}")
        
        # Связываем с вузом (если еще не связано)
        if profession not in university.professions:
            university.professions.append(profession)
    
    await db.commit()
    print(f"✅ Импорт завершен: {uni_name} ({len(university.professions)} профессий)\n")


async def import_all_from_folder(folder_path: str = "data_source"):
    """Импортирует все JSON из папки"""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"❌ Папка {folder_path} не найдена!")
        return
    
    async with AsyncSessionLocal() as db:
        for json_file in folder.glob("*.json"):
            try:
                await import_university_from_json(json_file, db)
            except Exception as e:
                print(f"❌ Ошибка при обработке {json_file.name}: {e}")
                await db.rollback()


if __name__ == "__main__":
    asyncio.run(import_all_from_folder())