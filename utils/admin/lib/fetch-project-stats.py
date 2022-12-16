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
import re
import logging
import psycopg2
from pathlib import Path
from datetime import datetime, timezone
from time import strftime

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

        #config.DEBUG = 'true' # TEMP HACK

        if config.DEBUG == 'true':
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

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        if len(rows) != 1:
            raise Exception("Failed to retrieve quota for project %s" % config.PROJECT)

        quota = rows[0][0]

        if quota.endswith("GB") == False:
            raise Exception("Quota defined in unsupported unit format: \"%s\"" % quota)

        # Note: Quotas are defined in gigabytes not gibibytes

        quotaBytes = int(re.sub("[^0-9]", "", quota)) * 1000000000

        if config.DEBUG == 'true':
            sys.stderr.write("QUOTA:         %d\n" % (quotaBytes))

        # Retrieve PSO storage id for project

        query = "SELECT numeric_id FROM %sstorages \
                 WHERE id = 'home::%s%s' \
                 LIMIT 1" % (config.DBTABLEPREFIX, config.PROJECT_USER_PREFIX, config.PROJECT)

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        if len(rows) != 1:
            raise Exception("Failed to retrieve storage id for project %s" % config.PROJECT)

        storage_id = rows[0][0]

        if config.DEBUG == 'true':
            sys.stderr.write("STORAGE_ID:    %d\n" % (storage_id))

        # Calculate total number of records for all files in frozen area

        query = "SELECT COUNT(*) FROM %sfilecache \
                 WHERE storage = %d \
                 AND mimetype != 2 \
                 AND path LIKE 'files/%s/%%' " % (config.DBTABLEPREFIX, storage_id, config.PROJECT)

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        frozenFiles = rows[0][0]

        if frozenFiles == None:
            frozenFiles = 0

        # Calculate total bytes of all files in frozen area

        query = "SELECT SUM(size) FROM %sfilecache \
                 WHERE storage = %d \
                 AND mimetype != 2 \
                 AND path LIKE 'files/%s/%%' " % (config.DBTABLEPREFIX, storage_id, config.PROJECT)

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        frozenBytes = rows[0][0]

        if frozenBytes == None:
            frozenBytes = 0

        # Calculate total number of records for all files in staging area

        query = "SELECT COUNT(*) FROM %sfilecache \
                 WHERE storage = %d \
                 AND mimetype != 2 \
                 AND path LIKE 'files/%s+/%%' " % (config.DBTABLEPREFIX, storage_id, config.PROJECT)

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        stagedFiles = rows[0][0]

        if stagedFiles == None:
            stagedFiles = 0

        # Calculate total bytes of all files in staging area

        query = "SELECT SUM(size) FROM %sfilecache \
                 WHERE storage = %d \
                 AND mimetype != 2 \
                 AND path LIKE 'files/%s+/%%' " % (config.DBTABLEPREFIX, storage_id, config.PROJECT)

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        stagedBytes = rows[0][0]

        if stagedBytes == None:
            stagedBytes = 0

        # Select last modified timestamp of any node

        query = "SELECT MAX(mtime) FROM %sfilecache \
                 WHERE storage = %d" % (config.DBTABLEPREFIX, storage_id)

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        lastActive = datetime.utcfromtimestamp(rows[0][0]).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Retrieve glusterfs volume where project data resides

        storageVolume = Path("%s/%s%s" % (config.STORAGE_OC_DATA_ROOT, config.PROJECT_USER_PREFIX, config.PROJECT)).resolve().parent.parent

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
            sys.stdout.write("%d\t" % quotaBytes)
            sys.stdout.write("%d\t" % (stagedFiles + frozenFiles))
            sys.stdout.write("%d\t" % (stagedBytes + frozenBytes))
            sys.stdout.write("%d\t" % stagedFiles)
            sys.stdout.write("%d\t" % stagedBytes)
            sys.stdout.write("%d\t" % frozenFiles)
            sys.stdout.write("%d\t" % frozenBytes)
            sys.stdout.write("%s\t" % lastActive)
            sys.stdout.write("%s\n" % storageVolume)
        else:
            sys.stdout.write("{\n")
            sys.stdout.write("  \"project\": \"%s\",\n" % config.PROJECT)
            sys.stdout.write("  \"quotaBytes\": %d,\n" % quotaBytes)
            sys.stdout.write("  \"totalFiles\": %d,\n" % (stagedFiles + frozenFiles))
            sys.stdout.write("  \"totalBytes\": %d,\n" % (stagedBytes + frozenBytes))
            sys.stdout.write("  \"stagedFiles\": %d,\n" % stagedFiles)
            sys.stdout.write("  \"stagedBytes\": %d,\n" % stagedBytes)
            sys.stdout.write("  \"frozenFiles\": %d,\n" % frozenFiles)
            sys.stdout.write("  \"frozenBytes\": %d,\n" % frozenBytes)
            sys.stdout.write("  \"lastActive\": \"%s\",\n" % lastActive)
            sys.stdout.write("  \"storageVolume\": \"%s\"\n" % storageVolume)
            sys.stdout.write("}\n")

    except Exception as error:
        try:
            logging.error(str(error))
        except Exception as logerror:
            sys.stderr.write("ERROR: %s\n" % str(logerror))
        sys.stderr.write("ERROR: %s\n" % str(error))
        sys.exit(1)


def load_configuration(pathname):
    """
    Load and return as a dict variables from the main ida configuration file
    """
    module_name = "config.variables"
    try:
        # python versions >= 3.5
        module_spec = importlib.util.spec_from_file_location(module_name, pathname)
        config = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(config)
    except AttributeError:
        # python versions < 3.5
        from importlib.machinery import SourceFileLoader
        config = SourceFileLoader(module_name, pathname).load_module()
    return config


if __name__ == "__main__":
    main()
