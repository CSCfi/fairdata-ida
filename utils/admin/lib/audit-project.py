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
from pathlib import Path
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from sortedcontainers import SortedDict
from datetime import datetime, timezone
from time import strftime
from subprocess import Popen, PIPE
from stat import *

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Node contexts:
#
# filesystem    glusterfs filesystem stats
# Nextcloud     Nextcloud database records
# IDA           IDA frozen file records
# Metax         Metax file records

def main():

    try:

        if len(sys.argv) < 4:
            raise Exception('Invalid number of arguments')
    
        # Load service configuration and constants, and add command arguments
        # and global values needed for auditing

        config = load_configuration("%s/config/config.sh" % sys.argv[1])
        constants = load_configuration("%s/lib/constants.sh" % sys.argv[1])

        # If in production, ensure we are not running on uida-man.csc.fi

        if config.IDA_ENVIRONMENT == "PRODUCTION":
            if socket.gethostname().startswith("uida-man"):
                raise Exception ("Do not run project auditing on uida-man.csc.fi!")

        config.STAGING_FOLDER_SUFFIX = constants.STAGING_FOLDER_SUFFIX
        config.PROJECT_USER_PREFIX = constants.PROJECT_USER_PREFIX
        config.SCRIPT = os.path.basename(sys.argv[0])
        config.PID = os.getpid()
        config.PROJECT = sys.argv[2]
        config.START = sys.argv[3]

        #config.DEBUG = 'true' # TEMP HACK

        config.IGNORE_TIMESTAMPS = False
        if len(sys.argv) == 5 and sys.argv[4] == '--ignore-timestamps':
            config.IGNORE_TIMESTAMPS = True

        config.TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

        if [ config.DEBUG == 'true' ]:
            config.LOG_LEVEL = logging.DEBUG
        else:
            config.LOG_LEVEL = logging.INFO
    
        if config.DEBUG == 'true':
            sys.stderr.write("--- %s ---\n" % config.SCRIPT)
            sys.stderr.write("HOSTNAME:      %s\n" % socket.gethostname())
            sys.stderr.write("PROJECT:       %s\n" % config.PROJECT)
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
            sys.stderr.write("START:         %s\n" % config.START)
            sys.stderr.write("IGNORE_TS:     %s\n" % config.IGNORE_TIMESTAMPS)
    
        # Convert START ISO timestamp strings to epoch seconds

        start_datetime = dateutil.parser.isoparse(config.START)
        config.START_TS = start_datetime.replace(tzinfo=timezone.utc).timestamp()

        if config.DEBUG == 'true':
            sys.stderr.write("START_TS:      %d\n" % config.START_TS)
            sys.stderr.write("START_DT:      %s\n" % str(start_datetime))
            start_datetime_check = datetime.utcfromtimestamp(config.START_TS)
            sys.stderr.write("START_DT_CHK:  %s\n" % str(start_datetime_check))

        # Initialize logging using UTC timestamps

        logging.basicConfig(
            filename=config.LOG,
            level=config.LOG_LEVEL,
            format="%s %s (%s) %s" % ('%(asctime)s', config.SCRIPT, config.PID, '%(message)s'),
            datefmt=config.TIMESTAMP_FORMAT)

        logging.Formatter.converter = time.gmtime

        # Audit the project according to the configured values

        audit_project(config)

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


def add_nextcloud_nodes(nodes, counts, config):
    """
    Query the Nextcloud database and add all relevant node stats to the auditing data objects
    provided and according to the configured values provided, limited to nodes modified before
    the auditing started.
    """

    if config.DEBUG == 'true':
        sys.stderr.write("--- Adding nextcloud nodes...\n")
        # Only count and report files in debug progress, because we track how many files are in in project, not nodes/folders/etc.
        fileCount = 0

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

    # Select all records for project nodes created and last modified before START timestamp

    query = "SELECT path, mimetype, size, mtime FROM %sfilecache \
             WHERE storage = %d \
             AND path ~ 'files/%s\+?/' \
             AND mtime < %d" % (config.DBTABLEPREFIX, storage_id, config.PROJECT, config.START_TS)

    if config.DEBUG == 'true':
        sys.stderr.write("QUERY: %s\n" % re.sub(r'\s+', ' ', query.strip()))

    cur.execute(query)
    rows = cur.fetchall()

    # Construct auditing data object for all selected nodes

    for row in rows:

        #if config.DEBUG == 'true':
        #    sys.stderr.write("filecache: %s\n" % (str(row)))

        pathname = row[0][5:]
        project_name_len = len(config.PROJECT)
        if pathname[(project_name_len + 1)] == '+':
            pathname = "staging/%s" % pathname[(project_name_len + 3):]
        else:
            pathname = "frozen/%s" % pathname[(project_name_len + 2):]

        node_type = 'file'
        modified = datetime.utcfromtimestamp(row[3]).strftime(config.TIMESTAMP_FORMAT)

        if row[1] == 2:
            node_type = 'folder'

        if node_type == 'file':
            if config.DEBUG == 'true':
                fileCount = fileCount + 1
            node = {'nextcloud': {'type': node_type, 'size': row[2], 'modified': modified}}
        else:
            node = {'nextcloud': {'type': node_type, 'modified': modified}}

        nodes[pathname] = node

        counts['nextcloudNodeCount'] = counts['nextcloudNodeCount'] + 1

        if config.DEBUG == 'true':
            #sys.stderr.write("%s: nextcloud: %d %s\n%s\n" % (config.PROJECT, fileCount, pathname, json.dumps(nodes[pathname]['nextcloud'], indent=2, sort_keys=True)))
            sys.stderr.write("%s: nextcloud: %d %s\n" % (config.PROJECT, fileCount, pathname))

    # Close database connection and return auditing data object

    conn.close()


def add_filesystem_nodes(nodes, counts, config):
    """
    Crawl the filesystem and add all relevant node stats to the auditing data objects
    provided and according to the configured values provided, limited to nodes modified
    before the start of the auditing
    """

    if config.DEBUG == 'true':
        sys.stderr.write("--- Adding filesystem nodes...\n")
        # Only count and report files in debug progress, because we track how many files are in in project, not nodes/folders/etc.
        fileCount = 0

    pso_root = "%s/%s%s/" % (config.STORAGE_OC_DATA_ROOT, config.PROJECT_USER_PREFIX, config.PROJECT)

    command = "cd %s; find files -mindepth 2 -printf \"%%Y\\t%%s\\t%%T@\\t%%p\\n\"" % (pso_root)

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

        full_pathname = "%s%s" % (pso_root, pathname)

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
                    fileCount = fileCount + 1
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
                #sys.stderr.write("%s: filesystem: %d %s\n%s\n" % (config.PROJECT, fileCount, pathname, json.dumps(nodes[pathname]['filesystem'], indent=2, sort_keys=True)))
                sys.stderr.write("%s: filesystem: %d %s\n" % (config.PROJECT, fileCount, pathname))


def add_frozen_files(nodes, counts, config):
    """
    Query the IDA database and add all relevant frozen file stats to the auditing data objects
    provided and according to the configured values provided, limited to actively frozen files
    which have no pending metadata postprocessing (i.e. only frozen files with metadata timestamps
    and no cleared or removed timestamps, and a metadata timestamp less than the start timestamp)
    """

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
             AND frozen < '%s' " % (config.DBTABLEPREFIX, config.PROJECT, config.START)

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
    
        counts['idaNodeCount'] = counts['idaNodeCount'] + 1

        if config.DEBUG == 'true':
            #sys.stderr.write("%s: ida: %d %s\n%s\n" % (config.PROJECT, counts['idaNodeCount'], pathname, json.dumps(nodes[pathname]['ida'], indent=2, sort_keys=True)))
            sys.stderr.write("%s: ida: %d %s\n" % (config.PROJECT, counts['idaNodeCount'], pathname))

    # Close database connection and return auditing data object

    conn.close()


def add_metax_files(nodes, counts, config):
    """
    Query the Metax API and add all relevant frozen file stats to the auditing data objects
    provided and according to the configured values provided, limited to actively frozen files
    published to metax before the start timestamp.
    """
    
    if config.DEBUG == 'true':
        sys.stderr.write("--- Adding Metax frozen files...\n")

    url_base = "%s/files?fields=file_path,file_modified,file_frozen,byte_size,identifier,checksum_value,removed&file_storage=urn:nbn:fi:att:file-storage-ida&project_identifier=%s&limit=%d" % (config.METAX_API_ROOT_URL, config.PROJECT, config.MAX_FILE_COUNT)

    offset = 0
    done = False # we are done when Metax returns less than the specified limit of files

    while not done: 

        url = "%s&offset=%d" % (url_base, offset)

        if config.DEBUG == 'true':
            sys.stderr.write("QUERY URL: %s\n" % url)

        try:

            response = requests.get(url, auth=(config.METAX_API_USER, config.METAX_API_PASS), verify=False)

            if response.status_code != 200:
                raise Exception("Failed to retrieve frozen file metadata from Metax for project %s: %d" % (config.PROJECT, response.status_code))

            response_data = response.json()
            files = response_data['results']

        except Exception as error:
            raise Exception("Failed to retrieve frozen file metadata from Metax for project %s: %s" % (config.PROJECT, str(error)))

        for file in files:

            if file["removed"] == False:

                #if config.DEBUG == 'true':
                #    sys.stderr.write("metadata:\n%s\n" % json.dumps(file, indent=2, sort_keys=True))

                pathname = "frozen%s" % file["file_path"]

                # Normalize modified and frozen timestamps to ISO UTC format

                modified = datetime.utcfromtimestamp(dateutil.parser.isoparse(file["file_modified"]).timestamp()).strftime(config.TIMESTAMP_FORMAT) 
                frozen = datetime.utcfromtimestamp(dateutil.parser.isoparse(file["file_frozen"]).timestamp()).strftime(config.TIMESTAMP_FORMAT) 
                try:
                    checksum = str(file["checksum_value"])
                except Exception as error: # temp workaround for Metax bug
                    csobject = file["checksum"]
                    checksum = str(csobject["value"])
                if checksum.startswith('sha256:'):
                    checksum = checksum[7:]

                node_details = {
                    'type': 'file',
                    'size': file["byte_size"],
                    'pid': file["identifier"],
                    'checksum': checksum,
                    'modified': modified,
                    'frozen': frozen
                }
    
                try:
                    node = nodes[pathname]
                    node['metax'] = node_details
                except KeyError:
                    node = {}
                    node['metax'] = node_details
                    nodes[pathname] = node
    
                counts['metaxNodeCount'] = counts['metaxNodeCount'] + 1

                if config.DEBUG == 'true':
                    #sys.stderr.write("%s: metax: %d %s\n%s\n" % (config.PROJECT, counts['metaxNodeCount'], pathname, json.dumps(nodes[pathname]['metax'], indent=2, sort_keys=True)))
                    sys.stderr.write("%s: metax: %d %s\n" % (config.PROJECT, counts['metaxNodeCount'], pathname))

        if len(files) < config.MAX_FILE_COUNT:
            done = True
        else:
            offset = offset + config.MAX_FILE_COUNT


def audit_project(config):
    """
    Audit a project according to the configured values provided
    """

    logging.info("START %s %s" % (config.PROJECT, config.START))

    counts = {'nextcloudNodeCount': 0, 'filesystemNodeCount': 0, 'idaNodeCount': 0, 'metaxNodeCount': 0}
    nodes = SortedDict({})

    # Populate auditing data objects for all nodes in scope according to the configured values provided

    add_nextcloud_nodes(nodes, counts, config)
    add_filesystem_nodes(nodes, counts, config)
    add_frozen_files(nodes, counts, config)
    add_metax_files(nodes, counts, config)

    # Iterate over all nodes, logging and reporting all errors

    invalidNodes = SortedDict({})
    invalidNodeCount = 0

    if config.DEBUG == 'true':
        # Only count and report files in debug progress, because we track how many files are in in project, not nodes/folders/etc.
        fileCount = 0

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

        if config.DEBUG == 'true':
            if (nextcloud and nextcloud['type'] == 'file') or (filesystem and filesystem['type'] == 'file') or (ida and ida['type'] == 'file') or (metax and metax['type'] == 'file'):
                fileCount = fileCount + 1
            sys.stderr.write("%s: auditing: %d %s\n" % (config.PROJECT, fileCount, pathname))

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

            if config.IGNORE_TIMESTAMPS == False:
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

                if config.IGNORE_TIMESTAMPS == False:
                    if ida['modified'] != filesystem['modified']:
                        errors['Node modification timestamp different for filesystem and IDA'] = True

            # if known in both IDA and nextcloud, check if file details agree
            if ida and nextcloud and nextcloud['type'] == 'file':

                if ida['size'] != nextcloud['size']:
                    errors['Node size different for Nextcloud and IDA'] = True

                if config.IGNORE_TIMESTAMPS == False:
                    if ida['modified'] != nextcloud['modified']:
                        errors['Node modification timestamp different for Nextcloud and IDA'] = True

            # if known in both metax and filesystem, check if file details agree
            if metax and filesystem and filesystem['type'] == 'file':

                if metax['size'] != filesystem['size']:
                    errors['Node size different for filesystem and Metax'] = True

                if config.IGNORE_TIMESTAMPS == False:
                    if metax['modified'] != filesystem['modified']:
                        errors['Node modification timestamp different for filesystem and Metax'] = True

            # if known in both metax and nextcloud, check if file details agree
            if metax and nextcloud and nextcloud['type'] == 'file':

                if metax['size'] != nextcloud['size']:
                    errors['Node size different for Nextcloud and Metax'] = True

                if config.IGNORE_TIMESTAMPS == False:
                    if metax['modified'] != nextcloud['modified']:
                        errors['Node modification timestamp different for Nextcloud and Metax'] = True

            # if known in both IDA and metax and filesystem, check if file details agree
            if ida and metax:

                if ida['size'] != metax['size']:
                    errors['Node size different for IDA and Metax'] = True

                if config.IGNORE_TIMESTAMPS == False:
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
    
                if replicated == "None" or replicated == None:
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

    # Output report

    sys.stdout.write("{\n")
    sys.stdout.write("\"project\": %s,\n" % str(json.dumps(config.PROJECT)))
    sys.stdout.write("\"ignoreTimestamps\": %s,\n" % json.dumps(config.IGNORE_TIMESTAMPS))
    sys.stdout.write("\"start\": %s,\n" % str(json.dumps(config.START)))
    sys.stdout.write("\"end\": %s,\n" % str(json.dumps(datetime.utcnow().strftime(config.TIMESTAMP_FORMAT))))
    sys.stdout.write("\"filesystemNodeCount\": %d,\n" % counts['filesystemNodeCount'])
    sys.stdout.write("\"nextcloudNodeCount\": %d,\n" % counts['nextcloudNodeCount'])
    sys.stdout.write("\"idaNodeCount\": %d,\n" % counts['idaNodeCount'])
    sys.stdout.write("\"metaxNodeCount\": %d,\n" % counts['metaxNodeCount'])
    sys.stdout.write("\"invalidNodeCount\": %d" % invalidNodeCount)

    if invalidNodeCount > 0:

        first = True

        sys.stdout.write(",\n\"invalidNodes\": {\n")

        for pathname, node in invalidNodes.items():

            if not first:
                sys.stdout.write(",\n")

            first = False

            sys.stdout.write("%s: {" % str(json.dumps(pathname)))
            sys.stdout.write("\n\"errors\": %s" % str(json.dumps(node['errors'])))

            try:
                node_details = node['filesystem']
                sys.stdout.write(",\n\"filesystem\": {")
                sys.stdout.write("\n\"type\": \"%s\"" % node_details['type'])
                if node_details['type'] == 'file':
                    try:
                        sys.stdout.write(",\n\"size\": %d" % node_details['size'])
                    except:
                        pass
                try:
                    sys.stdout.write(",\n\"modified\": \"%s\"" % node_details['modified'])
                except:
                    pass
                sys.stdout.write("}")
            except:
                pass

            try:
                node_details = node['nextcloud']
                sys.stdout.write(",\n\"nextcloud\": {")
                sys.stdout.write("\n\"type\": \"%s\"" % node_details['type'])
                if node_details['type'] == 'file':
                    try:
                        sys.stdout.write(",\n\"size\": %d" % node_details['size'])
                    except:
                        pass
                try:
                    sys.stdout.write(",\n\"modified\": \"%s\"" % node_details['modified'])
                except:
                    pass
                sys.stdout.write("\n}")
            except:
                pass

            try:
                node_details = node['ida']
                sys.stdout.write(",\n\"ida\": {")
                sys.stdout.write("\n\"type\": \"file\"")
                try:
                    sys.stdout.write(",\n\"size\": %d" % node_details['size'])
                except:
                    pass
                try:
                    sys.stdout.write(",\n\"pid\": \"%s\"" % node_details['pid'])
                except:
                    pass
                try:
                    sys.stdout.write(",\n\"checksum\": \"%s\"" % node_details['checksum'])
                except:
                    pass
                try:
                    sys.stdout.write(",\n\"modified\": \"%s\"" % node_details['modified'])
                except:
                    pass
                try:
                    sys.stdout.write(",\n\"frozen\": \"%s\"" % node_details['frozen'])
                except:
                    pass
                try:
                    sys.stdout.write(",\n\"replicated\": \"%s\"" % node_details['replicated'])
                except:
                    pass
                sys.stdout.write("\n}")
            except:
                pass

            try:
                node_details = node['metax']
                sys.stdout.write(",\n\"metax\": {")
                sys.stdout.write("\n\"type\": \"file\"")
                try:
                    sys.stdout.write(",\n\"size\": %d" % node_details['size'])
                except:
                    pass
                try:
                    sys.stdout.write(",\n\"pid\": \"%s\"" % node_details['pid'])
                except:
                    pass
                try:
                    sys.stdout.write(",\n\"checksum\": \"%s\"" % node_details['checksum'])
                except:
                    pass
                try:
                    sys.stdout.write(",\n\"modified\": \"%s\"" % node_details['modified'])
                except:
                    pass
                try:
                    sys.stdout.write(",\n\"frozen\": \"%s\"" % node_details['frozen'])
                except:
                    pass
                sys.stdout.write("\n}")
            except:
                pass

            try:
                node_details = node['replication']
                sys.stdout.write(",\n\"replication\": {")
                sys.stdout.write("\n\"type\": \"file\"")
                try:
                    sys.stdout.write(",\n\"size\": %d" % node_details['size'])
                except:
                    pass
                try:
                    sys.stdout.write(",\n\"modified\": \"%s\"" % node_details['modified'])
                except:
                    pass
                sys.stdout.write("}")
            except:
                pass
        
            sys.stdout.write("\n}")

        sys.stdout.write("\n}\n")

    sys.stdout.write("}\n")

    logging.info("DONE")


if __name__ == "__main__":
    main()
