from typing import Any, Callable, Optional

import sys
import queue
import threading

import tkinter as tk
from tkinter import ttk

from pathlib import Path
from dataclasses import dataclass, field


class SafeWidgetPatcher:
    """
    Класс для безопасного monkey-patching ttk.Label и ttk.Progressbar.
    Переопределяет config-методы с проверкой потока, чтобы исключить ошибки в многопоточности.

    """

    _original_label_config: Callable | None = None
    _original_progressbar_config: Callable | None = None
    _patched: bool = False

    @classmethod
    def apply(cls) -> None:
        """
        Применяет monkey-patching к методам .config() Label и Progressbar.

        """
        if cls._patched:
            return

        cls._original_label_config = ttk.Label.config
        cls._original_progressbar_config = ttk.Progressbar.config

        # Переопределяем методы экземпляров, передаём обычные функции
        def safe_label_config(self: ttk.Label, *args: Any, **kwargs: Any) -> None:
            if 'text' in kwargs and not cls._is_main_thread():
                self.after(0, lambda: cls._original_label_config(self, *args, **kwargs))  # noqa parameter unfilled
            else:
                cls._original_label_config(self, *args, **kwargs)  # noqa parameter unfilled

        def safe_progressbar_config(self: ttk.Progressbar, *args: Any, **kwargs: Any) -> None:
            if any(key in kwargs for key in ('value', 'maximum')) and not cls._is_main_thread():
                self.after(0, lambda: cls._original_progressbar_config(self, *args, **kwargs))  # noqa parameter unfilled
            else:
                cls._original_progressbar_config(self, *args, **kwargs)  # noqa parameter unfilled

        # Сохраняем в атрибутах, чтобы можно было потом использовать при восстановлении
        cls._safe_label_config_func = safe_label_config
        cls._safe_progressbar_config_func = safe_progressbar_config

        # Monkey-patch
        ttk.Label.config = safe_label_config  # noqa parameter unfilled
        ttk.Progressbar.config = safe_progressbar_config  # noqa parameter unfilled

        cls._patched = True

    @classmethod
    def restore(cls) -> None:
        """
        Восстанавливает оригинальные методы .config().

        """
        if not cls._patched:
            return

        if cls._original_label_config:
            ttk.Label.config = cls._original_label_config
        if cls._original_progressbar_config:
            ttk.Progressbar.config = cls._original_progressbar_config

        cls._patched = False

    @classmethod
    def _is_main_thread(cls) -> bool:
        """
        Проверяет, выполняется ли код в главном потоке.

        """
        return threading.current_thread().name == 'MainThread'


class ThreadTaskManager:
    """
    Менеджер задач в отдельном потоке

    """

    def __init__(self) -> None:
        self._task_queue: queue.Queue = queue.Queue()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._running = threading.Event()
        self._running.set()
        self._worker_thread.start()
        self._busy = threading.Event()

    def _worker(self) -> None:
        while self._running.is_set():
            try:
                func, args, kwargs = self._task_queue.get(timeout=0.2)
                self._busy.set()
            except queue.Empty:
                continue

            try:
                func(*args, **kwargs)
            except Exception:  # noqa too broad exception clause
                pass
            finally:
                self._task_queue.task_done()
                if self._task_queue.unfinished_tasks == 0:
                    self._busy.clear()

    def is_busy(self) -> bool:
        """
        Возвращает True, если поток занят

        """
        return self._busy.is_set()

    def add_task(self, func: Callable, *args: Any, **kwargs: Any) -> None:
        """
        Добавить задачу в очередь на выполнение

        """
        self._task_queue.put((func, args, kwargs))

    def wait_ready(self, widget: tk.Widget | ttk.Widget, callback: Callable[[], None | tuple[None, None]], delay: int = 100) -> None:
        """
        Универсальный метод ожидания завершения всех задач с поддержкой цепочек.
        Использует проверку unfinished_tasks для надёжности и позволяет вызывать себя рекурсивно.

        :param widget: Элемент с методом after, обычно tk или ttk виджет.
        :param callback: Функция, вызываемая после завершения всех задач.
        :param delay: Интервал повторной проверки в миллисекундах.

        """
        def check() -> None:
            if self._task_queue.unfinished_tasks == 0:
                callback()
            else:
                widget.after(delay, check)  # noqa parameter unfilled

        widget.after(delay, check)  # noqa parameter unfilled

    def stop(self, root: tk.Tk, callback: Optional[Callable[[], None]] = None) -> None:
        """
        Асинхронная остановка потока без блокировки GUI.

        """
        def stop_thread() -> None:
            self._task_queue.join()
            self._running.clear()
            self._worker_thread.join()
            if callback:
                root.after(0, callback)  # noqa parameter unfilled

        threading.Thread(target=stop_thread, daemon=True).start()


@dataclass
class GuiContext:
    """
    Контекст приложения Update Plugins, используется для хранения состояний,
    связанных с GUI и логикой.

    """
    plugins_pack: list[dict[str, str]] = field(default_factory=list)

    plugins: list[tk.BooleanVar] = field(default_factory=list)
    progress: list[ttk.Progressbar] = field(default_factory=list)
    labels: list[ttk.Label] = field(default_factory=list)

    plugins_set: list[dict[str, str | int | bool | None]] = field(default_factory=list)
    progress_set: list[ttk.Progressbar] = field(default_factory=list)
    labels_set: list[ttk.Label] = field(default_factory=list)


@dataclass
class Args:
    """
    Аргументы для компактной передачи в функции

    """
    title: str | None = field(default=None)
    frame: ttk.Frame = field(default_factory=ttk.Frame)
    label: ttk.Label = field(default_factory=ttk.Label)
    entry: ttk.Entry = field(default_factory=ttk.Entry)
    button: ttk.Button = field(default_factory=ttk.Button)


def resource_path(relative_path: str, dev_base_path: Optional[Path] = None) -> str:
    """
    Возвращает абсолютный путь к ресурсу.
    Работает как в режиме разработки, так и в скомпилированном exe (через PyInstaller).

    :param relative_path: Относительный путь к ресурсу
    :param dev_base_path: Базовая директория в режиме разработки (по умолчанию — текущая)
    :return: Абсолютный путь в виде строки

    """
    if not relative_path:
        return ''

    base_path: Path = (Path(getattr(sys, '_MEIPASS')) if hasattr(sys, '_MEIPASS') else dev_base_path or Path(__file__).parent)

    return str(base_path / relative_path)


if __name__ == '__main__':
    pass