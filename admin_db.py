# ============================================================================
# МОДУЛЬ АДМИНИСТРАТИВНЫХ ФУНКЦИЙ БАЗЫ ДАННЫХ
# ============================================================================
# 
# Этот модуль содержит специализированные функции для работы с базой данных
# в контексте административной панели. Обеспечивает:
# 
# - Сбор и анализ статистики использования системы
# - Расчет метрик производительности и активности
# - Фильтрацию и пагинацию больших объемов данных
# - Логирование действий пользователей
# - Мониторинг использования ресурсов
# 
# Все функции оптимизированы для работы с большими объемами данных
# и включают обработку ошибок для обеспечения стабильности системы.
# 
# ============================================================================

# ============================================================================
# ИМПОРТ НЕОБХОДИМЫХ МОДУЛЕЙ
# ============================================================================

import os  # Работа с файловой системой для расчета размеров файлов
from psycopg2.extras import RealDictCursor  # Курсор для получения результатов в виде словарей
from db import connect_db, close_db, create_table_statistics  # Основные функции работы с БД


# ============================================================================
# ФУНКЦИИ СБОРА МЕТРИК И СТАТИСТИКИ
# ============================================================================

def get_total_downloads():
    """
    Получает общее количество скачиваний файлов из системы.
    
    Эта функция анализирует таблицу статистики для подсчета всех действий
    типа 'download', которые регистрируются при каждом скачивании файла
    пользователем через кнопку "Скачать" в интерфейсе.
    
    Функция используется в административной панели для:
    - Отображения общей популярности контента
    - Мониторинга активности пользователей
    - Анализа нагрузки на сервер
    - Планирования ресурсов хранения
    
    Database Query:
        SELECT COUNT(*) FROM statistics WHERE action_type = 'download'
    
    Returns:
        int: Общее количество скачиваний файлов
             Возвращает 0 в случае ошибки подключения к БД
    
    Error Handling:
        - Обрабатывает ошибки подключения к базе данных
        - Логирует ошибки в консоль для отладки
        - Возвращает безопасное значение (0) при любых проблемах
    
    Performance Notes:
        - Использует COUNT(*) для эффективного подсчета
        - Индекс на поле action_type ускоряет выполнение
        - Минимальное использование памяти
    """
    try:
        # Устанавливаем соединение с базой данных
        conn = connect_db()
        cur = conn.cursor()
        
        # Выполняем оптимизированный запрос для подсчета скачиваний
        # Фильтруем только записи с типом действия 'download'
        cur.execute("SELECT COUNT(*) FROM statistics WHERE action_type = 'download'")
        total = cur.fetchone()[0]
        
        # Освобождаем ресурсы базы данных
        cur.close()
        close_db(conn)
        
        return total
    except Exception as e:
        # Логируем ошибку для диагностики, но не прерываем работу приложения
        print(f'Error getting total downloads: {str(e)}')
        return 0  # Возвращаем безопасное значение по умолчанию


def get_total_files_size():
    """
    Вычисляет общий размер всех файлов, хранящихся в системе.
    
    Эта функция выполняет комплексный анализ дискового пространства,
    используемого приложением. Сначала получает список всех файлов
    из базы данных, затем проверяет их физическое присутствие на диске
    и суммирует их размеры.
    
    Процесс вычисления:
    1. Извлекает список всех файлов и их владельцев из таблицы images
    2. Для каждого файла строит путь в файловой системе
    3. Проверяет существование файла на диске
    4. Суммирует размеры всех существующих файлов
    
    Используется для:
    - Мониторинга использования дискового пространства
    - Планирования расширения хранилища
    - Анализа роста объема данных
    - Отчетности по ресурсам системы
    
    File Structure:
        {UPLOAD_FOLDER}/{user_email}/{filename}
        Например: images/user@example.com/photo.jpg
    
    Returns:
        int: Общий размер всех файлов в байтах
             Возвращает 0 в случае ошибки или отсутствия файлов
    
    Error Handling:
        - Обрабатывает ошибки доступа к файловой системе
        - Пропускает несуществующие файлы без ошибок
        - Логирует проблемы для диагностики
        - Возвращает частичный результат при частичных ошибках
    
    Performance Considerations:
        - Может быть медленной при большом количестве файлов
        - Выполняет системные вызовы для каждого файла
        - Рекомендуется кэширование результата
        - Возможна оптимизация через асинхронное выполнение
    """
    try:
        # Подключаемся к базе данных для получения списка файлов
        conn = connect_db()
        cur = conn.cursor()
        
        # Получаем все зарегистрированные файлы с информацией о владельцах
        # Эта информация необходима для построения правильных путей к файлам
        cur.execute("SELECT filename, user_email FROM images")
        files = cur.fetchall()
        
        # Инициализируем счетчик общего размера
        total_size = 0
        
        # Получаем базовую папку для загрузок из переменных окружения
        # Используем 'images' как значение по умолчанию для совместимости
        upload_folder = os.getenv('UPLOAD_FOLDER', 'images')
        
        # Итерируем по всем файлам для подсчета их размеров
        for filename, user_email in files:
            # Строим полный путь к файлу в структуре папок пользователей
            # Каждый пользователь имеет свою подпапку для изоляции файлов
            user_folder = os.path.join(upload_folder, user_email)
            file_path = os.path.join(user_folder, filename)
            
            # Проверяем физическое существование файла перед получением размера
            # Это защищает от ошибок при несинхронизированности БД и файловой системы
            if os.path.exists(file_path):
                # Добавляем размер файла к общему счетчику
                total_size += os.path.getsize(file_path)
        
        # Освобождаем ресурсы базы данных
        cur.close()
        close_db(conn)
        
        return total_size
    except Exception as e:
        # Логируем ошибку с подробным описанием для диагностики
        print(f'Error calculating total files size: {str(e)}')
        return 0  # Возвращаем безопасное значение при любых ошибках


# ============================================================================
# ФУНКЦИИ ФИЛЬТРАЦИИ И ПАГИНАЦИИ ДАННЫХ
# ============================================================================

def get_statistics_with_filters(action_type=None, user_email=None, limit=50, offset=0):
    """
    Получает статистику действий пользователей с расширенной фильтрацией и пагинацией.
    
    Эта функция является основным инструментом для извлечения и анализа
    данных статистики в административной панели. Поддерживает гибкую
    фильтрацию по различным критериям и эффективную пагинацию для
    работы с большими объемами данных.
    
    Функциональность:
    - Динамическое построение SQL запросов на основе переданных фильтров
    - Безопасная параметризация запросов для предотвращения SQL-инъекций
    - Оптимизированная пагинация с использованием LIMIT/OFFSET
    - Сортировка по времени (новые записи первыми)
    - Возврат данных в удобном формате словарей
    
    Use Cases:
    - Просмотр всех действий конкретного пользователя
    - Анализ определенного типа активности (загрузки, просмотры, скачивания)
    - Комбинированная фильтрация для детального анализа
    - Постраничный просмотр больших журналов активности
    
    Args:
        action_type (str, optional): Тип действия для фильтрации
                                   Примеры: 'upload', 'download', 'view', 'login'
                                   None = без фильтрации по типу действия
        user_email (str, optional): Email пользователя для фильтрации
                                   None = показать действия всех пользователей
        limit (int): Максимальное количество записей для возврата
                    По умолчанию 50 - оптимальное значение для UI
        offset (int): Смещение для пагинации (количество пропускаемых записей)
                     Используется для реализации постраничной навигации
    
    Returns:
        list: Список словарей с записями статистики, отсортированный по времени
              Каждый словарь содержит поля:
              - action_type: тип действия
              - user_email: email пользователя
              - ip_address: IP-адрес пользователя
              - timestamp: время выполнения действия
              - additional_info: дополнительная информация
              Возвращает пустой список в случае ошибки
    
    Database Query Structure:
        SELECT action_type, user_email, ip_address, timestamp, additional_info 
        FROM statistics 
        [WHERE conditions] 
        ORDER BY timestamp DESC 
        LIMIT limit OFFSET offset
    
    Security Features:
        - Использует параметризованные запросы для предотвращения SQL-инъекций
        - Валидация входных параметров
        - Безопасная обработка пользовательского ввода
    
    Performance Optimizations:
        - Индекс на поле timestamp для быстрой сортировки
        - Индексы на поля action_type и user_email для фильтрации
        - LIMIT предотвращает загрузку избыточных данных
        - RealDictCursor для эффективного преобразования результатов
    """
    try:
        # Устанавливаем соединение с базой данных
        conn = connect_db()
        # Используем RealDictCursor для получения результатов в виде словарей
        # Это упрощает работу с данными в шаблонах и API
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Строим базовый SQL запрос с необходимыми полями
        # Выбираем только нужные поля для оптимизации производительности
        query = "SELECT action_type, user_email, ip_address, timestamp, additional_info FROM statistics"
        params = []      # Список параметров для безопасного выполнения запроса
        conditions = []  # Список условий WHERE для динамического построения запроса
        
        # ====================================================================
        # ДИНАМИЧЕСКОЕ ПОСТРОЕНИЕ УСЛОВИЙ ФИЛЬТРАЦИИ
        # ====================================================================
        
        # Добавляем фильтр по типу действия, если указан
        if action_type:
            conditions.append("action_type = %s")
            params.append(action_type)
        
        # Добавляем фильтр по пользователю, если указан
        if user_email:
            # Специальная обработка для фильтрации анонимных пользователей
            if user_email == 'Гость':
                conditions.append("user_email IS NULL")
            # Специальная обработка для фильтрации активных пользователей
            elif user_email == 'ACTIVE_USERS':
                conditions.append("user_email IS NOT NULL AND user_email NOT LIKE '%example.com%' AND LOWER(user_email) NOT LIKE '%admin%'")
            # Специальная обработка для кастомного списка пользователей
            elif user_email.startswith('CUSTOM_LIST:'):
                user_list = [u.strip() for u in user_email[12:].split(',') if u.strip()]
                print(f"DEBUG: CUSTOM_LIST user_list = {user_list}")  # Отладочная информация
                if user_list:
                    placeholders = ','.join(['%s'] * len(user_list))
                    conditions.append(f"user_email IN ({placeholders})")
                    params.extend(user_list)
                    print(f"DEBUG: SQL condition = user_email IN ({placeholders}), params = {user_list}")  # Отладочная информация
            else:
                conditions.append("user_email = %s")
                params.append(user_email)
        
        # Объединяем все условия в WHERE клаузулу, если есть фильтры
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # ====================================================================
        # ДОБАВЛЕНИЕ СОРТИРОВКИ И ПАГИНАЦИИ
        # ====================================================================
        
        # Сортируем по времени в убывающем порядке (новые записи первыми)
        # Добавляем пагинацию для эффективной работы с большими объемами данных
        query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        # Выполняем построенный запрос с параметрами
        cur.execute(query, params)
        statistics = cur.fetchall()
        
        # Освобождаем ресурсы базы данных
        cur.close()
        close_db(conn)
        
        return statistics
    except Exception as e:
        # Логируем ошибку с контекстной информацией для диагностики
        print(f'Error getting filtered statistics: {str(e)}')
        return []  # Возвращаем пустой список для безопасного продолжения работы


def get_statistics_count(action_type=None, user_email=None):
    """
    Получает общее количество записей статистики с учетом фильтров.
    
    Args:
        action_type (str, optional): Тип действия для фильтрации
        user_email (str, optional): Email пользователя для фильтрации
    
    Returns:
        int: Общее количество записей
    """
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Базовый запрос
        query = "SELECT COUNT(*) FROM statistics"
        params = []
        conditions = []
        
        # Добавляем фильтры
        if action_type:
            conditions.append("action_type = %s")
            params.append(action_type)
        
        if user_email:
            # Специальная обработка для подсчета анонимных пользователей
            if user_email == 'Гость':
                conditions.append("user_email IS NULL")
            # Специальная обработка для подсчета активных пользователей
            elif user_email == 'ACTIVE_USERS':
                conditions.append("user_email IS NOT NULL AND user_email NOT LIKE '%example.com%' AND LOWER(user_email) NOT LIKE '%admin%'")
            # Специальная обработка для подсчета кастомного списка пользователей
            elif user_email.startswith('CUSTOM_LIST:'):
                user_list = [u.strip() for u in user_email[12:].split(',') if u.strip()]
                if user_list:
                    placeholders = ','.join(['%s'] * len(user_list))
                    conditions.append(f"user_email IN ({placeholders})")
                    params.extend(user_list)
            else:
                conditions.append("user_email = %s")
                params.append(user_email)
        
        # Добавляем условия к запросу
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        cur.execute(query, params)
        count = cur.fetchone()[0]
        
        cur.close()
        close_db(conn)
        
        return count
    except Exception as e:
        print(f'Error getting statistics count: {str(e)}')
        return 0


def get_unique_action_types():
    """
    Получает список уникальных типов действий из статистики.
    
    Returns:
        list: Список уникальных типов действий
    """
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        cur.execute("SELECT DISTINCT action_type FROM statistics ORDER BY action_type")
        action_types = [row[0] for row in cur.fetchall()]
        
        cur.close()
        close_db(conn)
        
        return action_types
    except Exception as e:
        print(f'Error getting unique action types: {str(e)}')
        return []


def get_unique_users():
    """
    Получает список уникальных пользователей из статистики.
    
    Returns:
        list: Список уникальных email пользователей
    """
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        cur.execute("SELECT DISTINCT user_email FROM statistics WHERE user_email IS NOT NULL ORDER BY user_email")
        users = [row[0] for row in cur.fetchall()]
        
        cur.close()
        close_db(conn)
        
        return users
    except Exception as e:
        print(f'Error getting unique users: {str(e)}')
        return []


def log_statistics(action_type, user_email=None, file_id=None, ip_address=None, user_agent=None, additional_info=None):
    """
    Записывает статистику действий пользователей.
    
    Args:
        action_type (str): Тип действия (например, 'upload', 'download', 'view')
        user_email (str, optional): Email пользователя
        file_id (int, optional): ID файла
        ip_address (str, optional): IP-адрес пользователя
        user_agent (str, optional): User-Agent браузера
        additional_info (str, optional): Дополнительная информация
    
    Returns:
        bool: True если запись успешна, False в противном случае
    """
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        # Проверяем существование пользователя, если user_email указан
        if user_email:
            cur.execute("SELECT email FROM users WHERE email = %s", (user_email,))
            if not cur.fetchone():
                # Если пользователь не найден, записываем статистику без email
                user_email = None
        
        cur.execute("""
        INSERT INTO statistics (action_type, user_email, file_id, ip_address, user_agent, additional_info)
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (action_type, user_email, file_id, ip_address, user_agent, additional_info))
        
        conn.commit()
        cur.close()
        close_db(conn)
        
        return True
    except Exception as e:
        print(f'Error logging statistics: {str(e)}')
        return False


def get_statistics(action_type=None, user_email=None, limit=100, offset=0):
    """
    Получает статистику действий пользователей с фильтрацией.
    
    Args:
        action_type (str, optional): Тип действия для фильтрации
        user_email (str, optional): Email пользователя для фильтрации
        limit (int): Максимальное количество записей
        offset (int): Смещение для пагинации
    
    Returns:
        list: Список записей статистики
    """
    try:
        conn = connect_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT * FROM statistics"
        params = []
        conditions = []
        
        if action_type:
            conditions.append("action_type = %s")
            params.append(action_type)
        
        if user_email:
            conditions.append("user_email = %s")
            params.append(user_email)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        statistics = cur.fetchall()
        
        cur.close()
        close_db(conn)
        
        return statistics
    except Exception as e:
        print(f'Error getting statistics: {str(e)}')
        return []


def get_statistics_summary():
    """
    Получает сводную статистику по типам действий.
    
    Returns:
        list: Список кортежей (action_type, count) отсортированный по убыванию количества
    """
    try:
        conn = connect_db()
        cur = conn.cursor()
        
        query = "SELECT action_type, COUNT(*) FROM statistics GROUP BY action_type ORDER BY COUNT(*) DESC"
        cur.execute(query)
        summary = cur.fetchall()
        
        cur.close()
        close_db(conn)
        
        return summary
    except Exception as e:
        print(f'Error getting statistics summary: {str(e)}')
        return []