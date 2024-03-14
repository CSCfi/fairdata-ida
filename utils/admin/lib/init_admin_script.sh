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

# Verify needed utilities are available

for NEEDS_PROG in jq column
do
    PROG_LOCATION=`/usr/bin/which $NEEDS_PROG 2>/dev/null`
    if [ ! -e "$PROG_LOCATION" ]; then
        errorExit "Can't find $NEEDS_PROG in your \$PATH. Aborting."
    fi
done

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
# Verify required variables are defined

if [ "$NC_ADMIN_USER" = "" ]; then
    errorExit "The variable NC_ADMIN_USER must be defined"
fi

if [ "$NC_ADMIN_PASS" = "" ]; then
    errorExit "The variable NC_ADMIN_PASS must be defined"
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

if [ "$METAX_API" = "" ]; then
    errorExit "The variable METAX_API must be defined"
fi

if [ "$METAX_API_VERSION" = "" ]; then
    errorExit "The variable METAX_API_VERSION must be defined"
fi

if [ $METAX_API_VERSION -lt 3 ]; then
    if [ "$METAX_USER" = "" ]; then
        errorExit "The variable METAX_USER must be defined"
    fi
fi

if [ "$METAX_PASS" = "" ]; then
    errorExit "The variable METAX_PASS must be defined"
fi

if [ "$IDA_API" = "" ]; then
    errorExit "The variable IDA_API must be defined"
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

if [ "$START" = "" ]; then
    errorExit "The variable START must be defined"
fi

if [ "$IDA_MODE_HEADER" = "" ]; then
    errorExit "The IDA_MODE_HEADER variable must be defined"
fi

PROJECT_USER="${PROJECT_USER_PREFIX}${PROJECT}"
PROJECT_ROOT="${STORAGE_OC_DATA_ROOT}/${PROJECT_USER}"
PROJECT_STORAGE_OC_DATA_ROOT="${PROJECT_ROOT}/files"
PROJECT_LOCK="${PROJECT_STORAGE_OC_DATA_ROOT}/LOCK"
PROJECT_SUSPENDED="${PROJECT_STORAGE_OC_DATA_ROOT}/SUSPENDED"
PROJECT_REPLICATION_ROOT="${DATA_REPLICATION_ROOT}/projects/${PROJECT}"
PROJECT_TRASH_DATA_ROOT="${TRASH_DATA_ROOT}/${START}_${PROJECT}"
PROJECT_USER_CREDENTIALS="-u ${PROJECT_USER}:${PROJECT_USER_PASS}"
ADMIN_CREDENTIALS="-u ${NC_ADMIN_USER}:${NC_ADMIN_PASS}"

if [ $METAX_API_VERSION -ge 3 ]; then
    METAX_AUTH_HEADER="Authorization: Token ${METAX_PASS}"
else
    METAX_CREDENTIALS="-u ${METAX_USER}:${METAX_PASS}"
fi

HOSTNAME=`hostname`

#--------------------------------------------------------------------------------

ERR="/tmp/ida_${SCRIPT}_$$.err"

cleanup() {
    rm -f $ERR 2>/dev/null
}

trap cleanup EXIT

#--------------------------------------------------------------------------------

if [ "$DEBUG" = "true" ]; then
    echo ""
    echo "HOSTNAME                     $HOSTNAME"
    echo "ROOT                         $ROOT"
    echo "STORAGE_OC_DATA_ROOT         $STORAGE_OC_DATA_ROOT"
    echo "DATA_REPLICATION_ROOT        $DATA_REPLICATION_ROOT"
    echo "PROJECT_REPLICATION_ROOT     $PROJECT_REPLICATION_ROOT"
    echo "PROJECT_TRASH_DATA_ROOT      $PROJECT_TRASH_DATA_ROOT"
    echo "IDA_API                      $IDA_API"
    echo "METAX_API                    $METAX_API"
    echo "METAX_API_VERSION            $METAX_API_VERSION"
    echo "HTTPD_USER                   $HTTPD_USER"
    echo "NC_ADMIN_USER                $NC_ADMIN_USER"
    echo "NC_ADMIN_PASS                $NC_ADMIN_PASS"
    echo "METAX_USER                   $METAX_USER"
    echo "METAX_PASS                   $METAX_PASS"
    echo "BATCH_ACTION_TOKEN           $BATCH_ACTION_TOKEN"
    echo "OCC                          $OCC"
    echo "EMAIL_SENDER                 $EMAIL_SENDER"
    echo "EMAIL_RECIPIENTS             $EMAIL_RECIPIENTS"
    echo "TRASH_DATA_ROOT              $TRASH_DATA_ROOT"
    echo "QUARANTINE_PERIOD            $QUARANTINE_PERIOD"
    echo "PROJECT_USER_PREFIX          $PROJECT_USER_PREFIX"
    echo "PROJECT_USER_PASS            $PROJECT_USER_PASS"
    echo "PROJECT_USER                 $PROJECT_USER"
    echo "PROJECT_STORAGE_OC_DATA_ROOT $PROJECT_STORAGE_OC_DATA_ROOT"
    echo "PROJECT_LOCK                 $PROJECT_LOCK"
    echo "PROJECT_SUSPENDED            $PROJECT_SUSPENDED"
    echo "PROJECT_USER_CREDENTIALS     $PROJECT_USER_CREDENTIALS"
    echo "ADMIN_CREDENTIALS            $ADMIN_CREDENTIALS"
    echo "LOG                          $LOG"
    echo "ERR                          $ERR"
    echo ""
fi

function bytesToHR()
{
    local SIZE=`printf "%.f" "$1"`
    local UNITS="B KiB MiB GiB TiB PiB"
    local UNIT="B"

    if [ ${SIZE%.*} -le 0 ]; then

        SIZE=0
        UNIT="B"

    else
    
        for U in $UNITS; do
            UNIT=$U
            test ${SIZE%.*} -lt 1024 && break;
            SIZE=$(echo "$SIZE / 1024" | bc -l)
        done
    
        SIZE=$(echo "$SIZE + 0.5" | bc -l | sed -e 's/\.[0-9][0-9]*$//')

    fi

    printf "%u %s" $SIZE $UNIT
}

function hrToBytes()
{
    local SIZE="$1"
    local UNIT="$2"

    if [ "$UNIT" = "" ]; then
        SIZE=`echo "$1" | sed -e 's/[^0-9\.]//g'`
        UNIT=`echo "$1" | sed -e 's/[^a-zA-Z]//g'`
    fi

    SIZE=`printf "%f" "$SIZE"`
    UNIT=`echo "$UNIT" | tr '[a-z]' '[A-Z]'`

    if [ "$SIZE" = "" ]; then
        SIZE=0
    fi

    if [ ${SIZE%.*} -lt 0 ]; then
        SIZE=0
    fi

    # We only actually convert from B/KiB/MiB/GiB/TiB/PiB but accept both KB/MB/GB/TB/PB
    # and K/M/G/T/P as unit aliases per Nextcloud and common user (erroneous) practice

    case $UNIT in

      "B")
        ;;

      "KIB" | "KB" | "K")
        SIZE=$(echo "$SIZE * 1024" | bc -l)
        ;;

      "MIB" | "MB" | "M")
        SIZE=$(echo "$SIZE * 1024 * 1024" | bc -l)
        ;;

      "GIB" | "GB" | "G")
        SIZE=$(echo "$SIZE * 1024 * 1024 * 1024" | bc -l)
        ;;

      "TIB" | "TB" | "T")
        SIZE=$(echo "$SIZE * 1024 * 1024 * 1024 * 1024" | bc -l)
        ;;

      "PIB" | "PB" | "P")
        SIZE=$(echo "$SIZE * 1024 * 1024 * 1024 * 1024 * 1024" | bc -l)
        ;;

      *)
        echo "Error: Unsupported unit $UNIT" >&2
        exit 1
        ;;
    esac

    SIZE=$(echo "$SIZE + 0.5" | bc -l | sed -e 's/\.[0-9][0-9]*$//')

    printf "%u" $SIZE
}
