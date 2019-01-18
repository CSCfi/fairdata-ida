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

from agents.common import GenericAgent
from agents.utils.utils import construct_file_path, make_ba_http_header, current_time

class MetadataAgent(GenericAgent):

    def __init__(self):
        super(MetadataAgent, self).__init__()
        self._metax_api_url = self._uida_conf_vars['METAX_API_ROOT_URL']
        self.main_queue_name = 'metadata'
        self.failed_queue_name = 'metadata-failed'
        self.file_storage = self._uida_conf_vars['METAX_FILE_STORAGE_ID']

    def process_queue(self, channel, method, properties, action):
        """
        The main method which executes a single action.
        """
        if action['action'] == 'freeze':
            self._handle_freeze_action(action, method)
        elif action['action'] in ('unfreeze', 'delete'):
            self._handle_unfreeze_action(action, method)
        else:
            self._logger.error('Action type = %s is not something we can handle...' % action['action'])

    def _handle_freeze_action(self, action, method):

        # if sub-actions are being successfully executed sequentially, then
        # nodes downloaded during checksums processing will be re-used for
        # metadata publication.
        nodes = None

        if self._sub_action_processed(action, 'checksums'):
            self._logger.info('Checksums already processed')
        else:
            try:
                nodes = self._process_checksums(action)
            except Exception as e:
                self._logger.exception('Checksum processing failed')
                self._republish_or_fail_action(method, action, 'checksums', e)
                return

        if self._complete_actions_without_metax():
            self._logger.info('Note: Completing action without Metax')
            self._save_action_completion_timestamp(action, 'metadata')
        elif self._sub_action_processed(action, 'metadata'):
            self._logger.info('Metadata already processed')
        else:
            try:
                self._process_metadata_publication(action, nodes)
            except Exception as e:
                self._logger.exception('Metadata publication failed')
                self._republish_or_fail_action(method, action, 'metadata', e)
                return

        if self._sub_action_processed(action, 'replication'):
            self._logger.error('Replication already processed...? Okay... Something weird has happened here')
        else:
            self.publish_message(action, exchange='replication')
            self._logger.info('Publishing action %s to replication queue...' % action['pid'])

        self._ack_message(method)

    def _handle_unfreeze_action(self, action, method):
        if self._complete_actions_without_metax():
            self._logger.info('Note: Completing action without Metax')
        elif self._sub_action_processed(action, 'metadata'):
            self._logger.info('Metadata already processed')
        else:
            try:
                self._process_metadata_deletion(action)
            except Exception as e:
                self._logger.exception('Metadata deletion failed')
                self._republish_or_fail_action(method, action, 'metadata', e)
                return
        self._ack_message(method)

    def _process_checksums(self, action):
        self._logger.info('Processing checksums...')

        nodes = self._get_nodes_associated_with_action(action)

        self._logger.debug('Generating checksums...')

        for node in nodes:
            if self._graceful_shutdown_started:
                raise SystemExit
            file_path = construct_file_path(self._uida_conf_vars, node)
            node['checksum'] = self._get_file_checksum(file_path)

        self._save_nodes_to_db(nodes, fields=['checksum'])
        self._save_action_completion_timestamp(action, 'checksums')
        self._logger.info('Checksums processing OK')
        return nodes

    def _process_metadata_publication(self, action, nodes):
        self._logger.info('Processing metadata publication...')

        if not nodes:
            nodes = self._get_nodes_associated_with_action(action)

        metadata_start_time = current_time()
        for node in nodes:
            node['metadata'] = metadata_start_time

        technical_metadata = self._aggregate_technical_metadata(action, nodes)
        self._publish_metadata(technical_metadata)

        self._save_nodes_to_db(nodes, fields=['metadata'])
        self._save_action_completion_timestamp(action, 'metadata')
        self._logger.info('Metadata publication OK')

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
                'value': node['checksum'],
                'algorithm': 'sha2',
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

    def _publish_metadata(self, technical_metadata):
        """
        Publish file metadata to Metax.
        """
        self._logger.debug('Publishing file metadata to metax...')

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
        self._logger.info('Processing metadata deletion...')

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
        self._save_action_completion_timestamp(action, 'replication')

        self._logger.info('Metadata deletion OK')

    def _metax_api_request(self, method, detail_url, data=None):
        headers = {
            'Authorization': make_ba_http_header(self._uida_conf_vars['METAX_API_USER'], self._uida_conf_vars['METAX_API_PASS'])
        }
        return self._http_request(method, '%s%s' % (self._metax_api_url, detail_url), data=data, headers=headers)

    def _complete_actions_without_metax(self):
        """
        It is possible to set a flag in config/config.sh that actions should be marked as completed
        without even trying to connect to metax.

        If value is 0, metax is not connected during action processing:
        - freeze-actions are marked as completed once checksums have been
          saved to nodes in IDA
        - unfreeze/delete actions are marked completed immediately
        """
        return self._uida_conf_vars.get('METAX_AVAILABLE', 0) == 0


if __name__ == '__main__':
    print('-- Executing MetadataAgent main --')
    MdA = MetadataAgent()
    MdA.start()
    print('-- MetadataAgent main stopped --')
