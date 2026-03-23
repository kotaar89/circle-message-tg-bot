import os
import uuid
import asyncio
import logging
from moviepy import VideoFileClip  # 👈 ИСПРАВЛЕНО!


logger = logging.getLogger(__name__)

async def convert_to_circle(input_path: str) -> str:
    """
    Конвертирует обычное видео в формат для кружочка
    Возвращает путь к обработанному файлу
    """
    try:
        # Создаем уникальное имя для выходного файла
        output_filename = f"circle_{uuid.uuid4().hex}.mp4"
        output_path = os.path.join("/tmp", output_filename)
        
        # Загружаем видео (делаем в отдельном потоке, чтобы не блокировать бота)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _process_video, input_path, output_path)
        
        return output_path
    except Exception as e:
        logger.error(f"Ошибка конвертации: {e}")
        raise

def _process_video(input_path: str, output_path: str):
    """
    Синхронная функция обработки видео (выполняется в отдельном потоке)
    """
    # 👇 ИСПОЛЬЗУЕМ VideoFileClip, А НЕ VideoClip!
    clip = VideoFileClip(input_path)  # ✅ Правильно!
    
    try:
        # 1. Обрезаем до 60 секунд (максимум для кружков)
        max_duration = 60
        if clip.duration > max_duration:
            clip = clip.subclip(0, max_duration)
        
        # 2. Обрезаем до квадрата по центру
        size = min(clip.w, clip.h)
        x_center = clip.w / 2
        y_center = clip.h / 2
        clip = clip.cropped(
            x_center=x_center,
            y_center=y_center,
            width=size,
            height=size
        )
        
        # 3. Сохраняем с нужными параметрами
        clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            threads=4,
            bitrate="800k",
            preset="medium",

            logger=None
        )
    finally:
        clip.close()  # Важно закрыть клип для освобождения памяти