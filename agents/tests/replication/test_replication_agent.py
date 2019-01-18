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
from os.path import isfile
from time import sleep

import responses

from agents.metadata import MetadataAgent
from agents.replication import ReplicationAgent
from agents.utils.utils import construct_file_path
from agents.tests.lib import BaseAgentTestCase
from agents.tests.testdata import ida as ida_test_data


class ReplicationAgentTestsCommon(BaseAgentTestCase):

    """
    Common setups for all replication test classes
    """

    def setUp(self):
        super(ReplicationAgentTestsCommon, self).setUp()
        self.agent = ReplicationAgent()
        self.agent.rabbitmq_message = None


class ReplicationAgentUnitTests(ReplicationAgentTestsCommon):

    @responses.activate
    def test_copy_to_replication_location(self):
        """
        Ensure the actual file copy works.
        """
        test_action = deepcopy(ida_test_data['actions'][5])

        # note - an internal reads project identifier from the rabbitmq message
        self.agent.rabbitmq_message = test_action

        nodes = self.agent._get_nodes_associated_with_action(test_action)
        for node in nodes:
            self.agent._copy_to_replication_location(node)

        # assert copied files exist
        for node in nodes:
            file_path = construct_file_path(self.agent._uida_conf_vars, node, replication=True)
            self.assertEqual(isfile(file_path), True, 'copied file does not exist!')

    @responses.activate
    def test_replicated_files_are_not_copied_again(self):
        """
        Ensure replicated files do not get replicated again, when a replication-message
        is being re-processed.

        There should be 3 files total, one of which already has replicated-timestamp in
        place, and should not be copied again.
        """
        test_action = deepcopy(ida_test_data['actions'][5])

        # note - an internal reads project identifier from the rabbitmq message
        self.agent.rabbitmq_message = test_action

        self.agent._process_replication(test_action)
        self.assertEqual(self.agent.last_number_of_files_replicated, 2)


class ReplicationAgentProcessQueueTests(ReplicationAgentTestsCommon):

    @responses.activate
    def test_publish_to_actions_does_not_start_replication(self):
        """
        Ensure ReplicationAgent does not see messages published to exchange 'actions'.
        ReplicationAgent should only begin its work, once MetadataAgent has finished,
        and published a new message to exchange 'replication'
        """
        self._publish_test_messages(index=0, exchange='actions')
        mda = MetadataAgent()
        self.assertEqual(mda.messages_in_queue(), 1)
        self.assertEqual(self.agent.messages_in_queue(), 0)

    @responses.activate
    def test_consume_replication_message(self):
        """
        Consume one replicatiom message start to finish.
        """
        published_message = self._publish_test_messages(index=5, exchange='replication')
        self.assertEqual(self.agent.messages_in_queue(), 1)

        self.agent.consume_one()

        sleep(0.5) # to give rabbitmq time to process
        self.assertEqual(self.agent.messages_in_queue(), 0)

        # check action has replication marked completed.
        self.assertEqual('replication' in self.agent.last_completed_sub_action, True)
        self.assertEqual(self.agent.last_completed_sub_action['action_pid'], published_message['pid'])
        self.assert_messages_ended_in_failed_queue(0)
