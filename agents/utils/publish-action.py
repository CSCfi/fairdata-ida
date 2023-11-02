#--------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2018 Ministry of Education and Culture, Finland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# @author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
# @license  GNU Affero General Public License, version 3
# @link     https://research.csc.fi/
#--------------------------------------------------------------------------------

"""
This script will publish the specified action to rabbitmq for postprocessing

Before executing the script, ensure:
- the rabbitmq management plugin is enabled
- rabbitmq admin user has been configured by using script utils/rabbitmq_create_users
- rabbitmq admin credentials are in place in config/config.sh

Execution:
    cd /var/ida
    source /srv/venv-agents/bin/activate
    python -m agents.utils.publish-action pid
"""

from json import dumps as json_dumps
from sys import argv

import requests

from agents.utils.utils import get_settings, load_variables_from_uida_conf_files, executing_test_case

uida_conf_vars = load_variables_from_uida_conf_files()

settings = get_settings()

RABBITMQ_API_URL = '%s://%s:%d/api' % (
    uida_conf_vars.get('RABBIT_PROTOCOL', 'http'),
    uida_conf_vars['RABBIT_HOST'],
    uida_conf_vars['RABBIT_WEB_API_PORT'])

RABBITMQ_AUTH = (uida_conf_vars['RABBIT_ADMIN_USER'], uida_conf_vars['RABBIT_ADMIN_PASS'])

HEADERS = { 'Content-Type': 'application/json', 'IDA-Mode': 'System' }

VHOST_NAME = uida_conf_vars['RABBIT_VHOST']
EXCHANGES = [
    {
        'name': 'actions',
        'type': 'fanout',
        'arguments': {},
        'queues': [
            { 'name': 'metadata' },
        ]
    },
    {
        'name': 'replication',
        'type': 'fanout',
        'arguments': {},
        'queues': [
            { 'name': 'replication' }
        ]
    },
    {
        'name': 'batch-actions',
        'type': 'fanout',
        'arguments': {},
        'queues': [
            { 'name': 'batch-metadata' },
        ]
    },
    {
        'name': 'batch-replication',
        'type': 'fanout',
        'arguments': {},
        'queues': [
            { 'name': 'batch-replication' }
        ]
    },
]

SUCCESS_CODES = (200, 201, 204)

def publish_action_messages(exchange, message):
    if isinstance(message, dict):
        message = json_dumps(message)
    data = {
        "properties": {},
        "routing_key": "",
        "payload": message,
        "payload_encoding": "string"
    }

    _rabbitmq_api_call(
        'post',
        '/exchanges/%s/%s/publish' % (VHOST_NAME, exchange),
        data=json_dumps(data),
        error_msg='message was not published to exchange \'%s\'.' % exchange
    )

def _rabbitmq_api_call(method, resource_url, data=None, error_msg=None, success_codes=SUCCESS_CODES):
    response = getattr(requests, method)(
        '%s%s' % (RABBITMQ_API_URL, resource_url),
        data=data,
        headers=HEADERS,
        auth=RABBITMQ_AUTH
    )
    if response.status_code not in success_codes:
        error_msg += ' Error: %s. status_code: %d'
        raise Exception(error_msg % (response.content, response.status_code))

def _get_action_from_ida(pid):
    response = requests.get(
        '%s/actions/%s' % (uida_conf_vars['IDA_API_ROOT_URL'], pid),
        headers=HEADERS,
        auth=(uida_conf_vars['NC_ADMIN_USER'], uida_conf_vars['NC_ADMIN_PASS'])
    )

    if response.status_code != 200:
        raise Exception('error: %d, %s' % (response.status_code, response.content))

    return response.json()

def _publish_action(args):
    pid = argv[1]
    action_json = _get_action_from_ida(pid)
    print('Publishing action %s:\n%s\n...' % (pid, str(action_json)))
    publish_action_messages('batch-actions', action_json)
    print('Action published')

if __name__ == '__main__':
    if len(argv) > 1:
        _publish_action(argv)
    else:
        print('action pid not specified')

