# --------------------------------------------------------------------------------
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
# --------------------------------------------------------------------------------

import errno
import os
import shutil

from agents.common import GenericAgent
from agents.exceptions import ReplicationRootNotMounted
from agents.utils.utils import construct_file_path, current_time


class ReplicationAgent(GenericAgent):

    def __init__(self):
        super(ReplicationAgent, self).__init__()

        # Queue initialization
        self.main_queue_name = 'replication'
        self.failed_queue_name = 'replication-failed'
        self.main_batch_queue_name = 'batch-replication'
        self.failed_batch_queue_name = 'batch-replication-failed'

        # diagnostic variables for development and testing
        self.last_number_of_files_replicated = 0

    def process_queue(self, channel, method, properties, action, queue):
        """
        The main method which executes a single action.
        """
        if action['action'] == 'freeze' or action['action'] == 'repair':
            self._handle_freeze_action(action, method, queue)
        else:
            self._logger.error('Action type = %s is not something we can handle...' % action['action'])

    def _handle_freeze_action(self, action, method, queue):
        if self._sub_action_processed(action, 'replication'):
            self._logger.info('Replication already processed')
        else:
            try:
                self._process_replication(action)
            except Exception as e:
                self._logger.exception('Replication processing failed')
                self._republish_or_fail_action(method, action, 'replication', queue, e)
                return
        self._ack_message(method)

    def _process_replication(self, action):
        """
        Process replication for nodes in action.

        Replication basically means just a regular file copy from place a to b.
        """
        self._logger.info('Processing replication...')

        self._check_replication_root_is_mounted()
        nodes = self._get_nodes_associated_with_action(action)
        replication_start_time = current_time()
        files_copied = 0

        for node in nodes:

            if not node.get('checksum', None):
                raise Exception('Node %s did not have checksum generated before starting replication.' % node['pid'])

            if node.get('replicated', None) and action['action'] != 'repair':
                self._logger.debug('Node %s already copied, skipping...' % node['pid'])
                continue

            try:
                self._copy_to_replication_location(node, replication_start_time)
            except Exception:
                # on any error during file copy, check if the error is because the mount
                # point disappeared. if there is an error, the below method will raise
                # a ReplicationRootNotMounted exception, and the error will not count
                # towards retry limits.
                self._check_replication_root_is_mounted()

                # if code still executes here, the error was because of something else...
                # send the error down the usual error handling route.
                raise

            # save each individual successfully replicated node to IDA db immediately,
            # in case the replication process fails later. this way, already replicated
            # files will not be replicated again during a retry.
            self._save_nodes_to_db([node], fields=['replicated'], updated_only=True)
            if node.get('_copied', False) == True:
                files_copied += 1

        self.last_number_of_files_replicated = files_copied
        self._save_action_completion_timestamp(action, 'replication')
        self._save_action_completion_timestamp(action, 'completed')
        self._logger.info('Replication processing OK')

    def _check_replication_root_is_mounted(self):
        """
        In production environment, determine if the replication root volume is mounted.
        In non-production environments, the replication root location is just created on the fly
        during copy if it is missing.
        """
        self._logger.info('Checking replication root mount point...')

        if self._uida_conf_vars.get('IDA_ENVIRONMENT') != 'PRODUCTION':
            self._logger.info('IDA_ENVIRONMENT != PRODUCTION, not expecting a real mount point. Returning')
            return

        if not os.path.ismount(self._uida_conf_vars['DATA_REPLICATION_ROOT']):
            raise ReplicationRootNotMounted(
                'Replication root %s not mounted' % self._uida_conf_vars['DATA_REPLICATION_ROOT']
            )

        self._logger.info('Replication root at %s OK' % self._uida_conf_vars['DATA_REPLICATION_ROOT'])

    def _copy_to_replication_location(self, node, timestamp=current_time()):
        """
        Copy a single node from frozen location to replication location.

        As an extra precaution, checksums are re-calculated for files after copy,
        and compared with the checksums of the initial checksum generation phase.

        Note that for efficiencies sake, during repair of a project, the file will not be re-copied
        if a replication already exists and the file size is the same for both the frozen file and
        already replicated file.
        """

        src_path = construct_file_path(self._uida_conf_vars, node)
        dest_path = construct_file_path(self._uida_conf_vars, node, replication=True)

        if os.path.exists(dest_path):
            if os.stat(src_path).st_size == os.stat(dest_path).st_size:
                self._logger.debug('Skipping already replicated file: %s' % dest_path)
                # If the file has no replicated timestamp defined, set it to the frozen timestamp
                if not node.get('replicated', None):
                    self._logger.debug('Fixing missing replicated timestamp: %s' % node['frozen'])
                    node['replicated'] = node['frozen']
                    node['_updated'] = True
                return

        try:
            shutil.copy(src_path, dest_path)
        except IOError as e:
            # ENOENT(2): file does not exist, raised also on missing dest parent dir
            if e.errno != errno.ENOENT:
                raise
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy(src_path, dest_path)

        try:
            replicated_checksum = self._get_file_checksum(dest_path)
        except Exception as e:
            raise Exception('Error generating checksum for file: %s, pathname: %s, error: %s' % (node['pid'], node['pathname'], str(e)))

        # Remove any sha256: URI prefix
        node['checksum'] = self._get_checksum_value(node['checksum'])

        if node['checksum'] != replicated_checksum:
            raise Exception('Checksum mismatch after replication for file: %s, pathname: %s, frozen_checksum: %s, replicated_checksum: %s' % (node['pid'], node['pathname'], node['checksum'], replicated_checksum))

        node['replicated'] = timestamp
        node['_updated'] = True
        node['_copied'] = True

    def _republish_or_fail_action(self, method, action, sub_action_name, queue, exception):
        """
        Parameter 'method' is rabbitmq message method, needed to ack the message.

        Inherited from GenericAgent, in order to handle ReplicationRootNotMounted, to retry indefinetly
        """
        if isinstance(exception, ReplicationRootNotMounted):
            # probably a service break or such. failure does not count towards retry attempts
            try:
                if queue == 'replication' or queue == 'replication-failed':
                    used_exchange = 'actions-failed'
                elif queue == 'batch-replication' or queue == 'batch-replication-failed':
                    used_exchange = 'batch-actions-failed'
                else:
                    used_exchange = 'actions-failed'
                self.publish_message(action, routing_key='%s-failed-waiting' % sub_action_name, exchange=used_exchange)
            except Exception:
                self._logger.warning(
                    'Action republish failed. Message will return to original '
                    'queue and be retried in the future.'
                )
            else:
                self._ack_message(method)
        else:
            return super(ReplicationAgent, self)._republish_or_fail_action(method, action, sub_action_name, queue, exception)


if __name__ == '__main__':
    print('-- Executing ReplicationAgent main --')
    RA = ReplicationAgent()
    RA.start()
    print('-- ReplicationAgent main stopped --')
