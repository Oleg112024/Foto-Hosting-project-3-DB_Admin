#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image Hosting Web Application

Веб-приложение для хостинга изображений с поддержкой:
- Регистрации и аутентификации пользователей
- Загрузки и управления изображениями
- Административной панели и статистики
- Высокой производительности и масштабируемости
- Мониторинга и метрик

Автор: Image Hosting Project Team
Версия: 1.2.0-optimized
Дата: 2025
"""

# ============================================================================
# ИМПОРТЫ И ЗАВИСИМОСТИ
# ============================================================================

# Стандартные библиотеки Python
import os                    # Работа с операционной системой и файлами
import logging              # Система логирования для отслеживания событий
import time                 # Работа со временем
import atexit               # Регистрация функций завершения
from datetime import datetime  # Работа с датой и временем
from functools import wraps    # Декораторы для функций

# Flask - основной веб-фреймворк
from flask import (
    Flask,                  # Основной класс приложения
    request,               # Объект HTTP-запроса
    redirect,              # Перенаправление на другие страницы
    url_for,               # Генерация URL по имени маршрута
    flash,                 # Система flash-сообщений
    render_template,       # Рендеринг HTML-шаблонов
    session,               # Работа с пользовательскими сессиями
    send_from_directory,   # Отправка файлов из директории
    abort,                 # Прерывание запроса с HTTP-ошибкой
    jsonify                # Создание JSON-ответов
)

# Дополнительные библиотеки
from werkzeug.utils import secure_filename  # Безопасная обработка имен файлов
from PIL import Image                       # Обработка изображений (Pillow)
from dotenv import load_dotenv              # Загрузка переменных окружения

# Загружаем переменные окружения из .env файла
# Это должно быть выполнено ДО импорта наших модулей
load_dotenv()

# ============================================================================
# ИМПОРТЫ МОДУЛЕЙ ПРОЕКТА
# ============================================================================

# Модуль работы с базой данных PostgreSQL
from db import (
    connect_db,           # Подключение к базе данных
    close_db,             # Закрытие соединения с БД
    save_image,           # Сохранение метаданных изображения
    get_images_list,      # Получение списка изображений
    get_total_images,     # Подсчет общего количества изображений
    get_image_by_id,      # Получение изображения по ID
    delete_image,         # Удаление изображения из БД
    create_table_images,  # Создание таблицы изображений
    create_table_users,   # Создание таблицы пользователей
    register_user,        # Регистрация нового пользователя
    authenticate_user,    # Аутентификация пользователя
    get_user_images,      # Получение изображений пользователя
    get_total_user_images,# Подсчет изображений пользователя
    get_expired_images,   # Получение просроченных изображений
    ensure_schema         # Обеспечение корректности схемы БД
)

# ============================================================================
# НОВЫЕ МОДУЛИ ДЛЯ ОПТИМИЗАЦИИ ПРОИЗВОДИТЕЛЬНОСТИ
# ============================================================================

# Пул соединений для высокой производительности
# Временно отключен из-за проблем с кодировкой
# from db_pool import db_pool, get_pool_metrics

# Асинхронная обработка задач
try:
    from celery_app import process_image_async, log_statistics_async
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    logging.warning("Celery not available. Async processing disabled.")

# Мониторинг производительности
from monitoring import (
    performance_monitor, 
    track_request, 
    track_file_upload, 
    track_file_download,
    get_prometheus_metrics
)

# Redis для кэширования и сессий
try:
    import redis
    from flask_session import Session
    from flask_caching import Cache
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis components not available. Using fallback options.")

# Модуль статистики и администрирования
from admin_db import (
    log_statistics,           # Логирование статистических данных
    get_statistics,           # Получение статистики
    get_statistics_summary,   # Сводка статистики
    create_table_statistics,  # Создание таблицы статистики
    get_total_downloads,      # Общее количество скачиваний
    get_total_files_size,     # Общий размер файлов
    get_statistics_with_filters, # Статистика с фильтрами
    get_statistics_count,     # Подсчет записей статистики
    get_unique_action_types as get_action_types,  # Типы действий
    get_unique_users as get_all_users             # Все пользователи
)

# Модуль административных функций
from admin_app import (
    is_admin,              # Проверка прав администратора
    inject_admin_status,   # Внедрение статуса админа в контекст
    admin_statistics       # Административная статистика
)

# Импорт утилит для группировки flash-сообщений
from flash_utils import (
    flash_grouped_results,     # Группировка результатов операций с файлами
    flash_bulk_operation_result, # Сводные сообщения для массовых операций
    flash_validation_errors,   # Группировка ошибок валидации
    flash_summary_message      # Универсальные сводные сообщения
)

# Модуль конфигурации логирования
from logging_config import (
    setup_logging,         # Настройка системы логирования
    setup_monthly_archive, # Настройка месячного архивирования логов
    cleanup_old_archives   # Очистка старых архивов
)


# ============================================================================
# КОНФИГУРАЦИЯ FLASK ПРИЛОЖЕНИЯ
# ============================================================================

# Создание экземпляра Flask приложения
app = Flask(__name__)

# Конфигурация безопасности
# SECRET_KEY используется для подписи сессий и защиты от CSRF атак
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))

# Конфигурация загрузки файлов
# Максимальный размер загружаемого контента (по умолчанию 50MB)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))

# ============================================================================
# КОНФИГУРАЦИЯ REDIS И КЭШИРОВАНИЯ
# ============================================================================

# Настройка Redis соединения
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

if REDIS_AVAILABLE:
    try:
        # Инициализация Redis клиента
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        # Проверка соединения
        redis_client.ping()
        logging.info("Redis connection established")
        
        # Конфигурация сессий с Redis
        app.config['SESSION_TYPE'] = 'redis'
        app.config['SESSION_REDIS'] = redis_client
        app.config['SESSION_PERMANENT'] = False
        app.config['SESSION_USE_SIGNER'] = True
        app.config['SESSION_KEY_PREFIX'] = 'img_host:session:'
        app.config['SESSION_COOKIE_SECURE'] = False  # True для HTTPS
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        
        # Конфигурация кэша с Redis
        cache_config = {
            'CACHE_TYPE': 'redis',
            'CACHE_REDIS_URL': REDIS_URL,
            'CACHE_DEFAULT_TIMEOUT': 300,  # 5 минут по умолчанию
            'CACHE_KEY_PREFIX': 'img_host:cache:'
        }
        
    except Exception as e:
        logging.error(f"Redis connection failed: {e}")
        redis_client = None
        REDIS_AVAILABLE = False
        
if not REDIS_AVAILABLE:
    # Fallback конфигурация без Redis
    app.config['SESSION_TYPE'] = 'filesystem'
    cache_config = {
        'CACHE_TYPE': 'simple',
        'CACHE_DEFAULT_TIMEOUT': 300
    }
    logging.warning("Using filesystem sessions and simple cache (not recommended for production)")

# Инициализация сессий и кэша
if REDIS_AVAILABLE:
    Session(app)
    cache = Cache(app, config=cache_config)
else:
    cache = None

# Папка для хранения загруженных изображений
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'images')

# Включаем организацию файлов по папкам пользователей
# Каждый пользователь получает свою подпапку в UPLOAD_FOLDER
app.config['USER_FOLDERS'] = True

# Конфигурация сессий
# Сессии не сохраняются после закрытия браузера
app.config['SESSION_PERMANENT'] = False
# Тип хранения сессий - в файловой системе
app.config['SESSION_TYPE'] = 'filesystem'

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ ДИРЕКТОРИЙ
# ============================================================================

# Создаем необходимые директории, если они не существуют
# exist_ok=True предотвращает ошибку, если директория уже существует
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)  # Папка для изображений
os.makedirs('logs', exist_ok=True)                       # Папка для логов
os.makedirs('backups', exist_ok=True)                    # Папка для резервных копий


def get_client_ip():
    """
    Получение реального IP-адреса клиента с учетом прокси-серверов.
    
    Функция проверяет заголовки HTTP_X_FORWARDED_FOR и HTTP_X_REAL_IP,
    которые устанавливаются прокси-серверами (например, Nginx).
    Если заголовки отсутствуют, возвращает прямой IP-адрес.
    
    Проверяемые заголовки (в порядке приоритета):
    1. HTTP_X_FORWARDED_FOR - стандартный заголовок для прокси
    2. HTTP_X_REAL_IP - альтернативный заголовок для Nginx
    3. request.remote_addr - прямое соединение
    
    Returns:
        str: IP-адрес клиента в формате IPv4 или IPv6
        
    Example:
        >>> get_client_ip()
        '192.168.1.100'
    """
    # Проверяем заголовок X-Forwarded-For (может содержать несколько IP)
    if request.environ.get('HTTP_X_FORWARDED_FOR') is not None:
        return request.environ['HTTP_X_FORWARDED_FOR']
    # Проверяем заголовок X-Real-IP (содержит один IP)
    elif request.environ.get('HTTP_X_REAL_IP') is not None:
        return request.environ['HTTP_X_REAL_IP']
    # Возвращаем прямой IP-адрес
    else:
        return request.remote_addr

def login_required(f):
    """
    Декоратор для проверки аутентификации пользователя.
    
    Проверяет наличие 'user_email' в сессии и существование пользователя в базе данных.
    Если пользователь не авторизован или не существует в БД (устаревшая сессия),
    перенаправляет на страницу входа с соответствующим сообщением.
    
    Args:
        f: Функция-обработчик маршрута, которую нужно защитить
        
    Returns:
        function: Обернутая функция с проверкой аутентификации
        
    Security Notes:
        - Проверяет существование пользователя в БД для предотвращения доступа с устаревшими сессиями
        - Автоматически очищает сессию при обнаружении несуществующего пользователя
        - Защищает от доступа после перезапуска контейнеров с очисткой БД
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            flash('Пожалуйста, войдите в систему для доступа к этой странице', 'warning')
            return redirect(url_for('login'))
        
        # Дополнительная проверка: убеждаемся, что пользователь существует в базе данных
        # Это предотвращает доступ с устаревшими сессиями после перезапуска контейнеров
        user_email = session['user_email']
        try:
            conn = connect_db()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT email FROM users WHERE email = %s", (user_email,))
                user_exists = cur.fetchone() is not None
                cur.close()
                close_db(conn)
                
                # Если пользователь не существует в БД, очищаем сессию и требуем повторного входа
                if not user_exists:
                    session.clear()
                    flash('Ваша сессия устарела. Пожалуйста, войдите в систему заново.', 'warning')
                    return redirect(url_for('login'))
            else:
                # Если нет подключения к БД, требуем повторного входа для безопасности
                flash('Ошибка подключения к базе данных. Пожалуйста, войдите заново.', 'error')
                return redirect(url_for('login'))
        except Exception:
            # При любых ошибках БД требуем повторного входа для безопасности
            session.clear()
            flash('Произошла ошибка проверки сессии. Пожалуйста, войдите заново.', 'error')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# ИНИЦИАЛИЗАЦИЯ ЛОГИРОВАНИЯ
# ============================================================================

# Настройка системы логирования с автоматической ротацией файлов
setup_logging()          # Основная конфигурация логирования
setup_monthly_archive()  # Настройка месячного архивирования логов
cleanup_old_archives()   # Очистка старых архивных файлов

# ============================================================================
# КОНСТАНТЫ И НАСТРОЙКИ ПРИЛОЖЕНИЯ
# ============================================================================

# Разрешенные расширения файлов для загрузки
# Поддерживаются только основные форматы изображений для обеспечения безопасности
# и совместимости с веб-браузерами
ALLOWED_EXTENSIONS = {
    'png',   # Portable Network Graphics - поддержка прозрачности
    'jpeg',  # JPEG - сжатие с потерями, хорошо для фотографий
    'jpg',   # Альтернативное расширение для JPEG
    'gif',   # Graphics Interchange Format - поддержка анимации
    'webp'   # WebP - современный формат изображений, поддерживающий прозрачность
}

# Максимальные размеры и ограничения
MAX_IMAGE_DIMENSION = 4096  # Максимальный размер изображения в пикселях
MAX_IMAGES_PER_USER = 1000  # Максимальное количество изображений на пользователя
DEFAULT_STORAGE_DAYS = 30   # Срок хранения по умолчанию (дни)

# Настройки пагинации
IMAGES_PER_PAGE = 12        # Количество изображений на странице
STATISTICS_PER_PAGE = 50    # Количество записей статистики на странице


def allowed_file(filename):
    """
    Проверка допустимости расширения загружаемого файла.
    
    Проверяет, что файл имеет расширение и оно входит в список
    разрешенных форматов изображений для обеспечения безопасности.
    
    Поддерживаемые форматы:
    - PNG: Portable Network Graphics (с прозрачностью)
    - JPG/JPEG: Joint Photographic Experts Group (сжатие с потерями)
    - GIF: Graphics Interchange Format (анимация)
    
    Args:
        filename (str): Имя файла для проверки (например, 'image.jpg')
        
    Returns:
        bool: True если файл разрешен, False в противном случае
        
    Example:
        >>> allowed_file('photo.jpg')
        True
        >>> allowed_file('document.pdf')
        False
        >>> allowed_file('image')
        False
    """
    # Проверяем наличие точки в имени файла
    if '.' not in filename:
        return False
    
    # Извлекаем расширение файла и приводим к нижнему регистру
    file_extension = filename.rsplit('.', 1)[1].lower()
    
    # Проверяем, что расширение входит в список разрешенных
    return file_extension in ALLOWED_EXTENSIONS


# ============================================================================
# МАРШРУТЫ ПРИЛОЖЕНИЯ (ROUTES)
# ============================================================================

@app.route('/')
def index():
    """
    Главная страница приложения.
    
    Отображает основную страницу фото-хостинга с информацией о сервисе,
    возможностями регистрации и входа в систему.
    
    Функциональность:
    - Приветственная информация о сервисе
    - Ссылки на регистрацию и вход
    - Общая информация о возможностях платформы
    
    HTTP Methods:
        GET: Отображение главной страницы
    
    Returns:
        str: HTML-страница с главной страницей (templates/index.html)
        
    Template Variables:
        - Автоматически доступные переменные Flask
        - Статус администратора (через context_processor)
    """
    # Логируем посещение главной страницы для статистики
    try:
        # Получаем email пользователя из сессии, если он авторизован
        user_email = session.get('user_email')
        
        log_statistics(
            action_type='главная_страница',
            user_email=user_email,  # Передаем email если пользователь авторизован
            ip_address=get_client_ip(),
            user_agent=request.headers.get('User-Agent', 'Unknown'),
            additional_info=f'Посещение главной страницы пользователем {user_email or "гость"}'
        )
    except Exception as e:
        # Не прерываем работу при ошибке логирования
        logging.warning(f"Failed to log main page visit: {e}")
    
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Регистрация новых пользователей.
    
    GET: Отображает форму регистрации
    POST: Обрабатывает данные регистрации, создает нового пользователя
          и его персональную папку для изображений
    
    Form fields:
        email (str): Email пользователя (используется как логин)
        password (str): Пароль пользователя
        confirm_password (str): Подтверждение пароля
    
    Returns:
        str: Отрендеренный HTML-шаблон или редирект
    """
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Проверка валидности данных с группировкой ошибок
        validation_errors = []
        
        if not email or not password or not confirm_password:
            validation_errors.append('Пожалуйста, заполните все поля')
        
        if password and confirm_password and password != confirm_password:
            validation_errors.append('Пароли не совпадают')
        
        if validation_errors:
            flash_validation_errors(validation_errors, "регистрации")
            return redirect(url_for('register'))
        
        # Получаем IP-адрес и User-Agent для логирования
        client_ip = get_client_ip()
        user_agent = request.headers.get('User-Agent', '')
        
        # Проверяем, является ли это попыткой регистрации администратора
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        admin_emails_str = os.getenv('ADMIN_EMAILS', 'admin@example.com')
        admin_emails = [e.strip() for e in admin_emails_str.split(',') if e.strip()]
        if admin_email not in admin_emails:
            admin_emails.append(admin_email)
        
        is_admin_registration = email in admin_emails
        
        # Регистрация пользователя
        success, message = register_user(email, password)
        if success:
            # Создаем папку для пользователя
            user_folder = os.path.join(app.config['UPLOAD_FOLDER'], email)
            os.makedirs(user_folder, exist_ok=True)
            logging.info(f'Created folder for user: {email}')
            
            # Логируем успешную регистрацию
            if is_admin_registration:
                log_statistics(
                    action_type='успешная_регистрация_админа',
                    user_email=email,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    additional_info=f'Успешная регистрация администратора {email}'
                )
            else:
                log_statistics(
                    action_type='регистрация',
                    user_email=email,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    additional_info=f'Успешная регистрация пользователя {email}'
                )
            
            flash(message, 'success')
            return redirect(url_for('login'))
        else:
            # Логируем неудачную регистрацию
            if is_admin_registration:
                # Специальное логирование для неудачной регистрации администратора
                log_statistics(
                    action_type='неудачная_регистрация_админа',
                    user_email=email,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    additional_info=f'Попытка регистрации с email администратора {email} и неверным паролем'
                )
            else:
                # Обычная неудачная регистрация
                log_statistics(
                    action_type='неудачная_регистрация',
                    user_email=email,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    additional_info=f'Неудачная регистрация: {message}'
                )
            
            flash(message, 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Аутентификация пользователей.
    
    GET: Отображает форму входа
    POST: Проверяет учетные данные, создает сессию и логирует попытки входа
    
    Form fields:
        email (str): Email пользователя
        password (str): Пароль пользователя
    
    Логирует все попытки входа (успешные и неудачные) в таблицу statistics.
    
    Returns:
        str: Отрендеренный HTML-шаблон или редирект
    """
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Проверка валидности данных
        if not email or not password:
            flash('Пожалуйста, заполните все поля', 'warning')
            return redirect(url_for('login'))
            
        # Запись статистики попытки входа
        log_statistics(
            action_type='попытка_входа',
            user_email=email,
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string
        )
        
        # Аутентификация пользователя
        success, message = authenticate_user(email, password)
        if success:
            session['user_email'] = email
            
            # Запись статистики успешного входа
            log_statistics(
                action_type='успешный_вход',
                user_email=email,
                ip_address=get_client_ip(),
                user_agent=request.user_agent.string
            )
            
            flash(message, 'success')
            return redirect(url_for('index'))
        else:
            # Запись статистики неудачного входа
            log_statistics(
                action_type='неудачный_вход',
                user_email=email,
                ip_address=get_client_ip(),
                user_agent=request.user_agent.string,
                additional_info=message
            )
            
            flash(message, 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    Выход пользователя из системы.
    
    Удаляет данные пользователя из сессии и перенаправляет на главную страницу.
    
    Returns:
        Response: Редирект на главную страницу
    """
    session.pop('user_email', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))




# Регистрируем контекстный процессор для админ-функций
@app.context_processor
def inject_admin_status_processor():
    return inject_admin_status()

# ============================================================================
# НОВЫЕ ENDPOINTS ДЛЯ МОНИТОРИНГА И ОПТИМИЗАЦИИ
# ============================================================================

@app.route('/health')
def health_check():
    """
    Health check endpoint для мониторинга состояния приложения.
    
    Проверяет:
    - Состояние приложения Flask
    - Подключение к базе данных
    - Состояние пула соединений
    - Доступность Redis (если используется)
    
    Returns:
        JSON: Статус здоровья системы
    """
    try:
        # Проверка базы данных
        db_health = db_pool.health_check()
        
        # Получение метрик пула
        pool_metrics = get_pool_metrics()
        
        # Проверка Redis (если доступен)
        redis_health = True
        if REDIS_AVAILABLE and 'redis_client' in globals():
            try:
                redis_client.ping()
            except:
                redis_health = False
        
        # Общий статус
        overall_health = db_health and (redis_health if REDIS_AVAILABLE else True)
        
        return jsonify({
            'status': 'healthy' if overall_health else 'unhealthy',
            'database': 'ok' if db_health else 'error',
            'redis': 'ok' if redis_health else 'error' if REDIS_AVAILABLE else 'not_configured',
            'pool_metrics': pool_metrics,
            'timestamp': time.time()
        }), 200 if overall_health else 503
        
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': time.time()
        }), 503

@app.route('/metrics')
def metrics():
    """
    Endpoint для получения метрик приложения в формате Prometheus.
    Используется системами мониторинга.
    """
    try:
        # Получаем метрики в формате Prometheus
        prometheus_metrics = get_prometheus_metrics()
        
        # Добавляем дополнительные метрики
        additional_metrics = performance_monitor.get_comprehensive_metrics()
        
        # Возвращаем в формате Prometheus
        from flask import Response
        return Response(prometheus_metrics, mimetype='text/plain')
        
    except Exception as e:
        logging.error(f"Error generating metrics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/metrics/json')
def metrics_json():
    """
    Endpoint для получения метрик в JSON формате.
    """
    try:
        metrics_data = {
            'pool_metrics': get_pool_metrics(),
            'system_metrics': performance_monitor.get_comprehensive_metrics(),
            'app_metrics': {
                'uptime': time.time() - app.start_time if hasattr(app, 'start_time') else 0,
                'version': '1.2.0-optimized',
                'redis_available': REDIS_AVAILABLE,
                'celery_available': CELERY_AVAILABLE
            }
        }
        return jsonify(metrics_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def process_single_file(file, user_email, user_folder, storage_days):
    """
    Комплексная обработка одного загружаемого файла.
    
    Выполняет полный цикл обработки файла:
    - Проверка размера и формата
    - Генерация безопасного уникального имени
    - Сохранение в файловую систему
    - Валидация как изображения
    - Сохранение метаданных в БД
    - Логирование статистики
    
    Args:
        file: Объект загружаемого файла из Flask request
        user_email (str): Email пользователя-владельца
        user_folder (str): Путь к папке пользователя
        storage_days (int): Количество дней хранения файла
    
    Returns:
        dict: Результат обработки с ключами:
            - success (bool): Успешность операции
            - filename (str): Имя сохраненного файла (при успехе)
            - original_name (str): Оригинальное имя файла (при успехе)
            - url (str): URL для доступа к файлу (при успехе)
            - size (int): Размер файла в байтах (при успехе)
            - file_id (int): ID файла в БД (при успехе)
            - error (str): Описание ошибки (при неудаче)
    """
    try:
        # Проверка размера файла
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > app.config['MAX_CONTENT_LENGTH']:
            return {
                'success': False,
                'error': f'Размер файла превышает допустимый предел (5MB): {file_size} bytes'
            }
        
        # Проверка расширения файла
        if not allowed_file(file.filename):
            return {
                'success': False,
                'error': f'Неподдерживаемый формат файла. Разрешены: {", ".join(ALLOWED_EXTENSIONS)}'
            }
        
        # Генерация безопасного имени файла
        base_name, ext_name = os.path.splitext(file.filename)
        safe_filename = secure_filename(base_name) + ext_name
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        new_filename = f"{base_name}_(Foto-Hosting_{timestamp}){ext_name}"
        
        file_path = os.path.join(user_folder, new_filename)
        
        # Сохранение файла
        file.save(file_path)
        logging.info(f'File {new_filename} successfully saved to {file_path}')
        
        # Проверка, что файл является изображением
        with Image.open(file_path) as img:
            img.verify()
            actual_size = os.path.getsize(file_path)
            logging.info(f'File {new_filename} successfully verified as an image (size: {actual_size} bytes)')
        
        # Сохранение метаданных в базу данных
        file_type = ext_name.lower().replace('.', '')
        upload_time = datetime.now()
        try:
            save_image(new_filename, file.filename, actual_size, upload_time, file_type, user_email, storage_days)
        except Exception as db_error:
            # Проверяем, если ошибка связана с foreign key constraint (пользователь не существует)
            if "foreign key constraint" in str(db_error) and "user_email" in str(db_error):
                # Удаляем загруженный файл
                if os.path.exists(file_path):
                    os.remove(file_path)
                # Очищаем сессию и перенаправляем на главную страницу
                session.clear()
                raise Exception("Сессия пользователя устарела. Пожалуйста, войдите в систему заново.")
            else:
                # Если это другая ошибка БД, пробрасываем её дальше
                raise db_error
        
        # Получение ID загруженного изображения
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM images WHERE filename = %s ORDER BY upload_time DESC LIMIT 1", (new_filename,))
        file_id = cur.fetchone()[0] if cur.rowcount > 0 else None
        cur.close()
        close_db(conn)
        
        # Запись статистики успешной загрузки
        log_statistics(
            action_type='успешная_загрузка',
            user_email=user_email,
            file_id=file_id,
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string,
            additional_info=f"Size: {actual_size} bytes, Type: {file_type}, Storage: {storage_days} days"
        )
        
        # Генерация URL
        image_url = url_for('get_image', user_email=user_email, filename=new_filename, _external=True)
        view_url = url_for('view_image', user_email=user_email, filename=new_filename, _external=True)
        download_url = url_for('download_image', user_email=user_email, filename=new_filename, _external=True)
        
        return {
            'success': True,
            'filename': new_filename,
            'original_name': file.filename,
            'url': image_url,
            'view_url': view_url,
            'download_url': download_url,
            'size': actual_size,
            'file_id': file_id
        }
        
    except Exception as e:
        # Удаляем файл в случае ошибки
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
            logging.error(f'File {new_filename if "new_filename" in locals() else file.filename} deleted due to error: {str(e)}')
        
        logging.error(f'Error processing file {file.filename}: {str(e)}')
        return {
            'success': False,
            'error': f'Ошибка при обработке файла: {str(e)}'
        }

@app.route('/statistics')
@login_required
def view_statistics():
    """
    Отображение статистики системы с пагинацией и фильтрацией.
    
    Показывает сводную и детальную статистику действий в системе.
    Доступно только администраторам (проверка через is_admin()).
    
    Returns:
        str: Отрендеренный HTML-шаблон со статистикой или редирект
    """
    # Проверяем права администратора - только администраторы могут просматривать статистику
    if not is_admin():
        flash('Доступ запрещен. Статистика доступна только администраторам.', 'error')
        return redirect(url_for('index'))
    
    # Получаем параметры фильтрации и пагинации
    action_type = request.args.get('action_type', '')
    user_email = request.args.get('user_email', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    # Получаем сводную статистику для отображения
    summary = get_statistics_summary()
    
    # Получаем общее количество записей для пагинации
    total_records = get_statistics_count(action_type, user_email)
    total_pages = (total_records + per_page - 1) // per_page
    
    # Получаем детальную статистику с фильтрацией и пагинацией
    offset = (page - 1) * per_page
    details = get_statistics_with_filters(action_type, user_email, per_page, offset)
    
    # Получаем список всех типов действий для фильтра
    action_types = get_action_types()
    
    # Получаем список всех пользователей для фильтра
    users = get_all_users()
    
    return render_template('statistics.html', 
                         summary=summary, 
                         details=details,
                         action_types=action_types,
                         users=users,
                         current_action_type=action_type,
                         current_user_email=user_email,
                         current_page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         total_records=total_records)

@app.route('/admin_statistics')
@login_required
def admin_statistics_route():
    """
    Роут для административной панели с системной статистикой.
    
    Вызывает функцию admin_statistics из модуля admin_app.
    
    Returns:
        str: Отрендеренный HTML-шаблон административной панели или редирект
    """
    return admin_statistics()


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """
    Загрузка изображений пользователями.
    
    GET: Отображает форму загрузки файлов
    POST: Обрабатывает множественную загрузку файлов
    
    Form fields:
        file: Один или несколько файлов изображений
        storage_period: Срок хранения ('15' или '30' дней)
    
    Поддерживаемые форматы: PNG, JPG, JPEG, GIF
    Максимальный размер одного файла: 5MB
    
    Для каждого файла:
    - Проверяет формат и размер
    - Создает уникальное имя с временной меткой
    - Сохраняет в персональную папку пользователя
    - Записывает метаданные в БД
    - Логирует статистику
    
    Returns:
        str: Отрендеренный HTML-шаблон с результатами загрузки
    """
    
    # Обработка GET запроса с параметрами error
    if request.method == 'GET':
        error_type = request.args.get('error')
        if error_type == 'no_files':
            flash('Выберите файлы для загрузки', 'warning')
        elif error_type == 'upload_failed':
            error_message = request.args.get('message', 'Ошибка при загрузке файлов')
            flash(error_message, 'error')
        
        if error_type:
            return render_template('upload.html')
    
    if request.method == 'POST':
        # Поддержка множественной загрузки
        files = request.files.getlist('file')
        
        if not files or all(f.filename == '' for f in files):
            logging.warning('Upload attempt without selecting files')
            flash('Файлы не выбраны', 'warning')
            
            # Запись статистики ошибки загрузки
            log_statistics(
                action_type='upload_error',
                user_email=session['user_email'],
                ip_address=get_client_ip(),
                user_agent=request.user_agent.string,
                additional_info='Нет выбранных файлов'
            )
            
            return redirect(request.url)
        
        # Получаем срок хранения файла
        storage_period = request.form.get('storage_period', '30')
        storage_days = 30 if storage_period == '30' else 15
        
        user_email = session['user_email']
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_email)
        os.makedirs(user_folder, exist_ok=True)
        
        uploaded_files = []
        failed_files = []
        
        for file in files:
            if file.filename == '':
                continue
                
            try:
                result = process_single_file(file, user_email, user_folder, storage_days)
                if result['success']:
                    uploaded_files.append(result)
                else:
                    failed_files.append({'filename': file.filename, 'error': result['error']})
            except Exception as e:
                logging.error(f'Error processing file {file.filename}: {str(e)}')
                # Проверяем, если ошибка связана с устаревшей сессией
                if "Сессия пользователя устарела" in str(e):
                    flash('Ваша сессия устарела. Пожалуйста, войдите в систему заново.', 'warning')
                    return redirect(url_for('login'))
                failed_files.append({'filename': file.filename, 'error': str(e)})
        
        # Результаты загрузки
        # Используем группировку flash-сообщений вместо множественных отдельных сообщений
        if uploaded_files or failed_files:
            flash_grouped_results(uploaded_files, failed_files, "загрузки")
        
        if uploaded_files:
            if len(uploaded_files) == 1 and not failed_files:
                # Если загружен только один файл без ошибок, показываем детальную страницу
                file_data = uploaded_files[0]
                return render_template('upload_success.html', 
                                     image_url=file_data['url'],
                                     filename=file_data['filename'],
                                     original_name=file_data['original_name'],
                                     file_size=file_data['size'],
                                     view_url=file_data['view_url'],
                                     download_url=file_data['download_url'])
            else:
                # Множественная загрузка или есть ошибки - показываем сводную страницу
                return render_template('upload_success_multiple.html', uploaded_files=uploaded_files, failed_files=failed_files)
        
        return redirect(request.url)
    
    return render_template('upload.html')


@app.route('/view/<user_email>/<filename>')
def view_image(user_email, filename):
    """
    Маршрут для просмотра изображения с записью статистики.
    
    Записывает статистику просмотра и перенаправляет на изображение.
    Используется только при явном нажатии кнопки "Просмотр".
    
    Args:
        user_email (str): Email пользователя-владельца изображения
        filename (str): Имя файла изображения
    
    Returns:
        Response: Перенаправление на изображение
    """
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_email)
    file_path = os.path.join(user_folder, filename)
    
    if not os.path.exists(file_path):
        logging.warning(f'Attempt to view non-existent file: {filename} for user: {user_email}')
        abort(404)
    
    # Записываем статистику просмотра только при явном действии пользователя
    log_statistics(
        action_type='просмотр_изображения',
        user_email=session.get('user_email', 'anonymous'),
        ip_address=get_client_ip(),
        user_agent=request.user_agent.string,
        additional_info=f'Image: {filename}, Owner: {user_email}'
    )
    
    # Перенаправляем на прямую ссылку изображения
    return redirect(url_for('get_image', user_email=user_email, filename=filename))

@app.route('/download/<user_email>/<filename>')
def download_image(user_email, filename):
    """
    Обработка нажатия кнопки скачивания с записью статистики.
    
    Записывает статистику скачивания при нажатии кнопки "Скачать" и перенаправляет
    на фактическое скачивание файла через get_image.
    
    Args:
        user_email (str): Email пользователя-владельца изображения
        filename (str): Имя файла изображения
    
    Returns:
        Response: Редирект на get_image для фактического скачивания
    """
    # Записываем статистику скачивания (только при нажатии кнопки)
    log_statistics(
        action_type='download',
        user_email=session.get('user_email', 'anonymous'),
        ip_address=get_client_ip(),
        user_agent=request.user_agent.string,
        additional_info=f'Download: {filename}, Owner: {user_email}'
    )
    
    # Перенаправляем на фактическое скачивание
    return redirect(url_for('get_image', user_email=user_email, filename=filename))

@app.route('/images/<user_email>/<filename>')
def get_image(user_email, filename):
    """
    Прямой доступ к изображениям без записи статистики.
    
    Позволяет получить изображение по URL вида /images/user@email.com/filename.jpg
    без записи статистики. Статистика скачиваний ведется только через кнопку "Скачать".
    
    Args:
        user_email (str): Email пользователя-владельца изображения
        filename (str): Имя файла изображения
    
    Returns:
        Response: Файл изображения или 404 если файл не найден
    """
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_email)
    file_path = os.path.join(user_folder, filename)
    
    if not os.path.exists(file_path):
        logging.warning(f'Attempt to access non-existent file: {filename} for user: {user_email}')
        abort(404)
    
    return send_from_directory(user_folder, filename)

@app.route('/images/<filename>')
@login_required
def uploaded_file(filename):
    """
    Защищенный доступ к изображениям текущего пользователя.
    
    Позволяет авторизованному пользователю получить доступ к своим изображениям
    по короткому URL вида /images/filename.jpg
    
    Args:
        filename (str): Имя файла изображения
    
    Returns:
        Response: Файл изображения или редирект на список изображений с ошибкой
        
    Security:
        - Требует авторизации
        - Проверяет принадлежность файла текущему пользователю
        - Логирует попытки доступа к несуществующим файлам
    """
    # Проверяем, что файл принадлежит текущему пользователю
    user_email = session['user_email']
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_email)
    file_path = os.path.join(user_folder, filename)
    
    if not os.path.exists(file_path):
        logging.warning(f'Attempt to access non-existent file: {filename} by user: {user_email}')
        flash('Файл не найден или у вас нет доступа к нему', 'error')
        return redirect(url_for('images_list'))
    
    # Возвращаем файл напрямую из папки пользователя
    return send_from_directory(user_folder, filename)


@app.route('/images-list')
@login_required
def images_list():
    """
    Отображение списка изображений пользователя с пагинацией.
    
    Показывает галерею изображений текущего авторизованного пользователя
    с поддержкой постраничной навигации.
    
    Query parameters:
        page (int): Номер страницы (по умолчанию 1)
    
    Returns:
        str: Отрендеренный HTML-шаблон images_list.html с данными:
            - images: Список изображений на текущей странице
            - page: Текущий номер страницы
            - total_pages: Общее количество страниц
            
    Настройки:
        - per_page: 10 изображений на странице
        - Автоматический расчет общего количества страниц
    """
    # Получаем параметры пагинации из запроса
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Количество изображений на странице
    
    # Получаем email текущего пользователя
    user_email = session['user_email']
    
    try:
        # Получаем список изображений пользователя с учетом пагинации
        images = get_user_images(user_email, page=page, per_page=per_page)
        total_images = get_total_user_images(user_email)
        
        # Вычисляем общее количество страниц
        total_pages = (total_images + per_page - 1) // per_page if total_images > 0 else 1
        
        return render_template('images_list.html', 
                               images=images, 
                               page=page, 
                               total_pages=total_pages)
    except Exception as e:
        # Проверяем, если ошибка связана с foreign key constraint (пользователь не существует)
        if "foreign key constraint" in str(e) and "user_email" in str(e):
            session.clear()
            flash('Ваша сессия устарела. Пожалуйста, войдите в систему заново.', 'warning')
            return redirect(url_for('login'))
        else:
            # Если это другая ошибка БД, логируем и показываем общую ошибку
            logging.error(f'Error getting user images: {str(e)}')
            flash('Произошла ошибка при загрузке изображений.', 'error')
            return redirect(url_for('login'))


@app.route('/delete/<int:id>')
@login_required
def delete_image_route(id):
    """
    Удаление изображения пользователем.
    
    Позволяет авторизованному пользователю удалить свое изображение
    как из файловой системы, так и из базы данных.
    
    Args:
        id (int): ID изображения в базе данных
    
    Returns:
        Response: Редирект на список изображений с сообщением о результате
        
    Security:
        - Требует авторизации
        - Проверяет принадлежность изображения текущему пользователю
        - Проверяет существование изображения в БД
        
    Actions:
        - Удаляет файл с диска
        - Удаляет запись из базы данных
        - Логирует операцию в статистику (успех/ошибка)
        - Показывает flash-сообщения пользователю
     """
    # Получаем информацию об изображении
    image = get_image_by_id(id)
    if not image:
        flash('Изображение не найдено', 'error')
        
        # Запись статистики ошибки удаления
        log_statistics(
            action_type='delete_error',
            user_email=session['user_email'],
            file_id=id,
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string,
            additional_info='Изображение не найдено'
        )
        
        return redirect(url_for('images_list'))
    
    # Проверяем, принадлежит ли изображение текущему пользователю
    user_email = session['user_email']
    image_user_email = image[6]  # Индекс user_email в результате запроса
    
    if image_user_email != user_email:
        logging.warning(f'User {user_email} attempted to delete image {id} belonging to {image_user_email}')
        flash('У вас нет прав для удаления этого изображения', 'error')
        
        # Запись статистики ошибки доступа при удалении
        log_statistics(
            action_type='delete_access_denied',
            user_email=user_email,
            file_id=id,
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string,
            additional_info=f'Попытка удаления изображения пользователя {image_user_email}'
        )
        
        return redirect(url_for('images_list'))
    
    # Удаляем физический файл
    filename = image[1]  # Получаем имя файла из результата запроса
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_email, filename)
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f'File {filename} deleted from disk for user {user_email}')
        
        # Удаляем запись из базы данных
        delete_image(id)
        logging.info(f'Image with ID {id} deleted from database for user {user_email}')
        
        # Запись статистики успешного удаления
        log_statistics(
            action_type='успешное_удаление',
            user_email=user_email,
            file_id=id,
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string,
            additional_info=f'Удалено изображение {filename}'
        )
        
        flash('Изображение успешно удалено', 'success')
    except Exception as e:
        logging.error(f'Error deleting image with ID {id} for user {user_email}: {str(e)}')
        flash('Ошибка при удалении изображения', 'error')
        
        # Запись статистики ошибки при удалении
        log_statistics(
            action_type='delete_error',
            user_email=user_email,
            file_id=id,
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string,
            additional_info=f'Ошибка: {str(e)}'
        )
    
    return redirect(url_for('images_list'))


@app.route('/delete-multiple', methods=['POST'])
@login_required
def delete_multiple_images():
    """
    Групповое удаление изображений пользователем.
    
    Позволяет авторизованному пользователю удалить несколько своих изображений
    одновременно как из файловой системы, так и из базы данных.
    
    Form Data:
        image_ids (list): Список ID изображений для удаления
    
    Returns:
        Response: Редирект на список изображений с сообщением о результате
        
    Security:
        - Требует авторизации
        - Проверяет принадлежность каждого изображения текущему пользователю
        - Проверяет существование изображений в БД
        
    Actions:
        - Удаляет файлы с диска
        - Удаляет записи из базы данных
        - Логирует операции в статистику (успех/ошибка)
        - Показывает flash-сообщения пользователю с результатами
    """
    
    # Получаем список ID изображений для удаления
    image_ids = request.form.getlist('image_ids')
    
    if not image_ids:
        flash('Не выбрано ни одного изображения для удаления', 'warning')
        return redirect(url_for('images_list'))
        
    user_email = session['user_email']
    successful_deletions = 0
    failed_deletions = 0
    deleted_filenames = []
    
    for image_id in image_ids:
        try:
            # Получаем информацию об изображении
            image = get_image_by_id(int(image_id))
            if not image:
                logging.warning(f'Image with ID {image_id} not found for user {user_email}')
                failed_deletions += 1
                
                # Запись статистики ошибки удаления
                log_statistics(
                    action_type='delete_error',
                    user_email=user_email,
                    file_id=int(image_id),
                    ip_address=get_client_ip(),
                    user_agent=request.user_agent.string,
                    additional_info='Изображение не найдено при групповом удалении'
                )
                continue
            
            # Проверяем принадлежность изображения текущему пользователю
            image_user_email = image[6]  # Индекс user_email в результате запроса
            
            if image_user_email != user_email:
                logging.warning(f'User {user_email} attempted to delete image {image_id} belonging to {image_user_email} in bulk operation')
                failed_deletions += 1
                
                # Запись статистики ошибки доступа при удалении
                log_statistics(
                    action_type='delete_access_denied',
                    user_email=user_email,
                    file_id=int(image_id),
                    ip_address=get_client_ip(),
                    user_agent=request.user_agent.string,
                    additional_info=f'Попытка группового удаления изображения пользователя {image_user_email}'
                )
                continue
            
            # Удаляем физический файл
            filename = image[1]  # Получаем имя файла из результата запроса
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_email, filename)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f'File {filename} deleted from disk for user {user_email} (bulk operation)')
            
            # Удаляем запись из базы данных
            delete_image(int(image_id))
            logging.info(f'Image with ID {image_id} deleted from database for user {user_email} (bulk operation)')
            
            # Запись статистики успешного удаления
            log_statistics(
                action_type='успешное_удаление',
                user_email=user_email,
                file_id=int(image_id),
                ip_address=get_client_ip(),
                user_agent=request.user_agent.string,
                additional_info=f'Групповое удаление изображения {filename}'
            )
            
            successful_deletions += 1
            deleted_filenames.append(filename)
            
        except Exception as e:
            logging.error(f'Error deleting image with ID {image_id} for user {user_email} in bulk operation: {str(e)}')
            failed_deletions += 1
            
            # Запись статистики ошибки при удалении
            log_statistics(
                action_type='delete_error',
                user_email=user_email,
                file_id=int(image_id) if image_id.isdigit() else 0,
                ip_address=get_client_ip(),
                user_agent=request.user_agent.string,
                additional_info=f'Ошибка группового удаления: {str(e)}'
            )

    # Показываем результат операции
    flash_bulk_operation_result(
        success_count=successful_deletions,
        error_count=failed_deletions,
        operation="удаление изображений"
    )
    
    # Дополнительная информация о удаленных файлах
    if successful_deletions > 0:
        logging.info(f'Bulk deletion completed for user {user_email}: {successful_deletions} successful, {failed_deletions} failed')
        if len(deleted_filenames) <= 3:  # Показываем имена файлов только если их немного
            flash(f'Удалены файлы: {", ".join(deleted_filenames)}', 'info')
    
    return redirect(url_for('images_list'))


@app.route('/download-multiple', methods=['POST'])
@login_required
def download_multiple_images():
    """
    Групповое скачивание изображений пользователем.
    
    Позволяет авторизованному пользователю скачать несколько своих изображений
    одновременно в виде ZIP-архива.
    
    Form Data:
        image_ids (list): Список ID изображений для скачивания
    
    Returns:
        Response: ZIP-архив с выбранными изображениями или редирект с ошибкой
        
    Security:
        - Требует авторизации
        - Проверяет принадлежность каждого изображения текущему пользователю
        - Проверяет существование изображений в БД и файловой системе
        
    Actions:
        - Создает временный ZIP-архив
        - Добавляет файлы в архив с оригинальными именами
        - Логирует операции в статистику
        - Отправляет архив пользователю
        - Удаляет временный файл
    """
    import zipfile
    import tempfile
    from flask import send_file
    
    # Получаем список ID изображений для скачивания
    image_ids = request.form.getlist('image_ids')
    
    if not image_ids:
        flash('Не выбрано ни одного изображения для скачивания', 'warning')
        return redirect(url_for('images_list'))
    
    user_email = session['user_email']
    successful_downloads = 0
    failed_downloads = 0
    downloaded_filenames = []
    
    # Создаем временный ZIP-файл
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    
    try:
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for image_id in image_ids:
                try:
                    # Получаем информацию об изображении
                    image = get_image_by_id(int(image_id))
                    if not image:
                        logging.warning(f'Image with ID {image_id} not found for user {user_email}')
                        failed_downloads += 1
                        continue
                    
                    # Проверяем принадлежность изображения текущему пользователю
                    image_user_email = image[6]  # Индекс user_email в результате запроса
                    
                    if image_user_email != user_email:
                        logging.warning(f'User {user_email} attempted to download image {image_id} belonging to {image_user_email} in bulk operation')
                        failed_downloads += 1
                        continue
                    
                    # Получаем пути к файлу
                    filename = image[1]  # Системное имя файла
                    original_name = image[2]  # Оригинальное имя файла
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_email, filename)
                    
                    if not os.path.exists(file_path):
                        logging.warning(f'File {filename} not found on disk for user {user_email}')
                        failed_downloads += 1
                        continue
                    
                    # Добавляем файл в архив с оригинальным именем
                    zipf.write(file_path, original_name)
                    
                    # Запись статистики скачивания
                    log_statistics(
                        action_type='download',
                        user_email=user_email,
                        file_id=int(image_id),
                        ip_address=get_client_ip(),
                        user_agent=request.user_agent.string,
                        additional_info=f'Групповое скачивание: {original_name}'
                    )
                    
                    successful_downloads += 1
                    downloaded_filenames.append(original_name)
                    
                except Exception as e:
                    logging.error(f'Error processing image with ID {image_id} for user {user_email} in bulk download: {str(e)}')
                    failed_downloads += 1
        
        # Проверяем, есть ли файлы для скачивания
        if successful_downloads == 0:
            flash('Не удалось подготовить файлы для скачивания', 'error')
            os.unlink(temp_zip.name)  # Удаляем пустой архив
            return redirect(url_for('images_list'))
        
        # Формируем имя архива
        archive_name = f'images_{user_email}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        
        # Логируем общую операцию группового скачивания
        log_statistics(
            action_type='bulk_download',
            user_email=user_email,
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string,
            additional_info=f'Групповое скачивание: {successful_downloads} файлов, {failed_downloads} ошибок'
        )
        
        logging.info(f'Bulk download completed for user {user_email}: {successful_downloads} successful, {failed_downloads} failed')
        
        # Отправляем архив пользователю
        return send_file(
            temp_zip.name,
            as_attachment=True,
            download_name=archive_name,
            mimetype='application/zip'
        )
        
    except Exception as e:
        logging.error(f'Error creating ZIP archive for user {user_email}: {str(e)}')
        flash('Ошибка при создании архива для скачивания', 'error')
        
        # Удаляем временный файл в случае ошибки
        try:
            os.unlink(temp_zip.name)
        except:
            pass
        
        return redirect(url_for('images_list'))
    
    finally:
        # Планируем удаление временного файла через некоторое время
        # В production лучше использовать фоновую задачу
        try:
            import threading
            def cleanup_temp_file():
                import time
                time.sleep(60)  # Ждем минуту перед удалением
                try:
                    os.unlink(temp_zip.name)
                except:
                    pass
            
            cleanup_thread = threading.Thread(target=cleanup_temp_file)
            cleanup_thread.daemon = True
            cleanup_thread.start()
        except:
            pass


@app.route('/create-share-link', methods=['POST'])
@login_required
def create_share_link():
    """
    Создание временной ссылки для скачивания выбранных изображений.
    
    Позволяет авторизованному пользователю создать временную ссылку для
    удаленного скачивания выбранных изображений другими пользователями.
    
    JSON Data:
        image_ids (list): Список ID изображений для включения в ссылку
    
    Returns:
        JSON: Ответ с информацией о созданной ссылке или ошибке
        {
            "success": true/false,
            "share_url": "http://...",  # URL для скачивания
            "token": "abc123...",       # Уникальный токен
            "expires_at": "2024-01-16T14:30:25",  # Время истечения
            "file_count": 3,            # Количество файлов
            "error": "error message"    # Сообщение об ошибке (если есть)
        }
        
    Security:
        - Требует авторизации
        - Проверяет принадлежность каждого изображения текущему пользователю
        - Создает уникальный токен с ограниченным временем жизни
        - Сохраняет информацию о ссылке в Redis/файловой системе
        
    Actions:
        - Валидирует список изображений
        - Генерирует уникальный токен
        - Сохраняет метаданные ссылки
        - Возвращает URL для скачивания
        - Логирует создание ссылки
    """
    import secrets
    import json
    from datetime import datetime, timedelta
    
    global REDIS_AVAILABLE
    
    try:
        # Получаем данные из JSON запроса
        data = request.get_json()
        if not data or 'image_ids' not in data:
            return jsonify({
                'success': False,
                'error': 'Не указаны изображения для создания ссылки'
            }), 400
        
        image_ids = data['image_ids']
        if not image_ids or not isinstance(image_ids, list):
            return jsonify({
                'success': False,
                'error': 'Список изображений пуст или некорректен'
            }), 400
        
        user_email = session['user_email']
        valid_images = []
        
        # Проверяем каждое изображение
        for image_id in image_ids:
            try:
                image = get_image_by_id(int(image_id))
                if not image:
                    logging.warning(f'Image with ID {image_id} not found for share link creation by user {user_email}')
                    continue
                
                # Проверяем принадлежность изображения текущему пользователю
                image_user_email = image[6]  # Индекс user_email в результате запроса
                
                if image_user_email != user_email:
                    logging.warning(f'User {user_email} attempted to create share link for image {image_id} belonging to {image_user_email}')
                    continue
                
                # Проверяем существование файла
                filename = image[1]  # Системное имя файла
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_email, filename)
                
                if not os.path.exists(file_path):
                    logging.warning(f'File {filename} not found on disk for share link creation by user {user_email}')
                    continue
                
                valid_images.append({
                    'id': int(image_id),
                    'filename': filename,
                    'original_name': image[2],
                    'size': image[3],
                    'file_type': image[5]
                })
                
            except Exception as e:
                logging.error(f'Error validating image {image_id} for share link: {str(e)}')
                continue
        
        if not valid_images:
            return jsonify({
                'success': False,
                'error': 'Не найдено доступных изображений для создания ссылки'
            }), 400
        
        # Генерируем уникальный токен
        token = secrets.token_urlsafe(32)
        
        # Устанавливаем время истечения (24 часа)
        expires_at = datetime.now() + timedelta(hours=24)
        
        # Подготавливаем метаданные ссылки
        share_data = {
            'token': token,
            'user_email': user_email,
            'images': valid_images,
            'created_at': datetime.now().isoformat(),
            'expires_at': expires_at.isoformat(),
            'file_count': len(valid_images)
        }
        
        # Сохраняем данные ссылки
        if REDIS_AVAILABLE and redis_client:
            try:
                # Сохраняем в Redis с автоматическим истечением
                redis_key = f'share_link:{token}'
                redis_client.setex(
                    redis_key,
                    int(timedelta(hours=24).total_seconds()),
                    json.dumps(share_data, ensure_ascii=False)
                )
                logging.info(f'Share link saved to Redis: {token} for user {user_email}')
            except Exception as e:
                logging.error(f'Error saving share link to Redis: {str(e)}')
                # Fallback к файловой системе
                REDIS_AVAILABLE = False
        
        if not REDIS_AVAILABLE:
            # Сохраняем в файловую систему
            share_links_dir = os.path.join('logs', 'share_links')
            os.makedirs(share_links_dir, exist_ok=True)
            
            share_file = os.path.join(share_links_dir, f'{token}.json')
            with open(share_file, 'w', encoding='utf-8') as f:
                json.dump(share_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f'Share link saved to file: {token} for user {user_email}')
        
        # Генерируем URL для скачивания
        share_url = url_for('download_shared', token=token, _external=True)
        
        # Логируем создание ссылки
        log_statistics(
            action_type='share_link_created',
            user_email=user_email,
            ip_address=get_client_ip(),
            user_agent=request.user_agent.string,
            additional_info=f'Создана ссылка для скачивания: {len(valid_images)} файлов, токен: {token[:8]}...'
        )
        
        logging.info(f'Share link created successfully: {token} for user {user_email}, {len(valid_images)} files')
        
        return jsonify({
            'success': True,
            'share_url': share_url,
            'token': token,
            'expires_at': expires_at.isoformat(),
            'file_count': len(valid_images)
        })
        
    except Exception as e:
        logging.error(f'Error creating share link for user {session.get("user_email", "unknown")}: {str(e)}')
        return jsonify({
            'success': False,
            'error': 'Внутренняя ошибка сервера при создании ссылки'
        }), 500


@app.route('/shared/<token>')
def download_shared(token):
    """
    Скачивание файлов по временной ссылке.
    
    Позволяет любому пользователю (без авторизации) скачать файлы
    по временной ссылке, созданной владельцем изображений.
    
    Args:
        token (str): Уникальный токен временной ссылки
    
    Returns:
        Response: ZIP-архив с файлами или страница с ошибкой
        
    Security:
        - Не требует авторизации (публичная ссылка)
        - Проверяет валидность и срок действия токена
        - Проверяет существование файлов на диске
        - Логирует все попытки доступа
        
    Actions:
        - Загружает метаданные ссылки по токену
        - Проверяет срок действия ссылки
        - Создает ZIP-архив с файлами
        - Логирует скачивание
        - Отправляет архив пользователю
    """
    import zipfile
    import tempfile
    import json
    from datetime import datetime
    from flask import send_file
    
    global REDIS_AVAILABLE
    
    try:
        # Загружаем данные ссылки
        share_data = None
        
        if REDIS_AVAILABLE and redis_client:
            try:
                # Пытаемся загрузить из Redis
                redis_key = f'share_link:{token}'
                redis_data = redis_client.get(redis_key)
                if redis_data:
                    share_data = json.loads(redis_data)
                    logging.info(f'Share link data loaded from Redis: {token}')
            except Exception as e:
                logging.error(f'Error loading share link from Redis: {str(e)}')
        
        if not share_data:
            # Пытаемся загрузить из файловой системы
            share_file = os.path.join('logs', 'share_links', f'{token}.json')
            if os.path.exists(share_file):
                try:
                    with open(share_file, 'r', encoding='utf-8') as f:
                        share_data = json.load(f)
                    logging.info(f'Share link data loaded from file: {token}')
                except Exception as e:
                    logging.error(f'Error loading share link from file: {str(e)}')
        
        if not share_data:
            logging.warning(f'Share link not found: {token} from IP {get_client_ip()}')
            abort(404)
        
        # Проверяем срок действия ссылки
        expires_at = datetime.fromisoformat(share_data['expires_at'])
        if datetime.now() > expires_at:
            logging.warning(f'Expired share link accessed: {token} from IP {get_client_ip()}')
            
            # Удаляем просроченную ссылку
            if REDIS_AVAILABLE and redis_client:
                try:
                    redis_client.delete(f'share_link:{token}')
                except:
                    pass
            
            share_file = os.path.join('logs', 'share_links', f'{token}.json')
            if os.path.exists(share_file):
                try:
                    os.remove(share_file)
                except:
                    pass
            
            abort(410)  # Gone - ресурс больше не доступен
        
        # Получаем информацию о файлах
        images = share_data['images']
        user_email = share_data['user_email']
        
        if not images:
            logging.warning(f'No images in share link: {token} from IP {get_client_ip()}')
            abort(404)
        
        # Создаем временный ZIP-файл
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        successful_files = 0
        failed_files = 0
        
        try:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for image_info in images:
                    try:
                        filename = image_info['filename']
                        original_name = image_info['original_name']
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_email, filename)
                        
                        if not os.path.exists(file_path):
                            logging.warning(f'File not found for shared download: {filename} for token {token}')
                            failed_files += 1
                            continue
                        
                        # Добавляем файл в архив с оригинальным именем
                        zipf.write(file_path, original_name)
                        successful_files += 1
                        
                    except Exception as e:
                        logging.error(f'Error adding file to shared archive: {filename} for token {token}: {str(e)}')
                        failed_files += 1
            
            if successful_files == 0:
                logging.warning(f'No files available for shared download: {token} from IP {get_client_ip()}')
                os.unlink(temp_zip.name)
                abort(404)
            
            # Формируем имя архива
            archive_name = f'shared_images_{token[:8]}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
            
            # Логируем скачивание по ссылке
            log_statistics(
                action_type='shared_download',
                user_email='anonymous',  # Анонимный доступ
                ip_address=get_client_ip(),
                user_agent=request.user_agent.string,
                additional_info=f'Скачивание по ссылке: токен {token[:8]}..., владелец {user_email}, файлов: {successful_files}'
            )
            
            logging.info(f'Shared download completed: token {token}, {successful_files} files, {failed_files} failed, IP {get_client_ip()}')
            
            # Отправляем архив
            return send_file(
                temp_zip.name,
                as_attachment=True,
                download_name=archive_name,
                mimetype='application/zip'
            )
            
        except Exception as e:
            logging.error(f'Error creating shared ZIP archive for token {token}: {str(e)}')
            
            # Удаляем временный файл в случае ошибки
            try:
                os.unlink(temp_zip.name)
            except:
                pass
            
            abort(500)
        
        finally:
            # Планируем удаление временного файла
            try:
                import threading
                def cleanup_temp_file():
                    import time
                    time.sleep(60)  # Ждем минуту перед удалением
                    try:
                        os.unlink(temp_zip.name)
                    except:
                        pass
                
                cleanup_thread = threading.Thread(target=cleanup_temp_file)
                cleanup_thread.daemon = True
                cleanup_thread.start()
            except:
                pass
        
    except Exception as e:
        logging.error(f'Error in shared download for token {token}: {str(e)}')
        abort(500)


@app.route('/db-test')
def db_test_connect():
    """
    Тестирование соединения с базой данных.
    
    Простая функция для проверки работоспособности подключения к БД.
    Используется для диагностики и мониторинга состояния системы.
    
    Returns:
        dict: JSON-ответ с информацией о статусе соединения:
            - status: 'ok' или 'error'
            - message: Описание результата проверки
            
    Usage:
        GET /db-test - возвращает статус подключения к БД
    """
    conn = connect_db()
    if conn:
        close_db(conn)
        return {'status': 'ok', "message": "Соединение с БД установлено"}
    else:
        return {'status': 'error', "message": "Соединение с БД НЕ установлено"}


# Инициализация базы данных при запуске приложения
# Этот блок выполняется один раз при старте Flask-приложения
# и обеспечивает готовность всех компонентов системы к работе
with app.app_context():
    try:
        # Инициализируем схему базы данных
        # Создает все необходимые таблицы и обновляет существующие при необходимости
        ensure_schema()
        logging.info('Database schema initialized successfully')
        
        # Проверяем и удаляем изображения с истекшим сроком хранения
        # Автоматическая очистка при каждом запуске приложения
        # предотвращает накопление устаревших файлов
        try:
            expired_images = get_expired_images()
            for image in expired_images:
                try:
                    image_id = image[0]
                    filename = str(image[1]) if image[1] else ''
                    user_email = str(image[6]) if image[6] else ''
                    
                    # Удаляем физический файл с диска
                    if user_email:
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_email, filename)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logging.info(f'Expired file {filename} deleted for user {user_email}')
                    
                    # Удаляем запись из базы данных
                    delete_image(image_id)
                    logging.info(f'Expired image with ID {image_id} deleted from database')
                except (UnicodeDecodeError, UnicodeError) as ue:
                    logging.warning(f'Unicode error processing expired image {image_id}: {str(ue)}')
                    # Пропускаем проблемную запись и продолжаем
                    continue
                except Exception as ie:
                    logging.error(f'Error processing expired image {image_id}: {str(ie)}')
                    continue
        except Exception as ee:
            logging.error(f'Error getting expired images: {str(ee)}')
        
        logging.info('Database initialization completed successfully')
    except Exception as e:
        logging.error(f'Error initializing database: {str(e)}')


# Запуск Flask-приложения
# host='0.0.0.0' - принимает подключения со всех интерфейсов
# port=5000 - стандартный порт для Flask-разработки
# ============================================================================
# ИНИЦИАЛИЗАЦИЯ ВРЕМЕНИ ЗАПУСКА И GRACEFUL SHUTDOWN
# ============================================================================

# Время запуска приложения для метрик uptime и мониторинга
app.start_time = time.time()
logging.info(f"Application start time recorded: {datetime.fromtimestamp(app.start_time)}")


def cleanup():
    """
    Функция graceful shutdown для корректного завершения приложения.
    
    Выполняет очистку ресурсов при завершении работы приложения:
    - Закрывает все соединения с базой данных
    - Освобождает ресурсы пула соединений
    - Записывает информацию о завершении в лог
    
    Функция автоматически вызывается при:
    - Нормальном завершении программы
    - Получении сигнала SIGTERM
    - Исключениях, приводящих к завершению
    
    Note:
        Функция зарегистрирована через atexit.register()
        для автоматического вызова при завершении.
    """
    try:
        # Вычисляем время работы приложения
        uptime = time.time() - app.start_time
        uptime_str = f"{uptime:.2f} seconds"
        
        logging.info(f"Starting application cleanup. Uptime: {uptime_str}")
        
        # Закрываем все соединения с базой данных
        if 'db_pool' in globals():
            db_pool.close_all_connections()
            logging.info("Database connection pool closed")
        
        # Логируем успешное завершение
        logging.info("Application shutdown completed successfully")
        
    except Exception as e:
        # Логируем ошибки, но не прерываем процесс завершения
        logging.error(f"Error during application cleanup: {e}")
    finally:
        # Финальное сообщение о завершении
        logging.info("Image Hosting application terminated")


# Регистрируем функцию очистки для автоматического вызова при завершении
atexit.register(cleanup)

# ============================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================================================

if __name__ == '__main__':
    """
    Точка входа в приложение при прямом запуске.
    
    Выполняется только при запуске файла напрямую (python app.py),
    но не при импорте как модуля.
    
    Конфигурация запуска:
    - host='0.0.0.0': Принимает подключения со всех сетевых интерфейсов
    - port=5000: Стандартный порт для Flask-разработки
    - threaded=True: Включает многопоточность для обработки запросов
    
    Note:
        В production рекомендуется использовать WSGI-сервер
        (например, Gunicorn) вместо встроенного сервера Flask.
    """
    
    # Логируем информацию о запуске оптимизированной версии
    logging.info("="*60)
    logging.info("Starting Image Hosting v1.2.0-optimized")
    logging.info("="*60)
    
    # Информация о доступности компонентов
    logging.info(f"Redis caching available: {REDIS_AVAILABLE}")
    logging.info(f"Celery async processing available: {CELERY_AVAILABLE}")
    
    # Информация о конфигурации
    logging.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    logging.info(f"Max content length: {app.config['MAX_CONTENT_LENGTH'] / (1024*1024):.1f} MB")
    logging.info(f"Session type: {app.config.get('SESSION_TYPE', 'filesystem')}")
    
    # Информация о сетевых настройках
    logging.info("Server configuration:")
    logging.info("  - Host: 0.0.0.0 (all interfaces)")
    logging.info("  - Port: 5000")
    logging.info("  - Threading: Enabled")
    logging.info("  - Debug mode: Disabled (production)")
    
    logging.info("Application ready to accept connections")
    logging.info("="*60)
    
    # Запуск Flask development server
    # В production следует использовать Gunicorn или другой WSGI-сервер
    try:
        app.run(
            host='0.0.0.0',      # Принимаем соединения со всех интерфейсов
            port=5000,           # Стандартный порт Flask
            threaded=True,       # Многопоточность для параллельной обработки
            debug=False          # Отключаем debug в production
        )
    except KeyboardInterrupt:
        logging.info("Application stopped by user (Ctrl+C)")
    except Exception as e:
        logging.error(f"Application failed to start: {e}")
        raise