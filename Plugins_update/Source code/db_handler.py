import sqlite3
from typing import Any, TYPE_CHECKING
from pathlib import Path


def get_db_path() -> Path:
    """
    Возвращает путь к базе данных.

    """
    base_path: Path = Path(__file__).parent
    database_path: Path = base_path / 'database' / 'plugins.db'
    return database_path


def fetch_plugin_pack() -> list[dict[str, str]] | None:
    """
     Извлекает 'name', 'url' и 'file' из таблицы 'pycharm_plugins' базы данных plugins.db.

     :return: Список словарей, каждый из которых содержит:
              - 'name': имя плагина (строка),
              - 'url': URL плагина (строка),
              - 'file': имя файла плагина (строка).
              или None, если произошла ошибка при подключении к базе данных или выполнении запроса.

     """
    database_path: Path = get_db_path()
    db_query: str = 'SELECT id, name, url, file FROM pycharm_plugins ORDER BY name COLLATE NOCASE'

    try:
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(db_query)
            lines = cursor.fetchall()
            fetch_list: list[dict[str, str]] = [dict(row) for row in lines]

    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        return None

    return fetch_list


def update_files(plugins_set: list[dict[str, Any]]) -> None:
    """
    Обновляет столбец 'file' в таблице 'pycharm_plugins' в базе данных.

    :param plugins_set: Список словарей с ключами 'id',  'name' и 'file'.

    """
    database_path: Path = get_db_path()

    # Список пар (file, name) для обновления
    update_data: list[tuple[str, str]] = [(plugin['file'], plugin['name']) for plugin in plugins_set if 'file' in plugin and 'name' in plugin]

    if not update_data:
        return

    db_query: str = 'UPDATE pycharm_plugins SET file = ? WHERE name = ?'

    with sqlite3.connect(database_path) as connection:
        cursor = connection.cursor()
        cursor.executemany(db_query, update_data)
        connection.commit()


def update_paths(plugins_set: list[dict[str, Any]]) -> None:
    """
    Обновляет столбец 'folder' в таблице 'pycharm_plugins' в базе данных.

    :param plugins_set: Список словарей с ключами 'id', 'name' и 'file'.

    """
    database_path: Path = get_db_path()

    # Список пар (plugin_path, name) для обновления
    update_data: list[tuple[str, str]] = [(plugin['plugin_path'], plugin['name']) for plugin in plugins_set if 'plugin_path' in plugin and 'name' in plugin]

    if not update_data:
        return

    db_query: str = 'UPDATE pycharm_plugins SET folder = ? WHERE name = ?'

    with sqlite3.connect(database_path) as connection:
        cursor = connection.cursor()
        cursor.executemany(db_query, update_data)
        connection.commit()