#!/bin/bash
# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2020 Ministry of Education and Culture, Finland
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

INIT_FILE=`dirname "$(realpath $0)"`/lib/init_admin_script.sh

if [ -e $INIT_FILE ]
then
    . $INIT_FILE
else
    errorExit "The initialization file $INIT_FILE cannot be found"
fi

#--------------------------------------------------------------------------------
# Verify required variables are defined

if [ "$VENV_AUDIT" = "" ]; then
    errorExit "The variable VENV_AUDIT must be defined."
fi

if [ "$DBNAME" = "" ]; then
    errorExit "The variable DBNAME must be defined."
fi

if [ "$DBHOST" = "" ]; then
    errorExit "The variable DBHOST must be defined."
fi

if [ "$DBPORT" = "" ]; then
    errorExit "The variable DBPORT must be defined."
fi

if [ "$DBTABLEPREFIX" = "" ]; then
    errorExit "The variable DBTABLEPREFIX must be defined."
fi

if [ "$DBUSER" = "" ]; then
    errorExit "The variable DBUSER must be defined."
fi

if [ "$DBPASSWORD" = "" ]; then
    errorExit "The variable DBPASSWORD must be defined."
fi

#--------------------------------------------------------------------------------
# Verify python virtual environment has been configured

if [ ! -f "$VENV_AUDIT/bin/activate" ]; then
    errorExit "The python virtual environment $VENV_AUDIT not yet been configured"
fi

START="$TIMESTAMP"

if [ "$DEBUG" = "true" ]; then
    echo "--- $SCRIPT ---" >&2
    echo "START:         $START" >&2
fi
