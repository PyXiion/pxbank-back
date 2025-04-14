# Шпаргалка по командам Alembic

## Инициализация проекта
```sh
alembic init alembic  # Создание структуры каталогов Alembic
```

## Настройка подключения к базе данных
Файл `alembic.ini`:
```ini
sqlalchemy.url = sqlite:///example.db  # Укажите вашу БД
```

## Создание миграции
```sh
alembic revision -m "описание"  # Создание пустого файла миграции
alembic revision --autogenerate -m "описание"  # Автоматическое определение изменений
```

## Применение и откат миграций
```sh
alembic upgrade head  # Применить все миграции
alembic upgrade <version>  # Применить миграцию до указанной версии
alembic downgrade -1  # Откатить последнюю миграцию
alembic downgrade <version>  # Откатиться до указанной версии
```

## Пересоздание базы данных с нуля
```sh
rm -rf alembic/versions/*  # Удалить все миграции
alembic downgrade base  # Откатить все изменения
rm example.db  # Удалить саму базу данных (если SQLite)
alembic revision --autogenerate -m "init"  # Создать новую миграцию
alembic upgrade head  # Применить новую миграцию
```

## Просмотр состояния
```sh
alembic current  # Показать текущую версию схемы
alembic history  # Показать список всех миграций
alembic heads  # Показать последние миграции
alembic branches  # Показать ветки миграций
alembic show <version>  # Показать детали миграции
```

## Ручное редактирование миграций
Файл миграции (`versions/xxxxxxxx_description.py`):
```python
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(50), nullable=False)
    )

def downgrade():
    op.drop_table('users')
```

## Очистка миграционной истории
```sh
alembic stamp head  # Отметить текущую схему как актуальную без выполнения миграций
alembic stamp <version>  # Принудительно установить версию схемы
```

## Полезные команды
```sh
alembic check  # Проверить соответствие модели и БД
alembic merge <version1> <version2> -m "описание"  # Объединить ветки миграций
```

