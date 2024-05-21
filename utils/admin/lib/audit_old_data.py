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

import sys
import os
import socket
import requests
import json
import logging
import psycopg2
import time
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from sortedcontainers import SortedDict
from stat import *
from utils import LOG_ENTRY_FORMAT, TIMESTAMP_FORMAT, NULL_VALUES, load_configuration, normalize_timestamp, \
                  get_last_add_change_timestamps, log_and_output

# Use UTC
os.environ['TZ'] = 'UTC'
time.tzset()

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def main():

    try:

        # Arguments: ROOT PROJECT

        argc = len(sys.argv)

        if argc != 5:
            raise Exception('Invalid number of arguments: %s' % json.dumps(sys.argv))

        # Load service configuration and constants, and add command arguments
        # and global values needed for auditing

        config = load_configuration("%s/config/config.sh" % sys.argv[1])
        constants = load_configuration("%s/lib/constants.sh" % sys.argv[1])

        # If in production, ensure we are not running on uida-man.csc.fi
        hostname = socket.getfqdn()
        if config.IDA_ENVIRONMENT == 'PRODUCTION' and hostname in [ 'idaman.fairdata.fi', 'uida-man.csc.fi' ]:
            raise Exception ("Do not run old data auditing on %s" % hostname)

        #config.DEBUG = True         # TEMP HACK
        #config.DEBUG_VERBOSE = True # TEMP HACK

        # Copy essential constants to config so they are easily passed to functions
        config.STAGING_FOLDER_SUFFIX = constants.STAGING_FOLDER_SUFFIX
        config.PROJECT_USER_PREFIX = constants.PROJECT_USER_PREFIX
        config.IDA_MIGRATION = constants.IDA_MIGRATION
        config.IDA_MIGRATION_TS = constants.IDA_MIGRATION_TS

        config.PID = os.getpid()
        config.SCRIPT = os.path.basename(sys.argv[0])
        config.PROJECT = sys.argv[2]
        config.MAX_DATA_AGE_IN_DAYS = int(sys.argv[3])
        config.QUIET = bool(sys.argv[4] == 'true')

        config.PROJECT_ROOT = "%s/%s%s" % (config.STORAGE_OC_DATA_ROOT, config.PROJECT_USER_PREFIX, config.PROJECT)
        config.PROJECT_CREATED = max([normalize_timestamp(os.path.getmtime(config.PROJECT_ROOT)), config.IDA_MIGRATION])

        config.LOOP_MIN = 1000

        # Calculate age limit datetime and epoch timestamp

        config.AGE_LIMIT_SECONDS = int((datetime.now(timezone.utc) - timedelta(days=int(config.MAX_DATA_AGE_IN_DAYS))).timestamp())
        config.AGE_LIMIT_TIMESTAMP = normalize_timestamp(config.AGE_LIMIT_SECONDS)

        # Initialize logging using UTC timestamps

        log_root = os.path.dirname(config.LOG)
        log_file = os.path.basename(config.LOG)
        config.LOG = "%s/old_data/%s" % (log_root, log_file)

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

        logging.info("%s START" % config.PROJECT)

        if config.DEBUG:
            logging.debug("%s ROOT: %s" % (config.PROJECT, config.ROOT))
            logging.debug("%s LOG: %s" % (config.PROJECT, config.LOG))
            logging.debug("%s LOG_LEVEL: %s" % (config.PROJECT, config.LOG_LEVEL))
            logging.debug("%s DBHOST: %s" % (config.PROJECT, config.DBHOST))
            logging.debug("%s DBPORT: %s" % (config.PROJECT, config.DBPORT))
            logging.debug("%s DBROUSER: %s" % (config.PROJECT, config.DBROUSER))
            logging.debug("%s DBNAME: %s" % (config.PROJECT, config.DBNAME))
            logging.debug("%s METAX_API: %s" % (config.PROJECT, config.METAX_API))
            logging.debug("%s METAX_VERSION: %s" % (config.PROJECT, str(config.METAX_API_VERSION)))
            logging.debug("%s ARGS#: %d" % (config.PROJECT, argc))
            logging.debug("%s ARGS: %s" % (config.PROJECT, str(sys.argv)))
            logging.debug("%s PID: %s" % (config.PROJECT, config.PID))
            logging.debug("%s MAX_DATA_AGE_IN_DAYS: %s" % (config.PROJECT, config.MAX_DATA_AGE_IN_DAYS))
            logging.debug("%s AGE_LIMIT_SECONDS: %s" % (config.PROJECT, config.AGE_LIMIT_SECONDS))
            logging.debug("%s AGE_LIMIT_TIMESTAMP: %s" % (config.PROJECT, config.AGE_LIMIT_TIMESTAMP))

        # Audit the project data, detecting any old data, and output a report if there is old data

        report = audit_old_data(config)

        log_and_output(config, logging.INFO, "%s TOTAL_BYTES:         %d" % (config.PROJECT, report.get('totalFrozenBytes', 0) + report.get('totalStagingBytes', 0)))
        log_and_output(config, logging.INFO, "%s TOTAL_FILES:         %d" % (config.PROJECT, report.get('totalFrozenFiles', 0) + report.get('totalStagingFiles', 0)))
        log_and_output(config, logging.INFO, "%s TOTAL_FROZEN_BYTES:  %d" % (config.PROJECT, report.get('totalFrozenBytes', 0)))
        log_and_output(config, logging.INFO, "%s TOTAL_FROZEN_FILES:  %d" % (config.PROJECT, report.get('totalFrozenFiles', 0)))
        log_and_output(config, logging.INFO, "%s TOTAL_STAGING_BYTES: %d" % (config.PROJECT, report.get('totalStagingBytes', 0)))
        log_and_output(config, logging.INFO, "%s TOTAL_STAGING_FILES: %d" % (config.PROJECT, report.get('totalStagingFiles', 0)))
        output_report(config, report)

        logging.info("%s DONE" % config.PROJECT)

    except Exception as error:
        log_and_output(config, logging.ERROR, str(error))
        sys.exit(1)


def audit_old_data(config):
    """
    Audit a project's data according to the configured values provided and return a report of any old files
    (if the project is newer than the specified maximum age in days, skip all data analysis and report no old files)
    """

    report = {}
    report['project'] = config.PROJECT
    report['createdInIDA'] = config.PROJECT_CREATED
    report['maxDataAgeInDays'] = config.MAX_DATA_AGE_IN_DAYS
    report['totalFrozenFiles'] = 0
    report['totalFrozenBytes'] = 0
    report['totalStagingFiles'] = 0
    report['totalStagingBytes'] = 0
    report['frozenFiles'] = {}
    report['stagingFiles'] = {}

    if config.PROJECT_CREATED > config.AGE_LIMIT_TIMESTAMP:
        return report

    old_files = get_old_files(config)
    old_file_count = len(old_files.get('frozenFiles', 0))

    if old_file_count > 0:

        metax_published_files = get_metax_published_file_pathnames(config)

        # Iterate over all frozen files in IDA, filtering out those included in a published dataset

        log_and_output(config, logging.DEBUG, "%s Excluding old frozen files published in one or more datasets..." % config.PROJECT)

        old_frozen_files = {}

        if old_file_count >= config.LOOP_MIN:
            loop_count = 0
            if not config.QUIET:
                sys.stderr.write(".")

        for pathname, file in old_files['frozenFiles'].items():

            if old_file_count >= config.LOOP_MIN:
                loop_count = loop_count + 1
                if not config.QUIET and loop_count % config.LOOP_MIN == 0:
                    sys.stderr.write(".")

            if (metax_published_files.get(pathname, None) != None):
                if config.DEBUG_VERBOSE:
                    logging.debug("%s PUBLISHED FILE: %s" % (config.PROJECT, json.dumps(pathname)))
            else:
                old_frozen_files[pathname] = file
                if config.DEBUG_VERBOSE:
                    logging.debug("%s OLD FROZEN FILE: %s" % (config.PROJECT, json.dumps(pathname)))

        if not config.QUIET and old_file_count >= config.LOOP_MIN:
            sys.stderr.write("\n")

        old_files['frozenFiles'] = old_frozen_files

    # Update report from results

    report['totalFrozenFiles'] = len(old_files['frozenFiles'])
    report['totalFrozenBytes'] = sum(file['size'] for file in old_files['frozenFiles'].values())
    report['totalStagingFiles'] = len(old_files['stagingFiles'])
    report['totalStagingBytes'] = sum(file['size'] for file in old_files['stagingFiles'].values())
    report['frozenFiles'] = old_files['frozenFiles']
    report['stagingFiles'] = old_files['stagingFiles']

    return report


def get_old_files(config):
    """
    Query the Nextcloud database and return all files where the upload timestamp is null or older
    than the age limit. Returns object with root fields 'frozenFiles' and 'stagingFiles' each containing
    sorted dicts with pathnames as keys and file objects as values.
    """

    log_and_output(config, logging.DEBUG, "%s Retrieving old files from Nextcloud..." % config.PROJECT)

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
             LIMIT 1" % (config.DBTABLEPREFIX, config.PROJECT_USER_PREFIX, config.PROJECT)

    if config.DEBUG_VERBOSE:
        logging.debug("%s QUERY: %s" % (config.PROJECT, re.sub(r'\s+', ' ', query.strip())))

    cur.execute(query)
    rows = cur.fetchall()

    if len(rows) != 1:
        raise Exception("Failed to retrieve storage id for project %s" % config.PROJECT)

    storage_id = rows[0][0]

    if config.DEBUG_VERBOSE:
        logging.debug("%s STORAGE_ID: %d" % (config.PROJECT, storage_id))

    # Limit query to files where the modification and upload time (if any) is less (earlier) than AGE_LIMIT_SECONDS

    base_query = "SELECT cache.path, cache.size, cache.mtime, extended.upload_time \
                  FROM %sfilecache as cache \
                  LEFT JOIN %sfilecache_extended as extended \
                  ON cache.fileid = extended.fileid \
                  WHERE cache.storage = %d \
                  AND cache.mimetype != 2 \
                  AND GREATEST(cache.mtime, COALESCE(extended.upload_time, 0)) < %d" % (
                      config.DBTABLEPREFIX,
                      config.DBTABLEPREFIX,
                      storage_id,
                      config.AGE_LIMIT_SECONDS
                 )

    # Get frozen files

    log_and_output(config, logging.DEBUG, "%s Retrieving old frozen files..." % config.PROJECT)

    query = "%s AND cache.path LIKE 'files/%s/%%'" % (base_query, config.PROJECT)

    if config.DEBUG_VERBOSE:
        logging.debug("%s QUERY: %s" % (config.PROJECT, re.sub(r'\s+', ' ', query.strip())))

    cur.execute(query)
    rows = cur.fetchall()

    log_and_output(config, logging.DEBUG, "%s Retrieved frozen file count: %d" % (config.PROJECT, len(rows)))

    frozen_files = build_file_details(config, rows)

    if config.DEBUG_VERBOSE:
        logging.debug("%s FROZEN FILES: %s" % (config.PROJECT, json.dumps(frozen_files)))
        
    logging.debug("%s FROZEN FILE COUNT: %d" % (config.PROJECT, len(frozen_files)))

    # Get staging files

    log_and_output(config, logging.DEBUG, "%s Retrieving old staging files..." % config.PROJECT)

    query = "%s AND cache.path LIKE 'files/%s%s/%%'" % (base_query, config.PROJECT, config.STAGING_FOLDER_SUFFIX)

    if config.DEBUG_VERBOSE:
        logging.debug("%s QUERY: %s" % (config.PROJECT, re.sub(r'\s+', ' ', query.strip())))

    cur.execute(query)
    rows = cur.fetchall()

    log_and_output(config, logging.DEBUG, "%s Retrieved staging file count: %d" % (config.PROJECT, len(rows)))

    staging_files = build_file_details(config, rows)

    if config.DEBUG_VERBOSE:
        logging.debug("%s STAGING FILES: %s" % (config.PROJECT, json.dumps(staging_files)))
        
    logging.debug("%s STAGING FILE COUNT: %d" % (config.PROJECT, len(staging_files)))

    # Close database connection
    cur.close()
    conn.close()

    return { 'frozenFiles': frozen_files, 'stagingFiles': staging_files }


def build_file_details(config, rows):

    log_and_output(config, logging.DEBUG, "%s Building file details..." % config.PROJECT)

    row_count = len(rows)

    if config.DEBUG_VERBOSE:
        logging.debug("%s ROW COUNT: %d" % (config.PROJECT, len(rows)))

    files = SortedDict({})

    last_add_change_timestamps = get_last_add_change_timestamps(config)

    project_name_len = len(config.PROJECT)
    project_name_frozen_offset = project_name_len + 1
    project_name_staging_offset = project_name_len + 2

    if row_count >= config.LOOP_MIN:
        loop_count = 0
        if not config.QUIET:
            sys.stderr.write(".")

    for row in rows:

        if row_count >= config.LOOP_MIN:
            loop_count = loop_count + 1
            if not config.QUIET and loop_count % config.LOOP_MIN == 0:
                sys.stderr.write(".")

        if config.DEBUG_VERBOSE:
            logging.debug("%s ROW: %s" % (config.PROJECT, json.dumps(row)))

        pathname = row[0]

        # Remove 'files' prefix

        pathname = pathname[5:]

        # Remove shared folder prefix

        if pathname[(project_name_frozen_offset)] == '+':
            pathname = pathname[(project_name_staging_offset):]
        else:
            pathname = pathname[(project_name_frozen_offset):]

        modified = normalize_timestamp(datetime.utcfromtimestamp(row[2]))

        if row[3] in NULL_VALUES:
            uploaded = None
        else:
            uploaded = normalize_timestamp(datetime.utcfromtimestamp(row[3]))

        # If the uploaded timestamp is None, and if we are doing a full audit, retrieve the latest 'add' change event for
        # project and file pathname in staging from the changes table, and if exists and is older than the age limit, use
        # the add timestamp as the uploaded timestamp, else skip the file since it actually was uploaded later than the
        # specified time limit

        if uploaded == None:
            logging.debug("%s Getting last add change timestamp for pathname %s" % (config.PROJECT, pathname))
            added = last_add_change_timestamps.get(pathname)
            logging.debug("%s Last add change timestamp for pathname %s" % (config.PROJECT, str(added)))
            if added:
                if added < config.AGE_LIMIT_TIMESTAMP:
                    uploaded = added
                else:
                    continue

        file_details = { "size": row[1], "modified": modified, "uploaded": uploaded }
    
        if config.DEBUG_VERBOSE:
            logging.debug("%s FILE DETAILS: %s" % (config.PROJECT, json.dumps(file_details)))
    
        files[pathname] = file_details

    if not config.QUIET and row_count >= config.LOOP_MIN:
        sys.stderr.write("\n")

    return files


def get_metax_published_file_pathnames(config):
    """
    Query the Metax API and return a dict where for all files associated with the project which are
    included in a published dataset the key is the relative pathname of the file and the value is True
    """

    # Get all files from Metax associated with project, and store Metax identifier under pathname

    log_and_output(config, logging.DEBUG, "%s Retrieving project files from Metax..." % config.PROJECT)

    metax_project_files = {}

    if config.METAX_API_VERSION >= 3:
        url_base = "%s/files?csc_project=%s&storage_service=ida&limit=%d" % (
            config.METAX_API,
            config.PROJECT,
            config.MAX_FILE_COUNT
        )
        headers = { "Authorization": "Token %s" % config.METAX_PASS }
    else:
        url_base = "%s/files?file_storage=urn:nbn:fi:att:file-storage-ida&ordering=id&project_identifier=%s&limit=%d" % (
            config.METAX_API,
            config.PROJECT,
            config.MAX_FILE_COUNT
        )
        metax_user = (config.METAX_USER, config.METAX_PASS)

    offset = 0
    done = False # we are done when Metax returns less than the specified limit of files

    while not done:

        url = "%s&offset=%d" % (url_base, offset)

        if config.DEBUG_VERBOSE:
            logging.debug("%s QUERY URL: %s" % (config.PROJECT, url))

        try:

            if config.METAX_API_VERSION >= 3:
                response = requests.get(url, headers=headers)
            else:
                response = requests.get(url, auth=metax_user)

            if response.status_code not in [ 200, 404 ]:
                raise Exception("Failed to retrieve frozen file metadata from Metax for project %s: %d" % (config.PROJECT, response.status_code))

            response_data = response.json()

            if config.DEBUG_VERBOSE:
                logging.debug("%s QUERY RESPONSE: %s" % (config.PROJECT, json.dumps(response_data)))

            files = response_data['results']

        except Exception as error:
            raise Exception("Failed to retrieve frozen file metadata from Metax for project %s: %s" % (config.PROJECT, str(error)))

        for file in files:
            if config.METAX_API_VERSION >= 3:
                metax_project_files[file['storage_identifier']] = file['pathname']
            else:
                metax_project_files[file['identifier']] = file['file_path']

        if len(files) < config.MAX_FILE_COUNT:
            done = True
        else:
            offset = offset + config.MAX_FILE_COUNT

    log_and_output(config, logging.DEBUG, "%s Retrieved project file count: %d" % (config.PROJECT, len(metax_project_files)))

    # Construct file identifier list for all project files

    metax_project_file_identifiers = list(metax_project_files.keys())

    # Get all files from Metax which are part of a published dataset, based on retrieved file identifier list

    log_and_output(config, logging.DEBUG, "%s Retrieving dataset files from Metax..." % config.PROJECT)

    if len(metax_project_file_identifiers) > 0:

        try:

            if config.METAX_API_VERSION >= 3:
                url = '%s/files/datasets?storage_service=ida&relations=true' % config.METAX_API
                if config.DEBUG_VERBOSE:
                    logging.debug("%s QUERY URL: %s" % (config.PROJECT, url))
                response = requests.post(url, headers=headers, json=metax_project_file_identifiers)
            else:
                url = '%s/files/datasets?keys=files' % config.METAX_API
                if config.DEBUG_VERBOSE:
                    logging.debug("%s QUERY URL: %s" % (config.PROJECT, url))
                response = requests.post(url, auth=metax_user, json=metax_project_file_identifiers)

            response_data = response.json()

            if config.DEBUG_VERBOSE:
                logging.debug("%s QUERY RESPONSE: %s" % (config.PROJECT, json.dumps(response_data)))

            if response.status_code not in [ 200, 404 ]:
                raise Exception("Failed to retrieve frozen file dataset intersections from Metax for project %s: %d" % (config.PROJECT, response.status_code))

            if config.METAX_API_VERSION >= 3:
                metax_dataset_files = list(response.json().keys())
            else:
                metax_dataset_files = response.json()

        except Exception as error:
            raise Exception("Failed to retrieve frozen file metadata from Metax for project %s: %s" % (config.PROJECT, str(error)))

    else:
            metax_dataset_files = []

    if config.DEBUG_VERBOSE:
        logging.debug("%s DATASET FILES: %s" % (config.PROJECT, json.dumps(metax_dataset_files)))

    dataset_file_count = len(metax_dataset_files)

    log_and_output(config, logging.DEBUG, "%s Retrieved dataset file count: %d" % (config.PROJECT, dataset_file_count))

    # Contruct file pathname dict for all Metax project files part of published dataset

    log_and_output(config, logging.DEBUG, "%s Identifying project files published in one or more datasets..." % config.PROJECT)

    metax_published_files = {}

    if dataset_file_count >= config.LOOP_MIN:
        loop_count = 0
        if not config.QUIET:
            sys.stderr.write(".")

    for identifier in metax_dataset_files:

        if dataset_file_count >= config.LOOP_MIN:
            loop_count = loop_count + 1
            if not config.QUIET and loop_count % config.LOOP_MIN == 0:
                sys.stderr.write(".")

        metax_published_files[metax_project_files[identifier]] = True

    if not config.QUIET and dataset_file_count >= config.LOOP_MIN:
        sys.stderr.write("\n")

    if config.DEBUG_VERBOSE:
        logging.debug("%s PUBLISHED FILES: %s" % (config.PROJECT, json.dumps(list(metax_published_files.keys()))))

    log_and_output(config, logging.DEBUG, "%s Published file count: %d" % (config.PROJECT, len(metax_published_files)))

    return metax_published_files


def output_report(config, report):

    # Output report 

    sys.stdout.write('{\n')
    sys.stdout.write('"reportPathname": null,\n')
    sys.stdout.write('"project": %s,\n' % json.dumps(report.get('project')))
    sys.stdout.write('"createdInIDA": %s,\n' % json.dumps(report.get('createdInIDA')))
    sys.stdout.write('"maxDataAgeInDays": %s,\n' % json.dumps(report.get('maxDataAgeInDays')))
    sys.stdout.write('"totalBytes": %s,\n' % json.dumps(report.get('totalFrozenBytes', 0) + report.get('totalStagingBytes', 0)))
    sys.stdout.write('"totalFiles": %s,\n' % json.dumps(report.get('totalFrozenFiles', 0) + report.get('totalStagingFiles', 0)))
    sys.stdout.write('"totalFrozenBytes": %s,\n' % json.dumps(report.get('totalFrozenBytes', 0)))
    sys.stdout.write('"totalFrozenFiles": %s,\n' % json.dumps(report.get('totalFrozenFiles', 0)))
    sys.stdout.write('"totalStagingBytes": %s,\n' % json.dumps(report.get('totalStagingBytes', 0)))
    sys.stdout.write('"totalStagingFiles": %s,\n' % json.dumps(report.get('totalStagingFiles', 0)))
    sys.stdout.write('"frozenFiles": %s,\n' % json.dumps(report.get('frozenFiles', {})))
    sys.stdout.write('"stagingFiles": %s\n' % json.dumps(report.get('stagingFiles', {})))
    sys.stdout.write('}\n')


if __name__ == "__main__":
    main()
