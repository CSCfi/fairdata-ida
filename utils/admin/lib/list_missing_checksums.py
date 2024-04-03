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
# This script lists all files stored in Nextcloud which have no SHA-256 checksum
# defined in the Nextcloud cache
# --------------------------------------------------------------------------------

import sys
import os
import time
import requests
import logging
import psycopg2
from sortedcontainers import SortedDict
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from utils import LOG_ENTRY_FORMAT, TIMESTAMP_FORMAT, load_configuration

# Use UTC
os.environ['TZ'] = 'UTC'
time.tzset()

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def main():

    try:

        # Arguments: ROOT PROJECT

        if len(sys.argv) < 3 or len(sys.argv) > 4:
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

        files = get_files_with_no_checksum(config)

        for pathname in list(files.keys()):
            print("%s" % pathname[5:])

    except Exception as error:
        try:
            logging.error(str(error))
        except Exception as logerror:
            sys.stderr.write("ERROR: %s\n" % str(logerror))
        sys.stderr.write("ERROR: %s\n" % str(error))
        sys.exit(1)


def get_files_with_no_checksum(config):
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

    query = "SELECT fileid, path, size FROM %sfilecache \
             WHERE storage = %d \
             AND mimetype !=2 \
             AND path LIKE 'files/%s%%' \
             AND ( checksum IS NULL OR checksum = '' OR LOWER(checksum) NOT LIKE 'sha256:%%' )" % (
                 config.DBTABLEPREFIX,
                 storage_id,
                 config.PROJECT
            )

    cur.execute(query)
    rows = cur.fetchall()

    for row in rows:
        files[row[1]] = { 'id': row[0], 'size': row[2] }

    # Close database connection
    cur.close()
    conn.close()

    return files


if __name__ == "__main__":
    main()
