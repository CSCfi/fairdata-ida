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
import time
import glob
import pwd
import signal
import socket
import sys
import pika
import psutil
import requests
import urllib.parse
from contextlib import suppress
from hashlib import sha256
from json import loads as json_loads, dumps as json_dumps
from agents.exceptions import ApiAuthnzError, HttpApiNotResponding, MonitoringFilePermissionError
from agents.utils.utils import get_settings, load_variables_from_uida_conf_files, get_logger, make_ba_http_header, generate_timestamp


class GenericAgent():


    def __init__(self):
        self._channel = None
        self._uida_conf_vars = load_variables_from_uida_conf_files()
        self._settings = get_settings(self._uida_conf_vars)
        self._ida_api_url = self._uida_conf_vars['IDA_API']

        self._hostname = socket.gethostname()
        self._machine_name = self._hostname.split('.')[0]
        self._process_pid = os.getpid()
        self._sentinel_monitoring_file = '%s/%s-%s-%d' % (
            self._uida_conf_vars['RABBIT_MONITORING_DIR'],
            self._hostname,
            self.__class__.__name__,
            self._process_pid
        )
        self.name = self._get_name()        # The name of the agent, displayed in logs

        # Normal queues
        self.main_queue_name = None         # Queue with original, new actions
        self.failed_queue_name = None       # Queue with republished, failed actions

        # Batch queues
        self.main_batch_queue_name = None   # Queue with original, new batch actions
        self.failed_batch_queue_name = None  # Queue with republished, failed batch actions

        self.rabbitmq_message = None        # The message currently being processed from a queue
        self._graceful_shutdown_started = False
        self.gevent = None

        # Diagnostic variables for development and testing
        self.last_completed_sub_action = {}
        self.last_failed_action = {}
        self.last_updated_action = {}

        # Use UTC
        os.environ["TZ"] = "UTC"
        time.tzset()

        # Initialize logger
        self._logger = get_logger(self.name, self._uida_conf_vars)
        self._logger.info("TZ=%s" % str(time.tzname))

        # Perform initial housekeeping
        self.connect()
        self._cleanup_old_sentinel_monitoring_files()

        # On process close, try to remove sentinel monitoring files
        signal.signal(signal.SIGTERM, lambda signal, frame: self._signal_shutdown_started())
        signal.signal(signal.SIGINT, lambda signal, frame: self._signal_shutdown_started())


    def _signal_shutdown_started(self):
        if self._graceful_shutdown_started:
            self._logger.debug('Caught another shutdown signal. Killing process')
            # raises SystemExit, prompting termination immediately
            sys.exit()
        self._logger.info('Caught shutdown signal, begin graceful shutdown...')
        self._graceful_shutdown_started = True


    def _get_name(self):
        return '%s-%s' % (self._machine_name, self.__class__.__name__)


    def connect(self):
        host = self._uida_conf_vars['RABBIT_HOST']
        port = self._uida_conf_vars['RABBIT_PORT']
        vhost = self._uida_conf_vars['RABBIT_VHOST']
        username = self._uida_conf_vars['RABBIT_WORKER_USER']

        self._logger.info('Connecting to rabbitmq at %(host)s:%(port)d, vhost=%(vhost)s, username=%(username)s...' % locals())

        credentials = pika.PlainCredentials(
            username,
            self._uida_conf_vars['RABBIT_WORKER_PASS'],
        )

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host,
                port,
                vhost,
                credentials,
                heartbeat=self._uida_conf_vars['RABBIT_HEARTBEAT']))

        self._channel = connection.channel()
        self._logger.info('Connected')


    def process_queue(self, *args, **kwargs):
        raise NotImplementedError('Inheriting classes must implement this method')


    def dependencies_not_ok(self, *args, **kwargs):
        raise NotImplementedError('Inheriting classes must implement this method')


    def publish_message(self, message, routing_key='', exchange=None, persistent=True, delay=None):
        """
        Publish a new message to an exchange.

        Parameter 'delay' is in seconds.
        """
        properties = {}
        properties_args = {}

        if delay:
            # pika takes the delay in milliseconds
            # delayex exhange type currently not supported in older rabbitmq versions !
            # properties_args['headers'] = { 'x-delay': delay * 1000 }
            pass

        if persistent:
            properties_args['delivery_mode'] = 2

        if properties_args:
            properties = pika.BasicProperties(**properties_args)

        if isinstance(message, dict):
            message = json_dumps(message)

        self._logger.info('Publishing message: exchange: %s routing_key: %s message: %s properties: %s' % (exchange, routing_key, message, properties))
        self._channel.basic_publish(body=message, routing_key=routing_key, exchange=exchange, properties=properties)


    def start(self):
        self._logger.info('%s started' % self.__class__.__name__)
        try:
            self.start_consuming()
        except SystemExit:
            self._logger.info('Stopping due to shutdown signal')
        self._logger.info('%s stopped' % self.__class__.__name__)


    def start_consuming(self):
        """
        Continuously consume messages from the agent's queues, according to queue priority,
        until program is aborted. Using loop pattern instead of channel.basic_consume(callback),
        to properly spread work between different processes working on the same queue.

        If the IDA service enters offline mode, or any of the agent specific dependencies
        are no longer OK, the agent will sleep until the IDA service is again online and all
        agent dependencies are again OK.
        """

        self._logger.info('Started consuming from queues...')

        while True:

            # Only try to consume messages if there exist messages in any of the agent's queues...

            main_queue_not_empty         = self.messages_in_queue(self.main_queue_name)         > 0
            failed_queue_not_empty       = self.messages_in_queue(self.failed_queue_name)       > 0
            main_batch_queue_not_empty   = self.messages_in_queue(self.main_batch_queue_name)   > 0
            failed_batch_queue_not_empty = self.messages_in_queue(self.failed_batch_queue_name) > 0

            if main_queue_not_empty or failed_queue_not_empty or main_batch_queue_not_empty or failed_batch_queue_not_empty:

                is_offline_logged = False

                # Do not consume messages if the sentinel offline file exists
                while self._is_offline():
                    # Log only the first time
                    if not is_offline_logged:
                        self._logger.warning('Sentinel offline file present. Sleeping...')
                        is_offline_logged = True
                    time.sleep(60)

                if is_offline_logged:
                    self._logger.info('Sentinel offline file no longer present. Resuming...')

                dependencies_not_ok_logged = False

                # Do not consume messages if any dependencies required by the agent are not met
                while self.dependencies_not_ok():
                    # Log only the first time
                    if not dependencies_not_ok_logged:
                        self._logger.warning('Dependencies not OK. Sleeping...')
                        dependencies_not_ok_logged = True
                    time.sleep(60)

                if dependencies_not_ok_logged:
                    self._logger.info('Dependencies OK. Resuming...')

                # On each iteration, a message is consumed from the agent's queues with the following priority:
                #     failed_queue_name
                #     main_queue_name
                #     failed_batch_queue_name
                #     main_batch_queue_name
                # This ensures that user-initiated actions take precidence over batch actions. The prioritization
                # is applied on each loop iteration, so that new user-initiated actions will be immediately
                # processed even if there are many batch actions queued.

                if failed_queue_not_empty:
                    self.consume_one(self.failed_queue_name)
                elif main_queue_not_empty:
                    self.consume_one(self.main_queue_name)
                elif failed_batch_queue_not_empty:
                    self.consume_one(self.failed_batch_queue_name)
                elif main_batch_queue_not_empty:
                    self.consume_one(self.main_batch_queue_name)

            if self.gevent:
                # other agents being executed in the same process. the main loop will
                # sleep when it sees fit.
                self.gevent.sleep(0)
            else:
                # only this agent is being executed in this process
                time.sleep(self._settings['main_loop_delay'])


    def consume_one(self, queue=None):
        """
        By default consumes one message from self.main_queue_name, but queue name
        can be passed to consume other queues, most importantly self.failed_queue_name.

        This is the highest level of error handling, so need to deal with the errors that
        persisted all the way up here. In all cases, the resolution is to first try republish
        the message if possible (unless the error was with Pika/rabbitmq itself), or otherwise,
        pretty much not care about the error, and not ack the message, so that it will return
        to its original queue, and be processed again later.
        """
        queue = queue or self.main_queue_name

        self._logger.info('Consuming one message from %s queue' % queue)

        try:
            method, properties, body = self._channel.basic_get(queue)
        except pika.exceptions.ChannelClosed:
            self._logger.exception('Channel was closed. Retrying later...')
            return

        if not body:
            self._logger.warning('Tried to consume from queue, but message body was None. No messages in queue?')
            return

        try:
            action = self._get_action_record(body.decode('utf-8'))

            if action:
                self._logger.info('Started processing action %s' % action)
                self.process_queue(self._channel, method, properties, action, queue)
            else:
                self._logger.warning(
                    'Rabbitmq message did not match an action in IDA. Discarding. Received: %s'
                    % str(body.decode('utf-8'))
                )
                self._reject_message(method)

        except SystemExit:
            self._logger.info('Rejecting message back to queue due to shutdown signal')
            with suppress(Exception):
                # will get returned to queue automatically if there is some failure
                self._reject_message(method, requeue=True)
            raise
        except:
            self._logger.exception(
                'Unhandled exception during process_queue(). Rejecting message back to original queue,'
                ' hopefully the problem will be fixed by then.'
            )
            try:
                # no delay, since it is unknown at which phase the error occurred.
                # it is possible that the immediate next message can be processed up until a certain
                # part, where this exception happens again.
                self._reject_message(method, requeue=True)
            except:
                # reject failed? doesnt matter, dont ack the message so it will return
                # to its queue and be retried in the future.
                self._logger.exception('Exception while trying to reject action')
            else:
                self._logger.info('Rejected action %s back to original queue' % json_loads(body.decode('utf-8'))['pid'])
        else:
            self._logger.debug('Message processing ended')
        finally:
            self.rabbitmq_message = None
            self._remove_sentinel_monitoring_file()


    def messages_in_queue(self, queue=None):
        """
        By default checks queue from self.main_queue_name, but queue name can be passed as well.

        If the query to the queue fails, due to a closed or otherwise disfunctional connection,
        the agent will attempt to reopen the connection.
        """
        if self._graceful_shutdown_started:
            raise SystemExit

        queue = queue or self.main_queue_name

        try:
            queue_state = self._channel.queue_declare(queue, durable=True, passive=True)
        except Exception:
            self._logger.warning('Checking messages in %s queue encountered an error: %s  Re-connecting...' % (queue, str(e)))
            self.connect()
            try:
                queue_state = self._channel.queue_declare(queue, durable=True, passive=True)
            except Exception as e:
                self._logger.warning('Checking messages in %s queue encountered an error: %s  Sleeping for a bit and retrying later...' % (queue, str(e)))
                time.sleep(5)
                return 0

        if queue_state.method.message_count == 1:
            self._logger.info('1 message in %s queue' % queue)
        elif queue_state.method.message_count > 1:
            self._logger.info('%d messages in %s queue' % (queue_state.method.message_count, queue))
        #else:
        #    self._logger.debug('The %s queue is empty' % queue)

        return queue_state.method.message_count


    def _get_action_record(self, message):
        """
        Get from db the related action record, using the message that
        was received from the rabbitmq message queue.
        """
        self._logger.debug('Retrieving action record...')

        try:
            message = json_loads(message)
        except:
            self._logger.exception(
                'Could not convert message to dictionary in _get_action_record().'
                ' Message content was: %(message)s.' % locals()
            )
            return None

        self._set_sentinel_monitoring_file(message)

        # the message in the queue is kept separate from the actual action record.
        # when a record fails, more info is stored in the queue message, but not on the
        # action record, which represents what is stored in the db.
        self.rabbitmq_message = message

        response = self._ida_api_request('get', '/actions/%s' % message['pid'], message)

        if response.status_code == 404:
            self._logger.warning('Action %s not found in ida (404)' % message['pid'])
            return None
        elif response.status_code != 200:
            raise Exception(
                'IDA api returned an error when trying to retrieve action record. Code: %d. Error: %s' % (response.status_code, response.content)
            )

        try:
            action_record = response.json()
        except:
            self._logger.exception(
                'Could not get json from http response - instead response has the following content: %s' % response.content
            )
            raise

        return action_record


    def _get_nodes_associated_with_action(self, action):
        self._logger.info('Retrieving files associated with action %s' % action['pid'])
        response = self._ida_api_request('get', '/files/action/%s' % action['pid'], action)
        if response.status_code != 200:
            raise Exception(
                'IDA api returned an error. Code: %d. Error: %s' % (response.status_code, response.content)
            )
        nodes = response.json()
        if not isinstance(nodes, list):
            nodes = [nodes]
        # NOTE: it is possible for a repair action to have no associated files, if after re-scanning
        # the project frozen area there no longer exist any files in the frozen area.
        self._logger.info('Retrieved %d files associated with action %s' % (len(nodes), action['pid']))
        return nodes


    def _save_nodes_to_db(self, nodes, fields=[], updated_only=False):
        assert len(fields), 'need to specify fields to update for node.'

        self._logger.debug('Saving node fields %s to IDA db...' % str(fields))

        for node in nodes:

            update_node = True

            if updated_only:
                # Only update nodes which are flagged as having been updated
                update_node = node.get('_updated', False)

            if update_node:

                # Update IDA frozen file record
                data = {}
                for field in fields:
                    data[field] = node[field]
                response = self._ida_api_request('post', '/files/%s' % node['pid'], data=data)
                if response.status_code not in (200, 201, 204):
                    error_msg = 'IDA API returned an error when trying to update frozen file record for pid %s. Error message from API: %s'
                    raise Exception(error_msg % (node['pid'], str(response.content)))

                # If a checksum mismatch was reported for a repair action, repair the checksum in the Nextcloud file cache
                if node.get('_checksum_mismatch', False):
                    data = { 'pathname': 'frozen%s' % node['pathname'], 'checksum': node['checksum'] }
                    response = self._ida_api_request('post', '/repairCacheChecksum', data=data)
                    if response.status_code not in (200, 201, 204):
                        error_msg = 'IDA API returned an error when trying to update cache checksum for pid %s. Error message from API: %s'
                        raise Exception(error_msg % (node['pid'], str(response.content)))


    def _sub_action_processed(self, action, sub_action_name):
        """
        If a sub-action timestamp is set, the sub action has already been successfully completed.
        """
        if bool(action.get(sub_action_name, None)):
            # ^ bool() to make sure possible empty strings and other falsyness dont cause trouble
            return True
        return False


    def _save_action_completion_timestamp(self, action, sub_action_name):
        """
        Update the action being processed with a sub-action's completion timestamp,
        and save to db.
        """
        self._logger.info('Updating %s timestamp in IDA db for action %s' % (sub_action_name, action['pid']))

        # update existing action record in memory with the timestamp as well for convenience,
        # although not strictly necessary.
        action[sub_action_name] = generate_timestamp()

        self._update_action_to_db(action, { sub_action_name: action[sub_action_name] })
        self.last_completed_sub_action = {
            'action_pid': action['pid'],
            sub_action_name: action[sub_action_name],
        }


    def _save_action_failed_timestamp(self, action, exception):
        """
        The action has completely failed despite retries: Update the action
        being processed with a failed-timestamp and error description, and save to db.

        The action will no longer be automatically retried.
        """
        self._logger.info('Updating failed timestamp in IDA db for action %s' % action['pid'])
        error_data = { 'failed': generate_timestamp(), 'error': str(exception) }
        self._update_action_to_db(action, error_data)
        self._logger.warning('Marked action %s as failed' % action['pid'])
        self.last_failed_action = { 'action_pid': action['pid'], 'data': error_data }
        return True


    def _action_should_be_retried(self, sub_action_name):
        """
        Compare current retry-count of a sub-action to the sub-action's retry policy in the settings.
        """
        sub_action_retry_info = '%s_retry_info' % sub_action_name
        if sub_action_retry_info in self.rabbitmq_message:
            return self.rabbitmq_message[sub_action_retry_info]['retry'] < self._settings['retry_policy'][sub_action_name]['max_retries']
        return True


    def _republish_or_fail_action(self, method, action, sub_action_name, queue, exception):
        """
        All exceptions raised during message processing go through this method, where
        the exception is evaluated whether or not it should be retried.

        Parameter 'method' is rabbitmq message method, needed to ack the message.
        """
        if self._action_should_be_retried(sub_action_name):
            success = self._republish_action(sub_action_name, exception, queue)
        else:
            success = self._save_action_failed_timestamp(action, exception)

        if success:
            self._ack_message(method)
        else:
            # failure to republish or fail an action will result in the message not
            # getting ack'd, and action will return to queue
            pass


    def _republish_action(self, sub_action_name, exception, queue):
        """
        An action has information about a sub-action's retries saved in the key
        'sub_action_name + _retry_info'. No key present means it has never been retried yet.

        Note that this retry-information is never saved into the db, only in the action that is
        currently being circulated in the rabbitmq exchanges.

        Returns:
        - True when action is successfully republished
        - False when republish fails. Results in the message not being ack'ed, and message
          will return to its original queue.
        """
        action = self.rabbitmq_message
        pid = action['pid']

        self._logger.info('Republishing failed action %s...' % pid)

        sub_action_retry_info = '%s_retry_info' % sub_action_name

        if sub_action_retry_info not in action:
            action[sub_action_retry_info] = {}

        action[sub_action_retry_info]['previous_error'] = str(exception)
        action[sub_action_retry_info]['previous_attempt'] = generate_timestamp()
        retry_interval = self._settings['retry_policy'][sub_action_name]['retry_interval']

        if isinstance(exception, HttpApiNotResponding):
            # api-not-responding errors do not count towards retries, so that they may be
            # retried an infinite number of times.
            self._logger.info('Republishing action %s to %s-failed-waiting due to failed HTTP request' % (pid, sub_action_name))
        else:
            try:
                action[sub_action_retry_info]['retry'] += 1
            except KeyError:
                action[sub_action_retry_info]['retry'] = 1

            self._logger.debug('Next retry #: %d, retry interval of %s-failed-waiting: %d seconds'
                % (action[sub_action_retry_info]['retry'], sub_action_name, retry_interval))

        try:
            # Publish action to i.e. checksums-failed-waiting or batch-checksums-failed-waiting,
            # from where it will be dead-lettered to a queue called metadata-failed or batch-metadata-failed
            # once its specified retry_interval has expired.
            if queue == 'replication' or queue == 'replication-failed' or queue == 'metadata' or queue == 'metadata-failed':
                self.publish_message(action, routing_key='%s-failed-waiting' % sub_action_name, exchange='actions-failed')
            elif queue == 'batch-replication' or queue == 'batch-replication-failed' or queue == 'batch-metadata' or queue == 'batch-metadata-failed':
                self.publish_message(action, routing_key='batch-%s-failed-waiting' % sub_action_name, exchange='batch-actions-failed')

        except:
            # could not publish? doesnt matter, the message will return to its queue and be retried
            # at some point.
            self._logger.warning('Action %s republish failed. Message will return to original queue and be retried in the future' % pid)
            return False

        self._logger.info('Successfully republished action %s with a delay of %d seconds' % (pid, retry_interval))

        return True


    def _reject_message(self, method, requeue=False):
        """
        A message was being processed, but ended in an error. Reject the message,
        so that it is removed from the queue.

        If parameter requeue=True, the message will be requeued back to its original queue.
        """
        try:
            self._channel.basic_reject(delivery_tag=method.delivery_tag, requeue=requeue)
        except:
            # could not connect? doesnt matter, the next worker knows where to
            # continue based on the placed sub-action timestamps
            self._logger.warning('self._channel.basic_reject() failed')


    def _ack_message(self, method):
        """
        A message has been fully and successfully processed by this agent on its part.
        Ack the message, so the message is removed from the queue.
        """
        try:
            self._channel.basic_ack(delivery_tag=method.delivery_tag)
        except:
            # could not connect? doesnt matter, all the sub-action timestamps
            # have been placed, so the next worker knows where to continue
            self._logger.warning('self._channel.basic_ack() failed')


    def _update_action_to_db(self, action, data):
        self._ida_api_request('post', '/actions/%s' % action['pid'], data=data)
        self.last_updated_action = { 'action_pid': action['pid'], 'data': data }


    def _ida_api_request(self, method, detail_url, data=None):
        username = '%s%s' % (self._uida_conf_vars['PROJECT_USER_PREFIX'], self.rabbitmq_message['project'])
        password = self._uida_conf_vars['PROJECT_USER_PASS']

        headers = {
            "Authorization": make_ba_http_header(username, password)
        }

        res = self._http_request(method, '%s%s' % (self._ida_api_url, detail_url), data=data, headers=headers)

        if 'user is not logged in' in str(res.content.lower()):
            raise Exception('Authentication failed during ida2 api request. Error: %s' % str(res.content))

        return res


    def _http_request(self, method, url, data=None, headers=None):
        """
        Send http request to a web api, and retry a few times according to settings when failing
        """
        if self._graceful_shutdown_started:
            raise SystemExit

        _headers = { 'Content-type': 'application/json' }

        if headers:
            _headers.update(headers)

        if type(data) in (dict, list):
            data = json_dumps(data)

        retry_policy = self._settings['retry_policy']['http_request']
        self._current_http_request_retry = 0 # make an attribute, so that it can be observed during testing

        for i in range(1, retry_policy['max_retries'] + 1):
            try:
                self._logger.debug('HTTP %s request to %s' % (method.upper(), url))
                self._logger.debug('Headers: %s' % json_dumps(_headers))
                self._logger.debug('Data: %s' % data)
                self._current_http_request_retry += 1

                if url.startswith("https://localhost/"):
                    self._logger.debug('Verify: False')
                    response = getattr(requests, method)(url, data=data, headers=_headers, verify=False)
                else:
                    response = getattr(requests, method)(url, data=data, headers=_headers)

                self._logger.debug('Response: %d %s' % (response.status_code, response.content))
                if response.status_code in (401, 403):
                    raise ApiAuthnzError(
                        'Authentication error on HTTP %s request to %s: %d %s'
                        % (method, url, response.status_code, response.content)
                    )

                return response

            except ApiAuthnzError as e:
                self._logger.error(e)
                # no retries for you
                raise
            except Exception as e:
                if self._graceful_shutdown_started:
                    raise SystemExit

                # use each retry_interval step, and start repeating the last (longest) step for every exceeding loop
                retry_index = i - 1 if i - 1 < len(retry_policy['retry_intervals']) else -1

                self._logger.warning(
                    'HTTP %s request to %s resulted in an error: %s. This does not count towards retries. Retrying in %d seconds...'
                    % (method, url, str(e), retry_policy['retry_intervals'][retry_index])
                )
                time.sleep(retry_policy['retry_intervals'][retry_index])

        raise HttpApiNotResponding('HTTP %s request %s did not respond after %d attempts'
            % (method, url, self._current_http_request_retry))


    def _get_cache_checksum(self, pathname):
        """
        Retrieve Nextcloud cache checksum, if any, for frozen file with specified relative pathname
        """

        response = self._ida_api_request('get', '/retrieveCacheChecksum?pathname=%s' % urllib.parse.quote('frozen%s' % pathname))
        if response.status_code not in (200, 201, 204):
            return None
        node = response.json()
        checksum = node.get('checksum', None)
        if checksum is not None and isinstance(checksum, str) and checksum.strip() != '':
            return checksum.lower()
        return None


    def _get_file_checksum(self, file_path, block_size=65536):
        """
        Generate an SHA-256 checksum for the specified file
        """
        sha = sha256()
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                sha.update(block)
        checksum = sha.hexdigest()
        if checksum is not None and isinstance(checksum, str) and checksum.strip() != '':
            return checksum.lower()
        return None


    def _get_checksum_value(self, checksum):
        """
        Return a plain checksum value, given either a SHA-256 checksum URI or a plain checksum value
        Normalize returned string to lowercase
        """
        if checksum is not None and isinstance(checksum, str) and checksum.strip() != '':
            checksum = checksum.lower()
            if checksum.startswith('sha256:'):
                return checksum[7:]
            return checksum
        return None


    def _get_checksum_uri(self, checksum):
        """
        Return an SHA-256 checksum URI, given either a plain SHA-256 checksum value or a SHA-256 checksum URI
        Normalize returned string to lowercase
        """
        if checksum is not None and isinstance(checksum, str) and checksum.strip() != '':
            checksum = checksum.lower()
            if checksum.startswith('sha256:'):
                return checksum
            return 'sha256:%s' % checksum
        return None


    def _is_offline(self):
        """
        Check if the sentinel offline file exists.
        """
        _sentinel_offline_file = "%s/control/OFFLINE" % self._uida_conf_vars['STORAGE_OC_DATA_ROOT']
        if os.path.isfile(_sentinel_offline_file):
            return True
        else:
            return False


    def _set_sentinel_monitoring_file(self, message):
        """
        Create a sentinel monitoring file at the beginning of message processing, to know
        how long an agent is processing a message.
        """
        os.makedirs(self._uida_conf_vars['RABBIT_MONITORING_DIR'], exist_ok=True)
        try:
            with open(self._sentinel_monitoring_file, 'w') as f:
                f.write(
                    '# a sentinel file for monitoring message process duration of an IDA postprocessing agent.\n'
                    '# this file is automatically destroyed by the agent when message processing has ended.\n'
                    'HOST="%s"\n'
                    'AGENT="%s"\n'
                    'PROCESS_ID=%d\n'
                    'PROJECT="%s"\n'
                    'ACTION="%s"\n'
                    'ACTION_PID="%s"\n'
                    'PROCESSING_STARTED="%s"\n'
                    % (self._hostname, self.__class__.__name__, self._process_pid, message['project'], message['action'], message['pid'], generate_timestamp())
                )
        except PermissionError:
            st = os.stat(self._sentinel_monitoring_file)
            owner = pwd.getpwuid(st.st_uid).pw_name
            raise MonitoringFilePermissionError(
                'Unable to create sentinel file at %s: Operation not permitted. The file already existed, '
                'and is owned by: %s. The agent will refuse to process messages until it can create a '
                'monitoring file.'
                % (self._sentinel_monitoring_file, owner)
            )


    def _remove_sentinel_monitoring_file(self):
        """
        Remove monitoring file when message processing has ended.
        """
        self._logger.debug('Removing sentinel monitoring file...')
        try:
            os.remove(self._sentinel_monitoring_file)
        except FileNotFoundError:
            self._logger.debug('Monitoring file not found')
        except PermissionError:
            st = os.stat(self._sentinel_monitoring_file)
            owner = pwd.getpwuid(st.st_uid).pw_name
            # log the error, but do not raise an exception. at this point, the message has already
            # been processed, whether it was a success or not. an error will get raised when
            # the agent tries to create a new monitoring file.
            self._logger.error(
                'Unable to delete sentinel file at %s: Operation not permitted. File is owned by: %s'
                % (self._sentinel_monitoring_file, owner)
            )
        else:
            self._logger.debug('Done')


    def _cleanup_old_sentinel_monitoring_files(self):
        """
        Cleanup old sentinel monitoring files of no longer existing agent processes, which can loiter
        around due to crashes or other scenarios where the agent could not react to sigterm or sigint.
        Removes old monitoring files of all types of agents from the same host.
        """
        if not os.path.isdir(self._uida_conf_vars['RABBIT_MONITORING_DIR']):
            return

        self._logger.info('Cleaning up old sentinel monitoring files from %s...' % self._uida_conf_vars['RABBIT_MONITORING_DIR'])

        # recognizes current active processes when the process is started with a
        # command e.g. python -m agents.metadata.metadata_agent
        active_agent_processes = [
            p.info['pid'] for p in psutil.process_iter(attrs=['pid', 'name', 'cmdline'])
            if 'python' in p.info['name']
            and 'cmdline' in p.info
            and len(p.info['cmdline']) > 1
            and p.info['cmdline'][-1].startswith('agents.')
            and p.info['cmdline'][-1].endswith('_agent')
        ]

        old_monitoring_files = glob.glob(
            '%s/%s-*' % (self._uida_conf_vars['RABBIT_MONITORING_DIR'], self._hostname)
        )

        deleted_files_count = 0

        for file in old_monitoring_files:
            for active_pid in active_agent_processes:
                if file.endswith(str(active_pid)):
                    # monitoring file of an active process. do not remove!
                    break
            else:
                # the above loop went all the way through without breaking - the file is an old monitoring file.
                try:
                    os.remove(file)
                except FileNotFoundError:
                    # some other process got there first? thats fine
                    pass
                except PermissionError:
                    # log warning for informational purposes only. manual intervention needed to
                    # clean em up, but not fatal for agent functioning.
                    self._logger.warning(
                        'Unable to remove old sentinel monitoring file due to permission issues. File: %s'
                        % file
                    )
                deleted_files_count += 1

        self._logger.debug('Removed %d old monitoring files' % deleted_files_count)
