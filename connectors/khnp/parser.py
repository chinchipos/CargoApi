# chromedriver нужной версии можно скачать отсюда:
# https://googlechromelabs.github.io/chrome-for-testing/#stable

import io
import json
import os
import shutil
import time
import traceback
from datetime import datetime, date
from typing import Dict, Any

import selenium.webdriver as driver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from xls2xlsx import XLS2XLSX

from connectors.exceptions import KHNPParserError
from connectors.khnp.config import KHNP_URL, SYSTEM_USERNAME, SYSTEM_PASSWORD
from src.utils.log import ColoredLogger


class KHNPParser:

    # internal_error_msg = 'Внутренняя ошибка API.'

    def __init__(self, logger):
        self.logger = logger
        self.site = KHNP_URL

        # Убираем слэш в конце
        if self.site[-1] == '/':
            self.site = self.site[:-1]

        # Папка Chrome
        chrome_dir = os.getcwd() + '/selenium'

        # Папка для загрузок
        self.downloads_dir = os.getcwd() + '/downloads'

        options = driver.ChromeOptions()

        # Запуск без основного окна
        options.add_argument('--headless=new')

        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--unsafely-treat-insecure-origin-as-secure=http://clients.khnp.aoil.ru")

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
        chromedriver_path = os.getcwd() + '/chromedriver'

        # Стартуем webdriver
        self.driver = driver.Chrome(service=ChromeService(chromedriver_path), options=options)

        # Удаляем из браузера компрометирующие объекты
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        self.ac = ActionChains(self.driver)

    # def error(self, trace=None, message=None):
    #     if message:
    #         self.logger.error(message)

    #     if trace:
    #         self.logger.error(trace)

    #     return None

    def login(self) -> None:

        self.logger.info(f'Открываю главную страницу: {self.site}')
        self.driver.get(self.site)
        if 'login.html' in self.driver.current_url:
            try:
                # После открытия стартовой страницы сервер перенаправил на страницу авторизации
                self.logger.info(f'Сайт перенаправил на страницу авторизации.')

                self.logger.info('Ввожу логин.')
                login_input = WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.ID, 'LoginForm_username'))
                login_input.send_keys(SYSTEM_USERNAME)

                self.logger.info('Ввожу пароль.')
                password_input = WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.ID, 'LoginForm_password'))
                password_input.send_keys(SYSTEM_PASSWORD)

                self.logger.info('Устанавливаю опцию "запомнить меня на этом компьютере".')
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
                self.logger.error('Сбой авторизации.')
                self.logger.error(traceback.format_exc())
                raise KHNPParserError('Сбой авторизации.')

        elif 'info.html' in self.driver.current_url:
            pass

        else:
            error = 'Сбой авторизации'
            self.logger.error(error)
            self.logger.error(traceback.format_exc())
            raise KHNPParserError(error)

    def cards_page_open(self):
        try:
            self.logger.info(f'Открываю страницу "Информация по картам": {self.site}/card/info.html')
            self.driver.get(self.site + "/card/info.html")
            return {"success": True}

        except Exception:
            error = 'Не удалось открыть страницу "Информация по картам"'
            self.logger.error(error)
            self.logger.error(traceback.format_exc())
            raise KHNPParserError(error)

    """
    def messages_page_open(self):
        try:
            self.logger.info(f'Открываю страницу "Сообщения": {self.site}/messages.html.')
            self.driver.get(self.site + "/messages.html")
            return {"success": True}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось открыть страницу "Сообщения".')
            return {"success": False, "message": self.internal_error_msg}

    def get_balance(self):
        if 'info.html' not in self.driver.current_url:
            cards_page_open_result = self.cards_page_open()
            if not cards_page_open_result['success']:
                return {"success": False, "message": cards_page_open_result['message']}

        try:
            text = WebDriverWait(self.driver, 5).until(lambda x: x.find_element(By.CLASS_NAME, 'fund')).get_attribute(
                'innerText').replace("'", "").replace(" ", "").split(',')
            balance = text[0] + '.' + text[1][0:2]
            return {"success": True, "balance": balance}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось получить баланс.')
            return {"success": False, "message": self.internal_error_msg}

    def clear_card_filters(self):
        # Отображаем все карты (активные и заблокированные)
        try:
            state_changed = False
            self.logger.info('Убираю фильтрацию карт.')
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

            return {"success": True}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось убрать фильтрацию карт.')
            return {"success": False, "message": self.internal_error_msg}
    """

    def get_cards(self) -> Dict[str, Any]:
        if 'info.html' not in self.driver.current_url:
            self.cards_page_open()

            # Полный список карт уже структурирован и хранится в JS переменной. Получаем его.
            cards = self.driver.execute_script("return window.KHNP.userCards;")

            # Обрезаем единицу в конце каждого номера карты
            for card in cards:
                card['cardNo'] = card['cardNo'][:-1]

            return cards

    """
    def get_card_lock_element(self, card_num_tail, cards_all_block):
        try:
            # cards_all_block = WebDriverWait(self.driver, 5).until(lambda x: x.find_element(By.CSS_SELECTOR, 'article.cards-all'))
            if card_num_tail in cards_all_block.get_attribute('innerHTML'):
                container_table_block = WebDriverWait(cards_all_block, 5).until(
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
                        self.logger.info('Карта найдена.')
                        return {"success": True, "obj": card_lock_element}

            error = 'Карта не найдена.'
            self.error(message=error)
            return {"success": False, "message": error}

        except Exception:
            self.error(trace=traceback.format_exc(), message=self.internal_error_msg)
            return {"success": False, "message": self.internal_error_msg}

    def get_card_state_modal(self):
        try:
            modal = WebDriverWait(self.driver, 5).until(lambda x: x.find_element(By.ID, 'blockcard'))
            section = WebDriverWait(modal, 5).until(lambda x: x.find_element(By.CSS_SELECTOR, 'section.container'))
            modal_message = WebDriverWait(section, 5).until(
                lambda x: x.find_element(By.ID, 'card-operation')).get_attribute('innerText')
            return {"success": True, "modal": modal, "text": modal_message}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось сменить статус карты.')
            return {"success": False, "message": self.internal_error_msg}

    def get_card_state(self, card_num):
        get_cards_result = self.get_cards()
        if not get_cards_result['success']:
            return {"success": False, "message": get_cards_result['message']}

        cn = str(card_num)
        for card_data in get_cards_result['cards']:
            if card_data['cardNo'] == cn:
                if card_data['cardBlockRequest'] == 'block':
                    return {"success": True, "active": True}
                elif card_data['cardBlockRequest'] == 'cancelUnblock':
                    return {"success": True, "active": False}
                elif card_data['cardBlockRequest'] == 'unblock':
                    return {"success": True, "active": False}
                elif card_data['cardBlockRequest'] == 'cancelBlock':
                    return {"success": True, "active": True}
                elif card_data['cardBlockRequest'] == 'sent':
                    return {"success": False,
                            "message": "Сайт поставщика не позволяет выполнить запрос, так как еще не обработана \
                                предыдущая операция по смене статуса."
                            }

        return {"success": False, "message": "Не удалось определить статус карты."}

    def lock_card(self, params):
        if 'info.html' not in self.driver.current_url:
            cards_page_open_result = self.cards_page_open()
            if not cards_page_open_result['success']:
                return {"success": False, "message": cards_page_open_result['message']}

        try:
            # Получаем статус карты
            get_card_state_result = self.get_card_state(params['card_num'])
            if not get_card_state_result['success']:
                return {"success": False, "message": get_card_state_result['message']}

            # Отображаем на экране все карты
            clear_card_filters_result = self.clear_card_filters()
            if not clear_card_filters_result['success']:
                return {"success": False, "message": clear_card_filters_result['message']}

            # В зависимости от состояния карты выполняем необходимое действие
            if get_card_state_result['active']:
                # Блокируем
                # Выполняем поиск "замка", при нажатии на который можно заблокировать/разблокировать карту
                self.logger.info('Начинаю поиск "замка" карты.')
                cards_all_block = WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.CSS_SELECTOR, 'article.cards-all'))
                get_lock_element_result = self.get_card_lock_element(params['card_num'][-6:], cards_all_block)
                if get_lock_element_result['success']:
                    # Карта найдена
                    self.logger.info('Приступаю к блокировке.')
                    get_lock_element_result['obj'].click()
                    card_state_modal_result = self.get_card_state_modal()
                    if card_state_modal_result['success']:
                        footer = WebDriverWait(card_state_modal_result['modal'], 5).until(
                            lambda x: x.find_element(By.CSS_SELECTOR, 'footer.container'))
                        ok_btn = WebDriverWait(footer, 5).until(lambda x: x.find_element(By.CSS_SELECTOR, 'span.btn'))
                        ok_btn.click()
                        self.logger.info('Карта заблокирована.')
                        time.sleep(1)
                        return {"success": True}

                    else:
                        return {"success": False, "message": card_state_modal_result['message']}

                else:
                    return {"success": False, "message": get_lock_element_result['message']}
            else:
                # Ничего не делаем
                self.logger.info('Карта уже была заблокирована ранее. Прекращаю выполнение.')
                return {"success": True}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось заблокировать карту.')
            return {"success": False, "message": self.internal_error_msg}

    def bulk_lock_cards(self, params):
        cards = json.loads(params['cards'])
        if not cards:
            return {"success": True}

        if 'info.html' not in self.driver.current_url:
            cards_page_open_result = self.cards_page_open()
            if not cards_page_open_result['success']:
                return {"success": False, "message": cards_page_open_result['message']}

        try:
            # Отображаем на экране все карты
            clear_card_filters_result = self.clear_card_filters()
            if not clear_card_filters_result['success']:
                return {"success": False, "message": clear_card_filters_result['message']}

            cards_all_block = None
            if cards:
                cards_all_block = WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.CSS_SELECTOR, 'article.cards-all')
                )

            for card_num in cards:
                self.logger.info(f'Обработка карты {card_num}')
                # Получаем статус карты
                get_card_state_result = self.get_card_state(card_num)
                if not get_card_state_result['success']:
                    return {"success": False, "message": get_card_state_result['message']}

                # В зависимости от состояния карты выполняем необходимое действие
                if get_card_state_result['active']:
                    # Блокируем
                    # Выполняем поиск "замка", при нажатии на который можно заблокировать/разблокировать карту
                    self.logger.info('Начинаю поиск "замка" карты.')
                    get_lock_element_result = self.get_card_lock_element(card_num[-6:], cards_all_block)
                    if get_lock_element_result['success']:
                        # Карта найдена
                        self.logger.info('Приступаю к блокировке.')
                        get_lock_element_result['obj'].click()
                        card_state_modal_result = self.get_card_state_modal()
                        if card_state_modal_result['success']:
                            footer = WebDriverWait(card_state_modal_result['modal'], 5).until(
                                lambda x: x.find_element(By.CSS_SELECTOR, 'footer.container'))
                            ok_btn = WebDriverWait(footer, 5).until(
                                lambda x: x.find_element(By.CSS_SELECTOR, 'span.btn'))
                            ok_btn.click()
                            self.logger.info('Карта заблокирована.')
                            time.sleep(1)
                            return {"success": True}

                        else:
                            return {"success": False, "message": card_state_modal_result['message']}

                    else:
                        return {"success": False, "message": get_lock_element_result['message']}
                else:
                    # Ничего не делаем
                    self.logger.info('Карта уже была заблокирована ранее. Прекращаю выполнение.')
                    return {"success": True}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось заблокировать карту.')
            return {"success": False, "message": self.internal_error_msg}

    def unlock_card(self, params):
        if 'info.html' not in self.driver.current_url:
            cards_page_open_result = self.cards_page_open()
            if not cards_page_open_result['success']:
                return {"success": False, "message": cards_page_open_result['message']}

        try:
            # Получаем статус карты
            get_card_state_result = self.get_card_state(params['card_num'])
            if not get_card_state_result['success']:
                return {"success": False, "message": get_card_state_result['message']}

            # Отображаем на экране все карты
            clear_card_filters_result = self.clear_card_filters()
            if not clear_card_filters_result['success']:
                return {"success": False, "message": clear_card_filters_result['message']}

            # В зависимости от состояния карты выполняем необходимое действие
            if not get_card_state_result['active']:
                # Разблокируем
                # Выполняем поиск "замка", при нажатии на который можно заблокировать/разблокировать карту
                self.logger.info('Начинаю поиск "замка" карты.')
                cards_all_block = WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.CSS_SELECTOR, 'article.cards-all'))
                get_lock_element_result = self.get_card_lock_element(params['card_num'][-6:], cards_all_block)
                if get_lock_element_result['success']:
                    # Карта найдена
                    self.logger.info('Приступаю к разблокировке.')
                    get_lock_element_result['obj'].click()
                    card_state_modal_result = self.get_card_state_modal()
                    if card_state_modal_result['success']:
                        footer = WebDriverWait(card_state_modal_result['modal'], 5).until(
                            lambda x: x.find_element(By.CSS_SELECTOR, 'footer.container'))
                        ok_btn = WebDriverWait(footer, 5).until(lambda x: x.find_element(By.CSS_SELECTOR, 'span.btn'))
                        ok_btn.click()
                        self.logger.info('Карта разблокирована.')
                        time.sleep(1)
                        return {"success": True}

                    else:
                        return {"success": False, "message": card_state_modal_result['message']}

                else:
                    return {"success": False, "message": get_lock_element_result['message']}
            else:
                # Ничего не делаем
                self.logger.info('Карта уже была разблокирована ранее. Прекращаю выполнение.')
                return {"success": True}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось разблокировать карту.')
            return {"success": False, "message": self.internal_error_msg}

    def bulk_unlock_cards(self, params):
        cards = json.loads(params['cards'])
        if not cards:
            return {"success": True}

        if 'info.html' not in self.driver.current_url:
            cards_page_open_result = self.cards_page_open()
            if not cards_page_open_result['success']:
                return {"success": False, "message": cards_page_open_result['message']}

        try:
            # Отображаем на экране все карты
            clear_card_filters_result = self.clear_card_filters()
            if not clear_card_filters_result['success']:
                return {"success": False, "message": clear_card_filters_result['message']}

            cards_all_block = None
            if cards:
                cards_all_block = WebDriverWait(self.driver, 5).until(
                    lambda x: x.find_element(By.CSS_SELECTOR, 'article.cards-all')
                )

            for card_num in cards:
                self.logger.info(f'Обработка карты {card_num}')
                # Получаем статус карты
                get_card_state_result = self.get_card_state(card_num)
                if not get_card_state_result['success']:
                    return {"success": False, "message": get_card_state_result['message']}

                # В зависимости от состояния карты выполняем необходимое действие
                if not get_card_state_result['active']:
                    # Разблокируем
                    # Выполняем поиск "замка", при нажатии на который можно заблокировать/разблокировать карту
                    self.logger.info('Начинаю поиск "замка" карты.')
                    get_lock_element_result = self.get_card_lock_element(card_num[-6:], cards_all_block)
                    if get_lock_element_result['success']:
                        # Карта найдена
                        self.logger.info('Приступаю к разблокировке.')
                        get_lock_element_result['obj'].click()
                        card_state_modal_result = self.get_card_state_modal()
                        if card_state_modal_result['success']:
                            footer = WebDriverWait(card_state_modal_result['modal'], 5).until(
                                lambda x: x.find_element(By.CSS_SELECTOR, 'footer.container'))
                            ok_btn = WebDriverWait(footer, 5).until(
                                lambda x: x.find_element(By.CSS_SELECTOR, 'span.btn'))
                            ok_btn.click()
                            self.logger.info('Карта разблокирована.')
                            time.sleep(1)
                            return {"success": True}

                        else:
                            return {"success": False, "message": card_state_modal_result['message']}

                    else:
                        return {"success": False, "message": get_lock_element_result['message']}
                else:
                    # Ничего не делаем
                    self.logger.info('Карта уже была разблокирована ранее. Прекращаю выполнение.')
                    return {"success": True}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось разблокировать карту.')
            return {"success": False, "message": self.internal_error_msg}

    def set_limit(self, params):
        # В ЛК поставщика услуг нет функции установки лимита.
        # Лимит устанавливается путем направления соответствующего сообщения в текстовом произвольном
        # формате через ЛК.
        self.logger.info(f"Карта: {params['card_num']}")
        self.logger.info(f"Лимит: {params['limit']}")

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
            self.logger.info('Нажимаю кнопку "Направить сообщение".')
            article_reserve_btn = WebDriverWait(self.driver, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'article.reserve-btn'))
            div = WebDriverWait(article_reserve_btn, 5).until(lambda x: x.find_element(By.CSS_SELECTOR, 'div.small-3'))
            div.click()

            # Вставляем текст сообщения в форму
            self.logger.info('Вставляю текст сообщения в форму.')
            textarea = WebDriverWait(self.driver, 5).until(lambda x: x.find_element(By.ID, 'feedback_form_message_id'))
            textarea.send_keys(text)
            time.sleep(0.2)

            # Жмем кнопку "Отправить"
            self.logger.info('Нажимаю кнопку "Отправить".')
            form = WebDriverWait(self.driver, 5).until(lambda x: x.find_element(By.ID, 'feedback_form'))
            submit_btn = WebDriverWait(form, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'button[type="submit"]'))
            submit_btn.click()

            # Проверяем успешность отправки сообщения
            self.logger.info('Проверяю успешность отправки.')
            sections = form.find_elements(By.TAG_NAME, 'section')
            WebDriverWait(sections[3], 5).until(lambda x: x.is_displayed())

            return {"success": True}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось установить лимит по карте.')
            return {"success": False, "message": self.internal_error_msg}

    def select_all_cards(self):
        try:
            self.logger.info('Устанавливаю галку "выбрать все карты".')
            cards_all_block = WebDriverWait(self.driver, 5).until(lambda x: x.find_element(By.CLASS_NAME, 'cards-all'))
            container_table_block = WebDriverWait(cards_all_block, 5).until(
                lambda x: x.find_element(By.CLASS_NAME, 'table'))
            select_all_checkbox = WebDriverWait(container_table_block, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'input[name="all"]'))
            select_all_checkbox.click()
            self.logger.info('Жду отображения полного списка карт.')
            time.sleep(2)
            self.logger.info('Список сформирован.')
            return {"success": True}

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось установить галку "выбрать все карты".')
            return {"success": False, "message": self.internal_error_msg}

    def parse_transactions_report(self, excel, start_date: date):
        transactions = {}
        # min_date = date.today() - timedelta(days = int(params['days']))
        reading_card_data = False
        allowed_transaction_types = [
            "Дебет",
            "Кредит, возврат на карту",
            "Возмещение"
        ]
        try:
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

                        transaction_type = row[8].strip() if row[8] else None
                        if transaction_type not in allowed_transaction_types:
                            continue

                        card_num = str(row[0])[:-1]
                        t_date = row[9].strip() if row[9] else None
                        t_time = row[10].strip() if row[10] else None
                        date_time = datetime.strptime(t_date + ' ' + t_time,
                                                      "%d.%m.%Y %H:%M:%S") if t_date and t_time else None
                        liters_ordered = float(row[4]) if row[4] else 0.0
                        liters_received = float(row[5]) if row[5] else 0.0

                        transaction = dict(
                            azs=row[1].strip() if row[1] else None,
                            product_type=row[2].strip() if row[2] else None,
                            price=float(row[3]) if row[3] else 0.0,
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

        except Exception:
            self.error(trace=traceback.format_exc(), message='Не удалось обработать отчет по транзакциям.')
            return {"success": False, "message": self.internal_error_msg}

        return {"success": True, "transactions": transactions}

    def get_transactions(self, start_date: date, end_date: date = date.today()):
        if 'info.html' not in self.driver.current_url:
            cards_page_open_result = self.cards_page_open()
            if not cards_page_open_result['success']:
                return {"success": False, "message": cards_page_open_result['message']}
        try:
            # Отображаем на экране все карты
            clear_card_filters_result = self.clear_card_filters()
            if not clear_card_filters_result['success']:
                return {"success": False, "message": clear_card_filters_result['message']}

            # Ставим галку "Выбрать все"
            select_all_cards_result = self.select_all_cards()
            if not select_all_cards_result['success']:
                return {"success": False, "message": select_all_cards_result['message']}

            # Указываем дату начала периода
            start_date_str = start_date.strftime('%d.%m.%Y')
            end_date_str = end_date.strftime('%d.%m.%Y')
            days = (end_date - start_date).days
            self.logger.info(f"Запрашиваю данные за период с {start_date_str} по {end_date_str} ({days} дн).")
            script = "$('input[name=" + '"cards[startDate]"' + f"]').val('{start_date_str}');"
            self.driver.execute_script(script)
            script = "$('input[name=" + '"cards[endDate]"' + f"]').val('{end_date_str}');"
            self.driver.execute_script(script)

            # пересоздаем папку для загрузок
            if os.path.exists(self.downloads_dir):
                shutil.rmtree(self.downloads_dir)
            os.makedirs(self.downloads_dir)

            # Скачиваем сводный Excel файл
            self.logger.info('Приступаю к скачиванию файла отчета.')
            summary_article_block = WebDriverWait(self.driver, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'article.cards-total'))
            form = WebDriverWait(summary_article_block, 5).until(lambda x: x.find_element(By.TAG_NAME, 'form'))
            xls_download_btn = WebDriverWait(form, 5).until(
                lambda x: x.find_element(By.CSS_SELECTOR, 'button[value="xls"]'))
            xls_download_btn.click()

            def file_downloaded():
                listdir = os.listdir(self.downloads_dir)
                return listdir[0] if listdir and listdir[0].endswith('.xls') else False

            time.sleep(10)
            WebDriverWait(self.driver, 30).until(lambda x: file_downloaded())
            xls_filename = file_downloaded()
            self.logger.info(f'Файл скачан: {xls_filename}')

            # Скачанный файл в старом XLS формате. С ним неудобно работать. Преобразуем в XLSX.
            self.logger.info('Преобразование формата: XLS -> XLSX.')
            xls_filepath = self.downloads_dir + os.sep + xls_filename
            x2x = XLS2XLSX(xls_filepath)

            wb = x2x.to_xlsx()
            ws = wb.active
            excel = ws.values

            # Парсим содержимое файла
            self.logger.info('Начинаю парсинг содержимого файла, формирую JSON.')
            parse_transactions_report_result = self.parse_transactions_report(excel, start_date)
            if not parse_transactions_report_result['success']:
                return {"success": False, "message": parse_transactions_report_result['message']}

            self.logger.info('Парсинг выполнен, сформирован JSON.')
            return {"success": True, "transactions": parse_transactions_report_result['transactions']}

        except Exception:
            print('error')
            self.error(trace=traceback.format_exc(), message='Не удалось сформировать список карт.')
            return {"success": False, "message": self.internal_error_msg}
    """
