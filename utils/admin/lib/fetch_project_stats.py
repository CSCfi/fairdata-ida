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
# This script will query the Nextcloud database and return for the specified
# project: 
# - the total quota allocated to the project, in bytes
# - the total number of files
# - the total volume of all files, in bytes
# - the total number of staged files
# - the total volume of all staged files, in bytes
# - the total number of frozen files
# - the total volume of frozen files, in bytes
# - the last time any project data was added/modified
# - the storage volume where the project data resides
# The first argument must be the ROOT of the IDA code base.
# The second argument must be the name of a project.
# The third argument is optional, and if equal to 'csv', the output will be tab
# delmited; otherwise, the output will be encoded as a JSON object
# --------------------------------------------------------------------------------

import importlib.util
import sys
import os
import time
import re
import logging
import psycopg2
from pathlib import Path
from datetime import datetime, timezone
from time import strftime
from utils import *

# Use UTC
os.environ["TZ"] = "UTC"
time.tzset()


def hr_to_bytes(value_string):

    value = float(re.sub('[^0-9\.]', '', value_string))
    unit = re.sub('[^a-zA-Z]', '', value_string).upper()

    # We only actually convert from B/KiB/MiB/GiB/TiB/PiB but accept both KB/MB/GB/TB/PB
    # and K/M/G/T/P as unit aliases per Nextcloud and common user (erroneous) practice

    total_bytes = 0

    if value < 0:
        value = 0

    if unit == "B":
        total_bytes = value

    elif unit in [ "KIB", "KB", "K" ]:
        total_bytes = value * 1024

    elif unit in [ "MIB", "MB", "M" ]:
        total_bytes = value * 1024 * 1024

    elif unit in [ "GIB", "GB", "G" ]:
        total_bytes = value * 1024 * 1024 * 1024

    elif unit in [ "TIB", "TB", "T" ]:
        total_bytes = value * 1024 * 1024 * 1024 * 1024

    elif unit in [ "PIB", "PB", "P" ]:
        total_bytes = value * 1024 * 1024 * 1024 * 1024 * 1024

    else:
        raise ValueError("Error: Unsupported unit: %s" % unit)

    return round(total_bytes)


def main():

    try:

        if len(sys.argv) < 3:
            raise Exception('Invalid number of arguments')
    
        # Load service configuration and constants, and add command arguments
        # and global values needed for auditing

        config = load_configuration("%s/config/config.sh" % sys.argv[1])
        constants = load_configuration("%s/lib/constants.sh" % sys.argv[1])

        config.STAGING_FOLDER_SUFFIX = constants.STAGING_FOLDER_SUFFIX
        config.PROJECT_USER_PREFIX = constants.PROJECT_USER_PREFIX
        config.SCRIPT = os.path.basename(sys.argv[0])
        config.PROJECT = sys.argv[2]

        if config.DEBUG:
            sys.stderr.write("--- %s ---\n" % config.SCRIPT)
            sys.stderr.write("ROOT:          %s\n" % config.ROOT)
            sys.stderr.write("DATA_ROOT:     %s\n" % config.STORAGE_OC_DATA_ROOT)
            sys.stderr.write("DBTYPE:        %s\n" % config.DBTYPE)
            sys.stderr.write("DBHOST:        %s\n" % config.DBHOST)
            sys.stderr.write("DBROUSER:      %s\n" % config.DBROUSER)
            sys.stderr.write("DBNAME:        %s\n" % config.DBNAME)
            sys.stderr.write("ARGS#:         %d\n" % len(sys.argv))
            sys.stderr.write("ARGS:          %s\n" % str(sys.argv))
            sys.stderr.write("PROJECT:       %s\n" % config.PROJECT)
    
        # Open database connection 

        dblib = psycopg2

        conn = dblib.connect(database=config.DBNAME,
                             user=config.DBROUSER,
                             password=config.DBROPASSWORD,
                             host=config.DBHOST,
                             port=config.DBPORT)

        cur = conn.cursor()

        # Retrieve total storage quota allocated to project

        query = "SELECT configvalue FROM %spreferences \
                 WHERE userid = '%s%s' AND configkey = 'quota' \
                 LIMIT 1" % (config.DBTABLEPREFIX, config.PROJECT_USER_PREFIX, config.PROJECT)

        if config.DEBUG:
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        if len(rows) != 1:
            raise Exception("Failed to retrieve quota for project %s" % config.PROJECT)

        quota = rows[0][0]

        if config.DEBUG:
            sys.stderr.write("QUOTA: %s\n" % quota)

        # Note: Quotas are defined in gibibytes though Nextcloud uses the incorrect unit designator 'GB'

        quota_bytes = int(hr_to_bytes(quota))

        if config.DEBUG:
            sys.stderr.write("QUOTA: %d\n" % quota_bytes)

        # Retrieve PSO storage id for project

        query = "SELECT numeric_id FROM %sstorages \
                 WHERE id = 'home::%s%s' \
                 LIMIT 1" % (config.DBTABLEPREFIX, config.PROJECT_USER_PREFIX, config.PROJECT)

        if config.DEBUG:
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        if len(rows) != 1:
            raise Exception("Failed to retrieve storage id for project %s" % config.PROJECT)

        storage_id = rows[0][0]

        if config.DEBUG:
            sys.stderr.write("STORAGE_ID:    %d\n" % (storage_id))

        # Calculate total number of records for all files in frozen area

        query = "SELECT COUNT(*) FROM %sfilecache \
                 WHERE storage = %d \
                 AND mimetype != 2 \
                 AND path LIKE 'files/%s/%%' " % (config.DBTABLEPREFIX, storage_id, config.PROJECT)

        if config.DEBUG:
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        frozen_files = rows[0][0]

        if frozen_files == None:
            frozen_files = 0

        # Calculate total bytes of all files in frozen area

        query = "SELECT SUM(size) FROM %sfilecache \
                 WHERE storage = %d \
                 AND mimetype != 2 \
                 AND path LIKE 'files/%s/%%' " % (config.DBTABLEPREFIX, storage_id, config.PROJECT)

        if config.DEBUG:
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        frozen_bytes = rows[0][0]

        if frozen_bytes == None:
            frozen_bytes = 0

        # Calculate total number of records for all files in staging area

        query = "SELECT COUNT(*) FROM %sfilecache \
                 WHERE storage = %d \
                 AND mimetype != 2 \
                 AND path LIKE 'files/%s+/%%' " % (config.DBTABLEPREFIX, storage_id, config.PROJECT)

        if config.DEBUG:
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        staged_files = rows[0][0]

        if staged_files == None:
            staged_files = 0

        # Calculate total bytes of all files in staging area

        query = "SELECT SUM(size) FROM %sfilecache \
                 WHERE storage = %d \
                 AND mimetype != 2 \
                 AND path LIKE 'files/%s+/%%' " % (config.DBTABLEPREFIX, storage_id, config.PROJECT)

        if config.DEBUG:
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        staged_bytes = rows[0][0]

        if staged_bytes == None:
            staged_bytes = 0

        # Select last modified timestamp of any node

        query = "SELECT MAX(mtime) FROM %sfilecache \
                 WHERE storage = %d" % (config.DBTABLEPREFIX, storage_id)

        if config.DEBUG:
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        last_active = datetime.utcfromtimestamp(rows[0][0]).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Retrieve glusterfs volume where project data resides

        storage_volume = Path("%s/%s%s" % (config.STORAGE_OC_DATA_ROOT, config.PROJECT_USER_PREFIX, config.PROJECT)).resolve().parent.parent

        # Close database connection

        conn.close()

        # Return project stats

        if len(sys.argv) > 3 and sys.argv[3] == "csv":
            sys.stdout.write("PROJECT\t")
            sys.stdout.write("QUOTA_BYTES\t")
            sys.stdout.write("TOTAL_FILES\t")
            sys.stdout.write("TOTAL_BYTES\t")
            sys.stdout.write("STAGED_FILES\t")
            sys.stdout.write("STAGED_BYTES\t")
            sys.stdout.write("FROZEN_FILES\t")
            sys.stdout.write("FROZEN_BYTES\t")
            sys.stdout.write("LAST_MODIFIED\t")
            sys.stdout.write("STORAGE_VOLUME\n")
            sys.stdout.write("%s\t" % config.PROJECT)
            sys.stdout.write("%d\t" % quota_bytes)
            sys.stdout.write("%d\t" % (staged_files + frozen_files))
            sys.stdout.write("%d\t" % (staged_bytes + frozen_bytes))
            sys.stdout.write("%d\t" % staged_files)
            sys.stdout.write("%d\t" % staged_bytes)
            sys.stdout.write("%d\t" % frozen_files)
            sys.stdout.write("%d\t" % frozen_bytes)
            sys.stdout.write("%s\t" % last_active)
            sys.stdout.write("%s\n" % storage_volume)
        else:
            sys.stdout.write("{\n")
            sys.stdout.write("  \"project\": \"%s\",\n" % config.PROJECT)
            sys.stdout.write("  \"quotaBytes\": %d,\n" % quota_bytes)
            sys.stdout.write("  \"totalFiles\": %d,\n" % (staged_files + frozen_files))
            sys.stdout.write("  \"totalBytes\": %d,\n" % (staged_bytes + frozen_bytes))
            sys.stdout.write("  \"stagedFiles\": %d,\n" % staged_files)
            sys.stdout.write("  \"stagedBytes\": %d,\n" % staged_bytes)
            sys.stdout.write("  \"frozenFiles\": %d,\n" % frozen_files)
            sys.stdout.write("  \"frozenBytes\": %d,\n" % frozen_bytes)
            sys.stdout.write("  \"lastActive\": \"%s\",\n" % last_active)
            sys.stdout.write("  \"storageVolume\": \"%s\"\n" % storage_volume)
            sys.stdout.write("}\n")

    except Exception as error:
        try:
            logging.error(str(error))
        except Exception as logerror:
            sys.stderr.write("ERROR: %s\n" % str(logerror))
        sys.stderr.write("ERROR: %s\n" % str(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
