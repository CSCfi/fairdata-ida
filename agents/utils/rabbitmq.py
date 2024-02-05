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
This script initializes the rabbitmq vhost, exchanges, and queues, which the
rabbitmq postprocessing agents require to operate.

Before executing the script, ensure:
- the rabbitmq management plugin is enabled
- rabbitmq admin user has been configured by using script utils/rabbitmq_create_users
- rabbitmq admin credentials are in place in config/config.sh
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
    {
        'name': 'actions-failed',
        'type': 'direct',
        'arguments': {},
        'queues': [
            # queues where failed messages are republished to for waiting a period of time,
            # until they are dead-lettered to the actual queue where they will be processed from.
            # note that failed checksums, and metadata publication sub-actions, both finally end up
            # in the metadata-failed queue, although they have their separate waiting-queues, to
            # allow for different retry delays.
            {
                'name': 'checksums-failed-waiting',
                'routing_key': 'checksums-failed-waiting',
                'arguments': {
                    'x-message-ttl': settings['retry_policy']['checksums']['retry_interval'] * 1000,
                    'x-dead-letter-exchange': 'actions-failed',
                    'x-dead-letter-routing-key': 'metadata-failed'
                }
            },
            {
                'name': 'metadata-failed-waiting',
                'routing_key': 'metadata-failed-waiting',
                'arguments': {
                    'x-message-ttl': settings['retry_policy']['metadata']['retry_interval'] * 1000,
                    'x-dead-letter-exchange': 'actions-failed',
                    'x-dead-letter-routing-key': 'metadata-failed'
                }
            },
            {
                'name': 'replication-failed-waiting',
                'routing_key': 'replication-failed-waiting',
                'arguments': {
                    'x-message-ttl': settings['retry_policy']['replication']['retry_interval'] * 1000,
                    'x-dead-letter-exchange': 'actions-failed',
                    'x-dead-letter-routing-key': 'replication-failed'
                }
            },

            # queues where failed actions are published to from the waiting queue,
            # and are actually processed from
            {
                'name': 'metadata-failed',
                'routing_key': 'metadata-failed'
            },
            {
                'name': 'replication-failed',
                'routing_key': 'replication-failed'
            },
        ]
    },
    {
        'name': 'batch-actions-failed',
        'type': 'direct',
        'arguments': {},
        'queues': [
            {
                'name': 'batch-checksums-failed-waiting',
                'routing_key': 'batch-checksums-failed-waiting',
                'arguments': {
                    'x-message-ttl': settings['retry_policy']['checksums']['retry_interval'] * 1000,
                    'x-dead-letter-exchange': 'batch-actions-failed',
                    'x-dead-letter-routing-key': 'batch-metadata-failed'
                }
            },
            {
                'name': 'batch-metadata-failed-waiting',
                'routing_key': 'batch-metadata-failed-waiting',
                'arguments': {
                    'x-message-ttl': settings['retry_policy']['metadata']['retry_interval'] * 1000,
                    'x-dead-letter-exchange': 'batch-actions-failed',
                    'x-dead-letter-routing-key': 'batch-metadata-failed'
                }
            },
            {
                'name': 'batch-replication-failed-waiting',
                'routing_key': 'batch-replication-failed-waiting',
                'arguments': {
                    'x-message-ttl': settings['retry_policy']['replication']['retry_interval'] * 1000,
                    'x-dead-letter-exchange': 'batch-actions-failed',
                    'x-dead-letter-routing-key': 'batch-replication-failed'
                }
            },
            {
                'name': 'batch-metadata-failed',
                'routing_key': 'batch-metadata-failed'
            },
            {
                'name': 'batch-replication-failed',
                'routing_key': 'batch-replication-failed'
            },
        ]
    },
]

SUCCESS_CODES = (200, 201, 204)


def init_rabbitmq():
    """
    Initialize rabbitmq vhost, exchanges etc accorging to current
    execution env settings (production or test).

    Executing this method is basically a pre-condition to running the agents.
    This method is not however executed automatically when running the agents, but must be
    run separately to not have any uintended effects.
    """
    _create_vhost()
    _create_exchanges()
    if executing_test_case():
        # for non-testcase use, users should be created using a script in ida/utils/
        _create_users()
    _create_queues()

def teardown_rabbitmq():
    _delete_vhost()
    _delete_users()

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

def _create_vhost():
    _rabbitmq_api_call(
        'put',
        '/vhosts/%s' % VHOST_NAME,
        error_msg='vhost was not created.'
    )

    # admin must be assigned to the vhost, otherwise we wont be able to edit the vhost later
    _rabbitmq_api_call(
        'put',
        '/permissions/%s/%s' % (VHOST_NAME, uida_conf_vars['RABBIT_ADMIN_USER']),
        data=json_dumps({"configure": ".*", "write": ".*", "read": ".*"}),
        error_msg='Admin user was not added to vhost'
    )

def _create_exchanges():
    for exchange in EXCHANGES:
        _rabbitmq_api_call(
            'put',
            '/exchanges/%s/%s' % (VHOST_NAME, exchange['name']),
            data=json_dumps({
                "type": exchange['type'],
                "auto_delete": False,
                "durable": True,
                "internal": False,
                "arguments": exchange['arguments']
            }),
            error_msg='exchange was not created.'
        )

def _create_users():
    _rabbitmq_api_call(
        'put',
        '/users/%s' % uida_conf_vars['RABBIT_WORKER_USER'],
        data=json_dumps({ "password": uida_conf_vars['RABBIT_WORKER_PASS'], "tags": "" }),
        error_msg='user was not created.'
    )

    _rabbitmq_api_call(
        'put',
        '/permissions/%s/%s' % (VHOST_NAME, uida_conf_vars['RABBIT_WORKER_USER']),
        data=json_dumps({"configure": "", "write": ".*", "read": ".*"}),
        error_msg='user was not added to vhost.'
    )

def _create_queues():
    for exchange in EXCHANGES:
        for queue in exchange['queues']:

            queue_args = { "auto_delete": False, "durable": True }

            if 'arguments' in queue:
                queue_args.update({ 'arguments': queue['arguments'] })

            _rabbitmq_api_call(
                'put',
                '/queues/%s/%s' % (VHOST_NAME, queue['name']),
                data=json_dumps(queue_args),
                error_msg='queue \'%s\' was not added to vhost.' % queue['name']
            )

            _rabbitmq_api_call(
                'post',
                '/bindings/%s/e/%s/q/%s' % (VHOST_NAME, exchange['name'], queue['name']),
                data=json_dumps({ 'routing_key': queue['routing_key'] }) if 'routing_key' in queue else None,
                error_msg='queue \'%s\' was not bound to exchange \'%s\'.' % (queue['name'], exchange['name'])
            )

def _delete_vhost():
    _rabbitmq_api_call(
        'delete',
        '/vhosts/%s' % VHOST_NAME,
        error_msg='vhost was not deleted.',
        success_codes=SUCCESS_CODES + (404,)
    )

def _delete_users():
    _rabbitmq_api_call(
        'delete',
        '/users/%s' % uida_conf_vars['RABBIT_WORKER_USER'],
        error_msg='user was not deleted.',
        success_codes=SUCCESS_CODES + (404,)
    )

def _get_action_from_ida(pid):
    response = requests.get(
        '%s/actions/%s' % (uida_conf_vars['IDA_API'], pid),
        headers=HEADERS,
        auth=(uida_conf_vars['NC_ADMIN_USER'], uida_conf_vars['NC_ADMIN_PASS'])
    )

    if response.status_code != 200:
        raise Exception('error: %d, %s' % (response.status_code, response.content))

    return response.json()

def _publish_action(args):
    pid = argv[1].split('=')[1]
    action_json = _get_action_from_ida(pid)
    print('Publishing action %s:\n%s\n...' % (pid, str(action_json)))

    publish_action_messages('batch-actions', action_json)
    print('Action published')


if __name__ == '__main__':
    if len(argv) > 1:
        if argv[1].startswith('--publish-action='):
            _publish_action(argv)
        elif argv[1].startswith('--tear-down'):
            teardown_rabbitmq()
        else:
            print('unknown parameter %s' % argv[1])
    else:
        print('Initializing rabbitmq vhost, exchanges, users, and queues...')
        try:
            init_rabbitmq()
        except:
            raise
        else:
            print('Done')
