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

MIGRATION_ACTIVE="false"

SHARE_PROJECT_AFTER_TS=1529322748

IDA_ENVIRONMENT="TEST"

HTTPD_USER="apache"

NC_ADMIN_USER="admin"
NC_ADMIN_PASS="test"

PROJECT_USER_PASS="test"

ROOT="/var/ida"
OCC="$ROOT/nextcloud/occ"

STORAGE_OC_DATA_ROOT="/mnt/storage_vol01/ida"
STORAGE_CANDIDATES=("/mnt/storage_vol01/ida" "/mnt/storage_vol02/ida")

DATA_REPLICATION_ROOT="/var/ida-data-replication"

URL_BASE_SHARE="http://localhost/ocs/v1.php/apps/files_sharing/api/v1/shares"
URL_BASE_FILE="http://localhost/remote.php/webdav"
URL_BASE_GROUP="http://localhost/ocs/v1.php/cloud/groups"
URL_BASE_IDA="http://localhost/apps/ida"

IDA_API_ROOT_URL="http://localhost/apps/ida/api"

LOG="/mnt/storage_vol01/log/ida.log"

RABBIT_HOST="localhost"
RABBIT_PORT=5672
RABBIT_WEB_API_PORT=15672
RABBIT_VHOST="ida-vhost"
RABBIT_ADMIN_USER="admin"
RABBIT_ADMIN_PASS="test"
RABBIT_WORKER_USER="worker"
RABBIT_WORKER_PASS="test"
RABBIT_WORKER_LOG_FILE="/mnt/storage_vol01/log/ida-agents.log"
RABBIT_MONITOR_USER="monitor"
RABBIT_MONITOR_PASS="test"
RABBIT_HEARTBEAT=0 # seconds. 0 == disabled
RABBIT_MONITORING_DIR="/mnt/rabbitmq_monitoring"

METAX_API_ROOT_URL="https://metax.csc.fi/rest/v1"
METAX_AVAILABLE=1
METAX_FILE_STORAGE_ID=1

METAX_API_ROOT_URL="https://metax.csc.local/rest/v1"
METAX_API_USER="ida"
METAX_API_PASS="test-ida"
METAX_AVAILABLE=1 # If 0, the metadata publication agent will not try to store metadata to METAX

LDAP_HOST_URL="ldaps://ldaphost.domain.com"
LDAP_BIND_USER="uid=username,ou=group,dc=domain,dc=com;"
LDAP_PASSWORD="password"
LDAP_SEARCH_BASE="ou=scope,dc=domain,dc=com"

# 2592000 seconds = 30 days
QUARANTINE_PERIOD="2592000"
TRASH_DATA_ROOT="/mnt/storage_vol02/ida_trash"

EMAIL_SENDER="root@localhost"
EMAIL_RECIPIENTS="root@localhost"

