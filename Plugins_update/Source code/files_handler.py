from typing import TYPE_CHECKING

import shutil
import datetime
import requests

from tkinter import ttk
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from requests.exceptions import RequestException

from gui_support import resource_path

if TYPE_CHECKING:
    from gui_support import GuiContext


def get_path(folder_type: str) -> Path | None:
    """
    Возвращает путь к папке плагинов

    :param folder_type: 'packed' или 'unpacked'

    """
    # base_path = Path(__file__).parent
    packed_path: Path = Path(resource_path('plugins'))
    unpacked_path: Path = Path(packed_path) / 'unpacked'

    if folder_type == 'packed':
        return packed_path

    elif folder_type == 'unpacked':
        return unpacked_path

    return None


def clean_plugins() -> None:
    """
    Удаляет все файлы из папки 'plugins' кроме файлов, созданных сегодня.
    Удаляет все папки из 'unpacked'.

    """
    plugins_path: Path = get_path('packed')
    unpacked_path: Path = get_path('unpacked')

    if not plugins_path.is_dir():
        unpacked_path.mkdir(parents=True, exist_ok=True)
        return

    today = datetime.date.today()

    # Удаляем файлы из plugins, кроме созданных сегодня
    for item in plugins_path.iterdir():
        if item.is_file():
            try:
                created_date = datetime.date.fromtimestamp(item.stat().st_ctime)
                if created_date != today:
                    item.unlink()
            except (PermissionError, FileNotFoundError):
                pass

    # Удаляем папки из unpacked полностью
    if unpacked_path.exists():
        for item in unpacked_path.iterdir():
            if item.is_dir():
                try:
                    shutil.rmtree(item)
                except (PermissionError, FileNotFoundError):
                    pass


def get_download_list(plugins_pack) -> list[str]:
    """
    Получает список загруженных плагинов.

    """
    plugins_path: Path = get_path('packed')
    unpacked_path: Path = get_path('unpacked')

    existing_names = ({item.name for item in plugins_path.iterdir() if item.is_file()} |
                      {jar_file.name for jar_file in unpacked_path.rglob('*.jar')})

    ranked = [plugin['file'] for plugin in plugins_pack if plugin.get('file') in existing_names]
    return ranked


def update_progress(label: ttk.Label, progress: ttk.Progressbar, downloaded: int) -> None:
    """
    Обновляет progress bar и label с процентами.

    """
    total_size = int(progress['maximum'])

    percent = 100 * downloaded / total_size if total_size else 0
    progress['value'] = downloaded
    label.config(text=f'{percent:>3.0f} %'.ljust(25))  # пробелы нужны для удаления старых надписей


def update_jar(file_name: str, label: ttk.Label) -> None:
    """
    Обновляет label если файл .jar

    """
    if file_name.endswith('.jar'):
        label.config(text='файл распакован')


def get_save_path(context: 'GuiContext', index: int) -> Path | None:
    """
    Формирует путь для сохранения файла плагина.

    """
    plugins_path: Path = get_path('packed')
    unpacked_path: Path = get_path('unpacked')

    save_name: str = context.plugins_set[index]['file']
    plugin_name: str = context.plugins_set[index]['name']

    if save_name.endswith('.zip'):
        return plugins_path / save_name

    if save_name.endswith('.jar'):
        jar_path: Path = unpacked_path / plugin_name / 'lib'
        jar_path.mkdir(parents=True, exist_ok=True)
        return jar_path / save_name

    return None


def is_exist(file_path: Path) -> bool:
    """
    Проверяет что файл уже закачан.

    :param file_path:
    :return:
    """
    if file_path.exists():
        return True
    else:
        return False


def download_files(context: 'GuiContext', chunk_size: int = 4096) -> None:
    """
    Загружает файлы, обновляя прогресс в GUI.

    """
    for index, plugin in enumerate(context.plugins_set):

        current_label: ttk.Label = context.labels_set[index]
        current_progress: ttk.Progressbar = context.progress_set[index]

        download_url: str | None = plugin.get('download_url')
        total_size: int | None = plugin.get('file_size')
        file_name: str | None = plugin.get('file')

        if not all([download_url, total_size, file_name]):
            current_label.config(text='ошибка загрузки')
            continue

        save_path: Path = get_save_path(context, index)
        current_progress.configure(maximum=total_size)

        if is_exist(save_path):
            update_progress(current_label, current_progress, total_size)
            update_jar(file_name, current_label)
            continue

        try:
            with requests.get(download_url, stream=True) as response:
                response.raise_for_status()

                with open(save_path, 'wb') as file:
                    downloaded: int = 0
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        file.write(chunk)
                        downloaded += len(chunk)
                        update_progress(current_label, current_progress, downloaded)
                    update_jar(file_name, current_label)

        except RequestException:
            current_label.config(text='ошибка загрузки')

    return None


def update_zip(context: 'GuiContext', index: int, option: bool) -> None:
    """
    Если файл успешно распакован, устанавливает progress bar на 100%
    Если файл не распакован, устанавливает progress bar на 50%
    На label пишет 'файл распакован'/'файл поврежден'

    """
    if option:
        total = context.progress_set[index].cget('maximum')
        context.progress_set[index].configure(value=total)
        context.labels_set[index].config(text='файл распакован')

    else:
        total = context.progress_set[index].cget('maximum')
        context.progress_set[index].configure(value=total / 2)
        context.labels_set[index].config(text='файл поврежден')


def unpack_plugins(context: 'GuiContext') -> None:
    """
    Распаковывает все загруженные плагины из zip-архивов.
    Если распаковка успешна, обновляет путь плагина и вызывает update_zip.

    """
    packed_dir: Path = get_path('packed')
    unpacked_dir: Path = get_path('unpacked')

    for index, plugin in enumerate(context.plugins_set):
        file_name: str = plugin['file']
        file_ext: str = Path(file_name).suffix.lower()

        if file_ext == '.zip':
            source_path: Path = packed_dir / file_name
            unpacked_path = zip_extractor(source_path)

        elif file_ext == '.jar':
            jar_name: Path = unpacked_dir / plugin['name'] / 'lib' / plugin['file']

            if jar_name.is_file():
                unpacked_path: str | bool = plugin['name']
            else:
                unpacked_path: str | bool = False

        else:
            continue

        plugin['plugin_path'] = unpacked_path
        update_zip(context, index, bool(unpacked_path))


def zip_extractor(source_path: Path, ) -> bool | str:
    """
    Распаковывает ZIP-архив в указанную папку и проверяет успешность извлечения.
    Если архив не существует, пустой, повреждён или распаковка не удалась — возвращает False.

    :return bool: True, если хотя бы один файл был успешно извлечён; False в противном случае.

    """
    target_path: Path = get_path('unpacked')

    try:
        with ZipFile(source_path, 'r') as zip_source:
            file_list: list[str] = zip_source.namelist()

            if not file_list:
                return False  # пустой архив
            else:
                zip_source.extractall(target_path)
                any((target_path / name).exists() for name in file_list)

                return file_list[0].split('/')[0]

    except (BadZipFile, OSError):
        return False


def update_setup(context: 'GuiContext', index: int, option: bool) -> None:
    """
    Ставит progress bar всех устанавливаемых плагинов на 100%
    Если папка успешно скопирована, progress bar становится зеленого цвета
    Если при копировании произошла ошибка, progress bar становится красного цвета
    На label пишет 'плагин установлен'/'ошибка установки'

    """
    if option:
        style = ttk.Style()
        style_name = f'Green{index}.Horizontal.TProgressbar'
        style.configure(style_name, background='#006400')

        total = context.progress_set[index].cget('maximum')
        context.progress_set[index].configure(value=total)
        context.progress_set[index].configure(style=style_name)
        context.labels_set[index].config(text='плагин установлен')

    else:
        style = ttk.Style()
        style_name = f'Red{index}.Horizontal.TProgressbar'
        style.configure(style_name, background='#640000')

        total = context.progress_set[index].cget('maximum')
        context.progress_set[index].configure(value=total)
        context.progress_set[index].configure(style=style_name)
        context.labels_set[index].config(text='ошибка установки')


def setup_plugins(context: 'GuiContext', charm_folder: str) -> None:
    """
    Если install_path не существует, создает её.
    Если install_path уществует, то проверят папки в unpacked_path.
    Удаляет.папки с такими же именами в install_path остальные папки не трогает.
    Копирует все плагины из unpacked_path в install_path

    """
    unpacked_path: Path = get_path('unpacked')

    charm_path: Path = Path(charm_folder)
    install_path: Path = charm_path / 'plugins'

    if not install_path.is_dir():
        install_path.mkdir(parents=True, exist_ok=True)

    else:
        # Список папок для удаления
        storage_folders = tuple(plugin['plugin_path'].lower() for plugin in context.plugins_set if plugin['plugin_path'] is not False)

        # Удаление старых plugin'ов
        for item in install_path.iterdir():
            if item.is_dir() and item.name.lower() in storage_folders:
                shutil.rmtree(item)

        # Копирование новых plugin'ов
        for index, plugin in enumerate(context.plugins_set):

            if plugin['plugin_path'] is not False:

                src_path: Path = unpacked_path / plugin['plugin_path']
                des_path: Path = install_path / plugin['plugin_path']

                result = copy_with_status(src_path, des_path)

                if result == 'Error':
                    update_setup(context, index, False)
                else:
                    update_setup(context, index, True)


def copy_with_status(source: Path, destination: Path) -> str:
    """
    Копирует все файлы и папки из source в destination с учётом относительных путей.
    Возвращает status

    """
    status: str = ''

    for item in source.rglob('*'):
        try:
            relative_path = item.relative_to(source)
            destination_path = destination / relative_path

            if item.is_dir():
                destination_path.mkdir(parents=True, exist_ok=True)
                if status != 'Error':
                    status: str = 'Path OK'
            else:
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(item, destination_path)
                if status != 'Error':
                    status: str = 'File OK'

        except (PermissionError, OSError):
            status: str = 'Error'

    return status


if __name__ == '__main__':
    pass