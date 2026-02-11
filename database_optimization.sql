-- ============================================================================
-- ОПТИМИЗАЦИЯ БАЗЫ ДАННЫХ ДЛЯ ВЫСОКОЙ ПРОИЗВОДИТЕЛЬНОСТИ
-- ============================================================================

-- Создание индексов для улучшения производительности запросов
-- CONCURRENTLY позволяет создавать индексы без блокировки таблицы

-- ============================================================================
-- ИНДЕКСЫ ДЛЯ ТАБЛИЦЫ IMAGES
-- ============================================================================

-- Индекс по email пользователя (наиболее частый запрос)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_images_user_email 
ON images(user_email);

-- Индекс по времени загрузки для сортировки
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_images_upload_time 
ON images(upload_time DESC);

-- Индекс по дате истечения для очистки просроченных файлов
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_images_expires_at 
ON images(expires_at) 
WHERE expires_at IS NOT NULL;

-- Составной индекс для пагинации пользовательских изображений
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_images_user_time 
ON images(user_email, upload_time DESC);

-- Индекс по размеру файла для статистики
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_images_size 
ON images(size);

-- Индекс по типу файла для фильтрации
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_images_file_type 
ON images(file_type);

-- ============================================================================
-- ИНДЕКСЫ ДЛЯ ТАБЛИЦЫ USERS
-- ============================================================================

-- Уникальный индекс по email (должен быть уже создан, но проверим)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_unique 
ON users(email);

-- Индекс по дате регистрации
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_created_at 
ON users(created_at DESC);

-- ============================================================================
-- ИНДЕКСЫ ДЛЯ ТАБЛИЦЫ STATISTICS
-- ============================================================================

-- Индекс по типу действия (для фильтрации)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_statistics_action_type 
ON statistics(action_type);

-- Индекс по времени для сортировки и архивирования
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_statistics_timestamp 
ON statistics(timestamp DESC);

-- Индекс по пользователю для персональной статистики
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_statistics_user_email 
ON statistics(user_email) 
WHERE user_email IS NOT NULL;

-- Составной индекс для частых запросов статистики
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_statistics_type_time 
ON statistics(action_type, timestamp DESC);

-- Составной индекс для пользовательской статистики
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_statistics_user_type_time 
ON statistics(user_email, action_type, timestamp DESC) 
WHERE user_email IS NOT NULL;

-- ============================================================================
-- ПАРТИЦИОНИРОВАНИЕ ТАБЛИЦЫ STATISTICS (для больших объемов данных)
-- ============================================================================

-- Создание партиционированной таблицы статистики по месяцам
-- Это критично важно для систем с высокой нагрузкой

-- Переименовываем существующую таблицу
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'statistics') THEN
        ALTER TABLE statistics RENAME TO statistics_old;
    END IF;
END $$;

-- Создаем новую партиционированную таблицу
CREATE TABLE IF NOT EXISTS statistics (
    id SERIAL,
    action_type VARCHAR(50) NOT NULL,
    user_email VARCHAR(255),
    file_id INTEGER,
    ip_address INET,
    user_agent TEXT,
    additional_info TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
) PARTITION BY RANGE (timestamp);

-- Создаем партиции на несколько месяцев
CREATE TABLE IF NOT EXISTS statistics_2024_01 PARTITION OF statistics
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE IF NOT EXISTS statistics_2024_02 PARTITION OF statistics
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

CREATE TABLE IF NOT EXISTS statistics_2024_03 PARTITION OF statistics
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');

CREATE TABLE IF NOT EXISTS statistics_2024_04 PARTITION OF statistics
    FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');

CREATE TABLE IF NOT EXISTS statistics_2024_05 PARTITION OF statistics
    FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');

CREATE TABLE IF NOT EXISTS statistics_2024_06 PARTITION OF statistics
    FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');

CREATE TABLE IF NOT EXISTS statistics_2024_07 PARTITION OF statistics
    FOR VALUES FROM ('2024-07-01') TO ('2024-08-01');

CREATE TABLE IF NOT EXISTS statistics_2024_08 PARTITION OF statistics
    FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');

CREATE TABLE IF NOT EXISTS statistics_2024_09 PARTITION OF statistics
    FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');

CREATE TABLE IF NOT EXISTS statistics_2024_10 PARTITION OF statistics
    FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');

CREATE TABLE IF NOT EXISTS statistics_2024_11 PARTITION OF statistics
    FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');

CREATE TABLE IF NOT EXISTS statistics_2024_12 PARTITION OF statistics
    FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');

-- Копируем данные из старой таблицы (если существует)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'statistics_old') THEN
        INSERT INTO statistics SELECT * FROM statistics_old;
        DROP TABLE statistics_old;
    END IF;
END $$;

-- Создаем индексы на партиционированной таблице
CREATE INDEX IF NOT EXISTS idx_statistics_part_action_type ON statistics(action_type);
CREATE INDEX IF NOT EXISTS idx_statistics_part_timestamp ON statistics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_statistics_part_user_email ON statistics(user_email) WHERE user_email IS NOT NULL;

-- ============================================================================
-- ФУНКЦИИ ДЛЯ АВТОМАТИЧЕСКОГО СОЗДАНИЯ ПАРТИЦИЙ
-- ============================================================================

CREATE OR REPLACE FUNCTION create_monthly_partition(table_name text, start_date date)
RETURNS void AS $$
DECLARE
    partition_name text;
    end_date date;
BEGIN
    -- Вычисляем имя партиции и конечную дату
    partition_name := table_name || '_' || to_char(start_date, 'YYYY_MM');
    end_date := start_date + interval '1 month';
    
    -- Создаем партицию
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                   partition_name, table_name, start_date, end_date);
    
    -- Создаем индексы на новой партиции
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I(action_type)', 
                   'idx_' || partition_name || '_action_type', partition_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I(timestamp DESC)', 
                   'idx_' || partition_name || '_timestamp', partition_name);
END;
$$ LANGUAGE plpgsql;

-- Функция для автоматического создания партиций на будущие месяцы
CREATE OR REPLACE FUNCTION maintain_partitions()
RETURNS void AS $$
DECLARE
    next_month date;
BEGIN
    -- Создаем партиции на следующие 3 месяца
    FOR i IN 1..3 LOOP
        next_month := date_trunc('month', CURRENT_DATE) + (i || ' month')::interval;
        
        -- Проверяем, существует ли партиция
        IF NOT EXISTS (
            SELECT 1 FROM pg_tables 
            WHERE tablename = 'statistics_' || to_char(next_month, 'YYYY_MM')
        ) THEN
            PERFORM create_monthly_partition('statistics', next_month);
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Функция для удаления старых партиций (старше 1 года)
CREATE OR REPLACE FUNCTION cleanup_old_partitions()
RETURNS void AS $$
DECLARE
    old_partition text;
    cutoff_date date;
BEGIN
    cutoff_date := date_trunc('month', CURRENT_DATE) - interval '1 year';
    
    -- Находим и удаляем старые партиции
    FOR old_partition IN 
        SELECT tablename FROM pg_tables 
        WHERE tablename LIKE 'statistics_____' 
        AND to_date(substring(tablename from 12), 'YYYY_MM') < cutoff_date
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I', old_partition);
        RAISE NOTICE 'Dropped old partition: %', old_partition;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- НАСТРОЙКИ POSTGRESQL ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ
-- ============================================================================

-- Увеличиваем статистику для лучшего планирования запросов
ALTER TABLE images ALTER COLUMN user_email SET STATISTICS 1000;
ALTER TABLE statistics ALTER COLUMN action_type SET STATISTICS 1000;
ALTER TABLE statistics ALTER COLUMN timestamp SET STATISTICS 1000;

-- Обновляем статистику
ANALYZE images;
ANALYZE users;
ANALYZE statistics;

-- ============================================================================
-- МАТЕРИАЛИЗОВАННЫЕ ПРЕДСТАВЛЕНИЯ ДЛЯ БЫСТРОЙ АНАЛИТИКИ
-- ============================================================================

-- Создаем материализованное представление для ежедневной статистики
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_statistics AS
SELECT 
    DATE(timestamp) as date,
    action_type,
    COUNT(*) as count,
    COUNT(DISTINCT user_email) as unique_users
FROM statistics 
WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(timestamp), action_type
ORDER BY date DESC, action_type;

-- Создаем индекс для материализованного представления
CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_stats_date_type 
ON daily_statistics(date, action_type);

-- Создаем материализованное представление для пользовательской статистики
CREATE MATERIALIZED VIEW IF NOT EXISTS user_statistics AS
SELECT 
    user_email,
    COUNT(*) as total_actions,
    COUNT(*) FILTER (WHERE action_type = 'успешная_загрузка') as uploads,
    COUNT(*) FILTER (WHERE action_type = 'download') as downloads,
    COUNT(*) FILTER (WHERE action_type = 'просмотр_изображения') as views,
    MAX(timestamp) as last_activity
FROM statistics 
WHERE user_email IS NOT NULL
GROUP BY user_email;

-- Создаем индекс для пользовательской статистики
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_stats_email 
ON user_statistics(user_email);

-- ============================================================================
-- ФУНКЦИИ ДЛЯ ОБНОВЛЕНИЯ МАТЕРИАЛИЗОВАННЫХ ПРЕДСТАВЛЕНИЙ
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_statistics_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_statistics;
    REFRESH MATERIALIZED VIEW CONCURRENTLY user_statistics;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ТРИГГЕРЫ ДЛЯ АВТОМАТИЧЕСКОГО ОБСЛУЖИВАНИЯ
-- ============================================================================

-- Функция для автоматического создания партиций при вставке
CREATE OR REPLACE FUNCTION auto_create_partition()
RETURNS TRIGGER AS $$
DECLARE
    partition_date date;
BEGIN
    partition_date := date_trunc('month', NEW.timestamp);
    
    -- Проверяем, существует ли партиция для этого месяца
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE tablename = 'statistics_' || to_char(partition_date, 'YYYY_MM')
    ) THEN
        PERFORM create_monthly_partition('statistics', partition_date);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Создаем триггер для автоматического создания партиций
DROP TRIGGER IF EXISTS trigger_auto_create_partition ON statistics;
CREATE TRIGGER trigger_auto_create_partition
    BEFORE INSERT ON statistics
    FOR EACH ROW
    EXECUTE FUNCTION auto_create_partition();

-- ============================================================================
-- ПЕРИОДИЧЕСКИЕ ЗАДАЧИ (требует расширение pg_cron)
-- ============================================================================

-- Раскомментируйте следующие строки если установлено расширение pg_cron:

-- CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Создание партиций каждый месяц
-- SELECT cron.schedule('maintain-partitions', '0 0 1 * *', 'SELECT maintain_partitions();');

-- Очистка старых партиций каждые 3 месяца
-- SELECT cron.schedule('cleanup-partitions', '0 0 1 */3 *', 'SELECT cleanup_old_partitions();');

-- Обновление материализованных представлений каждый час
-- SELECT cron.schedule('refresh-stats', '0 * * * *', 'SELECT refresh_statistics_views();');

-- ============================================================================
-- ИНФОРМАЦИЯ О ВЫПОЛНЕННЫХ ОПТИМИЗАЦИЯХ
-- ============================================================================

-- Выводим информацию о созданных индексах
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename IN ('images', 'users', 'statistics')
ORDER BY tablename, indexname;

-- Выводим информацию о партициях
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE tablename LIKE 'statistics_%'
ORDER BY tablename;

-- Выводим размеры таблиц
SELECT 
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS size
FROM pg_catalog.pg_statio_user_tables 
WHERE relname IN ('images', 'users', 'statistics')
ORDER BY pg_total_relation_size(relid) DESC;

-- ============================================================================
-- ЗАВЕРШЕНИЕ ОПТИМИЗАЦИИ
-- ============================================================================

-- Обновляем статистику после создания всех индексов
ANALYZE;

-- Выводим сообщение о завершении
DO $$
BEGIN
    RAISE NOTICE 'Database optimization completed successfully!';
    RAISE NOTICE 'Created indexes for improved query performance';
    RAISE NOTICE 'Set up table partitioning for statistics';
    RAISE NOTICE 'Created materialized views for fast analytics';
    RAISE NOTICE 'Configured automatic maintenance functions';
END $$;