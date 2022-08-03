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

from json import dumps as json_dumps
from time import sleep
from unittest import TestCase

import responses

from agents.common import GenericAgent
from agents.utils.utils import load_variables_from_uida_conf_files, get_settings
from agents.tests.testdata import ida as ida_test_data
import agents.tests.utils as test_utils


"""
This file contains a superclass used by other test classes to provide
- setting up rabbitmq exchanges and queues
- setting up mock api responsed from test data
- creating test files on the file system from test data
- test tear down operations
- methods for publishing messages to the rabbitmq exchanges
- possibly other stuff as necessary
"""

class BaseAgentTestCase(TestCase):

    _settings = get_settings()
    _uida_conf_vars = load_variables_from_uida_conf_files()

    @classmethod
    def setUpClass(cls):
        # instead of setting a signal handler for ctrl+c,
        # call teardown class to make sure everything is clean
        try:
            cls.tearDownClass()
        except Exception:
            pass

    def setUp(self):

        print("%s" % self.__class__.__name__)

        test_utils.init_rabbitmq()
        self._init_files()
        self._prepare_api_responses()

    def tearDown(self):
        test_utils.teardown_rabbitmq()
        self._teardown_files()
        ok = self.currentResult.wasSuccessful()
        # errors = self.currentResult.errors
        # failures = self.currentResult.failures
        #print("Test Successful" if ok else "%d Errors and %d Failures found" % (len(errors), len(failures)))
        print('\033[92m\033[1m' + "\t    ....OK" + '\033[0m' if ok else '\033[91m\033[1m' + "\t    ....FAIL" + '\033[0m')

    def run(self, result=None):
        self.currentResult = result # remember result for use in tearDown
        TestCase.run(self, result) # call superclass run method

    @classmethod
    def tearDownClass(cls):
        test_utils.teardown_rabbitmq()
        cls._teardown_files(cls)

    def _publish_test_messages(self, index=None, exchange='actions'):
        """
        Publish one message from index 'index' from test data, or publish all messages if
        no index is passed.
        """
        message = None
        ga = GenericAgent()
        if index is not None:
            message = ida_test_data['actions'][index]
            ga.publish_message(message, exchange=exchange)
        else:
            for action in ida_test_data['actions']:
                ga.publish_message(action, exchange=exchange)

        # must give some time for messages to get processed in rabbitmq,
        # so that the agents and the asserts can detect the new messages
        sleep(0.5)
        return message

    def _prepare_response(self, method, service, url, status=None, body=None):
        """
        Prepare responses that will be returned by the mock apis that are called
        by the agents during tests, i.e. the response generated here would be what
        the ida-api and metax-api would be expected to return.
        """
        if service == 'ida':
            root_url = self._uida_conf_vars['IDA_API_ROOT_URL']
        elif service == 'metax':
            root_url = self._uida_conf_vars['METAX_API_ROOT_URL']
        else:
            raise Exception('oops! check your settings')

        responses.add(
            method,
            '%s%s' % (root_url, url),
            status=status,
            content_type='application/json',
            body=body
        )

    def _prepare_api_responses(self):
        """
        Generate mock responses made to...
        - ida api using test data. The testdata file is basically a mocked database.
        - metax api. all requests are by default assumed successful. tests which test
          against a failing metax action will override the mock response
        """

        # GET action
        for action in ida_test_data['actions']:
            self._prepare_response(
                responses.GET,
                'ida',
                '/actions/%s' % action['pid'],
                status=200,
                body=json_dumps(action)
            )

        # POST action
        for action in ida_test_data['actions']:
            self._prepare_response(
                responses.POST,
                'ida',
                '/actions/%s' % action['pid'],
                status=204
            )

        # GET nodes associated with action
        for action in ida_test_data['actions']:
            self._prepare_response(
                responses.GET,
                'ida',
                '/files/action/%s' % action['pid'],
                status=200,
                body=json_dumps(
                    [ node for node in ida_test_data['nodes'] if node['action'] == action['pid'] ]
                )
            )

        # POST nodes
        for node in ida_test_data['nodes']:
            self._prepare_response(
                responses.POST,
                'ida',
                '/files/%s' % node['pid'],
                status=204
            )

        # GET to metax root API URL
        self._prepare_response(
            responses.GET,
            'metax',
            '/',
            status=200,
            body=json_dumps({
                'success': True
            })
        )

        # POST to metax /files
        self._prepare_response(
            responses.POST,
            'metax',
            '/files?atomic=true',
            status=200,
            body=json_dumps({
                'success': [
                    { 'object': 'a successfully created object' }
                ],
                'failed': []
            })
        )

        # DELETE to metax /files
        for node in ida_test_data['nodes']:
            self._prepare_response(
                responses.DELETE,
                'metax',
                '/files',
                status=204
            )

    def _init_files(self):
        """
        Create files to the file system from test data
        """
        for f in (f for f in ida_test_data['nodes'] if f['type'] == 'file'):
            test_utils.create_test_file(self._uida_conf_vars, f)

    def _teardown_files(self):
        test_utils.delete_test_directory(self._uida_conf_vars['STORAGE_OC_DATA_ROOT'])
        test_utils.delete_test_directory(self._uida_conf_vars['DATA_REPLICATION_ROOT'])
        test_utils.delete_test_directory(self._uida_conf_vars['RABBIT_MONITORING_DIR'])

    def assert_messages_ended_in_failed_queue(self, message_qty):
        """
        At the end of a test it is useful to check how many messages being processed
        eneded up in the failed queue.
        """
        self.assertEqual(self.agent.messages_in_queue(self.agent.failed_queue_name), message_qty)
