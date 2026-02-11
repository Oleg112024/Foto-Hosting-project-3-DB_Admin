import os
import subprocess
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(
    filename='logs/backup.log',
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Создаем директорию для бэкапов, если она не существует
os.makedirs('backups', exist_ok=True)

def create_backup():
    """Создает резервную копию базы данных PostgreSQL"""
    try:
        # Формируем имя файла с текущей датой и временем
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_filename = f"backup_{timestamp}.sql"
        backup_path = os.path.join('backups', backup_filename)
        
        # Формируем команду для создания бэкапа
        # Для Docker используем docker exec
        command = [
            'docker', 'exec', 'image_hosting_db',
            'pg_dump', '-U', 'postgres', 'images_db'
        ]
        
        # Выполняем команду и сохраняем результат в файл
        with open(backup_path, 'w') as f:
            result = subprocess.run(command, stdout=f, stderr=subprocess.PIPE, text=True)
        
        # Проверяем результат выполнения команды
        if result.returncode == 0:
            logging.info(f"Резервная копия успешно создана: {backup_path}")
            print(f"Резервная копия успешно создана: {backup_path}")
            return True
        else:
            logging.error(f"Ошибка при создании резервной копии: {result.stderr}")
            print(f"Ошибка при создании резервной копии: {result.stderr}")
            return False
    
    except Exception as e:
        logging.error(f"Исключение при создании резервной копии: {str(e)}")
        print(f"Исключение при создании резервной копии: {str(e)}")
        return False

def restore_backup(backup_file):
    """Восстанавливает базу данных из резервной копии"""
    try:
        # Проверяем существование файла бэкапа
        backup_path = os.path.join('backups', backup_file)
        if not os.path.exists(backup_path):
            logging.error(f"Файл резервной копии не найден: {backup_path}")
            print(f"Файл резервной копии не найден: {backup_path}")
            return False
        
        # Формируем команду для восстановления из бэкапа
        command = [
            'docker', 'exec', '-i', 'image_hosting_db',
            'psql', '-U', 'postgres', '-d', 'images_db'
        ]
        
        # Выполняем команду, передавая содержимое файла бэкапа
        with open(backup_path, 'r') as f:
            result = subprocess.run(command, stdin=f, stderr=subprocess.PIPE, text=True)
        
        # Проверяем результат выполнения команды
        if result.returncode == 0:
            logging.info(f"База данных успешно восстановлена из: {backup_path}")
            print(f"База данных успешно восстановлена из: {backup_path}")
            return True
        else:
            logging.error(f"Ошибка при восстановлении базы данных: {result.stderr}")
            print(f"Ошибка при восстановлении базы данных: {result.stderr}")
            return False
    
    except Exception as e:
        logging.error(f"Исключение при восстановлении базы данных: {str(e)}")
        print(f"Исключение при восстановлении базы данных: {str(e)}")
        return False

# Если скрипт запущен напрямую, создаем резервную копию
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'restore' and len(sys.argv) > 2:
        # Восстановление из бэкапа: python backup_db.py restore backup_filename.sql
        restore_backup(sys.argv[2])
    else:
        # Создание бэкапа: python backup_db.py
        create_backup()