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
# Verify needed utilities are available

PATH="/opt/fairdata/python3/bin:$PATH"

for NEEDS_PROG in curl php python3 realpath
do
    PROG_LOCATION=`/usr/bin/which $NEEDS_PROG 2>/dev/null`
    if [ ! -e "$PROG_LOCATION" ]; then
        echo "Can't find $NEEDS_PROG in your \$PATH"
        exit 1
    fi
done

#--------------------------------------------------------------------------------
# Load service constants and configuration settings

SCRIPT_PATHNAME="$(realpath $0)"
PARENT_FOLDER=`dirname "$SCRIPT_PATHNAME"`
PARENT_BASENAME=`basename "$PARENT_FOLDER"`

if [ "$SCRIPT" == "" ]; then
    SCRIPT=`basename $SCRIPT_PATHNAME`
else
    SCRIPT=`basename $SCRIPT`
fi

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
    echo "You must execute this script as $HTTPD_USER"
    exit 1
fi

#--------------------------------------------------------------------------------
# Common initialization for all scripts

CURL_POST='curl --fail -k -s -S -X POST -u'
CURL_GET='curl --fail -k -s -S -u'
CURL_DELETE='curl --fail -k -s -S -X DELETE -u'
CURL_MKCOL='curl --fail -k -s -S -X MKCOL -u'

TIMESTAMP=`date -u +"%Y-%m-%dT%H:%M:%SZ"`
PROCESSID="$$"

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

if [ "$TMPDIR" = "" ]; then
    TMPDIR=/tmp
fi

if [ ! -d "$TMPDIR" ]; then
    mkdir -p $TMPDIR
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

OUT=`echo "$TIMESTAMP $SCRIPT ($PROCESSID) START $@" 2>/dev/null >>"$LOG"`
if [ "$?" -ne 0 ]; then
    echo "Can't write to log file \"$LOG\"" >&2
    exit 1
fi

#--------------------------------------------------------------------------------
# Common functions for all scripts

function urlEncode () {
    # Escape all special characters, for use in curl URLs
    local RESULT=`echo "${1}" | \
                      sed -e  's:\%:%25:g' \
                          -e  's: :%20:g' \
                          -e  's:\\+:%2b:g' \
                          -e  's:<:%3c:g' \
                          -e  's:>:%3e:g' \
                          -e  's:\#:%23:g' \
                          -e  's:{:%7b:g' \
                          -e  's:}:%7d:g' \
                          -e  's:|:%7c:g' \
                          -e  's:\\\\:%5c:g' \
                          -e  's:\\^:%5e:g' \
                          -e  's:~:%7e:g' \
                          -e  's:\\[:%5b:g' \
                          -e  's:\\]:%5d:g' \
                          -e $'s:\':%27:g' \
                          -e  's:\`:%60:g' \
                          -e  's:;:%3b:g' \
                          -e  's:\\?:%3f:g' \
                          -e  's/:/%3a/g' \
                          -e  's:@:%40:g' \
                          -e  's:=:%3d:g' \
                          -e  's:\\&:%26:g' \
                          -e  's:\\$:%24:g' \
                          -e  's:\\!:%21:g' \
                          -e  's:\\*:%2a:g'`

    echo "${RESULT}"
}

function addToLog {
    MSG=`echo "$@" | tr '\n' ' '`
    TIMESTAMP=`date -u +"%Y-%m-%dT%H:%M:%SZ"`
    echo "$TIMESTAMP $SCRIPT ($PROCESSID) $MSG" 2>/dev/null >>"$LOG"
}

function echoAndLog {
    MSG=`echo "$@" | tr '\n' ' '`
    echo "$MSG"
    TIMESTAMP=`date -u +"%Y-%m-%dT%H:%M:%SZ"`
    echo "$TIMESTAMP $SCRIPT ($PROCESSID) $MSG" 2>/dev/null >>"$LOG"
}

function errorExit {
    MSG=`echo "$@" | tr '\n' ' '`
    echo "$MSG" >&2
    TIMESTAMP=`date -u +"%Y-%m-%dT%H:%M:%SZ"`
    echo "$TIMESTAMP $SCRIPT ($PROCESSID) FATAL ERROR $MSG" >>"$LOG"
    exit 1
}

function sendEmail {

    # We report any argument count error here, but do not halt execution, leaving it
    # up to the calling script to detect the error and deal with it accordingly.

    if [ "$#" -lt 2 ]; then
        echo "Error: Insufficient number of arguments provided to sendEmail function!" >&2
        return
    fi

    SUBJECT=`echo "$1" | tr '\n' ' '`
    SUBJECT="[IDA Service] ${SUBJECT}"
    MESSAGE="$2"
    RECIPIENTS="$3"

    # If there is no email sender configured in the environment, we do nothing,
    # essentially ignoring the function request.

    if [ "$EMAIL_SENDER" != "" ]; then

        # If no explicit recipients are specified, then the message will only be sent
        # to the default recipients. I.e. it is simply an internal admin email; else
        # the default recipients will be treated as BCC recipients.

        if [ "$RECIPIENTS" = "" ]; then

            # If no default recipients are defined, report an error and do nothing.

            if [ "$EMAIL_RECIPIENTS" = "" ]; then
                echo "Error: No recipients specified either in function arguments or configuration!" >&2
                return
            fi

            RECIPIENTS="$EMAIL_RECIPIENTS"

        else

            # If default recipients defined in configuration and explicit recipients
            # specified, add default recipients as BCC

            if [ "$EMAIL_RECIPIENTS" != "" ]; then
                RECIPIENTS="-b $EMAIL_RECIPIENTS $RECIPIENTS"
            fi

        fi

        mail -s "$SUBJECT" -r $EMAIL_SENDER -S "replyto=$EMAIL_SENDER" $RECIPIENTS <<EOF

$MESSAGE

EOF
    fi
}
