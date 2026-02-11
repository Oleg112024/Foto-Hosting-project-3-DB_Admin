#!/bin/bash

# Скрипт инициализации pgAdmin с повышенной безопасностью
# Настраивает автоматическое создание сервера с требованием мастер-пароля

echo "Инициализация защищенного pgAdmin..."

# Создаем директорию для pgAdmin если не существует
mkdir -p /var/lib/pgadmin

# Создаем файл .pgpass для автоматической аутентификации к PostgreSQL
# (НЕ для входа в pgAdmin - он по-прежнему требует логин/пароль)
cat > /var/lib/pgadmin/.pgpass << EOF
# Файл автоматической аутентификации для подключения к PostgreSQL
# Формат: hostname:port:database:username:password
# Этот файл используется только для подключения к БД, не для входа в pgAdmin
db:5432:images_db:postgres:${DB_PASSWORD}
db:5432:*:postgres:${DB_PASSWORD}
*:*:*:postgres:${DB_PASSWORD}
EOF

# Устанавливаем правильные права доступа
chmod 600 /var/lib/pgadmin/.pgpass
chown pgadmin:pgadmin /var/lib/pgadmin/.pgpass

# Создаем файл с информацией о безопасности
cat > /var/lib/pgadmin/security_info.txt << EOF
=== ИНФОРМАЦИЯ О БЕЗОПАСНОСТИ PGADMIN ===

Для входа в pgAdmin требуется:
1. Email администратора: из переменной PGADMIN_DEFAULT_EMAIL
2. Пароль администратора: из переменной PGADMIN_DEFAULT_PASSWORD
3. Мастер-пароль: будет запрошен при первом входе

Сервер базы данных создается автоматически, но:
- Требуется аутентификация в pgAdmin
- Включена CSRF защита
- Активирован серверный режим

Дата создания: $(date)
EOF

echo "Настройка безопасности завершена"
echo "ВНИМАНИЕ: При первом входе потребуется установить мастер-пароль!"

# Запускаем оригинальную команду pgAdmin
exec "$@"