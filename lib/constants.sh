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
# Service constants
DISALLOWED_NAMES="ADMIN SYSTEM"      # whitespace separated list of names in uppercase
STAGING_FOLDER_SUFFIX="+"            # appended to project name to construct staging share folder name
PROJECT_USER_PREFIX="PSO_"           # "PSO" = "Project Share Owner"
USER_QUOTA=0                         # Normal users require no storage allocation
MAX_FILE_COUNT=5000                  # Maximum number of files allowed for a single action
IDA_MIGRATION="2018-11-01T00:00:00Z" # When legacy data migration from old iRODS IDA completed
IDA_MIGRATION_TS=1541030400          # When legacy data migration from old iRODS IDA completed, in epoch seconds
