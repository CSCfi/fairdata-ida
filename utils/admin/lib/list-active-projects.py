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
import json
import psycopg2
import time
import dateutil.parser
from sortedcontainers import SortedDict
from datetime import datetime, timezone
from time import strftime
from subprocess import Popen, PIPE
from stat import *


def main():

    try:

        if len(sys.argv) != 4:
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
        config.START = sys.argv[3]

        if config.DEBUG == 'true':
            config.LOG_LEVEL = logging.DEBUG
        else:
            config.LOG_LEVEL = logging.INFO
    
        if config.DEBUG == 'true':
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

        if config.DEBUG == 'true':
            sys.stderr.write("SINCE:         %s\n" % config.SINCE)
            sys.stderr.write("SINCE_TS:      %d\n" % config.SINCE_TS)
            sys.stderr.write("SINCE_DT:      %s\n" % str(since_datetime))
            since_datetime_check = datetime.fromtimestamp(config.SINCE_TS, timezone.utc)
            sys.stderr.write("SINCE_DT_CHK:  %s\n" % str(since_datetime_check))

        # Convert START ISO timestamp string to epoch seconds

        start_datetime = dateutil.parser.isoparse(config.START)
        config.START_TS = start_datetime.replace(tzinfo=timezone.utc).timestamp()

        if config.DEBUG == 'true':
            sys.stderr.write("START:         %s\n" % config.START)
            sys.stderr.write("START_TS:      %d\n" % config.START_TS)
            sys.stderr.write("START_DT:      %s\n" % str(start_datetime))
            start_datetime_check = datetime.fromtimestamp(config.START_TS, timezone.utc)
            sys.stderr.write("START_DT_CHK:  %s\n" % str(start_datetime_check))

        # Initialize logging with UTC timestamps

        logging.basicConfig(
            filename=config.LOG,
            level=config.LOG_LEVEL,
            format="%s %s (%s) %s" % ('%(asctime)s', config.SCRIPT, config.PID, '%(message)s'),
            datefmt="%Y-%m-%dT%H:%M:%SZ")

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


def add_from_ida_action_table(projects, config):
    """
    Query the ida_action table in the database for all actions initiated, complated
    or failed between the SINCE and START timestamps and record their projects.
    """

    # Open database connection 

    conn = psycopg2.connect(
               database=config.DBNAME,
               user=config.DBROUSER,
               password=config.DBROPASSWORD,
               host=config.DBHOST,
               port=config.DBPORT)

    cur = conn.cursor()

    # Select project from all actions initiated, completed, or failed after SINCE and before START

    cur.execute("SELECT project FROM %sida_action \
                 WHERE \
                 ( initiated > '%s' \
                   OR ( completed IS NOT NULL AND completed > '%s' ) \
                   OR ( failed    IS NOT NULL AND failed    > '%s' ) ) \
                 AND initiated < '%s'"
                 % (config.DBTABLEPREFIX, config.SINCE, config.SINCE, config.SINCE, config.START))

    rows = cur.fetchall()

    # Add project name to set of active projects

    for row in rows:

        project = row[0]
        projects[project] = True

        if config.DEBUG == 'true':
            sys.stderr.write("ida_action:    %s\n" % project)

    # Close database connection

    conn.close()


def add_from_filecache_table(projects, config):
    """
    Query the filecache table in the database for the storage ids of all nodes
    created or updated between the SINCE and START timestamps, and for each
    storage id, check if the storage owner is a PSO user, and if so, extract
    the project name from the PSO username and record the project.
    """

    # Open database connection 

    conn = psycopg2.connect(
               database=config.DBNAME,
               user=config.DBROUSER,
               password=config.DBROPASSWORD,
               host=config.DBHOST,
               port=config.DBPORT)

    cur = conn.cursor()

    # Select unique set of storage ids from all nodes created or modified after SINCE and before START

    cur.execute("SELECT DISTINCT storage FROM %sfilecache WHERE mtime > %d AND mtime < %d"
                 % (config.DBTABLEPREFIX, config.SINCE_TS, config.START_TS))

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

            if config.DEBUG == 'true':
                sys.stderr.write("filecache:     %s\n" % project)

    # Close database connection

    conn.close()


def list_active_projects(config):
    """
    List active projects according to the configured values provided by examining
    key tables in the database for activity.
    """

    logging.info("START %s" % config.START)

    projects = SortedDict({})

    # Identify active projects from each of the key databases 

    add_from_ida_action_table(projects, config)
    add_from_filecache_table(projects, config)

    # Output projects

    for project in projects.keys():
       sys.stdout.write("%s\n" % project)

    logging.info("DONE")


if __name__ == "__main__":
    main()
