from typing import Any

import re

import tkinter as tk
from tkinter import PhotoImage, BooleanVar
from tkinter import filedialog, ttk

from pathlib import Path

from gui_support import SafeWidgetPatcher, ThreadTaskManager, GuiContext, Args, resource_path

from vpn_launcher import is_vpn_connected, launch
from db_handler import fetch_plugin_pack, update_files, update_paths
from web_handler import process_plugins, get_driver
from files_handler import clean_plugins, download_files, get_download_list, unpack_plugins, setup_plugins

# Экземпляр контекста для глобальной области видимости
ctx: GuiContext = GuiContext()
# Экземпляр менеджера задач для глобальной области видимости
_manager = ThreadTaskManager()


def lock_buttons(frame: ttk.Frame) -> None:
    """
    Блокировка интерфейса
    Кнопки, поля ввода, чекбоксы

    """
    for child in frame.winfo_children():
        if isinstance(child, ttk.Button):
            child.state(['disabled'])
        if isinstance(child, tk.Entry):
            entry_readonly(child, True)
        if isinstance(child, tk.Checkbutton):
            checkbox_readonly(child, True)


def unlock_buttons(frame: ttk.Frame) -> None:
    """
    Разблокировка интерфейса

    """
    for child in frame.winfo_children():
        if isinstance(child, ttk.Button):
            child.state(['!disabled'])
        if isinstance(child, tk.Entry):
            entry_readonly(child, False)
        if isinstance(child, tk.Checkbutton):
            checkbox_readonly(child, False)


def resize(widget: ttk.Widget, start_width: int, target_width: int = 0, step: int = 1, delay: int = 3, remove: bool = True) -> None:
    """
    Анимация сжатия или расширения для виджетов ttk

    :param widget: имя виджета
    :param start_width: начальная ширина
    :param target_width: конечная ширина
    :param step: шаг приращения/уменьшения (+/-) соответственно
    :param delay: задержка между шагами в мс
    :param remove: удаление виджета после завершения анимации

    """
    if step < 0 and start_width <= target_width:
        if remove:
            widget.place_forget()
        else:
            widget.place_configure(width=target_width)
        return None
    elif step > 0 and start_width >= target_width:
        widget.place_configure(width=target_width)
        return None

    widget.place_configure(width=start_width)
    widget.after(delay, resize, widget, start_width + step, target_width, step, delay, remove)
    return None

def show_faultbox(title: str, message: str, parent: tk.Tk | ttk.Frame) -> None:
    """
    Тёмное модальное окно для вывода ошибки
    """
    icon: PhotoImage = PhotoImage(file=resource_path('image/logo.png'))

    box: tk.Toplevel = tk.Toplevel(parent)
    box.title(title)
    box.configure(bg='#2e2e2e')
    box.resizable(False, False)
    box.attributes('-topmost', True)
    box.iconphoto(False, icon)

    box.transient(parent)
    box.grab_set()

    # Размеры окна
    w, h = 360, 150

    # Центрирование по родителю
    parent.update_idletasks()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    x, y = px + (pw - w) // 2, py + (ph - h) // 2
    box.geometry(f'{w}x{h}+{x}+{y}')

    # Grid layout
    for i in range(3):
        box.grid_columnconfigure(i, weight=0)
    box.grid_columnconfigure(1, weight=1)
    box.grid_rowconfigure(0, minsize=5)
    box.grid_rowconfigure(1, weight=1)
    box.grid_rowconfigure(2, minsize=5)
    box.grid_rowconfigure(3, minsize=35)
    box.grid_rowconfigure(4, minsize=15)

    # Метка для текста ошибки
    label = tk.Label(
        box,
        text=message,
        bg='#2e2e2e',
        fg='#ff6464',
        font=('Arial', 12, 'bold'),
        wraplength=320,
        justify='center'
    )
    label.grid(row=1, column=1, sticky='nsew', padx=10)

    # Рамка с обводкой под кнопку OK
    button_frame = tk.Frame(box, bg='#cfcdc8')
    button_frame.grid(row=3, column=1)

    # Кнопка OK
    button = tk.Button(
        button_frame,
        text='OK',
        command=box.destroy,
        bg='#404040',
        fg='white',
        activebackground='#303030',
        activeforeground='white',
        font=('Arial', 11),
        relief='flat',
        width=15
    )
    button.grid(row=0, column=0)

    def on_enter(_: tk.Event) -> None:
        button.grid_configure(padx=2, pady=2)

    def on_leave(_: tk.Event) -> None:
        button.grid_configure(padx=0, pady=0)

    button.bind('<Enter>', on_enter)
    button.bind('<Leave>', on_leave)

    box.wait_window()

# def show_faultbox(title: str, message: str, parent: tk.Tk | ttk.Frame) -> None:
#     """
#     Тёмное модальное окно для вывода ошибки
#
#     """
#     icon: PhotoImage = PhotoImage(file=resource_path('image/logo.png'))
#
#     box: tk.Toplevel = tk.Toplevel(parent)
#     box.title(title)
#     box.configure(bg='#2e2e2e')
#     box.resizable(False, False)
#     box.attributes('-topmost', True)
#     box.iconphoto(False, icon)
#
#     box.transient(parent)
#     box.grab_set()
#
#     # Размеры окна
#     w, h = 360, 150
#
#     # Центрирование по родителю
#     parent.update_idletasks()
#     px, py = parent.winfo_rootx(), parent.winfo_rooty()
#     pw, ph = parent.winfo_width(), parent.winfo_height()
#     x, y = px + (pw - w) // 2, py + (ph - h) // 2
#     box.geometry(f'{w}x{h}+{x}+{y}')
#
#     # Grid layout: 5 строк, 3 колонки (края 10px)
#     for i in range(3):
#         box.grid_columnconfigure(i, weight=0)
#
#     box.grid_columnconfigure(1, weight=1)  # центр
#     box.grid_rowconfigure(0, minsize=5)  # верхний отступ
#     box.grid_rowconfigure(1, weight=1)  # текст
#     box.grid_rowconfigure(2, minsize=5)  # отступ
#     box.grid_rowconfigure(3, minsize=35)  # кнопка
#     box.grid_rowconfigure(4, minsize=15)  # нижний отступ
#
#     # Метка для текста ошибки
#     label = tk.Label(
#             box,
#             text=message,
#             bg='#2e2e2e',
#             fg='#ff6464',
#             font=('Arial', 12, 'bold'),
#             wraplength=320,
#             justify='center'
#     )
#     label.grid(row=1, column=1, sticky='nsew', padx=10)
#
#     # Рамка с обводкой под кнопку OK
#     button_frame = tk.Frame(box, bg='#cfcdc8')
#     button_frame.grid(row=3, column=1)
#
#     # Кнопка OK
#     button = tk.Button(
#             button_frame,
#             text='OK',
#             command=box.destroy,
#             bg='#404040',
#             fg='white',
#             activebackground='#303030',
#             activeforeground='white',
#             font=('Arial', 11),
#             relief='flat',
#             width=15
#     )
#     button.pack()
#
#     def on_enter(_: tk.Event) -> None:
#         button.pack_configure(padx=2, pady=2)
#
#     def on_leave(_: tk.Event) -> None:
#         button.pack_configure(padx=0, pady=0)
#
#     button.bind('<Enter>', on_enter)
#     button.bind('<Leave>', on_leave)
#
#     box.wait_window()


def entry(parent: tk.Widget, **kwargs) -> tk.Entry:
    """
    Создание тёмного поля ввода с белым курсором и стилизацией,
    аналогичной ttk.Entry со стилем TEntry, но с insertbackground='white'.

    :param parent: элемент в котором будет создан Entry
    :param kwargs: дополнительные параметры, например: textvariable, width и т.д.
    """
    entry_style: dict[str, Any] = dict(
            bg='#1e1e1e',
            fg='white',
            insertbackground='white',
            font=('Arial', 11),
            relief='flat',
            highlightthickness=1,
            highlightbackground='#464646',
            highlightcolor='#C8C8C8',
            bd=0
    )

    entry_style.update(kwargs)
    return tk.Entry(parent, **entry_style)


def entry_readonly(widget: tk.Entry, readonly: bool) -> None:
    """
    Установка/снятие блокировки поля ввода

    """
    if readonly:
        widget.bind('<Key>', lambda _: 'break')
        widget.bind('<Control-v>', lambda _: 'break')
        widget.bind('<Button-3>', lambda _: 'break')  # правая кнопка мыши
    else:
        widget.unbind('<Key>')
        widget.unbind('<Control-v>')
        widget.unbind('<Button-3>')


def checkbox(parent: tk.Widget, **kwargs) -> tk.Checkbutton:
    """
    Создание чекбокса, с правильной тёмной стилизацией

    :param parent: элемент в котором будет создан чекбокс (root, frame и т.п.)
    :param kwargs: именованные аргументы

    """
    checkbox_style: dict[str, Any] = dict(
            bg='#2e2e2e',
            fg='white',
            activebackground='#2e2e2e',
            activeforeground='white',
            selectcolor='#2e2e2e',
            font=('Arial', 11),
            bd=0,
            highlightthickness=0
    )

    checkbox_style.update(kwargs)
    return tk.Checkbutton(parent, **checkbox_style)


def checkbox_readonly(widget: tk.Checkbutton, readonly: bool) -> None:
    """
    Установка/снятие блокировки чекбокса

    """
    if readonly:
        widget.bind('<Button-1>', lambda _: 'break')
        widget.bind('<space>', lambda _: 'break')
    else:
        widget.unbind('<Button-1>')
        widget.unbind('<space>')


def set_style() -> None:
    """
    Настройка стилей для виджетов ttk

    """
    style = ttk.Style()
    style.theme_use('clam')

    style.configure('TFrame',
                    background='#27282c'
                    )

    style.configure('Separator.TFrame',
                    background='#969696'
                    )

    style.configure('TLabel',
                    background='#27282c',
                    foreground='white',
                    font=('Arial', 12)
                    )

    style.configure('TButton',
                    background='#404040',
                    foreground='white',
                    font=('Arial', 11),
                    padding=(0, 1)
                    )
    style.map('TButton',
              background=[('active', '#303030')],
              borderwidth=[('active', 1), ('!active', 0)]
              )

    style.configure('Low.TButton',
                    background='#404040',
                    foreground='white',
                    font=('Arial', 10),
                    padding=(0, 1)
                    )
    style.map('Low.TButton',
              background=[('active', '#303030')],
              borderwidth=[('active', 1), ('!active', 0)]
              )

    style.configure('TProgressbar',
                    troughcolor='#1e1e1e',  # фон (не заполненная часть)
                    background='#303030',  # заполненная часть
                    bordercolor='#565656',  # граница
                    lightcolor='#1e1e1e',  # верхний светлый край (выключить)
                    darkcolor='#1e1e1e'
                    )  # нижний тёмный край (выключить)


def set_window(root: tk.Tk) -> None:
    """
    Настройка root-окна

    :param root: root-окно

    """
    plugin_count: int = len(ctx.plugins_pack)
    window_height: int = 300 + 40 * plugin_count

    icon: PhotoImage = PhotoImage(file=resource_path('image/logo.png'))
    tile_text: str = 'Обновление и установка plugins для PyCharm v1.0'

    # Настройка главного окна
    root.title(tile_text)
    root.geometry(f'800x{window_height}')
    root.configure(bg='#27282c')
    root.resizable(width=False, height=False)
    root.iconphoto(False, icon)

    # Основной контейнер
    set_style()

    main_frame: ttk.Frame = ttk.Frame(root)
    main_frame.place(x=0, y=0, relwidth=1, relheight=1)

    set_widgets(main_frame)

    return None


def set_widgets(frame: ttk.Frame) -> None:
    """
    Установка виджетов

    :param frame: основной контейнер в root-окне

    """
    tile_text: str = 'Plugins для PyCharm v1.0'

    # Изображение в верхней части окна
    header_image: PhotoImage = PhotoImage(file=resource_path('image/header.png'))

    header_label: ttk.Label = ttk.Label(frame, image=header_image)
    header_label.image = header_image
    header_label.place(x=127, y=0)

    # Разделитель
    vert_pos: int = 75

    separator: ttk.Frame = ttk.Frame(frame, height=1, style='Separator.TFrame')
    separator.place(x=20, y=vert_pos, width=760)

    # Размещение VPN
    vert_pos += 25

    vpn_label: ttk.Label = ttk.Label(frame, text='Файл VPN:')
    vpn_label.place(x=20, y=vert_pos, width=150)
    vpn_entry: tk.Entry = entry(frame)
    vpn_entry.place(x=150, y=vert_pos, width=530, height=24)
    vpn_entry.configure(insertbackground='white')
    vpn_button: ttk.Button = ttk.Button(frame, text='Выбрать', command=lambda: find_vpn(vpn_args))
    vpn_button.place(x=690, y=vert_pos - 2, width=90, height=26)

    # Заполнение атрибутов класса
    vpn_args: Args = Args(
            title=tile_text,
            frame=frame,
            label=vpn_label,
            entry=vpn_entry,
            button=vpn_button,
    )

    # Привязка обработчиков к элементам
    vpn_entry.bind('<Return>', lambda _: vpn_entry_escape(vpn_args))
    vpn_entry.bind('<Tab>', lambda _: vpn_entry_escape(vpn_args))

    if is_vpn_connected():
        vpn_active(vpn_args)

    # Папка PyCharm на системном диске
    vert_pos += 35

    charm_label: ttk.Label = ttk.Label(frame, text='Папка PyCharm:')
    charm_label.place(x=20, y=vert_pos, width=150)
    charm_entry: tk.Entry = entry(frame)
    charm_entry.place(x=150, y=vert_pos, width=530, height=24)
    charm_button: ttk.Button = ttk.Button(frame, text='Выбрать', command=lambda: find_charm(charm_args))
    charm_button.place(x=690, y=vert_pos - 2, width=90, height=26)

    # Заполнение атрибутов класса
    charm_args: Args = Args(
            title=tile_text,
            frame=frame,
            entry=charm_entry,
            button=charm_button
    )

    # Привязка обработчиков к элементам
    charm_entry.bind('<Return>', lambda _: charm_entry_escape(charm_args))
    charm_entry.bind('<Tab>', lambda _: charm_entry_escape(charm_args))

    # Разделитель
    vert_pos += 45

    separator: ttk.Frame = ttk.Frame(frame, height=1, style='Separator.TFrame')
    separator.place(x=20, y=vert_pos, width=760)

    # Кнопки Выбрать все / Очистить выбор
    vert_pos += 15

    set_btn = ttk.Button(frame, text='Выбрать все', style='Low.TButton', command=lambda: manage_marks(True))
    set_btn.place(x=20, y=vert_pos, width=100, height=24)

    clean_btn = ttk.Button(frame, text='Очистить все', style='Low.TButton', command=lambda: manage_marks(False))
    clean_btn.place(x=130, y=vert_pos, width=100, height=24)

    # Плагины с прогресс-барами
    vert_pos += 45

    ctx.plugins.clear()  # checked plugins
    ctx.progress.clear()  # progress_bar
    ctx.labels.clear()  # progress_label

    for plugin in ctx.plugins_pack:
        check_state: tk.BooleanVar = tk.BooleanVar(value=False)
        check_plugin: tk.Checkbutton = checkbox(frame, text=plugin['name'], variable=check_state, command=lambda: manage_marks())
        check_plugin.place(x=20, y=vert_pos)
        ctx.plugins.append(check_state)

        progress_bar: ttk.Progressbar = ttk.Progressbar(frame, orient='horizontal', length=430, mode='determinate', maximum=100)
        progress_bar.place(x=210, y=vert_pos + 2)
        ctx.progress.append(progress_bar)

        progress_label: ttk.Label = ttk.Label(frame, text='не выбран', font=('Arial', 11))
        progress_label.place(x=650, y=vert_pos)
        ctx.labels.append(progress_label)

        vert_pos += 40

    # Кнопки действий
    vert_pos += 10

    download_btn = ttk.Button(frame, text='Скачать', command=lambda: download_plugins(vpn_args))
    download_btn.place(x=135, y=vert_pos, width=175, height=26)
    install_btn = ttk.Button(frame, text='Установить', command=lambda: install_plugins(charm_args))
    install_btn.place(x=325, y=vert_pos, width=175, height=26)
    load_and_set_btn = ttk.Button(frame, text='Скачать и установить', command=lambda: load_and_set_plugins(vpn_args, charm_args))
    load_and_set_btn.place(x=515, y=vert_pos, width=175, height=26)


def manage_marks(option: bool | None = None) -> None:
    """
    Изменение информации в info_label при выборе или отмене выбора плагинов

    :param option:

    """
    if option is not None:
        [state.set(option) for state in ctx.plugins]

    for state, label in zip(ctx.plugins, ctx.labels):
        now_text: str = label.cget('text')

        if now_text not in ('выбран', 'не выбран'):
            continue

        label.config(text='выбран' if state.get() else 'не выбран')


# Функции для запуска VPN
def launch_vpn(exe_path: Path, vpn_args: Args) -> None:
    """
    Запускает VPN
S
    """
    lock_buttons(vpn_args.frame)

    success: bool = launch(exe_path)
    status: str = vpn_args.label.cget('text')

    if success:
        if status != 'VPN подключен':
            vpn_active(vpn_args)
            unlock_buttons(vpn_args.frame)
    else:
        lock_buttons(vpn_args.frame)
        show_faultbox(f'{vpn_args.title} :: Ошибка', 'Не удалось подключиться к VPN. Попробуйте ещё раз.', vpn_args.frame)

    return None


def is_exist_vpn(path_str: str) -> bool:
    """
    Проверяет, что путь указывает на существующий .exe или .bat файл.

    """
    path: Path = Path(path_str)
    return path.is_file() and path.suffix.lower() in {'.exe', '.bat'}


def vpn_entry_escape(vpn_args: Args) -> None:
    """
    Обрабатывает завершение ввода VPN вручную (Enter или Tab).

    """
    raw_path: str = vpn_args.entry.get().strip()
    vpn_path: str = resource_path(vpn_args.entry.get().strip())

    if not raw_path:
        return

    if not is_exist_vpn(vpn_path):
        vpn_args.entry.delete(0, tk.END)
        vpn_args.entry.insert(0, raw_path)
        vpn_args.frame.update_idletasks()
        show_faultbox(f'{vpn_args.title} :: Ошибка', 'Укажите корректный .exe или .bat файл для запуска VPN.', vpn_args.frame)
        return

    launch_vpn(Path(vpn_path), vpn_args)


def find_vpn(vpn_args: Args) -> None:
    """
    Отключает кнопку для блокировки повторных нажатий
    Показывает диалог для выбора исполняемого VPN-файла (.exe или .bat) и запускает его.

    """
    vpn_args.button.config(state='disabled')
    vpn_args.entry.delete(0, tk.END)

    vpn_path: str = filedialog.askopenfilename(
            initialdir=Path(resource_path('.')) / 'psiphon',
            title='Выберите исполняемый файл VPN',
            filetypes=[('Исполняемый файл', '*.exe'), ('Пакетный файл', '*.bat')]
    )

    if not vpn_path:
        show_faultbox(f'{vpn_args.title} :: Ошибка', 'Файл VPN не был выбран.', vpn_args.frame)
        # vpn_args.entry.insert(0, vpn_path)
        vpn_args.button.config(state='enabled')
        return

    vpn_args.entry.insert(0, vpn_path)
    vpn_args.button.config(state='enabled')
    vpn_args.frame.update_idletasks()
    launch_vpn(Path(vpn_path), vpn_args)


def vpn_active(vpn_args: Args) -> None:
    """
    Изменяет интерфейс при подключенном VPN.

    """
    vpn_args.entry.place_forget()
    vpn_args.button.place_forget()

    vpn_args.label.config(text='VPN подключен')
    resize(vpn_args.label, start_width=0, target_width=150, remove=False)
    vpn_args.frame.update_idletasks()


# Функции для установки пути к PyCharm на системном диске
def is_exist_path(path_str: str) -> bool:
    """
    Проверяет, что путь указывает на существующую папку

    """
    if not path_str:
        return False

    path: Path = Path(path_str)
    return path.exists()


def charm_entry_escape(charm_args: Args) -> None:
    """
    Обрабатывает завершение ввода пути к PyCharm вручную (Enter или Tab).

    """
    charm_path: str = charm_args.entry.get().strip()

    if not charm_path:
        return

    if not is_exist_path(charm_path):
        charm_args.entry.delete(0, tk.END)
        charm_args.entry.insert(0, charm_path)
        charm_args.frame.update_idletasks()
        show_faultbox(f'{charm_args.title} :: Ошибка', 'Укажите корректный путь к папке PyCharm на системном диске.', charm_args.frame)


def init_path() -> Path:
    """
    Путь к папке где находятся приложения JetBrains на системном диске
    Если папка JetBrains не найдена то папка в которой находится папка приложения

    """
    home_path: Path = Path.home() / 'AppData' / 'Roaming' / 'JetBrains'

    if home_path.exists():
        return home_path
    else:
        return Path(resource_path('.')).parent


def find_charm(charm_args: Args) -> None:
    """
    Отключает кнопку, показывает диалог выбора папки PyCharm и обрабатывает результат.

    """
    charm_args.button.config(state='disabled')
    charm_args.entry.delete(0, tk.END)

    charm_path: str = filedialog.askdirectory(
            initialdir=init_path(),
            title='Выберите папку PyCharm на системном диске'
    )

    if not charm_path:
        show_faultbox(f'{charm_args.title} :: Ошибка', 'Папка PyCharm не была выбрана.', charm_args.frame)
        # charm_args.entry.insert(0, charm_path)
        charm_args.button.config(state='enabled')
        return

    charm_args.entry.insert(0, charm_path)
    charm_args.button.config(state='enabled')
    charm_args.frame.update_idletasks()


# Проверки перед операциями Загрузить, Установить, Загрузить и Установить
# Download
def download_pass(vnp_args: Args) -> bool:
    """
    Проверки перед загрузкой plugins

    :param vnp_args:
           title=tile_text - название окна для вывода сообщений
           frame=frame - главный фрейм приложения
           label=vpn_label - отображает статус VPN
           entry=vpn_entry - поле для ввода пути к VPN
           button=vpn_button - кнопка для поиска пути к VPN

    """
    fault_message: str = ''
    status: bool = False

    if not is_vpn_connected():
        if vnp_args.label.cget('text') != 'VPN подключен':
            if not status:
                fault_message: str = 'VPN не подключен. Сначала подключите VPN.'
                status: bool = True

        elif vnp_args.label.cget('text') == 'VPN подключен':
            vpn_path: str = vnp_args.entry.get()

            if is_exist_vpn(vpn_path):
                launch_vpn(Path(vpn_path), vnp_args)

            else:
                if not status:
                    fault_message: str = 'Похоже вы отключили VPN. Перезапустите программу.'
                    status: bool = True

    if get_driver() is None:
        if not status:
            fault_message: str = 'В системе не найден браузер. Требуется Chrome, Firefox или Edge'
            status: bool = True

    if status:
        show_faultbox(f'{vnp_args.title} :: Ошибка', fault_message, vnp_args.frame)

    return status


def install_pass(charm_args: Args) -> bool:
    """
    Проверки перед установкой plugins

    :param charm_args:
           title=tile_text - название окна для вывода сообщений
           frame=frame - главный фрейм приложения
           entry=charm_entry - поле для ввода пути к папке PyCharm на системном диске
           button=charm_button - кнопка для поиска пути к папке PyCharm на системном диске

    """
    fault_message: str = ''
    status: bool = False

    pycharm_path: str = charm_args.entry.get().split('/')[-1]
    pattern_path: re.Pattern = re.compile(r'^pycharm[a-z.0-9]*$', flags=re.IGNORECASE)

    if charm_args.entry.get().strip() == '':
        if not status:
            fault_message: str = 'Папка PyCharm на системном диске не выбрана.'
            status: bool = True

    if not re.match(pattern_path, pycharm_path):
        if not status:
            fault_message: str = 'Похоже вы выбрали не ту папку. Эта папка не является папкой PyCharm. '
            status: bool = True

    if status:
        show_faultbox(f'{charm_args.title} :: Ошибка', fault_message, charm_args.frame)

    return status


def clear_sets() -> None:
    """
    Удаление информации из ctx.set

    """
    ctx.plugins_set.clear()
    ctx.progress_set.clear()
    ctx.labels_set.clear()


def make_sets(data_set: list[dict[str, Any] | BooleanVar], option: str = None) -> None:
    """
    Создание ctx.set по выбранным плагинам

    """
    if option.casefold() == 'id':
        for plugin in data_set:
            index = plugin['id'] - 1
            ctx.progress_set.append(ctx.progress[index])
            ctx.labels_set.append(ctx.labels[index])

    elif option.casefold() == 'boolean':
        for index, state in enumerate(data_set):
            if state.get():
                ctx.plugins_set.append(ctx.plugins_pack[index])
                ctx.progress_set.append(ctx.progress[index])
                ctx.labels_set.append(ctx.labels[index])


def download_plugins(vnp_args: Args) -> None:
    """
    Загрузка выбранных плагинов

    """
    escape: bool = download_pass(vnp_args)
    if escape:
        unlock_buttons(vnp_args.frame)
        return

    lock_buttons(vnp_args.frame)

    if all(not item.get() for item in ctx.plugins):
        unlock_buttons(vnp_args.frame)
        return

    clear_sets()

    _manager.add_task(make_sets, ctx.plugins, 'boolean')
    _manager.add_task(process_plugins, ctx)
    _manager.add_task(clean_plugins)
    _manager.add_task(download_files, ctx)
    _manager.add_task(update_files, ctx.plugins_set)

    _manager.wait_ready(vnp_args.frame, lambda: unlock_buttons(vnp_args.frame))


def install_plugins(charm_args: Args) -> None:
    """
    Установка всех загруженных плагинов

    """
    escape: bool = install_pass(charm_args)
    if escape:
        unlock_buttons(charm_args.frame)
        return

    lock_buttons(charm_args.frame)
    clear_sets()

    file_list: list[str] = get_download_list(ctx.plugins_pack)
    ctx.plugins_set = [{'id': plugin.get('id'), 'name': plugin.get('name'), 'file': plugin.get('file')} for plugin in ctx.plugins_pack if plugin.get('file') in file_list]

    _manager.add_task(make_sets, ctx.plugins_set, 'id')
    _manager.add_task(unpack_plugins, ctx)
    _manager.add_task(update_paths, ctx.plugins_set)
    _manager.add_task(setup_plugins, ctx, charm_args.entry.get())

    _manager.wait_ready(charm_args.frame, lambda: unlock_buttons(charm_args.frame))


# Скачивание и установка выбранных плагинов
def load_and_set_plugins(vnp_args: Args, charm_args: Args) -> None:
    """
    Загрузка и установка выбранных плагинов

    """
    escape: bool = any((download_pass(vnp_args), install_pass(charm_args)))
    if escape:
        unlock_buttons(charm_args.frame)
        return

    lock_buttons(vnp_args.frame)

    if all(not item.get() for item in ctx.plugins):
        unlock_buttons(vnp_args.frame)
        return

    clear_sets()

    _manager.add_task(make_sets, ctx.plugins, 'boolean')
    _manager.add_task(process_plugins, ctx)
    _manager.add_task(clean_plugins)
    _manager.add_task(download_files, ctx)
    _manager.add_task(update_files, ctx.plugins_set)
    _manager.add_task(unpack_plugins, ctx)
    _manager.add_task(update_paths, ctx.plugins_set)
    _manager.add_task(setup_plugins, ctx, charm_args.entry.get())

    _manager.wait_ready(charm_args.frame, lambda: unlock_buttons(charm_args.frame))


def on_close() -> None:
    """
    Завершение работы

    """
    _manager.stop(root_window)
    root_window.destroy()


if __name__ == '__main__':
    root_window: tk.Tk = tk.Tk()

    # Действия перед открытием главного окна и при его закрытии
    ctx.plugins_pack = fetch_plugin_pack()
    SafeWidgetPatcher.apply()
    root_window.protocol("WM_DELETE_WINDOW", on_close)

    # Главный цикл приложения
    set_window(root_window)
    root_window.mainloop()