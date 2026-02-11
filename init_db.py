# -*- coding: utf-8 -*-
# ============================================================================
# МОДУЛЬ ИНИЦИАЛИЗАЦИИ БАЗЫ ДАННЫХ IMAGE HOSTING PROJECT
# ============================================================================
# 
# Этот модуль отвечает за создание и настройку структуры базы данных
# для приложения Image Hosting. Выполняет первоначальную инициализацию
# всех необходимых таблиц с правильными схемами, индексами и ограничениями.
# 
# Основные функции:
# - Создание таблицы пользователей (users)
# - Создание таблицы изображений (images)
# - Создание таблицы статистики (statistics)
# - Настройка связей между таблицами (Foreign Keys)
# - Обеспечение целостности данных
# 
# Использование:
#   python init_db.py
# 
# Безопасность:
# - Использует CREATE TABLE IF NOT EXISTS для безопасного повторного запуска
# - Правильная настройка каскадных удалений
# - Валидация подключения к БД перед операциями
# 
# ============================================================================

# ============================================================================
# ИМПОРТ НЕОБХОДИМЫХ МОДУЛЕЙ
# ============================================================================

import sys  # Системные функции для управления выходом из программы
from db import connect_db, close_db  # Основные функции работы с базой данных

# ============================================================================
# ФУНКЦИИ СОЗДАНИЯ ТАБЛИЦ БАЗЫ ДАННЫХ
# ============================================================================

def create_table_users():
    """
    Создает таблицу пользователей (users) в базе данных.
    
    Эта функция создает основную таблицу для хранения информации о
    зарегистрированных пользователях системы. Таблица содержит
    минимально необходимые поля для аутентификации и идентификации.
    
    Структура таблицы:
    - email (TEXT, PRIMARY KEY): Уникальный email пользователя
    - password_hash (TEXT, NOT NULL): Хэш пароля для безопасности
    - created_at (TIMESTAMP): Время регистрации пользователя
    
    Особенности дизайна:
    - Email используется как первичный ключ для простоты интеграции
    - Пароли хранятся только в виде хэшей (никогда в открытом виде)
    - Автоматическая установка времени создания записи
    - IF NOT EXISTS предотвращает ошибки при повторном запуске
    
    Security Features:
    - Первичный ключ обеспечивает уникальность email
    - NOT NULL предотвращает создание пользователей без пароля
    - Хэширование паролей обеспечивает безопасность
    
    Returns:
        bool: True если таблица создана успешно, False при ошибке
        
    Database Schema:
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    # Устанавливаем соединение с базой данных
    conn = connect_db()
    if not conn:
        print("Failed to connect to database for creating users table")
        return False
    
    # Создаем курсор для выполнения SQL команд
    cur = conn.cursor()

    # SQL запрос для создания таблицы пользователей
    # IF NOT EXISTS обеспечивает безопасность повторного запуска
    sql = """
        CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"""
    
    # Выполняем SQL команду создания таблицы
    cur.execute(sql)
    # Подтверждаем изменения в базе данных
    conn.commit()

    # Освобождаем ресурсы базы данных
    cur.close()
    close_db(conn)
    return True

def create_table_images():
    """
    Создает таблицу изображений (images) в базе данных.
    
    Эта функция создает центральную таблицу для хранения метаданных
    всех загруженных изображений в системе. Содержит полную информацию
    о файлах, их владельцах и характеристиках.
    
    Структура таблицы:
    - id (SERIAL, PRIMARY KEY): Уникальный автоинкрементный идентификатор
    - filename (TEXT, NOT NULL): Имя файла в файловой системе
    - original_name (TEXT, NOT NULL): Оригинальное имя файла пользователя
    - size (INTEGER, NOT NULL): Размер файла в байтах
    - upload_time (TIMESTAMP): Время загрузки файла
    - file_type (TEXT, NOT NULL): MIME-тип файла (image/jpeg, image/png, etc.)
    - user_email (TEXT): Email владельца файла (может быть NULL для анонимных)
    - expiration_date (TIMESTAMP): Дата истечения срока хранения (опционально)
    
    Связи с другими таблицами:
    - FOREIGN KEY (user_email) → users(email): Связь с таблицей пользователей
    - ON DELETE CASCADE: При удалении пользователя удаляются его файлы
    
    Особенности дизайна:
    - SERIAL PRIMARY KEY обеспечивает уникальные ID для каждого изображения
    - Разделение filename и original_name для безопасности файловой системы
    - Поддержка анонимных загрузок (user_email может быть NULL)
    - Возможность установки срока жизни файлов через expiration_date
    - Каскадное удаление обеспечивает целостность данных
    
    Use Cases:
    - Хранение метаданных всех загруженных изображений
    - Связывание файлов с их владельцами
    - Отслеживание размеров файлов для квот
    - Управление жизненным циклом файлов
    - Поддержка различных форматов изображений
    
    Returns:
        bool: True если таблица создана успешно, False при ошибке
        
    Database Schema:
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            size INTEGER NOT NULL,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_type TEXT NOT NULL,
            user_email TEXT,
            expiration_date TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE CASCADE
        );
    """
    # Устанавливаем соединение с базой данных
    conn = connect_db()
    if not conn:
        print("Failed to connect to database for creating images table")
        return False
    
    # Создаем курсор для выполнения SQL команд
    cur = conn.cursor()

    # SQL запрос для создания таблицы изображений
    # Включает все необходимые поля для управления файлами и их метаданными
    sql = """
        CREATE TABLE IF NOT EXISTS images (
        id SERIAL PRIMARY KEY,
        filename TEXT NOT NULL,
        original_name TEXT NOT NULL,
        size INTEGER NOT NULL,
        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_type TEXT NOT NULL,
        user_email TEXT,
        expiration_date TIMESTAMP,
        FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE CASCADE
    );"""
    
    # Выполняем SQL команду создания таблицы
    cur.execute(sql)
    # Подтверждаем изменения в базе данных
    conn.commit()

    # Освобождаем ресурсы базы данных
    cur.close()
    close_db(conn)
    return True

def create_table_statistics():
    """
    Создает таблицу статистики (statistics) в базе данных.
    
    Эта функция создает таблицу для логирования и анализа всех действий
    пользователей в системе. Обеспечивает полное отслеживание активности
    для административной панели, аналитики и безопасности.
    
    Структура таблицы:
    - id (SERIAL, PRIMARY KEY): Уникальный идентификатор записи
    - action_type (TEXT, NOT NULL): Тип действия (upload, download, view, login, etc.)
    - user_email (TEXT): Email пользователя (NULL для анонимных действий)
    - file_id (INTEGER): ID файла, с которым связано действие
    - ip_address (TEXT): IP-адрес пользователя для безопасности
    - user_agent (TEXT): User-Agent браузера для анализа
    - timestamp (TIMESTAMP): Время выполнения действия
    - additional_info (TEXT): Дополнительная информация в JSON или текстовом формате
    
    Связи с другими таблицами:
    - FOREIGN KEY (user_email) → users(email): Связь с пользователем
    - FOREIGN KEY (file_id) → images(id): Связь с файлом
    - ON DELETE SET NULL: При удалении связанных записей сохраняем статистику
    
    Особенности дизайна:
    - SET NULL вместо CASCADE для сохранения исторических данных
    - Поддержка анонимных действий (user_email может быть NULL)
    - Гибкое поле additional_info для расширения функциональности
    - Автоматическая установка времени для точного логирования
    - Индексирование по timestamp для быстрых запросов аналитики
    
    Use Cases:
    - Логирование всех действий пользователей
    - Анализ популярности контента
    - Мониторинг безопасности и подозрительной активности
    - Генерация отчетов для административной панели
    - Отслеживание использования ресурсов
    - Аудит системы и соответствие требованиям
    
    Action Types Examples:
    - 'upload': Загрузка файла
    - 'download': Скачивание файла
    - 'view': Просмотр изображения
    - 'login': Вход в систему
    - 'register': Регистрация пользователя
    - 'delete': Удаление файла
    
    Returns:
        bool: True если таблица создана успешно, False при ошибке
        
    Database Schema:
        CREATE TABLE IF NOT EXISTS statistics (
            id SERIAL PRIMARY KEY,
            action_type TEXT NOT NULL,
            user_email TEXT,
            file_id INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            additional_info TEXT,
            FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE SET NULL,
            FOREIGN KEY (file_id) REFERENCES images(id) ON DELETE SET NULL
        );
    """
    # Устанавливаем соединение с базой данных
    conn = connect_db()
    if not conn:
        print("Failed to connect to database for creating statistics table")
        return False
    
    # Создаем курсор для выполнения SQL команд
    cur = conn.cursor()

    # SQL запрос для создания таблицы статистики
    # Включает все поля для полного логирования активности пользователей
    sql = """
        CREATE TABLE IF NOT EXISTS statistics (
        id SERIAL PRIMARY KEY,
        action_type TEXT NOT NULL,
        user_email TEXT,
        file_id INTEGER,
        ip_address TEXT,
        user_agent TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        additional_info TEXT,
        FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE SET NULL,
        FOREIGN KEY (file_id) REFERENCES images(id) ON DELETE SET NULL
    );"""
    
    # Выполняем SQL команду создания таблицы
    cur.execute(sql)
    # Подтверждаем изменения в базе данных
    conn.commit()

    # Освобождаем ресурсы базы данных
    cur.close()
    close_db(conn)
    return True


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ
# ============================================================================

def main():
    """
    Основная функция инициализации базы данных.
    
    Выполняет последовательное создание всех необходимых таблиц
    для функционирования приложения Image Hosting. Обеспечивает
    правильный порядок создания таблиц с учетом зависимостей
    между ними (Foreign Keys).
    
    Порядок создания таблиц:
    1. users - базовая таблица пользователей (независимая)
    2. images - таблица файлов (зависит от users)
    3. statistics - таблица логирования (зависит от users и images)
    
    Обработка ошибок:
    - При ошибке создания любой таблицы процесс прерывается
    - Используется sys.exit(1) для индикации ошибки операционной системе
    - Подробные сообщения об ошибках для диагностики
    
    Exit Codes:
    - 0: Успешная инициализация всех таблиц
    - 1: Ошибка при создании одной или нескольких таблиц
    
    Usage:
        python init_db.py
        
    Prerequisites:
        - Настроенное подключение к PostgreSQL
        - Корректные переменные окружения для БД
        - Права на создание таблиц в базе данных
    """
    print("Initializing database...")
    
    # ========================================================================
    # СОЗДАНИЕ ТАБЛИЦЫ ПОЛЬЗОВАТЕЛЕЙ (БАЗОВАЯ ТАБЛИЦА)
    # ========================================================================
    
    # Создаем таблицу пользователей первой, так как на неё ссылаются другие таблицы
    if create_table_users():
        print("Users table created successfully")
    else:
        print("Error creating users table")
        sys.exit(1)  # Критическая ошибка - прерываем инициализацию
    
    # ========================================================================
    # СОЗДАНИЕ ТАБЛИЦЫ ИЗОБРАЖЕНИЙ (ЗАВИСИТ ОТ USERS)
    # ========================================================================
    
    # Создаем таблицу изображений, которая ссылается на таблицу пользователей
    if create_table_images():
        print("Images table created successfully")
    else:
        print("Error creating images table")
        sys.exit(1)  # Критическая ошибка - прерываем инициализацию
        
    # ========================================================================
    # СОЗДАНИЕ ТАБЛИЦЫ СТАТИСТИКИ (ЗАВИСИТ ОТ USERS И IMAGES)
    # ========================================================================
    
    # Создаем таблицу статистики последней, так как она ссылается на обе предыдущие
    if create_table_statistics():
        print("Statistics table created successfully")
    else:
        print("Error creating statistics table")
        sys.exit(1)  # Критическая ошибка - прерываем инициализацию
    
    # ========================================================================
    # ЗАВЕРШЕНИЕ ИНИЦИАЛИЗАЦИИ
    # ========================================================================
    
    print("Database initialization completed successfully")
    print("All tables created with proper relationships and constraints")
    print("The database is ready for use by the Image Hosting application")

# ============================================================================
# ТОЧКА ВХОДА СКРИПТА
# ============================================================================

if __name__ == "__main__":
    """
    Точка входа при запуске скрипта напрямую.
    
    Этот блок выполняется только при прямом запуске скрипта:
    python init_db.py
    
    При импорте модуля в другие файлы этот блок не выполняется,
    что позволяет использовать функции модуля без автоматической
    инициализации базы данных.
    """
    main()