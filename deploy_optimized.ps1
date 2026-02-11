# ============================================================================
# СКРИПТ АВТОМАТИЧЕСКОГО РАЗВЕРТЫВАНИЯ ОПТИМИЗИРОВАННОЙ СИСТЕМЫ (PowerShell)
# ============================================================================

$ErrorActionPreference = "Stop"

# Функции для цветного вывода
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Функция проверки команд
function Test-Command {
    param([string]$CommandName)
    
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        Write-Error "$CommandName не установлен. Пожалуйста, установите $CommandName и повторите попытку."
        exit 1
    }
}

# Функция ожидания готовности сервиса
function Wait-ForService {
    param(
        [string]$ServiceName,
        [string]$HealthUrl,
        [int]$MaxAttempts = 30
    )
    
    Write-Info "Ожидание готовности $ServiceName..."
    
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Success "$ServiceName готов!"
                return $true
            }
        }
        catch {
            # Игнорируем ошибки и продолжаем попытки
        }
        
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
    
    Write-Error "$ServiceName не готов после $MaxAttempts попыток"
    return $false
}

# ============================================================================
# ОСНОВНОЙ ПРОЦЕСС РАЗВЕРТЫВАНИЯ
# ============================================================================

Write-Info "Начало развертывания оптимизированной Image Hosting системы..."
Write-Host "============================================================================"

try {
    # 1. Проверка необходимых команд
    Write-Info "Проверка необходимых инструментов..."
    Test-Command "docker"
    Test-Command "docker-compose"
    Write-Success "Все необходимые инструменты установлены"

    # 2. Остановка текущей системы
    Write-Info "Остановка текущих сервисов..."
    try {
        docker-compose down
        Write-Success "Текущие сервисы остановлены"
    }
    catch {
        Write-Info "Сервисы уже остановлены"
    }

    # 3. Создание резервной копии
    Write-Info "Создание резервной копии..."
    $backupDir = "..\backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item -Path "." -Destination $backupDir -Recurse -Force
    Write-Success "Резервная копия создана: $backupDir"

    # 4. Проверка .env файла
    Write-Info "Проверка конфигурации..."
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Write-Warning "Файл .env не найден. Копирование из .env.example"
            Copy-Item ".env.example" ".env"
            Write-Warning "Пожалуйста, отредактируйте .env файл с вашими настройками"
            Read-Host "Нажмите Enter после редактирования .env файла"
        }
        else {
            Write-Error "Файл .env не найден и .env.example отсутствует"
            exit 1
        }
    }
    Write-Success "Конфигурация проверена"

    # 5. Создание необходимых директорий
    Write-Info "Создание необходимых директорий..."
    $directories = @(
        "monitoring\prometheus",
        "monitoring\grafana\dashboards",
        "monitoring\grafana\datasources",
        "images",
        "logs",
        "backups"
    )
    
    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    Write-Success "Директории созданы"

    # 6. Сборка новых образов
    Write-Info "Сборка Docker образов..."
    docker-compose -f docker-compose.optimized.yml build --no-cache
    Write-Success "Образы собраны"

    # 7. Запуск оптимизированной системы
    Write-Info "Запуск оптимизированной системы..."
    docker-compose -f docker-compose.optimized.yml up -d
    Write-Success "Система запущена"

    # 8. Ожидание готовности сервисов
    Write-Info "Ожидание готовности сервисов..."
    Start-Sleep -Seconds 15

    # Проверка состояния контейнеров
    Write-Info "Проверка состояния контейнеров..."
    docker-compose -f docker-compose.optimized.yml ps

    # 9. Проверка health check
    Write-Info "Проверка health check..."
    if (Wait-ForService "Application" "http://localhost/health") {
        Write-Success "Приложение готово к работе!"
    }
    else {
        Write-Error "Приложение не прошло health check"
        Write-Info "Проверка логов..."
        docker-compose -f docker-compose.optimized.yml logs --tail=20
        exit 1
    }

    # 10. Проверка метрик
    Write-Info "Проверка метрик..."
    try {
        $response = Invoke-WebRequest -Uri "http://localhost/metrics" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Success "Метрики доступны"
        }
    }
    catch {
        Write-Warning "Метрики недоступны"
    }

    # ============================================================================
    # ЗАВЕРШЕНИЕ РАЗВЕРТЫВАНИЯ
    # ============================================================================

    Write-Host ""
    Write-Host "============================================================================"
    Write-Success "Развертывание оптимизированной системы завершено!"
    Write-Host ""
    Write-Host "Доступные сервисы:"
    Write-Host "   Приложение: http://localhost"
    Write-Host "   Health check: http://localhost/health"
    Write-Host "   Метрики: http://localhost/metrics"
    Write-Host "   pgAdmin: http://localhost:5050"
    Write-Host ""
    Write-Host "Информация о системе:"
    Write-Host "   Экземпляры Flask: 4"
    Write-Host "   Балансировка нагрузки: Nginx"
    Write-Host "   Кэширование: Redis"
    Write-Host "   Пул соединений БД: 5-20"
    Write-Host ""
    Write-Host "Полезные команды:"
    Write-Host "   Просмотр логов: docker-compose -f docker-compose.optimized.yml logs -f"
    Write-Host "   Статус сервисов: docker-compose -f docker-compose.optimized.yml ps"
    Write-Host "   Остановка: docker-compose -f docker-compose.optimized.yml down"
    Write-Host "   Мониторинг ресурсов: docker stats"
    Write-Host ""
    Write-Success "Система готова к обработке высокой нагрузки!"
    Write-Host "============================================================================"
}
catch {
    Write-Error "Произошла ошибка во время развертывания: $($_.Exception.Message)"
    Write-Host "Для отладки проверьте логи Docker:"
    Write-Host "docker-compose -f docker-compose.optimized.yml logs"
    exit 1
}