#!/usr/bin/env python
# -*- coding: utf-8 -*-

import optparse
import copy
import sys
import os
import requests
import socket
import json
import syslog

from supervisor import childutils
from supervisor_eventflapping.process_state_monitor import ProcessStateMonitor


class ExitedSendToZabbix(ProcessStateMonitor):
    process_state_events = ['PROCESS_STATE_EXITED']

    def __init__(self, **kwargs):
        syslog.syslog('Eventflapping process started')
        ProcessStateMonitor.__init__(self, **kwargs)
        self.hostname = socket.getfqdn()
        # We get settings from ENV
        self.newrelic_url = os.environ.get('NEWRELIC_URL')
        self.newrelic_headers = {'X-Insert-Key': os.environ.get('NEWRELIC_KEY')}
        self.newrelic_event_type = os.environ.get('NEWRELIC_EVENT_TYPE')

    @classmethod
    def _get_opt_parser(cls):
        parser = optparse.OptionParser()
        parser.add_option("-i", "--interval", dest="interval", type="float", default=1.0,
                          help="batch interval in minutes")

        return parser

    @classmethod
    def parse_cmd_line_options(cls):
        parser = cls._get_opt_parser()
        (options, args) = parser.parse_args()
        return options

    @classmethod
    def validate_cmd_line_options(cls, options):
        # TBD different validations
        # of commandline settings
        parser = cls._get_opt_parser()
        validated = copy.copy(options)
        return validated

    @classmethod
    def get_cmd_line_options(cls):
        return cls.validate_cmd_line_options(cls.parse_cmd_line_options())

    @classmethod
    def create_from_cmd_line(cls):
        options = cls.get_cmd_line_options()

        if not 'SUPERVISOR_SERVER_URL' in os.environ:
            sys.stderr.write('Must run as a supervisor event listener\n')
            sys.exit(1)

        return cls(**options.__dict__)

    def get_process_state_change_msg(self, headers, payload):
        # Pheader example
        # 2019-03-14 21:16:15,376 DEBUG {'from_state': 'RUNNING', 'processname':
        #   'testdaemon1_02', 'pid': '22042', 'expected': '0', 'groupname': 'testdaemon1'}
        pheaders, pdata = childutils.eventdata(payload + '\n')

        # If exitcode expected
        if int(pheaders['expected']):
            return None

        # Create dict for push to newrelic
        newrelicdata = copy.copy(pheaders)
        newrelicdata['hostname'] = self.hostname
        newrelicdata['hostname_processname'] = '{}_{}'.format(self.hostname, pheaders['processname'])
        newrelicdata['eventType'] = self.newrelic_event_type

        try:
            r = requests.post(self.newrelic_url, data=json.dumps(newrelicdata),
                              headers=self.newrelic_headers, timeout=2)

            syslog.syslog('Status code for newrelic: {}'.format(r.status_code))

            if not r.status_code == requests.codes.ok:
                r.raise_for_status()
        except:
            syslog.syslog('Cant send data to newrelic: {}'.format(newrelicdata))

def main():
    send = ExitedSendToZabbix.create_from_cmd_line()
    send.run()


if __name__ == '__main__':
    main()

