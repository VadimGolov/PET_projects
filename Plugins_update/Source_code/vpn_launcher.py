import re
import time
import requests
import subprocess
from pathlib import Path

import pyautogui
import pygetwindow as getwin


# Url для проверки соединения
CHECK_IP_URL: str = 'https://ipwho.is/'

# Регулярное выражение для поиска окна с рекламой
REGEXP_PATH: re.Pattern = re.compile(r'^(freeip|futtiball|ip geolocation|psiphon news|speed test|persagg|перевести)', re.IGNORECASE)


def is_vpn_connected() -> bool:
    """
    Обращается к ipwho.is и проверяет страну в котрой находится IP-адрес.

    :return: True, если страна не Russia.

    """
    try:
        response: requests.Response = requests.get(CHECK_IP_URL, timeout=5)
        response.raise_for_status()

        country: str = response.json().get('country', '')
        return country.lower() != 'russia'

    except (requests.RequestException, ValueError):
        return False


def close_psiphon(psi_name: re.Pattern, timeout: int = 15, check_interval: float = 1) -> None:
    """
    Ожидает появления окна, имя которого соответствует REGEXP_PATH, и закрывает его.

    """
    stop_time: float = time.time() + timeout

    while time.time() <= stop_time:
        current_titles: list[str] = [title for title in getwin.getAllTitles() if title]

        for title in current_titles:
            if re.search(psi_name, title):
                windows = getwin.getWindowsWithTitle(title)
                for each_win in windows:
                    each_win.close()
                    return

        time.sleep(check_interval)


def run_psiphon(launch_path: Path) -> subprocess.Popen | None:
    """
    Запускает Psiphon в фоновом режиме и возвращает объект процесса.

    :param launch_path: Путь к исполняемому файлу Psiphon.
    :return: Объект процесса Popen.

    """
    psi_pattern: re.Pattern = re.compile(r'^psiphon', re.IGNORECASE)
    if re.search(psi_pattern, str(launch_path.name)):
        close_psiphon(psi_pattern)

    time.sleep(3)

    # Запускает Psiphon
    try:
        return subprocess.Popen(
            [str(launch_path)],
            cwd=str(launch_path.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def close_upper_window(initial_count: int, timeout: int, check_interval: float) -> None:
    """
    Ожидает появление нового окна и закрывает его комбинацией Ctrl+W.

    """
    stop_time: float = time.time() + timeout
    pyautogui.FAILSAFE = False

    while time.time() <= stop_time:
        current_titles: list[str] = [title for title in getwin.getAllTitles() if title]

        if len(current_titles) > initial_count:
            pyautogui.hotkey('ctrl', 'w')
            return
        time.sleep(check_interval)


def close_match_window(timeout: int, check_interval: float) -> None:
    """
    Ожидает появления окна, имя которого соответствует REGEXP_PATH, и закрывает его.

    """
    stop_time: float = time.time() + timeout

    while time.time() <= stop_time:
        current_titles: list[str] = [title for title in getwin.getAllTitles() if title]

        for title in current_titles:
            if re.search(REGEXP_PATH, title):
                windows = getwin.getWindowsWithTitle(title)
                for each_win in windows:
                    each_win.close()
                    return

        time.sleep(check_interval)


def close_advert_tab(timeout: int = 15, check_interval: float = 1) -> None:
    """
    Ждёт появления нового окна и закрывает его,
    Затем ищет закрывает окно, соответствующее REGEXP_PATH.

    :param timeout: Максимальное время ожидания (сек).
    :param check_interval: Интервал между проверками (сек).

    """
    # initial_titles: list[str] = [title for title in getwin.getAllTitles() if title]
    # initial_count: int = len(initial_titles)

    # close_upper_window(initial_count, timeout, check_interval)
    close_match_window(timeout, check_interval)


def force_focus(title: str) -> None:
    """
    Возобновляет окна и возвращает его в исходное состояние.

    :param title: Заголовок окна.

    """
    windows = getwin.getWindowsWithTitle(title)
    if windows:
        win = windows[0]
        win.minimize()
        time.sleep(0.1)  # дать системе время обработать сворачивание
        win.restore()
        win.activate()


def launch(launch_path: Path) -> bool:
    """
    Запускает VPN, проверяет подключение, закрывает рекламу

    :param launch_path:
    :return: Если все операции кроме закрытия рекламы успешны True иначе False
    """
    if run_psiphon(launch_path) is None:
        return False

    for _ in range(60):
        if is_vpn_connected():
            break
        time.sleep(2)
    else:
        return False

    psiphon_name = re.compile(r'^psiphon', re.IGNORECASE)

    if re.search(psiphon_name, str(launch_path.name)):
        close_advert_tab()
        force_focus(title='Обновление и установка plugins для PyCharm v1.0')

    return True


if __name__ == '__main__':
    pass