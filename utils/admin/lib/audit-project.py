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
import socket
import requests
import json
import logging
import psycopg2
import time
import re
import dateutil.parser
from datetime import datetime, timezone
from pathlib import Path
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from sortedcontainers import SortedList
from sortedcontainers import SortedDict
from time import strftime
from subprocess import Popen, PIPE
from stat import *

# Use UTC
os.environ['TZ'] = 'UTC'
time.tzset()

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Node contexts:
#
# filesystem    glusterfs filesystem stats
# Nextcloud     Nextcloud database records
# IDA           IDA frozen file records
# Metax         Metax file records

def main():

    try:

        # Arguments:
        #
        # ROOT PROJECT START SINCE [ ( --staging | --frozen ) ] [ --timestamps ]

        if len(sys.argv) < 5 or len(sys.argv) > 7:
            raise Exception('Invalid number of arguments')

        # Load service configuration and constants, and add command arguments
        # and global values needed for auditing

        config = load_configuration("%s/config/config.sh" % sys.argv[1])
        constants = load_configuration("%s/lib/constants.sh" % sys.argv[1])

        #config.DEBUG = 'true' # TEMP HACK

        # If in production, ensure we are not running on uida-man.csc.fi

        if config.IDA_ENVIRONMENT == 'PRODUCTION':
            if socket.gethostname().startswith('uida-man'):
                raise Exception ("Do not run project auditing on uida-man.csc.fi!")

        config.TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
        config.MIGRATION = '2018-11-01T00:00:00Z'
        config.MIGRATION_TS = 1541030400

        config.STAGING_FOLDER_SUFFIX = constants.STAGING_FOLDER_SUFFIX
        config.PROJECT_USER_PREFIX = constants.PROJECT_USER_PREFIX
        config.SCRIPT = os.path.basename(sys.argv[0])
        config.PID = os.getpid()
        config.PROJECT = sys.argv[2]

        config.START = sys.argv[3]
        config.SINCE = sys.argv[4]
        config.CHANGED_ONLY = (config.SINCE > config.MIGRATION)

        config.AUDIT_STAGING = True
        config.AUDIT_FROZEN = True
        config.CHECK_TIMESTAMPS = False

        if len(sys.argv) >= 6:
            if sys.argv[5] == '--staging':
                config.AUDIT_FROZEN = False
            elif sys.argv[5] == '--frozen':
                config.AUDIT_STAGING = False
            elif sys.argv[5] == '--timestamps':
                config.CHECK_TIMESTAMPS = True
            else:
                raise Exception("Unrecognized argument: " % sys.argv[5])

        if len(sys.argv) == 7:
            if sys.argv[6] == '--staging':
                config.AUDIT_FROZEN = False
            elif sys.argv[6] == '--frozen':
                config.AUDIT_STAGING = False
            elif sys.argv[6] == '--timestamps':
                config.CHECK_TIMESTAMPS = True
            else:
                raise Exception("Unrecognized argument: " % sys.argv[6])

        if config.AUDIT_STAGING == False and config.AUDIT_FROZEN == False:
            raise Exception("Only one of --staging or --frozen is allowed")

        if [ config.DEBUG == 'true' ]:
            config.LOG_LEVEL = logging.DEBUG
        else:
            config.LOG_LEVEL = logging.INFO

        if '/rest/' in config.METAX_API_ROOT_URL:
            config.METAX_API_VERSION = 1
        else:
            config.METAX_API_VERSION = 3

        if config.DEBUG == 'true':
            sys.stderr.write("--- %s ---\n" % config.SCRIPT)
            sys.stderr.write("HOSTNAME:      %s\n" % socket.gethostname())
            sys.stderr.write("ROOT:          %s\n" % config.ROOT)
            sys.stderr.write("PROJECT:       %s\n" % config.PROJECT)
            sys.stderr.write("DATA_ROOT:     %s\n" % config.STORAGE_OC_DATA_ROOT)
            sys.stderr.write("LOG:           %s\n" % config.LOG)
            sys.stderr.write("LOG_LEVEL:     %s\n" % config.LOG_LEVEL)
            sys.stderr.write("DBHOST:        %s\n" % config.DBHOST)
            sys.stderr.write("DBROUSER:      %s\n" % config.DBROUSER)
            sys.stderr.write("DBNAME:        %s\n" % config.DBNAME)
            sys.stderr.write("METAX_API:     %s\n" % config.METAX_API_ROOT_URL)
            sys.stderr.write("METAX_VERSION: %s\n" % str(config.METAX_API_VERSION))
            sys.stderr.write("ARGS#:         %d\n" % len(sys.argv))
            sys.stderr.write("ARGS:          %s\n" % str(sys.argv))
            sys.stderr.write("PID:           %s\n" % config.PID)
            sys.stderr.write("AUDIT_STAGING: %s\n" % config.AUDIT_STAGING)
            sys.stderr.write("AUDIT_FROZEN:  %s\n" % config.AUDIT_FROZEN)
            sys.stderr.write("CHKTIMESTAMPS: %s\n" % config.CHECK_TIMESTAMPS)
            sys.stderr.write("MIGRATION:     %s\n" % config.MIGRATION)
            sys.stderr.write("MIGRATION_TS:  %s\n" % config.MIGRATION_TS)

        # Convert START ISO timestamp strings to epoch seconds

        start_datetime = dateutil.parser.isoparse(config.START)
        config.START_TS = start_datetime.replace(tzinfo=timezone.utc).timestamp()

        if config.DEBUG == 'true':
            sys.stderr.write("START:         %s\n" % config.START)
            sys.stderr.write("START_DT:      %s\n" % start_datetime.strftime(config.TIMESTAMP_FORMAT))
            sys.stderr.write("START_TS:      %d\n" % config.START_TS)
            start_datetime_check = datetime.utcfromtimestamp(config.START_TS).strftime(config.TIMESTAMP_FORMAT)
            sys.stderr.write("START_TS_CHK:  %s\n" % str(start_datetime_check))

        # Convert SINCE ISO timestamp strings to epoch seconds

        since_datetime = dateutil.parser.isoparse(config.SINCE)
        config.SINCE_TS = since_datetime.replace(tzinfo=timezone.utc).timestamp()

        if config.DEBUG == 'true':
            sys.stderr.write("SINCE:         %s\n" % config.SINCE)
            sys.stderr.write("SINCE_DT:      %s\n" % since_datetime.strftime(config.TIMESTAMP_FORMAT))
            sys.stderr.write("SINCE_TS:      %d\n" % config.SINCE_TS)
            since_datetime_check = datetime.utcfromtimestamp(config.SINCE_TS).strftime(config.TIMESTAMP_FORMAT)
            sys.stderr.write("SINCE_TS_CHK:  %s\n" % str(since_datetime_check))

        # Initialize logging using UTC timestamps

        logging.basicConfig(
            filename=config.LOG,
            level=config.LOG_LEVEL,
            format="%s %s (%s) %s" % ('%(asctime)s', config.SCRIPT, config.PID, '%(message)s'),
            datefmt=config.TIMESTAMP_FORMAT)

        logging.Formatter.converter = time.gmtime

        # Audit the project according to the configured values, analyze any errors, and output a report

        logging.info("START %s %s" % (config.PROJECT, config.START))

        report = audit_project(config)
        analyze_audit_errors(report)
        output_report(report)

        logging.info("DONE")

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
    module_name = 'config.variables'
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


def add_frozen_files(nodes, counts, config):
    """
    Query the IDA database and add all relevant frozen file stats to the auditing data objects
    provided and according to the configured values provided.
    NOTE: must be called before adding Nextcloud or filesystem node details!
    """

    if config.AUDIT_FROZEN == False:
        if config.DEBUG == 'true':
            sys.stderr.write("--- Skipping IDA frozen files...\n")
        return

    if config.DEBUG == 'true':
        sys.stderr.write("--- Adding IDA frozen files...\n")

    # Open database connection

    dblib = psycopg2

    conn = dblib.connect(database=config.DBNAME,
                         user=config.DBROUSER,
                         password=config.DBROPASSWORD,
                         host=config.DBHOST,
                         port=config.DBPORT)

    cur = conn.cursor()

    # Select all records for actively frozen files which frozen before the START
    # timestamp (we also grab and record the metadata and replicated timestamps,
    # to decide whether we should include those files in comparisons with Metax
    # and the replication)

    query = "SELECT pathname, size, modified, pid, checksum, frozen, replicated FROM %sida_frozen_file \
             WHERE project = '%s' \
             AND removed IS NULL \
             AND cleared IS NULL \
             AND frozen IS NOT NULL \
             AND '%s' < frozen \
             AND frozen < '%s' " % (config.DBTABLEPREFIX, config.PROJECT, config.SINCE, config.START)

    if config.DEBUG == 'true':
        sys.stderr.write("QUERY: %s\n" % re.sub(r'\s+', ' ', query.strip()))

    cur.execute(query)
    rows = cur.fetchall()

    # Construct IDA frozen file object for all selected nodes

    for row in rows:

        #if config.DEBUG == 'true':
        #    sys.stderr.write("ida_frozen: %s\n" % (str(row)))

        checksum = str(row[4])
        if checksum.startswith('sha256:'):
            checksum = checksum[7:]

        pathname = "frozen%s" % row[0]

        node_details = {
            'type': 'file',
            'size': row[1],
            'modified': row[2],
            'pid': row[3],
            'checksum': checksum,
            'frozen': row[5],
            'replicated': row[6]
        }

        try:
            node = nodes[pathname]
            node['ida'] = node_details
        except KeyError:
            node = {}
            node['ida'] = node_details
            nodes[pathname] = node

        counts['frozenFileCount'] = counts['frozenFileCount'] + 1

        if config.DEBUG == 'true':
            sys.stderr.write("%s: ida: %d %s\n" % (config.PROJECT, counts['frozenFileCount'], pathname))

    # Close database connection
    conn.close()


def add_metax_files(nodes, counts, config):
    """
    Query the Metax API and add all relevant frozen file stats to the auditing data objects
    provided and according to the configured values provided.
    NOTE: must be called before adding Nextcloud or filesystem node details!
    """

    if config.AUDIT_FROZEN == False:
        if config.DEBUG == 'true':
            sys.stderr.write("--- Skipping Metax frozen files...\n")
        return

    if config.DEBUG == 'true':
        sys.stderr.write("--- Adding Metax frozen files...\n")

    if config.METAX_API_VERSION >= 3:
        url_base = "%s/files?project=%s&storage_service=ida&frozen__gt=%s&limit=%d" % (
            config.METAX_API_ROOT_URL,
            config.PROJECT,
            config.SINCE,
            config.MAX_FILE_COUNT
        )
    else:
        # Unfortunately, in v1 of the Metax API we have to retrieve all frozen files and can't filter by SINCE
        url_base = "%s/files?file_storage=urn:nbn:fi:att:file-storage-ida&ordering=id&project_identifier=%s&limit=%d" % (
            config.METAX_API_ROOT_URL,
            config.PROJECT,
            config.MAX_FILE_COUNT
        )

    offset = 0
    done = False # we are done when Metax returns less than the specified limit of files

    while not done:

        url = "%s&offset=%d" % (url_base, offset)

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY URL: %s\n" % url)

        try:

            if config.METAX_API_VERSION >= 3:
                # TODO: add bearer token header when supported
                response = requests.get(url)
            else:
                response = requests.get(url, auth=(config.METAX_API_USER, config.METAX_API_PASS))

            if response.status_code != 200:
                raise Exception("Failed to retrieve frozen file metadata from Metax for project %s: %d" % (config.PROJECT, response.status_code))

            response_data = response.json()

            if config.DEBUG == 'true':
                sys.stderr.write("QUERY RESPONSE: %s\n" % json.dumps(response_data))

            files = response_data['results']

        except Exception as error:
            raise Exception("Failed to retrieve frozen file metadata from Metax for project %s: %s" % (config.PROJECT, str(error)))

        for file in files:

            if config.DEBUG == 'true':
                sys.stderr.write("FILE: %s\n" % json.dumps(file))
                sys.stderr.write("REMOVED: %s\n" % json.dumps(file.get('removed')))

            # Even though Metax should not return records for removed files, we check just to be absolutely sure...
            if not file.get('removed', False):

                if config.METAX_API_VERSION >= 3:

                    pathname = "frozen%s" % file['pathname']
                    modified = datetime.utcfromtimestamp(dateutil.parser.isoparse(file['modified']).timestamp()).strftime(config.TIMESTAMP_FORMAT)
                    frozen = datetime.utcfromtimestamp(dateutil.parser.isoparse(file['frozen']).timestamp()).strftime(config.TIMESTAMP_FORMAT)

                    checksum = str(file['checksum'])
                    if checksum.startswith('sha256:'):
                        checksum = checksum[7:]

                    node_details = {
                        'type': 'file',
                        'size': file['size'],
                        'pid': file['storage_identifier'],
                        'checksum': checksum,
                        'modified': modified,
                        'frozen': frozen
                    }

                    if config.DEBUG == 'true':
                        sys.stderr.write("NODE: %s %s\n" % (pathname, json.dumps(node_details)))

                    try:
                        node = nodes[pathname]
                        node['metax'] = node_details
                    except KeyError:
                        node = {}
                        node['metax'] = node_details
                        nodes[pathname] = node

                    counts['metaxFileCount'] = counts['metaxFileCount'] + 1

                else:

                    frozen = datetime.utcfromtimestamp(dateutil.parser.isoparse(file['file_frozen']).timestamp()).strftime(config.TIMESTAMP_FORMAT)

                    # Only continue for files frozen after SINCE
                    if config.SINCE < frozen:

                        pathname = "frozen%s" % file['file_path']
                        modified = datetime.utcfromtimestamp(dateutil.parser.isoparse(file['file_modified']).timestamp()).strftime(config.TIMESTAMP_FORMAT)

                        try:
                            checksum = str(file['checksum_value'])
                        except Exception as error: # temp workaround for Metax bug
                            csobject = file['checksum']
                            checksum = str(csobject['value'])
                        if checksum.startswith('sha256:'):
                            checksum = checksum[7:]

                        node_details = {
                            'type': 'file',
                            'size': file['byte_size'],
                            'pid': file['identifier'],
                            'checksum': checksum,
                            'modified': modified,
                            'frozen': frozen
                        }

                        if config.DEBUG == 'true':
                            sys.stderr.write("NODE: %s %s\n" % (pathname, json.dumps(node_details)))

                        try:
                            node = nodes[pathname]
                            node['metax'] = node_details
                        except KeyError:
                            node = {}
                            node['metax'] = node_details
                            nodes[pathname] = node

                        counts['metaxFileCount'] = counts['metaxFileCount'] + 1

        if len(files) < config.MAX_FILE_COUNT:
            done = True
        else:
            offset = offset + config.MAX_FILE_COUNT


def add_nextcloud_nodes(nodes, counts, config):
    """
    Query the Nextcloud database and add all relevant node stats to the auditing data objects
    provided and according to the configured values provided.
    NOTE: must be called after adding IDA and Metax node details, and before adding filesystem details
    """

    file_count = 0

    if config.DEBUG == 'true':
        sys.stderr.write("--- Adding nextcloud nodes...\n")

    # Open database connection

    dblib = psycopg2

    conn = dblib.connect(database=config.DBNAME,
                         user=config.DBROUSER,
                         password=config.DBROPASSWORD,
                         host=config.DBHOST,
                         port=config.DBPORT)

    cur = conn.cursor()

    # Retrieve PSO storage id for project

    query = "SELECT numeric_id FROM %sstorages \
             WHERE id = 'home::%s%s' \
             LIMIT 1" % (config.DBTABLEPREFIX, config.PROJECT_USER_PREFIX, config.PROJECT)

    if config.DEBUG == 'true':
        sys.stderr.write("QUERY: %s\n" % re.sub(r'\s+', ' ', query.strip()))

    cur.execute(query)
    rows = cur.fetchall()

    if len(rows) != 1:
        raise Exception("Failed to retrieve storage id for project %s" % config.PROJECT)

    storage_id = rows[0][0]

    if config.DEBUG == 'true':
        sys.stderr.write("STORAGE_ID:    %d\n" % (storage_id))

    # If CHANGED_ONLY is true, first populate any Nextcloud node details based on already populated node pathnames
    # from IDA and Metax contexts, if they exist, as frozen file nodes will not have any timestamp updates in the
    # Nextcloud cache by which they can be detected and added...

    if config.CHANGED_ONLY:

        for pathname, node in list(nodes.items()):

            if config.DEBUG == 'true':
                sys.stderr.write("%s: existing: node pathname: %s\n" % (config.PROJECT, pathname))

            # If the node Nextcloud details have not already been recorded...
            if 'nextcloud' not in node:

                if pathname.startswith('frozen/'):
                    path = "files/%s/%s" % (config.PROJECT, pathname[7:])
                else:
                    path = "files/%s+/%s" % (config.PROJECT, pathname[8:])

                query = "SELECT cache.path, cache.mimetype, cache.size, cache.mtime, extended.upload_time \
                         FROM %sfilecache as cache LEFT JOIN %sfilecache_extended as extended \
                         ON cache.fileid = extended.fileid \
                         WHERE cache.storage = %d \
                         AND cache.path = '%s'" % (
                             config.DBTABLEPREFIX,
                             config.DBTABLEPREFIX,
                             storage_id,
                             path
                        )

                if config.DEBUG == 'true':
                    sys.stderr.write("QUERY: %s\n" % re.sub(r'\s+', ' ', query.strip()))

                cur.execute(query)
                row = cur.fetchone()

                if row:

                    if config.DEBUG == 'true':
                        sys.stderr.write("filecache: %s\n" % (str(row)))

                    node_type = 'file'

                    if row[1] == 2:
                        node_type = 'folder'

                    modified = datetime.utcfromtimestamp(row[3]).strftime(config.TIMESTAMP_FORMAT)

                    if node_type == 'file':

                        # If there is no upload timestamp, use the latest of the modification or migration timestamp
                        if row[4] in [ None, '', 0 ]:
                            uploaded = datetime.utcfromtimestamp(max(row[3], config.MIGRATION_TS)).strftime(config.TIMESTAMP_FORMAT)
                        else:
                            uploaded = datetime.utcfromtimestamp(row[4]).strftime(config.TIMESTAMP_FORMAT)

                        if config.DEBUG == 'true':
                            file_count = file_count + 1

                        node_details = {'type': node_type, 'size': row[2], 'modified': modified, 'uploaded': uploaded}

                    else: # node_type == 'folder'

                        node_details = {'type': node_type, 'modified': modified}

                    node['nextcloud'] = node_details

                    counts['nextcloudNodeCount'] = counts['nextcloudNodeCount'] + 1

                    if config.DEBUG == 'true':
                        sys.stderr.write("%s: nextcloud: %d %s\n" % (config.PROJECT, file_count, pathname))

    # Add all relevant Nexcloud node records not already recorded

    if config.AUDIT_STAGING == False:
        path_pattern = "^files/%s/" % config.PROJECT     # select file pathnames only in frozen area
    elif config.AUDIT_FROZEN == False:
        path_pattern = "^files/%s\+/" % config.PROJECT   # select file pathnames only in staging area
    else:
        path_pattern = "^files/%s\+?/" % config.PROJECT  # select file pathnames in both staging and frozen areas

    # If CHANGED_ONLY is true, limit query to nodes with either modified or upload timestamp later than
    # SINCE_TS, else limit query to nodes with either no upload timestamp or upload earlier than START_TS

    if config.CHANGED_ONLY:
        query = "SELECT cache.path, cache.mimetype, cache.size, cache.mtime, extended.upload_time \
                 FROM %sfilecache as cache LEFT JOIN %sfilecache_extended as extended \
                 ON cache.fileid = extended.fileid \
                 WHERE cache.storage = %d \
                 AND cache.path ~ '%s' \
                 AND ( \
                        ( cache.mtime > %d AND cache.mtime < %d ) \
                     OR  \
                        ( extended.upload_time IS NOT NULL AND extended.upload_time > %d AND extended.upload_time < %d ) \
                     )" % (
                     config.DBTABLEPREFIX,
                     config.DBTABLEPREFIX,
                     storage_id,
                     path_pattern,
                     config.SINCE_TS,
                     config.START_TS,
                     config.SINCE_TS,
                     config.START_TS
                )
    else:
        query = "SELECT cache.path, cache.mimetype, cache.size, cache.mtime, extended.upload_time \
                 FROM %sfilecache as cache LEFT JOIN %sfilecache_extended as extended \
                 ON cache.fileid = extended.fileid \
                 WHERE cache.storage = %d \
                 AND cache.path ~ '%s' \
                 AND cache.mtime < %d \
                 AND ( extended.upload_time IS NULL OR extended.upload_time < %d )" % (
                     config.DBTABLEPREFIX,
                     config.DBTABLEPREFIX,
                     storage_id,
                     path_pattern,
                     config.START_TS,
                     config.START_TS
                )

    if config.DEBUG == 'true':
        sys.stderr.write("QUERY: %s\n" % re.sub(r'\s+', ' ', query.strip()))

    cur.execute(query)
    rows = cur.fetchall()

    # Construct auditing data object for all selected nodes

    for row in rows:

        if config.DEBUG == 'true':
            sys.stderr.write("filecache: %s\n" % (str(row)))

        pathname = row[0][5:]
        project_name_len = len(config.PROJECT)
        if pathname[(project_name_len + 1)] == '+':
            pathname = "staging/%s" % pathname[(project_name_len + 3):]
        else:
            pathname = "frozen/%s" % pathname[(project_name_len + 2):]

        node = nodes.get(pathname)

        if (node is None) or ('nextcloud' not in node):

            node_type = 'file'

            if row[1] == 2:
                node_type = 'folder'

            modified = datetime.utcfromtimestamp(row[3]).strftime(config.TIMESTAMP_FORMAT)

            if node_type == 'file':

                # If there is no upload timestamp, use the latest of the modification or migration timestamp
                if row[4] in [ None, '', 0 ]:
                    uploaded = datetime.utcfromtimestamp(max(row[3], config.MIGRATION_TS)).strftime(config.TIMESTAMP_FORMAT)
                else:
                    uploaded = datetime.utcfromtimestamp(row[4]).strftime(config.TIMESTAMP_FORMAT)
    
                if config.DEBUG == 'true':
                    file_count = file_count + 1

                node_details = {'type': node_type, 'size': row[2], 'modified': modified, 'uploaded': uploaded}

            else: # node_type == 'folder'

                node_details = {'type': node_type, 'modified': modified}

            if node:
                node['nextcloud'] = node_details
            else:
                node = {}
                node['nextcloud'] = node_details
                nodes[pathname] = node

            counts['nextcloudNodeCount'] = counts['nextcloudNodeCount'] + 1

            if config.DEBUG == 'true':
                sys.stderr.write("%s: nextcloud: %d %s\n" % (config.PROJECT, file_count, pathname))

    # If CHANGED_ONLY is true, the query above only selected changed nodes, but we also want all ancestor
    # folders which were not marked as changed but should still exist, so populate any/all ancestor
    # folder node details for files selected

    if config.CHANGED_ONLY:

        nextcloud_file_pathnames = []

        # Extract only pathnames corresponding to Nextcloud file nodes
        for pathname, node in nodes.items():
            node_details = node.get('nextcloud')
            if node_details and node_details.get('type') == 'file':
                nextcloud_file_pathnames.append(pathname)

        for pathname in nextcloud_file_pathnames:

            path_levels = pathname.split(os.sep)
            area = path_levels[0]

            # Iterate top-down over pathname ancestor directory levels, adding node at each pathname level as needed...
            for i in range(2, len(path_levels)):

                level_pathname = os.sep.join(path_levels[1:i])
                node_pathname = "%s/%s" % (area, level_pathname)
                node = nodes.get(node_pathname)

                if config.DEBUG == 'true':
                    sys.stderr.write("%s: nextcloud: ancestor folder pathname: %s\n" % (config.PROJECT, node_pathname))

                # If the node filesystem details have not already been recorded...
                if (node is None) or ('nextcloud' not in node):

                    if area == 'frozen':
                        path_pattern = "files/%s/%s" % (config.PROJECT, level_pathname)
                    else:
                        path_pattern = "files/%s+/%s" % (config.PROJECT, level_pathname)

                    query = "SELECT path, mtime \
                             FROM %sfilecache \
                             WHERE storage = %d \
                             AND mimetype = 2 \
                             AND path = '%s' \
                             ORDER BY mtime DESC LIMIT 1" % (
                                 config.DBTABLEPREFIX,
                                 storage_id,
                                 path_pattern
                            )

                    if config.DEBUG == 'true':
                        sys.stderr.write("QUERY: %s\n" % re.sub(r'\s+', ' ', query.strip()))

                    cur.execute(query)
                    row = cur.fetchone()

                    #if config.DEBUG == 'true':
                    #    sys.stderr.write("filecache: %s\n" % (str(row)))

                    if row:

                        modified = datetime.utcfromtimestamp(row[1]).strftime(config.TIMESTAMP_FORMAT)
                        node_details = {'type': 'folder', 'modified': modified}

                        if node:
                            node['nextcloud'] = node_details
                        else:
                            node = {}
                            node['nextcloud'] = node_details
                            nodes[node_pathname] = node

                        counts['nextcloudNodeCount'] = counts['nextcloudNodeCount'] + 1

                        if config.DEBUG == 'true':
                            sys.stderr.write("%s: nextcloud: ancestor folder: %s\n" % (config.PROJECT, node_pathname))

    # Close database connection
    conn.close()


def add_filesystem_nodes(nodes, counts, config):
    """
    Add all relevant filesystem node stats to the auditing data objects provided and according
    to the configured values provided, limited to nodes modified before the start of the auditing
    NOTE: must be called last, after adding node details from all other contexts
    """

    if config.DEBUG == 'true':
        sys.stderr.write("--- Adding filesystem nodes...\n")

    file_count = 0

    pso_root = "%s/%s%s/" % (config.STORAGE_OC_DATA_ROOT, config.PROJECT_USER_PREFIX, config.PROJECT)

    # If CHANGED_ONLY is true, populate filesystem node details based on already populated node pathnames
    # from all other contexts, else crawl the filesystem

    if config.CHANGED_ONLY:

        for pathname in list(nodes.keys()):

            if config.DEBUG == 'true':
                sys.stderr.write("%s: existing: node pathname: %s\n" % (config.PROJECT, pathname))

            path_levels = pathname.split(os.sep)

            area = path_levels[0]

            # Iterate top-down over pathname levels, adding node at each pathname level as needed...
            for i in range(2, len(path_levels) + 1):

                level_pathname = os.sep.join(path_levels[1:i])
                node_pathname = "%s/%s" % (area, level_pathname)
                node = nodes.get(node_pathname)

                if config.DEBUG == 'true':
                    sys.stderr.write("%s: filesystem: node pathname: %s\n" % (config.PROJECT, node_pathname))

                # If the node filesystem details have not already been recorded...
                if (node is None) or ('filesystem' not in node):

                    if area == 'frozen':
                        full_pathname = "%sfiles/%s/%s" % (pso_root, config.PROJECT, level_pathname)
                    else:
                        full_pathname = "%sfiles/%s+/%s" % (pso_root, config.PROJECT, level_pathname)

                    if config.DEBUG == 'true':
                        sys.stderr.write("%s: filesystem: full pathname: %s\n" % (config.PROJECT, full_pathname))

                    path = Path(full_pathname)

                    if path.exists():

                        node_stats = path.stat()
                        modified = node_stats.st_mtime

                        if modified < config.START_TS:

                            node_type = 'file'
                            modified = datetime.utcfromtimestamp(modified).strftime(config.TIMESTAMP_FORMAT)
                            size = node_stats.st_size

                            if path.is_file():
                                file_count = file_count + 1
                                node_details = {'type': node_type, 'size': size, 'modified': modified}
                            else:
                                node_type = 'folder'
                                node_details = {'type': node_type, 'modified': modified}

                            if node:
                                node['filesystem'] = node_details
                            else:
                                node = {}
                                node['filesystem'] = node_details
                                nodes[node_pathname] = node

                            counts['filesystemNodeCount'] = counts['filesystemNodeCount'] + 1

                            if config.DEBUG == 'true':
                                sys.stderr.write("%s: filesystem: %d %s %s\n" % (config.PROJECT, file_count, node_type, node_pathname))

    else:

        if config.AUDIT_STAGING == False:
            find_root = "files/%s/" % config.PROJECT     # select file pathnames only in frozen area
            min_depth = '1'
        elif config.AUDIT_FROZEN == False:
            find_root = "files/%s\+/" % config.PROJECT   # select file pathnames only in staging area
            min_depth = '1'
        else:
            find_root = 'files'                          # select file pathnames in both staging and frozen areas
            min_depth = '2'

        command = "cd %s; find %s -mindepth %s -printf \"%%Y\\t%%s\\t%%T@\\t%%p\\n\"" % (pso_root, find_root, min_depth)

        if config.DEBUG == 'true':
            sys.stderr.write("COMMAND: %s\n" % command)

        pipe = Popen(command, shell=True, stdout=PIPE)

        pattern = re.compile("^(?P<type>[^\t])+\t(?P<size>[^\t]+)\t(?P<modified>[^\t]+)\t(?P<pathname>.+)$")

        for line in pipe.stdout:

            match = pattern.match(line.decode(sys.stdout.encoding))
            values = match.groupdict()

            if len(values) != 4:
                raise Exception("Parse error for output from find command: %s" % line.decode(sys.stdout.encoding))

            type = str(values['type'])
            size = int(values['size'])
            modified = int(float(values['modified']))
            pathname = str(values['pathname'])

            if modified < config.START_TS:

                pathname = pathname[5:]
                project_name_len = len(config.PROJECT)
                if pathname[(project_name_len + 1)] == '+':
                    pathname = "staging/%s" % pathname[(project_name_len + 3):]
                else:
                    pathname = "frozen/%s" % pathname[(project_name_len + 2):]

                node_type = 'file'

                modified = datetime.utcfromtimestamp(modified).strftime(config.TIMESTAMP_FORMAT)

                if type == 'd':
                    node_type = 'folder'

                if node_type == 'file':
                    if config.DEBUG == 'true':
                        file_count = file_count + 1
                    node_details = {'type': node_type, 'size': size, 'modified': modified}
                else:
                    node_details = {'type': node_type, 'modified': modified}

                try:
                    node = nodes[pathname]
                    node['filesystem'] = node_details
                except KeyError:
                    node = {}
                    node['filesystem'] = node_details
                    nodes[pathname] = node

                counts['filesystemNodeCount'] = counts['filesystemNodeCount'] + 1

                if config.DEBUG == 'true':
                    sys.stderr.write("%s: filesystem: %d %s %s\n" % (config.PROJECT, file_count, node_type, pathname))


def audit_project(config):
    """
    Audit a project according to the configured values provided and return a report of the results
    """

    counts = {'nextcloudNodeCount': 0, 'filesystemNodeCount': 0, 'frozenFileCount': 0, 'metaxFileCount': 0}
    nodes = SortedDict({})

    # Populate auditing data objects for all nodes in scope according to the configured values provided
    # NOTE: Order in which node details is populated is critical

    add_frozen_files(nodes, counts, config)
    add_metax_files(nodes, counts, config)
    add_nextcloud_nodes(nodes, counts, config)  # must be second to last
    add_filesystem_nodes(nodes, counts, config) # must be last

    if config.DEBUG == 'true':
        sys.stderr.write("NODES: %s\n" % json.dumps(nodes, indent=4))

    # Iterate over all nodes, logging and reporting all errors

    invalidNodes = SortedDict({})
    invalidNodeCount = 0
    file_count = 0

    for pathname, node in nodes.items():

        errors = SortedDict({})

        # Determine whether the node is in the frozen area based on the pathname

        is_frozen_area_pathname = False

        if pathname[:1] == 'f':
            is_frozen_area_pathname = True

        # Determine where the node exists

        try:
            filesystem = node['filesystem']
        except:
            filesystem = False

        try:
            nextcloud = node['nextcloud']
        except:
            nextcloud = False

        try:
            ida = node['ida']
        except:
            ida = False

        try:
            metax = node['metax']
        except:
            metax = False

        if (nextcloud and nextcloud['type'] == 'file') or (filesystem and filesystem['type'] == 'file') or (ida and ida['type'] == 'file') or (metax and metax['type'] == 'file'):
            file_count = file_count + 1

        if config.DEBUG == 'true':
            sys.stderr.write("%s: auditing: %d %s\n" % (config.PROJECT, file_count, pathname))

        # Check that node exists in both filesystem and Nextcloud, and with same type

        if filesystem and not nextcloud:
            errors['Node does not exist in Nextcloud'] = True

        if nextcloud and not filesystem:
            errors['Node does not exist in filesystem'] = True

        if filesystem and nextcloud and filesystem['type'] != nextcloud['type']:
            errors['Node type different for filesystem and Nextcloud'] = True

        # If filesystem and nextcloud agree node is a file, apply further checks...

        if filesystem and filesystem['type'] == 'file' and nextcloud and nextcloud['type'] == 'file':

            if filesystem and nextcloud and filesystem['size'] != nextcloud['size']:
                errors['Node size different for filesystem and Nextcloud'] = True

            if config.CHECK_TIMESTAMPS == True:
                if filesystem and nextcloud and filesystem['modified'] != nextcloud['modified']:
                    errors['Node modification timestamp different for filesystem and Nextcloud'] = True

        # If pathname is in the frozen area, and is known to either Nextcloud or the filesystem
        # as a file; check that the file is registered both as frozen by the IDA app and is published
        # to metax, is also known as a file by both the filesystem and Nextcloud, is replicated properly,
        # and that all relevant file details agree.

        if is_frozen_area_pathname and (ida or metax or (filesystem and filesystem['type'] == 'file') or (nextcloud and nextcloud['type'] == 'file')):

            # check if IDA details exist for frozen file
            if not ida:
                errors['Node does not exist in IDA'] = True

            # check if metax details exist for frozen file
            if not metax:
                errors['Node does not exist in Metax'] = True

            # check if details exist only in IDA or metax for frozen file
            if not filesystem and not nextcloud:
                errors['Node does not exist in filesystem'] = True
                errors['Node does not exist in Nextcloud'] = True

            # check node type agreement between IDA and filesystem
            if ida and filesystem and filesystem['type'] == 'folder':
                errors['Node type different for filesystem and IDA'] = True

            # check node type agreement between IDA and Nextcloud
            if ida and nextcloud and nextcloud['type'] == 'folder':
                errors['Node type different for Nextcloud and IDA'] = True

            # check node type agreement between metax and filesystem
            if metax and filesystem and filesystem['type'] == 'folder':
                errors['Node type different for filesystem and Metax'] = True

            # check node type agreement between metax and nextcloud
            if metax and nextcloud and nextcloud['type'] == 'folder':
                errors['Node type different for Nextcloud and Metax'] = True

            # if known in both IDA and filesystem, check if file details agree
            if ida and filesystem and filesystem['type'] == 'file':

                if ida['size'] != filesystem['size']:
                    errors['Node size different for filesystem and IDA'] = True

                if config.CHECK_TIMESTAMPS == True:
                    if ida['modified'] != filesystem['modified']:
                        errors['Node modification timestamp different for filesystem and IDA'] = True

            # if known in both IDA and nextcloud, check if file details agree
            if ida and nextcloud and nextcloud['type'] == 'file':

                if ida['size'] != nextcloud['size']:
                    errors['Node size different for Nextcloud and IDA'] = True

                if config.CHECK_TIMESTAMPS == True:
                    if ida['modified'] != nextcloud['modified']:
                        errors['Node modification timestamp different for Nextcloud and IDA'] = True

            # if known in both metax and filesystem, check if file details agree
            if metax and filesystem and filesystem['type'] == 'file':

                if metax['size'] != filesystem['size']:
                    errors['Node size different for filesystem and Metax'] = True

                if config.CHECK_TIMESTAMPS == True:
                    if metax['modified'] != filesystem['modified']:
                        errors['Node modification timestamp different for filesystem and Metax'] = True

            # if known in both metax and nextcloud, check if file details agree
            if metax and nextcloud and nextcloud['type'] == 'file':

                if metax['size'] != nextcloud['size']:
                    errors['Node size different for Nextcloud and Metax'] = True

                if config.CHECK_TIMESTAMPS == True:
                    if metax['modified'] != nextcloud['modified']:
                        errors['Node modification timestamp different for Nextcloud and Metax'] = True

            # if known in both IDA and metax and filesystem, check if file details agree
            if ida and metax:

                if ida['size'] != metax['size']:
                    errors['Node size different for IDA and Metax'] = True

                if config.CHECK_TIMESTAMPS == True:
                    if ida['modified'] != metax['modified']:
                        errors['Node modification timestamp different for IDA and Metax'] = True
                    if ida['frozen'] != metax['frozen']:
                        errors['Node frozen timestamp different for IDA and Metax'] = True

                if ida['checksum'] != metax['checksum']:
                    errors['Node checksum different for IDA and Metax'] = True

                if ida['pid'] != metax['pid']:
                    errors['Node pid different for IDA and Metax'] = True

            # if known in IDA and replication timestamp defined in IDA details, check if file details agree
            if ida:

                replicated = ida.get('replicated', False)

                if replicated == 'None' or replicated == None:
                    replicated = False

                if replicated != False:

                    full_pathname = "%s/projects/%s%s" % (config.DATA_REPLICATION_ROOT, config.PROJECT, pathname[6:])

                    #if config.DEBUG == 'true':
                    #    sys.stderr.write("REPLICATION PATHNAME: %s\n" % full_pathname)

                    path = Path(full_pathname)

                    if path.exists():

                        if path.is_file():

                            fsstat = os.stat(full_pathname)
                            size = fsstat.st_size
                            modified = datetime.utcfromtimestamp(fsstat.st_mtime).strftime(config.TIMESTAMP_FORMAT)

                            node['replication'] = {'type': 'file', 'size': size, 'modified': modified}

                            if ida['size'] != size:
                                errors['Node size different for replication and IDA'] = True

                        else:

                            node['replication'] = {'type': 'folder'}
                            errors['Node type different for replication and IDA'] = True

                    else:
                        errors['Node does not exist in replication'] = True

        # If any errors were detected, add the node to the set of invalid nodes
        # and increment the invalid node count

        if len(errors) > 0:
            node['errors'] = list(errors.keys())
            invalidNodes[pathname] = node
            invalidNodeCount = invalidNodeCount + 1

            if config.DEBUG == 'true':
                for error in node['errors']:
                    sys.stderr.write("Error: %s\n" % error)

    report = {}
    report['project'] = config.PROJECT
    report['start'] = config.START
    report['end'] = datetime.utcnow().strftime(config.TIMESTAMP_FORMAT)
    if config.SINCE == "1970-01-01T00:00:00Z":
        report['changedSince'] = None
    else:
        report['changedSince'] = config.SINCE
    report['auditStaging'] = config.AUDIT_STAGING
    report['auditFrozen'] = config.AUDIT_FROZEN
    report['checkTimestamps'] = config.CHECK_TIMESTAMPS
    report['filesystemNodeCount'] = counts['filesystemNodeCount']
    report['nextcloudNodeCount'] = counts['nextcloudNodeCount']
    report['frozenFileCount'] = counts['frozenFileCount']
    report['metaxFileCount'] = counts['metaxFileCount']
    report['invalidNodeCount'] = invalidNodeCount
    report['invalidNodes'] = invalidNodes

    return report


def get_node_type(node):
    node_type = None
    for context in [ 'filesystem', 'nextcloud', 'ida', 'metax' ]:
        context_details = node.get(context)
        if context_details:
            node_type = context_details.get('type')
        if node_type:
            return node_type
    raise Exception("Failed to determine node type")


def get_oldest_timestamp(node):
    oldest_timestamp = None
    for context in [ 'filesystem', 'nextcloud', 'ida', 'metax' ]:
        context_details = node.get(context)
        if context_details:
            node_modified = context_details.get('modified')
            if node_modified and (oldest_timestamp == None or node_modified < oldest_timestamp):
                oldest_timestamp = node_modified
    return oldest_timestamp


def get_newest_timestamp(node):
    newest_timestamp = None
    for context in [ 'filesystem', 'nextcloud', 'ida', 'metax' ]:
        context_details = node.get(context)
        if context_details:
            node_modified = context_details.get('modified')
            node_uploaded = context_details.get('uploaded')
            node_frozen = context_details.get('frozen')
            if node_modified and (newest_timestamp == None or node_modified > newest_timestamp):
                newest_timestamp = node_modified
            if node_uploaded and (newest_timestamp == None or node_uploaded > newest_timestamp):
                newest_timestamp = node_uploaded
            if node_frozen and (newest_timestamp == None or node_frozen > newest_timestamp):
                newest_timestamp = node_frozen
    return newest_timestamp


def get_node_key(node):
    return "%s_%s" % (node.get('start', '0000-00-00'), node['pathname'])


def add_node_error_entry(node_errors_dict, node_error, node_type, node_location, node_entry):
    node_error_dict = node_errors_dict.get(node_error, {})
    if node_type == 'file':
        node_type_dict = node_error_dict.get('files', {})
    else:
        node_type_dict = node_error_dict.get('folders', {})
    if node_location == 'staging':
        node_location_dict = node_type_dict.get('staging', {})
    else:
        node_location_dict = node_type_dict.get('frozen', {})
    nodes = node_location_dict.get('nodes', SortedList([], key=get_node_key))
    nodes.add(node_entry)
    node_location_dict['nodes'] = nodes
    node_type_dict[node_location] = node_location_dict
    if node_type == 'file':
        node_error_dict['files'] = node_type_dict
    else:
        node_error_dict['folders'] = node_type_dict
    node_errors_dict[node_error] = node_error_dict


def analyze_audit_errors(report):

    oldest = '9999-99-99'
    newest = '0000-00-00'
    errors = SortedDict({})

    nodes = report['invalidNodes']

    # for each invalid node in log file data:
    #     get node type ('file' or 'folder')
    #     get node location ('staging' or 'frozen')
    #     get node pathname
    #     get date from oldest timestamp associated with node
    #     get date from newest timestamp associated with node
    #     for each invalid node error:
    #         if errors[error][type][location]['nodes'] is None:
    #             initialize errors[error][type][location]['nodes'] to SortedList
    #         create node object { 'start': oldest, 'end': newest, 'pathname': pathname }
    #         append node object to analysis[error][type][location]['nodes']
    #         if the oldest timestamp for node is older than oldest:
    #             set oldest to oldest timestamp for node
    #         if the newest timestamp for node is newer than newest:
    #             set newest to newest timestamp for node

    for pathname in nodes:
        node = nodes[pathname]
        node_type = get_node_type(node)
        if pathname.startswith('staging/'):
            node_location = 'staging'
        else:
            node_location = 'frozen'
        node_oldest_timestamp = get_oldest_timestamp(node)
        node_newest_timestamp = get_newest_timestamp(node)

        for error in node.get('errors', []):

            if node_oldest_timestamp and node_newest_timestamp:
                entry = { 'start': node_oldest_timestamp, 'end': node_newest_timestamp, 'pathname': pathname }
            else:
                entry = { 'pathname': pathname }

            add_node_error_entry(errors, error, node_type, node_location, entry)

        if node_oldest_timestamp and node_oldest_timestamp < oldest:
            oldest = node_oldest_timestamp

        if node_newest_timestamp and node_newest_timestamp > newest:
            newest = node_newest_timestamp

    if oldest == '9999-99-99' or newest == '0000-00-00':
        oldest = None
        newest = None

    # get all keys for errors dict objects in analysis dict:
    # for each error key:
    #     get error dict for key
    #     initialize error['node_count'] to zero
    #     get all type dict objects for all keys in error dict:
    #     for each type dict object:
    #         initialize type['node_count'] to zero
    #         get all location dict objects for all keys in type dict:
    #         for each location dict object:
    #             sort objects in location['nodes'] array first by node['start'], then by node['pathname']
    #             count total nodes in location['nodes'] array
    #             store pathname count in location['node_count']
    #             add location node count to type node count
    #         add type node count to error node count
    # record total error node count
    # record total error count

    error_node_count = 0

    for key in errors:
        error_dict = errors.get(key, {})
        for node_type_group in [ 'files', 'folders' ]:
            group_dict = error_dict.get(node_type_group)
            if group_dict:
                group_node_count = 0
                for location in [ 'staging', 'frozen' ]:
                    location_dict = group_dict.get(location)
                    if location_dict:
                        location_node_count = 0
                        nodes_dict = location_dict.get('nodes')
                        if nodes_dict:
                            location_node_count = len(nodes_dict)
                        location_dict['node_count'] = location_node_count
                        group_dict[location] = location_dict
                        group_node_count += location_node_count
                group_dict['node_count'] = group_node_count
                error_dict[node_type_group] = group_dict
                error_node_count += group_node_count

    report['oldest'] = oldest
    report['newest'] = newest
    report['errorNodeCount'] = error_node_count
    report['errorCount'] = len(list(errors.keys()))
    report['errors'] = errors


def output_report(report):

    # Output report

    sys.stdout.write('{\n')
    sys.stdout.write('"project": %s,\n' % json.dumps(report.get('project')))
    sys.stdout.write('"start": %s,\n' % json.dumps(report.get('start')))
    sys.stdout.write('"end": %s,\n' % json.dumps(report.get('end')))
    sys.stdout.write('"changedSince": %s,\n' % json.dumps(report['changedSince']))
    sys.stdout.write('"auditStaging": %s,\n' % json.dumps(report['auditStaging']))
    sys.stdout.write('"auditFrozen": %s,\n' % json.dumps(report['auditFrozen']))
    sys.stdout.write('"checkTimestamps": %s,\n' % json.dumps(report['checkTimestamps']))
    sys.stdout.write('"filesystemNodeCount\": %d,\n' % report.get('filesystemNodeCount', 0))
    sys.stdout.write('"nextcloudNodeCount\": %d,\n' % report.get('nextcloudNodeCount', 0))
    sys.stdout.write('"frozenFileCount\": %d,\n' % report.get('frozenFileCount', 0))
    sys.stdout.write('"metaxFileCount\": %d,\n' % report.get('metaxFileCount', 0))
    sys.stdout.write('"invalidNodeCount": %d,\n' % report.get('invalidNodeCount', 0))
    sys.stdout.write('"errorNodeCount": %d,\n' % report.get('errorNodeCount', 0))
    sys.stdout.write('"errorCount": %d,\n' % report['errorCount'])
    sys.stdout.write('"oldest": %s,\n' % json.dumps(report.get('oldest')))
    sys.stdout.write('"newest": %s,\n' % json.dumps(report.get('newest')))
    output_errors(report)
    output_invalid_nodes(report)
    sys.stdout.write('}\n')


def output_errors(report):

    sys.stdout.write('"errors": {')

    if report['errorCount'] > 0:

        errors = report['errors']
        keys = errors.keys()
        first = True

        for key in keys:
            if 'timestamp' not in key:
                output_error(key, errors[key], first)
                first = False

        for key in keys:
            if 'timestamp' in key:
                output_error(key, errors[key], first)
                first = False

        if not first:
            sys.stdout.write('\n')

    sys.stdout.write('},\n')


def output_error(name, error, first):

    files = error.get('files')
    files_staging = None
    files_frozen = None

    if files:
        files_staging = files.get('staging')
        if files_staging:
            files_staging_nodes = files_staging['nodes']
        files_frozen = files.get('frozen')
        if files_frozen:
            files_frozen_nodes = files_frozen['nodes']

    folders = error.get('folders')
    folders_staging = None
    folders_frozen = None

    if folders:
        folders_staging = folders.get('staging')
        if folders_staging:
            folders_staging_nodes = folders_staging['nodes']
        folders_frozen = folders.get('frozen')
        if folders_frozen:
            folders_frozen_nodes = folders_frozen['nodes']

    if first:
        sys.stdout.write('\n')
    else:
        sys.stdout.write(',\n')

    sys.stdout.write('"%s": {\n' % name)

    if files:
        sys.stdout.write('"files": {\n')
        sys.stdout.write('"node_count": %d,\n' % files.get('node_count', 0))

    if files_staging:
        sys.stdout.write('"staging": {\n')
        sys.stdout.write('"node_count": %d,\n' % files_staging.get('node_count', 0))
        output_nodes(files_staging_nodes)
        sys.stdout.write('}')

    if files_frozen:
        if files_staging:
            sys.stdout.write(',\n')
        sys.stdout.write('"frozen": {\n')
        sys.stdout.write('"node_count": %d,\n' % files_frozen.get('node_count', 0))
        output_nodes(files_frozen_nodes)
        sys.stdout.write('}')

    if files:
        sys.stdout.write('\n}')

    if folders:
        if files:
            sys.stdout.write(',\n')
        sys.stdout.write('"folders": {\n')
        sys.stdout.write('"node_count": %d,\n' % folders.get('node_count', 0))

    if folders_staging:
        sys.stdout.write('"staging": {\n')
        sys.stdout.write('"node_count": %d,\n' % folders_staging.get('node_count', 0))
        output_nodes(folders_staging_nodes)
        sys.stdout.write('}')

    if folders_frozen:
        if folders_staging:
            sys.stdout.write(',\n')
        sys.stdout.write('"frozen": {\n')
        sys.stdout.write('"node_count": %d,\n' % folders_frozen.get('node_count', 0))
        output_nodes(folders_frozen_nodes)
        sys.stdout.write('}')

    if folders:
        sys.stdout.write('\n}\n')

    elif files:
        sys.stdout.write('\n')

    sys.stdout.write('}')


def output_nodes(nodes):

    sys.stdout.write('"nodes": [')
    first_node = True

    for node in nodes:

        if first_node:
            sys.stdout.write("\n")
        else:
            sys.stdout.write(",\n")

        node_start = node.get('start')
        node_end = node.get('end')

        if node_start and node_end:
            sys.stdout.write('{ "start": "%s", "end": "%s", "pathname": "%s" }' % ( node_start, node_end, node['pathname']))
        else:
            sys.stdout.write('{ "pathname": "%s" }' % node['pathname'])

        first_node = False

    sys.stdout.write(']\n')


def output_invalid_nodes(report):

    sys.stdout.write('"invalidNodes": {')

    if report['invalidNodeCount'] > 0:

        first = True

        for pathname, node in report['invalidNodes'].items():

            if first:
                sys.stdout.write('\n')
            else:
                sys.stdout.write(',\n')

            first = False

            sys.stdout.write('%s: {' % str(json.dumps(pathname)))
            sys.stdout.write('\n"errors": %s' % str(json.dumps(node['errors'])))

            try:
                node_details = node['filesystem']
                sys.stdout.write(',\n"filesystem": {')
                sys.stdout.write('\n"type": "%s"' % node_details['type'])
                if node_details['type'] == 'file':
                    try:
                        sys.stdout.write(',\n"size": %d' % node_details['size'])
                    except:
                        pass
                try:
                    sys.stdout.write(',\n"modified": "%s"' % node_details['modified'])
                except:
                    pass
                sys.stdout.write('}')
            except:
                pass

            try:
                node_details = node['nextcloud']
                sys.stdout.write(',\n"nextcloud": {')
                sys.stdout.write('\n"type": "%s"' % node_details['type'])
                if node_details['type'] == 'file':
                    try:
                        sys.stdout.write(',\n"size": %d' % node_details['size'])
                    except:
                        pass
                try:
                    sys.stdout.write(',\n"modified": "%s"' % node_details['modified'])
                except:
                    pass
                sys.stdout.write('\n}')
            except:
                pass

            try:
                node_details = node['ida']
                sys.stdout.write(',\n"ida": {')
                sys.stdout.write('\n"type": "file"')
                try:
                    sys.stdout.write(',\n"size": %d' % node_details['size'])
                except:
                    pass
                try:
                    sys.stdout.write(',\n"pid": "%s"' % node_details['pid'])
                except:
                    pass
                try:
                    sys.stdout.write(',\n"checksum": "%s"' % node_details['checksum'])
                except:
                    pass
                try:
                    sys.stdout.write(',\n"modified": "%s"' % node_details['modified'])
                except:
                    pass
                try:
                    sys.stdout.write(',\n"frozen": "%s"' % node_details['frozen'])
                except:
                    pass
                try:
                    sys.stdout.write(',\n"replicated": "%s"' % node_details['replicated'])
                except:
                    pass
                sys.stdout.write('\n}')
            except:
                pass

            try:
                node_details = node['metax']
                sys.stdout.write(',\n"metax": {')
                sys.stdout.write('\n"type": "file"')
                try:
                    sys.stdout.write(',\n"size": %d' % node_details['size'])
                except:
                    pass
                try:
                    sys.stdout.write(',\n"pid": "%s"' % node_details['pid'])
                except:
                    pass
                try:
                    sys.stdout.write(',\n"checksum": "%s"' % node_details['checksum'])
                except:
                    pass
                try:
                    sys.stdout.write(',\n"modified": "%s"' % node_details['modified'])
                except:
                    pass
                try:
                    sys.stdout.write(',\n"frozen": "%s"' % node_details['frozen'])
                except:
                    pass
                sys.stdout.write('\n}')
            except:
                pass

            try:
                node_details = node['replication']
                sys.stdout.write(',\n"replication": {')
                sys.stdout.write('\n"type": "file"')
                try:
                    sys.stdout.write(',\n"size": %d' % node_details['size'])
                except:
                    pass
                try:
                    sys.stdout.write(',\n"modified": "%s"' % node_details['modified'])
                except:
                    pass
                sys.stdout.write('}')
            except:
                pass

            sys.stdout.write('\n}')

        sys.stdout.write('\n')

    sys.stdout.write('}\n')


if __name__ == "__main__":
    main()
