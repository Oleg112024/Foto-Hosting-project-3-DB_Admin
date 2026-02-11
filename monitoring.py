# -*- coding: utf-8 -*-
"""
Система мониторинга производительности Image Hosting.

Обеспечивает:
- Сбор метрик производительности
- Мониторинг состояния системы
- Алерты при критических состояниях
- Интеграция с Prometheus/Grafana

Автор: Image Hosting Project
Версия: 2.0 (Monitoring)
"""

import time
import psutil
import logging
from datetime import datetime
from flask import jsonify
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest
except ImportError:
    # Fallback если prometheus_client не установлен
    class MockMetric:
        def __init__(self, *args, **kwargs):
            pass
        def set(self, value):
            pass
        def inc(self, *args, **kwargs):
            pass
        def observe(self, value):
            pass
    
    Counter = Histogram = Gauge = MockMetric
    def generate_latest():
        return "# Prometheus client not installed"

# Временно отключен из-за проблем с кодировкой
# from db_pool import db_pool, get_pool_metrics

# ============================================================================
# PROMETHEUS МЕТРИКИ
# ============================================================================

# Счетчики запросов
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Время обработки запросов
request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Метрики базы данных
db_connections_active = Gauge(
    'db_connections_active',
    'Active database connections'
)

db_connections_total = Gauge(
    'db_connections_total',
    'Total database connections in pool'
)

db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['query_type']
)

# Системные метрики
system_cpu_usage = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

system_memory_usage = Gauge(
    'system_memory_usage_percent',
    'System memory usage percentage'
)

system_disk_usage = Gauge(
    'system_disk_usage_percent',
    'System disk usage percentage'
)

# Метрики приложения
active_users = Gauge(
    'active_users_total',
    'Number of active users'
)

file_uploads_total = Counter(
    'file_uploads_total',
    'Total file uploads',
    ['status']
)

file_downloads_total = Counter(
    'file_downloads_total',
    'Total file downloads'
)

# ============================================================================
# КЛАСС МОНИТОРИНГА
# ============================================================================

class PerformanceMonitor:
    """
    Класс для мониторинга производительности системы.
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.alert_thresholds = {
            'cpu_percent': 90,
            'memory_percent': 90,
            'disk_percent': 95,
            'db_connections_percent': 90
        }
    
    def collect_system_metrics(self):
        """
        Сбор системных метрик.
        
        Returns:
            dict: Системные метрики
        """
        try:
            # CPU метрики
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Память
            memory = psutil.virtual_memory()
            
            # Диск
            try:
                disk = psutil.disk_usage('/')
            except:
                # Для Windows используем C:\
                disk = psutil.disk_usage('C:\\')
            
            # Сеть
            network = psutil.net_io_counters()
            
            # Обновляем Prometheus метрики
            system_cpu_usage.set(cpu_percent)
            system_memory_usage.set(memory.percent)
            system_disk_usage.set(disk.percent)
            
            metrics = {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                }
            }
            
            # Проверяем пороги для алертов
            self._check_system_alerts(metrics)
            
            return metrics
            
        except Exception as e:
            logging.error(f"Error collecting system metrics: {e}")
            return {}
    
    def collect_db_metrics(self):
        """
        Сбор метрик базы данных.
        
        Returns:
            dict: Метрики базы данных
        """
        try:
            # Временно отключено из-за проблем с db_pool
            # pool_metrics = get_pool_metrics()
            
            # Возвращаем базовые метрики без пула соединений
            db_connections_active.set(0)
            db_connections_total.set(0)
            
            return {
                'health': True,
                'pool_stats': {
                    'active_connections': 0,
                    'pool_size': 0,
                    'note': 'DB pool temporarily disabled'
                },
                'connection_usage_percent': 0
            }
                
        except Exception as e:
            logging.error(f"Error collecting database metrics: {e}")
            return {'health': False, 'error': str(e)}
    
    def collect_app_metrics(self):
        """
        Сбор метрик приложения.
        
        Returns:
            dict: Метрики приложения
        """
        try:
            uptime = time.time() - self.start_time
            
            # Здесь можно добавить сбор специфичных метрик приложения
            # Например, количество активных сессий, загруженных файлов и т.д.
            
            return {
                'uptime_seconds': uptime,
                'version': '1.2.0-optimized',
                'start_time': self.start_time
            }
            
        except Exception as e:
            logging.error(f"Error collecting app metrics: {e}")
            return {}
    
    def _check_system_alerts(self, metrics):
        """
        Проверка системных алертов.
        
        Args:
            metrics (dict): Системные метрики
        """
        try:
            # Проверка CPU
            if metrics['cpu']['percent'] > self.alert_thresholds['cpu_percent']:
                logging.warning(f"High CPU usage: {metrics['cpu']['percent']}%")
            
            # Проверка памяти
            if metrics['memory']['percent'] > self.alert_thresholds['memory_percent']:
                logging.warning(f"High memory usage: {metrics['memory']['percent']}%")
            
            # Проверка диска
            if metrics['disk']['percent'] > self.alert_thresholds['disk_percent']:
                logging.critical(f"High disk usage: {metrics['disk']['percent']}%")
            
        except Exception as e:
            logging.error(f"Error checking alerts: {e}")
    
    def get_comprehensive_metrics(self):
        """
        Получение всех метрик системы.
        
        Returns:
            dict: Полный набор метрик
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'system': self.collect_system_metrics(),
            'database': self.collect_db_metrics(),
            'application': self.collect_app_metrics()
        }

# Глобальный экземпляр монитора
performance_monitor = PerformanceMonitor()

# ============================================================================
# ФУНКЦИИ ДЛЯ ИНТЕГРАЦИИ С FLASK
# ============================================================================

def track_request(method, endpoint, status_code, duration):
    """
    Отслеживание HTTP запроса.
    
    Args:
        method (str): HTTP метод
        endpoint (str): Конечная точка
        status_code (int): Код статуса
        duration (float): Время выполнения в секундах
    """
    try:
        request_count.labels(method=method, endpoint=endpoint, status=status_code).inc()
        request_duration.labels(method=method, endpoint=endpoint).observe(duration)
    except Exception as e:
        logging.error(f"Error tracking request: {e}")

def track_file_upload(status):
    """
    Отслеживание загрузки файла.
    
    Args:
        status (str): Статус загрузки (success/error)
    """
    try:
        file_uploads_total.labels(status=status).inc()
    except Exception as e:
        logging.error(f"Error tracking file upload: {e}")

def track_file_download():
    """
    Отслеживание скачивания файла.
    """
    try:
        file_downloads_total.inc()
    except Exception as e:
        logging.error(f"Error tracking file download: {e}")

def get_prometheus_metrics():
    """
    Получение метрик в формате Prometheus.
    
    Returns:
        str: Метрики в формате Prometheus
    """
    try:
        return generate_latest()
    except Exception as e:
        logging.error(f"Error generating Prometheus metrics: {e}")
        return "# Error generating metrics"