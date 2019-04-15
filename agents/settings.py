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

ONE_MINUTE = 60
ONE_HOUR = ONE_MINUTE * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_HOUR * 7

"""
Production settings are used whenever the application is executed 'normally',
i.e. not within a test suite
"""
production = {
    # file paths to server instance specific configuration file, and service
    # constants file. relative and absolute paths are valid. variables from
    # these files are needed to build the filepath for the requested file.
    "server_configuration_path": "config/config.sh",
    "service_constants_path": "lib/constants.sh",

    "log_level": "INFO", # python logger log level names are valid values

    # when continuously consuming queues, sleep how many seconds between messages
    "main_loop_delay": 10,

    # retry policies for various actions made by the agents during rabbitmq
    # message processing.
    "retry_policy": {

        # the three main goals of processing actions - checksum generation, metadata
        # publication, and replication.
        #
        # specify the max number of times the actions should be retried, in case of
        # any kind of failure, and the delay before the retry shall take place. currently
        # due to the simple setup of dead-letter-exchanges, the retry interval between
        # different retry attempts will have to be the same.
        #
        # exceeding max_retries will result in the action being marked as failed, and
        # the agents will make no more autonomous attempts to complete the action.
        "checksums": {
            "max_retries": 3,
            "retry_interval": 10, # seconds
        },
        "metadata": {
            "max_retries": 3,
            "retry_interval": 10,
        },
        "replication": {
            "max_retries": 3,
            "retry_interval": 10,
        },

        # general http requests sent to http services. a simple loop for retry,
        # with a configurable delay for each retry when the service is not
        # responding. max_retries exceeding will cause an error for the current
        # processing of an action, and the action will be republished (if the
        # max_retries of the action itself permit).
        "http_request": {
            "max_retries": 10,
            "retry_intervals": [
                3,
                10,
                60,
            ],
        },

        # similar to above, except for rabbitmq connections using pika. any kind
        # of failure to communicate with the rabbitmq service itself will attempt
        # to retry according to below settings. max_retries exceeding will cause
        # an error for the current processing of an action, and since rabbitmq
        # cant really be connected for republishing, the message will simply return
        # to its queue, from where it will automatically be retried at a later date.
        # therefore, a failure in rabbitmq connections does not count towards the
        # max_retries of the action itself.
        "rabbitmq_errors": {
            "max_retries": 10,
            "retry_intervals": [
                3,
                10,
                60,
            ],
        }
    },
}

"""
Development settings are used whenever the application is executed in a test environment
as specified via the IDA_ENVIRONMENT variable and thus usually corresponding to a
development environment (but distinct from a automated test environment, as defined
separately below)
"""
development = {
    "server_configuration_path": "config/config.sh",
    "service_constants_path": "lib/constants.sh",

    "log_level": "DEBUG", # python logger log level names are valid values

    "main_loop_delay": 0.1,

    "retry_policy": {
        "checksums": {
            "max_retries": 10,
            "retry_interval": 1, # seconds
        },
        "metadata": {
            "max_retries": 10,
            "retry_interval": 1,
        },
        "replication": {
            "max_retries": 10,
            "retry_interval": 1,
        },
        "http_request": {
            "max_retries": 10,
            "retry_intervals": [
                1,
                1,
                1,
                1,
                1,
                3,
                10,
                60,
            ],
        },
        "rabbitmq_errors": {
            "max_retries": 10,
            "retry_intervals": [
                1,
                1,
                1,
                1,
                1,
                3,
                10,
                60,
            ],
        }
    },
}

"""
Unit test settings are used when executing automated unit tests. In practice, the
distinction between production and test mode is whether or not the module 'unittest' is
loaded in sys.modules
"""
test = {
    "server_configuration_path": "agents/tests/config/config.sh",

    "log_level": "DEBUG",

    "main_loop_delay": 5,

    "retry_policy": {
        "checksums": {
            "max_retries": 3,
            "retry_interval": 5,
        },
        "metadata": {
            "max_retries": 3,
            "retry_interval": 5,
        },
        "replication": {
            "max_retries": 3,
            "retry_interval": 5,
        },
        "http_request": {
            "max_retries": 3,
            "retry_intervals": [
                0.1,
                0.1,
                0.1,
            ],
        },
        "rabbitmq_errors": {
            "max_retries": 3,
            "retry_intervals": [
                0.1,
                0.1,
                0.1,
            ],
        }
    },
}
