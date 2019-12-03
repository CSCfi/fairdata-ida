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

from copy import deepcopy
from time import sleep

import responses

from agents.metadata import MetadataAgent
from agents.utils.utils import get_settings
from agents.tests.lib import BaseAgentTestCase
from agents.tests.testdata import ida as ida_test_data

SETTINGS = get_settings()


class TestMetadataAgent(MetadataAgent):

    """
    TestAgent to record calls to api's
    """

    ida_called = False
    ida_post_files_called = False
    ida_post_files_data = {}
    metax_called = False
    metax_delete_called = False
    metax_delete_data = []
    metax_post_called = False
    metax_post_data = []

    def __init__(self, *args, **kwargs):
        super(TestMetadataAgent, self).__init__(*args, **kwargs)
        self._uida_conf_vars = deepcopy(self._uida_conf_vars)

    def _http_request(self, method, url, data=None, headers=None):
        res = super(TestMetadataAgent, self)._http_request(method, url, data=data, headers=headers)

        if 'metax' in url:
            self.metax_called = True
        elif 'ida' in url:
            self.ida_called = True

        if 'metax' in url and method == 'delete':
            self.metax_delete_called = True
            self.metax_delete_data = data
        elif 'metax' in url and method == 'post':
            self.metax_post_called = True
            self.metax_post_data = data
        elif 'ida' in url and 'files' in url and method == 'post':
            self.ida_post_files_called = True
            self.ida_post_files_data = data

        return res


class MetadataAgentTestsCommon(BaseAgentTestCase):

    """
    Common setups for all metadata test classes
    """

    def setUp(self):
        super(MetadataAgentTestsCommon, self).setUp()
        self.agent = TestMetadataAgent()
        self.agent.rabbitmq_message = None

        # often used test things used for freeze action
        self.TEST_FREEZE_ACTION_WITH_ONE_NODE = deepcopy(ida_test_data['actions'][0])
        self.TEST_FREEZE_ACTION_NODE = deepcopy(ida_test_data['nodes'][0])
        self.TEST_FREEZE_NODE_CHECKSUM = 'c20a6d5b03450bbc65fd5cd043e1bc8d7842815efd4e431a06a7a7b641fc30ed'


class MetadataAgentUnitTests(MetadataAgentTestsCommon):

    """
    Testing some relevant methods in the MetadataAgent.

    Note: These tests do not require publishing a rabbitmq message.
    """

    @responses.activate
    def test_process_checksums(self):
        """
        When checksum processing has been successfully completed...
        - the method should return all nodes associated with the action, with their checksums
        - the checksums have been successfully saved to ida db
        - the checksum sub-action completion timestamp has been saved to ida db
        - nothing ever ended up in the failed-queue
        """
        self.agent.rabbitmq_message = self.TEST_FREEZE_ACTION_WITH_ONE_NODE
        nodes = self.agent._process_checksums(self.TEST_FREEZE_ACTION_WITH_ONE_NODE)

        # check nodes have checksums in place
        self.assertEqual('checksum' in nodes[0], True, 'when the checkum processing is successful, a node dict should have the key checksum in it')
        self.assertEqual(nodes[0]['checksum'], self.TEST_FREEZE_NODE_CHECKSUM)
        self.assertEqual(len(nodes), 1, 'most strange, the action should have only one associated with it')

        # check node checksum is updated to ida db
        self.assertEqual(self.agent.ida_post_files_called, True)
        self.assertEqual('checksum' in self.agent.ida_post_files_data, True)
        self.assertEqual(self.agent.ida_post_files_data['checksum'], self.TEST_FREEZE_NODE_CHECKSUM)

        # check sub-action completion is updated to ida db
        self.assertEqual('checksums' in self.agent.last_completed_sub_action, True)
        self.assertEqual(self.agent.last_completed_sub_action['action_pid'], self.TEST_FREEZE_ACTION_WITH_ONE_NODE['pid'])
        self.assert_messages_ended_in_failed_queue(0)

    def test_aggregate_technical_metadata(self):
        """
        An action, which has already processed the checksums previously, should result in
        the following file metadata for our frozen test node.
        """
        expected_node_metadata = [{
            'byte_size': 3728,
            'file_name': 'test01.dat',
            'checksum': {
                'checked': '2017-10-10T12:00:00Z',
                'value': self.TEST_FREEZE_NODE_CHECKSUM,
                'algorithm': 'SHA-256'
            },
            'project_identifier': 'Project_X',
            'file_storage': 1,
            'open_access': True,
            'file_modified': '2017-10-16T12:45:08Z',
            'file_uploaded': 'time_of_upload',
            'file_path': '/Custom_Experiment/test01.dat',
            'identifier': 'pidveryuniquefilepidhere',
            'file_format': 'dat',
            'file_frozen': '2017-10-26T07:48:45Z',
            'user_created': 'TestUser@cscuserid'
        }]

        # set a date on the action when the checksum processing was supposedly completed
        self.TEST_FREEZE_ACTION_WITH_ONE_NODE['checksums'] = '2017-10-10T12:00:00Z'

        # the previous processing of checksums resulted in this checksum for the node
        self.TEST_FREEZE_ACTION_NODE['checksum'] = self.TEST_FREEZE_NODE_CHECKSUM
        self.TEST_FREEZE_ACTION_NODE['metadata'] = 'time_of_upload'
        generated_metadata = self.agent._aggregate_technical_metadata(self.TEST_FREEZE_ACTION_WITH_ONE_NODE, [ self.TEST_FREEZE_ACTION_NODE ])

        self.assertEqual('file_uploaded' in generated_metadata[0], True)

        # copy this value for the rest of the assertion to be valid, since this
        # always comes from current time and cant be hardcoded.
        expected_node_metadata[0]['file_uploaded'] = generated_metadata[0]['file_uploaded']

        self.assertEqual(generated_metadata, expected_node_metadata)
        self.assert_messages_ended_in_failed_queue(0)

    @responses.activate
    def test_process_metadata_publication(self):
        self.TEST_FREEZE_ACTION_WITH_ONE_NODE['checksums'] = '2017-10-10T12:00:00Z'
        self.TEST_FREEZE_ACTION_NODE['checksum'] = self.TEST_FREEZE_NODE_CHECKSUM
        self.agent.rabbitmq_message = self.TEST_FREEZE_ACTION_WITH_ONE_NODE

        self.agent._process_metadata_publication(self.TEST_FREEZE_ACTION_WITH_ONE_NODE, [ self.TEST_FREEZE_ACTION_NODE ])

        # check file metadata is posted to metax api
        self.assertEqual(self.agent.metax_post_called, True)
        self.assertEqual(len(self.agent.metax_post_data), 1)

        # check sub-action completion is updated to ida db
        self.assertEqual('metadata' in self.agent.last_completed_sub_action, True)
        self.assertEqual(self.agent.last_completed_sub_action['action_pid'], self.TEST_FREEZE_ACTION_WITH_ONE_NODE['pid'])
        self.assert_messages_ended_in_failed_queue(0)

    @responses.activate
    def test_process_metadata_deletion(self):
        # unfreeze-action with one associated node
        unfreeze_action = deepcopy(ida_test_data['actions'][4])
        self.agent.rabbitmq_message = unfreeze_action
        self.agent._process_metadata_deletion(unfreeze_action)

        # check delete request is sent to metax-api
        self.assertEqual(self.agent.metax_delete_called, True)
        self.assertEqual(len(self.agent.metax_delete_data), 1)

        # check sub-action completion is updated to ida db
        self.assertEqual('completed' in self.agent.last_completed_sub_action, True)
        self.assertEqual(self.agent.last_completed_sub_action['action_pid'], unfreeze_action['pid'])
        self.assert_messages_ended_in_failed_queue(0)


class MetadataAgentProcessQueueTests(MetadataAgentTestsCommon):

    """
    Higher level tests starting from the point where a message is first received. Check
    that certain methods have been called with certain parameters at some point during the
    processing of an action, which should imply that things are working as expected.

    For some tests, cause side effects such as raise exceptions using mocking.

    Note: These tests require publishing a rabbitmq message.
    """

    @responses.activate
    def test_consume_one_when_none_completed(self):
        """
        Consume one message start to finish, successfully processing checksum generation
        and metadata publication.
        """

        # publish test action which has only one node associated with it, and 0 sub-actions completed.
        self._publish_test_messages(index=0)
        self.assertEqual(self.agent.messages_in_queue(), 1)

        self.agent.consume_one()

        sleep(0.5) # to give rabbitmq time to process
        self.assertEqual(self.agent.messages_in_queue(), 0)

        # check metadata was posted to metax api
        self.assertEqual(self.agent.metax_post_called, True)
        self.assertEqual(len(self.agent.metax_post_data), 1)

        # check sub-action completion is updated to ida db
        self.assertEqual('metadata' in self.agent.last_completed_sub_action, True)
        self.assertEqual(self.agent.last_completed_sub_action['action_pid'], self.TEST_FREEZE_ACTION_WITH_ONE_NODE['pid'])
        self.assert_messages_ended_in_failed_queue(0)

    @responses.activate
    def test_consume_one_when_checksums_already_completed(self):
        """
        Consume one message which has checksums already completed.
        """

        # publish test action which has only one node associated with it, and checksum sub-action completed.
        published_message = self._publish_test_messages(index=2)
        self.assertEqual(self.agent.messages_in_queue(), 1)

        self.agent.consume_one()

        sleep(0.5) # to give rabbitmq time to process
        self.assertEqual(self.agent.messages_in_queue(), 0)

        # check metadata was posted to metax api
        self.assertEqual(self.agent.metax_post_called, True)
        self.assertEqual(len(self.agent.metax_post_data), 1)

        # check sub-action completion is updated to ida db
        self.assertEqual('metadata' in self.agent.last_completed_sub_action, True)
        self.assertEqual(self.agent.last_completed_sub_action['action_pid'], published_message['pid'])
        self.assert_messages_ended_in_failed_queue(0)

    @responses.activate
    def test_consume_one_unfreeze_action(self):
        """
        Consume one unfreeze action.
        """

        # index=4 is an unfreeze action
        published_message = self._publish_test_messages(index=4)
        self.assertEqual(self.agent.messages_in_queue(), 1)

        self.agent.consume_one()

        sleep(0.5) # to give rabbitmq time to process
        self.assertEqual(self.agent.messages_in_queue(), 0)

        # check delete request was sent to metax api
        self.assertEqual(self.agent.metax_delete_called, True)
        self.assertEqual(len(self.agent.metax_delete_data), 1)

        # check sub-action completion is updated to ida db
        self.assertEqual('completed' in self.agent.last_completed_sub_action, True)
        self.assertEqual(self.agent.last_completed_sub_action['action_pid'], published_message['pid'])
        self.assert_messages_ended_in_failed_queue(0)

    @responses.activate
    def test_consume_one_complete_action_without_metax(self):
        """
        Consume one message start to finish, but with METAX_AVAILABLE=0 in config.sh.
        Action should be marked as complete without trying to publish anything to metax.
        """

        # normally this flag is 1 (=True) even in test settings - set it 0 (=False) here, so that
        # the action should be marked completed without connecting metax
        self.agent._uida_conf_vars['METAX_AVAILABLE'] = 0

        # publish test action which has only one node associated with it, and 0 sub-actions completed.
        published_message = self._publish_test_messages(index=0)
        self.assertEqual(self.agent.messages_in_queue(), 1)

        self.agent.consume_one()

        sleep(0.5) # to give rabbitmq time to process
        self.assertEqual(self.agent.messages_in_queue(), 0)
        self.assertEqual(self.agent.metax_called, False, 'metax should have never been called!')

        # check sub-action completion is updated to ida db
        self.assertEqual('metadata' in self.agent.last_completed_sub_action, True)
        self.assertEqual(self.agent.last_completed_sub_action['action_pid'], published_message['pid'])
        self.assert_messages_ended_in_failed_queue(0)
