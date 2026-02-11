# ============================================================================
# УТИЛИТЫ ДЛЯ ГРУППИРОВКИ FLASH-СООБЩЕНИЙ
# ============================================================================
# 
# Этот модуль содержит вспомогательные функции для группировки и оптимизации
# flash-сообщений, чтобы избежать показа множества отдельных уведомлений.
# 
# Основные функции:
# - Группировка похожих сообщений
# - Создание сводных сообщений
# - Форматирование множественных результатов
# 
# ============================================================================

from flask import flash
from typing import List, Dict, Any


def flash_grouped_results(uploaded_files: List[Dict], failed_files: List[Dict], 
                         operation: str = "загрузки") -> None:
    """
    Создает сгруппированные flash-сообщения для результатов операций с файлами.
    
    Вместо множества отдельных сообщений создает одно или два сводных сообщения:
    - Одно для успешных операций (если есть)
    - Одно для неудачных операций (если есть)
    
    Args:
        uploaded_files (List[Dict]): Список успешно обработанных файлов
        failed_files (List[Dict]): Список файлов с ошибками
        operation (str): Тип операции (загрузки, удаления, обработки)
    
    Examples:
        >>> flash_grouped_results([{"original_name": "file1.jpg"}], 
        ...                      [{"filename": "file2.jpg", "error": "Too large"}])
        # Создаст два сообщения:
        # ✅ Успех: Успешно загружено 1 файл
        # ❌ Ошибка: Не удалось загрузить 1 файл: file2.jpg (Too large)
    """
    
    # Сообщение об успешных операциях
    if uploaded_files:
        success_count = len(uploaded_files)
        if success_count == 1:
            file_name = uploaded_files[0].get('original_name', 'файл')
            flash(f'Файл "{file_name}" успешно загружен', 'success')
        else:
            flash(f'Успешно загружено {success_count} файлов', 'success')
    
    # Сгруппированное сообщение об ошибках
    if failed_files:
        error_count = len(failed_files)
        
        if error_count == 1:
            # Одна ошибка - показываем детали
            failed = failed_files[0]
            filename = failed.get('filename', 'файл')
            error = failed.get('error', 'неизвестная ошибка')
            flash(f'Ошибка {operation}: "{filename}" - {error}', 'error')
        elif error_count <= 3:
            # Несколько ошибок - показываем список
            error_details = []
            for failed in failed_files:
                filename = failed.get('filename', 'файл')
                error = failed.get('error', 'неизвестная ошибка')
                error_details.append(f'"{filename}" ({error})')
            
            error_list = ', '.join(error_details)
            flash(f'Ошибки {operation} {error_count} файлов: {error_list}', 'error')
        else:
            # Много ошибок - показываем сводку
            first_errors = failed_files[:2]
            error_details = []
            for failed in first_errors:
                filename = failed.get('filename', 'файл')
                error = failed.get('error', 'неизвестная ошибка')
                error_details.append(f'"{filename}" ({error})')
            
            remaining = error_count - 2
            error_list = ', '.join(error_details)
            flash(f'Ошибки {operation} {error_count} файлов: {error_list} и еще {remaining}', 'error')


def flash_bulk_operation_result(success_count: int, error_count: int, 
                               operation: str, details: List[str] = None) -> None:
    """
    Создает сгруппированное сообщение для массовых операций.
    
    Args:
        success_count (int): Количество успешных операций
        error_count (int): Количество неудачных операций  
        operation (str): Название операции (удаление, обработка, etc.)
        details (List[str], optional): Дополнительные детали для отображения
    
    Examples:
        >>> flash_bulk_operation_result(5, 2, "удаление изображений")
        # Создаст: "Операция завершена: удалено 5, ошибок 2"
    """
    
    if success_count > 0 and error_count > 0:
        # Смешанный результат
        message = f'Операция завершена: {operation} - успешно {success_count}, ошибок {error_count}'
        if details:
            details_list = ', '.join(details[:3])
            message += f'. Детали: {details_list}'
            if len(details) > 3:
                message += f' и еще {len(details) - 3}'
        flash(message, 'warning')
        
    elif success_count > 0:
        # Только успешные операции
        message = f'Успешно выполнено: {operation} - {success_count} элементов'
        flash(message, 'success')
        
    elif error_count > 0:
        # Только ошибки
        message = f'Ошибки при выполнении: {operation} - {error_count} элементов'
        if details:
            details_list = ', '.join(details[:3])
            message += f'. Детали: {details_list}'
            if len(details) > 3:
                message += f' и еще {len(details) - 3}'
        flash(message, 'error')
    else:
        # Ничего не обработано
        flash(f'Нет элементов для операции: {operation}', 'info')


def flash_validation_errors(errors: List[str], context: str = "валидации") -> None:
    """
    Группирует ошибки валидации в одно сообщение.
    
    Args:
        errors (List[str]): Список ошибок валидации
        context (str): Контекст ошибок (валидации, проверки, etc.)
    
    Examples:
        >>> flash_validation_errors(["Поле email обязательно", "Пароль слишком короткий"])
        # Создаст: "Ошибки валидации: Поле email обязательно; Пароль слишком короткий"
    """
    
    if not errors:
        return
        
    if len(errors) == 1:
        flash(f'Ошибка {context}: {errors[0]}', 'error')
    else:
        # Группируем множественные ошибки
        if len(errors) <= 5:
            error_text = '; '.join(errors)
        else:
            error_text = '; '.join(errors[:4]) + f' и еще {len(errors) - 4} ошибок'
        
        flash(f'Ошибки {context} ({len(errors)}): {error_text}', 'error')


def flash_summary_message(category: str, items: List[Any], 
                         item_formatter: callable = str, 
                         max_items: int = 3) -> None:
    """
    Создает сводное сообщение для списка элементов.
    
    Args:
        category (str): Категория сообщения ('success', 'error', 'warning', 'info')
        items (List[Any]): Список элементов для отображения
        item_formatter (callable): Функция для форматирования элементов
        max_items (int): Максимальное количество элементов для детального показа
    
    Examples:
        >>> flash_summary_message('info', ['file1.jpg', 'file2.png'], 
        ...                      lambda x: f'📁 {x}', max_items=2)
        # Создаст: "📁 file1.jpg, 📁 file2.png"
    """
    
    if not items:
        return
        
    if len(items) <= max_items:
        # Показываем все элементы
        formatted_items = [item_formatter(item) for item in items]
        message = ', '.join(formatted_items)
    else:
        # Показываем первые элементы + счетчик остальных
        formatted_items = [item_formatter(item) for item in items[:max_items]]
        remaining = len(items) - max_items
        items_list = ', '.join(formatted_items)
        message = f"{items_list} и еще {remaining}"
    
    flash(message, category)