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

INIT_FILE=`dirname "$(realpath $0)"`/../../lib/init_script.sh

if [ -e $INIT_FILE ]
then
    . $INIT_FILE
else
    errorExit "The initialization file $INIT_FILE cannot be found"
fi

#--------------------------------------------------------------------------------
# Process input and get project name, per default admin script behavior

if [ "$SCRIPT" = "" ]; then
    SCRIPT=`basename "$(realpath $0)"`
fi

if [ "$USAGE" = "" ]; then
    USAGE="
Usage: $SCRIPT project
       $SCRIPT -h
"
fi

if [ "$1" = "-h" ]; then
    echo "$USAGE" >&2
    addToLog "DONE"
    exit
fi

if [ "$PROJECT" = "" ]; then
    PROJECT=`echo "$1" | sed -e 's/ *//g' `
fi

if [ "$PROJECT" = "" ]; then
    echo "$USAGE" >&2
    errorExit "Required project name missing"
fi

#--------------------------------------------------------------------------------
# For admin scripts, we want API requests to be directed to localhost, not via
# the load balancer, which may not be avaialable during maintenance breaks.

if [ "$IDA_ENVIRONMENT" = "PRODUCTION" ]; then
    IDA_API_ROOT_URL="https://localhost/apps/ida/api"
fi

#--------------------------------------------------------------------------------
# Verify required variables are defined

if [ "$NC_ADMIN_USER" = "" ]; then
    errorExit "The variable NC_ADMIN_USER must be defined"
fi

if [ "$NC_ADMIN_PASS" = "" ]; then
    errorExit "The variable NC_ADMIN_PASS must be defined"
fi

if [ "$METAX_API_USER" = "" ]; then
    errorExit "The variable METAX_API_USER must be defined"
fi

if [ "$METAX_API_PASS" = "" ]; then
    errorExit "The variable METAX_API_PASS must be defined"
fi

if [ "$HTTPD_USER" = "" ]; then
    errorExit "The variable HTTPD_USER must be defined"
fi

if [ "$PROJECT_USER_PASS" = "" ]; then
    errorExit "The variable PROJECT_USER_PASS must be defined"
fi

if [ "$PROJECT_USER_PREFIX" = "" ]; then
    errorExit "The variable PROJECT_USER_PREFIX must be defined"
fi

if [ "$STAGING_FOLDER_SUFFIX" = "" ]; then
    errorExit "The variable PROJECT_USER_PREFIX must be defined"
fi

if [ "$METAX_API_ROOT_URL" = "" ]; then
    errorExit "The variable METAX_API_ROOT_URL must be defined"
fi

if [ "$IDA_API_ROOT_URL" = "" ]; then
    errorExit "The variable IDA_API_ROOT_URL must be defined"
fi

if [ "$ROOT" = "" ]; then
    errorExit "The variable ROOT must be defined"
fi

if [ "$STORAGE_OC_DATA_ROOT" = "" ]; then
    errorExit "The variable STORAGE_OC_DATA_ROOT must be defined"
fi

if [ "$DATA_REPLICATION_ROOT" = "" ]; then
    errorExit "The variable DATA_REPLICATION_ROOT must be defined"
fi

if [ "$OCC" = "" ]; then
    errorExit "The variable OCC must be defined"
fi

if [ "$LOG" = "" ]; then
    errorExit "The variable LOG must be defined"
fi

if [ "$TRASH_DATA_ROOT" = "" ]; then
    errorExit "The variable TRASH_DATA_ROOT must be defined"
fi

if [ "$QUARANTINE_PERIOD" = "" ]; then
    errorExit "The variable QUARANTINE_PERIOD must be defined"
fi

if [ "$TIMESTAMP" = "" ]; then
    errorExit "The variable TIMESTAMP must be defined"
fi

PROJECT_USER="${PROJECT_USER_PREFIX}${PROJECT}"
PROJECT_ROOT="${STORAGE_OC_DATA_ROOT}/${PROJECT_USER}"
PROJECT_STORAGE_OC_DATA_ROOT="${PROJECT_ROOT}/files"
PROJECT_LOCK="${PROJECT_STORAGE_OC_DATA_ROOT}/LOCK"
PROJECT_REPLICATION_ROOT="${DATA_REPLICATION_ROOT}/projects/${PROJECT}"
PROJECT_TRASH_DATA_ROOT="${TRASH_DATA_ROOT}/${TIMESTAMP}_${PROJECT}"
PROJECT_USER_CREDENTIALS="${PROJECT_USER}:${PROJECT_USER_PASS}"
ADMIN_CREDENTIALS="${NC_ADMIN_USER}:${NC_ADMIN_PASS}"
METAX_CREDENTIALS="${METAX_API_USER}:${METAX_API_PASS}"

ERR="/tmp/${SCRIPT}.$$.err"

if [ "$FORCE_HTTP" = "true" ]; then
    REQUEST_URL_ROOT="http://${ADMIN_CREDENTIALS}@localhost"
else
    REQUEST_URL_ROOT="https://${ADMIN_CREDENTIALS}@localhost"
fi

if [ "$DEBUG" = "true" ]; then
    echo "" >&2
    echo "NC_ADMIN_USER                $NC_ADMIN_USER" >&2
    echo "NC_ADMIN_PASS                $NC_ADMIN_PASS" >&2
    echo "METAX_API_USER               $METAX_API_USER" >&2
    echo "METAX_API_PASS               $METAX_API_PASS" >&2
    echo "HTTPD_USER                   $HTTPD_USER" >&2
    echo "PROJECT_USER_PASS            $PROJECT_USER_PASS" >&2
    echo "PROJECT_USER_PREFIX          $PROJECT_USER_PREFIX" >&2
    echo "BATCH_ACTION_TOKEN           $BATCH_ACTION_TOKEN" >&2
    echo "IDA_API_ROOT_URL             $IDA_API_ROOT_URL" >&2
    echo "METAX_API_ROOT_URL           $METAX_API_ROOT_URL" >&2
    echo "ROOT                         $ROOT" >&2
    echo "STORAGE_OC_DATA_ROOT         $STORAGE_OC_DATA_ROOT" >&2
    echo "DATA_REPLICATION_ROOT        $DATA_REPLICATION_ROOT" >&2
    echo "OCC                          $OCC" >&2
    echo "EMAIL_SENDER                 $EMAIL_SENDER" >&2
    echo "EMAIL_RECIPIENTS             $EMAIL_RECIPIENTS" >&2
    echo "TRASH_DATA_ROOT              $TRASH_DATA_ROOT" >&2
    echo "QUARANTINE_PERIOD            $QUARANTINE_PERIOD" >&2
    echo "PROJECT_USER                 $PROJECT_USER" >&2
    echo "PROJECT_STORAGE_OC_DATA_ROOT $PROJECT_STORAGE_OC_DATA_ROOT" >&2
    echo "PROJECT_LOCK                 $PROJECT_LOCK" >&2
    echo "PROJECT_TRASH_DATA_ROOT      $PROJECT_TRASH_DATA_ROOT" >&2
    echo "PROJECT_REPLICATION_ROOT     $PROJECT_REPLICATION_ROOT" >&2
    echo "PROJECT_USER_CREDENTIALS     $PROJECT_USER_CREDENTIALS" >&2
    echo "ADMIN_CREDENTIALS            $ADMIN_CREDENTIALS" >&2
    echo "LOG                          $LOG" >&2
    echo "ERR                          $ERR" >&2
    echo "REQUEST_URL_ROOT             $REQUEST_URL_ROOT" >&2
    echo "" >&2
fi

function bytesToHR()
{
    local SIZE=$1
    local UNITS="B KB MB GB TB PB"
    for F in $UNITS; do
        local UNIT=$F
        test ${SIZE%.*} -lt 1024 && break;
        SIZE=$(echo "$SIZE / 1024" | bc -l)
    done
  
    if [ "$UNIT" == "B" ]; then
        printf "%4.0f %s\n" $SIZE $UNIT
    else
        printf "%7.02f %s\n" $SIZE $UNIT
    fi
}
