# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2024 Ministry of Education and Culture, Finland
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
# This script loads a project audit error file (encoded in JSON) and for each
# file cache orphan record reported, purges the record from the database.
#
# Note that any Nextcloud cache record that is erroneously purged by this script
# where there actually exists a file on disk, can be restored using the Nextcloud
# occ files:scan utility.
# --------------------------------------------------------------------------------

import sys
import time
import json
import logging
import requests
import psycopg2
import re
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from utils import LOG_ENTRY_FORMAT, TIMESTAMP_FORMAT, load_configuration, generate_timestamp, get_project_pathname

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def main():

    try:

        # Arguments: ROOT ERROR_FILE

        argc = len(sys.argv)

        if argc != 3:
            raise Exception('Invalid number of arguments')
    
        # Load service configuration and constants, and add command arguments
        # and global values needed for auditing

        config = load_configuration("%s/config/config.sh" % sys.argv[1])
        constants = load_configuration("%s/lib/constants.sh" % sys.argv[1])

        config.STAGING_FOLDER_SUFFIX = constants.STAGING_FOLDER_SUFFIX
        config.PROJECT_USER_PREFIX = constants.PROJECT_USER_PREFIX

        # Initialize logging using UTC timestamps

        if config.DEBUG:
            config.LOG_LEVEL = logging.DEBUG
        else:
            config.LOG_LEVEL = logging.INFO

        logging.basicConfig(
            filename=config.LOG,
            level=config.LOG_LEVEL,
            format=LOG_ENTRY_FORMAT,
            datefmt=TIMESTAMP_FORMAT)

        logging.Formatter.converter = time.gmtime

        # load report file data

        with open(sys.argv[2]) as f:
           data = json.load(f)

        config.PROJECT = data["project"]
        config.STORAGE_ID = get_project_storage_id(config)

        logging.info("START %s %s" % (config.PROJECT, generate_timestamp()))

        # for each invalid node in audit report:
        #     if the node has an orphan cache record:
        #         purge the orphan cache record from the database

        nodes = data.get("invalidNodes", {})

        orphan_error = "Node does not exist in filesystem"

        for pathname in nodes:

            if config.DEBUG:
                sys.stderr.write("NODE PATHNAME: %s\n" % pathname)

            node = nodes[pathname]
            nextcloud = node.get("nextcloud")
            errors = node.get("errors", [])

            # If the node has details recorded in the Nextcloud cache and does not exist in the filesystem, then
            # the Nextcloud cache record is an orphan and needs to be purged.

            if nextcloud and orphan_error in errors:

                if config.DEBUG:
                    sys.stderr.write("ERROR: %s\n" % orphan_error)

                purge_orphan_node_from_database(config, pathname)

        logging.info("DONE")

    except Exception as e:
        try:
            logging.error(str(e).strip())
        except Exception as le:
            sys.stderr.write("ERROR: %s\n" % str(le).strip())
        sys.stderr.write("ERROR: %s\n" % str(e).strip())
        sys.exit(1)


def get_project_storage_id(config):

    conn = psycopg2.connect(database=config.DBNAME,
                            user=config.DBROUSER,
                            password=config.DBROPASSWORD,
                            host=config.DBHOST,
                            port=config.DBPORT)

    cur = conn.cursor()

    query = "SELECT numeric_id FROM %sstorages \
             WHERE id = 'home::%s%s' \
             LIMIT 1" % (config.DBTABLEPREFIX, config.PROJECT_USER_PREFIX, config.PROJECT)

    if config.DEBUG:
        sys.stderr.write("QUERY: %s\n" % re.sub(r'\s+', ' ', query.strip()))

    cur.execute(query)
    rows = cur.fetchall()

    if len(rows) != 1:
        raise Exception("Failed to retrieve storage id for project %s" % config.PROJECT)

    storage_id = rows[0][0]

    if config.DEBUG:
        sys.stderr.write("STORAGE_ID: %d\n" % (storage_id))

    return storage_id


def purge_orphan_node_from_database(config, pathname):

    conn = psycopg2.connect(database=config.DBNAME,
                            user=config.DBUSER,
                            password=config.DBPASSWORD,
                            host=config.DBHOST,
                            port=config.DBPORT)

    cur = conn.cursor()

    if pathname.startswith('frozen/'):
        cache_pathname = "files/%s/%s" % (config.PROJECT, pathname[7:])
    elif pathname.startswith('staging/'):
        cache_pathname = "files/%s%s/%s" % (config.PROJECT, config.STAGING_FOLDER_SUFFIX, pathname[8:])
    else:
        raise Exception("Invalid auditing report pathname %s" % pathname)

    if config.DEBUG:
        sys.stderr.write("CACHE PATHNAME: %s\n" % cache_pathname)

    query = "DELETE FROM %sfilecache \
             WHERE storage = %d \
             AND path = '%s'" % (config.DBTABLEPREFIX, config.STORAGE_ID, cache_pathname)

    if config.DEBUG:
        sys.stderr.write("QUERY: %s\n" % re.sub(r'\s+', ' ', query.strip()))

    cur.execute(query)

    if config.DEBUG:
        sys.stderr.write("ROWS PURGED: %d\n" % cur.rowcount)

    conn.commit()


if __name__ == "__main__":
    main()
