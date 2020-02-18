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
# This script will query the Nextcloud database and return the total number of
# total files, and frozen files associated with the specified project.
# The first argument must be the ROOT of the IDA code base.
# The second argument must be the name of a project.
# --------------------------------------------------------------------------------

import importlib.util
import sys
import os
import json
import psycopg2

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
        config.PROJECT = sys.argv[2]

        #config.DEBUG = 'true' # TEMP HACK

        if config.DEBUG == 'true':
            sys.stderr.write("--- %s ---\n" % config.SCRIPT)
            sys.stderr.write("ROOT:          %s\n" % config.ROOT)
            sys.stderr.write("DATA_ROOT:     %s\n" % config.STORAGE_OC_DATA_ROOT)
            sys.stderr.write("DBHOST:        %s\n" % config.DBHOST)
            sys.stderr.write("DBROUSER:      %s\n" % config.DBROUSER)
            sys.stderr.write("DBNAME:        %s\n" % config.DBNAME)
            sys.stderr.write("ARGS#:         %d\n" % len(sys.argv))
            sys.stderr.write("ARGS:          %s\n" % str(sys.argv))
            sys.stderr.write("PROJECT:       %s\n" % config.PROJECT)
    
        # Open database connection 

        conn = psycopg2.connect(
                   database=config.DBNAME,
                   user=config.DBROUSER,
                   password=config.DBROPASSWORD,
                   host=config.DBHOST,
                   port=config.DBPORT)

        cur = conn.cursor()

        # Retrieve PSO storage id for project

        query = "SELECT numeric_id FROM %sstorages \
                 WHERE id = 'home::%s%s' \
                 LIMIT 1" % (config.DBTABLEPREFIX, config.PROJECT_USER_PREFIX, config.PROJECT)

        #if config.DEBUG == 'true':
        #    sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        if len(rows) != 1:
            raise Exception("Failed to retrieve storage id for project %s" % config.PROJECT)

        storage_id = rows[0][0]

        if config.DEBUG == 'true':
            sys.stderr.write("STORAGE_ID:    %d\n" % (storage_id))

        # Select all records for project files

        query = "SELECT COUNT (*) FROM %sfilecache \
                 WHERE storage = %d \
                 AND mimetype != 2 \
                 AND path ~ 'files/%s\+?/' " % (config.DBTABLEPREFIX, storage_id, config.PROJECT)

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        totalFiles = rows[0][0]

        # Select all records for frozen project files

        query = "SELECT COUNT (*) FROM %sfilecache \
                 WHERE storage = %d \
                 AND mimetype != 2 \
                 AND path ~ 'files/%s/' " % (config.DBTABLEPREFIX, storage_id, config.PROJECT)

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY: %s\n" % query)

        cur.execute(query)
        rows = cur.fetchall()

        frozenFiles = rows[0][0]

        # Close database connection and return auditing data object

        conn.close()

        sys.stdout.write("{\n")
        sys.stdout.write("  \"totalFiles\":  %d,\n" % totalFiles)
        sys.stdout.write("  \"frozenFiles\": %d\n"  % frozenFiles)
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
