# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2023 Ministry of Education and Culture, Finland
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
# This script ensures that all files stored in Nextcloud have an SHA-256 checksum
# defined in the Nextcloud cache, generating checksums as needed
#
# Missing checksums can be generated either for a specific project or for all
# projects if no project is specified; and if done for all projects, generation
# is done project by project to keep database queries and memory usage reasonable
#
# The following index should be defined in postgres:
#
# CREATE INDEX oc_filecache_missing_checksums_idx
# ON oc_filecache
# USING btree (storage, mimetype, checksum)
# WITH (fillfactor = 50)
# --------------------------------------------------------------------------------

import importlib.util
import sys
import os
import time
import requests
import logging
import psycopg2
from hashlib import sha256
from pathlib import Path
from sortedcontainers import SortedDict
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from list_missing_checksums import get_files_with_no_checksum
from utils import *

# Use UTC
os.environ['TZ'] = 'UTC'
time.tzset()

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def main():

    try:

        # Arguments: ROOT PROJECT

        if len(sys.argv) != 3:
            raise Exception('Invalid number of arguments')

        # Load service configuration and constants, and add essential definitions

        config = load_configuration("%s/config/config.sh" % sys.argv[1])
        constants = load_configuration("%s/lib/constants.sh" % sys.argv[1])

        config.PROJECT_USER_PREFIX = constants.PROJECT_USER_PREFIX
        config.SCRIPT = os.path.basename(sys.argv[0])
        config.PID = os.getpid()
        config.PROJECT = sys.argv[2]

        # Initialize logging using UTC timestamps

        if config.DEBUG:
            config.LOG_LEVEL = logging.DEBUG
        else:
            config.LOG_LEVEL = logging.INFO

        logging.basicConfig(
            filename=config.LOG,
            level=config.LOG_LEVEL,
            format=LOG_ENTRY_FORMAT,
            datefmt=TIMESTAMP_FORMAT
        )
        logging.Formatter.converter = time.gmtime
        logging.info("START %s" % config.PROJECT)

        generate_missing_checksums(config)

    except Exception as error:
        try:
            logging.error(str(error))
        except Exception as logerror:
            sys.stderr.write("ERROR: %s\n" % str(logerror))
        sys.stderr.write("ERROR: %s\n" % str(error))
        sys.exit(1)


def generate_missing_checksums(config):

    if config.DEBUG:
        sys.stderr.write("Generating missing checksums for project: %s\n" % config.PROJECT)
        sys.stderr.write("Identifying files with missing checksums...\n")

    files = get_files_with_no_checksum(config)

    count = len(files)

    if config.DEBUG:
        sys.stderr.write("Files with missing checksums: %d\n" % count)

    for pathname, file in list(files.items()):

        if config.DEBUG:
            sys.stderr.write("Generating checksum for %s\n" % pathname[5:])

        checksum = generate_checksum("%s/%s%s/%s" % (
            config.STORAGE_OC_DATA_ROOT,
            config.PROJECT_USER_PREFIX,
            config.PROJECT,
            pathname
        ))

        if not checksum.startswith('sha256:'):
            checksum = "sha256:%s" % checksum

        if checksum:
            file['checksum'] = checksum

    store_checksums_in_cache(config, files)


def store_checksums_in_cache(config, files):
    """
    Store all checksums for all provided files to the Nextcloud file cache
    """

    if config.DEBUG:
        sys.stderr.write("Recording checksums to Nextcloud cache...\n")

    # Open database connection

    conn = psycopg2.connect(database=config.DBNAME,
                            user=config.DBROUSER,
                            password=config.DBROPASSWORD,
                            host=config.DBHOST,
                            port=config.DBPORT)

    cur = conn.cursor()

    for pathname, file in list(files.items()):

        try:

            checksum = file.get('checksum')

            if checksum:

                query = "UPDATE %sfilecache SET checksum = '%s' WHERE fileid = %d" % (
                    config.DBTABLEPREFIX,
                    checksum,
                    file['id']
                )

                cur.execute(query)
                conn.commit()

                if cur.rowcount == 1:
                    msg = "Checksum %s recorded in cache for %s" % (checksum, pathname[5:])
                    logging.info(msg)
                    if config.DEBUG:
                        sys.stderr.write("%s\n" % msg)
                else:
                    conn.rollback()
                    if config.DEBUG:
                        sys.stderr.write("Warning: Failed to record checksum for %s\n" % pathname[5:])

        except Exception as e:
            conn.rollback()
            if config.DEBUG:
                sys.stderr.write("Warning: Failed to record checksum for %s: %s\n" % (pathname[5:], str(e)))

    # Close database connection
    cur.close()
    conn.close()


def get_cache_file_details(config):
    """
    Query the Nextcloud database and return a dictionary for all cache files which have no SHA-256
    checksum where the key is the pathname and the value is an object containing the file id (to
    which a generated checksum will be later added)
    """

    files = SortedDict([])

    # Open database connection

    conn = psycopg2.connect(database=config.DBNAME,
                            user=config.DBROUSER,
                            password=config.DBROPASSWORD,
                            host=config.DBHOST,
                            port=config.DBPORT)

    cur = conn.cursor()

    # Retrieve PSO storage id for project

    query = "SELECT numeric_id FROM %sstorages \
             WHERE id = 'home::%s%s' \
             LIMIT 1" % (
                config.DBTABLEPREFIX,
                config.PROJECT_USER_PREFIX,
                config.PROJECT
            )

    cur.execute(query)
    rows = cur.fetchall()

    if len(rows) != 1:
        raise Exception("Failed to retrieve storage id for project %s" % config.PROJECT)

    storage_id = rows[0][0]

    # Retrieve files with no SHA-256 checksum

    query = "SELECT fileid, path FROM %sfilecache \
             WHERE storage = %d \
             AND mimetype !=2 \
             AND ( checksum IS NULL OR checksum = '' OR LOWER(checksum) NOT LIKE 'sha256:%%' )" % (
                 config.DBTABLEPREFIX,
                 storage_id
            )

    cur.execute(query)
    rows = cur.fetchall()

    for row in rows:
        files[row[1]] = { 'id': row[0] }

    # Close database connection
    cur.close()
    conn.close()

    return files


if __name__ == "__main__":
    main()
