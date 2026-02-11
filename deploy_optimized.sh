#!/bin/bash
# ============================================================================
# СКРИПТ АВТОМАТИЧЕСКОГО РАЗВЕРТЫВАНИЯ ОПТИМИЗИРОВАННОЙ СИСТЕМЫ
# ============================================================================
# 
# Этот скрипт выполняет полное развертывание оптимизированной версии
# Image Hosting системы с поддержкой высокой нагрузки.
# 
# Включает:
# - Остановку текущей системы
# - Создание резервной копии
# - Установку новых зависимостей
# - Сборку и запуск оптимизированных контейнеров
# - Проверку состояния системы
# - Опциональный запуск мониторинга
# 
# Использование: ./deploy_optimized.sh
# 
# ============================================================================

set -e  # Остановка при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Функция проверки команд
check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 не установлен. Пожалуйста, установите $1 и повторите попытку."
        exit 1
    fi
}

# Функция ожидания готовности сервиса
wait_for_service() {
    local service_name=$1
    local health_url=$2
    local max_attempts=30
    local attempt=1
    
    log_info "Ожидание готовности $service_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s $health_url > /dev/null 2>&1; then
            log_success "$service_name готов!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log_error "$service_name не готов после $max_attempts попыток"
    return 1
}

# ============================================================================
# ОСНОВНОЙ ПРОЦЕСС РАЗВЕРТЫВАНИЯ
# ============================================================================

log_info "🚀 Начало развертывания оптимизированной Image Hosting системы..."
echo "============================================================================"

# 1. Проверка необходимых команд
log_info "📋 Проверка необходимых инструментов..."
check_command "docker"
check_command "docker-compose"
check_command "curl"
log_success "Все необходимые инструменты установлены"

# 2. Остановка текущей системы
log_info "📦 Остановка текущих сервисов..."
if docker-compose ps | grep -q "Up"; then
    docker-compose down
    log_success "Текущие сервисы остановлены"
else
    log_info "Сервисы уже остановлены"
fi

# 3. Создание резервной копии
log_info "💾 Создание резервной копии..."
BACKUP_DIR="../backup_$(date +%Y%m%d_%H%M%S)"
cp -r . "$BACKUP_DIR"
log_success "Резервная копия создана: $BACKUP_DIR"

# 4. Проверка .env файла
log_info "🔧 Проверка конфигурации..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        log_warning "Файл .env не найден. Копирование из .env.example"
        cp .env.example .env
        log_warning "Пожалуйста, отредактируйте .env файл с вашими настройками"
        read -p "Нажмите Enter после редактирования .env файла..."
    else
        log_error "Файл .env не найден и .env.example отсутствует"
        exit 1
    fi
fi
log_success "Конфигурация проверена"

# 5. Установка новых зависимостей (если Python окружение активно)
if [ -n "$VIRTUAL_ENV" ]; then
    log_info "📚 Установка новых зависимостей..."
    pip install -r requirements.txt
    log_success "Зависимости установлены"
else
    log_warning "Виртуальное окружение Python не активно. Пропуск установки зависимостей."
fi

# 6. Создание необходимых директорий
log_info "📁 Создание необходимых директорий..."
mkdir -p monitoring/prometheus
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/grafana/datasources
mkdir -p images
mkdir -p logs
mkdir -p backups
log_success "Директории созданы"

# 7. Сборка новых образов
log_info "🔨 Сборка Docker образов..."
docker-compose -f docker-compose.optimized.yml build --no-cache
log_success "Образы собраны"

# 8. Запуск оптимизированной системы
log_info "🚀 Запуск оптимизированной системы..."
docker-compose -f docker-compose.optimized.yml up -d
log_success "Система запущена"

# 9. Ожидание готовности сервисов
log_info "⏳ Ожидание готовности сервисов..."
sleep 10

# Проверка состояния контейнеров
log_info "🔍 Проверка состояния контейнеров..."
docker-compose -f docker-compose.optimized.yml ps

# 10. Проверка health check
log_info "❤️ Проверка health check..."
if wait_for_service "Application" "http://localhost/health"; then
    log_success "Приложение готово к работе!"
else
    log_error "Приложение не прошло health check"
    log_info "Проверка логов..."
    docker-compose -f docker-compose.optimized.yml logs --tail=20
    exit 1
fi

# 11. Применение оптимизаций базы данных
log_info "🗄️ Применение оптимизаций базы данных..."
if [ -f "database_optimization.sql" ]; then
    # Ожидание готовности базы данных
    sleep 5
    
    # Применение SQL оптимизаций
    if docker-compose -f docker-compose.optimized.yml exec -T db psql -U "${DB_USER:-postgres}" -d "${DB_NAME:-image_hosting_db}" -f - < database_optimization.sql; then
        log_success "Оптимизации базы данных применены"
    else
        log_warning "Не удалось применить оптимизации БД. Продолжаем без них."
    fi
else
    log_warning "Файл database_optimization.sql не найден"
fi

# 12. Проверка метрик
log_info "📊 Проверка метрик..."
if curl -f -s http://localhost/metrics > /dev/null; then
    log_success "Метрики доступны"
else
    log_warning "Метрики недоступны"
fi

# 13. Опциональный запуск мониторинга
echo ""
read -p "🔍 Запустить мониторинг (Prometheus/Grafana)? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "📊 Запуск системы мониторинга..."
    
    # Создание конфигурации Prometheus
    cat > monitoring/prometheus/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'image-hosting'
    static_configs:
      - targets: ['nginx:80']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx:8080']
    metrics_path: '/nginx_status'
    scrape_interval: 30s
EOF

    # Создание docker-compose для мониторинга
    cat > docker-compose.monitoring.yml << EOF
services:
  prometheus:
    image: prom/prometheus:v2.45.0
    container_name: image_hosting_prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    restart: unless-stopped
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:10.0.0
    container_name: image_hosting_grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
    restart: unless-stopped
    networks:
      - monitoring

volumes:
  prometheus_data:
  grafana_data:

networks:
  monitoring:
    driver: bridge
EOF

    docker-compose -f docker-compose.monitoring.yml up -d
    
    log_success "Мониторинг запущен!"
    echo "📊 Доступные сервисы мониторинга:"
    echo "   Prometheus: http://localhost:9090"
    echo "   Grafana: http://localhost:3000 (admin/admin123)"
fi

# ============================================================================
# ЗАВЕРШЕНИЕ РАЗВЕРТЫВАНИЯ
# ============================================================================

echo ""
echo "============================================================================"
log_success "✅ Развертывание оптимизированной системы завершено!"
echo ""
echo "🌐 Доступные сервисы:"
echo "   Приложение: http://localhost"
echo "   Health check: http://localhost/health"
echo "   Метрики: http://localhost/metrics"
echo "   pgAdmin: http://localhost:5050"
echo ""
echo "📊 Информация о системе:"
echo "   Экземпляры Flask: 4"
echo "   Балансировка нагрузки: Nginx"
echo "   Кэширование: Redis"
echo "   Пул соединений БД: 5-20"
echo ""
echo "🔧 Полезные команды:"
echo "   Просмотр логов: docker-compose -f docker-compose.optimized.yml logs -f"
echo "   Статус сервисов: docker-compose -f docker-compose.optimized.yml ps"
echo "   Остановка: docker-compose -f docker-compose.optimized.yml down"
echo "   Мониторинг ресурсов: docker stats"
echo ""
log_success "🚀 Система готова к обработке высокой нагрузки!"
echo "============================================================================"