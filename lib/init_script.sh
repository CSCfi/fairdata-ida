#!/bin/bash
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
# load service constants and configuration settings

PARENT_FOLDER=`dirname "$(realpath $0)"`
PARENT_BASENAME=`basename "$PARENT_FOLDER"`

while [ "$PARENT_BASENAME" != "ida" -a "$PARENT_BASENAME" != "" ]; do
    PARENT_FOLDER=`dirname "$PARENT_FOLDER"`
    PARENT_BASENAME=`basename "$PARENT_FOLDER"`
done

CONSTANTS_FILE="$PARENT_FOLDER/lib/constants.sh"

if [ -e $CONSTANTS_FILE ]
then
    . $CONSTANTS_FILE
else
    echo "The service constants file $CONSTANTS_FILE cannot be found. Aborting." >&2
    exit 1
fi

CONFIG_FILE="$PARENT_FOLDER/config/config.sh"

if [ -e $CONFIG_FILE ]
then
    . $CONFIG_FILE
else
    echo "The configuration file $CONFIG_FILE cannot be found. Aborting." >&2
    exit 1
fi

#--------------------------------------------------------------------------------
# Ensure script is run as apache

ID=`id -u -n`
if [ "$ID" != "$HTTPD_USER" ]; then
    echo "You need to be $HTTPD_USER"
    exit 1
fi

#--------------------------------------------------------------------------------
# Common initialization for all scripts

CURL_POST='curl -k --raw -s -S -X POST -u'
CURL_GET='curl -k --raw -s -S -u'
CURL_DELETE='curl -k --raw -s -S -X DELETE -u'
CURL_MKCOL='curl -k --raw -s -S -X MKCOL -u'

TIMESTAMP=`date -u +"%Y-%m-%dT%H:%M:%SZ"`

if [ "$SCRIPT" == "" ]; then
    SCRIPT=`basename $0`
else
    SCRIPT=`basename $SCRIPT`
fi

#--------------------------------------------------------------------------------
# Verify needed utilities are available

for NEEDS_PROG in curl php python ascii2uni
do
    PROG_LOCATION=`/usr/bin/which $NEEDS_PROG 2>/dev/null`
    if [ ! -e "$PROG_LOCATION" ]; then
        echo "Can't find $NEEDS_PROG in your \$PATH"
        exit 1
    fi
done

#--------------------------------------------------------------------------------
# Initialize log and tmp folders, if necessary...

LOGS=`dirname "$LOG"`

if [ ! -d $LOGS ]; then
    mkdir -p $LOGS 2>/dev/null
fi

if [ ! -d $LOGS ]; then
    echo "Error: Can't initialize log folder: \"$LOGS\"" >&2
    exit 1
fi

if [ ! -d $TMPDIR ]; then
    mkdir -p $TMPDIR 2>/dev/null
fi

if [ ! -d $TMPDIR ]; then
    echo "Error: Can't initialize temporary folder: \"$TMPDIR\"" >&2
    exit 1
fi

#--------------------------------------------------------------------------------
# Initialize log file and record start of script execution

if [ ! -e $LOG ]; then
    OUT=`touch $LOG`
    if [ "$?" -ne 0 ]; then
        echo "Can't create log file \"$LOG\"" >&2
        exit 1
    fi
    OUT=`chown $HTTPD_USER:$HTTPD_USER $LOG`
    if [ "$?" -ne 0 ]; then
        echo "Can't set ownership of log file \"$LOG\"" >&2
        exit 1
    fi
fi

OUT=`echo "$TIMESTAMP $SCRIPT START $@" 2>/dev/null >>"$LOG"`
if [ "$?" -ne 0 ]; then
    echo "Can't write to log file \"$LOG\"" >&2
    exit 1
fi

#--------------------------------------------------------------------------------
# Common functions for all scripts

function addToLog {
    MSG=`echo "$@" | tr '\n' ' '`
    echo "$TIMESTAMP $SCRIPT $MSG" 2>/dev/null >>"$LOG"
}

function echoAndLog {
    MSG=`echo "$@" | tr '\n' ' '`
    echo "$MSG"
    echo "$TIMESTAMP $SCRIPT $MSG" 2>/dev/null >>"$LOG"
}

function errorExit {
    MSG=`echo "$@" | tr '\n' ' '`
    echo "$MSG" >&2
    echo "$TIMESTAMP $SCRIPT ERROR $MSG" >>"$LOG"
    exit 1
}

# TODO Include all project users as recipients

function sendEmail {
    SUBJECT=`echo "$1" | tr '\n' ' '`
    MESSAGE="$2"
    if [ "$EMAIL_SENDER" != "" ]; then
        if [ "$EMAIL_RECIPIENTS" = "" ]; then
            EMAIL_RECIPIENTS="$EMAIL_SENDER"
        fi
        mail -s "$SUBJECT" -r $EMAIL_SENDER $EMAIL_RECIPIENTS <<EOF

$MESSAGE

EOF
    fi
}

