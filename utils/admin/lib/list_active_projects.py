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

import importlib.util
import sys
import os
import logging
import psycopg2
import time
import dateutil.parser
from sortedcontainers import SortedDict
from datetime import datetime, timezone
from time import strftime
from subprocess import Popen, PIPE
from stat import *
from utils import *

# Use UTC
os.environ["TZ"] = "UTC"
time.tzset()


def main():

    try:

        if len(sys.argv) != 3:
            raise Exception('Invalid number of arguments')

        # Load service configuration and constants, and add command arguments
        # and global values needed for auditing

        config = load_configuration("%s/config/config.sh" % sys.argv[1])
        constants = load_configuration("%s/lib/constants.sh" % sys.argv[1])

        config.STAGING_FOLDER_SUFFIX = constants.STAGING_FOLDER_SUFFIX
        config.PROJECT_USER_PREFIX = constants.PROJECT_USER_PREFIX
        config.SCRIPT = os.path.basename(sys.argv[0])
        config.PID = os.getpid()
        config.SINCE = sys.argv[2]

        if config.DEBUG:
            config.LOG_LEVEL = logging.DEBUG
        else:
            config.LOG_LEVEL = logging.INFO

        if config.DEBUG:
            sys.stderr.write("--- %s ---\n" % config.SCRIPT)
            sys.stderr.write("ROOT:          %s\n" % config.ROOT)
            sys.stderr.write("DATA_ROOT:     %s\n" % config.STORAGE_OC_DATA_ROOT)
            sys.stderr.write("LOG:           %s\n" % config.LOG)
            sys.stderr.write("LOG_LEVEL:     %s\n" % config.LOG_LEVEL)
            sys.stderr.write("DBHOST:        %s\n" % config.DBHOST)
            sys.stderr.write("DBROUSER:      %s\n" % config.DBROUSER)
            sys.stderr.write("DBNAME:        %s\n" % config.DBNAME)
            sys.stderr.write("ARGS#:         %d\n" % len(sys.argv))
            sys.stderr.write("ARGS:          %s\n" % str(sys.argv))
            sys.stderr.write("PID:           %s\n" % config.PID)

        # Convert SINCE ISO timestamp string to epoch seconds

        since_datetime = dateutil.parser.isoparse(config.SINCE)
        config.SINCE_TS = since_datetime.replace(tzinfo=timezone.utc).timestamp()

        if config.DEBUG:
            sys.stderr.write("SINCE:         %s\n" % config.SINCE)
            sys.stderr.write("SINCE_DT:      %s\n" % since_datetime.strftime(TIMESTAMP_FORMAT))
            sys.stderr.write("SINCE_TS:      %d\n" % config.SINCE_TS)
            since_datetime_check = datetime.utcfromtimestamp(config.SINCE_TS).strftime(TIMESTAMP_FORMAT)
            sys.stderr.write("SINCE_TS_CHK:  %s\n" % str(since_datetime_check))

        # Initialize logging with UTC timestamps

        logging.basicConfig(
            filename=config.LOG,
            level=config.LOG_LEVEL,
            format=LOG_ENTRY_FORMAT,
            datefmt=TIMESTAMP_FORMAT)

        logging.Formatter.converter = time.gmtime

        # Audit the project according to the configured values

        list_active_projects(config)

    except Exception as error:
        try:
            logging.error(str(error))
        except Exception as logerror:
            sys.stderr.write("%s\n" % str(logerror))
        sys.stderr.write("%s\n" % str(error))
        sys.exit(1)


def add_from_ida_action_table(projects, config):
    """
    Query the ida_action table in the database for all actions initiated, complated
    or failed later than the SINCE timestamp and record their projects.
    """

    # Open database connection

    dblib = psycopg2

    conn = dblib.connect(database=config.DBNAME,
                         user=config.DBROUSER,
                         password=config.DBROPASSWORD,
                         host=config.DBHOST,
                         port=config.DBPORT)

    cur = conn.cursor()

    # Select project from all actions initiated, completed, or failed after SINCE timestamp

    cur.execute("SELECT project FROM %sida_action \
                 WHERE \
                 ( initiated > '%s' \
                   OR ( completed IS NOT NULL AND completed > '%s' ) \
                   OR ( failed    IS NOT NULL AND failed    > '%s' ) )" % (
                    config.DBTABLEPREFIX,
                    config.SINCE,
                    config.SINCE,
                    config.SINCE
                ))

    rows = cur.fetchall()

    # Add project name to set of active projects

    for row in rows:

        project = row[0]
        projects[project] = True

        if config.DEBUG:
            sys.stderr.write("ida_action:    %s\n" % project)

    # Close database connection

    conn.close()


def add_from_filecache_table(projects, config):
    """
    Query the filecache table in the database for the storage ids of all nodes
    uploaded or modified after the SINCE timestamp, and for each storage id, if the
    storage owner is a PSO user, extract the project name from the PSO username and
    record the project.
    """

    # Open database connection

    dblib = psycopg2

    conn = dblib.connect(database=config.DBNAME,
                         user=config.DBROUSER,
                         password=config.DBROPASSWORD,
                         host=config.DBHOST,
                         port=config.DBPORT)

    cur = conn.cursor()

    # Select unique set of storage ids from all files uploaded after SINCE

    query = "SELECT DISTINCT cache.storage \
             FROM %sfilecache as cache LEFT JOIN %sfilecache_extended as extended \
             ON cache.fileid = extended.fileid \
             WHERE cache.mtime > %d \
             OR ( extended.upload_time IS NOT NULL AND extended.upload_time > %d )" % (
                 config.DBTABLEPREFIX,
                 config.DBTABLEPREFIX,
                 config.SINCE_TS,
                 config.SINCE_TS
            )

    cur.execute(query)

    rows = cur.fetchall()

    # For each storage id, if it belongs to a PSO user, add project name to set of active projects

    for row in rows:

        storage_id = row[0]

        # Retrieve PSO storage id for project

        cur.execute("SELECT id from %sstorages WHERE numeric_id = %d LIMIT 1"
                    % (config.DBTABLEPREFIX, storage_id))

        rows2 = cur.fetchall()

        if len(rows2) != 1:
            raise Exception("Failed to retrieve storage owner for storage id %d" % storage_id)

        storage = rows2[0][0]

        pso_home_prefix = "home::%s" % config.PROJECT_USER_PREFIX
        offset = len(pso_home_prefix)

        # If storage owned by PSO user, extract and record project name

        if storage[:offset] == pso_home_prefix:

            project = storage[offset:]

            projects[project] = True

            if config.DEBUG:
                sys.stderr.write("filecache:     %s\n" % project)

    # Close database connection

    conn.close()


def list_active_projects(config):
    """
    List active projects according to the configured values provided by examining
    key tables in the database for activity.
    """

    logging.info("START since=%s" % config.SINCE)

    projects = SortedDict({})

    # Identify active projects from each of the key databases

    add_from_ida_action_table(projects, config)
    add_from_filecache_table(projects, config)

    # Output projects

    for project in projects.keys():
        if os.path.exists("%s/%s%s/files/%s/" % (config.STORAGE_OC_DATA_ROOT, config.PROJECT_USER_PREFIX, project, project)):
            print("%s" % project)

    logging.info("DONE")


if __name__ == "__main__":
    main()
