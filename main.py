import os
import asyncio
import logging
import time
from pathlib import Path
from dotenv import load_dotenv 
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
import aiofiles
import shutil

from video_processor import convert_to_circle

# Загружаем переменные из .env
load_dotenv()

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Проверка, что токен загрузился
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Константы
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
TEMP_DIR = Path("./tmp")  # Временная папка
CLEANUP_DELAY = 60  # Секунд до удаления файлов (для асинхронной очистки)

# Создаем временную папку, если её нет
TEMP_DIR.mkdir(exist_ok=True)


async def cleanup_file(file_path, delay=CLEANUP_DELAY):
    """
    Асинхронное удаление файла через задержку
    Чтобы файл точно успел отправиться перед удалением
    """
    await asyncio.sleep(delay)
    try:
        if file_path and file_path.exists():
            file_path.unlink()
            logger.info(f"🗑️ Удален: {file_path}")
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении {file_path}: {e}")

async def cleanup_temp_folder():
    """
    Очистка всей временной папки от старых файлов (при запуске бота)
    """
    try:
        count = 0
        for file_path in TEMP_DIR.glob("*"):
            if file_path.is_file():
                # Удаляем файлы старше 1 часа
                if time.time() - file_path.stat().st_mtime > 3600:
                    file_path.unlink()
                    count += 1
        if count > 0:
            logger.info(f"🧹 Очищено {count} старых файлов из {TEMP_DIR}")
    except Exception as e:
        logger.error(f"❌ Ошибка очистки папки: {e}")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Приветственное сообщение"""
    await message.answer(
        "👋 Привет! Я бот для превращения видео в кружочки!\n\n"
        "Просто отправь мне любое видео (до 60 секунд), и я сделаю из него "
        "видео-сообщение \n\n"
        "📌 Ограничения:\n"
        "• Длительность: до 60 секунд\n"
        "• Размер: до 20 МБ\n"
        "• Формат: MP4, AVI, MOV и другие"
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь"""
    await cmd_start(message)


@dp.message(lambda message: message.video is not None)
async def handle_video(message: Message):
    """Обработчик видеофайлов"""
    
    input_path = None
    output_path = None
    status_msg = None
    
    try:
        # Проверяем размер
        if message.video.file_size > MAX_FILE_SIZE:
            await message.answer("❌ Видео слишком большое! Максимум 20 МБ.")
            return
        
        # Проверяем длительность
        if message.video.duration and message.video.duration > 60:
            await message.answer("⚠️ Видео длиннее 60 секунд! Обрежу до минуты.")
        
        # Отправляем сообщение о начале обработки
        status_msg = await message.answer("⏳ Скачиваю видео...")
        
        # Скачиваем видео
        file = await bot.get_file(message.video.file_id)
        file_path = file.file_path
        
        # Создаем временный файл
        input_filename = f"input_{message.video.file_unique_id}.mp4"
        input_path = TEMP_DIR / input_filename
        
        await status_msg.edit_text("⏳ Скачиваю видео... 📥")
        await bot.download_file(file_path, input_path)
        await status_msg.edit_text("✅ Видео получено! Начинаю обработку... 🎬")
        
        # Конвертируем в кружок
        output_path = await convert_to_circle(str(input_path))
        
        # Проверяем, что выходной файл существует
        if not Path(output_path).exists():
            raise Exception("Выходной файл не создан")
        
        await status_msg.edit_text("🎬 Отправляю результат... 📤")
        
        # Отправляем как видео-сообщение (кружок)
        with open(output_path, 'rb') as video_file:
            await message.answer_video_note(
                video_note=types.BufferedInputFile(
                    video_file.read(),
                    filename="circle.mp4"
                ),
                length=240
            )
        
        # Удаляем статусное сообщение
        await status_msg.delete()
        
        # Отправляем сообщение об успехе
        await message.answer("✅ Готово! Видео превращено в кружок 🎉")
        
    except Exception as e:
        logger.error(f"Ошибка обработки: {e}", exc_info=True)
        error_text = f"❌ Ошибка: {str(e)[:200]}"
        if status_msg:
            await status_msg.edit_text(error_text)
        else:
            await message.answer(error_text)
            
    finally:
        # Асинхронно удаляем временные файлы (через задержку)
        if input_path:
            asyncio.create_task(cleanup_file(Path(input_path)))
        if output_path:
            asyncio.create_task(cleanup_file(Path(output_path)))

@dp.message(lambda message: message.document and message.document.mime_type and 'video' in message.document.mime_type)
async def handle_video_document(message: Message):
    """Обработчик видео, отправленных как документы"""
    # Создаем видимость, что это видео
    message.video = message.document
    await handle_video(message)

@dp.message()
async def handle_other(message: Message):
    """Обработчик всего остального"""
    await message.answer(
        "📹 Пожалуйста, отправь видео, которое хочешь превратить в кружок!\n\n"
        "Поддерживаются форматы: MP4, AVI, MOV, MKV"
    )

async def main():
    """Запуск бота"""
    logger.info("🚀 Бот запущен и готов к работе!")
    logger.info(f"📁 Временная папка: {TEMP_DIR.absolute()}")
    
    # Очищаем старые файлы при запуске
    await cleanup_temp_folder()
    
    # Запускаем периодическую очистку (каждый час)
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(3600)  # Каждый час
            await cleanup_temp_folder()
    
    # Запускаем фоновую задачу очистки
    asyncio.create_task(periodic_cleanup())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())