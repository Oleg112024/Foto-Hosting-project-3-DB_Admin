# -*- coding: utf-8 -*-
"""
Модуль для работы с базой данных PostgreSQL.

Этот модуль содержит все функции для взаимодействия с базой данных:
- Подключение и управление соединениями
- Создание и управление таблицами
- CRUD операции для изображений и пользователей
- Аутентификация и авторизация
- Управление сроками хранения файлов

Автор: Image Hosting Project
Версия: 2.0 (PostgreSQL)
"""

# ============================================================================
# ИМПОРТЫ И ЗАВИСИМОСТИ
# ============================================================================

import psycopg2                    # Драйвер PostgreSQL для Python
from psycopg2 import OperationalError  # Исключения операций БД
import hashlib                     # Хеширование паролей (SHA-256)
from datetime import datetime, timedelta  # Работа с датой и временем
import os                          # Переменные окружения

# ============================================================================
# КОНФИГУРАЦИЯ ПОДКЛЮЧЕНИЯ К POSTGRESQL
# ============================================================================

# Параметры подключения к базе данных из переменных окружения
# Значения по умолчанию используются для разработки
DB_NAME = os.getenv("DB_NAME", "image_hosting_db")     # Имя базы данных
DB_USER = os.getenv("DB_USER", "postgres")             # Пользователь БД
DB_PASSWORD = os.getenv("DB_PASSWORD", "")             # Пароль БД
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")            # Хост БД (localhost)
DB_PORT = int(os.getenv("DB_PORT", "5432"))            # Порт БД (стандартный PostgreSQL)

# ============================================================================
# ФУНКЦИИ ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ
# ============================================================================

def connect_db():
    """
    Установка соединения с базой данных PostgreSQL.
    
    Функция создает подключение к PostgreSQL с использованием параметров
    из переменных окружения. Включает обработку различных типов ошибок:
    - Ошибки кодировки (UnicodeDecodeError)
    - Операционные ошибки PostgreSQL (OperationalError)
    - Прочие непредвиденные ошибки
    
    Returns:
        psycopg2.connection: Объект соединения с БД или None при ошибке
        
    Note:
        Использует UTF-8 кодировку для корректной работы с русским текстом
    """
    try:
        # Устанавливаем соединение с PostgreSQL
        # Параметры берутся из переменных окружения или значений по умолчанию
        conn = psycopg2.connect(
            dbname=DB_NAME,           # Имя базы данных
            user=DB_USER,             # Имя пользователя
            password=DB_PASSWORD,     # Пароль пользователя
            host=DB_HOST,             # Хост сервера БД
            port=DB_PORT,             # Порт сервера БД
            client_encoding='utf8'    # Кодировка клиента (UTF-8)
        )
        return conn
        
    except UnicodeDecodeError as e:
        # Обработка ошибок кодировки при подключении
        # Часто возникает при проблемах с локализацией Windows
        try:
            error_bytes = e.args[1]
            decoded_msg = error_bytes.decode('windows-1251', errors='ignore')
            print(f'Database connection encoding error: {decoded_msg}')
        except:
            print(f'Database connection encoding error: {e}')
        return None
        
    except OperationalError as e:
        # Ошибки подключения к PostgreSQL
        # Например: неверные учетные данные, недоступный сервер
        print(f'Database connection error: {e}')
        return None
        
    except Exception as e:
        # Обработка всех остальных непредвиденных ошибок
        print(f'Unexpected database connection error: {e}')
        return None


def close_db(conn):
    """
    Закрытие соединения с базой данных.
    
    Безопасно закрывает соединение с PostgreSQL, проверяя его существование.
    
    Args:
        conn (psycopg2.connection): Объект соединения с БД
        
    Note:
        Функция безопасна - не вызывает ошибок при передаче None
    """
    if conn:
        conn.close()


# ============================================================================
# ФУНКЦИИ СОЗДАНИЯ ТАБЛИЦ
# ============================================================================

def create_table_images():
    """
    Создание таблицы изображений в базе данных.
    
    Создает таблицу 'images' для хранения метаданных загруженных изображений.
    Таблица содержит информацию о файлах, их владельцах и сроках хранения.
    
    Структура таблицы:
        - id: Уникальный идентификатор (автоинкремент)
        - filename: Имя файла на сервере (уникальное)
        - original_name: Оригинальное имя файла пользователя
        - size: Размер файла в байтах
        - upload_time: Время загрузки (автоматически)
        - file_type: Тип/расширение файла
        - user_email: Email владельца (внешний ключ)
        - expiration_date: Дата истечения срока хранения
    
    Returns:
        bool: True при успешном создании, False при ошибке
        
    Note:
        Использует CASCADE для автоматического удаления изображений
        при удалении пользователя
    """
    conn = connect_db()
    if not conn:
        print("Не удалось подключиться к базе данных для создания таблицы")
        return False
    
    cur = conn.cursor()

    # SQL запрос для создания таблицы изображений
    sql = """
        CREATE TABLE IF NOT EXISTS images (
        id SERIAL PRIMARY KEY,                    -- Уникальный ID (автоинкремент)
        filename TEXT NOT NULL,                   -- Имя файла на сервере
        original_name TEXT NOT NULL,              -- Оригинальное имя файла
        size INTEGER NOT NULL,                    -- Размер файла в байтах
        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Время загрузки
        file_type TEXT NOT NULL,                  -- Тип файла (расширение)
        user_email TEXT,                          -- Email владельца
        expiration_date TIMESTAMP,                -- Дата истечения срока
        FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE CASCADE
    );"""
    # Выполняем SQL запрос для создания таблицы
    cur.execute(sql)
    conn.commit()  # Подтверждаем изменения в БД

    # Закрываем курсор и соединение
    cur.close()
    close_db(conn)
    return True


def create_table_users():
    """
    Создание таблицы пользователей в базе данных.
    
    Создает таблицу 'users' для хранения учетных записей пользователей.
    Таблица содержит данные для аутентификации и авторизации.
    
    Структура таблицы:
        - email: Email пользователя (первичный ключ)
        - password_hash: Хеш пароля (SHA-256)
        - registration_date: Дата регистрации (автоматически)
    
    Returns:
        bool: True при успешном создании, False при ошибке
        
    Note:
        Пароли хранятся в виде хеша для безопасности.
        Email используется как уникальный идентификатор пользователя.
    """
    conn = connect_db()
    if not conn:
        print("Не удалось подключиться к базе данных для создания таблицы пользователей")
        return False
    
    cur = conn.cursor()

    # SQL запрос для создания таблицы пользователей
    sql = """
        CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,                   -- Email (уникальный идентификатор)
        password_hash TEXT NOT NULL,              -- Хеш пароля (SHA-256)
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- Дата регистрации
    );"""
    
    # Выполняем SQL запрос для создания таблицы
    cur.execute(sql)
    conn.commit()  # Подтверждаем изменения в БД

    # Закрываем курсор и соединение
    cur.close()
    close_db(conn)
    return True


# ============================================================================
# ФУНКЦИИ РАБОТЫ С ИЗОБРАЖЕНИЯМИ
# ============================================================================

def save_image(filename, original_name, size, upload_time, file_type, user_email=None, storage_days=30):
    """
    Сохранение метаданных изображения в базу данных.
    
    Добавляет запись о загруженном изображении в таблицу 'images'.
    Автоматически вычисляет дату истечения срока хранения.
    
    Args:
        filename (str): Имя файла на сервере (уникальное)
        original_name (str): Оригинальное имя файла пользователя
        size (int): Размер файла в байтах
        upload_time (datetime): Время загрузки файла
        file_type (str): Тип/расширение файла
        user_email (str, optional): Email владельца файла
        storage_days (int): Количество дней хранения (по умолчанию 30)
    
    Returns:
        bool: True при успешном сохранении, False при ошибке
        
    Note:
        Для авторизованных пользователей устанавливается срок хранения.
        Анонимные загрузки (user_email=None) хранятся без ограничений.
    """
    conn = connect_db()
    if not conn:
        return False
    
    cur = conn.cursor()

    # Вычисляем дату истечения срока хранения
    # Только для авторизованных пользователей
    expiration_date = None
    if user_email:
        expiration_date = datetime.now() + timedelta(days=storage_days)

    # SQL запрос для вставки метаданных изображения
    sql = """
        INSERT INTO images (filename, original_name, size, upload_time, file_type, user_email, expiration_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    
    # Выполняем запрос с параметрами (защита от SQL-инъекций)
    cur.execute(sql, (filename, original_name, size, upload_time, file_type, user_email, expiration_date))
    conn.commit()  # Подтверждаем изменения в БД

    # Закрываем курсор и соединение
    cur.close()
    close_db(conn)
    return True


def get_images_list(page=1, per_page=10, sort_by='upload_time'):
    """
    Возвращает paginated список изображений с учётом сортировки
    Args:
        page (int): Номер текущей страницы (начиная с 1)
        per_page (int): Количество элементов на странице
        sort_by (str): Поле для сортировки (по умолчанию: upload_time)
    Returns:
        list: Список кортежей с данными изображений
    """
    conn = connect_db()
    if not conn:
        return []
    
    cur = conn.cursor()
    
    # Валидация параметров сортировки
    allowed_columns = ['id', 'filename', 'size', 'upload_time']
    sort_by = sort_by if sort_by in allowed_columns else 'upload_time'
    
    # Расчёт смещения для SQL запроса
    offset = (page - 1) * per_page
    query = f"SELECT * FROM images ORDER BY {sort_by} DESC LIMIT {per_page} OFFSET {offset}"
    cur.execute(query)
    result = cur.fetchall()
    
    cur.close()
    close_db(conn)
    return result


def get_total_images():
    """
    Возвращает общее количество изображений в базе данных
    Returns:
        int: Количество изображений
    """
    conn = connect_db()
    if not conn:
        return 0
    
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM images")
    result = cur.fetchone()[0]
    
    cur.close()
    close_db(conn)
    return result


def get_image_by_id(image_id):
    """
    Получает информацию об изображении по его ID
    Args:
        image_id (int): ID изображения
    Returns:
        tuple: Кортеж с данными изображения или None, если изображение не найдено
    """
    conn = connect_db()
    if not conn:
        return None
    
    cur = conn.cursor()
    cur.execute("SELECT * FROM images WHERE id = %s", (image_id,))
    result = cur.fetchone()
    
    cur.close()
    close_db(conn)
    return result


def delete_image(image_id):
    """
    Удаляет изображение из базы данных по его ID
    Args:
        image_id (int): ID изображения
    Returns:
        bool: True, если удаление прошло успешно, иначе False
    """
    conn = connect_db()
    if not conn:
        return False
    
    cur = conn.cursor()
    cur.execute("DELETE FROM images WHERE id = %s", (image_id,))
    conn.commit()
    
    cur.close()
    close_db(conn)
    return True
    










def register_user(email, password):
    """
    Регистрирует нового пользователя с проверкой безопасности.
    
    Выполняет дополнительные проверки безопасности:
    - Предотвращает регистрацию с email администратора
    - Проверяет уникальность email адреса
    - Безопасно хеширует пароль
    
    Args:
        email (str): Email пользователя
        password (str): Пароль пользователя
        
    Returns:
        tuple: (bool, str) - статус регистрации и сообщение
        
    Security Notes:
        - Блокирует регистрацию с email главного администратора
        - Блокирует регистрацию с email из списка администраторов
        - Использует безопасное хеширование SHA-256
    """
    # Получаем список администраторов из переменных окружения
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
    admin_emails_str = os.getenv('ADMIN_EMAILS', 'admin@example.com')
    admin_emails = [e.strip() for e in admin_emails_str.split(',') if e.strip()]
    
    # Добавляем главный email администратора в список, если его там нет
    if admin_email not in admin_emails:
        admin_emails.append(admin_email)
    
    # Проверяем, пытается ли пользователь зарегистрироваться с email администратора
    if email in admin_emails:
        # Для администратора проверяем соответствие пароля из переменных окружения
        admin_password = os.getenv('ADMIN_PASSWORD')
        if not admin_password:
            return False, "Ошибка конфигурации: пароль администратора не установлен."
        
        if password != admin_password:
            # Логируем попытку некорректной регистрации с админ логином
            # Логирование будет выполнено в app.py с полными данными IP и User-Agent
            pass
            
            return False, "Неверный логин или пароль для регистрации администратора. Логин или пароль должен быть правильным!!!."
        
        # Если email и пароль администратора совпадают с переменными окружения, разрешаем регистрацию
        # Это позволяет администратору зарегистрироваться с правильными данными
    
    conn = connect_db()
    if not conn:
        return False, "Ошибка подключения к базе данных"
    
    # Проверяем, существует ли пользователь с таким email
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        cur.close()
        close_db(conn)
        return False, "Пользователь с таким email уже существует"
    
    # Хешируем пароль
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Добавляем пользователя в базу данных
    try:
        cur.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)", (email, password_hash))
        conn.commit()
        cur.close()
        close_db(conn)
        return True, "Регистрация прошла успешно"
    except Exception as e:
        conn.rollback()
        cur.close()
        close_db(conn)
        return False, f"Ошибка при регистрации: {str(e)}"


def authenticate_user(email, password):
    """
    Аутентифицирует пользователя
    Args:
        email (str): Email пользователя
        password (str): Пароль пользователя
    Returns:
        tuple: (bool, str) - статус аутентификации и сообщение
    """
    conn = connect_db()
    if not conn:
        return False, "Ошибка подключения к базе данных"
    
    cur = conn.cursor()
    
    # Сначала проверяем, существует ли пользователь
    cur.execute("SELECT email, password_hash FROM users WHERE email = %s", (email,))
    user = cur.fetchone()
    
    if not user:
        cur.close()
        close_db(conn)
        return False, "Пользователь с таким email не зарегистрирован. Пожалуйста, зарегистрируйтесь."
    
    # Если пользователь существует, проверяем пароль
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    stored_password_hash = user[1]
    
    cur.close()
    close_db(conn)
    
    if password_hash == stored_password_hash:
        return True, "Аутентификация прошла успешно"
    else:
        return False, "Неверный пароль. Проверьте правильность ввода."


def get_user_images(email, page=1, per_page=10):
    """
    Возвращает список изображений пользователя
    Args:
        email (str): Email пользователя
        page (int): Номер страницы
        per_page (int): Количество элементов на странице
    Returns:
        list: Список изображений пользователя
    """
    conn = connect_db()
    if not conn:
        return []
    
    cur = conn.cursor()
    offset = (page - 1) * per_page
    cur.execute("SELECT * FROM images WHERE user_email = %s ORDER BY upload_time DESC LIMIT %s OFFSET %s", 
                (email, per_page, offset))
    result = cur.fetchall()
    
    cur.close()
    close_db(conn)
    return result


def get_total_user_images(email):
    """
    Возвращает общее количество изображений пользователя
    Args:
        email (str): Email пользователя
    Returns:
        int: Количество изображений пользователя
    """
    conn = connect_db()
    if not conn:
        return 0
    
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM images WHERE user_email = %s", (email,))
    result = cur.fetchone()[0]
    
    cur.close()
    close_db(conn)
    return result


def get_expired_images():
    """
    Возвращает список изображений с истекшим сроком хранения
    Returns:
        list: Список изображений с истекшим сроком хранения
    """
    conn = connect_db()
    if not conn:
        return []
    
    cur = conn.cursor()
    cur.execute("SELECT * FROM images WHERE expiration_date IS NOT NULL AND expiration_date < %s", (datetime.now(),))
    result = cur.fetchall()
    
    cur.close()
    close_db(conn)
    return result


def ensure_schema():
    """
    Проверяет и создает необходимые таблицы и колонки в базе данных PostgreSQL.
    Эта функция обеспечивает совместимость схемы БД с текущей версией приложения.
    """
    conn = connect_db()
    if not conn:
        print("Не удалось подключиться к базе данных для проверки схемы")
        return False
    
    # Устанавливаем кодировку для соединения
    conn.set_client_encoding('UTF8')
    cur = conn.cursor()
    
    try:
        # Проверяем существование таблицы users
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            );
        """)
        if not cur.fetchone()[0]:
            create_table_users()
            print("Создана таблица users")
        
        # Проверяем существование таблицы images
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'images'
            );
        """)
        if not cur.fetchone()[0]:
            create_table_images()
            print("Создана таблица images")
        else:
            # Проверяем наличие колонки user_email в таблице images
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'images' 
                    AND column_name = 'user_email'
                );
            """)
            if not cur.fetchone()[0]:
                cur.execute("ALTER TABLE images ADD COLUMN user_email TEXT")
                cur.execute("""
                    ALTER TABLE images 
                    ADD CONSTRAINT fk_images_user_email 
                    FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE SET NULL
                """)
                conn.commit()
                print("Добавлена колонка user_email в таблицу images")
            
            # Проверяем наличие колонки expiration_date в таблице images
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'images' 
                    AND column_name = 'expiration_date'
                );
            """)
            if not cur.fetchone()[0]:
                cur.execute("ALTER TABLE images ADD COLUMN expiration_date TIMESTAMP")
                conn.commit()
                print("Добавлена колонка expiration_date в таблицу images")
        
        # Проверяем существование таблицы statistics
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'statistics'
            );
        """)
        if not cur.fetchone()[0]:
            create_table_statistics()
            print("Создана таблица statistics")
        
        # Создаем администратора если его нет
        ensure_admin_user()
        
        cur.close()
        close_db(conn)
        return True
        
    except Exception as e:
        print(f"Ошибка при проверке схемы базы данных: {e}")
        conn.rollback()
        cur.close()
        close_db(conn)
        return False


def create_table_statistics():
    """
    Создает таблицу statistics для хранения статистики действий пользователей.
    
    Returns:
        bool: True если таблица создана успешно, False в противном случае
    """
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS statistics (
            id SERIAL PRIMARY KEY,
            action_type VARCHAR(50) NOT NULL,
            user_email VARCHAR(255),
            file_id INTEGER,
            ip_address INET,
            user_agent TEXT,
            additional_info TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        cur.close()
        close_db(conn)
        
        return True
    except Exception as e:
        print(f'Error creating statistics table: {str(e)}')
        return False


def ensure_admin_user():
    """
    Создает администратора из переменных окружения только при первом запуске.
    
    Использует ADMIN_EMAIL и ADMIN_PASSWORD из переменных окружения
    для создания учетной записи администратора только если:
    1. Установлена переменная CREATE_ADMIN_USER=true
    2. Администратор не существует в базе данных
    
    Это предотвращает автоматическое создание администратора после
    пересоздания контейнеров, что улучшает безопасность системы.
    
    Returns:
        bool: True если администратор создан или уже существует, False при ошибке
    """
    import hashlib
    
    # Проверяем, нужно ли создавать администратора
    create_admin = os.getenv('CREATE_ADMIN_USER', 'false').lower() == 'true'
    if not create_admin:
        print("Автоматическое создание администратора отключено (CREATE_ADMIN_USER != true)")
        return True
    
    admin_email = os.getenv('ADMIN_EMAIL')
    admin_password = os.getenv('ADMIN_PASSWORD')
    
    if not admin_email or not admin_password:
        print("Предупреждение: ADMIN_EMAIL или ADMIN_PASSWORD не установлены в переменных окружения")
        return False
    
    try:
        conn = connect_db()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        # Проверяем, существует ли администратор
        cur.execute("SELECT email FROM users WHERE email = %s", (admin_email,))
        existing_admin = cur.fetchone()
        
        if not existing_admin:
            # Создаем администратора только если его нет
            password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
            cur.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (%s, %s, NOW())",
                (admin_email, password_hash)
            )
            conn.commit()
            print(f"Создан администратор: {admin_email}")
        else:
            print(f"Администратор уже существует: {admin_email}")
        
        cur.close()
        close_db(conn)
        return True
        
    except Exception as e:
        print(f"Ошибка при создании администратора: {e}")
        return False
