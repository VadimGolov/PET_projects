from typing import TYPE_CHECKING

import re
import requests
from tkinter import ttk

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

if TYPE_CHECKING:
    from gui_support import GuiContext


def get_driver() -> WebDriver | None:
    """
    Возвращает WebDriver Chrome, Firefox или Edge c headless-режимом.

    """
    browsers = [
        ('Chrome', webdriver.Chrome),
        ('Firefox', webdriver.Firefox),
        ('Edge', webdriver.Edge),
    ]

    for browser_name, driver in browsers:
        try:
            options = getattr(webdriver, f'{browser_name}Options')()
            options.add_argument('--headless')
            return driver(options=options)
        except WebDriverException:
            continue

    return None


def file_properties(url: str) -> tuple[str | None, int | None]:
    """
    Делает HEAD-запрос и для определения имени файла и размера файла.
    Возвращает (file_name и file_size) или (None, None) если не удалось.

    """
    try:
        response: requests.Response = requests.head(url, allow_redirects=True, timeout=10)
        response.raise_for_status()

        # Размер файла
        file_size: str | None = response.headers.get('Content-Length')
        file_size: int | None = int(file_size) if file_size and file_size.isdigit() else None

        # Имя файла
        disposition: str = response.headers.get('Content-Disposition')
        file_name: str | None = None
        if disposition:
            match: re.Match | None = re.search(r'filename="?([^"]+)"?', disposition)
            if match:
                file_name: str = match.group(1)

        return file_name, file_size

    except requests.RequestException:
        return None, None


# Функции интерфейса

def seek_label(context: 'GuiContext', index: int) -> None:
    """
    Выводит в info_label сообщение о поиске ссылки.

    """
    label: ttk.Label = context.labels_set[index]
    label.config(text='поиск ссылки...')


def found_label(context: 'GuiContext', index: int, option: bool) -> None:
    """
    Выводит в info_label сообщение найдена или не найдена ссылка.

    """
    label: ttk.Label = context.labels_set[index]
    message: str = 'ссылка найдена' if option else 'ссылка не найдена'
    label.config(text=message)


# Управляющая функция
def process_plugins(context: 'GuiContext') -> None:
    """
    Добавляет данные в список плагинов (ссылка для загрузки, имя и размер файла)
    Функция обрабатывает плагины из списка, и записывает информацию исходныЙ словарь:
    context.plugins_set c ключами 'download_url', 'file' и 'file_size'.

    :param context: контекст ctx из Update_GUI

    """
    driver: WebDriver = get_driver()

    try:
        for index, plugin in enumerate(context.plugins_set):
            url = plugin['url']

            seek_label(context, index)
            driver.get(url)

            try:
                wait = WebDriverWait(driver, 20)
                download: WebElement = wait.until(expected_conditions.presence_of_element_located((By.XPATH, '//a[contains(@href, "/plugin/download")]')))

                download_url: str = download.get_attribute('href')
                file_name, file_size = file_properties(download_url)

                if file_name is not None and file_size is not None:
                    plugin['download_url'] = download_url
                    plugin['file'] = file_name
                    plugin['file_size'] = file_size

                    found_label(context, index, True)
                else:
                    found_label(context, index, False)

            except (TimeoutException, NoSuchElementException, WebDriverException):
                found_label(context, index, False)

    finally:
        driver.quit()
    return None


if __name__ == '__main__':
    pass