# -*- coding: utf-8 -*-
"""
Celery конфигурация для асинхронной обработки задач.

Обеспечивает:
- Асинхронную обработку изображений
- Фоновую запись статистики
- Периодические задачи очистки
- Масштабируемую архитектуру

Автор: Image Hosting Project
Версия: 2.0 (Async)
"""

import os
import logging
from celery import Celery
from celery.schedules import crontab

# ============================================================================
# КОНФИГУРАЦИЯ CELERY
# ============================================================================

# Создание экземпляра Celery
celery_app = Celery('image_hosting')

# Конфигурация брокера и результатов
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

celery_app.conf.update(
    # Брокер сообщений
    broker_url=f'{REDIS_URL}/0',
    result_backend=f'{REDIS_URL}/0',
    
    # Сериализация
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Настройки производительности
    worker_prefetch_multiplier=4,
    task_acks_late=True,
    worker_disable_rate_limits=True,
    
    # Время жизни результатов
    result_expires=3600,  # 1 час
    
    # Маршрутизация задач
    task_routes={
        'image_hosting.process_image': {'queue': 'image_processing'},
        'image_hosting.log_statistics': {'queue': 'statistics'},
        'image_hosting.cleanup_expired': {'queue': 'maintenance'},
    },
    
    # Периодические задачи
    beat_schedule={
        'cleanup-expired-images': {
            'task': 'image_hosting.cleanup_expired_images',
            'schedule': crontab(hour=2, minute=0),  # Каждый день в 2:00
        },
        'generate-daily-stats': {
            'task': 'image_hosting.generate_daily_statistics',
            'schedule': crontab(hour=1, minute=0),  # Каждый день в 1:00
        },
        'health-check': {
            'task': 'image_hosting.system_health_check',
            'schedule': 300.0,  # Каждые 5 минут
        },
    },
)

# ============================================================================
# АСИНХРОННЫЕ ЗАДАЧИ
# ============================================================================

@celery_app.task(bind=True, max_retries=3)
def process_image_async(self, file_path, user_email, original_name):
    """
    Асинхронная обработка загруженного изображения.
    
    Args:
        file_path (str): Путь к файлу изображения
        user_email (str): Email пользователя
        original_name (str): Оригинальное имя файла
    
    Returns:
        dict: Результат обработки
    """
    try:
        from PIL import Image
        import os
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Открываем и анализируем изображение
        with Image.open(file_path) as img:
            # Получаем информацию об изображении
            width, height = img.size  # Размеры изображения
            format_type = img.format  # Формат изображения (JPEG, PNG и т.д.)
          
                        
            # Создаем миниатюру (если нужно)
            if width > 1920 or height > 1920:
                # Создаем уменьшенную версию для быстрого просмотра
                thumbnail_path = file_path.replace('.', '_thumb.')
                img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                img.save(thumbnail_path, optimize=True, quality=85)
                
                logging.info(f"Thumbnail created: {thumbnail_path}")
        
        # Получаем размер файла
        file_size = os.path.getsize(file_path)
        
        # Логируем успешную обработку
        log_statistics_async.delay(
            action_type='image_processed',
            user_email=user_email,
            additional_info=f'File: {original_name}, Size: {file_size}, Dimensions: {width}x{height}'
        )
        
        return {
            'status': 'success',
            'file_path': file_path,
            'width': width,
            'height': height,
            'format': format_type,
            'size': file_size
        }
        
    except Exception as exc:
        logging.error(f"Image processing failed: {exc}")
        
        # Повторяем задачу при ошибке
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        return {
            'status': 'error',
            'error': str(exc)
        }

@celery_app.task(bind=True, max_retries=3)
def log_statistics_async(self, action_type, user_email=None, **kwargs):
    """
    Асинхронная запись статистики.
    
    Args:
        action_type (str): Тип действия
        user_email (str): Email пользователя
        **kwargs: Дополнительные параметры
    
    Returns:
        dict: Результат записи
    """
    try:
        from admin_db import log_statistics
        
        # Записываем статистику
        success = log_statistics(
            action_type=action_type,
            user_email=user_email,
            ip_address=kwargs.get('ip_address'),
            user_agent=kwargs.get('user_agent'),
            additional_info=kwargs.get('additional_info')
        )
        
        if success:
            return {'status': 'success', 'action_type': action_type}
        else:
            raise Exception("Failed to log statistics")
            
    except Exception as exc:
        logging.error(f"Statistics logging failed: {exc}")
        
        # Повторяем при ошибке
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30 * (self.request.retries + 1))
        
        return {'status': 'error', 'error': str(exc)}

@celery_app.task
def cleanup_expired_images():
    """
    Периодическая очистка просроченных изображений.
    
    Returns:
        dict: Результат очистки
    """
    try:
        from db import get_expired_images, delete_image
        import os
        
        expired_images = get_expired_images()
        deleted_count = 0
        errors = []
        
        for image in expired_images:
            try:
                image_id = image[0]
                filename = image[1]
                user_email = image[6]
                
                # Удаляем файл
                if user_email and filename:
                    file_path = os.path.join('images', user_email, filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                
                # Удаляем запись из БД
                delete_image(image_id)
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"Error deleting image {image_id}: {str(e)}")
        
        # Логируем результат
        log_statistics_async.delay(
            action_type='cleanup_completed',
            additional_info=f'Deleted: {deleted_count}, Errors: {len(errors)}'
        )
        
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'errors': errors
        }
        
    except Exception as e:
        logging.error(f"Cleanup task failed: {e}")
        return {'status': 'error', 'error': str(e)}

@celery_app.task
def generate_daily_statistics():
    """
    Генерация ежедневной статистики.
    
    Returns:
        dict: Результат генерации статистики
    """
    try:
        from admin_db import get_statistics_summary
        from datetime import datetime, timedelta
        
        # Получаем статистику за вчера
        yesterday = datetime.now() - timedelta(days=1)
        stats = get_statistics_summary()
        
        # Здесь можно добавить отправку отчетов администраторам
        # или сохранение агрегированной статистики
        
        logging.info(f"Daily statistics generated for {yesterday.date()}")
        
        return {
            'status': 'success',
            'date': yesterday.isoformat(),
            'stats': stats
        }
        
    except Exception as e:
        logging.error(f"Daily statistics generation failed: {e}")
        return {'status': 'error', 'error': str(e)}

@celery_app.task
def system_health_check():
    """
    Периодическая проверка здоровья системы.
    
    Returns:
        dict: Результат проверки
    """
    try:
        from db_pool import db_pool
        import psutil
        from datetime import datetime
        
        # Проверка базы данных
        db_health = db_pool.health_check()
        
        # Проверка системных ресурсов
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        health_data = {
            'database': db_health,
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'disk_percent': disk.percent,
            'timestamp': datetime.now().isoformat()
        }
        
        # Логируем критические состояния
        if cpu_percent > 90:
            logging.warning(f"High CPU usage: {cpu_percent}%")
        
        if memory.percent > 90:
            logging.warning(f"High memory usage: {memory.percent}%")
        
        if disk.percent > 90:
            logging.warning(f"High disk usage: {disk.percent}%")
        
        return {
            'status': 'success',
            'health_data': health_data
        }
        
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        return {'status': 'error', 'error': str(e)}