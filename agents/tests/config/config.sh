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

#
# Variablies defined in this file will replace matching variables
# loaded from the real production config/config.sh configuration
# file during postprocessing agent automatic testcase execution.
#

RABBIT_VHOST="test-ida-vhost"
RABBIT_WORKER_USER="user"
RABBIT_WORKER_PASS="pass"
RABBIT_WORKER_LOG_FILE="agents/tests/tests.log"
RABBIT_MONITORING_DIR="/tmp/rabbitmq_monitoring_tests"

# Defining these urls here to make it obvious that these apis are actually mocked
IDA_API="https://mock.ida-api"
METAX_API="https://mock.metax-api"

METAX_AVAILABLE=1
METAX_FILE_STORAGE_ID=1

METAX_USER="user"
METAX_PASS="pass"

STORAGE_OC_DATA_ROOT="/tmp/ida2_data_root"
DATA_REPLICATION_ROOT="/tmp/ida/replication"
