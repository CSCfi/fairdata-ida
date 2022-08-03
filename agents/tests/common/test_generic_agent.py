from contextlib import suppress
from json import dumps as json_dumps, loads as json_loads
from time import sleep
import os
import signal

from requests.exceptions import ConnectionError
import responses
import inspect
import sys

from agents.tests.lib import BaseAgentTestCase
from agents.metadata import MetadataAgent
from agents.exceptions import HttpApiNotResponding
from agents.tests.testdata import ida as ida_test_data
import agents.tests.utils as test_utils


class GenericAgentShutdownTests(BaseAgentTestCase):

    """
    Test agent graceful shutdown on shutdown signals SIGINT, SIGTERM.
    """

    def setUp(self):
        super().setUp()
        self._publish_test_messages(index=0)

    @responses.activate
    def test_agent_responds_to_graceful_shutdown_signals(self):
        """
        Ensure receives and responds to SIGINT and SIGTERM.
        """

        print("   %s" % inspect.currentframe().f_code.co_name)

        for SIG_code in [signal.SIGINT, signal.SIGTERM]:

            with self.subTest(SIG_code=SIG_code):

                # catch the signal also in the testcase, in case the agent fails to catch it,
                # otherwise the unittest execution terminates.
                signal.signal(SIG_code, lambda signal, frame: None)

                class MetadataAgentShutdownTester(MetadataAgent):
                    """
                    TestAgent which sends a termination signal to its own process to simulate SIGINT,
                    SIGTERM.
                    """
                    counter = 0
                    def _get_action_record(self, *args, **kwargs):
                        res = super()._get_action_record(*args, **kwargs)
                        # could also launch a thread in the test case which sends the signal,
                        # but this should be effectively the same thing, plus can control the
                        # exact moment when the signal is received, instead of using sleep.
                        os.kill(os.getpid(), SIG_code)
                        return res

                    # NOTE: This overridden method is now incompatible with the revised queue
                    # consumption logic such that entire queues are not consumed on any particular
                    # loop iteration, therefore it is correct and expected that when the iteration
                    # loop is interrupted, that messages can remain in one or more queues. 
                    #
                    # Commenting this out because it is broken, but leaving it here for posterity.
                    #
                    #def messages_in_queue(self, *args, **kwargs):
                    #    """
                    #    Override to break free of listening for new messages, in case the test failed
                    #    and the agent never received the signal.
                    #    """
                    #    res = super().messages_in_queue(*args, **kwargs)
                    #    self.counter += 1
                    #    if self.counter > 2:
                    #        raise Exception('Agent never received shutdown signal')
                    #    return res

                self.agent = MetadataAgentShutdownTester()

                with suppress(SystemExit):
                    self.agent.start()

                self.assertEqual(self.agent._graceful_shutdown_started, True,
                    'Signal "%d" was not caught?' % SIG_code)
                self.assertEqual(len(self.agent.last_completed_sub_action.keys()), 0,
                    'agent should have stopped processing the action')


class GenericAgentMonitoringTests(BaseAgentTestCase):

    """
    Test agent action processing duration monitoring facilities.
    """

    def setUp(self):
        super().setUp()
        self._publish_test_messages(index=0)

    @responses.activate
    def test_sentinel_monitoring_files_are_created_and_destroyed(self):
        """
        Ensure action processing monitoring files are created and destroyed as intended
        at the beginning and end of action processing.
        """

        print("   %s" % inspect.currentframe().f_code.co_name)

        class MetadataAgentMonitoringTester(MetadataAgent):
            monitoring_file_spotted = False
            monitoring_file_contents = None
            def _get_action_record(self, *args, **kwargs):
                res = super()._get_action_record(*args, **kwargs)
                try:
                    with open(self._sentinel_monitoring_file, 'r') as f:
                        self.monitoring_file_spotted = True
                        self.monitoring_file_contents = f.read()
                except FileNotFoundError:
                    print('Monitoring file not found at %s!' % self._sentinel_monitoring_file)
                return res

        self.agent = MetadataAgentMonitoringTester()
        self.agent.consume_one()
        self.assertEqual(self.agent.monitoring_file_spotted, True)
        self.assertEqual('AGENT="%s"' % self.agent.__class__.__name__ in self.agent.monitoring_file_contents, True)
        self.assertEqual(str(self.agent._process_pid) in self.agent.monitoring_file_contents, True,
            self.agent.monitoring_file_contents)
        self.assertEqual(os.path.isfile(self.agent._sentinel_monitoring_file), False,
            'monitoring file should have been removed when message processing ended')

    @responses.activate
    def test_sentinel_monitoring_files_are_cleaned_up_on_shutdown(self):
        """
        Ensure action processing monitoring files are cleaned up when the agent is shut down.
        """

        print("   %s" % inspect.currentframe().f_code.co_name)

        class MetadataAgentMonitoringCleanupTester(MetadataAgent):
            def _get_action_record(self, *args, **kwargs):
                res = super()._get_action_record(*args, **kwargs)
                self._signal_shutdown_started()
                return res

        self.agent = MetadataAgentMonitoringCleanupTester()

        with suppress(SystemExit):
            self.agent.consume_one()

        # ensure cleanup happened due to shutdown, and not due to normally ending action processing...
        self.assertEqual(len(self.agent.last_completed_sub_action.keys()), 0,
            'agent should not have finished processing the action')

        # the actual interesting end result
        self.assertEqual(os.path.isfile(self.agent._sentinel_monitoring_file), False,
            'monitoring file should have been removed when message processing ended')


class GenericAgentWebRequestTests(BaseAgentTestCase):

    """
    Test fault tolerance of general HTTP api requests.
    """

    def setUp(self):
        test_utils.init_rabbitmq()
        self._init_files()
        self.agent = MetadataAgent()
        self._prepare_api_responses()

    def _prepare_api_responses(self):
        """
        Rig IDA api GET /files to always fail.
        """
        action = ida_test_data['actions'][0]

        self._prepare_response(
            responses.GET,
            'ida',
            '/actions/%s' % action['pid'],
            status=200,
            body=json_dumps(action)
        )

        # make every request to retrieve nodes fail
        self._prepare_response(
            responses.GET,
            'ida',
            '/files/action/%s' % action['pid'],
            body=ConnectionError('server not responding, or such')
        )

        # finally, publish a test message matching the prepared api responses
        self.agent.publish_message(action, exchange='actions')
        sleep(0.5)

    @responses.activate
    def test_http_requests_are_retried(self):

        print("   %s" % inspect.currentframe().f_code.co_name)

        self.agent.consume_one()
        # proceeds up to retrieving nodes from IDA api, then retries a few times since the
        # mocked api only returns an error
        self.assertEqual(self.agent._current_http_request_retry, 3)

    @responses.activate
    def test_http_requests_fail_does_not_increment_retries(self):
        """
        IDA api GET /files is mocked to always fail. Ensure failed http requests are republished
        to checksums-failed-waiting queue, and they do not have the field 'retry' set
        in checksums_retry_info, which means HTTP failures do not count towards retry limits.
        """

        print("   %s" % inspect.currentframe().f_code.co_name)

        self.agent.consume_one()

        # ensure message is republished to failed-queue, and retries
        # were not incremented after message was failed
        sleep(0.5)
        self.assertEqual(self.agent.messages_in_queue('checksums-failed-waiting'), 1)

        method, properties, body = self.agent._channel.basic_get('checksums-failed-waiting')
        msg = json_loads(body.decode('utf-8'))
        self.assertEqual('retry' in msg['checksums_retry_info'], False,
            'retry_info should not contain retry count, since http connection error does not count as retry')
