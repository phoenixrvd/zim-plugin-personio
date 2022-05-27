import sys
import re
import uuid
import json

from datetime import datetime, timedelta

from zim.config import ConfigDict
from zim.plugins import PluginClass
from zim.actions import action
from zim.formats import get_dumper
from zim.gui.pageview import PageViewExtension
from zim.gui.widgets import Dialog, ErrorDialog

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
        lines = get_dumper('plain').dump(self.pageview.page.get_parsetree())
        work_time = 0.0

        for line in lines:
            matches = re.search(r'@zp +(\d+(,\d+)?)', line.strip())
            if matches is not None:
                work_time += float(matches.group(1).replace(',', '.'))

        if work_time < .25:
            return

        date = '-'.join(self.pageview.page.source_file.pathnames[-3:]).rstrip('.txt')
        config = self.plugin.preferences
        ConfirmationDialog(self.pageview, config, date, work_time).run()


class ConfirmationDialog(Dialog):

    def __init__(self, parent: PageViewExtension, config: ConfigDict, date: str, time: float):
        self.parent = parent
        self.config = config
        self.date = date
        self.time = time

        Dialog.__init__(
            self,
            parent,
            title=_('Bitte den Eintrag überprüfen'),
            button=_('Alles korrekt. Jetzt Speichern')
        )

        self.add_text(_('Date: {0}').format(date))
        self.add_text(_('Time: {0:.2f}').format(time))

    def do_response_ok(self):
        try:
            Personio(self.config).login().track(self.date, self.time)
            return True
        except Exception as error:
            ErrorDialog(self, str(error)).run()

        return False


class Personio(object):
    url = 'https://'
    user = ''
    password = ''
    time_start = '7:30'
    hours_max = 4
    hours_pause = 1
    time_format = '%Y-%m-%d %H:%M'

    def __init__(self, config):
        self.__dict__.update(config)

        self.hours_max = float(self.hours_max)
        self.hours_pause = float(self.hours_pause)
        self.browser = webdriver.Firefox(firefox_binary="/opt/firefox/firefox-bin")

    def element(self, selector):
        return self.browser.find_element_by_css_selector(selector)

    def login(self):
        self.browser.get(self.url)

        WebDriverWait(self.browser, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'form'))
        )

        self.element('#email').send_keys(self.user)
        self.element('#password').send_keys(self.password)
        self.element('form [type=submit]').click()

        return self

    def track(self, date, hours):
        max_time = self.hours_max
        intervals = int(hours / max_time)
        date_time = "{date} {time}".format(date=date, time=self.time_start)
        employee_id = self.get_employee_id()
        payload = []

        start = datetime.strptime(date_time, self.time_format)
        for interval in range(0, intervals):
            end = start + timedelta(hours=max_time)
            payload.append(self.format_data(start, end, employee_id))
            start = end + timedelta(hours=self.hours_pause)

        remaining_time = hours % max_time
        if remaining_time > 0:
            end = start + timedelta(hours=remaining_time)
            payload.append(self.format_data(start, end, employee_id))

        self.submit_intervals(payload)

        return self

    def format_data(self, start, end, employee_id):
        js_date_format = '%Y-%m-%dT%H:%M:00Z'
        return {
            'id': str(uuid.uuid4()),
            'start': start.strftime(js_date_format),
            'end': end.strftime(js_date_format),
            'employee_id': employee_id,
            'comment': '',
            'project_id': None,
            'activity_id': None,
        }

    def get_employee_id(self):
        return self.browser.execute_script('return window.REDUX_INITIAL_STATE.bladeState.dashboard.absences.employeeId')

    def submit_intervals(self, data):
        entries = json.dumps(data)
        js = """window['@personio/request']
            .postJson( `/api/v1/attendances/periods`, {data})
            .catch((e) => alert(JSON.parse(e.message).error.message))""".format(data=entries)

        self.browser.execute_script(js)

