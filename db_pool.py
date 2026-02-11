# -*- coding: utf-8 -*-
"""
Модуль пула соединений PostgreSQL для высокой производительности.

Этот модуль заменяет простые соединения на пул соединений,
что критично важно для обработки высокой нагрузки.

Особенности:
- ThreadedConnectionPool для многопоточности
- Автоматическое управление соединениями
- Мониторинг состояния пула
- Graceful degradation при проблемах

Автор: Image Hosting Project
Версия: 2.0 (Optimized)
"""

import os
import logging
import threading
import time
from contextlib import contextmanager
from psycopg2 import pool, OperationalError
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# ============================================================================
# КОНФИГУРАЦИЯ ПУЛА СОЕДИНЕНИЙ
# ============================================================================

# Параметры пула из переменных окружения
DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "5"))    # Минимум соединений
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "20"))   # Максимум соединений

# Параметры подключения
DB_NAME = os.getenv("DB_NAME", "image_hosting_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

# ============================================================================
# КЛАСС УПРАВЛЕНИЯ ПУЛОМ СОЕДИНЕНИЙ
# ============================================================================

class DatabasePool:
    """
    Класс для управления пулом соединений PostgreSQL.
    
    Обеспечивает:
    - Эффективное переиспользование соединений
    - Автоматическое восстановление при сбоях
    - Мониторинг состояния пула
    - Thread-safe операции
    """
    
    def __init__(self):
        self._pool = None
        self._lock = threading.Lock()
        self._stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'pool_exhausted': 0
        }
        self._initialize_pool()
    
    def _initialize_pool(self):
        """
        Инициализация пула соединений с обработкой ошибок.
        """
        try:
            self._pool = pool.ThreadedConnectionPool(
                minconn=DB_POOL_MIN,
                maxconn=DB_POOL_MAX,
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT,
                # Дополнительные параметры для производительности
                cursor_factory=RealDictCursor,
                # Настройки соединения
                connect_timeout=10,
                # Параметры для поддержания соединений
                keepalives_idle=600,
                keepalives_interval=30,
                keepalives_count=3
            )
            logging.info(f"Database pool initialized: {DB_POOL_MIN}-{DB_POOL_MAX} connections")
            
        except Exception as e:
            logging.error(f"Failed to initialize database pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Context manager для получения соединения из пула.
        
        Использование:
            with db_pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users")
                result = cursor.fetchall()
        
        Yields:
            psycopg2.connection: Соединение из пула
        """
        conn = None
        try:
            # Получаем соединение из пула
            conn = self._pool.getconn()
            if conn:
                # Проверяем состояние соединения
                if conn.closed:
                    # Соединение закрыто, получаем новое
                    self._pool.putconn(conn, close=True)
                    conn = self._pool.getconn()
                
                self._stats['active_connections'] += 1
                yield conn
            else:
                self._stats['pool_exhausted'] += 1
                raise Exception("Pool exhausted: no available connections")
                
        except pool.PoolError as e:
            self._stats['failed_connections'] += 1
            logging.error(f"Pool error: {e}")
            raise
            
        except Exception as e:
            self._stats['failed_connections'] += 1
            logging.error(f"Database connection error: {e}")
            raise
            
        finally:
            # Возвращаем соединение в пул
            if conn:
                try:
                    self._pool.putconn(conn)
                    self._stats['active_connections'] -= 1
                except Exception as e:
                    logging.error(f"Error returning connection to pool: {e}")
    
    def get_stats(self):
        """
        Получение статистики пула соединений.
        
        Returns:
            dict: Статистика использования пула
        """
        if self._pool:
            # Добавляем информацию о текущем состоянии пула
            self._stats.update({
                'pool_size': len(self._pool._pool),
                'available_connections': len([c for c in self._pool._pool if not c.closed])
            })
        
        return self._stats.copy()
    
    def health_check(self):
        """
        Проверка здоровья пула соединений.
        
        Returns:
            bool: True если пул работает нормально
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None
        except Exception as e:
            logging.error(f"Pool health check failed: {e}")
            return False
    
    def close_all_connections(self):
        """
        Закрытие всех соединений в пуле.
        Используется при завершении приложения.
        """
        if self._pool:
            self._pool.closeall()
            logging.info("All database connections closed")

# ============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ПУЛА
# ============================================================================

# Создаем единственный экземпляр пула для всего приложения
db_pool = DatabasePool()

# ============================================================================
# ФУНКЦИИ СОВМЕСТИМОСТИ С СУЩЕСТВУЮЩИМ КОДОМ
# ============================================================================

def connect_db():
    """
    Функция совместимости для существующего кода.
    
    ВНИМАНИЕ: Эта функция оставлена для совместимости,
    но рекомендуется использовать db_pool.get_connection()
    
    Returns:
        psycopg2.connection: Соединение из пула
    """
    logging.warning("Using deprecated connect_db(). Use db_pool.get_connection() instead.")
    return db_pool._pool.getconn()

def close_db(conn):
    """
    Функция совместимости для возврата соединения в пул.
    
    Args:
        conn: Соединение для возврата в пул
    """
    if conn:
        db_pool._pool.putconn(conn)

# ============================================================================
# МОНИТОРИНГ И МЕТРИКИ
# ============================================================================

def get_pool_metrics():
    """
    Получение метрик пула для мониторинга.
    
    Returns:
        dict: Детальные метрики пула соединений
    """
    stats = db_pool.get_stats()
    health = db_pool.health_check()
    
    return {
        'pool_health': health,
        'pool_stats': stats,
        'timestamp': time.time()
    }