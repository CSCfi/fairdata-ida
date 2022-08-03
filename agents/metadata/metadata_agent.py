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
# @author CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
# @license GNU Affero General Public License, version 3
# @link https://research.csc.fi/
#--------------------------------------------------------------------------------

import os
import requests

from agents.common import GenericAgent
from agents.utils.utils import construct_file_path, make_ba_http_header, current_time

class MetadataAgent(GenericAgent):

    def __init__(self):
        super(MetadataAgent, self).__init__()
        self._metax_api_url = self._uida_conf_vars['METAX_API_ROOT_URL']

        # Queue initialization
        self.main_queue_name = 'metadata'
        self.failed_queue_name = 'metadata-failed'
        self.main_batch_queue_name = 'batch-metadata'
        self.failed_batch_queue_name = 'batch-metadata-failed'

        self.file_storage = self._uida_conf_vars['METAX_FILE_STORAGE_ID']

    def process_queue(self, channel, method, properties, action, queue):
        """
        The main method which executes a single action.
        """
        if action['action'] == 'freeze':
            self._handle_freeze_action(action, method, queue)
        elif action['action'] in ('unfreeze', 'delete'):
            self._handle_unfreeze_action(action, method, queue)
        elif action['action'] == 'repair':
            self._handle_repair_action(action, method, queue)
        else:
            self._logger.error('Action type = %s is not something we can handle...' % action['action'])

    def dependencies_not_ok(self):
        """
        If the Metax service API is not available, return True, else return False.
        Always return True if the dependency checks fail with an exception.
        """
        try:
            response = self._metax_api_request('get', '/', auth=False)
            if response.status_code != 200:
                self._logger.debug('Dependencies not OK')
                return True
            else:
                self._logger.debug('Dependencies OK')
                return False
        except SystemExit:
            raise
        except BaseException as e:
            self._logger.warning('Dependency check failed')
            self._logger.exception(e)
            return True

    def _handle_freeze_action(self, action, method, queue):

        # if sub-actions are being successfully executed sequentially, then
        # nodes downloaded during checksums processing will be re-used for
        # metadata publication.
        nodes = None

        if self._sub_action_processed(action, 'checksums'):
            self._logger.debug('Checksums already processed')
        else:
            try:
                nodes = self._process_checksums(action)
            except Exception as e:
                self._logger.exception('Checksum processing failed')
                self._republish_or_fail_action(method, action, 'checksums', queue, e)
                return

        if self._complete_actions_without_metax():
            self._logger.debug('Note: Completing action without Metax')
            self._save_action_completion_timestamp(action, 'metadata')
        elif self._sub_action_processed(action, 'metadata'):
            self._logger.debug('Metadata already processed')
        else:
            try:
                self._process_metadata_publication(action, nodes)
            except Exception as e:
                self._logger.exception('Metadata publication failed')
                self._republish_or_fail_action(method, action, 'metadata', queue, e)
                return

        if self._sub_action_processed(action, 'replication'):
            self._logger.error('Replication already processed...? Okay... Something weird has happened here')
        else:
            if queue == 'metadata' or queue == 'metadata-failed':
                used_exchange = 'replication'
            elif queue == 'batch-metadata' or queue == 'batch-metadata-failed':
                used_exchange = 'batch-replication'
            else:
                used_exchange = 'replication'
            self.publish_message(action, exchange=used_exchange)
            self._logger.info('Publishing action %s to replication queue...' % action['pid'])

        self._ack_message(method)

    def _handle_unfreeze_action(self, action, method, queue):
        if self._complete_actions_without_metax():
            self._logger.debug('Note: Completing action without Metax')
            self._save_action_completion_timestamp(action, 'metadata')
            self._save_action_completion_timestamp(action, 'completed')
        elif self._sub_action_processed(action, 'metadata'):
            self._logger.debug('Metadata already processed')
        else:
            try:
                self._process_metadata_deletion(action)
            except Exception as e:
                self._logger.exception('Metadata deletion failed')
                self._republish_or_fail_action(method, action, 'metadata', queue, e)
                return
        self._ack_message(method)

    def _handle_repair_action(self, action, method, queue):

        # nodes obtained during checksums processing
        nodes = None

        # Repair checksums (and file sizes) as required
        #
        # Note: the default behavior of the checksum processing accommodates both normal freeze
        # actions and repair actions, so all that is needed here is to process the checksums for
        # all nodes associated with the action, and is no different than for a repair action

        if self._sub_action_processed(action, 'checksums'):
            self._logger.debug('Checksums already processed')
        else:
            try:
                nodes = self._process_checksums(action)
            except Exception as e:
                self._logger.exception('Checksum processing failed')
                self._republish_or_fail_action(method, action, 'checksums', queue, e)
                return

        # Repair published metadata as required

        if self._complete_actions_without_metax():
            self._logger.debug('Note: Completing action without Metax')
            self._save_action_completion_timestamp(action, 'metadata')
        elif self._sub_action_processed(action, 'metadata'):
            self._logger.debug('Metadata repair already processed')
        else:
            try:
                self._process_metadata_repair(action, nodes)
            except Exception as e:
                self._logger.exception('Metadata repair failed')
                self._republish_or_fail_action(method, action, 'metadata', queue, e)
                return

        # Publish action message to replication queue

        if self._sub_action_processed(action, 'replication'):
            self._logger.error('Replication already processed...? Okay... Something weird has happened here')
        else:
            if queue == 'metadata' or queue == 'metadata-failed':
                used_exchange = 'replication'
            elif queue == 'batch-metadata' or queue == 'batch-metadata-failed':
                used_exchange = 'batch-replication'
            else:
                used_exchange = 'replication'
            self.publish_message(action, exchange=used_exchange)
            self._logger.info('Publishing action %s to replication queue...' % action['pid'])

        self._ack_message(method)

    def _process_checksums(self, action):
        self._logger.debug('Processing checksums...')

        nodes = self._get_nodes_associated_with_action(action)

        self._logger.debug('Generating checksums...')

        for node in nodes:
            if self._graceful_shutdown_started:
                raise SystemExit

            # Generate local filesystem pathname to file in frozen area
            file_path = construct_file_path(self._uida_conf_vars, node)

            # If the file size reported for the file differs from the file size on disk,
            # or if no file size is recorded in IDA for the file, or if no checksum is
            # recorded in IDA for the file, then the file size should be updated in IDA
            # based on the file size on disk, and a new checksum generated based on the
            # current file on disk, and the new checksum recorded in IDA.
            #
            # The following logic works efficiently both for freeze and repair actions.

            # Assume no updates to either file size or checksum required
            node_updated = False

            # Get reported file size, if defined
            try:
                node_size = node['size']
            except:
                node_size = None

            # Get reported checksum, if defined
            try:
                node_checksum = node['checksum']
            except:
                node_checksum = None

            # If no file size is reported, or we have a repair action, get the actual size on disk
            # Else trust the reported size and avoid the cost of retrieving the size on disk
            if node_size == None or action['action'] == 'repair':
                file_size = os.path.getsize(file_path)
            else:
                file_size = node_size

            # If the reported file size disagrees with the determined file size, record file size
            # on disk and generate and record new checksum
            if node_size != file_size:
                self._logger.debug('Recording both size and checksum for file %s' % node['pid'])
                node_size = file_size
                try:
                    node_checksum = self._get_file_checksum(file_path)
                except Exception as e:
                    raise Exception('Error generating checksum for file: %s, pathname: %s, error: %s' % (node['pid'], node['pathname'], str(e)))
                node_updated = True

            # If still no checksum, generate and record new checksum
            if node_checksum == None:
                self._logger.debug('Recording checksum for file %s' % node['pid'])
                try:
                    node_checksum = self._get_file_checksum(file_path)
                except Exception as e:
                    raise Exception('Error generating checksum for file: %s, pathname: %s, error: %s' % (node['pid'], node['pathname'], str(e)))
                node_updated = True

            # If either new file size or new checksum, update node values and flag node as updated
            if node_updated:
                node['size'] = node_size
                node['checksum'] = node_checksum
                node['_updated'] = node_updated

        # Update db records for all updated nodes
        self._save_nodes_to_db(nodes, fields=['checksum', 'size'], updated_only=True)

        self._save_action_completion_timestamp(action, 'checksums')
        self._logger.debug('Checksums processing OK')
        return nodes

    def _process_metadata_publication(self, action, nodes):
        self._logger.debug('Processing metadata publication...')

        if not nodes:
            nodes = self._get_nodes_associated_with_action(action)

        metadata_start_time = current_time()

        for node in nodes:
            node['metadata'] = metadata_start_time

        technical_metadata = self._aggregate_technical_metadata(action, nodes)

        self._publish_metadata(technical_metadata)

        self._save_nodes_to_db(nodes, fields=['metadata'])
        self._save_action_completion_timestamp(action, 'metadata')
        self._logger.debug('Metadata publication OK')

    def _process_metadata_repair(self, action, nodes):
        self._logger.debug('Processing metadata repair...')

        if not nodes:
            nodes = self._get_nodes_associated_with_action(action)

        metadata_start_time = current_time()

        for node in nodes:
            node['metadata'] = metadata_start_time

        technical_metadata = self._aggregate_technical_metadata(action, nodes)

        self._repair_metadata(technical_metadata, action)

        self._save_nodes_to_db(nodes, fields=['metadata'])
        self._save_action_completion_timestamp(action, 'metadata')
        self._logger.debug('Metadata repair OK')

    def _aggregate_technical_metadata(self, action, nodes):
        self._logger.debug('Aggregating technical metadata...')

        technical_metadata = []

        for node in nodes:
            if self._graceful_shutdown_started:
                raise SystemExit
            technical_metadata.append(self._get_metadata_for_file(action, node))

        return technical_metadata

    def _get_metadata_for_file(self, action, node):
        """
        Gather metadata for a single node of type 'file', in a form that is accepted by Metax
        """
        file_metadata = {
            'byte_size': node['size'],
            'checksum': {
                'value': self._get_checksum_value(node['checksum']),
                'algorithm': 'SHA-256',
                'checked': action['checksums'],
            },
            'file_frozen': node['frozen'],
            'file_modified': node['modified'],
            'file_name': os.path.split(node['pathname'])[1],
            'file_path': node['pathname'],
            'file_storage': self.file_storage,
            'file_uploaded': node['metadata'],
            'identifier': node['pid'],
            'open_access': True,
            'project_identifier': node['project'],
        }

        user = action.get('user', None)
        if user:
            # the users in metax are normally stored in the Fairdata idm, where user id's include
            # a suffix telling where the id is from. when a user is authenticated using Fairdata auth
            # component, the user's id should always be the fairdata id, suffixed with @fairdataid. in
            # the "linkedIds" section, other linked accounts contain suffixes too. for csc user accounts,
            # the suffix is @cscuserid. while ida is not using Fairdata auth component, append the
            # suffix so we know what id is in question.
            if not user.endswith('@fairdataid'):
                # not authenticated using Fairdata auth component. csc-account instead is assumed
                if not user.endswith('@cscuserid'):
                    # probably this check will be unnecessary, but can never be too sure...
                    user = '%s@cscuserid' % user
            file_metadata['user_created'] = user

        file_format = os.path.splitext(node['pathname'])[1][1:]
        if file_format:
            file_metadata['file_format'] = file_format

        return file_metadata

    def _repair_metadata(self, technical_metadata, action):
        """
        Repair file metadata in Metax.
        """
        self._logger.debug('Repairing file metadata in metax...')

        existing_file_pids = []
        active_file_pids = []
        existing_files = []
        new_files = []
        removed_file_pids = []

        # retrieve PIDs of all active files known by metax which are associated with project
        response = self._metax_api_request('get', '/files?fields=identifier&project_identifier=%s&limit=100000000' % (action['project']))
        # TODO Find more elegant way to unset limit rather than specify insanely high limit
        if response.status_code != 200:
            raise Exception(
                'Failed to retrieve details of frozen files associated with project. HTTP status code: %d. Error messages: %s'
                % (response.status_code, response.content)
            )
        file_data = response.json()
        recieved_count= len(file_data['results'])
        if file_data['count'] != recieved_count:
            raise Exception('Failed to retrieve all records: total = %d returned = %d' % (file_data['count'], recieved_count))
        for record in file_data['results']:
            existing_file_pids.append(record['identifier'])

        # segregate descriptions of all files in technical metadata based on whether they are known to metax or not
        for record in technical_metadata:
            if record['identifier'] in existing_file_pids:
                existing_files.append(record)
            else:
                new_files.append(record)
            active_file_pids.append(record['identifier'])

        # extract PIDs of all files known to metax which are no longer actively frozen
        for pid in existing_file_pids:
            if pid not in active_file_pids:
                removed_file_pids.append(pid)

        active_file_count   = len(active_file_pids)
        existing_file_count = len(existing_files)
        new_file_count      = len(new_files)
        removed_file_count  = len(removed_file_pids)

        self._logger.debug('ACTIVE FILE COUNT:   %d' % (active_file_count))
        self._logger.debug('EXISTING FILE COUNT: %d' % (existing_file_count))
        self._logger.debug('NEW FILE COUNT:      %d' % (new_file_count))
        self._logger.debug('REMOVED FILE COUNT:  %d' % (removed_file_count))

        # PATCH metadata descriptions of all existing files

        if existing_file_count > 0:

            response = self._metax_api_request('patch', '/files', data=existing_files)

            if response.status_code not in (200, 201, 204):
                try:
                    response_json = response.json()
                except:
                    raise Exception(
                        'Metadata update failed, Metax returned an error. HTTP status code: %d. Error messages: %s'
                        % (response.status_code, response.content)
                    )

                if 'failed' in response_json:
                    errors = []
                    for i, entry in enumerate(response_json['failed']):
                        errors.append(str({ 'identifier': entry['object']['identifier'], 'errors': entry['errors'] }))
                        if i > 10:
                            break

                    raise Exception(
                        'Metadata update failed, Metax returned an error. HTTP status code: %d. First %d errors: %s'
                        % (response.status_code, len(errors), '\n'.join(errors))
                    )

                # some unexpected type of error...
                raise Exception(
                    'Metadata update failed, Metax returned an error. HTTP status code: %d. Error messages: %s'
                    % (response.status_code, response.content)
                )

        # POST metadata descriptions of all new files

        if new_file_count > 0:

            response = self._metax_api_request('post', '/files', data=new_files)

            if response.status_code not in (200, 201, 204):
                try:
                    response_json = response.json()
                except:
                    raise Exception(
                        'Metadata publication failed, Metax returned an error. HTTP status code: %d. Error messages: %s'
                        % (response.status_code, response.content)
                    )

                if 'failed' in response_json:
                    errors = []
                    for i, entry in enumerate(response_json['failed']):
                        errors.append(str({ 'identifier': entry['object']['identifier'], 'errors': entry['errors'] }))
                        if i > 10:
                            break

                    raise Exception(
                        'Metadata publication failed, Metax returned an error. HTTP status code: %d. First %d errors: %s'
                        % (response.status_code, len(errors), '\n'.join(errors))
                    )

                # some unexpected type of error...
                raise Exception(
                    'Metadata publication failed, Metax returned an error. HTTP status code: %d. Error messages: %s'
                    % (response.status_code, response.content)
                )

        # DELETE metadata descriptions of all removed files

        if removed_file_count > 0:

            response = self._metax_api_request('delete', '/files', data=removed_file_pids)

            if response.status_code not in (200, 201, 204):
                try:
                    response_json = response.json()
                except:
                    raise Exception(
                        'Metadata deletion failed, Metax returned an error. HTTP status code: %d. Error messages: %s'
                        % (response.status_code, response.content)
                    )

                if 'failed' in response_json:
                    errors = []
                    for i, entry in enumerate(response_json['failed']):
                        errors.append(str({ 'identifier': entry['object']['identifier'], 'errors': entry['errors'] }))
                        if i > 10:
                            break

                    raise Exception(
                        'Metadata deletion failed, Metax returned an error. HTTP status code: %d. First %d errors: %s'
                        % (response.status_code, len(errors), '\n'.join(errors))
                    )

                # some unexpected type of error...
                raise Exception(
                    'Metadata deletion failed, Metax returned an error. HTTP status code: %d. Error messages: %s'
                    % (response.status_code, response.content)
                )


    def _publish_metadata(self, technical_metadata):
        """
        Publish file metadata to Metax.
        """
        self._logger.debug('Publishing file metadata to metax...')

        # TODO Determine if use of ignore_already_exists_errors is correct, or whether an error should be raised
        # if there exists a record for an active file in metax, since that should not be possible if IDA is working
        # correctly... or whether a similar treatment to repair actions should be used, with both POST and PATCH...
        response = self._metax_api_request('post', '/files?ignore_already_exists_errors=true', data=technical_metadata)

        if response.status_code not in (200, 201, 204):
            try:
                response_json = response.json()
            except:
                raise Exception(
                    'Metadata publication failed, Metax returned an error. HTTP status code: %d. Error messages: %s'
                    % (response.status_code, response.content)
                )

            if 'failed' in response_json:
                errors = []
                for i, entry in enumerate(response_json['failed']):
                    errors.append(str({ 'identifier': entry['object']['identifier'], 'errors': entry['errors'] }))
                    if i > 10:
                        break

                raise Exception(
                    'Metadata publication failed, Metax returned an error. HTTP status code: %d. First %d errors: %s'
                    % (response.status_code, len(errors), '\n'.join(errors))
                )

            # some unexpected type of error...
            raise Exception(
                'Metadata publication failed, Metax returned an error. HTTP status code: %d. Error messages: %s'
                % (response.status_code, response.content)
            )

    def _process_metadata_deletion(self, action):
        self._logger.debug('Processing metadata deletion...')

        nodes = self._get_nodes_associated_with_action(action)
        file_identifiers = [ n['pid'] for n in nodes ]
        response = self._metax_api_request('delete', '/files', data=file_identifiers)
        if response.status_code not in (200, 201, 204):
            raise Exception(
                'Metadata deletion failed, Metax returned an error. HTTP status code: %d. Error message: %s'
                % (response.status_code, response.content)
            )
        self._save_action_completion_timestamp(action, 'metadata')

        # ideally, once deletion has been completed, a new message should be published to the replication-queue,
        # which then does whatever it does (probably nothing right now), and places the replication-timestamp once
        # done. that would then trigger the API to place the completed-timestamp. for convenience right now though,
        # immediately place the replication-timestamp. once some processing will happen in replication for deletion,
        # move this to its correct place.
        self._save_action_completion_timestamp(action, 'completed')
        self._logger.debug('Metadata deletion OK')

    def _metax_api_request(self, method, detail_url, data=None, auth=True):
        if auth:
            headers = {
                'Authorization': make_ba_http_header(self._uida_conf_vars['METAX_API_USER'], self._uida_conf_vars['METAX_API_PASS'])
            }
        else:
            headers = None
        return self._http_request(method, '%s%s' % (self._metax_api_url, detail_url), data=data, headers=headers)

    def _complete_actions_without_metax(self):
        """
        It is possible to set a flag in config/config.sh that actions should be marked as completed
        without even trying to connect to metax.

        If value is 0, metax is not connected during action processing:
        - freeze actions are marked as completed once checksums have been
          saved to nodes in IDA
        - unfreeze/delete actions are marked completed immediately
        """
        return self._uida_conf_vars.get('METAX_AVAILABLE', 0) == 0


if __name__ == '__main__':
    print('-- Executing MetadataAgent main --')
    MdA = MetadataAgent()
    MdA.start()
    print('-- MetadataAgent main stopped --')
