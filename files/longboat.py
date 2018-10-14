# -*- coding: utf-8 -*-

# DO NOT CHANGE THIS FILE!
# Changes will be overwritten on: boat pull
#
# Enable the plugin by adding it to ansible.cfg's [defaults] section:
#
#     callback_whitelist = longboat
#

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

DOCUMENTATION = '''
    callback: longboat
    type: aggregate
    short_description: Sends task results to Longboat
    author: "Lasse Brandt <contact@longboat.io>"
    description:
      - This callback plugin will send task results as JSON formatted events to Longboat.
      - Credit to "Stuart Hirst" for source upon which this is based.
    requirements:
      - Whitelisting this callback plugin
'''

EXAMPLES = '''
examples: >
  To enable, add this to your ansible.cfg file in the defaults block
    [defaults]
    callback_whitelist = longboat
'''

import os
import json
import uuid
import socket
import getpass

from subprocess import Popen, PIPE, STDOUT

from datetime import datetime
from os.path import basename

from ansible.plugins.callback import CallbackBase
from ansible.module_utils.urls import open_url

class LongboatCollectorSource(object):
    def __init__(self):
        self.ansible_check_mode = False
        self.ansible_playbook = ""
        self.ansible_version = ""
        self.session = str(uuid.uuid4())

    def send_event(self, state, result, runtime):
        if result._task_fields['args'].get('_ansible_check_mode') is True:
            self.ansible_check_mode = True

        if result._task_fields['args'].get('_ansible_version'):
            self.ansible_version = \
                result._task_fields['args'].get('_ansible_version')

        if result._task._role:
            ansible_role = str(result._task._role)
        else:
            ansible_role = None

        data = {}
        data['uuid'] = result._task._uuid
        data['session'] = self.session
        data['status'] = state
        data['timestamp'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S '
                                                       '+0000')
        data['runtime'] = runtime
        data['ansible_version'] = self.ansible_version
        data['ansible_check_mode'] = self.ansible_check_mode
        data['ansible_host'] = result._host.name
        data['ansible_playbook'] = self.ansible_playbook
        data['ansible_role'] = ansible_role
        data['ansible_task'] = result._task_fields
        data['ansible_result'] = result._result

        jsondata = json.dumps(data, sort_keys=True)

        proc = Popen([os.environ['LONGBOAT_CLI'] + '/boat','collect'], stdout=PIPE, stdin=PIPE, stderr=STDOUT)
        (stdout_data, stderr_data) = proc.communicate(input=jsondata)
        if proc.returncode > 0:
            print(stdout_data)

class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'longboat'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self, display=None):
        super(CallbackModule, self).__init__(display=display)
        self.start_datetimes = {}  # Collect task start times
        self.longboat = LongboatCollectorSource()

    def _runtime(self, result):
        return (
            datetime.utcnow() -
            self.start_datetimes[result._task._uuid]
        ).total_seconds()

    def set_options(self, task_keys=None, var_options=None, direct=None):
        super(CallbackModule, self).set_options(task_keys=task_keys, var_options=var_options, direct=direct)

    def v2_playbook_on_start(self, playbook):
        self.longboat.ansible_playbook = basename(playbook._file_name)

    def v2_playbook_on_task_start(self, task, is_conditional):
        self.start_datetimes[task._uuid] = datetime.utcnow()

    def v2_playbook_on_handler_task_start(self, task):
        self.start_datetimes[task._uuid] = datetime.utcnow()

    def v2_runner_on_ok(self, result, **kwargs):
        self.longboat.send_event(
            'OK',
            result,
            self._runtime(result)
        )

    def v2_runner_on_skipped(self, result, **kwargs):
        self.longboat.send_event(
            'SKIPPED',
            result,
            self._runtime(result)
        )

    def v2_runner_on_failed(self, result, **kwargs):
        self.longboat.send_event(
            'FAILED',
            result,
            self._runtime(result)
        )

    def runner_on_async_failed(self, result, **kwargs):
        self.longboat.send_event(
            'FAILED',
            result,
            self._runtime(result)
        )

    def v2_runner_on_unreachable(self, result, **kwargs):
        self.longboat.send_event(
            'UNREACHABLE',
            result,
            self._runtime(result)
        )

    def v2_playbook_on_stats(self, stats):
        self._display.display("https://gorm.longboat.io/logbook/session/" + self.longboat.session)

