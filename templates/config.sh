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

IDA_ENVIRONMENT="TEST"
DEBUG="true"

HTTPD_USER="apache"

NC_ADMIN_USER="admin"
NC_ADMIN_PASS="****"
PROJECT_USER_PASS="****"
TEST_USER_PASS="****"
BATCH_ACTION_TOKEN="****"

DBTYPE="pgsql"
DBNAME="nextcloud"
DBHOST="localhost"
DBPORT=5432
DBTABLEPREFIX="oc_"
DBUSER="nextcloud"
DBPASSWORD="****"
#DBROUSER="inspector"
#DBROPASSWORD="****"

RABBIT_HOST="localhost"
RABBIT_PORT=5672
RABBIT_WEB_API_PORT=15672
RABBIT_VHOST="ida-vhost"
RABBIT_ADMIN_USER="admin"
RABBIT_ADMIN_PASS="****"
RABBIT_WORKER_USER="worker"
RABBIT_WORKER_PASS="****"
RABBIT_WORKER_LOG_FILE="/mnt/storage_vol01/log/agents-ida-test.log"
RABBIT_HEARTBEAT=0
RABBIT_MONITOR_USER="monitor"
RABBIT_MONITOR_PASS="****"
RABBIT_MONITORING_DIR="/mnt/storage_vol01/log/rabbitmq_monitoring"

METAX_AVAILABLE=1
METAX_FILE_STORAGE_ID="urn:nbn:fi:att:file-storage-ida"
METAX_FILE_STORAGE_ID=1
METAX_API_USER="ida"
METAX_API_ROOT_URL="https://localhost/rest/v1"
METAX_API_RPC_URL="https://localhost/rpc/v1"
METAX_API_PASS="****"

ROOT="/var/ida"
OCC="$ROOT/nextcloud/occ"
LOG="/mnt/storage_vol01/log/ida-test.log"

IDA_API_ROOT_URL="https://localhost/apps/ida/api"

IDA_CLI_ROOT="/var/ida-tools" # only required for automated tests, not for service run-time

URL_BASE_SHARE='https://localhost/ocs/v1.php/apps/files_sharing/api/v1/shares'
URL_BASE_FILE='https://localhost/remote.php/webdav'
URL_BASE_GROUP='https://localhost/ocs/v1.php/cloud/groups'
URL_BASE_IDA="https://localhost/apps/ida"

LDAP_HOST_URL="ldaps://localhost"
LDAP_BIND_USER="uid=irodsbind,ou=Special Users,dc=csc,dc=fi"
LDAP_PASSWORD="****"
LDAP_SEARCH_BASE="ou=idm,dc=csc,dc=fi"

DMF_SERVER="dmf.csc.fi"
DMF_STATUS="/var/ida/agents/replication/dmfstatus"

# multiple local storage volumes
STORAGE_CANDIDATES=("/mnt/storage_vol01/ida" "/mnt/storage_vol02/ida")
STORAGE_OC_DATA_ROOT="/mnt/storage_vol01/ida"

DATA_REPLICATION_ROOT="/mnt/storage_vol02/ida_replication"

PYTHON="/opt/fairdata/python3/bin/python" 

TRASH_DATA_ROOT="/mnt/storage_vol02/ida_trash"
QUARANTINE_PERIOD="2592000"
# 2592000 seconds = 30 days

EMAIL_SENDER="root@localhost"
EMAIL_RECIPIENTS="root@localhost"
