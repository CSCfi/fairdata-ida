# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2019 Ministry of Education and Culture, Finland
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
# Initialize script with common definitions

INIT_FILE=`dirname $0`/../../lib/init_script.sh

if [ -e $INIT_FILE ]
then
    . $INIT_FILE
else
    echo "The initialization file $INIT_FILE cannot be found. Aborting." >&2
    exit 1
fi

DEBUG="false"

#--------------------------------------------------------------------------------
# Process input and get project name, per default script behavior

if [ "$USAGE" = "" ]; then
    USAGE="Usage: $SCRIPT project_name"
fi

if [ "$PROJECT" = "" ]; then
    PROJECT=`echo "$1" | sed -e 's/ *//g' `
fi

if [ "$PROJECT" = "" ]; then
    echo "$USAGE" >&2
    exit 1
fi

#--------------------------------------------------------------------------------
# Verify required variables are defined

if [ "$NC_ADMIN_USER" = "" ]; then
    echo "Error: The variable NC_ADMIN_USER must be defined." >&2
    exit 1
fi

if [ "$NC_ADMIN_PASS" = "" ]; then
    echo "Error: The variable NC_ADMIN_PASS must be defined." >&2
    exit 1
fi

if [ "$METAX_API_USER" = "" ]; then
    echo "Error: The variable METAX_API_USER must be defined." >&2
    exit 1
fi

if [ "$METAX_API_PASS" = "" ]; then
    echo "Error: The variable METAX_API_PASS must be defined." >&2
    exit 1
fi

if [ "$HTTPD_USER" = "" ]; then
    echo "Error: The variable HTTPD_USER must be defined." >&2
    exit 1
fi

if [ "$PROJECT_USER_PASS" = "" ]; then
    echo "Error: The variable PROJECT_USER_PASS must be defined." >&2
    exit 1
fi

if [ "$PROJECT_USER_PREFIX" = "" ]; then
    echo "Error: The variable PROJECT_USER_PREFIX must be defined." >&2
    exit 1
fi

if [ "$STAGING_FOLDER_SUFFIX" = "" ]; then
    echo "Error: The variable PROJECT_USER_PREFIX must be defined." >&2
    exit 1
fi

if [ "$METAX_API_ROOT_URL" = "" ]; then
    echo "Error: The variable METAX_API_ROOT_URL must be defined." >&2
    exit 1
fi

if [ "$IDA_API_ROOT_URL" = "" ]; then
    echo "Error: The variable IDA_API_ROOT_URL must be defined." >&2
    exit 1
fi

if [ "$ROOT" = "" ]; then
    echo "Error: The variable ROOT must be defined." >&2
    exit 1
fi

if [ "$STORAGE_OC_DATA_ROOT" = "" ]; then
    echo "Error: The variable STORAGE_OC_DATA_ROOT must be defined." >&2
    exit 1
fi

if [ "$DATA_REPLICATION_ROOT" = "" ]; then
    echo "Error: The variable DATA_REPLICATION_ROOT must be defined." >&2
    exit 1
fi

if [ "$OCC" = "" ]; then
    echo "Error: The variable OCC must be defined." >&2
    exit 1
fi

if [ "$LOG" = "" ]; then
    echo "Error: The variable LOG must be defined." >&2
    exit 1
fi

if [ "$EMAIL_SENDER" = "" ]; then
    echo "Error: The variable EMAIL_SENDER must be defined." >&2
    exit 1
fi

if [ "$EMAIL_RECIPIENTS" = "" ]; then
    echo "Error: The variable EMAIL_RECIPIENTS must be defined." >&2
    exit 1
fi

if [ "$TRASH_DATA_ROOT" = "" ]; then
    echo "Error: The variable TRASH_DATA_ROOT must be defined." >&2
    exit 1
fi

if [ "$QUARANTINE_PERIOD" = "" ]; then
    echo "Error: The variable QUARANTINE_PERIOD must be defined." >&2
    exit 1
fi

if [ "$TIMESTAMP" = "" ]; then
    echo "Error: The variable TIMESTAMP must be defined." >&2
    exit 1
fi

PROJECT_USER="${PROJECT_USER_PREFIX}${PROJECT}"
PROJECT_STORAGE_OC_DATA_ROOT="${STORAGE_OC_DATA_ROOT}/${PROJECT_USER}/files"
PROJECT_LOCK="${PROJECT_STORAGE_OC_DATA_ROOT}/LOCK"
PROJECT_REPLICATION_ROOT="${DATA_REPLICATION_ROOT}/projects/${PROJECT}"
PROJECT_TRASH_DATA_ROOT="${TRASH_DATA_ROOT}/${TIMESTAMP}_${PROJECT}"
PROJECT_USER_CREDENTIALS="${PROJECT_USER}:${PROJECT_USER_PASS}"
ADMIN_CREDENTIALS="${NC_ADMIN_USER}:${NC_ADMIN_PASS}"
METAX_CREDENTIALS="${METAX_API_USER}:${METAX_API_PASS}"

ERR="/tmp/${SCRIPT}.$$.err"

if [ "$DEBUG" = "true" ]; then
    echo ""
    echo "NC_ADMIN_USER                $NC_ADMIN_USER"
    echo "NC_ADMIN_PASS                $NC_ADMIN_PASS"
    echo "METAX_API_USER               $METAX_API_USER"
    echo "METAX_API_PASS               $METAX_API_PASS"
    echo "HTTPD_USER                   $HTTPD_USER"
    echo "PROJECT_USER_PASS            $PROJECT_USER_PASS"
    echo "PROJECT_USER_PREFIX          $PROJECT_USER_PREFIX"
    echo "IDA_API_ROOT_URL             $IDA_API_ROOT_URL"
    echo "METAX_API_ROOT_URL           $METAX_API_ROOT_URL"
    echo "ROOT                         $ROOT"
    echo "STORAGE_OC_DATA_ROOT         $STORAGE_OC_DATA_ROOT"
    echo "DATA_REPLICATION_ROOT        $DATA_REPLICATION_ROOT"
    echo "OCC                          $OCC"
    echo "EMAIL_SENDER                 $EMAIL_SENDER"
    echo "EMAIL_RECIPIENTS             $EMAIL_RECIPIENTS"
    echo "TRASH_DATA_ROOT              $TRASH_DATA_ROOT"
    echo "QUARANTINE_PERIOD            $QUARANTINE_PERIOD"
    echo "PROJECT_USER                 $PROJECT_USER"
    echo "PROJECT_STORAGE_OC_DATA_ROOT $PROJECT_STORAGE_OC_DATA_ROOT"
    echo "PROJECT_LOCK                 $PROJECT_LOCK"
    echo "PROJECT_TRASH_DATA_ROOT      $PROJECT_TRASH_DATA_ROOT"
    echo "PROJECT_REPLICATION_ROOT     $PROJECT_REPLICATION_ROOT"
    echo "PROJECT_USER_CREDENTIALS     $PROJECT_USER_CREDENTIALS"
    echo "ADMIN_CREDENTIALS            $ADMIN_CREDENTIALS"
    echo "LOG                          $LOG"
    echo "ERR                          $ERR"
    echo ""
fi

