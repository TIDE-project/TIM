import os
import socket
import traceback
from base64 import b64decode
from io import BytesIO
from pprint import pprint
from typing import Union, List

import math
from urllib.parse import urlencode

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, ScreenshotException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import RemoteConnection
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from wand.exceptions import BaseError
from wand.image import Image

from timApp.document.docinfo import DocInfo
from timApp.tests.db.timdbtest import TEST_USER_1_NAME, TEST_USER_2_NAME, TEST_USER_3_NAME
from timApp.tests.server.timroutetest import TimRouteTest
from timApp.tests.timliveserver import TimLiveServer
from timApp.timdb.sqa import db
from timApp.user.user import Consent

PREV_ANSWER = 'answerbrowser .prevAnswer'


def ignore_timeout(func):
    def dec(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except socket.timeout:
            warn_about_socket_timeout()
    return dec


options = webdriver.ChromeOptions()
options.set_headless()
options.add_argument('--window-size=1024x768')

global_drv = webdriver.Remote(command_executor='http://chrome:4444/wd/hub',
                              desired_capabilities=options.to_capabilities())
global_drv.implicitly_wait(10)


class BrowserTest(TimLiveServer, TimRouteTest):
    login_dropdown_path = '//login-menu/user-menu/div/button'
    screenshot_dir = '/service/screenshots'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_screenshot_tolerance(self) -> float:
        return 5

    @property
    def drv(self):
        return global_drv

    def setUp(self):
        TimLiveServer.setUp(self)
        # options = webdriver.ChromeOptions()
        #
        # options.set_headless()
        # options.add_argument('--window-size=1024x768')
        RemoteConnection.set_timeout(15)  # according to experience, 10 is too low
        # try:
        #     self.drv = webdriver.Remote(command_executor=self.app.config['SELENIUM_REMOTE_URL'] + ':4444/wd/hub',
        #                                 desired_capabilities=options.to_capabilities())
        # except socket.timeout:
        #     self.skipTest('socket timeout occurred when trying to initialize webdriver')
        # self.drv.implicitly_wait(10)
        self.wait = WebDriverWait(self.drv, 15)

    def login_browser_as(self, email: str, password: str, name: str):
        self.client.__exit__(None, None, None)
        self.goto('')
        # self.save_screenshot('adsasd')
        elem = self.drv.find_element_by_xpath('//login-menu/button')
        elem.click()
        elem = self.find_element("login-dialog")
        elem.find_element_by_xpath("//input[@type='text']").send_keys(email)
        elem.find_element_by_xpath("//input[@type='password']").send_keys(password)
        elem.find_element_by_xpath("//button[@type='submit']").click()
        self.wait.until(ec.text_to_be_present_in_element((By.XPATH, self.login_dropdown_path), name))
        self.client.__enter__()

    def login_browser_quick_test1(self):
        """Logs testuser 1 in quickly by directly adding the session cookie to the browser."""
        self.goto("/empty")
        self.drv.delete_all_cookies()
        self.drv.add_cookie(
            {'class': 'org.openqa.selenium.Cookie',
             'domain': 'nginx',
             'expiry': 7544144177,
             'hCode': 1984987798,
             'httpOnly': True,
             'name': 'session',
             'path': '/',
             'secure': False,
             'value': 'eyJfcGVybWFuZW50Ijp0cnVlLCJhbmNob3IiOiIiLCJjYW1lX2Zyb20iOiIvIiwidXNlcl9pZCI6Mn0.DowETw.cyvyDZcvHWr2aKC5agfIW5sUVrU'})

    def login_browser_test1(self):
        """Logs in as Test user 1."""
        self.drv.delete_all_cookies()
        self.login_browser_as('test1@example.com', 'test1pass', TEST_USER_1_NAME)

    def login_browser_test2(self):
        """Logs in as Test user 2."""
        self.drv.delete_all_cookies()
        self.login_browser_as('test2@example.com', 'test2pass', TEST_USER_2_NAME)

    def login_browser_test3(self):
        """Logs in as Test user 3."""
        self.drv.delete_all_cookies()
        self.login_browser_as('test3@example.com', 'test3pass', TEST_USER_3_NAME)

    def get_browser_url(self):
        return self.app.config['SELENIUM_BROWSER_URL']

    def goto(self, url: str):
        """Navigates to a new URL using the browser.

        :param url: The URL to which to navigate. This must be relative.

        """
        url_ = f"{self.get_browser_url()}{url}"
        # raise Exception(url_)
        self.drv.get(url_)

    def print_console(self):
        logs = self.drv.get_log("browser")
        pprint(logs)

    def refresh(self):
        """Refreshes the current browser page."""
        self.drv.refresh()

    def save_screenshot(self, filename: str='screenshot'):
        """Saves the current browser screen to a PNG file in screenshots directory.

        :param filename: The file name of the PNG file.

        """

        os.makedirs(self.screenshot_dir, exist_ok=True)
        if not self.drv.save_screenshot(f'{self.screenshot_dir}/{filename}.png'):
            raise Exception('Screenshot failed')

    def save_element_screenshot(self, element: WebElement, filename_or_file: Union[str, BytesIO, None]=None,
                                move_to_element: bool = False) -> Image:
        """Saves the screenshot of an element to a PNG file.

        :return: The image object.
        :param element: The element to save.
        :param filename_or_file: Filename for the image without extension, a file object or None. If None, the image
         exists only in memory.
        :param move_to_element: Whether to move to the element before taking the screenshot. Use this if there is a
         possibility that the element is not in viewport.
        """
        if move_to_element:
            # It seems like move_to_element is no longer enough (at least in some cases)
            # to get the element fully visible, so we have to use JS.
            self.drv.execute_script("arguments[0].scrollIntoView();", element)
            # ActionChains(self.drv).move_to_element(element).perform()
        src_base64 = self.drv.get_screenshot_as_base64()
        im = Image(blob=b64decode(src_base64))

        x = element.location["x"]
        y = element.location["y"]
        w = element.size["width"]
        h = element.size["height"]
        if w == 0 or h == 0:
            raise ScreenshotException('Element width and height must not be 0')
        offset = int(self.drv.execute_script('return window.pageYOffset;'))
        y -= offset

        im.crop(
            left=math.floor(x),
            top=math.floor(y),
            width=math.ceil(w),
            height=math.ceil(h),
        )
        if isinstance(filename_or_file, str):
            self.save_im(im, filename_or_file)
        elif isinstance(filename_or_file, BytesIO):
            im.save(file=filename_or_file)
        return im

    def save_im(self, im, filename_or_file):
        os.makedirs(os.path.dirname(os.path.join(self.screenshot_dir, filename_or_file)), exist_ok=True)
        im.save(filename=f'{self.screenshot_dir}/{filename_or_file}.png')

    def assert_same_screenshot(self,
                               element: WebElement,
                               filename: Union[str, List[str]],
                               move_to_element: bool = False,
                               attempts=1):
        """Asserts that the provided element looks the same as in the provided screenshot.
        :param attempts: Number of comparison attempts.
        :param element: The element to check.
        :param filename: The filename of the expected screenshot.
        :param move_to_element: Whether to move to the element before taking the screenshot.
        """
        filenames = filename if isinstance(filename, list) else [filename]
        diff = None
        result = None
        fail_suffix = ''
        im = None
        f = None
        for i in range(attempts):
            if im:
                im.close()
            try:
                im = self.save_element_screenshot(element, move_to_element=move_to_element)
            except ScreenshotException:
                continue
            for f in filenames:
                try:
                    ref = Image(filename=f'tests/browser/expected_screenshots/{f}.png')
                except BaseError:
                    print(f'Expected screenshot not found, saving image to {f}.png')
                    im.save(filename=f'{self.screenshot_dir}/{f}.png')
                    im.close()
                    return
                im.fuzz = 300  # 250 is too low
                diff, result = im.compare(ref, metric='absolute')
                if result <= self.get_screenshot_tolerance():
                    im.close()
                    return
        if not f:
            raise Exception('Failed to get screenshot of element')
        self.save_im(im, f'{f}{fail_suffix}')
        im.close()
        self.save_im(diff, f'{f}{fail_suffix}_DIFF')
        diff.close()
        assert_msg = f'Screenshots did not match (diff value is {result}); ' \
                     f'failed screenshot saved to screenshots/{f}{fail_suffix} ' \
                     f'and difference to screenshots/{f}{fail_suffix}_DIFF'
        new_screenshots = 0  # change here 1 for generating new screenshots
        if new_screenshots == 0:
            self.assertTrue(False, msg=assert_msg)

    def should_not_exist(self, css_selector: str):
        """Asserts that the current document should not contain any elements that match the specified CSS selector.

        :param css_selector: The CSS selector to test.

        """
        self.drv.implicitly_wait(0.5)
        try:
            self.drv.find_element_by_css_selector(css_selector)
        except NoSuchElementException:
            pass
        else:
            self.assertTrue(False, f'Selector "{css_selector}" matched something.')
        finally:
            self.drv.implicitly_wait(10)

    def tearDown(self):
        TimLiveServer.tearDown(self)
        try:
            #self.drv.quit()
            pass
        except socket.timeout:
            pass

    def goto_document(self, d: DocInfo, view='view', query=None):
        params = ''
        if query:
            params = '?' + urlencode(query)
        self.goto(f'/{view}/{d.path}{params}')

    def wait_until_hidden(self, selector):
        self.drv.implicitly_wait(0.1)
        self.wait.until(ec.invisibility_of_element_located((By.CSS_SELECTOR, selector)))
        self.drv.implicitly_wait(10)

    def wait_until_present(self, selector):
        self.wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, selector)))
        self.wait.until(ec.visibility_of_element_located((By.CSS_SELECTOR, selector)))

    def wait_until_text_present(self, selector: str, text: str):
        self.wait.until(ec.text_to_be_present_in_element((By.CSS_SELECTOR, selector), text))

    def select_text(self, selector: str, start_offset: int, end_offset: int):
        self.drv.execute_script(f"""
        var range = document.createRange();
        var element = document.querySelector('{selector}').childNodes[0];
        range.setStart(element, {start_offset});
        range.setEnd(element, {end_offset});
        window.getSelection().addRange(range);
        """)

    def find_element_and_move_to(self, selector: str, times=1) -> WebElement:
        e = None
        for i in range(0, times):
            e = self.drv.find_element_by_css_selector(selector)
            ActionChains(self.drv).move_to_element(e).perform()
        return e

    def find_element(self, selector: str) -> WebElement:
        return self.drv.find_element_by_css_selector(selector)

    def find_element_avoid_staleness(self, selector: str, tries: int = 10, click=False) -> WebElement:
        while True:
            e = self.find_element(selector)
            try:
                if click:
                    e.click()
                else:
                    self.touch(e)
            except StaleElementReferenceException:
                tries -= 1
                if tries == 0:
                    raise
                continue
            else:
                return e

    def touch(self, e: WebElement):
        ActionChains(self.drv).move_to_element(e).perform()

    def wait_and_click(self, selector: str):
        self.wait.until(ec.element_to_be_clickable((By.CSS_SELECTOR, selector)))
        self.drv.find_element_by_css_selector(selector).click()

    def accept_consent(self):
        self.current_user.consent = Consent.CookieOnly
        db.session.commit()


def find_button_by_text(root: WebElement, text: str):
    return find_element_by_text(root, text, 'button')


def find_element_by_text(root: WebElement, text: str, element: str='*') -> WebElement:
    return root.find_element_by_xpath(f"//{element}[contains(text(),'{text}')]")


def find_by_ngmodel(element: WebElement, model: str, tagname='*') -> WebElement:
    return element.find_element_by_css_selector(f'{tagname}[ng-model="{model}"]')


def find_by_ngclick(element: WebElement, value: str, tagname='*') -> WebElement:
    return element.find_element_by_css_selector(f'{tagname}[ng-click="{value}"]')


def find_all_by_ngmodel(element: WebElement, model: str, tagname='*') -> List[WebElement]:
    return element.find_elements_by_css_selector(f'{tagname}[ng-model="{model}"]')


def warn_about_socket_timeout():
    print("WARNING: socket timeout occurred during test")
    traceback.print_exc()
