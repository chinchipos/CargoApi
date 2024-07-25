# CHROMEDRIVER НУЖНОЙ ВЕРСИИ МОЖНО СКАЧАТЬ ОТСЮДА:
# https://googlechromelabs.github.io/chrome-for-testing/#stable

import os
import sys
import time
from datetime import date, datetime

from typing import Dict, Any, List

import selenium.webdriver as driver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from xls2xlsx import XLS2XLSX

from src.config import ROOT_DIR
from src.connectors.khnp.exceptions import KHNPParserError, khnp_parser_logger as logger
from src.connectors.khnp.config import KHNP_URL, SYSTEM_USERNAME, SYSTEM_PASSWORD

from pathlib import Path


class KHNPParser:

    def __init__(self):
        self.site = KHNP_URL

        # Убираем слэш в конце
        if self.site[-1] == '/':
            self.site = self.site[:-1]

        # Папка Chrome
        chrome_dir = os.path.join(ROOT_DIR, 'selenium_profiles', 'khnp')
        if not os.path.exists(chrome_dir):
            os.makedirs(chrome_dir)

        # Папка для загрузок
        self.downloads_dir = os.path.join(str(Path.home()), 'Downloads')

        options = driver.ChromeOptions()

        # Запуск без основного окна
        options.add_argument('--headless=new')

        options.add_argument("--allow-running-insecure-content")
        options.add_argument(f"--unsafely-treat-insecure-origin-as-secure={KHNP_URL}")

        # Указываем папку пользователя Chrome для хранения настроек
        options.add_argument(f"user-data-dir={chrome_dir}")

        # Отключаем индикацию роботизированного режима
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Отключаем загрузку картинок
        image_preferences = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", image_preferences)

        # Задаем стратегию загрузки страниц
        options.page_load_strategy = 'eager'

        # Указываем путь к chromedriver
        if sys.platform == 'win32':
            chromedriver_path = os.path.join(ROOT_DIR, 'chromedriver.exe')
        else:
            chromedriver_path = os.path.join(ROOT_DIR, 'chromedriver')

        # Стартуем webdriver
        self.driver = driver.Chrome(service=ChromeService(chromedriver_path), options=options)

        # Удаляем из браузера компрометирующие объекты
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        self.ac = ActionChains(self.driver)

        self.cards = []
        self.cards_all_block = None

    def login(self) -> None:
        logger.info(f'Открываю главную страницу: {self.site}')
        self.driver.get(self.site)

        if 'info.html' in self.driver.current_url:
            return

        if 'login.html' in self.driver.current_url:
            try:
                # После открытия стартовой страницы сервер перенаправил на страницу авторизации
                logger.info(f'Сайт перенаправил на страницу авторизации.')

                logger.info('Ввожу логин.')
                login_input = WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.ID, 'LoginForm_username'))
                login_input.send_keys(SYSTEM_USERNAME)

                logger.info('Ввожу пароль.')
                password_input = WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.ID, 'LoginForm_password'))
                password_input.send_keys(SYSTEM_PASSWORD)

                logger.info('Устанавливаю опцию "запомнить меня на этом компьютере".')
                remember_me_checkbox = WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.ID, 'login_form_save_id'))
                remember_me_checkbox.click()

                login_btn = WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.CSS_SELECTOR, 'button[value="login"]'))
                login_btn.click()

                # Проверяем что мы попали в ЛК - ждем пока появится ссылка на выход из ЛК
                WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.CSS_SELECTOR, 'a[href="/logout.html"]'))

            except Exception:
                raise KHNPParserError(trace=True, message='Сбой авторизации')

        else:
            raise KHNPParserError(trace=False, message='Сбой авторизации')

    def get_balance(self) -> float:
        if 'info.html' not in self.driver.current_url:
            self.open_cards_page()

        try:
            text = (WebDriverWait(self.driver, 5).until(
                lambda x: x.find_element(By.CLASS_NAME, 'fund'))
                    .get_attribute('innerText')
                    .replace("'", "")
                    .replace(" ", "")
                    .split(',')
            )
            balance = text[0] + '.' + text[1][0:2]
            return float(balance)

        except Exception:
            raise KHNPParserError(trace=True, message='Не удалось получить баланс')

    def open_cards_page(self) -> None:
        try:
            logger.info(f'Открываю страницу "Информация по картам": {self.site}/card/info.html')
            self.driver.get(self.site + "/card/info.html")

        except Exception:
            raise KHNPParserError(trace=True, message='Не удалось открыть страницу "Информация по картам"')

    def get_cards(self) -> List[Dict[str, Any]]:
        if 'info.html' not in self.driver.current_url:
            self.open_cards_page()

        try:
            # Полный список карт уже структурирован и хранится в JS переменной. Получаем его.
            cards = self.driver.execute_script("return window.KHNP.userCards;")

            # Обрезаем единицу в конце каждого номера карты
            for card in cards:
                card['cardNo'] = card['cardNo'][:-1]

            return cards

        except Exception:
            raise KHNPParserError(trace=True, message='Не удалось получить список карт от поставщика услуг')

    def clear_card_filters(self) -> None:
        # Отображаем все карты (активные и заблокированные)
        try:
            state_changed = False
            logger.info('Убираю фильтрацию карт')
            filter_cards_form = WebDriverWait(self.driver, 5).until(
                lambda x: x.find_element(By.ID, 'filter_cards_form'))

            active_card_chbox_exists = filter_cards_form.find_elements(By.CSS_SELECTOR, 'input[name="active_card"]')
            if active_card_chbox_exists:
                active_card_chbox = WebDriverWait(filter_cards_form, 5).until(
                    lambda x: x.find_element(By.CSS_SELECTOR, 'input[name="active_card"]'))
                if active_card_chbox.is_selected():
                    active_card_chbox.click()
                    state_changed = True

            blocked_card_chbox_exists = filter_cards_form.find_elements(By.CSS_SELECTOR, 'input[name="block_card"]')
            if blocked_card_chbox_exists:
                blocked_card_chbox = WebDriverWait(filter_cards_form, 5).until(
                    lambda x: x.find_element(By.CSS_SELECTOR, 'input[name="block_card"]'))
                if blocked_card_chbox.is_selected():
                    blocked_card_chbox.click()
                    state_changed = True

            zero_balance_card_chbox = WebDriverWait(filter_cards_form, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'input[name="null_card"]'))
            if zero_balance_card_chbox.is_selected():
                zero_balance_card_chbox.click()
                state_changed = True

            if state_changed:
                time.sleep(1)

        except Exception:
            raise KHNPParserError(trace=True, message='Не удалось убрать фильтрацию карт')

    def select_all_cards(self) -> None:
        try:
            logger.info('Устанавливаю галку "выбрать все карты"')
            cards_all_block = WebDriverWait(self.driver, 5).until(lambda x: x.find_element(By.CLASS_NAME, 'cards-all'))
            container_table_block = WebDriverWait(cards_all_block, 5).until(
                lambda x: x.find_element(By.CLASS_NAME, 'table'))
            select_all_checkbox = WebDriverWait(container_table_block, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'input[name="all"]'))
            select_all_checkbox.click()
            logger.info('Жду отображения полного списка карт')
            time.sleep(2)
            logger.info('Список сформирован')

        except Exception:
            raise KHNPParserError(trace=True, message='Не удалось установить галку "выбрать все карты"')

    @staticmethod
    def parse_transactions_report(excel, start_date: date) -> Dict[str, Any]:
        reading_card_data = False
        allowed_transaction_types = [
            "Дебет",
            "Кредит, возврат на карту",
            "Возмещение"
        ]
        try:
            transactions = {}
            for row in excel:
                first_cell = str(row[0]).lower()
                if not reading_card_data and 'карта №' in first_cell:
                    # Со следующей строки начнутся транзакции
                    reading_card_data = True

                elif reading_card_data:
                    if 'итого' in first_cell:
                        # Данные по карте закончились
                        reading_card_data = False
                    else:
                        # Считываем транзакцию
                        transaction_date = datetime.strptime(row[9], "%d.%m.%Y").date()
                        if transaction_date < start_date:
                            continue

                        # Выполняем проверки, т.к. не все транзакции от поставщика услуг нужно принять
                        transaction_type = row[8].strip() if row[8] else None
                        if transaction_type not in allowed_transaction_types:
                            continue

                        azs = row[1].strip() if row[1] else None
                        if not azs:
                            continue

                        price = float(row[3]) if row[3] else 0.0
                        if not price:
                            continue

                        card_num = str(row[0])[:-1]

                        t_date = row[9].strip() if row[9] else None
                        if not t_date:
                            continue

                        t_time = row[10].strip() if row[10] else None
                        if not t_time:
                            continue

                        date_time = datetime.strptime(
                            t_date + ' ' + t_time, "%d.%m.%Y %H:%M:%S"
                        ) if t_date and t_time else None
                        liters_ordered = float(row[4]) if row[4] else 0.0
                        liters_received = float(row[5]) if row[5] else 0.0

                        transaction = dict(
                            azs=azs,
                            product_type=row[2].strip() if row[2] else None,
                            price=price,
                            liters_ordered=liters_ordered,
                            liters_received=liters_received,
                            fuel_volume=liters_ordered if transaction_type == 'Дебет' else liters_received,
                            money_request=float(row[6]) if row[6] else 0.0,
                            money_rest=float(row[7]) if row[7] else 0.0,
                            type=transaction_type,
                            date=t_date,
                            time=t_time,
                            date_time=date_time,
                        )
                        if card_num in transactions.keys():
                            transactions[card_num].append(transaction)
                        else:
                            transactions[card_num] = [dict(transaction)]

            return transactions

        except Exception:
            raise KHNPParserError(trace=True, message='Не удалось обработать отчет по транзакциям')

    def get_transactions(self, start_date: date, end_date: date = date.today()) -> Dict[str, Any]:
        if 'info.html' not in self.driver.current_url:
            self.open_cards_page()

        try:
            # Отображаем на экране все карты
            self.clear_card_filters()

            # Ставим галку "Выбрать все"
            self.select_all_cards()

            # Указываем дату начала периода
            start_date_str = start_date.strftime('%d.%m.%Y')
            end_date_str = end_date.strftime('%d.%m.%Y')
            days = (end_date - start_date).days

            # Получаем данные за период
            logger.info(f"Запрашиваю данные за период с {start_date_str} по {end_date_str} ({days} дн)")
            script = "$('input[name=" + '"cards[startDate]"' + f"]').val('{start_date_str}');"
            self.driver.execute_script(script)
            script = "$('input[name=" + '"cards[endDate]"' + f"]').val('{end_date_str}');"
            self.driver.execute_script(script)

            # Удаляем из папки загрузок все предыдущие отчеты
            files = [f for f in os.listdir(self.downloads_dir) if f.startswith('cards_details')]
            for filename in files:
                os.remove(os.path.join(self.downloads_dir, filename))

            # Скачиваем сводный Excel файл
            logger.info('Приступаю к скачиванию файла отчета')
            summary_article_block = WebDriverWait(self.driver, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'article.cards-total'))
            form = WebDriverWait(summary_article_block, 5).until(lambda x: x.find_element(By.TAG_NAME, 'form'))
            xls_download_btn = WebDriverWait(form, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'button[value="xls"]'))
            xls_download_btn.click()

            def file_downloaded():
                _files = [os.path.join(self.downloads_dir, f) for f in os.listdir(self.downloads_dir)
                          if f.startswith('cards_details') and f.endswith('xls')]
                if _files:
                    transactions_file = _files[0]
                    size1 = os.path.getsize(transactions_file)
                    time.sleep(1)
                    size2 = os.path.getsize(transactions_file)
                    return transactions_file if size2 == size1 else False

                else:
                    return False

            time.sleep(10)
            WebDriverWait(self.driver, 30).until(lambda x: file_downloaded())
            xls_filename = file_downloaded()
            logger.info(f'Файл скачан: {xls_filename}')

            # Скачанный файл в старом XLS формате. С ним неудобно работать. Преобразуем в XLSX.
            logger.info('Преобразование формата: XLS -> XLSX')
            xls_filepath = xls_filename
            x2x = XLS2XLSX(xls_filepath)

            wb = x2x.to_xlsx()
            ws = wb.active
            excel = ws.values

            # Парсим содержимое файла
            logger.info('Начинаю парсинг содержимого файла, формирую JSON')
            transactions = self.parse_transactions_report(excel, start_date)
            logger.info('Парсинг выполнен, сформирован JSON')

            for card_number, card_transactions in transactions.items():
                for card_transaction in card_transactions:
                    card_transaction['date_time'].replace(microsecond=0)

            return transactions

        except Exception:
            raise KHNPParserError(trace=True, message='Не удалось сформировать список карт')

    """
    def messages_page_open(self):
        try:
            khnp_logger.info(f'Открываю страницу "Сообщения": {self.site}/messages.html.')
            self.driver.get(self.site + "/messages.html")
            return {"success": True}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось открыть страницу "Сообщения".')
            return {"success": False, "message": self.internal_error_msg}
    """

    def get_card_lock_element(self, card_num: str) -> Any:
        card_num_tail = card_num[-6:]
        if not self.cards_all_block:
            self.cards_all_block = WebDriverWait(self.driver, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'article.cards-all')
            )
        try:
            # cards_all_block = WebDriverWait(self.driver, 5).until(
            # lambda x: x.find_element(By.CSS_SELECTOR, 'article.cards-all'))
            if card_num_tail in self.cards_all_block.get_attribute('innerHTML'):
                container_table_block = WebDriverWait(self.cards_all_block, 5).until(
                    lambda x: x.find_element(By.CSS_SELECTOR, 'section.table'))
                tbody = WebDriverWait(container_table_block, 5).until(lambda x: x.find_element(By.TAG_NAME, 'tbody'))
                tr_blocks = tbody.find_elements(By.CSS_SELECTOR, 'tr[class^="card_"]')
                for tr in tr_blocks:
                    td = tr.find_element(By.CSS_SELECTOR, 'td:nth-child(4)')
                    span = td.find_element(By.CSS_SELECTOR, 'span:nth-child(2)')
                    if card_num_tail in span.get_attribute('innerText'):
                        td = tr.find_element(By.CSS_SELECTOR, 'td:nth-child(3)')
                        card_lock_element = WebDriverWait(td, 5).until(
                            lambda x: x.find_element(By.CSS_SELECTOR, 'span.blockcard'))
                        logger.info(f'{card_num} | Замок найден')
                        return card_lock_element

        except Exception as e:
            raise KHNPParserError(trace=True, message=str(e))

    def get_card_state_modal(self) -> Any:
        try:
            modal = WebDriverWait(self.driver, 5).until(lambda x: x.find_element(By.ID, 'blockcard'))
            section = WebDriverWait(modal, 5).until(lambda x: x.find_element(By.CSS_SELECTOR, 'section.container'))
            modal_message = WebDriverWait(section, 5).until(
                lambda x: x.find_element(By.ID, 'card-operation')).get_attribute('innerText')
            return modal

        except Exception:
            raise KHNPParserError(trace=True, message='Не удалось сменить статус карты')

    def is_card_active(self, card_num: str) -> bool:
        if not self.cards:
            self.cards = self.get_cards()

        for card_data in self.cards:
            if card_data['cardNo'] == card_num:
                if card_data['cardBlockRequest'] == 'block' or card_data['cardBlockRequest'] == 'cancelBlock':
                    return True
                elif card_data['cardBlockRequest'] == 'cancelUnblock' or card_data['cardBlockRequest'] == 'unblock':
                    return False
                elif card_data['cardBlockRequest'] == 'sent':
                    logger.info("Сайт поставщика не позволяет выполнить запрос, так как еще не обработана "
                                f"предыдущая операция по смене статуса карты {card_num}")
                    return False

        logger.info(f"Не удалось определить статус карты {card_num}")
        return False

    def _change_card_state(self, card_num) -> None:
        logger.info(f'{card_num} | Начинаю поиск "замка" карты')
        card_lock_element = self.get_card_lock_element(card_num)

        # Карта найдена
        card_lock_element.click()
        card_state_modal = self.get_card_state_modal()

        footer = WebDriverWait(card_state_modal, 5).until(
            lambda x: x.find_element(By.CSS_SELECTOR, 'footer.container')
        )
        ok_btn = WebDriverWait(footer, 5).until(lambda x: x.find_element(By.CSS_SELECTOR, 'span.btn'))
        ok_btn.click()

    def _lock_card(self, card_num: str) -> None:
        logger.info(f'{card_num} | Получена задача на блокировку')

        # Получаем статус карты
        card_active = self.is_card_active(card_num)

        # В зависимости от состояния карты выполняем необходимое действие
        if not card_active:
            logger.info(f'{card_num} | Карта уже была заблокирована ранее')
            return None

        # Блокируем
        # Выполняем поиск "замка", при нажатии на который можно заблокировать/разблокировать карту
        self._change_card_state(card_num)
        logger.info(f'{card_num} | Карта заблокирована')
        time.sleep(1)

    def bulk_lock_cards(self, card_numbers: List[str]) -> None:
        if not card_numbers:
            return None

        if 'info.html' not in self.driver.current_url:
            self.open_cards_page()

        # Отображаем на экране все карты
        self.clear_card_filters()

        for card_num in card_numbers:
            self._lock_card(card_num)

    def _unlock_card(self, card_num: str) -> None:
        logger.info(f'{card_num} | Получена задача на разблокировку')

        # Получаем статус карты
        card_active = self.is_card_active(card_num)

        # В зависимости от состояния карты выполняем необходимое действие
        if card_active:
            logger.info(f'{card_num} | Карта уже была раззаблокирована ранее')
            return None

        # Разблокируем
        # Выполняем поиск "замка", при нажатии на который можно заблокировать/разблокировать карту
        self._change_card_state(card_num)
        logger.info(f'{card_num} | Карта разблокирована')
        time.sleep(1)

    def bulk_unlock_cards(self, card_numbers: List[str]) -> None:
        if not card_numbers:
            return None

        if 'info.html' not in self.driver.current_url:
            self.open_cards_page()

        # Отображаем на экране все карты
        self.clear_card_filters()

        for card_num in card_numbers:
            self._unlock_card(card_num)

    """
    def set_limit(self, params):
        # В ЛК поставщика услуг нет функции установки лимита.
        # Лимит устанавливается путем направления соответствующего сообщения в текстовом произвольном
        # формате через ЛК.
        khnp_logger.info(f"Карта: {params['card_num']}")
        khnp_logger.info(f"Лимит: {params['limit']}")

        # Открываем страницу "Сообщения"
        if '/messages.html' not in self.driver.current_url:
            messages_page_open_result = self.messages_page_open()
            if not messages_page_open_result['success']:
                return {"success": False, "message": messages_page_open_result['message']}

        try:
            # Считываем файл с шаблоном текста
            with io.open(os.getcwd() + '/letter_templates/set_limit.txt', encoding='utf-8') as file:
                text = file.read().replace("{card_num}", params['card_num']).replace("{limit}", params['limit'])

            # Жмем кнопку "Направить сообщение"
            khnp_logger.info('Нажимаю кнопку "Направить сообщение".')
            article_reserve_btn = WebDriverWait(self.driver, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'article.reserve-btn'))
            div = WebDriverWait(article_reserve_btn, 5).until(lambda x: x.find_element(By.CSS_SELECTOR, 'div.small-3'))
            div.click()

            # Вставляем текст сообщения в форму
            khnp_logger.info('Вставляю текст сообщения в форму.')
            textarea = WebDriverWait(self.driver, 5).until(lambda x: x.find_element(By.ID, 'feedback_form_message_id'))
            textarea.send_keys(text)
            time.sleep(0.2)

            # Жмем кнопку "Отправить"
            khnp_logger.info('Нажимаю кнопку "Отправить".')
            form = WebDriverWait(self.driver, 5).until(lambda x: x.find_element(By.ID, 'feedback_form'))
            submit_btn = WebDriverWait(form, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'button[type="submit"]'))
            submit_btn.click()

            # Проверяем успешность отправки сообщения
            khnp_logger.info('Проверяю успешность отправки.')
            sections = form.find_elements(By.TAG_NAME, 'section')
            WebDriverWait(sections[3], 5).until(lambda x: x.is_displayed())

            return {"success": True}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось установить лимит по карте.')
            return {"success": False, "message": self.internal_error_msg}
    """
