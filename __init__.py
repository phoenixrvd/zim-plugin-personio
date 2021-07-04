import sys
import time
import re
import datetime

from datetime import datetime, timedelta
from pathlib import Path

from zim.plugins import PluginClass
from zim.actions import action
from zim.formats import get_dumper
from zim.gui.pageview import PageViewExtension

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    webdriver = None


class PersonioPlugin(PluginClass):
    plugin_info = {
        'name': _('Personio'),  # T: plugin name
        'description': _('Basic integration of personio time tracking.'),  # T: plugin description
        'author': 'Viacheslav Wolf',
        'help': 'Plugins:00 Personio',
    }

    plugin_preferences = (
        ('url', 'string', _('URL'), 'https://'),  # T: Label for plugin preference
        ('user', 'string', _('Login'), ''),  # T: Label for plugin preference
        ('password', 'password', _('Password'), ''),  # T: Label for plugin preference
        ('time_start', 'string', _('Time start'), '7:30'),  # T: Label for plugin preference
        ('hours_max', 'string', _('Max hours without pause'), '4'),  # T: Label for plugin preference
        ('hours_pause', 'string', _('Pause time'), '1'),  # T: Label for plugin preference
    )

    @classmethod
    def check_dependencies(cls):
        sys_python_version = sys.version_info[0] >= 3
        return bool(sys_python_version and webdriver), [
            ('python3', sys_python_version, True),
            ('selenium', webdriver is not None, True),
        ]


class PersonioTimeTrackExtension(PageViewExtension):

    @action(_('_Zeiten nach Personio übertragen'), accelerator='<Control><Shift>H', menuhints='tools')  # T: Menu item
    def on_submit_time_for_personio(self):
        lines = get_dumper('plain').dump(self.pageview.get_parsetree())
        work_time = 0.0

        for line in lines:
            matches = re.search(r'@zp +(\d+(,\d+)?)', line.strip())
            if matches is not None:
                work_time += float(matches.group(1).replace(',', '.'))

        if work_time < .25:
            return

        date = '-'.join(self.pageview.get_page().source_file.pathnames[-3:]).rstrip('.txt')
        config = self.plugin.preferences
        Personio(config) \
            .start() \
            .login() \
            .track(date, work_time)


class CssPaths:
    EMAIL = '#email'
    PASSWORD = '#password'
    SUBMIT_LOGIN_BUTTON = 'form [type=submit]'


class Personio(object):
    config = {
        'plugin_path': Path(__file__).parent.resolve(),
        'url': 'https://',
        'user': '',
        'password': '',
        'time_start': '7:30',
        'hours_max': 4,
        'hours_pause': 1,
        'time_format': '%Y-%m-%d %H:%M',
    }

    def __init__(self, config):
        self.config = {**self.config, **config}
        self.config['hours_max'] = float(self.config['hours_max'])
        self.config['hours_pause'] = float(self.config['hours_pause'])
        self.browser = None

    def start(self):
        self.browser = webdriver.Firefox()
        self.open(self.config['url'], CssPaths.EMAIL)

        return self

    def open(self, uri, waite_for):
        self.browser.get(uri)

        WebDriverWait(self.browser, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, waite_for))
        )

        return self

    def element(self, selector):
        return self.browser.find_element_by_css_selector(selector)

    def login(self):
        self.element(CssPaths.EMAIL).send_keys(self.config['user'])
        self.element(CssPaths.PASSWORD).send_keys(self.config['password'])
        self.element(CssPaths.SUBMIT_LOGIN_BUTTON).click()

        return self

    def track_interval(self, start, end):
        time.sleep(.5)
        js_path = "{dir}/{file}".format(dir=self.config['plugin_path'], file='inject.js')
        js_date_format = '%Y-%m-%dT%H:%M:00Z'
        js = Path(js_path) \
            .read_text() \
            .replace('{', '{{') \
            .replace('/%', '{') \
            .replace('}', '}}') \
            .replace('%/', '}') \
            .format(start=start.strftime(js_date_format), end=end.strftime(js_date_format))

        self.browser.execute_script(js)

    def track(self, date, hours):
        max_time = self.config['hours_max']
        pause = self.config['hours_pause']
        intervals = int(hours / max_time)
        rest_time = hours % max_time
        date_time = "{date} {time}".format(date=date, time=self.config['time_start'])
        start = datetime.strptime(date_time, self.config['time_format'])

        for interval in range(0, intervals):
            end = start + timedelta(hours=max_time)
            self.track_interval(start, end)
            start = end + timedelta(hours=pause)

        end = start + timedelta(hours=rest_time)
        self.track_interval(start, end)

        return self
