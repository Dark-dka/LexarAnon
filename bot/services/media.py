"""
Media handling service: downloads files from Telegram and saves them locally.
"""
import os
import uuid
import logging
from pathlib import Path

from aiogram import Bot
from django.conf import settings

logger = logging.getLogger(__name__)

# Extension map by content type
EXTENSION_MAP = {
    'photo': '.jpg',
    'video': '.mp4',
    'voice': '.ogg',
    'video_note': '.mp4',
    'document': '',  # use original extension
    'sticker': '.webp',
}


async def download_and_save(bot: Bot, file_id: str, media_type: str, original_filename: str = None) -> str:
    """
    Download a file from Telegram and save it to MEDIA_ROOT.
    
    Args:
        bot: The aiogram Bot instance
        file_id: Telegram file_id
        media_type: Type of media (photo, video, voice, etc.)
        original_filename: Original filename for documents
    
    Returns:
        Relative path to the saved file (relative to MEDIA_ROOT)
    """
    try:
        file = await bot.get_file(file_id)
    except Exception as e:
        logger.error(f'Failed to get file info for {file_id}: {e}')
        raise

    # Determine extension
    if media_type == 'document' and original_filename:
        ext = Path(original_filename).suffix or '.bin'
    else:
        ext = EXTENSION_MAP.get(media_type, '.bin')

    # Create directory structure
    from datetime import date
    today = date.today()
    relative_dir = f'chat_media/{today.year}/{today.month:02d}/{today.day:02d}'
    full_dir = Path(settings.MEDIA_ROOT) / relative_dir
    full_dir.mkdir(parents=True, exist_ok=True)

    # Unique filename
    unique_name = f'{uuid.uuid4().hex}{ext}'
    relative_path = f'{relative_dir}/{unique_name}'
    full_path = Path(settings.MEDIA_ROOT) / relative_path

    # Download
    try:
        await bot.download_file(file.file_path, destination=str(full_path))
        logger.info(f'Saved media: {relative_path} (type={media_type})')
        return relative_path
    except Exception as e:
        logger.error(f'Failed to download file {file_id}: {e}')
        raise


async def download_profile_photo(bot: Bot, user_id: int) -> str | None:
    """
    Download user's profile photo.
    Returns relative path or None if no photo.
    """
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if not photos.photos:
            return None

        # Get the largest version of the first photo
        photo = photos.photos[0][-1]
        
        # Create directory
        profile_dir = Path(settings.MEDIA_ROOT) / 'profile_photos'
        profile_dir.mkdir(parents=True, exist_ok=True)

        relative_path = f'profile_photos/{user_id}.jpg'
        full_path = Path(settings.MEDIA_ROOT) / relative_path

        file = await bot.get_file(photo.file_id)
        await bot.download_file(file.file_path, destination=str(full_path))
        
        logger.info(f'Saved profile photo for user {user_id}')
        return relative_path
    except Exception as e:
        logger.error(f'Failed to download profile photo for {user_id}: {e}')
        return None
