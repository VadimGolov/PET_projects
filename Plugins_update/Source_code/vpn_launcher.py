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


def run_vpn(launch_path: Path) -> subprocess.Popen | None:
    """
    Запускает Psiphon в фоновом режиме и возвращает объект процесса.

    :param launch_path: Путь к исполняемому файлу Psiphon.
    :return: Объект процесса Popen.

    """
    try:
        return subprocess.Popen(
            [str(launch_path)],
            cwd=str(launch_path.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def close_psiphon(pattern: re.Pattern) -> None:
    """
    Закрывает Psiphon, если он открыт.

    """
    current_titles: list[str] = [title for title in getwin.getAllTitles() if title]

    for title in current_titles:
        for win in getwin.getWindowsWithTitle(title):
            if re.match(pattern, win.title):
                win.close()
                return


def close_match(pattern: re.Pattern, timeout: int, check_interval: float) -> None:
    """
    Ожидает появления окна с рекламой и закрывает его.

    """
    stop_time: float = time.time() + timeout

    while time.time() <= stop_time:
        current_titles: list[str] = [title for title in getwin.getAllTitles() if title]

        for title in current_titles:
            for win in getwin.getWindowsWithTitle(title):
                if re.search(pattern, win.title):
                    win.close()
                    return

        time.sleep(check_interval)


def launch(launch_path: Path) -> bool:
    """
    Запускает VPN, проверяет подключение, закрывает рекламу

    :param launch_path:
    :return: Если все операции кроме закрытия рекламы успешны True иначе False
    """
    vpn_name: re.Pattern = re.compile(r'^psiphon', re.IGNORECASE)
    psi_true: bool = True if re.match(vpn_name, str(launch_path.name)) else False

    if psi_true:
        close_psiphon(vpn_name)

    if run_vpn(launch_path) is None:
        return False

    for _ in range(30):
        if is_vpn_connected():
            break
        time.sleep(2)
    else:
        return False

    if psi_true:
        close_match(REGEXP_PATH, 15, 1)

    return True


if __name__ == '__main__':
    pass